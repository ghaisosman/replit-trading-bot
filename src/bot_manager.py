import asyncio
import logging
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from src.config.global_config import global_config
from src.binance_client.client import BinanceClientWrapper
from src.data_fetcher.price_fetcher import PriceFetcher
from src.data_fetcher.balance_fetcher import BalanceFetcher
from src.strategy_processor.signal_processor import SignalProcessor
from src.execution_engine.order_manager import OrderManager
from src.execution_engine.strategies.rsi_oversold_config import RSIOversoldConfig
from src.execution_engine.strategies.macd_divergence_config import MACDDivergenceConfig
from src.reporting.telegram_reporter import TelegramReporter
from src.config.trading_config import trading_config_manager
from src.execution_engine.trade_monitor import TradeMonitor
from src.execution_engine.anomaly_detector import AnomalyDetector
import schedule
import threading
from collections import deque
import logging


# WebLogHandler moved to src/utils/logger.py to prevent circular imports

class BotManager:
    """Main bot manager that orchestrates all components"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Validate configuration
        if not global_config.validate_config():
            raise ValueError("Invalid configuration. Check environment variables.")

        # Check live trading readiness
        if not global_config.is_live_trading_ready():
            raise ValueError("Configuration not ready for live trading.")

        # Initialize components
        self.binance_client = BinanceClientWrapper()

        # Test connection early to validate everything works
        self.logger.info("🔍 TESTING BINANCE CONNECTION...")

        try:
            connection_success = self.binance_client.test_connection()
            if not connection_success:
                self.logger.warning("⚠️ BINANCE CONNECTION FAILED - Continuing with limited functionality")
                self.logger.warning("💡 Bot will start but may have issues with live trading")
            else:
                self.logger.info("✅ BINANCE CONNECTION SUCCESSFUL")
        except Exception as conn_error:
            self.logger.error(f"❌ Connection test error: {conn_error}")
            self.logger.warning("🔄 Continuing bot startup despite connection issues...")

        # Validate API permissions
        self.logger.info("🔍 VALIDATING API PERMISSIONS...")
        try:
            permissions = self.binance_client.validate_api_permissions()

            if not permissions['market_data']:
                self.logger.warning("⚠️ Market data access limited - continuing anyway")

            if not permissions['account_access'] and not global_config.BINANCE_TESTNET:
                self.logger.warning("⚠️ Account access limited - continuing anyway")

            self.logger.info("✅ API VALIDATION COMPLETE")
        except Exception as e:
            self.logger.warning(f"⚠️ API VALIDATION ERROR: {e} - continuing anyway")

        self.price_fetcher = PriceFetcher(self.binance_client)
        self.balance_fetcher = BalanceFetcher(self.binance_client)
        self.signal_processor = SignalProcessor()

        # Import trade_logger
        from src.analytics.trade_logger import trade_logger

        # Initialize telegram reporter first
        self.telegram_reporter = TelegramReporter()

        # Initialize order manager with required parameters
        self.order_manager = OrderManager(self.binance_client, trade_logger, self.telegram_reporter)

        # Load ALL strategies from web dashboard configurations
        self.strategies = trading_config_manager.get_all_strategies()

        # Log loaded strategies
        strategy_names = list(self.strategies.keys())
        self.logger.info(f"🎯 LOADED STRATEGIES: {', '.join(strategy_names)}")

        for strategy_name, config in self.strategies.items():
            symbol = config.get('symbol', 'UNKNOWN')
            margin = config.get('margin', 0)
            leverage = config.get('leverage', 1)
            self.logger.info(f"   📊 {strategy_name}: {symbol} | ${margin} @ {leverage}x")

        # Strategy assessment timers
        self.strategy_last_assessment = {}

        # Signal cooldown tracking to prevent duplicate signals
        self.last_signal_time = {}
        self.signal_cooldown_minutes = 15  # 15 minute cooldown between same signals

        # Running state
        self.is_running = False
        self.startup_notified = False

        # Position logging throttle
        self.last_position_log_time = {}
        self.position_log_interval = 60  # Log active positions every 60 seconds until closed

        # Initialize anomaly detector for orphan/ghost detection
        self.anomaly_detector = AnomalyDetector(
            binance_client=self.binance_client,
            order_manager=self.order_manager,
            telegram_reporter=self.telegram_reporter
        )

        # Set anomaly detector reference in order manager
        self.order_manager.set_anomaly_detector(self.anomaly_detector)
        self.logger.info("🔍 Anomaly detector initialized and connected to order manager")

        # Register all loaded strategies with anomaly detector
        for strategy_name, strategy_config in self.strategies.items():
            symbol = strategy_config.get('symbol', 'UNKNOWN')
            if symbol != 'UNKNOWN':
                self.anomaly_detector.register_strategy(strategy_name, symbol)
                self.logger.info(f"🔍 Registered strategy {strategy_name} with symbol {symbol}")
            else:
                self.logger.warning(f"⚠️ Strategy {strategy_name} has no symbol configured")

        # Daily reporter
        from src.analytics.daily_reporter import DailyReporter
        self.daily_reporter = DailyReporter(self.telegram_reporter)

        # Track if startup notification was sent
        self.startup_notification_sent = False

                # FIXED: Initialize web log handler safely after all components are ready
        # Prevent initialization failures from blocking bot startup
        self.log_handler = None
        try:
            self._initialize_web_logging()
            self.logger.info("🌐 Web log handler initialized for dashboard integration")
        except Exception as e:
            self.logger.warning(f"⚠️ Web log handler initialization failed (non-critical): {e}")
            # Continue without web logging - bot can still function

    def _initialize_web_logging(self):
        """Initialize web logging handler safely after basic setup"""
        try:
            # Import WebLogHandler from utils.logger to prevent circular dependencies
            from src.utils.logger import WebLogHandler

            self.log_handler = WebLogHandler()
            self.log_handler.setFormatter(logging.Formatter('%(message)s'))  # Simplified format for web
            self.log_handler.setLevel(logging.DEBUG)  # Ensure DEBUG level messages are captured

            # Add to root logger to capture all logs
            root_logger = logging.getLogger()

            # Remove any existing web log handlers to prevent duplicates
            existing_handlers = [h for h in root_logger.handlers if isinstance(h, WebLogHandler)]
            for handler in existing_handlers:
                root_logger.removeHandler(handler)

            # Add the new handler
            root_logger.addHandler(self.log_handler)

            # Also add to bot manager's own logger
            self.logger.addHandler(self.log_handler)

            self.logger.debug("🔍 Web log handler successfully initialized")

        except Exception as e:
            self.logger.warning(f"⚠️ Could not initialize web log handler: {e}")
            # FIXED: Create a minimal fallback log handler to prevent API failures
            from src.utils.logger import WebLogHandler
            self.log_handler = WebLogHandler()  # Use imported class as fallback
            self.logger.warning("🔄 Using fallback log handler for web dashboard")

    async def start(self):
        """Start the trading bot"""
        self.is_running = True

        # Log startup source - simplified detection
        startup_source = "Web Interface"

        # Check if this is a web interface call by looking at the call stack
        import inspect
        frame = inspect.currentframe()
        try:
            while frame:
                filename = str(frame.f_code.co_filename)
                if 'web_dashboard' in filename:
                    startup_source = "Web Interface"
                    break
                elif 'main.py' in filename and 'web_dashboard' not in filename:
                    startup_source = "Console"
                    break
                frame = frame.f_back
        except:
            startup_source = "Console"
        finally:
            del frame

        self.logger.info(f"🌐 BOT STARTUP INITIATED FROM: {startup_source}")

        try:
            # Startup banner
            startup_type = "RESTARTED" if startup_source == "Web Interface" else "ACTIVATED"
            self.logger.info(f"🚀 TRADING BOT {startup_type}")

            mode = "FUTURES TESTNET" if global_config.BINANCE_TESTNET else "FUTURES MAINNET"
            self.logger.info(f"📊 MODE: {mode}")

            strategies = list(self.strategies.keys())
            self.logger.info(f"📈 ACTIVE STRATEGIES: {', '.join(strategies)}")

            # Get initial balance
            self.logger.info(f"🔍 FETCHING ACCOUNT BALANCE...")
            balance_info = self.balance_fetcher.get_usdt_balance() or 0
            self.logger.info(f"💰 ACCOUNT BALANCE: ${balance_info:,.1f} USDT")

            self.logger.info(f"⚡ MONITORING INTERVAL: {global_config.PRICE_UPDATE_INTERVAL}s")

            # Check for existing positions from previous runs FIRST
            self.logger.info(f"🔍 CHECKING FOR EXISTING POSITIONS...")
            await self._recover_active_positions()

            # Get pairs being watched
            pairs = [config['symbol'] for config in self.strategies.values()]

            # Send startup notification ONCE with correct open trades count
            self.logger.info(f"📱 SENDING TELEGRAM STARTUP NOTIFICATION ({startup_source})")

            try:
                success = self.telegram_reporter.report_bot_startup(
                    pairs=pairs,
                    strategies=strategies,
                    balance=balance_info,
                    open_trades=len(self.order_manager.active_positions)
                )
                if success:
                    self.logger.info("✅ TELEGRAM STARTUP NOTIFICATION SENT SUCCESSFULLY")
                    self.startup_notified = True
                else:
                    self.logger.warning("⚠️ TELEGRAM STARTUP NOTIFICATION FAILED OR BLOCKED")
            except Exception as e:
                self.logger.error(f"❌ FAILED TO SEND TELEGRAM STARTUP NOTIFICATION: {e}")

            self.is_running = True
            self.logger.info(f"🔍 BOT STATUS: is_running = {self.is_running}")

            # Start daily reporter scheduler
            self.daily_reporter.start_scheduler()

            # Clear any ghost anomalies for symbols where we have legitimate positions
            self._cleanup_misidentified_positions()

            # Initial anomaly check AFTER startup notification - SUPPRESS notifications for startup scan
            self.logger.info("🔍 PERFORMING INITIAL ANOMALY CHECK (SUPPRESSED)...")
            self.anomaly_detector.run_detection(suppress_notifications=True)

            # Log startup scan completion status
            self.logger.info(f"🔍 STARTUP SCAN STATUS: startup_protection_complete = {self.anomaly_detector.startup_complete}")

            await self._main_trading_loop()

        except Exception as e:
            error_msg = f"Startup Error: {str(e)}"
            self.logger.error(error_msg)
            self.telegram_reporter.report_error("Startup Error", str(e))

            # Send shutdown notification for startup failure
            self.telegram_reporter.report_bot_stopped(f"Failed to start: {str(e)}")
            raise

    async def stop(self, reason: str = "Manual shutdown"):
        """Stop the trading bot"""
        if not self.is_running:
            self.logger.info("Bot is already stopped")
            return

        self.logger.info(f"🛑 Stopping trading bot: {reason}")
        self.is_running = False

        try:
            # Stop daily reporter scheduler
            if hasattr(self, 'daily_reporter'):
                try:
                    import schedule
                    schedule.clear()  # Clear all scheduled jobs
                    self.logger.info("🔄 Stopped daily reporter scheduler")
                except Exception as e:
                    self.logger.warning(f"Could not stop daily reporter: {e}")

            # Close any open positions gracefully (if required)
            if hasattr(self, 'order_manager') and self.order_manager.active_positions:
                self.logger.info("🔄 Bot has active positions - they will continue running")

            # Send shutdown notification to Telegram (non-blocking)
            try:
                self.telegram_reporter.report_bot_stopped(reason)
                self.logger.info("📱 Telegram shutdown notification sent")
            except Exception as e:
                self.logger.warning(f"Could not send Telegram notification: {e}")

            # Close database connections safely
            if hasattr(self, 'anomaly_detector') and hasattr(self.anomaly_detector, 'db'):
                try:
                    if hasattr(self.anomaly_detector.db, 'close'):
                        self.anomaly_detector.db.close()
                    self.logger.info("🔄 Closed anomaly detector database")
                except Exception as e:
                    self.logger.warning(f"Could not close anomaly detector database: {e}")

            # DON'T remove web log handler - keep it for dashboard
            self.logger.info("🌐 Keeping web log handler active for dashboard")

            # Small delay to ensure cleanup completes
            await asyncio.sleep(0.5)  # Reduced delay

        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
        finally:
            self.logger.info("🔴 Bot manager shutdown complete - Web dashboard remains active")

    async def _main_trading_loop(self):
        """Main trading loop with enhanced error handling and restart prevention"""
        consecutive_errors = 0
        max_consecutive_errors = 5
        last_anomaly_check = datetime.now()
        anomaly_check_interval = 30  # Check anomalies every 30 seconds

        while self.is_running:
            try:
                # Display current PnL for all active positions (throttled)
                await self._display_active_positions_pnl_throttled()

                # Check each strategy
                for strategy_name, strategy_config in self.strategies.items():
                    if not strategy_config.get('enabled', True):
                        continue

                    await self._process_strategy(strategy_name, strategy_config)

                # Check exit conditions for open positions
                await self._check_exit_conditions()

                # Run anomaly detection continuously for automatic orphan/ghost trade management
                if hasattr(self, 'anomaly_detector') and self.anomaly_detector:
                    try:
                        self.anomaly_detector.run_detection(suppress_notifications=False)
                    except Exception as e:
                        self.logger.error(f"❌ Anomaly detection error: {e}")
                        # Continue running despite anomaly detection errors

                # Reset error counter on successful iteration
                consecutive_errors = 0

                # Sleep before next iteration
                await asyncio.sleep(global_config.PRICE_UPDATE_INTERVAL)

            except (ConnectionError, TimeoutError) as e:
                consecutive_errors += 1
                self.logger.error(f"❌ Network Error #{consecutive_errors}: {e}")

                if consecutive_errors >= max_consecutive_errors:
                    self.logger.error(f"🚫 Too many consecutive network errors ({consecutive_errors}). Stopping bot to prevent restart loop.")
                    self.telegram_reporter.report_error("Network Error - Bot Stopped", str(e))
                    await self.stop(f"Network error after {consecutive_errors} attempts: {str(e)}")
                    break
                else:
                    # Exponential backoff for network errors
                    wait_time = min(30, 2 ** consecutive_errors)
                    self.logger.warning(f"🔄 Waiting {wait_time}s before retry (attempt {consecutive_errors}/{max_consecutive_errors})")
                    await asyncio.sleep(wait_time)

            except (KeyError, AttributeError) as e:
                consecutive_errors += 1
                self.logger.error(f"❌ Configuration Error #{consecutive_errors}: {e}")

                if consecutive_errors >= max_consecutive_errors:
                    self.logger.error(f"🚫 Too many consecutive config errors. This usually indicates a serious issue.")
                    await self.stop(f"Configuration error after {consecutive_errors} attempts: {str(e)}")
                    break
                else:
                    self.telegram_reporter.report_error("Configuration Error", str(e))
                    await asyncio.sleep(min(60, 10 * consecutive_errors))  # Longer wait for config issues

            except (ValueError, TypeError) as e:
                consecutive_errors += 1
                self.logger.error(f"❌ Data Processing Error #{consecutive_errors}: {e}")

                if consecutive_errors >= max_consecutive_errors:
                    await self.stop(f"Data processing error after {consecutive_errors} attempts: {str(e)}")
                    break
                else:
                    self.telegram_reporter.report_error("Data Error", str(e))
                    await asyncio.sleep(5)

            except Exception as e:
                consecutive_errors += 1
                error_msg = f"Unexpected Error #{consecutive_errors}: {str(e)}"
                self.logger.error(error_msg)

                # Log memory usage for debugging
                try:
                    import psutil
                    process = psutil.Process()
                    memory_mb = process.memory_info().rss / 1024 / 1024
                    self.logger.warning(f"🔍 MEMORY USAGE: {memory_mb:.1f} MB")
                except ImportError:
                    pass

                # Check if it's a critical error that requires immediate shutdown
                error_str = str(e).lower()
                if any(keyword in error_str for keyword in ["api", "connection", "auth", "permission", "key"]):
                    self.logger.error(f"🚫 Critical error detected: {str(e)}")
                    await self.stop(f"Critical error: {str(e)}")
                    break

                if consecutive_errors >= max_consecutive_errors:
                    self.logger.error(f"🚫 Too many consecutive errors ({consecutive_errors}). Stopping bot to prevent instability.")
                    self.telegram_reporter.report_error("Multiple Errors - Bot Stopped", str(e))
                    await self.stop(f"Multiple errors after {consecutive_errors} attempts")
                    break
                else:
                    self.telegram_reporter.report_error("Unexpected Error", str(e))
                    await asyncio.sleep(min(30, 5 * consecutive_errors))  # Progressive backoff

    async def _display_active_positions_pnl_throttled(self):
        """Display current PnL for all active positions with throttling - FIXED DUPLICATE DISPLAY"""
        try:
            current_time = datetime.now()

            # Prevent duplicate calls within same second
            if hasattr(self, '_last_position_display_time'):
                if (current_time - self._last_position_display_time).total_seconds() < 1:
                    return
            self._last_position_display_time = current_time

            # Memory cleanup for position log times
            if hasattr(self, 'last_position_log_time'):
                # Clean up old entries to prevent memory leak
                cutoff_time = current_time - timedelta(hours=24)
                to_remove = []
                for strategy_name, log_time in self.last_position_log_time.items():
                    if log_time < cutoff_time:
                        to_remove.append(strategy_name)

                for strategy_name in to_remove:
                    del self.last_position_log_time[strategy_name]

            for strategy_name, position in self.order_manager.active_positions.items():
                # Check if we should log this position (throttle to once per minute)
                last_log_time = self.last_position_log_time.get(strategy_name)
                if last_log_time and (current_time - last_log_time).total_seconds() < self.position_log_interval:
                    continue  # Skip logging for this position

                strategy_config = self.strategies.get(strategy_name)
                if not strategy_config:
                    continue

                try:
                    symbol = strategy_config['symbol']

                    # Get current price with enhanced fetching and validation
                    current_price = None
                    try:
                        # Method 1: Direct Binance ticker call
                        if self.binance_client.is_futures:
                            ticker = self.binance_client.client.futures_symbol_ticker(symbol=symbol)
                        else:
                            ticker = self.binance_client.client.get_symbol_ticker(symbol=symbol)
                        
                        if ticker and 'price' in ticker:
                            price_candidate = float(ticker['price'])
                            # Validate price is reasonable for the symbol
                            if self._validate_price_for_symbol(symbol, price_candidate):
                                current_price = price_candidate
                                self.logger.debug(f"🔍 Got valid price for {symbol}: ${current_price}")

                        # Fallback: try price fetcher if first method failed
                        if not current_price:
                            price_candidate = self.price_fetcher.get_current_price(symbol)
                            if price_candidate and self._validate_price_for_symbol(symbol, price_candidate):
                                current_price = price_candidate
                                self.logger.debug(f"🔍 Fallback price for {symbol}: ${current_price}")

                        if not current_price or current_price <= 0:
                            self.logger.warning(f"🔍 Could not get valid price for {symbol}, skipping PnL display")
                            continue
                            
                    except Exception as price_error:
                        self.logger.warning(f"🔍 Price fetch error for {symbol}: {price_error}")
                        continue

                    # Use simple, reliable manual PnL calculation (matches web dashboard)
                    entry_price = position.entry_price
                    quantity = position.quantity
                    side = position.side

                    # Manual PnL calculation (same as web dashboard)
                    if side == 'BUY':  # Long position
                        pnl = (current_price - entry_price) * quantity
                    else:  # Short position (SELL)
                        pnl = (entry_price - current_price) * quantity

                    # Use actual margin used for this specific position, fallback to configured margin
                    margin_invested = getattr(position, 'actual_margin_used', None) or strategy_config.get('margin', 50.0)

                    # Calculate PnL percentage against actual margin invested
                    pnl_percent = (pnl / margin_invested) * 100 if margin_invested > 0 else 0

                    # Display the position with clean, single formatting and current RSI
                    if margin_invested > 0:
                        # Get configured values for display
                        configured_leverage = strategy_config.get('leverage', 5)

                        # Get current indicators based on strategy type
                        indicator_text = "N/A"
                        try:
                            # Get fresh market data for indicator calculation
                            timeframe = strategy_config.get('timeframe', '15m')
                            df = await self.price_fetcher.get_market_data(symbol, timeframe, 100)
                            if df is not None and not df.empty:
                                # Calculate indicators
                                df = self.price_fetcher.calculate_indicators(df)

                                # Display strategy-specific indicators
                                if 'rsi' in strategy_name.lower():
                                    # RSI Strategy - show current RSI
                                    if 'rsi' in df.columns:
                                        current_rsi = df['rsi'].iloc[-1]
                                        if not pd.isna(current_rsi):
                                            indicator_text = f"RSI: {current_rsi:.1f}"
                                elif 'macd' in strategy_name.lower():
                                    # MACD Strategy - show MACD line and signal
                                    if 'macd' in df.columns and 'macd_signal' in df.columns:
                                        macd_line = df['macd'].iloc[-1]
                                        macd_signal = df['macd_signal'].iloc[-1]
                                        if not pd.isna(macd_line) and not pd.isna(macd_signal):
                                            indicator_text = f"MACD: {macd_line:.2f}/{macd_signal:.2f}"
                                else:
                                    # Other strategies - try to show RSI as fallback
                                    if 'rsi' in df.columns:
                                        current_rsi = df['rsi'].iloc[-1]
                                        if not pd.isna(current_rsi):
                                            indicator_text = f"RSI: {current_rsi:.1f}"
                        except Exception as e:
                            self.logger.debug(f"Could not fetch indicators for {symbol}: {e}")

                        # Clean, single position display with strategy-specific indicators
                        position_display = f"""╔═══════════════════════════════════════════════════╗
