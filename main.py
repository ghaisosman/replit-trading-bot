import asyncio
import logging
import signal
import sys
import threading
import time
from src.bot_manager import BotManager
from src.utils.logger import setup_logger
from web_dashboard import app

# Global bot manager for signal handling and web interface access
bot_manager = None
shutdown_event = asyncio.Event()
web_server_running = False

# Make bot manager accessible to web interface
import sys
sys.modules['__main__'].bot_manager = None

def signal_handler(signum, frame):
    """Handle termination signals"""
    print("\n🛑 Shutdown signal received...")
    # Set the shutdown event to trigger graceful shutdown
    if shutdown_event:
        shutdown_event.set()

def run_web_dashboard():
    """Run web dashboard in separate thread - keeps running even if bot stops"""
    global web_server_running
    logger = logging.getLogger(__name__)

    try:
        web_server_running = True
        logger.info("🌐 WEB DASHBOARD: Starting persistent web interface on http://0.0.0.0:5000")
        logger.info("🌐 WEB DASHBOARD: Dashboard will remain active even when bot stops")

        # Run Flask with minimal logging to reduce console noise
        import logging as flask_logging
        flask_log = flask_logging.getLogger('werkzeug')
        flask_log.setLevel(flask_logging.WARNING)

        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False, threaded=True)
    except Exception as e:
        logger.error(f"Web dashboard error: {e}")
    finally:
        web_server_running = False

async def main():
    global bot_manager, web_server_running

    # Setup logging
    setup_logger()
    logger = logging.getLogger(__name__)

    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("Starting Multi-Strategy Trading Bot with Persistent Web Interface")

    # Start web dashboard in background thread - this will keep running
    web_thread = threading.Thread(target=run_web_dashboard, daemon=False)  # Not daemon so it persists
    web_thread.start()

    # Give web dashboard time to start
    await asyncio.sleep(3)
    logger.info("🌐 Web Dashboard accessible and will remain active")

    try:
        # Initialize the bot manager
        bot_manager = BotManager()

        # Make bot manager accessible to web interface
        sys.modules['__main__'].bot_manager = bot_manager

        # Start the bot in a task so we can handle shutdown signals
        logger.info("🚀 Starting trading bot main loop...")
        bot_task = asyncio.create_task(bot_manager.start())
        shutdown_task = asyncio.create_task(shutdown_event.wait())

        # Wait for either the bot to complete or shutdown signal
        done, pending = await asyncio.wait(
            [bot_task, shutdown_task],
            return_when=asyncio.FIRST_COMPLETED
        )

        # Check if shutdown was triggered
        if shutdown_task in done:
            logger.info("🛑 Shutdown signal received, stopping bot...")
            await bot_manager.stop("Manual shutdown via Ctrl+C or SIGTERM")

        # Cancel any pending tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Keep web server running after bot stops
        logger.info("🔴 Bot stopped but web interface remains active for control")
        logger.info("💡 You can restart the bot using the web interface")

        # Keep the main process alive to maintain web interface
        while web_server_running:
            await asyncio.sleep(5)

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        if bot_manager:
            await bot_manager.stop("Manual shutdown via keyboard interrupt")
        logger.info("🌐 Web interface remains active")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if bot_manager:
            await bot_manager.stop(f"Unexpected error: {str(e)}")
        logger.info("🌐 Web interface remains active despite bot error")

if __name__ == "__main__":
    # Setup logging first
    setup_logger()
    logger = logging.getLogger(__name__)

    # Initialize bot_manager as None initially
    bot_manager = None

    # Make it globally accessible for web interface
    sys.modules[__name__].bot_manager = None

    # Start web dashboard in persistent background thread
    web_thread = threading.Thread(target=run_web_dashboard, daemon=False)
    web_thread.start()

    # Give web dashboard time to start
    time.sleep(3)
    logger.info("🌐 Persistent Web Dashboard started - accessible via Replit webview")

    try:
        # Create and setup bot manager
        bot_manager = BotManager()
        sys.modules[__name__].bot_manager = bot_manager

        # Run the bot
        logger.info("🚀 Starting bot from console...")
        asyncio.run(bot_manager.start())

    except KeyboardInterrupt:
        logger.info("🔴 BOT STOPPED: Manual shutdown via console (Ctrl+C)")
        # Send stop notification
        try:
            if bot_manager:
                bot_manager.telegram_reporter.report_bot_stopped("Manual shutdown via Ctrl+C")
        except:
            pass

        # Keep web interface running
        logger.info("🌐 Web interface remains active for bot control")
        logger.info("💡 The process will continue running to keep web interface accessible")

        # Keep process alive for web interface
        try:
            while web_server_running:
                time.sleep(5)
        except KeyboardInterrupt:
            logger.info("🔴 Final shutdown - terminating web interface")

    except Exception as e:
        logger.error(f"Bot error: {e}")
        if bot_manager:
            try:
                bot_manager.telegram_reporter.report_bot_stopped(f"Error: {str(e)}")
            except:
                pass

        # Keep web interface running even on error
        logger.info("🌐 Web interface remains active despite bot error")
        try:
            while web_server_running:
                time.sleep(5)
        except KeyboardInterrupt:
            logger.info("🔴 Final shutdown - terminating web interface")
