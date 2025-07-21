import json
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

class TradeDatabase:
    """Simple trade database for tracking bot trades and validating positions"""

    def __init__(self, db_file: str = "trading_data/trade_database.json"):
        self.logger = logging.getLogger(__name__)
        self.db_file = db_file
        self.trades = {}
        self._ensure_directory()
        self._load_database()

    def _ensure_directory(self):
        """Ensure the trading_data directory exists"""
        os.makedirs(os.path.dirname(self.db_file), exist_ok=True)

    def _load_database(self):
        """Load trades from database file with bulletproof startup cleanup and recovery"""
        try:
            if os.path.exists(self.db_file):
                with open(self.db_file, 'r') as f:
                    data = json.load(f)
                    self.trades = data.get('trades', {})
                    self.logger.info(f"🛡️ BULLETPROOF: Loaded {len(self.trades)} trades from database")

                    # Bulletproof startup sequence
                    self.logger.info(f"🛡️ BULLETPROOF: Running comprehensive startup verification...")

                    # Step 1: Clean up stale trades
                    self.cleanup_stale_open_trades(hours=6, sync_with_binance=True)

                    # Step 2: Run health check and recovery
                    health_report = self.run_bulletproof_health_check()

                    # Step 3: Log startup summary
                    open_count = len([t for t in self.trades.values() if t.get('trade_status') == 'OPEN'])
                    self.logger.info(f"🛡️ BULLETPROOF STARTUP COMPLETE:")
                    self.logger.info(f"   📊 Total trades: {len(self.trades)}")
                    self.logger.info(f"   🔓 Open trades: {open_count}")
                    self.logger.info(f"   🔧 Issues fixed: {len(health_report.get('fixed_issues', []))}")
                    self.logger.info(f"   ⚠️ Issues remaining: {len(health_report.get('remaining_issues', []))}")

            else:
                self.logger.info("🛡️ BULLETPROOF: Trade database file not found, starting with empty database")
                self.trades = {}
        except Exception as e:
            self.logger.error(f"🚨 BULLETPROOF: Error loading trade database: {e}")
            self.trades = {}

    def _save_database(self):
        """Save trades to database file"""
        try:
            data = {
                'trades': self.trades,
                'last_updated': datetime.now().isoformat()
            }
            with open(self.db_file, 'w') as f:
                json.dump(data, f, indent=2)
            self.logger.debug(f"Saved {len(self.trades)} trades to database")
        except Exception as e:
            self.logger.error(f"Error saving trade database: {e}")

    def add_trade(self, trade_id: str, trade_data: Dict[str, Any]):
        """Add a trade to the database with bulletproof verification and complete data"""
        try:
            # Pre-validation checks
            required_fields = ['strategy_name', 'symbol', 'side', 'quantity', 'entry_price', 'trade_status']
            missing_fields = [field for field in required_fields if field not in trade_data or trade_data[field] is None]
            if missing_fields:
                self.logger.error(f"🚨 BULLETPROOF: Missing required fields {missing_fields} in trade {trade_id}")
                self.logger.error(f"🚨 BULLETPROOF: Trade data received: {trade_data}")
                return False

            # Validate data types and values
            try:
                if not isinstance(trade_data['quantity'], (int, float)) or trade_data['quantity'] <= 0:
                    self.logger.error(f"🚨 BULLETPROOF: Invalid quantity {trade_data['quantity']} in trade {trade_id}")
                    return False

                if not isinstance(trade_data['entry_price'], (int, float)) or trade_data['entry_price'] <= 0:
                    self.logger.error(f"🚨 BULLETPROOF: Invalid entry_price {trade_data['entry_price']} in trade {trade_id}")
                    return False

                if trade_data['side'] not in ['BUY', 'SELL']:
                    self.logger.error(f"🚨 BULLETPROOF: Invalid side {trade_data['side']} in trade {trade_id}")
                    return False

            except (KeyError, TypeError, ValueError) as e:
                self.logger.error(f"🚨 BULLETPROOF: Data validation failed for trade {trade_id}: {e}")
                return False

            # Calculate missing critical fields if not provided
            entry_price = float(trade_data['entry_price'])
            quantity = float(trade_data['quantity'])

            # Calculate position value in USDT
            position_value_usdt = entry_price * quantity
            if 'position_value_usdt' not in trade_data or trade_data['position_value_usdt'] is None:
                trade_data['position_value_usdt'] = position_value_usdt

            # Set default leverage if missing
            if 'leverage' not in trade_data or trade_data['leverage'] is None:
                trade_data['leverage'] = 1  # Default to 1x leverage for spot, will be updated for futures

            # Calculate margin used if missing
            if 'margin_used' not in trade_data or trade_data['margin_used'] is None:
                leverage = trade_data.get('leverage', 1)
                trade_data['margin_used'] = position_value_usdt / leverage

            # Create a complete trade data copy to avoid reference issues
            # Record trade time in Dubai timezone (UTC+4)
            from src.config.global_config import global_config
            if global_config.USE_LOCAL_TIMEZONE:
                dubai_time = datetime.utcnow() + timedelta(hours=global_config.TIMEZONE_OFFSET_HOURS)
                timestamp = dubai_time.isoformat()
            else:
                timestamp = datetime.now().isoformat()

            complete_trade_data = {
                'trade_id': trade_id,
                'strategy_name': str(trade_data['strategy_name']),
                'symbol': str(trade_data['symbol']),
                'side': str(trade_data['side']),
                'quantity': float(trade_data['quantity']),
                'entry_price': float(trade_data['entry_price']),
                'trade_status': str(trade_data['trade_status']),
                'created_at': datetime.now().isoformat(),
                'last_verified': datetime.now().isoformat(),
                'sync_status': 'PENDING_VERIFICATION',

                # MANDATORY fields for complete trade tracking
                'position_value_usdt': float(trade_data['position_value_usdt']),
                'leverage': int(trade_data['leverage']),
                'margin_used': float(trade_data['margin_used']),
                'timestamp': timestamp
            }

            # Add optional fields if present - EXPANDED LIST for complete data capture
            optional_fields = [
                'stop_loss', 'take_profit', 'position_side', 'order_id', 'entry_time', 
                'exit_price', 'exit_reason', 'pnl_usdt', 'pnl_percentage', 'duration_minutes',
                
                # Technical indicators at entry
                'rsi_at_entry', 'macd_at_entry', 'sma_20_at_entry', 'sma_50_at_entry', 
                'volume_at_entry', 'entry_signal_strength',
                
                # Market conditions
                'market_trend', 'volatility_score', 'market_phase',
                
                # Performance metrics
                'risk_reward_ratio', 'max_drawdown',
                
                # Additional metadata
                'recovery_source', 'closure_verified', 'exit_time'
            ]
            for field in optional_fields:
                if field in trade_data and trade_data[field] is not None:
                    complete_trade_data[field] = trade_data[field]

            # Check for existing trade with same position details (prevent duplicates)
            existing_trade_id = self.find_existing_trade_by_position(
                complete_trade_data['symbol'], 
                complete_trade_data['side'], 
                complete_trade_data['quantity'], 
                complete_trade_data['entry_price']
            )

            if existing_trade_id and existing_trade_id != trade_id:
                self.logger.warning(f"🔄 DUPLICATE PREVENTION: Trade {trade_id} matches existing {existing_trade_id}")
                self.logger.warning(f"🔄 UPDATING existing trade instead of creating duplicate")

                # Update existing trade with any new information
                self.trades[existing_trade_id].update(complete_trade_data)
                self.trades[existing_trade_id]['trade_id'] = existing_trade_id  # Keep original ID
                self._save_database()
                return existing_trade_id

            # Add to database WITH IMMEDIATE VERIFICATION
            self.trades[trade_id] = complete_trade_data
            
            # FORCE SAVE IMMEDIATELY
            save_success = False
            try:
                self._save_database()
                save_success = True
            except Exception as save_error:
                self.logger.error(f"🚨 DATABASE SAVE FAILED: {save_error}")
                save_success = False
            
            # VERIFY THE TRADE WAS ACTUALLY SAVED
            if save_success and trade_id in self.trades:
                # Log successful addition with complete data
                self.logger.info(f"🛡️ TRADE ADDED & VERIFIED: {trade_id} | {complete_trade_data['symbol']} | {complete_trade_data['side']}")
                self.logger.info(f"   💰 Value: ${complete_trade_data['position_value_usdt']:.2f} USDT | Margin: ${complete_trade_data['margin_used']:.2f} | Leverage: {complete_trade_data['leverage']}x")
                self.logger.debug(f"🛡️ COMPLETE DATA: {complete_trade_data}")
            else:
                self.logger.error(f"🚨 TRADE SAVE VERIFICATION FAILED: {trade_id}")
                return False

            # Immediate verification with Binance
            if self._verify_trade_on_binance(trade_id, complete_trade_data):
                self.trades[trade_id]['sync_status'] = 'VERIFIED'
                self._save_database()
                self.logger.info(f"🛡️ BULLETPROOF: Added and verified trade {trade_id}")
            else:
                self.logger.warning(f"⚠️ BULLETPROOF: Trade {trade_id} added but verification pending")

            return True
        except Exception as e:
            self.logger.error(f"🚨 BULLETPROOF: Error adding trade to database: {e}")
            import traceback
            self.logger.error(f"🚨 BULLETPROOF: Full traceback: {traceback.format_exc()}")
            return False

    def find_trade_by_position(self, strategy_name: str, symbol: str, side: str, 
                             quantity: float, entry_price: float, tolerance: float = 0.01) -> Optional[str]:
        """Find a trade ID by position details with tolerance for price/quantity matching"""
        try:
            self.logger.debug(f"Searching for trade: {strategy_name} | {symbol} | {side} | Qty: {quantity} | Entry: ${entry_price}")

            for trade_id, trade_data in self.trades.items():
                # If strategy_name is 'UNKNOWN', search across ALL strategies
                # Otherwise, match specific strategy
                strategy_match = (strategy_name == 'UNKNOWN' or 
                                trade_data.get('strategy_name') == strategy_name)

                if (strategy_match and 
                    trade_data.get('symbol') == symbol and
                    trade_data.get('side') == side and
                    trade_data.get('trade_status') == 'OPEN'):  # Only check open trades

                    # Check quantity match with tolerance
                    db_quantity = trade_data.get('quantity', 0)
                    quantity_diff = abs(db_quantity - quantity)
                    quantity_tolerance = max(quantity * tolerance, 0.001)

                    # Check price match with tolerance
                    db_entry_price = trade_data.get('entry_price', 0)
                    price_diff = abs(db_entry_price - entry_price)
                    price_tolerance = max(entry_price * tolerance, 0.01)

                    if quantity_diff <= quantity_tolerance and price_diff <= price_tolerance:
                        self.logger.debug(f"Found matching trade: {trade_id} (strategy: {trade_data.get('strategy_name')})")
                        return trade_id
                    else:
                        self.logger.debug(f"Trade {trade_id} close but not exact match - "
                                        f"Qty diff: {quantity_diff:.6f} (tol: {quantity_tolerance:.6f}), "
                                        f"Price diff: {price_diff:.4f} (tol: {price_tolerance:.4f})")

            search_scope = "all strategies" if strategy_name == 'UNKNOWN' else strategy_name
            self.logger.debug(f"No matching trade found for {search_scope} | {symbol}")
            return None

        except Exception as e:
            self.logger.error(f"Error searching for trade: {e}")
            return None

    def find_existing_trade_by_position(self, symbol: str, side: str, quantity: float, entry_price: float, tolerance: float = 0.02) -> Optional[str]:
        """Find ANY existing trade (regardless of strategy) with matching position details to prevent duplicates"""
        try:
            for trade_id, trade_data in self.trades.items():
                if (trade_data.get('symbol') == symbol and
                    trade_data.get('side') == side and
                    trade_data.get('trade_status') == 'OPEN'):

                    # Check quantity match with tolerance
                    db_quantity = trade_data.get('quantity', 0)
                    quantity_diff = abs(db_quantity - quantity)
                    quantity_tolerance = max(quantity * tolerance, 0.001)

                    # Check price match with tolerance
                    db_entry_price = trade_data.get('entry_price', 0)
                    price_diff = abs(db_entry_price - entry_price)
                    price_tolerance = max(entry_price * tolerance, 0.01)

                    if quantity_diff <= quantity_tolerance and price_diff <= price_tolerance:
                        self.logger.debug(f"Found existing trade: {trade_id} matches position {symbol} {side} {quantity}")
                        return trade_id

            return None

        except Exception as e:
            self.logger.error(f"Error finding existing trade: {e}")
            return None

    def get_trade(self, trade_id: str) -> Optional[Dict[str, Any]]:
        """Get trade data by ID"""
        return self.trades.get(trade_id)

    def update_trade(self, trade_id: str, updates: Dict[str, Any]):
        """Update trade data with bulletproof verification and complete closure data"""
        try:
            if trade_id in self.trades:
                # Add update metadata
                updates['last_updated'] = datetime.now().isoformat()
                updates['last_verified'] = datetime.now().isoformat()

                # Critical status changes require verification and complete data
                if 'trade_status' in updates and updates['trade_status'] == 'CLOSED':
                    trade_data = self.trades[trade_id]

                    # Ensure all closure data is complete
                    if 'exit_price' not in updates or updates['exit_price'] is None:
                        updates['exit_price'] = trade_data.get('entry_price', 0)  # Default to entry price
                        self.logger.warning(f"⚠️ CLOSURE: No exit price provided for {trade_id}, using entry price")

                    # Calculate P&L if not provided
                    if 'pnl_usdt' not in updates or updates['pnl_usdt'] is None:
                        entry_price = trade_data.get('entry_price', 0)
                        exit_price = updates.get('exit_price', entry_price)
                        quantity = trade_data.get('quantity', 0)
                        side = trade_data.get('side', 'BUY')

                        if side == 'BUY':
                            pnl_usdt = (exit_price - entry_price) * quantity
                        else:  # SELL
                            pnl_usdt = (entry_price - exit_price) * quantity

                        updates['pnl_usdt'] = pnl_usdt

                        # Calculate P&L percentage
                        position_value = trade_data.get('position_value_usdt', entry_price * quantity)
                        if position_value > 0:
                            updates['pnl_percentage'] = (pnl_usdt / position_value) * 100
                        else:
                            updates['pnl_percentage'] = 0.0

                    # Calculate duration if not provided
                    if 'duration_minutes' not in updates:
                        entry_time_str = trade_data.get('timestamp', trade_data.get('created_at'))
                        if entry_time_str:
                            try:
                                entry_time = datetime.fromisoformat(entry_time_str.replace('Z', '+00:00'))
                                duration = datetime.now() - entry_time
                                updates['duration_minutes'] = int(duration.total_seconds() / 60)
                            except:
                                updates['duration_minutes'] = 0

                    # Add closure timestamp
                    updates['closed_at'] = datetime.now().isoformat()

                    # Verify closure with Binance if trade was marked as closed
                    if self._verify_trade_closure_on_binance(trade_id, self.trades[trade_id]):
                        updates['closure_verified'] = True
                        updates['sync_status'] = 'CLOSURE_VERIFIED'
                        self.logger.info(f"🛡️ BULLETPROOF: Trade closure verified for {trade_id}")
                    else:
                        updates['closure_verified'] = False
                        updates['sync_status'] = 'CLOSURE_PENDING'
                        self.logger.warning(f"⚠️ BULLETPROOF: Trade closure not verified for {trade_id}")

                    # Log complete closure information
                    symbol = trade_data.get('symbol', 'UNKNOWN')
                    side = trade_data.get('side', 'UNKNOWN')
                    pnl_usdt = updates.get('pnl_usdt', 0)
                    pnl_pct = updates.get('pnl_percentage', 0)
                    duration = updates.get('duration_minutes', 0)
                    exit_reason = updates.get('exit_reason', 'Unknown')

                    self.logger.info(f"🔒 TRADE CLOSED: {trade_id} | {symbol} {side}")
                    self.logger.info(f"   💰 P&L: ${pnl_usdt:.2f} USDT ({pnl_pct:+.2f}%) | Duration: {duration}min | Reason: {exit_reason}")

                self.trades[trade_id].update(updates)
                self._save_database()
                self.logger.info(f"🛡️ BULLETPROOF: Updated trade {trade_id} with complete data")
            else:
                self.logger.error(f"🚨 BULLETPROOF: Trade {trade_id} not found for update - potential orphan!")
                # Create orphan detection entry
                self._log_orphan_operation(trade_id, 'UPDATE_MISSING', updates)
        except Exception as e:
            self.logger.error(f"🚨 BULLETPROOF: Error updating trade: {e}")
            self._log_critical_error('UPDATE_TRADE', trade_id, str(e))

    def get_all_trades(self) -> Dict[str, Dict[str, Any]]:
        """Get all trades"""
        return self.trades.copy()

    def cleanup_old_trades(self, days: int = 30):
        """Clean up trades older than specified days"""
        try:
            current_time = datetime.now()
            trades_to_remove = []

            for trade_id, trade_data in self.trades.items():
                entry_time_str = trade_data.get('entry_time') or trade_data.get('timestamp')
                if entry_time_str:
                    try:
                        entry_time = datetime.fromisoformat(entry_time_str.replace('Z', '+00:00'))
                        if (current_time - entry_time).days > days:
                            trades_to_remove.append(trade_id)
                    except ValueError:
                        continue

            for trade_id in trades_to_remove:
                del self.trades[trade_id]

            if trades_to_remove:
                self._save_database()
                self.logger.info(f"Cleaned up {len(trades_to_remove)} old trades")

        except Exception as e:
            self.logger.error(f"Error cleaning up old trades: {e}")

    def cleanup_stale_open_trades(self, hours: int = 6, sync_with_binance: bool = True):
        """Bulletproof cleanup of stale open trades with optional Binance synchronization"""
        try:
            current_time = datetime.now()
            trades_to_close = []

            # Get actual Binance positions if sync is enabled
            actual_binance_positions = {}
            if sync_with_binance:
                try:
                    from src.binance_client.client import BinanceClientWrapper
                    from src.config.global_config import global_config

                    binance_client = BinanceClientWrapper()
                    if binance_client.is_futures:
                        account_info = binance_client.client.futures_account()
                        positions = account_info.get('positions', [])

                        for position in positions:
                            symbol = position.get('symbol')
                            position_amt = float(position.get('positionAmt', 0))
                            if abs(position_amt) > 0.0001:  # Position exists
                                actual_binance_positions[symbol] = {
                                    'position_amt': position_amt,
                                    'entry_price': float(position.get('entryPrice', 0)),
                                    'side': 'BUY' if position_amt > 0 else 'SELL',
                                    'quantity': abs(position_amt)
                                }

                        self.logger.info(f"🔄 AGGRESSIVE CLEANUP: Found {len(actual_binance_positions)} active Binance positions")
                        self.logger.info(f"🔄 AGGRESSIVE CLEANUP: Binance positions: {list(actual_binance_positions.keys())}")
                except Exception as e:
                    self.logger.warning(f"Could not sync with Binance during cleanup: {e}")
                    sync_with_binance = False

            for trade_id, trade_data in self.trades.items():
                # Only process OPEN trades
                if trade_data.get('trade_status') == 'OPEN':
                    symbol = trade_data.get('symbol')
                    db_side = trade_data.get('side')
                    db_quantity = trade_data.get('quantity', 0)
                    strategy_name = trade_data.get('strategy_name', 'UNKNOWN')

                    should_close = False
                    close_reason = 'Stale Trade - Auto Closed'

                    # AGGRESSIVE METHOD 1: Check if position exists on Binance (PRIMARY METHOD)
                    if sync_with_binance and symbol:
                        position_exists_on_binance = False

                        if symbol in actual_binance_positions:
                            binance_pos = actual_binance_positions[symbol]
                            # Check if position details match with tolerance
                            quantity_match = abs(binance_pos['quantity'] - db_quantity) < 0.1
                            side_match = binance_pos['side'] == db_side

                            if quantity_match and side_match:
                                position_exists_on_binance = True
                                self.logger.debug(f"🔄 AGGRESSIVE CLEANUP: {trade_id} - Position confirmed on Binance")
                            else:
                                self.logger.info(f"🔄 AGGRESSIVE CLEANUP: {trade_id} - Position mismatch on Binance (Qty: {binance_pos['quantity']} vs {db_quantity}, Side: {binance_pos['side']} vs {db_side})")
                        else:
                            self.logger.info(f"🔄 AGGRESSIVE CLEANUP: {trade_id} - Symbol {symbol} not found on Binance")

                        if not position_exists_on_binance:
                            should_close = True
                            close_reason = 'Position not found on Binance - Aggressive cleanup'
                            self.logger.warning(f"🔄 AGGRESSIVE CLEANUP: {trade_id} ({strategy_name}) - No matching position on Binance, marking as CLOSED")

                    # AGGRESSIVE METHOD 2: Recovery trades older than 1 hour (SUPER AGGRESSIVE)
                    if not should_close and strategy_name == 'RECOVERY':
                        entry_time_str = trade_data.get('timestamp')
                        if entry_time_str:
                            try:
                                entry_time = datetime.fromisoformat(entry_time_str.replace('Z', '+00:00'))
                                hours_old = (current_time - entry_time).total_seconds() / 3600

                                if hours_old > 1:  # Only 1 hour for RECOVERY trades
                                    should_close = True
                                    close_reason = f'RECOVERY trade expired - Open for {hours_old:.1f} hours'
                                    self.logger.warning(f"🔄 AGGRESSIVE CLEANUP: {trade_id} - RECOVERY trade is {hours_old:.1f} hours old, forcing closure")
                            except ValueError:
                                # If timestamp parsing fails, consider it stale
                                should_close = True
                                close_reason = 'RECOVERY trade - Invalid timestamp'

                    # AGGRESSIVE METHOD 3: Standard trades older than specified hours
                    if not should_close:
                        entry_time_str = trade_data.get('timestamp')
                        if entry_time_str:
                            try:
                                entry_time = datetime.fromisoformat(entry_time_str.replace('Z', '+00:00'))
                                hours_old = (current_time - entry_time).total_seconds() / 3600

                                if hours_old > hours:
                                    should_close = True
                                    close_reason = f'Stale Trade - Open for {hours_old:.1f} hours'
                                    self.logger.warning(f"🔄 AGGRESSIVE CLEANUP: {trade_id} - Trade is {hours_old:.1f} hours old, forcing closure")
                            except ValueError:
                                # If timestamp parsing fails, consider it stale
                                should_close = True
                                close_reason = 'Stale Trade - Invalid timestamp'

                    # AGGRESSIVE METHOD 4: Duplicate RECOVERY entries for same symbol
                    if not should_close and strategy_name == 'RECOVERY':
                        # Count how many RECOVERY entries exist for this symbol
                        recovery_count_for_symbol = 0
                        for other_trade_id, other_trade_data in self.trades.items():
                            if (other_trade_data.get('symbol') == symbol and 
                                other_trade_data.get('strategy_name') == 'RECOVERY' and
                                other_trade_data.get('trade_status') == 'OPEN'):
                                recovery_count_for_symbol += 1

                        if recovery_count_for_symbol > 1:
                            # Keep only the newest RECOVERY entry for each symbol
                            recovery_trades_for_symbol = []
                            for other_trade_id, other_trade_data in self.trades.items():
                                if (other_trade_data.get('symbol') == symbol and 
                                    other_trade_data.get('strategy_name') == 'RECOVERY' and
                                    other_trade_data.get('trade_status') == 'OPEN'):
                                    timestamp_str = other_trade_data.get('timestamp', '')
                                    try:
                                        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                                        recovery_trades_for_symbol.append((other_trade_id, timestamp))
                                    except:
                                        recovery_trades_for_symbol.append((other_trade_id, datetime.min))

                            # Sort by timestamp (newest first)
                            recovery_trades_for_symbol.sort(key=lambda x: x[1], reverse=True)

                            # If this trade is not the newest, mark it for closure
                            if trade_id != recovery_trades_for_symbol[0][0]:
                                should_close = True
                                close_reason = f'Duplicate RECOVERY entry - Keeping newest only ({recovery_count_for_symbol} found)'
                                self.logger.warning(f"🔄 AGGRESSIVE CLEANUP: {trade_id} - Duplicate RECOVERY for {symbol}, keeping only newest")

                    # Close the trade if any criteria met
                    if should_close:
                        trades_to_close.append((trade_id, close_reason))

            # Mark stale trades as closed
            for trade_id, close_reason in trades_to_close:
                self.trades[trade_id]['trade_status'] = 'CLOSED'
                self.trades[trade_id]['exit_reason'] = close_reason
                self.trades[trade_id]['exit_price'] = self.trades[trade_id].get('entry_price', 0)  # Use entry price as exit
                self.trades[trade_id]['pnl_usdt'] = 0.0
                self.trades[trade_id]['pnl_percentage'] = 0.0
                self.trades[trade_id]['duration_minutes'] = 0
                self.trades[trade_id]['closed_at'] = current_time.isoformat()

            if trades_to_close:
                self._save_database()
                self.logger.info(f"🔄 BULLETPROOF CLEANUP: Marked {len(trades_to_close)} stale trades as CLOSED")
                for trade_id, close_reason in trades_to_close:
                    self.logger.info(f"   ✅ {trade_id}: {close_reason}")
            else:
                self.logger.debug(f"🔄 CLEANUP: No stale trades found - database is clean")

        except Exception as e:
            self.logger.error(f"Error in bulletproof cleanup: {e}")
            import traceback
            self.logger.error(f"Cleanup error traceback: {traceback.format_exc()}")



    def _verify_trade_on_binance(self, trade_id: str, trade_data: Dict[str, Any]) -> bool:
        """Verify trade exists on Binance with bulletproof error handling"""
        try:
            from src.binance_client.client import BinanceClientWrapper

            binance_client = BinanceClientWrapper()
            if not binance_client.is_futures:
                return True  # Skip verification for spot trading

            account_info = binance_client.client.futures_account()
            positions = account_info.get('positions', [])

            symbol = trade_data.get('symbol')
            expected_side = trade_data.get('side')
            expected_quantity = trade_data.get('quantity', 0)

            for position in positions:
                if position.get('symbol') == symbol:
                    position_amt = float(position.get('positionAmt', 0))
                    if abs(position_amt) > 0.0001:  # Position exists
                        actual_side = 'BUY' if position_amt > 0 else 'SELL'
                        actual_quantity = abs(position_amt)

                        # Check if matches with tolerance
                        quantity_match = abs(actual_quantity - expected_quantity) < 0.1
                        side_match = actual_side == expected_side

                        if quantity_match and side_match:
                            self.logger.debug(f"🛡️ VERIFICATION: {trade_id} confirmed on Binance")
                            return True

            self.logger.warning(f"⚠️ VERIFICATION: {trade_id} not found on Binance")
            return False

        except Exception as e:
            self.logger.error(f"🚨 VERIFICATION ERROR for {trade_id}: {e}")
            return False

    def _verify_trade_closure_on_binance(self, trade_id: str, trade_data: Dict[str, Any]) -> bool:
        """Verify trade is actually closed on Binance"""
        try:
            from src.binance_client.client import BinanceClientWrapper

            binance_client = BinanceClientWrapper()
            if not binance_client.is_futures:
                return True  # Skip verification for spot trading

            account_info = binance_client.client.futures_account()
            positions = account_info.get('positions', [])

            symbol = trade_data.get('symbol')

            for position in positions:
                if position.get('symbol') == symbol:
                    position_amt = float(position.get('positionAmt', 0))
                    if abs(position_amt) > 0.0001:  # Position still exists
                        self.logger.warning(f"⚠️ CLOSURE VERIFICATION: {trade_id} still open on Binance")
                        return False

            self.logger.info(f"🛡️ CLOSURE VERIFICATION: {trade_id} confirmed closed on Binance")
            return True

        except Exception as e:
            self.logger.error(f"🚨 CLOSURE VERIFICATION ERROR for {trade_id}: {e}")
            return False

    def _log_orphan_operation(self, trade_id: str, operation: str, data: Dict[str, Any]):
        """Log orphan operations for investigation"""
        try:
            orphan_log_file = "trading_data/orphan_operations.json"
            os.makedirs(os.path.dirname(orphan_log_file), exist_ok=True)

            orphan_entry = {
                'trade_id': trade_id,
                'operation': operation,
                'data': data,
                'timestamp': datetime.now().isoformat(),
                'severity': 'HIGH'
            }

            # Load existing orphan log
            orphan_log = []
            if os.path.exists(orphan_log_file):
                with open(orphan_log_file, 'r') as f:
                    existing_data = json.load(f)
                    orphan_log = existing_data.get('orphan_operations', [])

            orphan_log.append(orphan_entry)

            # Save updated log
            with open(orphan_log_file, 'w') as f:
                json.dump({
                    'orphan_operations': orphan_log[-100:],  # Keep last 100 entries
                    'last_updated': datetime.now().isoformat()
                }, f, indent=2)

            self.logger.error(f"🚨 ORPHAN LOGGED: {operation} for {trade_id}")

        except Exception as e:
            self.logger.error(f"🚨 Failed to log orphan operation: {e}")

    def _log_critical_error(self, operation: str, trade_id: str, error: str):
        """Log critical database errors for investigation"""
        try:
            error_log_file = "trading_data/critical_errors.json"
            os.makedirs(os.path.dirname(error_log_file), exist_ok=True)

            error_entry = {
                'operation': operation,
                'trade_id': trade_id,
                'error': error,
                'timestamp': datetime.now().isoformat(),
                'severity': 'CRITICAL'
            }

            # Load existing error log
            error_log = []
            if os.path.exists(error_log_file):
                with open(error_log_file, 'r') as f:
                    existing_data = json.load(f)
                    error_log = existing_data.get('critical_errors', [])

            error_log.append(error_entry)

            # Save updated log
            with open(error_log_file, 'w') as f:
                json.dump({
                    'critical_errors': error_log[-50:],  # Keep last 50 entries
                    'last_updated': datetime.now().isoformat()
                }, f, indent=2)

            self.logger.error(f"🚨 CRITICAL ERROR LOGGED: {operation} for {trade_id}")

        except Exception as e:
            self.logger.error(f"🚨 Failed to log critical error: {e}")

    def recover_missing_positions(self) -> Dict[str, Any]:
        """INTELLIGENT recovery that follows position recovery logic - find existing trades FIRST"""
        try:
            recovery_report = {
                'recovered_trades': [],
                'matched_existing_trades': [],
                'verification_failures': []
            }

            from src.binance_client.client import BinanceClientWrapper

            binance_client = BinanceClientWrapper()
            if not binance_client.is_futures:
                self.logger.info("🛡️ SMART RECOVERY: Spot trading mode - skipping position recovery")
                return recovery_report

            account_info = binance_client.client.futures_account()
            positions = account_info.get('positions', [])

            self.logger.info(f"🛡️ SMART RECOVERY: Starting intelligent recovery scan for {len(positions)} positions")

            for position in positions:
                symbol = position.get('symbol')
                position_amt = float(position.get('positionAmt', 0))

                if abs(position_amt) > 0.0001:  # Active position
                    entry_price = float(position.get('entryPrice', 0))
                    side = 'BUY' if position_amt > 0 else 'SELL'
                    quantity = abs(position_amt)

                    self.logger.debug(f"🛡️ SMART RECOVERY: Analyzing {symbol} | {side} | Qty: {quantity} | Entry: ${entry_price}")

                    # STEP 1: INTELLIGENT SEARCH - Find existing trade by position details (PRIMARY)
                    # This matches the logic in order_manager.py for position recovery
                    existing_trade_id = self.find_trade_by_position(
                        'UNKNOWN',  # Search across ALL strategies like position recovery does
                        symbol, 
                        side, 
                        quantity, 
                        entry_price,
                        tolerance=0.05  # 5% tolerance to handle price variations
                    )

                    if existing_trade_id:
                        # FOUND EXISTING TRADE - Update and verify it
                        existing_trade = self.trades[existing_trade_id]
                        original_strategy = existing_trade.get('strategy_name', 'UNKNOWN')
                        
                        # Update trade with Binance data to ensure accuracy
                        self.trades[existing_trade_id].update({
                            'sync_status': 'BINANCE_VERIFIED',
                            'last_verified': datetime.now().isoformat(),
                            'recovery_source': 'MATCHED_EXISTING',
                            'binance_entry_price': entry_price,
                            'binance_quantity': quantity
                        })

                        recovery_report['matched_existing_trades'].append({
                            'trade_id': existing_trade_id,
                            'original_strategy': original_strategy,
                            'symbol': symbol,
                            'status': 'MATCHED_AND_VERIFIED'
                        })

                        self.logger.info(f"✅ SMART RECOVERY: Found existing trade {existing_trade_id} for {symbol} | Strategy: {original_strategy}")
                        continue

                    # STEP 2: NO EXISTING TRADE FOUND - Create recovery trade with complete data
                    # Only reach here if no existing trade was found (same logic as position recovery)
                    
                    # Try to determine original strategy from symbol (enhanced logic)
                    original_strategy = self._determine_original_strategy(symbol)
                    
                    recovery_trade_id = f"{original_strategy}_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_RECOVERED"

                    # Calculate complete trade data for recovery
                    position_value_usdt = entry_price * quantity
                    leverage = 5  # Use reasonable default leverage
                    margin_used = position_value_usdt / leverage

                    # Record trade time in Dubai timezone (UTC+4)
                    from src.config.global_config import global_config
                    if global_config.USE_LOCAL_TIMEZONE:
                        dubai_time = datetime.utcnow() + timedelta(hours=global_config.TIMEZONE_OFFSET_HOURS)
                        timestamp = dubai_time.isoformat()
                    else:
                        timestamp = datetime.now().isoformat()

                    recovery_trade_data = {
                        'strategy_name': original_strategy,  # Use original strategy, not "RECOVERY"
                        'symbol': symbol,
                        'side': side,
                        'quantity': quantity,
                        'entry_price': entry_price,
                        'trade_status': 'OPEN',
                        'timestamp': timestamp,
                        'recovery_source': 'SMART_RECOVERY',
                        'sync_status': 'RECOVERED',
                        'created_at': datetime.now().isoformat(),
                        'last_verified': datetime.now().isoformat(),

                        # MANDATORY complete data for recovered positions
                        'position_value_usdt': position_value_usdt,
                        'leverage': leverage,
                        'margin_used': margin_used,
                        'trade_id': recovery_trade_id,
                        
                        # Recovery metadata
                        'recovery_method': 'INTELLIGENT_DATABASE_RECOVERY',
                        'binance_verified': True
                    }

                    # Use the bulletproof add_trade method to ensure data integrity
                    success = self.add_trade(recovery_trade_id, recovery_trade_data)
                    
                    if success:
                        recovery_report['recovered_trades'].append({
                            'trade_id': recovery_trade_id,
                            'strategy': original_strategy,
                            'symbol': symbol,
                            'method': 'SMART_RECOVERY'
                        })

                        self.logger.warning(f"🛡️ SMART RECOVERY: Created new trade {recovery_trade_id} for {symbol}")
                        self.logger.warning(f"   📊 Strategy: {original_strategy} | Value: ${position_value_usdt:.2f} USDT | Margin: ${margin_used:.2f}")
                    else:
                        self.logger.error(f"🚨 SMART RECOVERY: Failed to create recovery trade for {symbol}")
                        recovery_report['verification_failures'].append(f"Failed to create trade for {symbol}")

            # Save database if any changes were made
            if recovery_report['recovered_trades'] or recovery_report['matched_existing_trades']:
                self._save_database()
                
            # Summary logging
            matched_count = len(recovery_report['matched_existing_trades'])
            recovered_count = len(recovery_report['recovered_trades'])
            total_positions = len([p for p in positions if abs(float(p.get('positionAmt', 0))) > 0.0001])
            
            self.logger.info(f"🛡️ SMART RECOVERY COMPLETE:")
            self.logger.info(f"   📊 Total Binance positions: {total_positions}")
            self.logger.info(f"   ✅ Matched existing trades: {matched_count}")
            self.logger.info(f"   🆕 Created new recoveries: {recovered_count}")
            self.logger.info(f"   ❌ Failed recoveries: {len(recovery_report['verification_failures'])}")

            return recovery_report

        except Exception as e:
            self.logger.error(f"🚨 SMART RECOVERY ERROR: {e}")
            return {'error': str(e)}

    def _determine_original_strategy(self, symbol: str) -> str:
        """Intelligently determine the original strategy for a symbol"""
        try:
            # Look for any existing closed trades for this symbol to infer strategy
            for trade_id, trade_data in self.trades.items():
                if (trade_data.get('symbol') == symbol and 
                    trade_data.get('strategy_name') not in ['RECOVERY', 'UNKNOWN']):
                    original_strategy = trade_data.get('strategy_name')
                    self.logger.debug(f"🧠 STRATEGY INFERENCE: {symbol} -> {original_strategy} (from historical data)")
                    return original_strategy
            
            # Symbol-based strategy inference as fallback
            symbol_upper = symbol.upper()
            if 'SOL' in symbol_upper:
                return 'rsi_oversold'  # SOL typically uses RSI strategy
            elif 'ETH' in symbol_upper:
                return 'macd_divergence'  # ETH typically uses MACD strategy
            else:
                return 'AUTO_RECOVERED'  # Generic strategy for unknown symbols
                
        except Exception as e:
            self.logger.warning(f"Error determining strategy for {symbol}: {e}")
            return 'AUTO_RECOVERED'

    def run_bulletproof_health_check(self) -> Dict[str, Any]:
        """Comprehensive health check with automatic fixes"""
        try:
            health_report = {
                'total_trades': len(self.trades),
                'open_trades': 0,
                'closed_trades': 0,
                'unverified_trades': 0,
                'fixed_issues': [],
                'remaining_issues': []
            }

            for trade_id, trade_data in self.trades.items():
                status = trade_data.get('trade_status', 'UNKNOWN')

                if status == 'OPEN':
                    health_report['open_trades'] += 1

                    # Check if trade needs verification
                    sync_status = trade_data.get('sync_status', 'UNKNOWN')
                    if sync_status in ['PENDING_VERIFICATION', 'UNKNOWN']:
                        if self._verify_trade_on_binance(trade_id, trade_data):
                            self.trades[trade_id]['sync_status'] = 'VERIFIED'
                            self.trades[trade_id]['last_verified'] = datetime.now().isoformat()
                            health_report['fixed_issues'].append(f"Verified {trade_id}")
                        else:
                            health_report['unverified_trades'] += 1
                            health_report['remaining_issues'].append(f"Cannot verify {trade_id}")

                elif status == 'CLOSED':
                    health_report['closed_trades'] += 1

            # Run recovery for missing positions
            recovery_report = self.recover_missing_positions()
            if recovery_report.get('recovered_trades'):
                health_report['fixed_issues'].extend([f"Recovered {trade_id}" for trade_id in recovery_report['recovered_trades']])

            if health_report['fixed_issues']:
                self._save_database()

            self.logger.info(f"🛡️ HEALTH CHECK: {health_report}")
            return health_report

        except Exception as e:
            self.logger.error(f"🚨 HEALTH CHECK ERROR: {e}")
            return {'error': str(e)}