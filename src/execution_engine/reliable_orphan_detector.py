
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
        """
        Main verification cycle - checks all open trades against Binance positions
        Returns summary of verification results
        """
        try:
            if not self.should_run_verification():
                return {'status': 'skipped', 'reason': 'interval_not_reached'}

            self.logger.info("🔍 ORPHAN VERIFICATION: Starting verification cycle")
            
            # Get all open trades from database
            open_trades = self._get_open_trades_from_db()
            if not open_trades:
                self.logger.debug("📊 No open trades found in database")
                self.last_verification = datetime.now()
                return {'status': 'completed', 'open_trades': 0, 'orphans_detected': 0}

            self.logger.info(f"📊 Found {len(open_trades)} open trades to verify")

            # Get all active positions from Binance
            binance_positions = self._get_all_binance_positions()
            self.logger.info(f"📊 Found {len(binance_positions)} active positions on Binance")

            # Check each open trade
            orphans_detected = []
            trades_verified = 0

            for trade in open_trades:
                try:
                    is_orphan = self._verify_trade_against_binance(trade, binance_positions)
                    trades_verified += 1

                    if is_orphan:
                        orphan_result = self._mark_trade_as_manually_closed(trade)
                        if orphan_result['success']:
                            orphans_detected.append(orphan_result)
                            self.logger.warning(f"👻 ORPHAN DETECTED: {trade['trade_id']} | {trade['symbol']} | Marked as manually closed")

                except Exception as trade_error:
                    self.logger.error(f"❌ Error verifying trade {trade.get('trade_id', 'unknown')}: {trade_error}")

            # Update last verification time
            self.last_verification = datetime.now()

            # Send summary notification if orphans found
            if orphans_detected:
                self._send_orphan_summary_notification(orphans_detected)

            result = {
                'status': 'completed',
                'timestamp': self.last_verification.isoformat(),
                'open_trades': len(open_trades),
                'trades_verified': trades_verified,
                'orphans_detected': len(orphans_detected),
                'orphan_details': orphans_detected
            }

            self.logger.info(f"✅ VERIFICATION COMPLETE: {trades_verified} trades verified, {len(orphans_detected)} orphans detected")
            return result

        except Exception as e:
            self.logger.error(f"❌ Error in verification cycle: {e}")
            import traceback
            self.logger.error(f"🔍 Verification error traceback: {traceback.format_exc()}")
            return {'status': 'error', 'error': str(e)}

    def _get_open_trades_from_db(self) -> List[Dict[str, Any]]:
        """Get all trades marked as 'open' in the database"""
        try:
            all_trades = self.trade_db.get_all_trades()
            open_trades = []

            for trade_id, trade_data in all_trades.items():
                if trade_data.get('trade_status', '').upper() == 'OPEN':
                    # Ensure required fields exist
                    if all(field in trade_data for field in ['symbol', 'strategy_name', 'entry_price', 'quantity']):
                        trade_data['trade_id'] = trade_id  # Ensure trade_id is included
                        open_trades.append(trade_data)
                    else:
                        self.logger.warning(f"⚠️ Trade {trade_id} missing required fields, skipping verification")

            return open_trades

        except Exception as e:
            self.logger.error(f"❌ Error getting open trades from database: {e}")
            return []

    def _get_all_binance_positions(self) -> List[Dict[str, Any]]:
        """Get all active positions from Binance"""
        try:
            if not self.binance_client.is_futures:
                self.logger.warning("⚠️ Spot trading mode - position verification limited")
                return []

            account_info = self.binance_client.client.futures_account()
            all_positions = account_info.get('positions', [])

            # Filter for positions with meaningful amounts
            active_positions = []
            for pos in all_positions:
                position_amt = float(pos.get('positionAmt', 0))
                if abs(position_amt) >= self.position_threshold:
                    active_positions.append(pos)

            return active_positions

        except Exception as e:
            self.logger.error(f"❌ Error getting Binance positions: {e}")
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

            # Find matching Binance position
            matching_position = None
            for pos in binance_positions:
                if pos.get('symbol') == symbol:
                    matching_position = pos
                    break

            if not matching_position:
                # No position found on Binance for this symbol
                self.logger.debug(f"🔍 No Binance position found for {symbol} - potential orphan")
                return True

            # Check if position size matches (within tolerance)
            binance_amt = float(matching_position.get('positionAmt', 0))
            
            # Calculate expected position amount based on DB trade
            expected_amt = db_quantity if db_side == 'BUY' else -db_quantity

            # If Binance position is significantly different or zero, it's an orphan
            position_difference = abs(binance_amt - expected_amt)
            tolerance = max(0.01, db_quantity * 0.05)  # 5% tolerance or 0.01 minimum

            if abs(binance_amt) < self.position_threshold:
                self.logger.debug(f"🔍 Binance position for {symbol} is zero/minimal ({binance_amt}) - orphan detected")
                return True

            if position_difference > tolerance:
                self.logger.debug(f"🔍 Position mismatch for {symbol}: DB expects {expected_amt}, Binance has {binance_amt} - difference: {position_difference}")
                return True

            # Position exists and matches - not an orphan
            self.logger.debug(f"✅ Position verified for {symbol}: {binance_amt}")
            return False

        except Exception as e:
            self.logger.error(f"❌ Error verifying trade {trade.get('trade_id', 'unknown')}: {e}")
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

            self.telegram_reporter.send_custom_message("\n".join(message_lines))

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
        self.last_verification = datetime.now() - timedelta(seconds=self.verification_interval + 1)
        return self.run_verification_cycle()
