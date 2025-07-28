import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from src.binance_client.client import BinanceClientWrapper
from src.execution_engine.trade_database import TradeDatabase
from src.reporting.telegram_reporter import TelegramReporter
import os

class ReliableOrphanDetector:
    """
    Enhanced Reliable Orphan Detection System

    Detects trades logged in DB as "open" but no longer exist on Binance,
    and marks them as manually closed with proper audit trail.
    """

    def __init__(self, binance_client: BinanceClientWrapper, trade_db: TradeDatabase, 
                 telegram_reporter: TelegramReporter):
        self.binance_client = binance_client
        self.trade_db = trade_db
        self.telegram_reporter = telegram_reporter
        self.logger = logging.getLogger(__name__)

        # Configuration
        self.verification_interval = 30  # Reduced interval for faster detection
        self.position_threshold = 0.001  # minimum position size to consider active
        self.last_verification = datetime.now()
        self.consecutive_failures = 0
        self.max_failures = 3

        self.logger.info("🔍 Enhanced Reliable Orphan Detection System initialized")
        self.logger.info(f"⏰ Verification interval: {self.verification_interval}s")

    def should_run_verification(self) -> bool:
        """Check if enough time has passed for next verification"""
        time_elapsed = (datetime.now() - self.last_verification).total_seconds()
        return time_elapsed >= self.verification_interval

    def run_verification_cycle(self) -> Dict[str, Any]:
        """Run a complete verification cycle with enhanced error handling"""
        try:
            self.logger.info("🔍 STARTING ENHANCED ORPHAN VERIFICATION CYCLE")

            # Get open trades from database
            open_trades = self._get_open_trades_from_db()

            if not open_trades:
                self.logger.info("📊 No open trades found in database")
                # Still check for orphaned Binance positions
                return self._check_orphaned_binance_positions()

            self.logger.info(f"📊 Found {len(open_trades)} open trades to verify")

            # Get Binance positions using WebSocket first, API as fallback
            binance_positions = self._get_binance_positions_safe()

            if binance_positions is None:
                self.consecutive_failures += 1
                if self.consecutive_failures >= self.max_failures:
                    self.logger.error("❌ Too many consecutive failures, skipping verification")
                    return {'status': 'error', 'error': 'consecutive_failures'}
                else:
                    self.logger.warning(f"⚠️ Verification failed, attempt {self.consecutive_failures}/{self.max_failures}")
                    return {'status': 'failed', 'attempt': self.consecutive_failures}

            # Reset failure counter on success
            self.consecutive_failures = 0

            self.logger.info(f"📊 Found {len(binance_positions)} active positions on Binance")

            # Process orphan detection
            orphans_detected = []
            trades_verified = 0

            for trade in open_trades:
                try:
                    trade_id = trade.get('trade_id', 'unknown')
                    is_orphan = self._verify_trade_against_binance(trade, binance_positions)
                    trades_verified += 1

                    if is_orphan:
                        self.logger.warning(f"🚨 ORPHAN DETECTED: {trade_id}")
                        orphan_result = self._mark_trade_as_manually_closed(trade)

                        if orphan_result['success']:
                            orphans_detected.append(orphan_result)
                            self.logger.info(f"✅ ORPHAN PROCESSED: {trade_id}")

                except Exception as trade_error:
                    self.logger.error(f"❌ Error verifying trade {trade.get('trade_id', 'unknown')}: {trade_error}")

            # Update last verification time
            self.last_verification = datetime.now()

            # Send notifications
            if orphans_detected:
                self._send_orphan_summary_notification(orphans_detected)

            result = {
                'status': 'completed',
                'timestamp': self.last_verification.isoformat(),
                'open_trades': len(open_trades),
                'trades_verified': trades_verified,
                'orphans_detected': len(orphans_detected),
                'orphan_details': orphans_detected,
                'binance_positions': len(binance_positions)
            }

            self.logger.info(f"✅ VERIFICATION COMPLETE: {len(orphans_detected)} orphans detected")
            return result

        except Exception as e:
            self.logger.error(f"❌ Error in verification cycle: {e}")
            self.consecutive_failures += 1
            return {'status': 'error', 'error': str(e)}

    def _get_binance_positions_safe(self) -> Optional[List[Dict[str, Any]]]:
        """Safely get Binance positions with multiple fallback methods"""
        try:
            # Method 1: Try WebSocket cache first
            positions = self._get_positions_from_websocket()
            if positions is not None:
                self.logger.info(f"✅ Retrieved {len(positions)} positions from WebSocket cache")
                return positions

            # Method 2: Try direct API call with rate limiting
            self.logger.info("🔄 WebSocket cache unavailable, trying API...")
            positions = self._get_positions_from_api()
            if positions is not None:
                self.logger.info(f"✅ Retrieved {len(positions)} positions from API")
                return positions

            # Method 3: Use cached data if available
            positions = self._get_cached_positions()
            if positions is not None:
                self.logger.warning(f"⚠️ Using cached positions: {len(positions)} positions")
                return positions

            self.logger.error("❌ All position retrieval methods failed")
            return None

        except Exception as e:
            self.logger.error(f"❌ Error getting Binance positions: {e}")
            return None

    def _get_positions_from_websocket(self) -> Optional[List[Dict[str, Any]]]:
        """Get positions from WebSocket manager cache"""
        try:
            # Import WebSocket manager
            from src.data_fetcher.websocket_manager import WebSocketKlineManager

            # Try to access global WebSocket instance
            if hasattr(self.binance_client, 'websocket_manager'):
                ws_manager = self.binance_client.websocket_manager
                if ws_manager and ws_manager.is_connected():
                    # Get position data from WebSocket cache
                    positions = []
                    # WebSocket typically provides price data, not position data
                    # So we'll skip this method for now
                    return None

            return None

        except Exception as e:
            self.logger.error(f"❌ WebSocket position retrieval failed: {e}")
            return None

    def _get_positions_from_api(self) -> Optional[List[Dict[str, Any]]]:
        """Get positions from Binance API with error handling"""
        try:
            if not self.binance_client.is_futures:
                self.logger.info("📊 Not using futures - no positions to check")
                return []

            # Add delay to respect rate limits
            time.sleep(0.1)

            account_info = self.binance_client.client.futures_account()
            all_positions = account_info.get('positions', [])

            # Filter active positions
            active_positions = []
            for pos in all_positions:
                position_amt = float(pos.get('positionAmt', 0))
                if abs(position_amt) > self.position_threshold:
                    active_positions.append(pos)

            return active_positions

        except Exception as api_error:
            error_str = str(api_error)
            if "banned" in error_str.lower() or "IP" in error_str:
                self.logger.error("🚫 IP banned - using WebSocket data only")
            elif "permission" in error_str.lower():
                self.logger.error("🔐 Permission error - check API key")
            else:
                self.logger.error(f"❌ API error: {api_error}")
            return None

    def _get_cached_positions(self) -> Optional[List[Dict[str, Any]]]:
        """Get cached position data as fallback"""
        try:
            # Check if we have recent cached data
            cache_file = "trading_data/position_cache.json"
            if os.path.exists(cache_file):
                import json
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)

                cache_time = datetime.fromisoformat(cache_data.get('timestamp', '1970-01-01'))
                if (datetime.now() - cache_time).total_seconds() < 300:  # 5 minutes
                    return cache_data.get('positions', [])

            return None

        except Exception as e:
            self.logger.error(f"❌ Cache retrieval failed: {e}")
            return None

    def _check_orphaned_binance_positions(self) -> Dict[str, Any]:
        """Check for Binance positions without database records"""
        try:
            binance_positions = self._get_binance_positions_safe()
            if not binance_positions:
                return {
                    'status': 'completed',
                    'open_trades': 0,
                    'trades_verified': 0,
                    'orphans_detected': 0
                }

            orphans_created = 0
            for position in binance_positions:
                symbol = position.get('symbol')
                position_amt = float(position.get('positionAmt', 0))
                entry_price = float(position.get('entryPrice', 0))

                # Check if we have a database record for this position
                position_matched = False
                for trade_id, trade_data in self.trade_db.trades.items():
                    if (trade_data.get('symbol') == symbol and 
                        trade_data.get('trade_status') == 'OPEN'):
                        position_matched = True
                        break

                if not position_matched:
                    # Create recovery record
                    success = self.trade_db.create_orphan_trade_record(
                        position, f"orphan_recovery_{symbol.lower()}"
                    )
                    if success:
                        orphans_created += 1
                        self.logger.info(f"✅ Created recovery record for orphaned {symbol}")

                        # Send notification
                        try:
                            self.telegram_reporter.send_message(
                                f"🚨 ORPHAN POSITION RECOVERED\n"
                                f"Symbol: {symbol}\n"
                                f"Side: {'LONG' if position_amt > 0 else 'SHORT'}\n"
                                f"Quantity: {abs(position_amt)}\n"
                                f"Entry: ${entry_price}\n"
                                f"Recovery record created."
                            )
                        except Exception as e:
                            self.logger.warning(f"Notification failed: {e}")

            return {
                'status': 'completed',
                'open_trades': 0,
                'trades_verified': 0,
                'orphans_detected': orphans_created
            }

        except Exception as e:
            self.logger.error(f"❌ Error checking orphaned positions: {e}")
            return {'status': 'error', 'error': str(e)}

    def _get_open_trades_from_db(self) -> List[Dict[str, Any]]:
        """Get all trades marked as 'open' in the database"""
        try:
            all_trades = self.trade_db.get_all_trades()
            open_trades = []

            for trade_id, trade_data in all_trades.items():
                if trade_data.get('trade_status', '').upper() == 'OPEN':
                    # Validate required fields
                    required_fields = ['symbol', 'strategy_name', 'entry_price', 'quantity', 'side']
                    if all(field in trade_data for field in required_fields):
                        trade_data['trade_id'] = trade_id
                        open_trades.append(trade_data)

            return open_trades

        except Exception as e:
            self.logger.error(f"❌ Error getting open trades: {e}")
            return []

    def _verify_trade_against_binance(self, trade: Dict[str, Any], binance_positions: List[Dict[str, Any]]) -> bool:
        """Verify if a trade exists on Binance - returns True if orphaned"""
        try:
            symbol = trade['symbol']
            db_quantity = float(trade['quantity'])
            db_side = trade['side']

            # Find matching Binance position
            matching_position = None
            for pos in binance_positions:
                if pos.get('symbol') == symbol:
                    matching_position = pos
                    break

            if not matching_position:
                return True  # No position on Binance = orphan

            # Check position size
            binance_amt = float(matching_position.get('positionAmt', 0))
            expected_amt = db_quantity if db_side == 'BUY' else -db_quantity

            # If Binance position is zero or significantly different
            if abs(binance_amt) < self.position_threshold:
                return True  # Orphan

            position_difference = abs(binance_amt - expected_amt)
            tolerance = max(0.01, abs(db_quantity) * 0.05)

            if position_difference > tolerance:
                return True  # Orphan

            return False  # Valid position

        except Exception as e:
            self.logger.error(f"❌ Error verifying trade: {e}")
            return False

    def _mark_trade_as_manually_closed(self, trade: Dict[str, Any]) -> Dict[str, Any]:
        """Mark a trade as manually closed with proper audit trail"""
        try:
            trade_id = trade['trade_id']
            symbol = trade['symbol']

            # Get current price (try WebSocket first, then API)
            current_price = self._get_current_price_safe(symbol)
            if not current_price:
                current_price = float(trade['entry_price'])  # Fallback

            # Calculate PnL
            entry_price = float(trade['entry_price'])
            quantity = float(trade['quantity'])
            side = trade['side']

            if side == 'BUY':
                pnl_usdt = (current_price - entry_price) * quantity
            else:
                pnl_usdt = (entry_price - current_price) * quantity

            # Calculate PnL percentage
            margin_used = float(trade.get('margin_used', entry_price * quantity))
            pnl_percentage = (pnl_usdt / margin_used) * 100 if margin_used > 0 else 0.0

            # Update database
            updates = {
                'trade_status': 'CLOSED',
                'exit_price': current_price,
                'exit_time': datetime.now().isoformat(),
                'exit_reason': 'orphan_detection',
                'pnl_usdt': round(pnl_usdt, 2),
                'pnl_percentage': round(pnl_percentage, 2),
                'manually_closed': True,
                'orphan_detected': True,
                'orphan_detection_time': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat()
            }

            success = self.trade_db.update_trade(trade_id, updates)

            if success:
                self.logger.info(f"✅ Trade {trade_id} marked as orphan closed | PnL: ${pnl_usdt:.2f}")
                return {
                    'success': True,
                    'trade_id': trade_id,
                    'symbol': symbol,
                    'strategy_name': trade['strategy_name'],
                    'pnl_usdt': pnl_usdt,
                    'pnl_percentage': pnl_percentage,
                    'exit_price': current_price
                }
            else:
                return {'success': False, 'trade_id': trade_id, 'error': 'database_update_failed'}

        except Exception as e:
            self.logger.error(f"❌ Error marking trade as closed: {e}")
            return {'success': False, 'trade_id': trade.get('trade_id', 'unknown'), 'error': str(e)}

    def _get_current_price_safe(self, symbol: str) -> Optional[float]:
        """Safely get current price with multiple fallback methods"""
        try:
            # Method 1: WebSocket cache
            try:
                if hasattr(self.binance_client, 'price_fetcher'):
                    price = self.binance_client.price_fetcher.get_current_price(symbol)
                    if price:
                        return price
            except:
                pass

            # Method 2: Direct API (with ban protection)
            try:
                ticker = self.binance_client.get_symbol_ticker(symbol)
                if ticker and 'price' in ticker:
                    return float(ticker['price'])
            except:
                pass

            # Method 3: Cache fallback
            try:
                cache_file = f"trading_data/price_cache_{symbol}.json"
                if os.path.exists(cache_file):
                    import json
                    with open(cache_file, 'r') as f:
                        cache_data = json.load(f)

                    cache_time = datetime.fromisoformat(cache_data.get('timestamp', '1970-01-01'))
                    if (datetime.now() - cache_time).total_seconds() < 60:  # 1 minute
                        return float(cache_data.get('price', 0))
            except:
                pass

            return None

        except Exception as e:
            self.logger.error(f"❌ Error getting price for {symbol}: {e}")
            return None

    def _send_orphan_summary_notification(self, orphans: List[Dict[str, Any]]):
        """Send Telegram notification for detected orphans"""
        try:
            if not orphans:
                return

            message_lines = [
                "👻 ORPHAN TRADES DETECTED & CLOSED",
                f"Found and processed {len(orphans)} orphan positions:",
                ""
            ]

            total_pnl = 0.0
            for orphan in orphans:
                if orphan.get('success'):
                    strategy = orphan.get('strategy_name', 'Unknown')
                    symbol = orphan.get('symbol', 'Unknown')
                    pnl = orphan.get('pnl_usdt', 0.0)
                    pnl_pct = orphan.get('pnl_percentage', 0.0)

                    pnl_emoji = "🟢" if pnl >= 0 else "🔴"
                    message_lines.append(f"{pnl_emoji} {strategy} | {symbol}")
                    message_lines.append(f"   PnL: ${pnl:.2f} ({pnl_pct:.2f}%)")
                    message_lines.append("")

                    total_pnl += pnl

            total_emoji = "🟢" if total_pnl >= 0 else "🔴"
            message_lines.append(f"{total_emoji} Total Impact: ${total_pnl:.2f}")
            message_lines.append("✅ All orphans automatically processed")

            self.telegram_reporter.send_message("\n".join(message_lines))

        except Exception as e:
            self.logger.error(f"❌ Error sending notification: {e}")

    def force_verification(self) -> Dict[str, Any]:
        """Force immediate verification"""
        self.logger.info("🔧 FORCING IMMEDIATE ORPHAN VERIFICATION")
        self.last_verification = datetime.now() - timedelta(seconds=self.verification_interval + 1)
        return self.run_verification_cycle()

    def get_status(self) -> Dict[str, Any]:
        """Get current status"""
        return {
            'last_verification': self.last_verification.isoformat(),
            'verification_interval': self.verification_interval,
            'position_threshold': self.position_threshold,
            'consecutive_failures': self.consecutive_failures,
            'next_verification_in': max(0, self.verification_interval - (datetime.now() - self.last_verification).total_seconds())
        }

    def reset_failure_counter(self):
        """Reset the consecutive failure counter"""
        self.consecutive_failures = 0
        self.logger.info("✅ Orphan detector failure counter reset")
        
    def debug_verification_status(self) -> Dict[str, Any]:
        """Debug current verification status"""
        try:
            self.logger.info("🔍 DEBUG: Starting verification status check")

            # Check database trades
            open_trades = self._get_open_trades_from_db()
            self.logger.info(f"🔍 DEBUG: Found {len(open_trades)} open trades in database:")
            for trade in open_trades:
                self.logger.info(f"   - {trade['trade_id']}: {trade['symbol']} {trade['side']} {trade['quantity']}")

            # Check Binance positions
            binance_positions = self._get_binance_positions_safe()
            self.logger.info(f"🔍 DEBUG: Found {len(binance_positions)} active Binance positions:")
            for pos in binance_positions:
                symbol = pos.get('symbol', 'UNKNOWN')
                amt = pos.get('positionAmt', 0)
                self.logger.info(f"   - {symbol}: {amt}")

            # Check verification timing
            time_since_last = (datetime.now() - self.last_verification).total_seconds()
            should_run = self.should_run_verification()

            status = {
                'open_trades_count': len(open_trades),
                'binance_positions_count': len(binance_positions),
                'time_since_last_verification': time_since_last,
                'should_run_verification': should_run,
                'verification_interval': self.verification_interval,
                'last_verification': self.last_verification.isoformat(),
                'consecutive_failures': self.consecutive_failures
            }

            self.logger.info(f"🔍 DEBUG: Verification status: {status}")
            return status

        except Exception as e:
            self.logger.error(f"❌ Error in debug verification: {e}")
            return {'error': str(e)}