
import asyncio
import logging
from typing import Dict, List
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
        
        # Initialize components
        self.binance_client = BinanceClientWrapper()
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
    
    async def start(self):
        """Start the trading bot"""
        try:
            self.logger.info("Starting trading bot...")
            self.telegram_reporter.report_bot_startup()
            
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
            
            # Check if strategy already has an active position
            if strategy_name in self.order_manager.active_positions:
                return
            
            # Check balance requirements
            if not self._check_balance_requirements(strategy_config):
                return
            
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
            
            # Evaluate entry conditions
            signal = self.signal_processor.evaluate_entry_conditions(df, strategy_config)
            
            if signal:
                self.logger.info(f"Entry signal detected for {strategy_name}")
                
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
                    # Report position opened
                    from dataclasses import asdict
                    self.telegram_reporter.report_position_opened(asdict(position))
            else:
                # Report market assessment
                current_price = df['close'].iloc[-1]
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
                    pnl = (current_price - position.entry_price) * position.quantity
                    if position.side == 'SELL':
                        pnl = -pnl
                    
                    # Close position
                    if self.order_manager.close_position(strategy_name, "Exit signal triggered"):
                        from dataclasses import asdict
                        self.telegram_reporter.report_position_closed(
                            asdict(position), 
                            "Exit signal triggered", 
                            pnl
                        )
                        
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
    
    def get_bot_status(self) -> Dict:
        """Get current bot status"""
        return {
            'is_running': self.is_running,
            'active_positions': len(self.order_manager.active_positions),
            'strategies': list(self.strategies.keys()),
            'balance': self.balance_fetcher.get_usdt_balance()
        }
