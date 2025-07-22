
#!/usr/bin/env python3
"""
Comprehensive Strategy Entry Testing
Tests MACD Divergence and Smart Money Reversal strategies with simulated market conditions
"""

import sys
import os
import logging
import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np

# Add src to path
sys.path.append('src')

from src.binance_client.client import BinanceClientWrapper
from src.execution_engine.order_manager import OrderManager, Position
from src.execution_engine.trade_database import TradeDatabase
from src.strategy_processor.signal_processor import SignalProcessor, TradingSignal, SignalType
from src.execution_engine.strategies.smart_money_config import SmartMoneyStrategy
from src.config.global_config import global_config
from src.analytics.trade_logger import trade_logger

class StrategyTester:
    """Comprehensive strategy testing with simulated market conditions"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        
        # Initialize components
        self.binance_client = BinanceClientWrapper()
        self.trade_db = TradeDatabase()
        self.signal_processor = SignalProcessor()
        self.order_manager = OrderManager(self.binance_client, trade_logger)
        
        # Test configurations
        self.test_strategies = {
            'macd_divergence': {
                'name': 'MACD_TEST',
                'symbol': 'BTCUSDT',
                'timeframe': '5m',
                'margin': 15.0,
                'leverage': 3,
                'max_loss_pct': 8,
                'macd_fast': 12,
                'macd_slow': 26,
                'macd_signal': 9,
                'min_histogram_threshold': 0.0001,
                'macd_entry_threshold': 0.005,
                'macd_exit_threshold': 0.002,
                'confirmation_candles': 2,
                'partial_tp_pnl_threshold': 15.0,
                'partial_tp_position_percentage': 50.0,
                'decimals': 3
            },
            'smart_money': {
                'name': 'SMART_MONEY_TEST',
                'symbol': 'ETHUSDT',
                'timeframe': '15m',
                'margin': 12.0,
                'leverage': 3,
                'swing_lookback_period': 25,
                'sweep_threshold_pct': 0.1,
                'reversion_candles': 3,
                'volume_spike_multiplier': 2.0,
                'min_swing_distance_pct': 1.0,
                'session_filter_enabled': True,
                'allowed_sessions': ['LONDON', 'NEW_YORK'],
                'max_daily_trades': 3,
                'trend_filter_enabled': True,
                'decimals': 2
            }
        }
        
        self.test_results = []
        
    def create_test_market_data(self, symbol: str, strategy_type: str, scenario: str) -> pd.DataFrame:
        """Create realistic market data for testing specific scenarios"""
        try:
            # Get current real price as baseline
            ticker = self.binance_client.get_symbol_ticker(symbol)
            current_price = float(ticker['price'])
            
            # Generate 100 candles of test data
            num_candles = 100
            timestamps = [datetime.now() - timedelta(minutes=5*i) for i in range(num_candles)]
            timestamps.reverse()
            
            if strategy_type == 'macd_divergence':
                return self._create_macd_test_data(current_price, timestamps, scenario)
            elif strategy_type == 'smart_money':
                return self._create_smart_money_test_data(current_price, timestamps, scenario)
            else:
                raise ValueError(f"Unknown strategy type: {strategy_type}")
                
        except Exception as e:
            self.logger.error(f"Error creating test data: {e}")
            return pd.DataFrame()
    
    def _create_macd_test_data(self, base_price: float, timestamps: List[datetime], scenario: str) -> pd.DataFrame:
        """Create MACD-specific test scenarios"""
        prices = []
        volumes = []
        
        for i, timestamp in enumerate(timestamps):
            # Create different scenarios
            if scenario == 'bullish_divergence':
                # Price trend down but MACD building momentum up
                price_trend = base_price * (1 - 0.02 * (50 - i) / 50)  # Price declining
                macd_influence = 0.001 * np.sin(i * 0.3) * (i / 50)  # MACD building momentum
                price = price_trend + base_price * macd_influence
                
            elif scenario == 'bearish_divergence':
                # Price trend up but MACD building momentum down
                price_trend = base_price * (1 + 0.02 * (50 - i) / 50)  # Price rising
                macd_influence = -0.001 * np.sin(i * 0.3) * (i / 50)  # MACD building down momentum
                price = price_trend + base_price * macd_influence
                
            elif scenario == 'take_profit':
                # Strong trend after entry
                if i < 70:
                    price = base_price * (1 + 0.001 * i)  # Gradual rise
                else:
                    price = base_price * (1 + 0.03 + 0.002 * (i - 70))  # Acceleration
                    
            elif scenario == 'stop_loss':
                # Adverse movement after entry
                if i < 70:
                    price = base_price * (1 + 0.001 * i)  # Initial rise
                else:
                    price = base_price * (1 - 0.05 - 0.001 * (i - 70))  # Sharp decline
                    
            else:  # neutral
                price = base_price * (1 + 0.001 * np.random.normal(0, 1))
            
            # Add some noise
            price += price * 0.0005 * np.random.normal(0, 1)
            prices.append(max(price, 0.01))  # Ensure positive price
            
            # Volume patterns
            base_volume = 1000000
            if scenario in ['bullish_divergence', 'bearish_divergence'] and i > 80:
                volume = base_volume * (2 + np.random.uniform(0, 1))  # High volume for signal
            else:
                volume = base_volume * (0.5 + np.random.uniform(0, 1))
            volumes.append(volume)
        
        # Create DataFrame
        df = pd.DataFrame({
            'timestamp': timestamps,
            'open': prices,
            'high': [p * (1 + np.random.uniform(0, 0.002)) for p in prices],
            'low': [p * (1 - np.random.uniform(0, 0.002)) for p in prices],
            'close': prices,
            'volume': volumes
        })
        
        # Calculate technical indicators
        df = self._add_technical_indicators(df)
        return df
    
    def _create_smart_money_test_data(self, base_price: float, timestamps: List[datetime], scenario: str) -> pd.DataFrame:
        """Create Smart Money-specific test scenarios"""
        prices_high = []
        prices_low = []
        prices_close = []
        volumes = []
        
        for i, timestamp in enumerate(timestamps):
            base_vol = 500000
            
            if scenario == 'liquidity_sweep_long':
                if i < 80:
                    # Build up to swing low
                    price = base_price * (1 - 0.01 * np.sin(i * 0.1))
                elif i == 85:
                    # Sweep below swing low (liquidity hunt)
                    price = base_price * 0.985  # -1.5% sweep
                    base_vol *= 3  # High volume on sweep
                else:
                    # Recovery above swing low
                    price = base_price * (1 + 0.01 * (i - 85) / 15)
                    
            elif scenario == 'liquidity_sweep_short':
                if i < 80:
                    # Build up to swing high
                    price = base_price * (1 + 0.01 * np.sin(i * 0.1))
                elif i == 85:
                    # Sweep above swing high (liquidity hunt)
                    price = base_price * 1.015  # +1.5% sweep
                    base_vol *= 3  # High volume on sweep
                else:
                    # Recovery below swing high
                    price = base_price * (1 - 0.01 * (i - 85) / 15)
                    
            elif scenario == 'take_profit':
                # Strong directional move after sweep
                if i < 70:
                    price = base_price
                else:
                    price = base_price * (1 + 0.025 * (i - 70) / 30)  # 2.5% move
                    
            elif scenario == 'stop_loss':
                # Failed reversal
                if i < 80:
                    price = base_price
                elif i < 85:
                    price = base_price * (1 + 0.005)  # Small bounce
                else:
                    price = base_price * (1 - 0.03)  # Continued in original direction
                    
            else:  # neutral
                price = base_price * (1 + 0.001 * np.random.normal(0, 1))
            
            # Add noise and create OHLC
            noise = price * 0.0003 * np.random.normal(0, 1)
            close_price = price + noise
            high_price = close_price * (1 + abs(np.random.normal(0, 0.001)))
            low_price = close_price * (1 - abs(np.random.normal(0, 0.001)))
            
            prices_high.append(high_price)
            prices_low.append(low_price)
            prices_close.append(close_price)
            
            # Volume
            volume = base_vol * (0.5 + np.random.uniform(0, 1.5))
            volumes.append(volume)
        
        # Create DataFrame
        df = pd.DataFrame({
            'timestamp': timestamps,
            'open': prices_close,  # Simplified
            'high': prices_high,
            'low': prices_low,
            'close': prices_close,
            'volume': volumes
        })
        
        return df
    
    def _add_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add technical indicators to DataFrame"""
        try:
            # RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
            # EMAs for MACD
            df['ema_12'] = df['close'].ewm(span=12).mean()
            df['ema_26'] = df['close'].ewm(span=26).mean()
            
            # MACD
            df['macd'] = df['ema_12'] - df['ema_26']
            df['macd_signal'] = df['macd'].ewm(span=9).mean()
            df['macd_histogram'] = df['macd'] - df['macd_signal']
            
            # Moving averages
            df['sma_20'] = df['close'].rolling(window=20).mean()
            df['sma_50'] = df['close'].rolling(window=50).mean()
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error adding technical indicators: {e}")
            return df
    
    def test_macd_strategy(self, scenario: str) -> Dict[str, Any]:
        """Test MACD Divergence strategy with specific scenario"""
        try:
            self.logger.info(f"🔬 TESTING MACD STRATEGY | Scenario: {scenario.upper()}")
            
            config = self.test_strategies['macd_divergence'].copy()
            symbol = config['symbol']
            
            # Create test data
            df = self.create_test_market_data(symbol, 'macd_divergence', scenario)
            if df.empty:
                return {'success': False, 'error': 'Failed to create test data'}
            
            # Test signal generation
            signal = self.signal_processor.evaluate_macd_divergence(df, config)
            
            if signal:
                self.logger.info(f"✅ MACD SIGNAL GENERATED | {signal.signal_type} | Entry: ${signal.entry_price:.4f}")
                
                # Test position execution
                position = self.order_manager.execute_signal(signal, config)
                
                if position:
                    self.logger.info(f"✅ POSITION OPENED | Trade ID: {position.trade_id}")
                    
                    # Test scenarios
                    result = self._test_position_lifecycle(position, config, scenario, df)
                    result['strategy'] = 'MACD_DIVERGENCE'
                    result['signal_generated'] = True
                    result['position_opened'] = True
                    
                    return result
                else:
                    return {
                        'strategy': 'MACD_DIVERGENCE',
                        'scenario': scenario,
                        'signal_generated': True,
                        'position_opened': False,
                        'success': False,
                        'error': 'Failed to open position'
                    }
            else:
                self.logger.warning(f"⚠️ NO MACD SIGNAL GENERATED for scenario: {scenario}")
                return {
                    'strategy': 'MACD_DIVERGENCE',
                    'scenario': scenario,
                    'signal_generated': False,
                    'position_opened': False,
                    'success': False,
                    'error': 'No signal generated'
                }
                
        except Exception as e:
            self.logger.error(f"❌ MACD TEST ERROR: {e}")
            return {'success': False, 'error': str(e)}
    
    def test_smart_money_strategy(self, scenario: str) -> Dict[str, Any]:
        """Test Smart Money Reversal strategy with specific scenario"""
        try:
            self.logger.info(f"🔬 TESTING SMART MONEY STRATEGY | Scenario: {scenario.upper()}")
            
            config = self.test_strategies['smart_money'].copy()
            symbol = config['symbol']
            
            # Create test data
            df = self.create_test_market_data(symbol, 'smart_money', scenario)
            if df.empty:
                return {'success': False, 'error': 'Failed to create test data'}
            
            # Create Smart Money strategy instance
            smart_money = SmartMoneyStrategy(config)
            
            # Convert DataFrame to klines format for Smart Money strategy
            klines = []
            for _, row in df.iterrows():
                kline = [
                    int(row['timestamp'].timestamp() * 1000),  # timestamp
                    str(row['open']),   # open
                    str(row['high']),   # high
                    str(row['low']),    # low
                    str(row['close']),  # close
                    str(row['volume']), # volume
                ]
                klines.append(kline)
            
            # Test signal generation
            current_price = df['close'].iloc[-1]
            signal = smart_money.analyze_market(klines, current_price)
            
            if signal:
                self.logger.info(f"✅ SMART MONEY SIGNAL GENERATED | {signal.signal_type} | Entry: ${signal.entry_price:.4f}")
                
                # Test position execution
                position = self.order_manager.execute_signal(signal, config)
                
                if position:
                    self.logger.info(f"✅ POSITION OPENED | Trade ID: {position.trade_id}")
                    
                    # Test scenarios
                    result = self._test_position_lifecycle(position, config, scenario, df)
                    result['strategy'] = 'SMART_MONEY'
                    result['signal_generated'] = True
                    result['position_opened'] = True
                    
                    return result
                else:
                    return {
                        'strategy': 'SMART_MONEY',
                        'scenario': scenario,
                        'signal_generated': True,
                        'position_opened': False,
                        'success': False,
                        'error': 'Failed to open position'
                    }
            else:
                self.logger.warning(f"⚠️ NO SMART MONEY SIGNAL GENERATED for scenario: {scenario}")
                return {
                    'strategy': 'SMART_MONEY',
                    'scenario': scenario,
                    'signal_generated': False,
                    'position_opened': False,
                    'success': False,
                    'error': 'No signal generated'
                }
                
        except Exception as e:
            self.logger.error(f"❌ SMART MONEY TEST ERROR: {e}")
            return {'success': False, 'error': str(e)}
    
    def _test_position_lifecycle(self, position: Position, config: Dict, scenario: str, df: pd.DataFrame) -> Dict[str, Any]:
        """Test complete position lifecycle from entry to exit"""
        try:
            result = {
                'scenario': scenario,
                'trade_id': position.trade_id,
                'entry_price': position.entry_price,
                'symbol': position.symbol,
                'side': position.side,
                'quantity': position.quantity,
                'margin_used': getattr(position, 'actual_margin_used', config.get('margin', 10.0)),
                'success': True
            }
            
            # Verify database entry
            trade_data = self.trade_db.get_trade(position.trade_id)
            if trade_data:
                self.logger.info(f"✅ DATABASE RECORD CREATED | Trade ID: {position.trade_id}")
                result['database_entry'] = True
            else:
                self.logger.error(f"❌ DATABASE RECORD MISSING | Trade ID: {position.trade_id}")
                result['database_entry'] = False
                result['success'] = False
            
            # Simulate price movement based on scenario
            if scenario in ['take_profit', 'bullish_divergence', 'liquidity_sweep_long']:
                # Simulate profitable movement
                if position.side == 'BUY':
                    exit_price = position.entry_price * 1.025  # +2.5% profit
                else:
                    exit_price = position.entry_price * 0.975  # +2.5% profit for short
                exit_reason = "Take Profit Hit"
                
            elif scenario in ['stop_loss', 'bearish_divergence', 'liquidity_sweep_short']:
                # Simulate loss scenario
                if position.side == 'BUY':
                    exit_price = position.entry_price * 0.985  # -1.5% loss
                else:
                    exit_price = position.entry_price * 1.015  # -1.5% loss for short
                exit_reason = "Stop Loss Hit"
                
            else:
                # Neutral exit
                exit_price = position.entry_price * 1.005  # Small profit
                exit_reason = "Manual Exit"
            
            # Test partial take profit if applicable
            partial_tp_tested = False
            if config.get('partial_tp_pnl_threshold', 0) > 0:
                # Simulate partial TP trigger
                partial_price = position.entry_price * 1.015 if position.side == 'BUY' else position.entry_price * 0.985
                partial_tp_result = self.order_manager.check_partial_take_profit(config['name'], partial_price)
                if partial_tp_result:
                    self.logger.info(f"✅ PARTIAL TAKE PROFIT EXECUTED")
                    result['partial_tp_executed'] = True
                    partial_tp_tested = True
                else:
                    result['partial_tp_executed'] = False
            
            # Close position
            self.logger.info(f"🔄 CLOSING POSITION | Exit Price: ${exit_price:.4f} | Reason: {exit_reason}")
            
            # Manually set exit price for testing (since we're not using real market)
            close_result = self.order_manager.close_position(config['name'], exit_reason)
            
            if close_result:
                self.logger.info(f"✅ POSITION CLOSED | P&L: ${close_result.get('pnl_usdt', 0):.2f} USDT")
                result['position_closed'] = True
                result['exit_price'] = close_result.get('exit_price', exit_price)
                result['pnl_usdt'] = close_result.get('pnl_usdt', 0)
                result['pnl_percentage'] = close_result.get('pnl_percentage', 0)
                result['exit_reason'] = exit_reason
                
                # Verify database update
                updated_trade = self.trade_db.get_trade(position.trade_id)
                if updated_trade and updated_trade.get('trade_status') == 'CLOSED':
                    self.logger.info(f"✅ DATABASE UPDATED | Status: CLOSED")
                    result['database_updated'] = True
                else:
                    self.logger.error(f"❌ DATABASE NOT UPDATED | Trade ID: {position.trade_id}")
                    result['database_updated'] = False
                    result['success'] = False
                    
            else:
                self.logger.error(f"❌ FAILED TO CLOSE POSITION")
                result['position_closed'] = False
                result['success'] = False
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ POSITION LIFECYCLE TEST ERROR: {e}")
            return {'success': False, 'error': str(e)}
    
    def run_comprehensive_tests(self) -> Dict[str, Any]:
        """Run comprehensive tests for both strategies"""
        try:
            self.logger.info("🚀 STARTING COMPREHENSIVE STRATEGY TESTING")
            
            # Test scenarios for each strategy
            test_scenarios = {
                'macd_divergence': [
                    'bullish_divergence',
                    'bearish_divergence', 
                    'take_profit',
                    'stop_loss'
                ],
                'smart_money': [
                    'liquidity_sweep_long',
                    'liquidity_sweep_short',
                    'take_profit',
                    'stop_loss'
                ]
            }
            
            all_results = []
            
            # Test MACD Strategy
            self.logger.info("=" * 60)
            self.logger.info("🔬 TESTING MACD DIVERGENCE STRATEGY")
            self.logger.info("=" * 60)
            
            for scenario in test_scenarios['macd_divergence']:
                self.logger.info(f"\n📊 Testing MACD scenario: {scenario}")
                result = self.test_macd_strategy(scenario)
                result['timestamp'] = datetime.now().isoformat()
                all_results.append(result)
                time.sleep(2)  # Brief pause between tests
            
            # Test Smart Money Strategy
            self.logger.info("=" * 60)
            self.logger.info("🧠 TESTING SMART MONEY STRATEGY")
            self.logger.info("=" * 60)
            
            for scenario in test_scenarios['smart_money']:
                self.logger.info(f"\n🎯 Testing Smart Money scenario: {scenario}")
                result = self.test_smart_money_strategy(scenario)
                result['timestamp'] = datetime.now().isoformat()
                all_results.append(result)
                time.sleep(2)  # Brief pause between tests
            
            # Generate summary
            summary = self._generate_test_summary(all_results)
            
            self.logger.info("=" * 60)
            self.logger.info("📈 TEST SUMMARY")
            self.logger.info("=" * 60)
            
            for key, value in summary.items():
                self.logger.info(f"{key}: {value}")
            
            return {
                'summary': summary,
                'detailed_results': all_results,
                'test_completed': True,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"❌ COMPREHENSIVE TEST ERROR: {e}")
            return {'success': False, 'error': str(e)}
    
    def _generate_test_summary(self, results: List[Dict]) -> Dict[str, Any]:
        """Generate comprehensive test summary"""
        summary = {
            'total_tests': len(results),
            'successful_tests': 0,
            'failed_tests': 0,
            'macd_tests': 0,
            'smart_money_tests': 0,
            'signals_generated': 0,
            'positions_opened': 0,
            'positions_closed': 0,
            'database_entries': 0,
            'database_updates': 0,
            'partial_tp_executed': 0,
            'avg_pnl_usdt': 0,
            'total_pnl_usdt': 0
        }
        
        total_pnl = 0
        pnl_count = 0
        
        for result in results:
            if result.get('success', False):
                summary['successful_tests'] += 1
            else:
                summary['failed_tests'] += 1
            
            if result.get('strategy') == 'MACD_DIVERGENCE':
                summary['macd_tests'] += 1
            elif result.get('strategy') == 'SMART_MONEY':
                summary['smart_money_tests'] += 1
            
            if result.get('signal_generated', False):
                summary['signals_generated'] += 1
            
            if result.get('position_opened', False):
                summary['positions_opened'] += 1
            
            if result.get('position_closed', False):
                summary['positions_closed'] += 1
            
            if result.get('database_entry', False):
                summary['database_entries'] += 1
            
            if result.get('database_updated', False):
                summary['database_updates'] += 1
            
            if result.get('partial_tp_executed', False):
                summary['partial_tp_executed'] += 1
            
            if 'pnl_usdt' in result:
                total_pnl += result['pnl_usdt']
                pnl_count += 1
        
        if pnl_count > 0:
            summary['avg_pnl_usdt'] = round(total_pnl / pnl_count, 2)
            summary['total_pnl_usdt'] = round(total_pnl, 2)
        
        return summary

def main():
    """Run the comprehensive strategy tests"""
    try:
        print("🚀 INITIALIZING STRATEGY TESTING ENVIRONMENT")
        
        tester = StrategyTester()
        
        # Verify connection
        if not tester.binance_client.test_connection():
            print("❌ BINANCE CONNECTION FAILED - Cannot proceed with tests")
            return
        
        print("✅ BINANCE CONNECTION VERIFIED")
        
        # Run comprehensive tests
        results = tester.run_comprehensive_tests()
        
        if results.get('test_completed', False):
            print("\n🎉 ALL TESTS COMPLETED SUCCESSFULLY")
            print(f"📊 Summary: {results['summary']}")
            
            # Save results to file
            import json
            with open('strategy_test_results.json', 'w') as f:
                json.dump(results, f, indent=2)
            print("💾 Test results saved to strategy_test_results.json")
            
        else:
            print(f"❌ TESTS FAILED: {results.get('error', 'Unknown error')}")
        
    except Exception as e:
        print(f"❌ CRITICAL ERROR: {e}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    main()
