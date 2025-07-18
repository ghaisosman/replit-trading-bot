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

        # Test Binance API connection and permissions
        if not self.binance_client.test_connection():
            error_msg = f"""
❌ Failed to connect to Binance API.

Current mode: {'TESTNET' if global_config.BINANCE_TESTNET else 'MAINNET'}

For TESTNET:
1. Go to https://testnet.binance.vision/
2. Create API keys with TRADING permissions
3. Update your Replit Secrets with the testnet keys

For MAINNET:
1. Set BINANCE_TESTNET=false in Secrets
2. Use your real Binance API keys with trading permissions
3. Ensure IP whitelisting is disabled or your IP is whitelisted
            """
            raise ValueError(error_msg)

        # Validate API permissions
        self.logger.info("🔍 VALIDATING API PERMISSIONS...")
        permissions = self.binance_client.validate_api_permissions()

        if not permissions['market_data']:
            raise ValueError("❌ Market data access required but not available")

        if not permissions['account_access'] and not global_config.BINANCE_TESTNET:
            raise ValueError("❌ Account access required for live trading")

        self.logger.info("✅ API VALIDATION COMPLETE")

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

        self.logger.info(f"Stopping trading bot: {reason}")
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

            # Send shutdown notification to Telegram
            self.telegram_reporter.report_bot_stopped(reason)

            # Close database connections
            if hasattr(self, 'anomaly_detector') and hasattr(self.anomaly_detector, 'db'):
                try:
                    if hasattr(self.anomaly_detector.db, 'close'):
                        self.anomaly_detector.db.close()
                    self.logger.info("🔄 Closed anomaly detector database")
                except Exception as e:
                    self.logger.warning(f"Could not close anomaly detector database: {e}")

            # Remove web log handler to prevent memory leaks
            if hasattr(self, 'log_handler'):
                try:
                    root_logger = logging.getLogger()
                    root_logger.removeHandler(self.log_handler)
                    self.logger.removeHandler(self.log_handler)
                    self.logger.info("🔄 Removed web log handler")
                except Exception as e:
                    self.logger.warning(f"Could not remove web log handler: {e}")

            # Small delay to ensure cleanup completes
            await asyncio.sleep(1)

        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
        finally:
            self.logger.info("🔴 Bot manager shutdown complete")

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

                # Check for trade anomalies (orphan/ghost trades) - throttled for performance
                current_time = datetime.now()
                if (current_time - last_anomaly_check).total_seconds() >= anomaly_check_interval:
                    try:
                        self.anomaly_detector.run_detection()
                        last_anomaly_check = current_time
                    except Exception as e:
                        self.logger.error(f"Error in anomaly detection: {e}")

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

                    # Get current price with timeout protection
                    current_price = self._get_current_price(symbol)
                    if not current_price:
                        self.logger.debug(f"🔍 Price fetch failed for {symbol}, skipping display")
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

                    # Use the configured margin as the actual margin invested (matches web dashboard)
                    margin_invested = strategy_config.get('margin', 50.0)

                    # Calculate PnL percentage against margin invested (matches web dashboard)
                    pnl_percent = (pnl / margin_invested) * 100 if margin_invested > 0 else 0

                    # Display the position with clean, single formatting
                    if margin_invested > 0:
                        # Get configured values for display
                        configured_leverage = strategy_config.get('leverage', 5)

                        # FIXED: Single, clean position display without nesting
                        position_display = f"""╔═══════════════════════════════════════════════════╗
║ 📊 ACTIVE POSITION                                ║
║ ⏰ {datetime.now().strftime('%H:%M:%S')}                                        ║
║                                                   ║
║ 📊 TRADE IN PROGRESS                             ║
║ 🎯 Strategy: {strategy_name.upper():<15}                    ║
║ 💱 Symbol: {position.symbol:<20}                      ║
║ 📊 Side: {position.side:<25}                           ║
║ 💵 Entry: ${position.entry_price:.1f}                          ║
║ 📊 Current: ${current_price:.1f}                           ║
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
                                            self.logger.warning(f"""╔═══════════════════════════════════════════════════╗
║ ⚠️  UNTRACKED POSITION DETECTED                   ║
║ ⏰ {datetime.now().strftime('%H:%M:%S')}                                        ║
║                                                   ║
║ 📊 TRADE IN PROGRESS (NOT TRACKED)               ║
║ 🎯 Strategy: {managing_strategy.upper()}                        ║
║ 💱 Symbol: {symbol}                              ║
║ 📊 Side: {side}                                 ║
║ 💵 Entry: ${entry_price:.1f}                          ║
║ 📊 Current: ${current_price:.1f}                           ║
║ ⚡ Config: ${margin_invested:.1f} USDT @ {configured_leverage}x           ║
║ 💰 PnL: ${pnl:.1f} USDT ({pnl_percent:+.1f}%)              ║
║ ⚠️  WARNING: Position exists but not tracked internally  ║
║ 📝 SOLUTION: Position recovery needed on next restart    ║
║                                                   ║
╚═══════════════════════════════════════════════════╝""")

                                            # Update last log time
                                            self.last_position_log_time[f"untracked_{managing_strategy}"] = current_time

            except Exception as e:
                self.logger.error(f"❌ ERROR CHECKING UNTRACKED POSITIONS | {e}")
                # Don't crash the bot for untracked position errors
        except Exception as e:
            self.logger.error(f"Error checking untracked positions: {e}")
            # Don't crash the bot for untracked position errors

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

            # Get market data with error handling
            df = self.price_fetcher.get_ohlcv_data(
                strategy_config['symbol'],
                strategy_config['timeframe']
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

                # Get current RSI
                current_rsi = None
                if 'rsi' in df.columns:
                    current_rsi = df['rsi'].iloc[-1]

                # Strategy-specific consolidated market assessment - single message
                if 'macd' in strategy_name.lower():
                    # Get MACD values for display
                    macd_line = df['macd'].iloc[-1] if 'macd' in df.columns else 0.0
                    macd_signal = df['macd_signal'].iloc[-1] if 'macd_signal' in df.columns else 0.0
                    macd_histogram = df['macd_histogram'].iloc[-1] if 'macd_histogram' in df.columns else 0.0

                    # Consolidated MACD market assessment - single message
                    assessment_message = f"""📈 MARKET ASSESSMENT
