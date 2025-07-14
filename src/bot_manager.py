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
from src.execution_engine.strategies.sma_crossover_config import SMACrossoverConfig
from src.execution_engine.strategies.rsi_oversold_config import RSIOversoldConfig
from src.reporting.telegram_reporter import TelegramReporter

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

        # Strategy configurations
        self.strategies = {
            'sma_crossover': SMACrossoverConfig.get_config(),
            'rsi_oversold': RSIOversoldConfig.get_config()
        }

        # Strategy assessment timers
        self.strategy_last_assessment = {}

        # Running state
        self.is_running = False
        
        # Anomaly detection
        self.trade_monitor = TradeMonitor()


    async def start(self):
        """Start the trading bot"""
        try:
            # Startup banner
            self.logger.info("🚀 TRADING BOT ACTIVATED")

            mode = "FUTURES TESTNET" if global_config.BINANCE_TESTNET else "FUTURES MAINNET"
            self.logger.info(f"📊 MODE: {mode}")

            strategies = list(self.strategies.keys())
            self.logger.info(f"📈 ACTIVE STRATEGIES: {', '.join(strategies)}")

            # Get initial balance
            balance_info = self.balance_fetcher.get_usdt_balance() or 0
            self.logger.info(f"💰 ACCOUNT BALANCE: ${balance_info:.2f} USDT")

            self.logger.info(f"⚡ MONITORING INTERVAL: {global_config.PRICE_UPDATE_INTERVAL}s")

            # Get pairs being watched
            pairs = [config['symbol'] for config in self.strategies.values()]

            # Send startup notification
            self.telegram_reporter.report_bot_startup(
                pairs=pairs,
                strategies=strategies,
                balance=balance_info,
                open_trades=len(self.order_manager.active_positions)
            )

            self.is_running = True

            # Start main trading loop
            await self._main_trading_loop()

        except Exception as e:
            self.logger.error(f"Error starting bot: {e}")
            self.telegram_reporter.report_error("Startup Error", str(e))
            raise

    async def stop(self):
        """Stop the trading bot"""
        self.logger.info("Stopping trading bot...")
        self.is_running = False

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

                # Sleep before next iteration
                await asyncio.sleep(global_config.PRICE_UPDATE_INTERVAL)

            except Exception as e:
                self.logger.error(f"Error in main trading loop: {e}")
                self.telegram_reporter.report_error("Main Loop Error", str(e))
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
            if self.trade_monitor.has_blocking_anomaly(strategy_name):
                anomaly_status = self.trade_monitor.get_anomaly_status(strategy_name)
                self.logger.info(f"⚠️ STRATEGY BLOCKED | {strategy_name.upper()} | {strategy_config['symbol']} | Status: {anomaly_status}")
                return

            # Check if strategy already has an active position
            if strategy_name in self.order_manager.active_positions:
                # Show current position status
                position = self.order_manager.active_positions[strategy_name]
                current_price = self._get_current_price(strategy_config['symbol'])
                if current_price:
                    pnl = self._calculate_pnl(position, current_price)
                    self.logger.info(f"📊 ACTIVE POSITION | {strategy_name.upper()} | {strategy_config['symbol']} | {position.side} | Entry: ${position.entry_price:.4f} | Current: ${current_price:.4f} | PnL: ${pnl:.2f} USDT")
                return

            # Check balance requirements
            if not self._check_balance_requirements(strategy_config):
                return

            # Log market assessment start
            self.logger.info(f"🔍 SCANNING {strategy_config['symbol']} | {strategy_name.upper()} | {strategy_config['timeframe']}")

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
                self.logger.info(f"🚨 ENTRY SIGNAL DETECTED | {strategy_name.upper()} | {strategy_config['symbol']} | {signal.signal_type.value} | ${signal.entry_price:.4f} | Reason: {signal.reason}")

                # Report signal to Telegram
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
                    self.logger.info(f"✅ POSITION OPENED | {strategy_name.upper()} | {strategy_config['symbol']} | {position.side} | Entry: ${position.entry_price:.4f} | Qty: {position.quantity} | SL: ${position.stop_loss:.4f} | TP: ${position.take_profit:.4f}")

                    # Report position opened
                    from dataclasses import asdict
                    self.telegram_reporter.report_position_opened(asdict(position))
                else:
                    self.logger.warning(f"❌ POSITION FAILED | {strategy_name.upper()} | {strategy_config['symbol']} | Could not execute signal")
            else:
                # Log market assessment result
                market_info = self._get_market_info(df, strategy_name)
                self.logger.info(f"📈 MARKET ASSESSMENT | {strategy_name.upper()} | {strategy_config['symbol']} | Price: ${current_price:.4f} | {market_info}")

                # Report market assessment
                self.telegram_reporter.report_market_assessment(strategy_name, {
                    'symbol': strategy_config['symbol'],
                    'current_price': current_price,
                    'trend': 'Neutral',
                    'signal_strength': 'No Signal'
                })

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
                should_exit = self.signal_processor.evaluate_exit_conditions(
                    df, 
                    {'entry_price': position.entry_price, 'stop_loss': position.stop_loss, 'take_profit': position.take_profit}, 
                    strategy_config
                )

                if should_exit:
                    current_price = df['close'].iloc[-1]
                    pnl = self._calculate_pnl(position, current_price)

                    # Determine exit reason
                    exit_reason = "Stop Loss" if current_price <= position.stop_loss else "Take Profit" if current_price >= position.take_profit else "Exit Signal"
                    pnl_status = "PROFIT" if pnl > 0 else "LOSS"

                    self.logger.info(f"🔄 EXIT TRIGGERED | {strategy_name.upper()} | {strategy_config['symbol']} | {exit_reason} | Exit: ${current_price:.4f} | PnL: ${pnl:.2f} ({pnl_status})")

                    # Close position
                    if self.order_manager.close_position(strategy_name, exit_reason):
                        self.logger.info(f"✅ POSITION CLOSED | {strategy_name.upper()} | {strategy_config['symbol']} | Final PnL: ${pnl:.2f}")

                        from dataclasses import asdict
                        self.telegram_reporter.report_position_closed(
                            asdict(position), 
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
            if ticker:
                return float(ticker['price'])
            return None
        except Exception as e:
            self.logger.error(f"Error getting current price for {symbol}: {e}")
            return None

    def _calculate_pnl(self, position, current_price: float) -> float:
        """Calculate PnL for a position"""
        try:
            if position.side == 'BUY':
                return (current_price - position.entry_price) * position.quantity
            else:  # SELL
                return (position.entry_price - current_price) * position.quantity
        except Exception as e:
            self.logger.error(f"Error calculating PnL: {e}")
            return 0.0

    def _get_market_info(self, df: pd.DataFrame, strategy_name: str) -> str:
        """Get market information string for logging"""
        try:
            if strategy_name == 'sma_crossover':
                if 'sma_20' in df.columns and 'sma_50' in df.columns:
                    sma_20 = df['sma_20'].iloc[-1]
                    sma_50 = df['sma_50'].iloc[-1]
                    trend = "Bullish" if sma_20 > sma_50 else "Bearish"
                    return f"SMA20: ${sma_20:.2f} | SMA50: ${sma_50:.2f} | Trend: {trend}"
            elif strategy_name == 'rsi_oversold':
                if 'rsi' in df.columns:
                    rsi = df['rsi'].iloc[-1]
                    condition = "Oversold" if rsi < 30 else "Overbought" if rsi > 70 else "Normal"
                    return f"RSI: {rsi:.2f} | Condition: {condition}"

            return "No Signal"
        except Exception as e:
            return f"Error: {e}"

    def get_bot_status(self) -> Dict:
        """Get current bot status"""
        return {
            'is_running': self.is_running,
            'active_positions': len(self.order_manager.active_positions),
            'strategies': list(self.strategies.keys()),
            'balance': self.balance_fetcher.get_usdt_balance()
        }

class TradeMonitor:
    """
    Monitors trades for anomalies like orphan and ghost trades.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.anomalies = {}  # Stores anomaly status per strategy

    def has_blocking_anomaly(self, strategy_name: str) -> bool:
        """
        Checks if a blocking anomaly exists for a strategy.
        """
        return strategy_name in self.anomalies

    def get_anomaly_status(self, strategy_name: str) -> Optional[str]:
        """
        Returns the status of the anomaly for a strategy, if any.
        """
        return self.anomalies.get(strategy_name)

    def detect_orphan_trade(self, strategy_name: str):
        """
        Detects and flags orphan trades.
        """
        self.logger.warning(f"Orphan trade detected for strategy: {strategy_name}")
        self.anomalies[strategy_name] = "Orphan Trade Detected"
        # TODO: Implement telegram notification

    def detect_ghost_trade(self, strategy_name: str):
        """
        Detects and flags ghost trades.
        """
        self.logger.warning(f"Ghost trade detected for strategy: {strategy_name}")
        self.anomalies[strategy_name] = "Ghost Trade Detected"
        # TODO: Implement telegram notification

    def clear_anomaly(self, strategy_name: str):
         """
         Clears anomaly after a cooldown period (e.g., 2 market cycles).
         """
         if strategy_name in self.anomalies:
            del self.anomalies[strategy_name]
            self.logger.info(f"Anomaly cleared for strategy: {strategy_name}")
         # TODO: Implement telegram notification