import asyncio
import logging
import signal
import sys
import threading
import time
from datetime import datetime

from src.order_manager import OrderManager
from src.position import Position
from src.risk_manager import RiskManager
from src.strategy_manager import StrategyManager
from src.telegram_reporter import TelegramReporter
from src.utils.binance_client import BinanceClient
from src.utils.database import Database
from src.utils.logger import setup_logger
from src.utils.technical_indicators import TechnicalIndicators
from web_dashboard import app

# Set default environment variables
DEFAULT_ENV_VARS = {
    'API_KEY': 'YOUR_API_KEY',
    'API_SECRET': 'YOUR_API_SECRET',
    'TELEGRAM_BOT_TOKEN': 'YOUR_TELEGRAM_BOT_TOKEN',
    'TELEGRAM_CHAT_ID': 'YOUR_TELEGRAM_CHAT_ID',
    'DATABASE_URL': 'sqlite:///./trading_bot.db',
    'PRICE_UPDATE_INTERVAL': '5',
    'MAX_ACTIVE_TRADES': '3',
    'DEFAULT_TRADE_SIZE': '25',
    'PNL_CHECK_INTERVAL': '30',
    'PNL_TELEGRAM_REPORT_THRESHOLD': '10',
    'RISK_FREE_RATE': '0.05',  # Representing 5%
    'HISTORICAL_DATA_LOOKBACK': '30',
    'RSI_OVERBOUGHT_THRESHOLD': '70',
    'RSI_OVERSOLD_THRESHOLD': '30',
    'EMA_FAST_PERIOD': '12',
    'EMA_SLOW_PERIOD': '26',
    'MACD_SIGNAL_PERIOD': '9',
    'STOCH_RSI_K': '14',
    'STOCH_RSI_D': '3',
    'STOCH_RSI_SMOOTHING': '3',
}