║ 📊 ACTIVE POSITION                                ║
║ ⏰ {datetime.now().strftime('%H:%M:%S')}                                        ║
║                                                   ║
║ 📊 TRADE IN PROGRESS                             ║
║ 🎯 Strategy: {strategy_name.upper():<15}                    ║
║ 💱 Symbol: {position.symbol:<20}                      ║
║ 📊 Side: {position.side:<25}                           ║
║ 💵 Entry: ${position.entry_price:,.1f}                        ║
║ 📊 Current: ${current_price:,.1f}                         ║
║ 📈 Indicator: {indicator_text:<25}                      ║
║ ⚡ Config: ${margin_invested:.1f} USDT @ {configured_leverage}x           ║
║ 💰 PnL: ${pnl:.1f} USDT ({pnl_percent:+.1f}%)              ║
║                                                   ║
╚═══════════════════════════════════════════════════╝"""

                        self.logger.info(position_display)
                    else:
                        self.logger.error(f"❌ PnL DISPLAY ERROR | {strategy_name} | Invalid margin configuration for {symbol}")

                    # Update last log time
                    self.last_position_log_time[strategy_name] = current_time

                except Exception as e:
                    self.logger.error(f"❌ ERROR DISPLAYING POSITION PnL | {strategy_name} | {e}")
                    # Continue with other positions despite error
                    continue

        except Exception as main_error:
            self.logger.error(f"❌ CRITICAL ERROR in position display: {main_error}")
            return  # Exit gracefully instead of crashing

        # CRITICAL FIX: Also check for Binance positions that aren't in active_positions
        try:
            # This handles the case where positions exist but weren't recovered properly
            try:
                if self.binance_client.is_futures:
                    positions = self.binance_client.client.futures_position_information()
                    for position in positions:
                        symbol = position.get('symbol')
                        position_amt = float(position.get('positionAmt', 0))

                        if abs(position_amt) > 0.001:  # Position exists
                            # Check if this position is already tracked
                            position_tracked = False
                            for strategy_name, tracked_position in self.order_manager.active_positions.items():
                                if tracked_position.symbol == symbol:
                                    position_tracked = True
                                    break

                            if not position_tracked:
                                # Find which strategy should handle this symbol
                                managing_strategy = None
                                for strategy_name, strategy_config in self.strategies.items():
                                    if strategy_config.get('symbol') == symbol:
                                        managing_strategy = strategy_name
                                        break

                                if managing_strategy:
                                    # Get current price
                                    current_price = self._get_current_price(symbol)
                                    if current_price:
                                        entry_price = float(position.get('entryPrice', 0))
                                        side = 'BUY' if position_amt > 0 else 'SELL'
                                        quantity = abs(position_amt)

                                        # Calculate PnL
                                        if side == 'BUY':
                                            pnl = (current_price - entry_price) * quantity
                                        else:
                                            pnl = (entry_price - current_price) * quantity

                                        # Get strategy config
                                        strategy_config = self.strategies.get(managing_strategy, {})
                                        margin_invested = strategy_config.get('margin', 50.0)
                                        configured_leverage = strategy_config.get('leverage', 5)
                                        pnl_percent = (pnl / margin_invested) * 100 if margin_invested > 0 else 0

                                        # Check if we should log this position (throttle to once per minute)
                                        last_log_time = self.last_position_log_time.get(f"untracked_{managing_strategy}")
                                        if not last_log_time or (current_time - last_log_time).total_seconds() >= self.position_log_interval:
                                            untracked_display = f"""╔═══════════════════════════════════════════════════╗
