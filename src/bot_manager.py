import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from src.binance_client.client import BinanceClientWrapper
from src.execution_engine.order_manager import OrderManager
from src.execution_engine.trade_database import TradeDatabase
from src.execution_engine.reliable_orphan_detector import ReliableOrphanDetector
from src.analytics.trade_logger import trade_logger
from src.reporting.telegram_reporter import TelegramReporter
from src.config.global_config import global_config
from src.config.trading_config import trading_config_manager
from src.data_fetcher.price_fetcher import PriceFetcher
from src.data_fetcher.balance_fetcher import BalanceFetcher
from src.strategy_processor.signal_processor import SignalProcessor

class BotManager:
    """Enhanced Bot Manager with integrated orphan detection"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Core components
        self.binance_client = None
        self.telegram_reporter = None
        self.trade_db = None
        self.order_manager = None
        self.orphan_detector = None

        # Data fetchers
        self.price_fetcher = None
        self.balance_fetcher = None

        # Processing
        self.signal_processor = None

        # State management
        self.is_running = False
        self.last_orphan_check = datetime.now()
        self.orphan_check_interval = 30  # seconds

        self.logger.info("🤖 Enhanced Bot Manager initialized")

    async def initialize(self):
        """Initialize all bot components with enhanced error handling"""
        try:
            self.logger.info("🚀 Initializing bot components...")

            # Initialize Binance client
            self.binance_client = BinanceClientWrapper()
            if not self.binance_client.test_connection():
                self.logger.warning("⚠️ Binance API connection issues detected")
                self.logger.info("✅ WebSocket fallback mechanisms available")

            # Initialize Telegram reporter
            self.telegram_reporter = TelegramReporter()

            # Initialize trade database with cloud sync
            self.trade_db = TradeDatabase()

            # Initialize enhanced orphan detector
            self.orphan_detector = ReliableOrphanDetector(
                self.binance_client,
                self.trade_db,
                self.telegram_reporter
            )

            # Initialize order manager
            self.order_manager = OrderManager(self.binance_client, self.telegram_reporter)

            # Initialize data fetchers
            self.price_fetcher = PriceFetcher(self.binance_client)
            self.balance_fetcher = BalanceFetcher(self.binance_client)

            # Initialize signal processor
            self.signal_processor = SignalProcessor(
                self.binance_client,
                self.order_manager,
                self.telegram_reporter
            )

            # Load existing positions
            await self._load_existing_positions()

            # Run initial orphan check
            await self._run_orphan_check()

            self.logger.info("✅ All bot components initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"❌ Bot initialization failed: {e}")
            return False

    async def _load_existing_positions(self):
        """Load existing positions with orphan detection"""
        try:
            self.logger.info("📊 Loading existing positions...")

            # Get recovery candidates from database
            candidates = self.trade_db.get_recovery_candidates()

            if candidates:
                self.logger.info(f"🔍 Found {len(candidates)} recovery candidates")

                # Attempt to recover positions
                for candidate in candidates:
                    try:
                        await self.order_manager.recover_position_from_data(candidate)
                        self.logger.info(f"✅ Recovered position: {candidate['symbol']}")
                    except Exception as recovery_error:
                        self.logger.warning(f"⚠️ Could not recover {candidate['symbol']}: {recovery_error}")
            else:
                self.logger.info("📊 No existing positions to recover")

        except Exception as e:
            self.logger.error(f"❌ Error loading existing positions: {e}")

    async def _run_orphan_check(self):
        """Run orphan detection check"""
        try:
            current_time = datetime.now()
            if (current_time - self.last_orphan_check).total_seconds() >= self.orphan_check_interval:
                self.logger.info("👻 Running orphan detection check...")

                result = self.orphan_detector.run_verification_cycle()

                if result.get('status') == 'completed':
                    orphans = result.get('orphans_detected', 0)
                    if orphans > 0:
                        self.logger.warning(f"🚨 Detected and processed {orphans} orphan trades")
                    else:
                        self.logger.info("✅ No orphan trades detected")
                elif result.get('status') == 'error':
                    self.logger.error(f"❌ Orphan detection error: {result.get('error', 'unknown')}")

                self.last_orphan_check = current_time

        except Exception as e:
            self.logger.error(f"❌ Orphan check failed: {e}")

    async def start_trading(self):
        """Start the trading bot with enhanced monitoring"""
        try:
            self.logger.info("🚀 Starting enhanced trading bot...")

            if not await self.initialize():
                self.logger.error("❌ Bot initialization failed")
                return False

            self.is_running = True

            # Send startup notification
            try:
                await self.telegram_reporter.send_message_async(
                    "🤖 ENHANCED TRADING BOT STARTED\n"
                    f"✅ All systems initialized\n"
                    f"👻 Orphan detection active\n" 
                    f"☁️ Cloud sync enabled\n"
                    f"📊 Ready for trading!"
                )
            except Exception as notification_error:
                self.logger.warning(f"Startup notification failed: {notification_error}")

            # Main trading loop
            while self.is_running:
                try:
                    # Run orphan detection
                    await self._run_orphan_check()

                    # Process trading signals
                    await self.signal_processor.process_all_strategies()

                    # Update balances
                    await self.balance_fetcher.update_balance()

                    # Short sleep to prevent excessive CPU usage
                    await asyncio.sleep(1)

                except Exception as loop_error:
                    self.logger.error(f"❌ Trading loop error: {loop_error}")
                    await asyncio.sleep(5)  # Wait before retrying

            self.logger.info("⏹️ Trading bot stopped")
            return True

        except Exception as e:
            self.logger.error(f"❌ Trading bot failed: {e}")
            return False

    async def stop_trading(self):
        """Stop the trading bot gracefully"""
        try:
            self.logger.info("⏹️ Stopping trading bot...")
            self.is_running = False

            # Run final orphan check
            await self._run_orphan_check()

            # Save database
            if self.trade_db:
                self.trade_db._save_database()

            # Send shutdown notification
            try:
                await self.telegram_reporter.send_message_async(
                    "⏹️ TRADING BOT STOPPED\n"
                    "✅ All positions saved\n"
                    "📊 Database synchronized"
                )
            except Exception as notification_error:
                self.logger.warning(f"Shutdown notification failed: {notification_error}")

            self.logger.info("✅ Trading bot stopped gracefully")

        except Exception as e:
            self.logger.error(f"❌ Error stopping trading bot: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive bot status"""
        try:
            status = {
                'is_running': self.is_running,
                'timestamp': datetime.now().isoformat(),
                'components': {
                    'binance_client': self.binance_client is not None,
                    'trade_database': self.trade_db is not None,
                    'order_manager': self.order_manager is not None,
                    'orphan_detector': self.orphan_detector is not None,
                    'telegram_reporter': self.telegram_reporter is not None
                }
            }

            # Add orphan detector status
            if self.orphan_detector:
                status['orphan_detector_status'] = self.orphan_detector.get_status()

            # Add database stats
            if self.trade_db:
                all_trades = self.trade_db.get_all_trades()
                open_trades = [t for t in all_trades.values() if t.get('trade_status') == 'OPEN']
                status['database'] = {
                    'total_trades': len(all_trades),
                    'open_trades': len(open_trades)
                }

            # Add order manager stats
            if self.order_manager:
                status['active_positions'] = len(self.order_manager.active_positions)

            return status

        except Exception as e:
            self.logger.error(f"❌ Error getting status: {e}")
            return {'error': str(e)}

    def force_orphan_check(self) -> Dict[str, Any]:
        """Force immediate orphan detection check"""
        try:
            self.logger.info("🔧 Forcing immediate orphan check...")

            if self.orphan_detector:
                result = self.orphan_detector.force_verification()
                self.last_orphan_check = datetime.now()
                return result
            else:
                return {'error': 'Orphan detector not initialized'}

        except Exception as e:
            self.logger.error(f"❌ Force orphan check failed: {e}")
            return {'error': str(e)}

    def reset_orphan_detector(self):
        """Reset orphan detector failure counter"""
        try:
            if self.orphan_detector:
                self.orphan_detector.reset_failure_counter()
                self.logger.info("✅ Orphan detector reset successfully")
                return True
            else:
                self.logger.warning("⚠️ Orphan detector not initialized")
                return False

        except Exception as e:
            self.logger.error(f"❌ Orphan detector reset failed: {e}")
            return False

# Global bot manager instance
bot_manager = BotManager()