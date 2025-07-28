import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from src.binance_client.client import BinanceClientWrapper
from src.execution_engine.trade_database import TradeDatabase
from src.reporting.telegram_reporter import TelegramReporter

class ReliableOrphanDetector:
    """
    Reliable Orphan Detection System

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
        self.verification_interval = 60  # seconds
        self.position_threshold = 0.001  # minimum position size to consider active
        self.last_verification = datetime.now()

        self.logger.info("🔍 Reliable Orphan Detection System initialized")
        self.logger.info(f"⏰ Verification interval: {self.verification_interval}s")

    def should_run_verification(self) -> bool:
        """Check if enough time has passed for next verification"""
        time_elapsed = (datetime.now() - self.last_verification).total_seconds()
        return time_elapsed >= self.verification_interval

    def run_verification_cycle(self) -> Dict[str, Any]:
        """Run a complete verification cycle"""
        try:
            self.logger.info("🔍 STARTING ORPHAN VERIFICATION CYCLE")

            # Get open trades from database
            open_trades = {}
            for trade_id, trade_data in self.trade_db.trades.items():
                if trade_data.get('trade_status') == 'OPEN':
                    open_trades[trade_id] = trade_data

            self.logger.info(f"📊 NO OPEN TRADES FOUND IN DATABASE")

            # CRITICAL FIX: Always check Binance positions even if no database trades
            # Get current Binance positions
            binance_positions = []
            try:
                if self.binance_client.is_futures:
                    positions = self.binance_client.client.futures_position_information()
                    for position in positions:
                        position_amt = float(position.get('positionAmt', 0))
                        if abs(position_amt) > 0.001:  # Has actual position
                            binance_positions.append(position)
                            symbol = position.get('symbol')
                            entry_price = float(position.get('entryPrice', 0))
                            side = 'LONG' if position_amt > 0 else 'SHORT'
                            self.logger.info(f"🔍 FOUND BINANCE POSITION: {symbol} {side} Qty:{abs(position_amt)} Entry:${entry_price}")
            except Exception as e:
                self.logger.error(f"❌ Error checking Binance positions: {e}")

            # Check for orphaned positions (Binance positions without database records)
            orphans_detected = 0
            if binance_positions and not open_trades:
                self.logger.warning(f"🚨 ORPHAN POSITIONS DETECTED: {len(binance_positions)} Binance positions with no database records!")

                for position in binance_positions:
                    symbol = position.get('symbol')
                    position_amt = float(position.get('positionAmt', 0))
                    entry_price = float(position.get('entryPrice', 0))

                    # Create recovery record for orphaned position
                    success = self.trade_db.create_orphan_trade_record(position, f"orphan_recovery_{symbol.lower()}")
                    if success:
                        orphans_detected += 1
                        self.logger.info(f"✅ Created recovery record for orphaned {symbol} position")

                        # Send Telegram notification
                        try:
                            self.telegram_reporter.send_message(
                                f"🚨 ORPHAN POSITION RECOVERED\n"
                                f"Symbol: {symbol}\n"
                                f"Side: {'LONG' if position_amt > 0 else 'SHORT'}\n"
                                f"Quantity: {abs(position_amt)}\n"
                                f"Entry: ${entry_price}\n"
                                f"Recovery record created automatically."
                            )
                        except Exception as e:
                            self.logger.warning(f"Could not send Telegram notification: {e}")

            if not open_trades and not binance_positions:
                return {
                    'status': 'completed',
                    'open_trades': 0,
                    'trades_verified': 0,
                    'orphans_detected': orphans_detected
                }

            self.logger.info("🔍 DEEP DEBUG: Starting comprehensive orphan verification cycle")

            # Check if verification should run
            time_since_last = (datetime.now() - self.last_verification).total_seconds()
            should_run = self.should_run_verification()

            self.logger.info(f"🔍 DEEP DEBUG: Verification timing check:")
            self.logger.info(f"   Time since last: {time_since_last:.1f}s")
            self.logger.info(f"   Interval required: {self.verification_interval}s")
            self.logger.info(f"   Should run: {should_run}")

            if not should_run:
                self.logger.info("⏭️ SKIPPING: Verification interval not reached")
                return {'status': 'skipped', 'reason': 'interval_not_reached'}

            self.logger.info("🔍 ORPHAN VERIFICATION: Starting verification cycle")

            # Get all open trades from database
            self.logger.info("📊 STEP 1: Getting open trades from database...")
            open_trades = self._get_open_trades_from_db()

            if not open_trades:
                self.logger.warning("📊 NO OPEN TRADES FOUND IN DATABASE")
                self.logger.info("   This means there should be no orphans to detect")
                self.last_verification = datetime.now()
                return {'status': 'completed', 'open_trades': 0, 'orphans_detected': 0}

            self.logger.info(f"📊 Found {len(open_trades)} open trades to verify:")
            for i, trade in enumerate(open_trades):
                trade_id = trade.get('trade_id', 'unknown')
                symbol = trade.get('symbol', 'unknown')
                side = trade.get('side', 'unknown')
                quantity = trade.get('quantity', 0)
                self.logger.info(f"   {i+1}. {trade_id}: {symbol} {side} {quantity}")

            # Get all active positions from Binance
            self.logger.info("📊 STEP 2: Getting active positions from Binance...")
            binance_positions = self._get_all_binance_positions()
            self.logger.info(f"📊 Found {len(binance_positions)} active positions on Binance")

            # This is the critical check - if we have open trades in DB but no positions on Binance,
            # ALL open trades should be detected as orphans
            if len(open_trades) > 0 and len(binance_positions) == 0:
                self.logger.warning("🚨 CRITICAL SCENARIO: Open trades in DB but NO positions on Binance!")
                self.logger.warning("   ALL open trades should be detected as orphans!")

            # Check each open trade
            self.logger.info("📊 STEP 3: Verifying each trade against Binance positions...")
            orphans_detected = []
            trades_verified = 0

            for i, trade in enumerate(open_trades):
                try:
                    trade_id = trade.get('trade_id', 'unknown')
                    self.logger.info(f"🔍 Verifying trade {i+1}/{len(open_trades)}: {trade_id}")

                    is_orphan = self._verify_trade_against_binance(trade, binance_positions)
                    trades_verified += 1

                    self.logger.info(f"📊 Verification result for {trade_id}: {'ORPHAN' if is_orphan else 'VALID'}")

                    if is_orphan:
                        self.logger.warning(f"🚨 ORPHAN DETECTED: Processing {trade_id}")
                        orphan_result = self._mark_trade_as_manually_closed(trade)

                        if orphan_result['success']:
                            orphans_detected.append(orphan_result)
                            self.logger.warning(f"✅ ORPHAN PROCESSED: {trade['trade_id']} | {trade['symbol']} | Marked as manually closed")
                        else:
                            self.logger.error(f"❌ ORPHAN PROCESSING FAILED: {trade_id}")

                except Exception as trade_error:
                    self.logger.error(f"❌ Error verifying trade {trade.get('trade_id', 'unknown')}: {trade_error}")
                    import traceback
                    self.logger.error(f"🔍 Trade verification error traceback: {traceback.format_exc()}")

            # Update last verification time
            self.last_verification = datetime.now()

            # Send summary notification if orphans found
            if orphans_detected:
                self.logger.info(f"📱 Sending orphan summary notification for {len(orphans_detected)} orphans")
                self._send_orphan_summary_notification(orphans_detected)
            else:
                self.logger.info("📱 No orphans detected - no notification needed")

            result = {
                'status': 'completed',
                'timestamp': self.last_verification.isoformat(),
                'open_trades': len(open_trades),
                'trades_verified': trades_verified,
                'orphans_detected': len(orphans_detected),
                'orphan_details': orphans_detected
            }

            self.logger.info(f"✅ VERIFICATION COMPLETE:")
            self.logger.info(f"   📊 Open trades found: {len(open_trades)}")
            self.logger.info(f"   📊 Trades verified: {trades_verified}")
            self.logger.info(f"   📊 Orphans detected: {len(orphans_detected)}")
            self.logger.info(f"   📊 Binance positions: {len(binance_positions)}")

            if len(open_trades) > 0 and len(orphans_detected) == 0 and len(binance_positions) == 0:
                self.logger.error("🚨 POTENTIAL BUG: Open trades exist, no Binance positions, but no orphans detected!")
                self.logger.error("   This suggests the orphan detection logic has a problem")

            return result

        except Exception as e:
            self.logger.error(f"❌ Error in verification cycle: {e}")
            import traceback
            self.logger.error(f"🔍 Verification error traceback: {traceback.format_exc()}")
            return {'status': 'error', 'error': str(e)}

    def _get_open_trades_from_db(self) -> List[Dict[str, Any]]:
        """Get all trades marked as 'open' in the database"""
        try:
            self.logger.info("🔍 DEEP DEBUG: Getting open trades from database...")
            all_trades = self.trade_db.get_all_trades()

            self.logger.info(f"📊 Total trades in database: {len(all_trades)}")

            # Analyze all trades by status
            status_counts = {}
            open_trades = []
            missing_fields_trades = []

            for trade_id, trade_data in all_trades.items():
                trade_status = trade_data.get('trade_status', 'UNKNOWN').upper()
                status_counts[trade_status] = status_counts.get(trade_status, 0) + 1

                if trade_status == 'OPEN':
                    # Check required fields
                    required_fields = ['symbol', 'strategy_name', 'entry_price', 'quantity']
                    missing_fields = [field for field in required_fields if field not in trade_data]

                    if not missing_fields:
                        trade_data['trade_id'] = trade_id  # Ensure trade_id is included
                        open_trades.append(trade_data)
                        self.logger.info(f"   ✅ Open trade: {trade_id} | {trade_data.get('symbol')} | {trade_data.get('side')} | {trade_data.get('quantity')}")
                    else:
                        missing_fields_trades.append((trade_id, missing_fields))
                        self.logger.warning(f"   ❌ Open trade {trade_id} missing fields: {missing_fields}")

            self.logger.info(f"📊 Trade status breakdown:")
            for status, count in status_counts.items():
                self.logger.info(f"   {status}: {count}")

            self.logger.info(f"📊 Usable open trades: {len(open_trades)}")
            self.logger.info(f"📊 Open trades with missing fields: {len(missing_fields_trades)}")

            if len(open_trades) == 0:
                self.logger.warning("🚨 NO OPEN TRADES FOUND!")
                if len(missing_fields_trades) > 0:
                    self.logger.warning("   However, there are open trades with missing fields")
                    self.logger.warning("   This could indicate a data integrity issue")
                else:
                    self.logger.info("   This is normal if all trades are closed")

            return open_trades

        except Exception as e:
            self.logger.error(f"❌ Error getting open trades from database: {e}")
            import traceback
            self.logger.error(f"🔍 Database error traceback: {traceback.format_exc()}")
            return []

    def _get_all_binance_positions(self) -> List[Dict[str, Any]]:
        """Get all active positions from Binance"""
        try:
            self.logger.info("🔍 DEEP DEBUG: Starting Binance position retrieval...")

            if not self.binance_client.is_futures:
                self.logger.warning("⚠️ Spot trading mode - position verification limited")
                return []

            # Test Binance connectivity first
            try:
                self.logger.info("🔍 DEEP DEBUG: Testing Binance API connectivity...")
                account_info = self.binance_client.client.futures_account()
                self.logger.info("✅ DEEP DEBUG: Successfully retrieved Binance account info")

                # Log account balance for context
                total_balance = float(account_info.get('totalWalletBalance', 0))
                available_balance = float(account_info.get('availableBalance', 0))
                self.logger.info(f"📊 Account Balance: Total=${total_balance:.2f}, Available=${available_balance:.2f}")

            except Exception as api_error:
                self.logger.error(f"❌ Binance API error: {api_error}")
                # Check if it's a geographic restriction
                if "IP" in str(api_error) or "geo" in str(api_error).lower() or "restricted" in str(api_error).lower():
                    self.logger.error("🌍 Geographic restriction detected - orphan detection may not work in deployment")
                elif "permission" in str(api_error).lower():
                    self.logger.error("🔐 Permission error - check API key permissions")
                elif "signature" in str(api_error).lower():
                    self.logger.error("🔑 Signature error - check API key and secret")
                else:
                    self.logger.error(f"🚨 Unknown API error type: {type(api_error).__name__}")
                return []

            all_positions = account_info.get('positions', [])
            self.logger.info(f"🔍 DEEP DEBUG: Retrieved {len(all_positions)} total positions from Binance")

            # Log detailed position analysis
            zero_positions = 0
            small_positions = 0
            active_positions = []

            self.logger.info("🔍 DEEP DEBUG: Analyzing all Binance positions...")

            for i, pos in enumerate(all_positions):
                position_amt = float(pos.get('positionAmt', 0))
                symbol = pos.get('symbol', 'UNKNOWN')
                entry_price = float(pos.get('entryPrice', 0))
                unrealized_pnl = float(pos.get('unRealizedProfit', 0))

                if abs(position_amt) == 0:
                    zero_positions += 1
                elif abs(position_amt) < self.position_threshold:
                    small_positions += 1
                    if i < 5:  # Log first 5 small positions for debugging
                        self.logger.info(f"   📊 Small position: {symbol} = {position_amt} (below threshold {self.position_threshold})")
                else:
                    active_positions.append(pos)
                    self.logger.info(f"   ✅ ACTIVE POSITION: {symbol} = {position_amt}, Entry=${entry_price:.4f}, PnL=${unrealized_pnl:.2f}")

            self.logger.info(f"📊 Position Analysis Summary:")
            self.logger.info(f"   Zero positions: {zero_positions}")
            self.logger.info(f"   Small positions (below {self.position_threshold}): {small_positions}")
            self.logger.info(f"   Active positions (above threshold): {len(active_positions)}")

            # If no active positions, this might be why orphan detection isn't working
            if len(active_positions) == 0:
                self.logger.warning("🚨 NO ACTIVE POSITIONS FOUND ON BINANCE!")
                self.logger.warning("   This means any open trades in database should be detected as orphans")
                self.logger.warning("   If orphan detection isn't working, the issue is elsewhere")

            return active_positions

        except Exception as e:
            self.logger.error(f"❌ Error getting Binance positions: {e}")
            import traceback
            self.logger.error(f"🔍 Binance position error traceback: {traceback.format_exc()}")
            return []

    def _verify_trade_against_binance(self, trade: Dict[str, Any], binance_positions: List[Dict[str, Any]]) -> bool:
        """
        Verify if a trade exists on Binance
        Returns True if trade is orphaned (exists in DB but not on Binance)
        """
        try:
            symbol = trade['symbol']
            db_quantity = float(trade['quantity'])
            db_side = trade['side']
            trade_id = trade.get('trade_id', 'unknown')

            self.logger.info(f"🔍 DEEP DEBUG: Verifying trade {trade_id}")
            self.logger.info(f"   📊 DB Trade Details: {symbol} | {db_side} | Qty: {db_quantity}")
            self.logger.info(f"   📊 Available Binance positions: {len(binance_positions)}")

            # Log all Binance positions for this symbol
            symbol_positions = [pos for pos in binance_positions if pos.get('symbol') == symbol]
            self.logger.info(f"   📊 Binance positions for {symbol}: {len(symbol_positions)}")

            for i, pos in enumerate(symbol_positions):
                pos_amt = float(pos.get('positionAmt', 0))
                entry_price = float(pos.get('entryPrice', 0))
                self.logger.info(f"   📊 Binance position {i+1}: amt={pos_amt}, entry=${entry_price}")

            # Find matching Binance position
            matching_position = None
            for pos in binance_positions:
                if pos.get('symbol') == symbol:
                    matching_position = pos
                    break

            if not matching_position:
                # No position found on Binance for this symbol
                self.logger.warning(f"🚨 ORPHAN CANDIDATE: No Binance position found for {symbol} (Trade: {trade_id})")
                self.logger.info(f"   📊 DB expects: {db_side} {db_quantity} {symbol}")
                self.logger.info(f"   📊 Binance has: NO POSITION")
                return True

            # Check if position size matches (within tolerance)
            binance_amt = float(matching_position.get('positionAmt', 0))
            entry_price = float(matching_position.get('entryPrice', 0))

            # Calculate expected position amount based on DB trade
            expected_amt = db_quantity if db_side == 'BUY' else -db_quantity

            self.logger.info(f"   📊 Position comparison for {symbol}:")
            self.logger.info(f"      Expected (DB): {expected_amt}")
            self.logger.info(f"      Actual (Binance): {binance_amt}")
            self.logger.info(f"      Entry Price (Binance): ${entry_price}")

            # If Binance position is significantly different or zero, it's an orphan
            position_difference = abs(binance_amt - expected_amt)
            tolerance = max(0.01, abs(db_quantity) * 0.05)  # 5% tolerance or 0.01 minimum

            self.logger.info(f"   📊 Position difference: {position_difference}")
            self.logger.info(f"   📊 Tolerance threshold: {tolerance}")
            self.logger.info(f"   📊 Position threshold: {self.position_threshold}")

            if abs(binance_amt) < self.position_threshold:
                self.logger.warning(f"🚨 ORPHAN DETECTED: Binance position for {symbol} is zero/minimal ({binance_amt}) - Trade {trade_id}")
                self.logger.info(f"   📊 DB expects: {db_side} {db_quantity}")
                self.logger.info(f"   📊 Binance has: {binance_amt} (below threshold {self.position_threshold})")
                return True

            if position_difference > tolerance:
                self.logger.warning(f"🚨 ORPHAN DETECTED: Position mismatch for {symbol} - Trade {trade_id}")
                self.logger.info(f"   📊 DB expects: {expected_amt}")
                self.logger.info(f"   📊 Binance has: {binance_amt}")
                self.logger.info(f"   📊 Difference: {position_difference} > tolerance {tolerance}")
                return True

            # Position exists and matches - not an orphan
            self.logger.info(f"✅ POSITION VERIFIED: {symbol} matches between DB and Binance")
            self.logger.info(f"   📊 Expected: {expected_amt}, Actual: {binance_amt}, Difference: {position_difference}")
            return False

        except Exception as e:
            self.logger.error(f"❌ Error verifying trade {trade.get('trade_id', 'unknown')}: {e}")
            import traceback
            self.logger.error(f"🔍 Verification error traceback: {traceback.format_exc()}")
            return False

    def _mark_trade_as_manually_closed(self, trade: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mark a trade as manually closed with proper audit trail
        """
        try:
            trade_id = trade['trade_id']
            symbol = trade['symbol']

            # Get current price for PnL calculation
            current_price = self._get_current_price(symbol)
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

            # Prepare update data
            updates = {
                'trade_status': 'CLOSED',
                'exit_price': current_price,
                'exit_time': datetime.now().isoformat(),
                'exit_reason': 'manual',
                'pnl_usdt': round(pnl_usdt, 2),
                'pnl_percentage': round(pnl_percentage, 2),
                'manually_closed': True,
                'orphan_detected': True,
                'orphan_detection_time': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat()
            }

            # Update database
            success = self.trade_db.update_trade(trade_id, updates)

            if success:
                self.logger.info(f"✅ Trade {trade_id} marked as manually closed | PnL: ${pnl_usdt:.2f} ({pnl_percentage:.2f}%)")
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
                self.logger.error(f"❌ Failed to update trade {trade_id} in database")
                return {'success': False, 'trade_id': trade_id, 'error': 'database_update_failed'}

        except Exception as e:
            self.logger.error(f"❌ Error marking trade as manually closed: {e}")
            return {'success': False, 'trade_id': trade.get('trade_id', 'unknown'), 'error': str(e)}

    def _get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for a symbol"""
        try:
            ticker = self.binance_client.get_symbol_ticker(symbol)
            if ticker and 'price' in ticker:
                return float(ticker['price'])
            return None
        except Exception as e:
            self.logger.error(f"❌ Error getting current price for {symbol}: {e}")
            return None

    def _send_orphan_summary_notification(self, orphans: List[Dict[str, Any]]):
        """Send Telegram notification summarizing detected orphans"""
        try:
            if not orphans:
                return

            message_lines = [
                "👻 ORPHAN TRADES DETECTED",
                f"Found {len(orphans)} manually closed positions:",
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
            message_lines.append("ℹ️ Trades marked as manually closed in database")

            self.telegram_reporter.send_message("\n".join(message_lines))

        except Exception as e:
            self.logger.error(f"❌ Error sending orphan summary notification: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Get current status of the orphan detection system"""
        return {
            'last_verification': self.last_verification.isoformat(),
            'verification_interval': self.verification_interval,
            'position_threshold': self.position_threshold,
            'next_verification_in': max(0, self.verification_interval - (datetime.now() - self.last_verification).total_seconds())
        }

    def force_verification(self) -> Dict[str, Any]:
        """Force immediate verification regardless of interval"""
        self.logger.info("🔧 FORCING IMMEDIATE ORPHAN VERIFICATION")
        self.last_verification = datetime.now() - timedelta(seconds=self.verification_interval + 1)
        return self.run_verification_cycle()

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
            binance_positions = self._get_all_binance_positions()
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
                'last_verification': self.last_verification.isoformat()
            }

            self.logger.info(f"🔍 DEBUG: Verification status: {status}")
            return status

        except Exception as e:
            self.logger.error(f"❌ Error in debug verification: {e}")
            return {'error': str(e)}