class BotManager:
    def __init__(self):
        # Initialize logger and set up environment variables
        setup_logger()
        self.logger = logging.getLogger(__name__)
        self.telegram_reporter = None  # Initialize to None
        self.binance_client = None  # Initialize to None
        self.strategy_manager = None
        self.order_manager = None
        self.risk_manager = None
        self.database = None  # Initialize the database attribute

        # Load environment variables, using defaults if not set
        self.api_key = sys.modules['__main__'].bot_manager.get_env_variable('API_KEY', DEFAULT_ENV_VARS)
        self.api_secret = sys.modules['__main__'].bot_manager.get_env_variable('API_SECRET', DEFAULT_ENV_VARS)
        self.telegram_bot_token = sys.modules['__main__'].bot_manager.get_env_variable('TELEGRAM_BOT_TOKEN', DEFAULT_ENV_VARS)
        self.telegram_chat_id = sys.modules['__main__'].bot_manager.get_env_variable('TELEGRAM_CHAT_ID', DEFAULT_ENV_VARS)
        self.database_url = sys.modules['__main__'].bot_manager.get_env_variable('DATABASE_URL', DEFAULT_ENV_VARS)
        self.price_update_interval = int(sys.modules['__main__'].bot_manager.get_env_variable('PRICE_UPDATE_INTERVAL', DEFAULT_ENV_VARS))
        self.max_active_trades = int(sys.modules['__main__'].bot_manager.get_env_variable('MAX_ACTIVE_TRADES', DEFAULT_ENV_VARS))
        self.default_trade_size = float(sys.modules['__main__'].bot_manager.get_env_variable('DEFAULT_TRADE_SIZE', DEFAULT_ENV_VARS))
        self.pnl_check_interval = int(sys.modules['__main__'].bot_manager.get_env_variable('PNL_CHECK_INTERVAL', DEFAULT_ENV_VARS))
        self.pnl_telegram_report_threshold = float(sys.modules['__main__'].bot_manager.get_env_variable('PNL_TELEGRAM_REPORT_THRESHOLD', DEFAULT_ENV_VARS))
        self.risk_free_rate = float(sys.modules['__main__'].bot_manager.get_env_variable('RISK_FREE_RATE', DEFAULT_ENV_VARS))
        self.historical_data_lookback = int(sys.modules['__main__'].bot_manager.get_env_variable('HISTORICAL_DATA_LOOKBACK', DEFAULT_ENV_VARS))
        self.rsi_overbought_threshold = int(sys.modules['__main__'].bot_manager.get_env_variable('RSI_OVERBOUGHT_THRESHOLD', DEFAULT_ENV_VARS))
        self.rsi_oversold_threshold = int(sys.modules['__main__'].bot_manager.get_env_variable('RSI_OVERSOLD_THRESHOLD', DEFAULT_ENV_VARS))
        self.ema_fast_period = int(sys.modules['__main__'].bot_manager.get_env_variable('EMA_FAST_PERIOD', DEFAULT_ENV_VARS))
        self.ema_slow_period = int(sys.modules['__main__'].bot_manager.get_env_variable('EMA_SLOW_PERIOD', DEFAULT_ENV_VARS))
        self.macd_signal_period = int(sys.modules['__main__'].bot_manager.get_env_variable('MACD_SIGNAL_PERIOD', DEFAULT_ENV_VARS))
        self.stoch_rsi_k = int(sys.modules['__main__'].bot_manager.get_env_variable('STOCH_RSI_K', DEFAULT_ENV_VARS))
        self.stoch_rsi_d = int(sys.modules['__main__'].bot_manager.get_env_variable('STOCH_RSI_D', DEFAULT_ENV_VARS))
        self.stoch_rsi_smoothing = int(sys.modules['__main__'].bot_manager.get_env_variable('STOCH_RSI_SMOOTHING', DEFAULT_ENV_VARS))

        # Log the loaded configurations
        self.logger.info("Loaded Configurations:")
        self.logger.info(f"  API Key: {'*' * (len(self.api_key) - 4) + self.api_key[-4:] if self.api_key else 'Not Set'}")
        self.logger.info(f"  Telegram Bot Token: {'Set' if self.telegram_bot_token else 'Not Set'}")
        self.logger.info(f"  Database URL: {self.database_url}")
        self.logger.info(f"  Price Update Interval: {self.price_update_interval} seconds")
        self.logger.info(f"  Max Active Trades: {self.max_active_trades}")
        self.logger.info(f"  Default Trade Size: {self.default_trade_size}")
        self.logger.info(f"  PNL Check Interval: {self.pnl_check_interval} seconds")
        self.logger.info(f"  PNL Telegram Report Threshold: {self.pnl_telegram_report_threshold}")
        self.logger.info(f"  Risk Free Rate: {self.risk_free_rate}")
        self.logger.info(f"  Historical Data Lookback: {self.historical_data_lookback} days")
        self.logger.info(f"  RSI Overbought Threshold: {self.rsi_overbought_threshold}")
        self.logger.info(f"  RSI Oversold Threshold: {self.rsi_oversold_threshold}")
        self.logger.info(f"  EMA Fast Period: {self.ema_fast_period}")
        self.logger.info(f"  EMA Slow Period: {self.ema_slow_period}")
        self.logger.info(f"  MACD Signal Period: {self.macd_signal_period}")
        self.logger.info(f"  Stoch RSI K: {self.stoch_rsi_k}")
        self.logger.info(f"  Stoch RSI D: {self.stoch_rsi_d}")
        self.logger.info(f"  Stoch RSI Smoothing: {self.stoch_rsi_smoothing}")

        self._stop_event = asyncio.Event()  # Initialize the stop event
        self._pnl_check_running = False  # Track PNL background task

    def get_env_variable(self, var_name, default_vars):
        """Fetch environment variable or return default value."""
        value = sys.modules['__main__'].bot_manager.get_env_variable_static(var_name)
        return value if value is not None else default_vars.get(var_name)

    @staticmethod
    def get_env_variable_static(var_name):
        """Static method to fetch environment variable."""
        return sys.modules['__main__'].app.config.get(var_name)

    async def start(self):
        """Start the trading bot."""
        self.logger.info("Bot is starting...")
        try:
            # Initialize Telegram reporter
            self.telegram_reporter = TelegramReporter(self.telegram_bot_token, self.telegram_chat_id)
            await self.telegram_reporter.initialize()

            # Initialize Binance client
            self.binance_client = BinanceClient(self.api_key, self.api_secret)

            # Initialize database
            self.database = Database(self.database_url)
            await self.database.connect()

            # Initialize TechnicalIndicators
            self.technical_indicators = TechnicalIndicators(
                lookback=self.historical_data_lookback,
                rsi_overbought=self.rsi_overbought_threshold,
                rsi_oversold=self.rsi_oversold_threshold,
                ema_fast=self.ema_fast_period,
                ema_slow=self.ema_slow_period,
                macd_signal=self.macd_signal_period,
                stoch_rsi_k=self.stoch_rsi_k,
                stoch_rsi_d=self.stoch_rsi_d,
                stoch_rsi_smoothing=self.stoch_rsi_smoothing
            )

            # Initialize other components
            self.risk_manager = RiskManager(risk_free_rate=self.risk_free_rate)
            self.order_manager = OrderManager(self.binance_client, self.database)
            self.strategy_manager = StrategyManager(self, self.binance_client, self.database, self.technical_indicators, self.default_trade_size, self.risk_manager)

            # Load active positions from database
            await self.order_manager.load_active_positions()

            # Start background tasks
            asyncio.create_task(self._update_prices())
            asyncio.create_task(self._check_and_report_pnl())

            # Bot is now started
            await self.telegram_reporter.report_bot_started()
            self.logger.info("Trading bot started successfully.")

            # Main trading loop
            while not self._stop_event.is_set():
                await self._process_strategies()
                await asyncio.sleep(self.price_update_interval)

        except Exception as e:
            self.logger.error(f"Error during bot startup: {e}", exc_info=True)
            if self.telegram_reporter:
                await self.telegram_reporter.report_error(f"Bot failed to start: {e}")

            # Stop the bot if it encounters an error during startup
            await self.stop(f"Error during startup: {e}")

    async def stop(self, reason=""):
        """Stop the trading bot."""
        if self._stop_event.is_set():
            self.logger.info("Bot is already stopping...")
            return

        self.logger.info(f"Bot is stopping. Reason: {reason}")
        self._stop_event.set()  # Set the stop event immediately

        try:
            # Stop background tasks
            tasks_to_cancel = [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
            for task in tasks_to_cancel:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            # Close any open orders, cancelling them
            if self.order_manager:
                await self.order_manager.close_all_positions()

            # Report bot stopped
            if self.telegram_reporter:
                await self.telegram_reporter.report_bot_stopped(reason)

            # Close database connection
            if self.database:
                await self.database.close()

            self.logger.info("Bot has stopped successfully.")

        except Exception as e:
            self.logger.error(f"Error during bot shutdown: {e}", exc_info=True)
            if self.telegram_reporter:
                await self.telegram_reporter.report_error(f"Error during shutdown: {e}")

    async def _process_strategies(self):
        """Process trading strategies."""
        try:
            # Get all available strategies
            strategies = self.strategy_manager.get_strategies()

            # Execute each strategy
            for strategy in strategies:
                await self.strategy_manager.execute_strategy(strategy)

        except Exception as e:
            self.logger.error(f"Error processing strategies: {e}", exc_info=True)
            if self.telegram_reporter:
                await self.telegram_reporter.report_error(f"Error processing strategies: {e}")

        # Display current positions periodically
        active_positions = self.order_manager.get_active_positions()
        if active_positions and hasattr(self, '_last_main_position_log'):
            time_since_log = datetime.now() - self._last_main_position_log
            if time_since_log.seconds < 60:  # Only log every minute
                return

        if active_positions:
            self._last_main_position_log = datetime.now()
            print(f"📊 Active trades: {len(active_positions)}")
        elif not hasattr(self, '_last_main_position_log'):
            self._last_main_position_log = datetime.now()

    async def _update_prices(self):
        """Update prices in the order manager."""
        while not self._stop_event.is_set():
            try:
                await self.order_manager.update_all_prices()
                await asyncio.sleep(self.price_update_interval)
            except Exception as e:
                self.logger.error(f"Error updating prices: {e}", exc_info=True)
                if self.telegram_reporter:
                    await self.telegram_reporter.report_error(f"Error updating prices: {e}")

    async def _check_and_report_pnl(self):
        """Check and report profit and loss."""
        if self._pnl_check_running:
            self.logger.warning("PNL check is already running. Skipping...")
            return

        self._pnl_check_running = True
        try:
            while not self._stop_event.is_set():
                await asyncio.sleep(self.pnl_check_interval)

                # Get total PNL from the order manager
                total_pnl = self.order_manager.get_total_pnl()

                # Check if PNL exceeds the threshold
                if abs(total_pnl) > self.pnl_telegram_report_threshold:
                    # Report the PNL to Telegram
                    message = f"Total PNL: {total_pnl:.2f}"
                    await self.telegram_reporter.report_message(message)

        except Exception as e:
            self.logger.error(f"Error checking and reporting PNL: {e}", exc_info=True)
            if self.telegram_reporter:
                await self.telegram_reporter.report_error(f"Error checking and reporting PNL: {e}")
        finally:
            self._pnl_check_running = False