║ ⚠️  UNTRACKED POSITION DETECTED                   ║
║ ⏰ {datetime.now().strftime('%H:%M:%S')}                                        ║
║                                                   ║
║ 📊 TRADE IN PROGRESS (NOT TRACKED)               ║
║ 🎯 Strategy: {managing_strategy.upper():<15}                  ║
║ 💱 Symbol: {symbol:<20}                            ║
║ 📊 Side: {side:<25}                               ║
║ 💵 Entry: ${entry_price:,.1f}                        ║
║ 📊 Current: ${current_price:,.1f}                         ║
║ ⚡ Config: ${margin_invested:.1f} USDT @ {configured_leverage}x           ║
║ 💰 PnL: ${pnl:.1f} USDT ({pnl_percent:+.1f}%)              ║
║ ⚠️  WARNING: Position exists but not tracked internally  ║
║ 📝 SOLUTION: Position recovery needed on next restart    ║
║                                                   ║
╚═══════════════════════════════════════════════════╝"""
                                            self.logger.warning(untracked_display)

                                            # Update last log time
                                            self.last_position_log_time[f"untracked_{managing_strategy}"] = current_time

            except Exception as e:
                self.logger.error(f"❌ ERROR CHECKING UNTRACKED POSITIONS | {e}")
                # Don't crash the bot for untracked position errors
        except Exception as e:
            self.logger.error(f"Error checking untracked positions: {e}")
            # Don't crash the bot for untracked position errors

    async def _recover_active_positions(self):
        """Recover active positions from database and Binance on startup"""
        try:
            self.logger.info("🔍 POSITION RECOVERY: Starting intelligent position recovery...")

            # Use the trade database's smart recovery system
            from src.execution_engine.trade_database import TradeDatabase
            trade_db = TradeDatabase()

            # Perform smart recovery which handles both database matching and Binance verification
            recovery_report = trade_db.recover_missing_positions()

            # Process recovery results
            recovered_count = len(recovery_report.get('recovered_trades', []))
            matched_count = len(recovery_report.get('matched_existing_trades', []))
            total_recovered = recovered_count + matched_count

            if total_recovered > 0:
                self.logger.info(f"🛡️ POSITION RECOVERY: Found {total_recovered} positions to recover")

                # Now load recovered positions into order manager
                all_recovered_items = recovery_report.get('recovered_trades', []) + recovery_report.get('matched_existing_trades', [])

                for recovery_item in all_recovered_items:
                    try:
                        # Extract trade_id from the recovery item (which is a dictionary)
                        if isinstance(recovery_item, dict):
                            trade_id = recovery_item.get('trade_id')
                        else:
                            trade_id = recovery_item  # Fallback for string format

                        if not trade_id:
                            self.logger.warning(f"⚠️ Skipping recovery item with no trade_id: {recovery_item}")
                            continue

                        # Get trade data from database
                        trade_data = trade_db.get_trade(trade_id)
                        if trade_data and trade_data.get('trade_status') == 'OPEN':
                            strategy_name = trade_data.get('strategy_name', 'RECOVERY')

                            # Create position object for order manager
                            from src.execution_engine.order_manager import Position
                            position = Position(
                                strategy_name=strategy_name,
                                symbol=trade_data['symbol'],
                                side=trade_data['side'],
                                entry_price=trade_data['entry_price'],
                                quantity=trade_data['quantity'],
                                stop_loss=trade_data.get('stop_loss'),
                                take_profit=trade_data.get('take_profit'),
                                actual_margin_used=trade_data.get('margin_used', 0)
                            )

                            # Add to active positions
                            self.order_manager.active_positions[strategy_name] = position
                            self.logger.info(f"✅ RECOVERED POSITION | {strategy_name} | {trade_data['symbol']} | {trade_data['side']} | Entry: ${trade_data['entry_price']}")

                    except Exception as e:
                        self.logger.error(f"❌ Error recovering position from {recovery_item}: {e}")
                        continue

                self.logger.info(f"🛡️ POSITION RECOVERY: Successfully loaded {len(self.order_manager.active_positions)} active positions")
            else:
                self.logger.info("🛡️ POSITION RECOVERY: No positions to recover - starting fresh")

        except Exception as e:
            self.logger.error(f"❌ POSITION RECOVERY ERROR: {e}")
            self.logger.info("🔄 Continuing startup without position recovery...")

    async def _process_strategy(self, strategy_name: str, strategy_config: Dict):
        """Process a single strategy with improved error handling"""
        try:
            # Check if it's time to assess this strategy
            if not self._should_assess_strategy(strategy_name, strategy_config):
                return

            # Update last assessment time
            self.strategy_last_assessment[strategy_name] = datetime.now()

            # Check if strategy has blocking anomaly
            if self.anomaly_detector.has_blocking_anomaly(strategy_name):
                anomaly_status = self.anomaly_detector.get_anomaly_status(strategy_name)
                self.logger.info(f"⚠️ STRATEGY BLOCKED | {strategy_name.upper()} | {strategy_config['symbol']} | Status: {anomaly_status}")
                return

            # Check if strategy already has an active position
            if strategy_name in self.order_manager.active_positions:
                return  # Position status already logged in throttled method

            # Check for conflicting positions on the same symbol
            symbol = strategy_config['symbol']
            existing_position = self.order_manager.get_position_on_symbol(symbol)
            if existing_position:
                self.logger.info(f"⚠️ SYMBOL CONFLICT | {strategy_name.upper()} | {symbol} | Already trading via {existing_position.strategy_name} | Skipping duplicate")
                return

            # CRITICAL: Also check if there's already a position on Binance for this symbol
            try:
                if self.binance_client.is_futures:
                    positions = self.binance_client.client.futures_position_information(symbol=symbol)
                    for position in positions:
                        position_amt = float(position.get('positionAmt', 0))
                        if abs(position_amt) > 0:
                            self.logger.warning(f"⚠️ BINANCE POSITION EXISTS | {strategy_name.upper()} | {symbol} | Position: {position_amt} | Skipping new trade to prevent duplicates")
                            return
            except Exception as e:
                self.logger.error(f"Error checking Binance positions for {symbol}: {e}")
                # Continue execution despite error

            # Check balance requirements
            if not self._check_balance_requirements(strategy_config):
                return

            # Log market assessment start
            margin = strategy_config.get('margin', 50.0)
            leverage = strategy_config.get('leverage', 5)
            self.logger.info(f"🔍 SCANNING {strategy_config['symbol']} | {strategy_name.upper()} | {strategy_config['timeframe']} | Margin: ${margin:.1f} | Leverage: {leverage}x")

            # Enhanced market data fetching with timeframe-specific optimization
            timeframe = strategy_config['timeframe']

            # Optimize data limit based on timeframe for better indicator accuracy
            if timeframe in ['1m', '3m', '5m']:
                data_limit = 300  # Short timeframes need more recent data
            elif timeframe in ['15m', '30m', '1h']:
                data_limit = 200  # Medium timeframes
            else:
                data_limit = 150  # Longer timeframes

            df = await self.price_fetcher.get_market_data(
                symbol=strategy_config['symbol'], 
                interval=timeframe, 
                limit=data_limit
            )
            if df is None or df.empty:
                self.logger.warning(f"No data for {strategy_config['symbol']}")
                return

            # Calculate indicators with error handling
            try:
                df = self.price_fetcher.calculate_indicators(df)
            except Exception as e:
                self.logger.error(f"Error calculating indicators for {strategy_config['symbol']}: {e}")
                return

            # Get current market info
            current_price = df['close'].iloc[-1]

            # Ensure strategy name is in config for signal processor
            strategy_config_with_name = strategy_config.copy()
            strategy_config_with_name['name'] = strategy_name

            # Evaluate entry conditions
            signal = self.signal_processor.evaluate_entry_conditions(df, strategy_config_with_name)

            if signal:
                # Check signal cooldown to prevent spam
                signal_key = f"{strategy_name}_{strategy_config['symbol']}_{signal.signal_type.value}"
                current_time = datetime.now()

                if signal_key in self.last_signal_time:
                    time_since_last_signal = (current_time - self.last_signal_time[signal_key]).total_seconds()
                    if time_since_last_signal < (self.signal_cooldown_minutes * 60):
                        remaining_cooldown = (self.signal_cooldown_minutes * 60) - time_since_last_signal
                        self.logger.info(f"🔄 SIGNAL COOLDOWN | {strategy_name.upper()} | {strategy_config['symbol']} | {signal.signal_type.value} | {remaining_cooldown:.0f}s remaining")
                        return

                # Record this signal time
                self.last_signal_time[signal_key] = current_time

                # Entry signal detection format
                entry_signal_message = f"""╔═══════════════════════════════════════════════════╗
