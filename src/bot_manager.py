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
        self.order_manager = OrderManager(self.binance_client)
        self.telegram_reporter = TelegramReporter()

        # Initialize strategies with flexible configuration
        base_strategies = {
            'rsi_oversold': RSIOversoldConfig.get_config(),
            'macd_divergence': MACDDivergenceConfig.get_config()
        }

        # Apply trading parameters through config manager
        self.strategies = {}
        for strategy_name, base_config in base_strategies.items():
            self.strategies[strategy_name] = trading_config_manager.get_strategy_config(
                strategy_name, base_config
            )

        # Strategy assessment timers
        self.strategy_last_assessment = {}

        # Running state
        self.is_running = False
        self.startup_notified = False  # Flag to prevent duplicate startup notifications

        # Initialize anomaly detector for orphan/ghost detection
        self.anomaly_detector = AnomalyDetector(
            binance_client=self.binance_client,
            order_manager=self.order_manager,
            telegram_reporter=self.telegram_reporter
        )

        # Set anomaly detector reference in order manager
        self.order_manager.set_anomaly_detector(self.anomaly_detector)
        self.logger.info("🔍 Anomaly detector initialized and connected to order manager")

        # Register strategies with anomaly detector
        for strategy_name, strategy_config in self.strategies.items():
            self.anomaly_detector.register_strategy(strategy_name, strategy_config['symbol'])
            self.logger.debug(f"🔍 Registered strategy {strategy_name} with symbol {strategy_config['symbol']}")

        # Daily reporter
        from src.analytics.daily_reporter import DailyReporter
        self.daily_reporter = DailyReporter(self.telegram_reporter)

        # Track if startup notification was sent
        self.startup_notification_sent = False


    async def start(self):
        """Start the trading bot"""
        self.is_running = True

        # Log startup source - simplified detection
        startup_source = "Web Interface"  # Default to web interface since this is the issue we're fixing

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
            # If detection fails, assume console for safety
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
            if not self.startup_notified:
                self.logger.info(f"📱 SENDING TELEGRAM STARTUP NOTIFICATION ({startup_source})")

                try:
                    self.telegram_reporter.report_bot_startup(
                        pairs=pairs,
                        strategies=strategies,
                        balance=balance_info,
                        open_trades=len(self.order_manager.active_positions)
                    )
                    self.logger.info("✅ TELEGRAM STARTUP NOTIFICATION SENT SUCCESSFULLY")
                    self.startup_notified = True
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
        self.logger.info(f"Stopping trading bot: {reason}")
        self.is_running = False

        # Send shutdown notification to Telegram
        self.telegram_reporter.report_bot_stopped(reason)

        # Small delay to ensure message is sent before process terminates
        await asyncio.sleep(1)

    async def _main_trading_loop(self):
        """Main trading loop"""
        while self.is_running:
            try:
                # Check each strategy
                for strategy_name, strategy_config in self.strategies.items():
                    if not strategy_config.get('enabled', True):
                        continue

                    await self._process_strategy(strategy_name, strategy_config)

                # Check exit conditions for open positions
                await self._check_exit_conditions()

                # Check for trade anomalies (orphan/ghost trades)
                self.anomaly_detector.run_detection()

                # Sleep before next iteration
                await asyncio.sleep(global_config.PRICE_UPDATE_INTERVAL)

            except Exception as e:
                error_msg = f"Main Loop Error: {str(e)}"
                self.logger.error(error_msg)
                self.telegram_reporter.report_error("Main Loop Error", str(e))

                # Log memory usage for debugging
                import psutil
                process = psutil.Process()
                memory_mb = process.memory_info().rss / 1024 / 1024
                self.logger.warning(f"🔍 MEMORY USAGE: {memory_mb:.1f} MB")

                # If it's a critical error, stop the bot
                if "API" in str(e) or "connection" in str(e).lower() or "auth" in str(e).lower():
                    await self.stop(f"Critical error: {str(e)}")
                    break

                await asyncio.sleep(5)  # Brief pause before retrying

    async def _process_strategy(self, strategy_name: str, strategy_config: Dict):
        """Process a single strategy"""
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
                # Show current position status
                position = self.order_manager.active_positions[strategy_name]
                current_price = self._get_current_price(strategy_config['symbol'])
                if current_price:
                    # Log active position with proper PnL calculation
                    pnl_usdt = self._calculate_pnl(position, current_price)
                    position_value_usdt = position.entry_price * position.quantity
                    pnl_percent = (pnl_usdt / position_value_usdt) * 100 if position_value_usdt > 0 else 0

                    # Show comprehensive position status
                    self.logger.info(f"📊 TRADE IN PROGRESS | {strategy_name.upper()} | {position.symbol} | Entry: ${position.entry_price:.4f} | Current: ${current_price:.4f} | Value: ${position_value_usdt:.2f} USDT | PnL: ${pnl_usdt:.2f} USDT ({pnl_percent:+.2f}%)")
                else:
                    # Fallback if price fetch fails
                    position_value_usdt = position.entry_price * position.quantity
                    self.logger.info(f"📊 TRADE IN PROGRESS | {strategy_name.upper()} | {position.symbol} | Entry: ${position.entry_price:.4f} | Value: ${position_value_usdt:.2f} USDT | PnL: Price fetch failed")
                return

            # Check balance requirements
            if not self._check_balance_requirements(strategy_config):
                return

            # Log market assessment start
            margin = strategy_config.get('margin', 50.0)
            leverage = strategy_config.get('leverage', 5)
            self.logger.info(f"🔍 SCANNING {strategy_config['symbol']} | {strategy_name.upper()} | {strategy_config['timeframe']} | Margin: ${margin:.1f} | Leverage: {leverage}x")

            # Get market data
            df = self.price_fetcher.get_ohlcv_data(
                strategy_config['symbol'],
                strategy_config['timeframe']
            )

            if df is None or df.empty:
                self.logger.warning(f"No data for {strategy_config['symbol']}")
                return

            # Calculate indicators
            df = self.price_fetcher.calculate_indicators(df)

            # Get current market info
            current_price = df['close'].iloc[-1]

            # Evaluate entry conditions
            signal = self.signal_processor.evaluate_entry_conditions(df, strategy_config)

            if signal:
                self.logger.info(f"🚨 ENTRY SIGNAL DETECTED | {strategy_name.upper()} | {strategy_config['symbol']} | {signal.signal_type.value} | ${signal.entry_price:,.1f} | Reason: {signal.reason}")

                # Entry signals are still reported to Telegram
                self.telegram_reporter.report_entry_signal(strategy_name, {
                    'symbol': strategy_config['symbol'],
                    'signal_type': signal.signal_type.value,
                    'entry_price': signal.entry_price,
                    'stop_loss': signal.stop_loss,
                    'take_profit': signal.take_profit,
                    'reason': signal.reason
                })

                # Execute the signal
                position = self.order_manager.execute_signal(signal, strategy_config)

                if position:
                    self.logger.info(f"✅ POSITION OPENED | {strategy_name.upper()} | {strategy_config['symbol']} | {position.side} | Entry: ${position.entry_price:,.1f} | Qty: {position.quantity:,.1f} | SL: ${position.stop_loss:,.1f} | TP: ${position.take_profit:,.1f}")

                    # Report position opened
                    from dataclasses import asdict
                    self.telegram_reporter.report_position_opened(asdict(position))
                else:
                    self.logger.warning(f"❌ POSITION FAILED | {strategy_name.upper()} | {strategy_config['symbol']} | Could not execute signal")
            else:
                # Log market assessment result (console only, no Telegram)
                market_info = self._get_market_info(df, strategy_name)
                margin = strategy_config.get('margin', 50.0)
                self.logger.info(f"📈 MARKET ASSESSMENT | {strategy_name.upper()} | {strategy_config['symbol']} | Price: ${current_price:,.1f} | Margin: ${margin:.1f} | {market_info}")

        except Exception as e:
            self.logger.error(f"Error processing strategy {strategy_name}: {e}")
            self.telegram_reporter.report_error("Strategy Processing Error", str(e), strategy_name)

    async def _check_exit_conditions(self):
        """Check exit conditions for all open positions"""
        try:
            active_positions = self.order_manager.get_active_positions()

            for strategy_name, position in active_positions.items():
                strategy_config = self.strategies.get(strategy_name)
                if not strategy_config:
                    continue

                # Get current market data
                df = self.price_fetcher.get_ohlcv_data(
                    strategy_config['symbol'],
                    strategy_config['timeframe']
                )

                if df is None or df.empty:
                    continue

                # Calculate indicators
                df = self.price_fetcher.calculate_indicators(df)

                # Check exit conditions
                exit_reason = self.signal_processor.evaluate_exit_conditions(
                    df, 
                    {'entry_price': position.entry_price, 'stop_loss': position.stop_loss, 'take_profit': position.take_profit}, 
                    strategy_config
                )

                if exit_reason:
                    current_price = df['close'].iloc[-1]
                    pnl = self._calculate_pnl(position, current_price)

                    pnl_status = "PROFIT" if pnl > 0 else "LOSS"

                    self.logger.info(f"🔄 EXIT TRIGGERED | {strategy_name.upper()} | {strategy_config['symbol']} | {exit_reason} | Exit: ${current_price:,.1f} | PnL: ${pnl:,.1f} ({pnl_status})")

                    # Close position
                    if self.order_manager.close_position(strategy_name, exit_reason):
                        self.logger.info(f"✅ POSITION CLOSED | {strategy_name.upper()} | {strategy_config['symbol']} | {exit_reason} | Entry: ${position.entry_price:,.1f} | Exit: ${current_price:,.1f} | Final PnL: ${pnl:,.1f}")

                        from dataclasses import asdict
                        position_data = asdict(position)
                        position_data['exit_price'] = current_price  # Add current price as exit price
                        self.telegram_reporter.report_position_closed(
                            position_data, 
                            exit_reason, 
                            pnl
                        )
                    else:
                        self.logger.warning(f"❌ CLOSE FAILED | {strategy_name.upper()} | {strategy_config['symbol']} | Could not close position")

        except Exception as e:
            self.logger.error(f"Error checking exit conditions: {e}")
            self.telegram_reporter.report_error("Exit Check Error", str(e))

    def _should_assess_strategy(self, strategy_name: str, strategy_config: Dict) -> bool:
        """Check if strategy should be assessed based on timing"""
        if strategy_name not in self.strategy_last_assessment:
            return True

        last_assessment = self.strategy_last_assessment[strategy_name]
        assessment_interval = strategy_config.get('assessment_interval', 300)  # Default 5 minutes

        return (datetime.now() - last_assessment).seconds >= assessment_interval

    def _check_balance_requirements(self, strategy_config: Dict) -> bool:
        """Check if there's sufficient balance for the strategy"""
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
        """Update strategy configuration"""
        if strategy_name in self.strategies:
            self.strategies[strategy_name].update(updates)
            self.logger.info(f"Updated configuration for {strategy_name}: {updates}")
        else:
            self.logger.warning(f"Strategy {strategy_name} not found")

    def _get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for a symbol"""
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
            self.logger.error(f"❌ PRICE FETCH ERROR | {symbol} | {e}")
            return None

    def _calculate_pnl(self, position, current_price: float) -> float:
        """Calculate PnL for a position (futures trading)"""
        try:
            if not current_price or current_price <= 0:
                self.logger.warning(f"❌ PnL CALC | Invalid current price: {current_price}")
                return 0.0

            # For futures trading, PnL calculation
            if position.side == 'BUY':  # Long position
                pnl = (current_price - position.entry_price) * position.quantity
            else:  # Short position (SELL)
                pnl = (position.entry_price - current_price) * position.quantity

            self.logger.debug(f"🔍 PnL CALC | {position.symbol} | Side: {position.side} | Entry: ${position.entry_price:.4f} | Current: ${current_price:.4f} | Qty: {position.quantity} | PnL: ${pnl:.2f}")
            return pnl

        except Exception as e:
            self.logger.error(f"❌ PnL CALCULATION ERROR | {position.symbol} | {e}")
            return 0.0

    def _get_market_info(self, df: pd.DataFrame, strategy_name: str) -> str:
        """Get market information string for logging"""
        try:
            if strategy_name == 'rsi_oversold':
                if 'rsi' in df.columns:
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
                symbol = strategy_config['symbol']

                # Get open positions from Binance for this symbol
                try:
                    if self.binance_client.is_futures:
                        positions = self.binance_client.client.futures_position_information(symbol=symbol)

                        for position in positions:
                            position_amt = float(position.get('positionAmt', 0))

                            if abs(position_amt) > 0:  # Position exists
                                # Recover position details
                                entry_price = float(position.get('entryPrice', 0))
                                side = 'BUY' if position_amt > 0 else 'SELL'
                                quantity = abs(position_amt)

                                self.logger.info(f"📍 EXISTING POSITION FOUND | {strategy_name.upper()} | {symbol} | {side} | Qty: {quantity:,.6f} | Entry: ${entry_price:,.4f}")

                                # Check if this position has a trade ID in our database
                                is_legitimate, trade_id = self.order_manager.is_legitimate_bot_position(strategy_name, symbol, side, quantity, entry_price)

                                if is_legitimate and trade_id:
                                    # This is a legitimate bot position - recover it
                                    self.logger.info(f"✅ LEGITIMATE BOT POSITION | Trade ID: {trade_id} | {strategy_name.upper()} | {symbol}")

                                    from src.execution_engine.order_manager import Position
                                    from datetime import datetime

                                    recovered_position = Position(
                                        strategy_name=strategy_name,
                                        symbol=symbol,
                                        side=side,
                                        entry_price=entry_price,
                                        quantity=quantity,
                                        stop_loss=entry_price * 0.985 if side == 'BUY' else entry_price * 1.015,  # Estimated
                                        take_profit=entry_price * 1.025 if side == 'BUY' else entry_price * 0.975,  # Estimated
                                        position_side='LONG' if side == 'BUY' else 'SHORT',
                                        order_id=0,  # Unknown on recovery
                                        entry_time=datetime.now(),  # Current time as fallback
                                        status='RECOVERED',
                                        trade_id=trade_id  # Include the trade ID
                                    )

                                    # Add to active positions
                                    self.order_manager.active_positions[strategy_name] = recovered_position
                                    recovered_count += 1

                                    # Notify anomaly detector that this is a legitimate bot position
                                    self.anomaly_detector.register_bot_trade(symbol, strategy_name)

                                    self.logger.info(f"✅ POSITION RECOVERED | Trade ID: {trade_id} | {strategy_name.upper()} | {symbol} | Entry: ${entry_price:,.4f} | Qty: {quantity:,.6f}")
                                else:
                                    # No trade ID found - this is a manual position
                                    self.logger.warning(f"🚨 MANUAL POSITION | No Trade ID | {strategy_name.upper()} | {symbol} | Ghost detection will handle it")

                                break  # Only one position per strategy

                except Exception as e:
                    self.logger.warning(f"Could not check positions for {symbol}: {e}")

            if recovered_count > 0:
                self.logger.info(f"✅ RECOVERED {recovered_count} LEGITIMATE BOT POSITIONS")
            else:
                self.logger.info("✅ NO LEGITIMATE BOT POSITIONS FOUND FOR RECOVERY")

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
                # Get current position info from Binance
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
                                if self.order_manager.is_legitimate_bot_position(strategy_name, symbol, side, quantity, entry_price):
                                    self.logger.info(f"🔍 MISIDENTIFIED POSITION FOUND | {strategy_name.upper()} | {symbol} | Clearing ghost anomaly and recovering position")

                                    # Clear the ghost anomaly
                                    self.anomaly_detector.clear_anomaly_by_id(anomaly.id, "Position re-validated as legitimate bot trade")

                                    # Recover the position properly
                                    from src.execution_engine.order_manager import Position
                                    from datetime import datetime

                                    # Generate recovery trade ID for tracking
                                    recovery_trade_id = f"RECOVERY_{strategy_name}_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

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
                                        trade_id=recovery_trade_id
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
        """Get current bot status"""
        return {
            'is_running': self.is_running,
            'active_positions': len(self.order_manager.active_positions),
            'strategies': list(self.strategies.keys()),
            'balance': self.balance_fetcher.get_usdt_balance()
        }

    async def _recover_positions(self) -> None:
        """Recover existing positions from Binance on startup (with ghost trade protection)"""
        try:
            self.logger.info("🔍 CHECKING FOR EXISTING POSITIONS...")

            recovered_count = 0

            if self.binance_client.is_futures:
                account_info = self.binance_client.client.futures_account()
                positions = account_info.get('positions', [])

                for position in positions:
                    position_amt = float(position.get('positionAmt', 0))

                    if abs(position_amt) > 0.001:  # Position exists
                        symbol = position.get('symbol')
                        entry_price = float(position.get('entryPrice', 0))

                        # Find which strategy should handle this symbol
                        strategy_name = None
                        for name, strategy in self.strategies.items():
                            if strategy['symbol'] == symbol:
                                strategy_name = name
                                break

                        if strategy_name:
                            side = 'BUY' if position_amt > 0 else 'SELL'

                            self.logger.info(f"🔍 POSITION FOUND | {strategy_name.upper()} | {symbol} | {side} | Qty: {abs(position_amt)} | Entry: ${entry_price}")

                            # Use enhanced position validation
                            if self.order_manager.is_legitimate_bot_position(strategy_name, symbol, side, abs(position_amt), entry_price):
                                # This is a legitimate bot position - recover it
                                self.logger.info(f"✅ LEGITIMATE BOT POSITION | {strategy_name.upper()} | {symbol} | Recovering...")

                                from src.execution_engine.order_manager import Position
                                from datetime import datetime

                                recovered_position = Position(
                                    strategy_name=strategy_name,
                                    symbol=symbol,
                                    side=side,
                                    entry_price=entry_price,
                                    quantity=abs(position_amt),
                                    stop_loss=entry_price * 0.985 if side == 'BUY' else entry_price * 1.015,
                                    take_profit=entry_price * 1.025 if side == 'BUY' else entry_price * 0.975,
                                    position_side='LONG' if side == 'BUY' else 'SHORT',
                                    order_id=0,
                                    entry_time=datetime.now(),
                                    status='RECOVERED'
                                )

                                self.order_manager.active_positions[strategy_name] = recovered_position
                                recovered_count += 1

                                self.logger.info(f"✅ POSITION RECOVERED | {strategy_name.upper()} | {symbol} | Entry: ${entry_price} | Qty: {abs(position_amt)}")
                            else:
                                # This is likely a manual position - let ghost trade detection handle it
                                self.logger.warning(f"🚨 UNVERIFIED POSITION | {strategy_name.upper()} | {symbol} | Will be processed by ghost trade detection")

            self.logger.info(f"✅ POSITION RECOVERY COMPLETE: {recovered_count} legitimate bot positions recovered")
            self.logger.info(f"🔍 Unverified positions will be processed by trade monitoring system")

        except Exception as e:
            self.logger.error(f"Error checking existing positions: {e}")
            import traceback
            self.logger.error(f"Position check error: {traceback.format_exc()}")