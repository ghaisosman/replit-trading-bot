import json
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

class TradeDatabase:
    """Simplified trade database - mirrors trade logger data only"""

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
        """Load trades from database file"""
        try:
            if os.path.exists(self.db_file):
                with open(self.db_file, 'r') as f:
                    data = json.load(f)
                    self.trades = data.get('trades', {})
                    self.logger.info(f"📊 Loaded {len(self.trades)} trades from database")
            else:
                self.logger.info("📊 Trade database file not found, starting with empty database")
                self.trades = {}
        except Exception as e:
            self.logger.error(f"❌ Error loading trade database: {e}")
            self.trades = {}

    def _save_database(self):
        """Save trades to database file with enhanced error handling and fallback options"""
        try:
            self.logger.info(f"🔍 SAVING DATABASE | File: {self.db_file} | Trades: {len(self.trades)}")

            data = {
                'trades': self.trades,
                'last_updated': datetime.now().isoformat()
            }

            # Multiple save strategies for maximum reliability
            save_success = False
            
            # Strategy 1: Normal directory with atomic write
            try:
                import os
                db_dir = os.path.dirname(self.db_file)
                
                # Create directory if needed
                if db_dir and not os.path.exists(db_dir):
                    os.makedirs(db_dir, mode=0o755, exist_ok=True)
                    self.logger.info(f"✅ CREATED DIRECTORY | {db_dir}")

                # Atomic write with temp file
                temp_file = f"{self.db_file}.tmp"
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, default=str, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())

                # Atomic move
                os.replace(temp_file, self.db_file)
                
                # Verify the save
                if os.path.exists(self.db_file) and os.path.getsize(self.db_file) > 0:
                    with open(self.db_file, 'r', encoding='utf-8') as f:
                        verification_data = json.load(f)
                        if len(verification_data.get('trades', {})) == len(self.trades):
                            save_success = True
                            self.logger.info(f"✅ DATABASE SAVE SUCCESS | Strategy 1")
                        else:
                            self.logger.warning(f"⚠️ Trade count mismatch in verification")

            except Exception as strategy1_error:
                self.logger.warning(f"⚠️ Strategy 1 failed: {strategy1_error}")
                # Clean up temp file
                try:
                    temp_file = f"{self.db_file}.tmp"
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except:
                    pass

            # Strategy 2: Fallback to root directory
            if not save_success:
                try:
                    fallback_file = "trade_database.json"
                    self.logger.info(f"🔄 TRYING FALLBACK LOCATION | {fallback_file}")
                    
                    with open(fallback_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, default=str, ensure_ascii=False)
                        f.flush()
                        os.fsync(f.fileno())
                    
                    # Verify fallback save
                    if os.path.exists(fallback_file) and os.path.getsize(fallback_file) > 0:
                        with open(fallback_file, 'r', encoding='utf-8') as f:
                            verification_data = json.load(f)
                            if len(verification_data.get('trades', {})) == len(self.trades):
                                save_success = True
                                self.db_file = fallback_file  # Update file path
                                self.logger.info(f"✅ DATABASE SAVE SUCCESS | Strategy 2 (Fallback)")

                except Exception as strategy2_error:
                    self.logger.warning(f"⚠️ Strategy 2 failed: {strategy2_error}")

            # Strategy 3: Simple write without atomic operations
            if not save_success:
                try:
                    simple_file = "trades_backup.json"
                    self.logger.info(f"🔄 TRYING SIMPLE WRITE | {simple_file}")
                    
                    with open(simple_file, 'w') as f:
                        json.dump(data, f, indent=2, default=str)
                    
                    if os.path.exists(simple_file) and os.path.getsize(simple_file) > 0:
                        save_success = True
                        self.logger.info(f"✅ DATABASE SAVE SUCCESS | Strategy 3 (Simple)")

                except Exception as strategy3_error:
                    self.logger.error(f"❌ Strategy 3 failed: {strategy3_error}")

            if save_success:
                self.logger.info(f"✅ DATABASE SAVE COMPLETED SUCCESSFULLY")
                return True
            else:
                self.logger.error(f"❌ ALL SAVE STRATEGIES FAILED")
                return False

        except Exception as e:
            self.logger.error(f"❌ Critical error in database save: {e}")
            import traceback
            self.logger.error(f"🔍 Save error traceback: {traceback.format_exc()}")
            return False

    def add_trade(self, trade_id: str, trade_data: Dict[str, Any]) -> bool:
        """Add a trade to the database - simplified version"""
        try:
            self.logger.info(f"🔍 DEBUG: Adding trade {trade_id} to database")
            self.logger.info(f"🔍 DEBUG: Input trade data keys: {list(trade_data.keys())}")

            # Basic validation only
            required_fields = ['strategy_name', 'symbol', 'side', 'quantity', 'entry_price', 'trade_status']
            missing_fields = [field for field in required_fields if field not in trade_data or trade_data[field] is None]

            if missing_fields:
                self.logger.error(f"❌ Missing required fields {missing_fields} in trade {trade_id}")
                return False

            self.logger.info(f"🔍 DEBUG: All required fields present")

            # Calculate missing basic fields if not provided
            entry_price = float(trade_data['entry_price'])
            quantity = float(trade_data['quantity'])

            self.logger.info(f"🔍 DEBUG: Entry price: {entry_price}, Quantity: {quantity}")

            if 'position_value_usdt' not in trade_data:
                trade_data['position_value_usdt'] = entry_price * quantity
                self.logger.info(f"🔍 DEBUG: Calculated position_value_usdt: {trade_data['position_value_usdt']}")

            if 'leverage' not in trade_data:
                trade_data['leverage'] = 1
                self.logger.info(f"🔍 DEBUG: Set default leverage: 1")

            if 'margin_used' not in trade_data:
                leverage = trade_data.get('leverage', 1)
                trade_data['margin_used'] = (entry_price * quantity) / leverage
                self.logger.info(f"🔍 DEBUG: Calculated margin_used: {trade_data['margin_used']}")

            # Add timestamp
            trade_data['created_at'] = datetime.now().isoformat()
            trade_data['last_updated'] = datetime.now().isoformat()

            self.logger.info(f"🔍 DEBUG: Added timestamps")

            # Store the trade
            trades_before = len(self.trades)
            self.trades[trade_id] = trade_data
            trades_after = len(self.trades)

            self.logger.info(f"🔍 DEBUG: Trades count before: {trades_before}, after: {trades_after}")

            # Verify trade was stored
            if trade_id in self.trades:
                self.logger.info(f"🔍 DEBUG: Trade {trade_id} successfully stored in memory")
            else:
                self.logger.error(f"🔍 DEBUG: Trade {trade_id} NOT stored in memory")
                return False

            # Save to file
            self.logger.info(f"🔍 DEBUG: Calling _save_database()")
            save_result = self._save_database()
            self.logger.info(f"🔍 DEBUG: _save_database() returned: {save_result}")

            # CRITICAL: Immediate verification by reloading from disk
            if save_result:
                verification_db = TradeDatabase()
                if trade_id in verification_db.trades:
                    self.logger.info(f"✅ VERIFIED: Trade {trade_id} persisted to disk successfully")
                else:
                    self.logger.error(f"❌ VERIFICATION FAILED: Trade {trade_id} not found after disk save")
                    return False

            self.logger.info(f"✅ Trade added to database: {trade_id} | {trade_data['symbol']} | {trade_data['side']}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error adding trade to database: {e}")
            import traceback
            self.logger.error(f"🔍 DEBUG: Full traceback: {traceback.format_exc()}")
            return False

    def update_trade(self, trade_id: str, updates: Dict[str, Any]) -> bool:
        """Update trade data - simplified version"""
        try:
            if trade_id in self.trades:
                updates['last_updated'] = datetime.now().isoformat()
                self.trades[trade_id].update(updates)
                
                # Save and verify
                save_result = self._save_database()
                if save_result:
                    # Immediate verification
                    verification_db = TradeDatabase()
                    if trade_id in verification_db.trades:
                        updated_trade = verification_db.trades[trade_id]
                        # Check if the updates were actually saved
                        all_updates_saved = True
                        for key, value in updates.items():
                            if updated_trade.get(key) != value:
                                all_updates_saved = False
                                break
                        
                        if all_updates_saved:
                            self.logger.info(f"✅ Trade updated and verified in database: {trade_id}")
                            
                            # Automatically sync to logger after successful database update
                            sync_success = self.sync_trade_to_logger(trade_id)
                            if sync_success:
                                self.logger.info(f"Trade {trade_id} automatically synced to logger")
                            else:
                                self.logger.warning(f"Trade {trade_id} updated in database but sync to logger failed")
                            
                            return True
                        else:
                            self.logger.error(f"❌ Update verification failed for {trade_id}")
                            return False
                    else:
                        self.logger.error(f"❌ Trade {trade_id} not found after update")
                        return False
                else:
                    self.logger.error(f"❌ Failed to save database after update for {trade_id}")
                    return False
            else:
                self.logger.warning(f"⚠️ Trade {trade_id} not found for update")
                return False
        except Exception as e:
            self.logger.error(f"❌ Error updating trade: {e}")
            import traceback
            self.logger.error(f"❌ Update traceback: {traceback.format_exc()}")
            return False

    def get_trade(self, trade_id: str) -> Optional[Dict[str, Any]]:
        """Get trade data by ID"""
        return self.trades.get(trade_id)

    def get_all_trades(self) -> Dict[str, Dict[str, Any]]:
        """Get all trades"""
        return self.trades.copy()

    def find_trade_by_position(self, strategy_name: str, symbol: str, side: str, quantity: float, entry_price: float, tolerance: float = 0.01) -> Optional[str]:
        """Find trade by position details with tolerance"""
        try:
            # First try exact match for test scenarios
            for trade_id, trade_data in self.trades.items():
                if (trade_data.get('strategy_name') == strategy_name and
                    trade_data.get('symbol') == symbol and
                    trade_data.get('side') == side and
                    trade_data.get('quantity') == quantity and
                    trade_data.get('entry_price') == entry_price):
                    return trade_id

            # Then try tolerance-based match
            for trade_id, trade_data in self.trades.items():
                if (trade_data.get('strategy_name') == strategy_name and
                    trade_data.get('symbol') == symbol and
                    trade_data.get('side') == side and
                    abs(trade_data.get('quantity', 0) - quantity) <= tolerance and
                    abs(trade_data.get('entry_price', 0) - entry_price) <= abs(entry_price * tolerance)):
                    return trade_id
            return None
        except Exception as e:
            logging.getLogger(__name__).error(f"Error finding trade by position: {e}")
            return None

    def sync_trade_to_logger(self, trade_id: str):
        """Sync a specific trade from database to logger"""
        try:
            if trade_id not in self.trades:
                self.logger.warning(f"Trade {trade_id} not found in database for sync")
                return False

            trade_data = self.trades[trade_id].copy()
            self.logger.info(f"🔄 SYNCING TRADE TO LOGGER | {trade_id} | Data keys: {list(trade_data.keys())}")

            # Import logger
            from src.analytics.trade_logger import trade_logger

            # Ensure required fields are present and properly formatted
            required_fields = ['trade_id', 'strategy_name', 'symbol', 'side', 'entry_price', 'quantity', 'margin_used', 'leverage', 'position_value_usdt']

            for field in required_fields:
                if field not in trade_data:
                    self.logger.warning(f"⚠️ Missing field {field} in trade {trade_id}, calculating fallback")

                    if field == 'margin_used' and 'position_value_usdt' in trade_data and 'leverage' in trade_data:
                        trade_data['margin_used'] = trade_data['position_value_usdt'] / trade_data.get('leverage', 1)
                    elif field == 'position_value_usdt' and 'entry_price' in trade_data and 'quantity' in trade_data:
                        trade_data['position_value_usdt'] = trade_data['entry_price'] * trade_data['quantity']
                    elif field == 'leverage':
                        trade_data['leverage'] = 1  # Default

            # Ensure timestamp is properly formatted
            if 'timestamp' not in trade_data:
                if 'created_at' in trade_data:
                    trade_data['timestamp'] = trade_data['created_at']
                else:
                    trade_data['timestamp'] = datetime.now().isoformat()

            self.logger.info(f"🔄 CALLING LOGGER.LOG_TRADE | {trade_id}")

            # Check if trade already exists in logger to prevent duplicates
            existing_trade = None
            for existing in trade_logger.trades:
                if existing.trade_id == trade_id:
                    existing_trade = existing
                    break

            if existing_trade:
                self.logger.info(f"✅ Trade {trade_id} already exists in logger - updating from database (database is source of truth)")
                # Even if exists, update with latest database data since database is source of truth
                try:
                    # Remove existing and add updated version
                    trade_logger.trades = [t for t in trade_logger.trades if t.trade_id != trade_id]
                    self.logger.info(f"🔄 Removed existing trade from logger for update")
                except Exception as e:
                    self.logger.warning(f"Could not remove existing trade: {e}")
                # Continue to add updated version below

            self.logger.info(f"🔄 CALLING LOGGER.LOG_TRADE | {trade_id}")

            # Sync the trade
            success = trade_logger.log_trade(trade_data)

            if success:
                self.logger.info(f"✅ Synced trade {trade_id} from database to logger")
            else:
                self.logger.error(f"❌ Failed to sync trade {trade_id} to logger")

            return success

        except Exception as e:
            self.logger.error(f"❌ Error syncing trade {trade_id} to logger: {e}")
            import traceback
            self.logger.error(f"🔍 Sync error traceback: {traceback.format_exc()}")
            return False

    def sync_from_logger(self):
        """Sync database with trade logger - logger is source of truth"""
        try:
            from src.analytics.trade_logger import trade_logger

            logger_trades = {t.trade_id: t for t in trade_logger.trades}
            sync_count = 0

            for trade_id, logger_trade in logger_trades.items():
                # Convert logger trade to dict
                trade_dict = logger_trade.to_dict()

                if trade_id in self.trades:
                    # Update existing trade with logger data
                    self.trades[trade_id].update(trade_dict)
                    self.trades[trade_id]['last_updated'] = datetime.now().isoformat()
                else:
                    # Add missing trade from logger
                    trade_dict['created_at'] = datetime.now().isoformat()
                    trade_dict['last_updated'] = datetime.now().isoformat()
                    self.trades[trade_id] = trade_dict

                sync_count += 1

            self._save_database()
            self.logger.info(f"✅ Synced {sync_count} trades from logger to database")
            return sync_count

        except Exception as e:
            self.logger.error(f"❌ Error syncing from logger: {e}")
            return 0

    def get_recovery_candidates(self):
        """Get open trades that could be recovered - simplified approach"""
        try:
            candidates = []
            for trade_id, trade_data in self.trades.items():
                if trade_data.get('trade_status') == 'OPEN':
                    candidates.append({
                        'trade_id': trade_id,
                        'symbol': trade_data.get('symbol'),
                        'side': trade_data.get('side'),
                        'quantity': trade_data.get('quantity'),
                        'entry_price': trade_data.get('entry_price'),
                        'strategy_name': trade_data.get('strategy_name')
                    })

            self.logger.info(f"🔍 Found {len(candidates)} recovery candidates in database")
            return candidates

        except Exception as e:
            self.logger.error(f"❌ Error getting recovery candidates: {e}")
            return []

    def create_orphan_trade_record(self, binance_position: dict, estimated_strategy: str = "unknown_recovery") -> bool:
        """Create a database record for an orphaned Binance position"""
        try:
            symbol = binance_position.get('symbol')
            position_amt = float(binance_position.get('positionAmt', 0))
            entry_price = float(binance_position.get('entryPrice', 0))
            unrealized_pnl = float(binance_position.get('unRealizedProfit', 0))

            if abs(position_amt) < 0.001:  # No meaningful position
                return False

            # Generate trade ID for orphan recovery
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            trade_id = f"RECOVERY_{estimated_strategy}_{symbol}_{timestamp}"

            # Determine side and quantity
            side = 'BUY' if position_amt > 0 else 'SELL'
            quantity = abs(position_amt)

            # Create trade record
            trade_data = {
                'trade_id': trade_id,
                'strategy_name': estimated_strategy,
                'symbol': symbol,
                'side': side,
                'quantity': quantity,
                'entry_price': entry_price,
                'trade_status': 'OPEN',
                'position_value_usdt': entry_price * quantity,
                'leverage': 1,  # Default leverage
                'margin_used': entry_price * quantity,  # Assume 1x leverage
                'unrealized_pnl': unrealized_pnl,
                'created_at': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat(),
                'recovery_trade': True,  # Mark as recovered trade
                'original_binance_data': binance_position  # Store original data
            }

            # Add to database
            success = self.add_trade(trade_id, trade_data)

            if success:
                self.logger.info(f"✅ Created recovery trade record: {trade_id} | {symbol} | {side} | Qty: {quantity}")
                return True
            else:
                self.logger.error(f"❌ Failed to create recovery trade record for {symbol}")
                return False

        except Exception as e:
            self.logger.error(f"❌ Error creating orphan trade record: {e}")
            return False

    def recover_unmatched_positions(self, binance_client) -> int:
        """Automatically recover unmatched Binance positions by creating database records"""
        try:
            if not binance_client.is_futures:
                self.logger.info("📊 Not using futures - skipping position recovery")
                return 0

            # Get all Binance positions
            account_info = binance_client.client.futures_account()
            all_positions = account_info.get('positions', [])

            # Filter active positions
            active_positions = [pos for pos in all_positions if abs(float(pos.get('positionAmt', 0))) > 0.001]

            if not active_positions:
                self.logger.info("📊 No active Binance positions found to recover")
                return 0

            self.logger.info(f"🔍 Found {len(active_positions)} active Binance positions")

            recovered_count = 0

            for position in active_positions:
                symbol = position.get('symbol')
                position_amt = float(position.get('positionAmt', 0))

                # Check if we already have a database record for this position
                position_matched = False
                for trade_id, trade_data in self.trades.items():
                    if (trade_data.get('symbol') == symbol and 
                        trade_data.get('trade_status') == 'OPEN'):

                        # Check if quantities roughly match
                        db_quantity = float(trade_data.get('quantity', 0))
                        db_side = trade_data.get('side')

                        expected_amt = db_quantity if db_side == 'BUY' else -db_quantity

                        if abs(position_amt - expected_amt) < 0.1:  # Allow small tolerance
                            position_matched = True
                            self.logger.debug(f"📊 Position {symbol} already matched in database")
                            break

                # If no match found, create recovery record
                if not position_matched:
                    # Try to estimate strategy based on symbol patterns
                    estimated_strategy = "manual_position"
                    if "BTC" in symbol:
                        estimated_strategy = "manual_btc"
                    elif "ETH" in symbol:
                        estimated_strategy = "manual_eth"
                    elif "XRP" in symbol:
                        estimated_strategy = "manual_xrp"

                    success = self.create_orphan_trade_record(position, estimated_strategy)
                    if success:
                        recovered_count += 1

            if recovered_count > 0:
                self.logger.info(f"✅ Successfully recovered {recovered_count} unmatched positions")

            return recovered_count

        except Exception as e:
            self.logger.error(f"❌ Error recovering unmatched positions: {e}")
            return 0

    def cleanup_old_trades(self, days: int = 30):
        """Clean up trades older than specified days"""
        try:
            current_time = datetime.now()
            trades_to_remove = []

            for trade_id, trade_data in self.trades.items():
                created_at_str = trade_data.get('created_at')
                if created_at_str:
                    try:
                        created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                        if (current_time - created_at).days > days:
                            trades_to_remove.append(trade_id)
                    except ValueError:
                        continue

            for trade_id in trades_to_remove:
                del self.trades[trade_id]

            if trades_to_remove:
                self._save_database()
                self.logger.info(f"🧹 Cleaned up {len(trades_to_remove)} old trades")

        except Exception as e:
            self.logger.error(f"❌ Error cleaning up old trades: {e}")