║ 🚨 ENTRY SIGNAL DETECTED                         ║
║ ⏰ {datetime.now().strftime('%H:%M:%S')}                                        ║
║                                                   ║
║ 🎯 Strategy: {strategy_name.upper()}                        ║
║ 💱 Symbol: {strategy_config['symbol']}                              ║
║ 📊 Signal Type: {signal.signal_type.value}                         ║
║ 💵 Entry Price: ${signal.entry_price:,.1f}                          ║
║ 📝 Reason: {signal.reason}                         ║
║                                                   ║
╚═══════════════════════════════════════════════════╝"""
                self.logger.info(entry_signal_message)

                # Execute the signal with the config that includes the strategy name
                position = self.order_manager.execute_signal(signal, strategy_config_with_name)

                if position:
                    self.logger.info(f"✅ POSITION OPENED | {strategy_name.upper()} | {strategy_config['symbol']} | {position.side} | Entry: ${position.entry_price:,.1f} | Qty: {position.quantity:,.1f} | SL: ${position.stop_loss:,.1f} | TP: ${position.take_profit:,.1f}")

                    # Send ONLY position opened notification (no separate entry signal notification)
                    # Add a small delay to ensure position is fully stored before sending notification
                    import asyncio
                    await asyncio.sleep(0.1)

                    from dataclasses import asdict
                    position_dict = asdict(position)
                    # Add current leverage info to the position data
                    position_dict['leverage'] = strategy_config.get('leverage', 5)
                    self.telegram_reporter.report_position_opened(position_dict)
                else:
                    self.logger.warning(f"❌ POSITION FAILED | {strategy_name.upper()} | {strategy_config['symbol']} | Could not execute signal")
            else:
                # Get assessment interval for logging
                assessment_interval = strategy_config.get('assessment_interval', 300)

                # Get additional indicators for consolidated logging
                margin = strategy_config.get('margin', 50.0)
                leverage = strategy_config.get('leverage', 5)

                # Get current RSI for consolidated logging (with NaN check)
                current_rsi = None
                if 'rsi' in df.columns:
                    rsi_value = df['rsi'].iloc[-1]
                    if not pd.isna(rsi_value):
                        current_rsi = rsi_value
                    else:
                        # Force recalculation if RSI is NaN
                        try:
                            df = self.price_fetcher.calculate_indicators(df)
                            rsi_value = df['rsi'].iloc[-1]
                            if not pd.isna(rsi_value):
                                current_rsi = rsi_value
                        except Exception as e:
                            self.logger.debug(f"RSI recalculation failed for {strategy_config['symbol']}: {e}")

                # Strategy-specific consolidated market assessment - single message
                if 'macd' in strategy_name.lower():
                    # Get MACD values for display
                    macd_line = df['macd'].iloc[-1] if 'macd' in df.columns else 0.0
                    macd_signal = df['macd_signal'].iloc[-1] if 'macd_signal' in df.columns else 0.0
                    macd_histogram = df['macd_histogram'].iloc[-1] if 'macd_histogram' in df.columns else 0.0

                    # Consolidated MACD market assessment - single line for dashboard display
                    assessment_message = f"📈 SCANNING {strategy_config['symbol']} | {strategy_name.upper()} | {strategy_config['timeframe']} | ${margin:.1f}@{leverage}x | Price: ${current_price:,.1f} | MACD: {macd_line:.2f}/{macd_signal:.2f} | H: {macd_histogram:.2f} | Every {assessment_interval}s"
                    self.logger.info(assessment_message)

                elif 'rsi' in strategy_name.lower():
                    # Consolidated RSI market assessment - single line for dashboard display
                    rsi_text = f"{current_rsi:.1f}" if current_rsi is not None else "N/A"
                    assessment_message = f"📈 SCANNING {strategy_config['symbol']} | {strategy_name.upper()} | {strategy_config['timeframe']} | ${margin:.1f}@{leverage}x | Price: ${current_price:,.1f} | RSI: {rsi_text} | Every {assessment_interval}s"
                    self.logger.info(assessment_message)

                elif 'smart' in strategy_name.lower() and 'money' in strategy_name.lower():
                    # Consolidated Smart Money market assessment - single line for dashboard display
                    assessment_message = f"📈 SCANNING {strategy_config['symbol']} | {strategy_name.upper()} | {strategy_config['timeframe']} | ${margin:.1f}@{leverage}x | Price: ${current_price:,.1f} | Smart Money Analysis | Every {assessment_interval}s"
                    self.logger.info(assessment_message)

        except Exception as e:
            self.logger.error(f"Error processing strategy {strategy_name}: {e}")
            self.telegram_reporter.report_error("Strategy Processing Error", str(e), strategy_name)

    def _should_assess_strategy(self, strategy_name: str, strategy_config: Dict) -> bool:
        """Check if it's time to assess this strategy based on assessment interval"""
        try:
            assessment_interval = strategy_config.get('assessment_interval', 300)  # Default 5 minutes

            last_assessment = self.strategy_last_assessment.get(strategy_name)
            if not last_assessment:
                return True

            time_since_last = (datetime.now() - last_assessment).total_seconds()
            return time_since_last >= assessment_interval

        except Exception as e:
            self.logger.error(f"Error checking strategy assessment timing: {e}")
            return True  # Assess by default if error

    def _check_balance_requirements(self, strategy_config: Dict) -> bool:
        """Check if we have sufficient balance for the strategy"""
        try:
            margin_required = strategy_config.get('margin', 50.0)
            current_balance = self.balance_fetcher.get_usdt_balance() or 0

            if current_balance < margin_required:
                self.logger.warning(f"❌ INSUFFICIENT BALANCE | Need ${margin_required:.1f} | Have ${current_balance:.1f}")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Error checking balance requirements: {e}")
            return False  # Fail safe

    def _get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for a symbol with enhanced error handling"""
        try:
            current_price = None
            
            # Method 1: Use appropriate ticker call based on futures/spot mode
            if self.binance_client.is_futures:
                ticker = self.binance_client.client.futures_symbol_ticker(symbol=symbol)
            else:
                ticker = self.binance_client.client.get_symbol_ticker(symbol=symbol)
                
            if ticker and 'price' in ticker:
                price_candidate = float(ticker['price'])
                if self._validate_price_for_symbol(symbol, price_candidate):
                    current_price = price_candidate
                    self.logger.debug(f"🔍 Direct ticker price for {symbol}: ${current_price:,.2f}")

            # Method 2: Use price fetcher as fallback
            if not current_price:
                price_candidate = self.price_fetcher.get_current_price(symbol)
                if price_candidate and self._validate_price_for_symbol(symbol, price_candidate):
                    current_price = price_candidate
                    self.logger.debug(f"🔍 Price fetcher price for {symbol}: ${current_price:,.2f}")

            if not current_price:
                self.logger.warning(f"🔍 Could not get valid price for {symbol}")
                
            return current_price
            
        except Exception as e:
            self.logger.warning(f"Error getting current price for {symbol}: {e}")
            return None

    def _validate_price_for_symbol(self, symbol: str, price: float) -> bool:
        """Validate if a price is reasonable for a given symbol"""
        try:
            if price <= 0:
                return False

            # Symbol-specific price validation ranges
            symbol_upper = symbol.upper()

            if 'BTC' in symbol_upper:
                # Bitcoin should be between $10,000 and $200,000
                return 10000 <= price <= 200000
            elif 'ETH' in symbol_upper:
                # Ethereum should be between $100 and $20,000
                return 100 <= price <= 20000
            elif 'SOL' in symbol_upper:
                # Solana should be between $1 and $1,000
                return 1 <= price <= 1000
            elif 'BNB' in symbol_upper:
                # BNB should be between $10 and $2,000
                return 10 <= price <= 2000
            elif 'ADA' in symbol_upper:
                # Cardano should be between $0.01 and $10
                return 0.01 <= price <= 10
            elif 'DOT' in symbol_upper:
                # Polkadot should be between $1 and $100
                return 1 <= price <= 100
            else:
                # Generic validation for other symbols
                return 0.0001 <= price <= 100000

        except Exception as e:
            self.logger.warning(f"Price validation error for {symbol}: {e}")
            return False

    def _cleanup_misidentified_positions(self):
        """Clear any ghost anomalies for symbols where we have legitimate positions"""
        try:
            if not hasattr(self, 'anomaly_detector') or not self.anomaly_detector:
                return

            # Clear anomalies for symbols where we have legitimate positions
            for strategy_name, position in self.order_manager.active_positions.items():
                symbol = position.symbol
                self.anomaly_detector.clear_anomaly(strategy_name)
                self.logger.debug(f"🔍 Cleared any ghost anomalies for {strategy_name} ({symbol})")

        except Exception as e:
            self.logger.debug(f"Error cleaning up misidentified positions: {e}")

    async def _check_exit_conditions(self):
        """Check exit conditions for all active positions"""
        try:
            positions_to_close = []

            for strategy_name, position in self.order_manager.active_positions.items():
                try:
                    # Get current price
                    current_price = self._get_current_price(position.symbol)
                    if not current_price:
                        continue

                    # Check stop loss
                    if position.stop_loss and (
                        (position.side == 'BUY' and current_price <= position.stop_loss) or
                        (position.side == 'SELL' and current_price >= position.stop_loss)
                    ):
                        positions_to_close.append((strategy_name, 'STOP_LOSS'))
                        continue

                    # Check take profit
                    if position.take_profit and (
                        (position.side == 'BUY' and current_price >= position.take_profit) or
                        (position.side == 'SELL' and current_price <= position.take_profit)
                    ):
                        positions_to_close.append((strategy_name, 'TAKE_PROFIT'))
                        continue

                except Exception as e:
                    self.logger.error(f"Error checking exit conditions for {strategy_name}: {e}")
                    continue

            # Close positions that hit exit conditions
            for strategy_name, exit_reason in positions_to_close:
                try:
                    success = self.order_manager.close_position(strategy_name, exit_reason)
                    if success:
                        self.logger.info(f"✅ POSITION CLOSED | {strategy_name} | {exit_reason}")
                    else:
                        self.logger.warning(f"❌ FAILED TO CLOSE | {strategy_name} | {exit_reason}")
                except Exception as e:
                    self.logger.error(f"Error closing position {strategy_name}: {e}")

        except Exception as e:
            self.logger.error(f"Error in exit conditions check: {e}")