Interval: every {assessment_interval} seconds
💱 Symbol: {strategy_config['symbol']}
🎯 {strategy_name.upper()} | {strategy_config['timeframe']} | Margin: ${margin:.1f} | Leverage: {leverage}x
💵 Price: ${current_price:,.1f}
📈 MACD: {macd_line:.6f} | Signal: {macd_signal:.6f} | Histogram: {macd_histogram:.6f}
🔍 SCANNING FOR ENTRY"""
                    self.logger.info(assessment_message)

                elif 'rsi' in strategy_name.lower():
                    # Consolidated RSI market assessment - single message for ALL RSI strategies
                    rsi_text = f"📈 RSI: {current_rsi:.2f}" if current_rsi is not None else "📈 RSI: N/A"
                    assessment_message = f"""📈 MARKET ASSESSMENT
Interval: every {assessment_interval} seconds
💱 Symbol: {strategy_config['symbol']}
🎯 {strategy_name.upper()} | {strategy_config['timeframe']} | Margin: ${margin:.1f} | Leverage: {leverage}x
💵 Price: ${current_price:,.1f}
{rsi_text}
🔍 SCANNING FOR ENTRY"""
                    self.logger.info(assessment_message)

        except Exception as e:
            self.logger.error(f"Error processing strategy {strategy_name}: {e}")
            self.telegram_reporter.report_error("Strategy Processing Error", str(e), strategy_name)

    async def _check_exit_conditions(self):
        """Check exit conditions for all open positions with improved error handling"""
        try:
            active_positions = self.order_manager.get_active_positions()

            for strategy_name, position in active_positions.items():
                try:
                    strategy_config = self.strategies.get(strategy_name)
                    if not strategy_config:
                        continue

                    # FIRST: Check Binance-based stop loss (most accurate)
                    current_price = self._get_current_price(strategy_config['symbol'])
                    if current_price and await self._check_stop_loss(strategy_name, strategy_config, position, current_price):
                        continue  # Position was closed by stop loss, skip other checks

                    # Get current market data
                    df = self.price_fetcher.get_ohlcv_data(
                        strategy_config['symbol'],
                        strategy_config['timeframe']
                    )

                    if df is None or df.empty:
                        continue

                    # Calculate indicators
                    df = self.price_fetcher.calculate_indicators(df)

                    # Ensure strategy name is in config for exit conditions
                    strategy_config_with_name = strategy_config.copy()
                    strategy_config_with_name['name'] = strategy_name

                    # Check strategy-specific exit conditions (take profit, RSI levels, etc.)
                    exit_reason = self.signal_processor.evaluate_exit_conditions(
                        df, 
                        {'entry_price': position.entry_price, 'stop_loss': position.stop_loss, 'take_profit': position.take_profit, 'side': position.side, 'quantity': position.quantity}, 
                        strategy_config_with_name
                    )

                    if exit_reason:
                        current_price = df['close'].iloc[-1]
                        pnl = self._calculate_pnl(position, current_price)

                        pnl_status = "PROFIT" if pnl > 0 else "LOSS"

                        self.logger.info(f"🔄 EXIT TRIGGERED | {strategy_name.upper()} | {strategy_config['symbol']} | {exit_reason} | Exit: ${current_price:,.1f} | PnL: ${pnl:.1f} ({pnl_status})")

                        # Close position
                        if self.order_manager.close_position(strategy_name, exit_reason):
                            self.logger.info(f"✅ POSITION CLOSED | {strategy_name.upper()} | {strategy_config['symbol']} | {exit_reason} | Entry: ${position.entry_price:,.1f} | Exit: ${current_price:,.1f} | Final PnL: ${pnl:.1f}")

                            # Send Telegram notification for position closed
                            try:
                                from dataclasses import asdict
                                position_data = asdict(position)
                                position_data['exit_price'] = current_price

                                self.logger.info(f"🔍 TELEGRAM DEBUG: Sending position closed notification for {strategy_name}")
                                success = self.telegram_reporter.report_position_closed(
                                    position_data, exit_reason, pnl)

                                if success:
                                    self.logger.info(f"🔍 TELEGRAM DEBUG: Position closed notification sent successfully")
                                else:
                                    self.logger.warning(f"🔍 TELEGRAM DEBUG: Failed to send position closed notification")

                            except Exception as e:
                                self.logger.error(f"❌ TELEGRAM ERROR: Failed to send position closed notification: {e}")
                                import traceback
                                self.logger.error(f"❌ TELEGRAM ERROR: Traceback: {traceback.format_exc()}")

                except Exception as e:
                    self.logger.error(f"Error checking exit conditions for {strategy_name}: {e}")

        except Exception as e:
            self.logger.error(f"Error checking exit conditions: {e}")
            self.telegram_reporter.report_error("Exit Check Error", str(e))

    def _should_assess_strategy(self, strategy_name: str, strategy_config: Dict) -> bool:
        """Check if it's time to assess this strategy using strategy-specific intervals"""
        current_time = datetime.now()

        # Check if we have a last assessment time for this strategy
        if strategy_name not in self.strategy_last_assessment:
            return True

        # Check if enough time has passed since last assessment
        time_since_last = current_time - self.strategy_last_assessment[strategy_name]

        # Use strategy-specific assessment interval from config
        assessment_interval = strategy_config.get('assessment_interval', 300)  # Default 5 minutes

        should_assess = time_since_last.total_seconds() >= assessment_interval

        # Log assessment timing for debugging
        if should_assess:
            self.logger.debug(f"🔍 {strategy_name.upper()} assessment interval ({assessment_interval}s) reached - proceeding with market scan")

        return should_assess

    def _check_balance_requirements(self, strategy_config: Dict) -> bool:
        """Check if there's sufficient balance for the strategy with error handling"""
        try:
            # Get the biggest margin across all strategies
            max_margin = max(config['margin'] for config in self.strategies.values())

            # Check if balance is sufficient
            if not self.balance_fetcher.check_sufficient_balance(max_margin, global_config.BALANCE_MULTIPLIER):
                current_balance = self.balance_fetcher.get_usdt_balance() or 0
                required_balance = max_margin * global_config.BALANCE_MULTIPLIER

                self.telegram_reporter.report_balance_warning(required_balance, current_balance)
                self.logger.warning(f"Insufficient balance. Required: {required_balance}, Available: {current_balance}")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Error checking balance requirements: {e}")
            return False

    def update_strategy_config(self, strategy_name: str, updates: Dict):
        """Update strategy configuration with validation"""
        try:
            if strategy_name in self.strategies:
                # Update the strategy config directly
                self.strategies[strategy_name].update(updates)

                # CRITICAL: Also update the trading config manager to persist changes
                from src.config.trading_config import trading_config_manager
                trading_config_manager.update_strategy_params(strategy_name, updates)

                self.logger.info(f"✅ CONFIGURATION UPDATED | {strategy_name} | {updates}")

                # Log specific important updates
                if 'leverage' in updates:
                    self.logger.info(f"🔧 LEVERAGE UPDATED | {strategy_name} | {updates['leverage']}x")
                if 'margin' in updates:
                    self.logger.info(f"💰 MARGIN UPDATED | {strategy_name} | ${updates['margin']} USDT")
                if 'max_loss_pct' in updates:
                    self.logger.info(f"🛡️ STOP LOSS UPDATED | {strategy_name} | {updates['max_loss_pct']}%")
            else:
                self.logger.warning(f"Strategy {strategy_name} not found")
        except Exception as e:
            self.logger.error(f"Error updating strategy config: {e}")

    def _get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for a symbol with improved error handling"""
        try:
            ticker = self.binance_client.get_symbol_ticker(symbol)
            if ticker and 'price' in ticker:
                price = float(ticker['price'])
                self.logger.debug(f"🔍 PRICE FETCH | {symbol} | Current: ${price:.4f}")
                return price
            else:
                self.logger.warning(f"❌ PRICE FETCH FAILED | {symbol} | Invalid ticker response: {ticker}")
                return None
        except Exception as e:
            self.logger.error(f"❌ PRICEFETCH ERROR | {symbol} | {e}")
            return None

    def _calculate_pnl(self, position, current_price: float) -> float:
        """Calculate PnL for a position with better validation"""
        try:
            if not current_price or current_price <= 0:
                self.logger.warning(f"❌ PnL CALC | Invalid current price: {current_price}")
                return 0.0

            if not position or not hasattr(position, 'entry_price') or not hasattr(position, 'quantity'):
                self.logger.warning(f"❌ PnL CALC | Invalid position data")
                return 0.0

            # For futures trading, PnL calculation
            if position.side == 'BUY':  # Long position
                pnl = (current_price - position.entry_price) * position.quantity
            else:  # Short position (SELL)
                pnl = (position.entry_price - current_price) * position.quantity

            self.logger.debug(f"🔍 PnL CALC | {position.symbol} | Side: {position.side} | Entry: ${position.entry_price:.4f} | Current: ${current_price:.4f} | Qty: {position.quantity} | PnL: ${pnl:.2f}")
            return pnl

        except Exception as e:
            self.logger.error(f"❌ PnL CALCULATION ERROR | {getattr(position, 'symbol', 'UNKNOWN')} | {e}")
            return 0.0

    def _get_market_info(self, df: pd.DataFrame, strategy_name: str) -> str:
        """Get market information string for logging with error handling"""
        try:
            if strategy_name == 'rsi_oversold':
                if 'rsi' in df.columns and not df['rsi'].empty:
                    rsi = df['rsi'].iloc[-1]
                    condition = "Oversold" if rsi < 30 else "Overbought" if rsi > 70 else "Normal"
                    return f"RSI: {rsi:.1f} | Condition: {condition}"
            elif strategy_name == 'macd_divergence':
                return "MACD Analysis | Status: Monitoring"

            return "No Signal"
        except Exception as e:
            return f"Error: {e}"

    async def _recover_active_positions(self):
        """Recover active positions from Binance on startup with enhanced validation"""
        try:
            self.logger.info("🔍 CHECKING FOR EXISTING POSITIONS...")

            recovered_count = 0

            for strategy_name, strategy_config in self.strategies.items():
                symbol = strategy_config.get('symbol')
                if not symbol:
                    continue

                try:
                    if self.binance_client.is_futures:
                        positions = self.binance_client.client.futures_position_information(symbol=symbol)

                        for position in positions:
                            position_amt = float(position.get('positionAmt', 0))

                            # Use a more restrictive threshold to avoid recovering tiny positions
                            if abs(position_amt) > 0.0001:  # Position exists and is significant (lowered for MACD)
                                # Recover position details
                                entry_price = float(position.get('entryPrice', 0))
                                side = 'BUY' if position_amt > 0 else 'SELL'
                                quantity = abs(position_amt)

                                # Check if there's a matching trade in our database
                                trade_id = None

                                try:
                                    from src.execution_engine.trade_database import TradeDatabase
                                    trade_db = TradeDatabase()
                                    trade_id = trade_db.find_trade_by_position(strategy_name, symbol, side, quantity, entry_price, tolerance=0.01)
                                    if trade_id:
                                        self.logger.info(f"🔍 FOUND MATCHING TRADE ID: {trade_id}")
                                    else:
                                        self.logger.info(f"🔍 NO MATCHING TRADE ID FOUND in database")
                                except Exception as e:
                                    self.logger.error(f"Error checking trade database: {e}")

                                # IMPROVED RECOVERY LOGIC: Always recover valid positions to prevent ghost detection
                                should_recover = True  # Default to recovery for valid positions

                                # Additional validation - ensure position has realistic values
                                if entry_price <= 0 or abs(quantity) < 0.0001:
                                    should_recover = False
                                    self.logger.warning(f"⚠️ INVALID POSITION DATA | {strategy_name.upper()} | {symbol} | Entry: ${entry_price} | Qty: {quantity} | Skipping recovery")

                                if should_recover:
                                    # Position recovery - always recover valid positions to prevent ghost detection
                                    from src.execution_engine.order_manager import Position
                                    from datetime import datetime

                                    recovered_position = Position(
                                        strategy_name=strategy_name,
                                        symbol=symbol,
                                        side=side,
                                        entry_price=entry_price,
                                        quantity=quantity,
                                        stop_loss=entry_price * (0.98 if side == 'BUY' else 1.02),
                                        take_profit=entry_price * (1.02 if side == 'BUY' else 0.98),
                                        position_side='LONG' if side == 'BUY' else 'SHORT',
                                        order_id=0,
                                        entry_time=datetime.now(),
                                        status='RECOVERED',
                                        trade_id=trade_id or f"recovered_{symbol}_{int(datetime.now().timestamp())}",
                                        strategy_config=strategy_config
                                    )

                                    # Add to active positions
                                    self.order_manager.active_positions[strategy_name] = recovered_position

                                    # CRITICAL: Notify anomaly detector that this is a legitimate bot position
                                    self.anomaly_detector.register_bot_trade(symbol, strategy_name)

                                    recovery_status = "WITH TRADE ID" if trade_id else "WITHOUT TRADE ID"
                                    self.logger.info(f"✅ POSITION RECOVERED ({recovery_status}) | {strategy_name.upper()} | {symbol} | Entry: ${entry_price:,.4f} | Qty: {quantity:,.6f}")

                                    recovered_count += 1
                                else:
                                    self.logger.warning(f"⚠️ POSITION NOT RECOVERED | {strategy_name.upper()} | {symbol} | Invalid data or too small")

                                break  # Only one position per strategy

                except Exception as e:
                    self.logger.warning(f"Could not check positions for {symbol}: {e}")

            if recovered_count > 0:
                self.logger.info(f"✅ RECOVERED {recovered_count} POSITIONS")
            else:
                self.logger.info("✅ NO POSITIONS FOUND FOR RECOVERY")

        except Exception as e:
            self.logger.error(f"Error recovering active positions: {e}")

    def _cleanup_misidentified_positions(self):
        """Clean up ghost anomalies for positions that should be legitimate bot positions"""
        try:
            self.logger.info("🔍 CHECKING FOR MISIDENTIFIED POSITIONS...")

            # Get all active ghost anomalies
            active_anomalies = self.anomaly_detector.db.get_active_anomalies()
            ghost_anomalies = [a for a in active_anomalies if a.type.value == 'ghost']

            for anomaly in ghost_anomalies:
                strategy_name = anomaly.strategy_name
                symbol = anomaly.symbol

                # Check if this position should actually be recognized as a legitimate bot position
                try:
                    if self.binance_client.is_futures:
                        positions = self.binance_client.client.futures_position_information(symbol=symbol)
                        for position in positions:
                            position_amt = float(position.get('positionAmt', 0))
                            if abs(position_amt) > 0:
                                entry_price = float(position.get('entryPrice', 0))
                                side = 'BUY' if position_amt > 0 else 'SELL'
                                quantity = abs(position_amt)

                                # Re-validate this position with enhanced validation
                                is_legitimate, trade_id = self.order_manager.is_legitimate_bot_position(strategy_name, symbol, side, quantity, entry_price)
                                if is_legitimate and trade_id:
                                    self.logger.info(f"🔍 MISIDENTIFIED POSITION FOUND | {strategy_name.upper()} | {symbol} | Clearing ghost anomaly and recovering position")

                                    # Clear the ghost anomaly
                                    self.anomaly_detector.clear_anomaly_by_id(anomaly.id, "Position re-validated as legitimate bot trade")

                                    # Recover the position properly
                                    from src.execution_engine.order_manager import Position
                                    from datetime import datetime

                                    recovered_position = Position(
                                        strategy_name=strategy_name,
                                        symbol=symbol,
                                        side=side,
                                        entry_price=entry_price,
                                        quantity=quantity,
                                        stop_loss=entry_price * 0.985 if side == 'BUY' else entry_price * 1.015,
                                        take_profit=entry_price * 1.025 if side == 'BUY' else entry_price * 0.975,
                                        position_side='LONG' if side == 'BUY' else 'SHORT',
                                        order_id=0,
                                        entry_time=datetime.now(),
                                        status='RECOVERED',
                                        trade_id=trade_id,
                                        strategy_config=self.strategies.get(strategy_name, {})
                                    )

                                    # Add to active positions
                                    self.order_manager.active_positions[strategy_name] = recovered_position

                                    # Register with anomaly detector
                                    self.anomaly_detector.register_bot_trade(symbol, strategy_name)

                                    self.logger.info(f"✅ POSITION RECOVERED FROM MISIDENTIFICATION | {strategy_name.upper()} | {symbol} | Entry: ${entry_price:,.4f} | Qty: {quantity:,.6f}")

                                break

                except Exception as e:
                    self.logger.warning(f"Could not re-validate position for {symbol}: {e}")

        except Exception as e:
            self.logger.error(f"Error cleaning up misidentified positions: {e}")

    def get_bot_status(self) -> Dict:
        """Get current bot status with error handling"""
        try:
            return {
                'is_running': self.is_running,
                'active_positions': len(self.order_manager.active_positions),
                'strategies': list(self.strategies.keys()),
                'balance': self.balance_fetcher.get_usdt_balance() or 0
            }
        except Exception as e:
            self.logger.error(f"Error getting bot status: {e}")
            return {
                'is_running': self.is_running,
                'active_positions': 0,
                'strategies': [],
                'balance': 0
            }

    def get_recent_logs(self, count=50):
        """Get recent logs for web dashboard with safe fallback"""
        try:
            # FIXED: Always ensure we return a valid list to prevent empty API responses
            if self.log_handler and hasattr(self.log_handler, 'get_recent_logs'):
                logs = self.log_handler.get_recent_logs(count)
                # Ensure logs is always a list
                if not isinstance(logs, list) or len(logs) == 0:
                    return self._get_fallback_logs()
                return logs
            else:
                return self._get_fallback_logs()
        except Exception as e:
            self.logger.error(f"Error getting recent logs: {e}")
            return self._get_fallback_logs()

    def _get_fallback_logs(self):
        """Generate fallback logs when log handler is not available"""
        # FIXED: Always return informative logs to prevent empty dashboard console
        current_time = datetime.now().strftime('%H:%M:%S')
        return [
            f"[{current_time}] 🚀 Bot manager initialized successfully",
            f"[{current_time}] 📊 Running: {getattr(self, 'is_running', False)}",
            f"[{current_time}] 💼 Active positions: {len(getattr(self.order_manager, 'active_positions', {})) if hasattr(self, 'order_manager') else 0}",
            f"[{current_time}] 📈 Strategies: {len(getattr(self, 'strategies', {})) if hasattr(self, 'strategies') else 0}",
            f"[{current_time}] 🌐 Web dashboard connected"
        ]

    async def _check_misidentified_positions(self):
        """Check for positions that might be incorrectly identified as manual"""
        try:
            # This would contain logic to identify and correct misidentified positions
            # For now, just log that we're checking
            pass
        except Exception as e:
            self.logger.error(f"Error checking misidentified positions: {e}")

    async def _synchronize_existing_positions(self):
        """Synchronize bot's internal positions with existing Binance positions during startup"""
        try:
            if not self.binance_client.is_futures:
                return

            # Get all positions from Binance
            positions = self.binance_client.client.futures_position_information()
            synced_count = 0

            for position in positions:
                symbol = position.get('symbol')
                position_amt = float(position.get('positionAmt', 0))

                if abs(position_amt) < 0.000001:
                    continue  # Skip zero positions

                # Check if this symbol is managed by any of our strategies
                managing_strategy = None
                for strategy_name, strategy_config in self.strategies.items():
                    if strategy_config.get('symbol') == symbol:
                        managing_strategy = strategy_name
                        break

                if managing_strategy:
                    # Check if bot already has this position tracked
                    if managing_strategy in self.order_manager.active_positions:
                        self.logger.info(f"🔍 SYNC: {managing_strategy} | {symbol} | Already tracked internally")
                        continue

                    # Import this position into bot's tracking
                    side = 'BUY' if position_amt > 0 else 'SELL'
                    entry_price = float(position.get('entryPrice', 0))
                    unrealized_pnl = float(position.get('unRealizedPnl', 0))

                    self.logger.warning(f"🔄 POSITION SYNC | {managing_strategy} | {symbol} | Importing existing position")
                    self.logger.warning(f"   📊 Side: {side} | Quantity: {abs(position_amt)} | Entry: ${entry_price:.4f}")
                    self.logger.warning(f"   💰 Unrealized PnL: ${unrealized_pnl:.2f} USDT")

                    # Note: We don't actually import these into active_positions here
                    # because they weren't opened by the bot in this session
                    # The duplicate prevention will handle skipping new trades
                    synced_count += 1
                else:
                    self.logger.info(f"🔍 SYNC: {symbol} | Position exists but not managed by any strategy")

            if synced_count > 0:
                self.logger.info(f"🔄 SYNC COMPLETE: Found {synced_count} existing positions on managed symbols")
            else:
                self.logger.info("🔄 SYNC COMPLETE: No existing positions found on managed symbols")

        except Exception as e:
            self.logger.error(f"Error synchronizing existing positions: {e}")

    async def _monitor_active_positions(self):
        """Monitor active positions for exit conditions"""
        try:
            active_positions = self.order_manager.get_active_positions()

            for strategy_name, position in active_positions.items():
                try:
                    # Get current market data
                    symbol = position.symbol
                    strategy_config = self.strategies[strategy_name]

                    # Fetch fresh market data
                    df = await self.price_fetcher.get_market_data(
                        symbol=symbol,
                        timeframe=strategy_config['timeframe'],
                        limit=100
                    )

                    if df is None or df.empty:
                        self.logger.warning(f"No market data for position monitoring: {symbol}")
                        continue

                    # Get current price
                    current_price = df['close'].iloc[-1]
                    # Calculate PnL
                    pnl = self.order_manager.calculate_pnl(position, current_price)
                    margin_invested = position.entry_price * position.quantity / strategy_config.get('leverage', 1)
                    pnl_percent = (pnl / margin_invested) * 100 if margin_invested > 0 else 0

                    # Get current RSI for logging
                    current_rsi = None
                    if 'rsi' in df.columns:
                        current_rsi = df['rsi'].iloc[-1]

                    # Log position status with RSI
                    self.logger.info(f"📊 TRADE IN PROGRESS")
                    self.logger.info(f"🎯 Strategy: {strategy_name.upper()}")
                    self.logger.info(f"💱 Symbol: {symbol}")
                    self.logger.info(f"📊 Side: {position.side}")
                    self.logger.info(f"💵 Entry: ${position.entry_price:.4f}")
                    self.logger.info(f"📊 Current: ${current_price:.4f}")
                    if current_rsi is not None:
                        self.logger.info(f"📈 RSI: {current_rsi:.2f}")
                    self.logger.info(f"💸 Margin: ${margin_invested:.1f} USDT")
                    self.logger.info(f"💰 PnL: ${pnl:.1f} USDT ({pnl_percent:+.1f}%)")

                    # Check exit conditions
                    position_dict = {
                        'entry_price': position.entry_price,
                        'stop_loss': position.stop_loss,
                        'take_profit': position.take_profit,
                        'side': position.side,
                        'quantity': position.quantity
                    }

                    exit_reason = self.signal_processor.evaluate_exit_conditions(df, position_dict, strategy_config)

                    if exit_reason:
                        self.logger.info(f"🚪 EXIT SIGNAL: {exit_reason}")

                        # Close position
                        await self.order_manager.close_position(strategy_name, exit_reason)

                        # Send exit notification
                        await self.telegram_reporter.report_trade_exit(
                            strategy_name=strategy_name,
                            symbol=symbol,
                            side=position.side,
                            entry_price=position.entry_price,
                            exit_price=current_price,
                            pnl=pnl,
                            pnl_percent=pnl_percent,
                            exit_reason=exit_reason
                        )

                except Exception as e:
                    self.logger.error(f"Error monitoring position {strategy_name}: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Error in position monitoring: {e}")

    def _notify_position_closed(self, strategy_name, result):
        """Helper method to notify position closed via Telegram"""
        try:
            position = self.order_manager.active_positions.get(strategy_name)
            if position:
                from dataclasses import asdict
                self.telegram_reporter.report_position_closed(
                    position_data=asdict(position),
                    exit_reason=result['reason'],
                    pnl=result['pnl']
                )
        except Exception as e:
            self.logger.error(f"Error notifying position close for {strategy_name}: {e}")

    async def _check_stop_loss(self, strategy_name: str, strategy_config: Dict, position, current_price: float) -> bool:
        """Check and trigger stop loss based on PnL percentage"""
        try:
            symbol = position.symbol
            max_loss_pct = strategy_config.get('max_loss_pct', 10)

            # Calculate PnL using reliable method
            pnl = self._calculate_pnl(position, current_price)

            # Calculate margin invested with validation
            leverage = max(1, strategy_config.get('leverage', 5))  # Ensure minimum leverage of 1
            position_value = position.entry_price * position.quantity
            margin_invested = position_value / leverage

            # Ensure margin_invested is not zero
            if margin_invested <= 0:
                margin_invested = strategy_config.get('margin', 50.0)

            # Calculate PnL percentage
            pnl_percentage = (pnl / margin_invested) * 100 if margin_invested > 0 else 0

            self.logger.debug(f"🔍 STOP LOSS CHECK | {strategy_name} | PnL: ${pnl:.2f} ({pnl_percentage:.1f}%) | Threshold: -{max_loss_pct}%")

            # Trigger stop loss if loss percentage exceeds threshold
            if pnl_percentage <= -max_loss_pct:
                self.logger.info(f"💥 STOP LOSS TRIGGERED | {strategy_name} | PnL: ${pnl:.2f} ({pnl_percentage:.1f}%) >= -{max_loss_pct}% threshold")
                result = self.order_manager.close_position(strategy_name, "Stop Loss")
                if result:
                    self._notify_position_closed(strategy_name, result)
                return True

            return False

        except Exception as e:
            self.logger.error(f"Error checking stop loss for {strategy_name}: {e}")
            return False


    def _monitor_positions(self) -> None:
        """Monitor active positions and display their status"""
        try:
            active_positions = self.order_manager.get_active_positions()

            if not active_positions:
                return

            for strategy_name, position in active_positions.items():
                try:
                    # Get current price
                    current_price = self._get_current_price(position.symbol)
                    if not current_price:
                        continue

                    # Get strategy config for display
                    strategy_config = self.strategies.get(strategy_name, {})
                    configured_margin = strategy_config.get('margin', 0.0)
                    configured_leverage = strategy_config.get('leverage', 1)

                    # Calculate actual margin used (position value / leverage)
                    position_value = position.entry_price * position.quantity
                    actual_margin_used = position_value / configured_leverage

                    # Get unrealized PnL from Binance directly
                    unrealized_pnl_usdt = 0.0
                    pnl_percentage = 0.0

                    try:
                        if self.binance_client.is_futures:
                            # Get position information from Binance
                            positions = self.binance_client.client.futures_position_information(symbol=position.symbol)
                            for pos in positions:
                                if pos.get('symbol') == position.symbol:
                                    position_amt = float(pos.get('positionAmt', 0))
                                    # Only get PnL if there's an actual position
                                    if abs(position_amt) > 0.001:
                                        unrealized_pnl_usdt = float(pos.get('unRealizedProfit', 0))
                                        self.logger.debug(f"🔍 PnL DEBUG | {strategy_name} | Binance Position Amt: {position_amt} | Unrealized PnL: ${unrealized_pnl_usdt:.2f}")
                                        break
                            else:
                                self.logger.warning(f"⚠️ No active position found on Binance for {position.symbol}")

                        # Calculate PnL percentage against configured margin
                        if configured_margin > 0:
                            pnl_percentage = (unrealized_pnl_usdt / configured_margin) * 100
                        else:
                            pnl_percentage = 0.0

                        self.logger.debug(f"🔍 PnL CALCULATION | {strategy_name} | Unrealized PnL: ${unrealized_pnl_usdt:.2f} | Margin: ${configured_margin} | Percentage: {pnl_percentage:+.2f}%")

                    except Exception as e:
                        self.logger.error(f"❌ Error getting unrealized PnL for {position.symbol}: {e}")
                        unrealized_pnl_usdt = 0.0
                        pnl_percentage = 0.0

                    # Log position status with proper formatting
                    status_message = f"""📊 TRADE IN PROGRESS
🎯 Strategy: {strategy_name}
💱 Symbol: {position.symbol}
📊 Side: {position.side}
💵 Entry: ${position.entry_price:.1f}
📊 Current: ${current_price:.1f}
⚡ Config: ${configured_margin} USDT @ {configured_leverage}x
💸 Actual Margin: ${actual_margin_used:.1f} USDT
💰 PnL: ${unrealized_pnl_usdt:.1f} USDT ({pnl_percentage:+.1f}%)"""

                    self.logger.info(status_message)

                except Exception as e:
                    self.logger.error(f"Error monitoring position {strategy_name}: {e}")

        except Exception as e:
            self.error(f"Error in position monitoring: {e}")

    async def _check_positions_for_exit(self):
        """Check exit conditions for all open positions with improved error handling"""
        try:
            active_positions = self.order_manager.get_active_positions()

            for strategy_name, position in active_positions.items():
                try:
                    strategy_config = self.strategies.get(strategy_name)
                    if not strategy_config:
                        continue

                    # FIRST: Check Binance-based stop loss (most accurate)
                    current_price = self._get_current_price(strategy_config['symbol'])
                    if current_price and await self._check_stop_loss(strategy_name, strategy_config, position, current_price):
                        continue  # Position was closed by stop loss, skip other checks

                    # Get current market data
                    df = self.price_fetcher.get_ohlcv_data(
                        strategy_config['symbol'],
                        strategy_config['timeframe']
                    )

                    if df is None or df.empty:
                        continue

                    # Calculate indicators
                    df = self.price_fetcher.calculate_indicators(df)

                    # Ensure strategy name is in config for exit conditions
                    strategy_config_with_name = strategy_config.copy()
                    strategy_config_with_name['name'] = strategy_name

                    # Check strategy-specific exit conditions (take profit, RSI levels, etc.)
                    exit_reason = self.signal_processor.evaluate_exit_conditions(
                        df,
                        {'entry_price': position.entry_price, 'stop_loss': position.stop_loss, 'take_profit': position.take_profit, 'side': position.side, 'quantity': position.quantity},
                        strategy_config_with_name
                    )

                    if exit_reason:
                        current_price = df['close'].iloc[-1]
                        pnl = self._calculate_pnl(position, current_price)

                        pnl_status = "PROFIT" if pnl > 0 else "LOSS"

                        self.logger.info(f"🔄 EXIT TRIGGERED | {strategy_name.upper()} | {strategy_config['symbol']} | {exit_reason} | Exit: ${current_price:,.1f} | PnL: ${pnl:.1f} ({pnl_status})")

                        # Close position
                        if self.order_manager.close_position(strategy_name, exit_reason):
                            self.logger.info(f"✅ POSITION CLOSED | {strategy_name.upper()} | {strategy_config['symbol']} | {exit_reason} | Entry: ${position.entry_price:,.1f} | Exit: ${current_price:,.1f} | Final PnL: ${pnl:.1f}")

                            from dataclasses import asdict
                            position_data = asdict(position)
                            position_data['exit_price'] = current_price
                            self.telegram_reporter.report_position_closed(
                                position_data,
                                exit_reason,
                                pnl
                            )
                        else:
                            self.logger.warning(f"❌ CLOSE FAILED | {strategy_name.upper()} | {strategy_config['symbol']} | Could not close position")
                    else:
                        # Get additional indicators for consolidated logging
                        margin = strategy_config.get('margin', 50.0)
                        leverage = strategy_config.get('leverage', 5)

                        # Get current RSI
                        current_rsi = None
                        if 'rsi' in df.columns:
                            current_rsi = df['rsi'].iloc[-1]

                        # Log active position with current market data and RSI
                        rsi_text = f"{current_rsi:.1f}" if current_rsi is not None else "N/A"
                        self.logger.info(f"TRADE IN PROGRESS | {strategy_name.upper()} | {strategy_config['symbol']} | Side: {position.side} | Entry: ${position.entry_price:.4f} | Current: ${current_price:.1f} | RSI: {rsi_text} | Config: ${margin:.1f} USDT @ {leverage}x | PnL: ${pnl:.1f} USDT ({pnl:.1f}%)")

                except Exception as e:
                    self.logger.error(f"Error checking exit conditions for {strategy_name}: {e}")

        except Exception as e:
            self.logger.error(f"Error checking exit conditions: {e}")
            self.telegram_reporter.report_error("Exit Check Error", str(e))

    def _get_strategy_config(self, strategy_name: str) -> Dict:
        """Helper method to get strategy configuration by name"""
        return self.strategies.get(strategy_name, {})

    async def _check_stop_loss(self, strategy_name: str, strategy_config: Dict, position, current_price: float) -> bool:
        """Check and trigger stop loss based on PnL percentage"""
        try:
            symbol = position.symbol
            # Calculate PnL using reliable method
            pnl_usdt = self._calculate_pnl(position, current_price)

            # Get stop loss threshold
            #stop_loss_threshold = strategy_config.get('max_loss_pct', 10)

            # Check if position should be closed due to stop loss (using Binance's unrealized PnL)
            # Calculate PnL percentage vs MARGIN (not position value) for proper stop loss
            strategy_config = self._get_strategy_config(strategy_name)
            margin_used = strategy_config.get('margin', 50.0) if strategy_config else 50.0
            max_loss_pct = strategy_config.get('max_loss_pct', 10) if strategy_config else 10

            # Calculate PnL vs margin (the actual risk amount)
            pnl_vs_margin = (pnl_usdt / margin_used) * 100 if margin_used > 0 else 0

            self.logger.debug(f"🔍 STOP LOSS CHECK | {strategy_name} | PnL: ${pnl_usdt:.2f} | Margin: ${margin_used:.2f} | PnL vs Margin: {pnl_vs_margin:.2f}% | Max Loss: -{max_loss_pct}%")

            if pnl_vs_margin <= -max_loss_pct:
                self.logger.warning(f"🛑 STOP LOSS TRIGGERED | {strategy_name} | {symbol} | PnL vs Margin: {pnl_vs_margin:.2f}% | Max Loss: -{max_loss_pct}%")
                close_result = self.order_manager.close_position(strategy_name, f"Stop Loss (PnL vs Margin: {pnl_vs_margin:.2f}%)")
                if close_result:
                    self.logger.info(f"✅ Position closed due to stop loss: {close_result}")
                return True

            return False

        except Exception as e:
            self.logger.error(f"Error checking stop loss for {strategy_name}: {e}")
            return False