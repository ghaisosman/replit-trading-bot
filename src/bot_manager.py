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
    """Enhanced Bot Manager with integrated orphan detection and improved error handling"""

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
        self.initialization_successful = False

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

            self.initialization_successful = True
            self.logger.info("✅ All bot components initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"❌ Bot initialization failed: {e}")
            self.initialization_successful = False
            return False

    async def _load_existing_positions(self):
        """Load existing positions with orphan detection"""
        try:
            self.logger.info("📊 Loading existing positions...")
            
            # Get positions from database
            all_trades = self.trade_db.get_all_trades()
            open_positions = 0
            
            for trade_id, trade_data in all_trades.items():
                if trade_data.get('trade_status') == 'OPEN':
                    open_positions += 1
                    self.logger.info(f"📈 Found open position: {trade_data.get('symbol')} - {trade_data.get('strategy_name')}")
            
            self.logger.info(f"📊 Loaded {open_positions} open positions from database")
            
        except Exception as e:
            self.logger.error(f"❌ Error loading existing positions: {e}")

    async def _run_orphan_check(self):
        """Run orphan detection check"""
        try:
            if self.orphan_detector:
                orphans = await self.orphan_detector.detect_orphans()
                if orphans:
                    self.logger.warning(f"⚠️ Found {len(orphans)} orphan positions")
                    for orphan in orphans:
                        self.logger.warning(f"   - {orphan}")
                else:
                    self.logger.info("✅ No orphan positions detected")
        except Exception as e:
            self.logger.error(f"❌ Error during orphan check: {e}")

    async def start_trading(self):
        """Start the trading bot with improved error handling"""
        if not self.initialization_successful:
            self.logger.error("❌ Bot not properly initialized. Please initialize first.")
            return False

        if self.is_running:
            self.logger.warning("⚠️ Bot is already running")
            return True

        try:
            self.logger.info("🚀 Starting trading bot...")
            
            # Validate configuration
            if not global_config.validate_config():
                self.logger.error("❌ Configuration validation failed")
                return False

            # Check if ready for live trading
            if not global_config.is_live_trading_ready():
                self.logger.error("❌ Not ready for live trading")
                return False

            self.is_running = True
            self.logger.info("✅ Trading bot started successfully")
            
            # Send startup notification
            if self.telegram_reporter:
                await self.telegram_reporter.send_startup_message()
            
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to start trading bot: {e}")
            self.is_running = False
            return False

    async def stop_trading(self, reason: str = "Manual stop"):
        """Stop the trading bot"""
        if not self.is_running:
            self.logger.warning("⚠️ Bot is not running")
            return True

        try:
            self.logger.info(f"🛑 Stopping trading bot: {reason}")
            
            # Send shutdown notification
            if self.telegram_reporter:
                await self.telegram_reporter.send_shutdown_message(reason)
            
            self.is_running = False
            self.logger.info("✅ Trading bot stopped successfully")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error stopping trading bot: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get current bot status"""
        try:
            active_positions = len(self.order_manager.get_active_positions()) if self.order_manager else 0
            balance = self.balance_fetcher.get_usdt_balance() if self.balance_fetcher else 0.0
            
            return {
                'is_running': self.is_running,
                'active_positions': active_positions,
                'balance': balance,
                'last_orphan_check': self.last_orphan_check.isoformat() if self.last_orphan_check else None,
                'initialization_successful': self.initialization_successful
            }
        except Exception as e:
            self.logger.error(f"❌ Error getting bot status: {e}")
            return {
                'is_running': False,
                'active_positions': 0,
                'balance': 0.0,
                'error': str(e)
            }

    def force_orphan_check(self) -> Dict[str, Any]:
        """Force an orphan detection check"""
        try:
            if not self.orphan_detector:
                return {'success': False, 'error': 'Orphan detector not initialized'}
            
            orphans = asyncio.run(self.orphan_detector.detect_orphans())
            return {
                'success': True,
                'orphans_found': len(orphans),
                'orphans': orphans
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def reset_orphan_detector(self):
        """Reset the orphan detector"""
        try:
            if self.orphan_detector:
                self.orphan_detector.reset()
                self.logger.info("✅ Orphan detector reset successfully")
        except Exception as e:
            self.logger.error(f"❌ Error resetting orphan detector: {e}")

# Global bot manager instance
bot_manager = BotManager()