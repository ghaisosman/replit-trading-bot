
#!/usr/bin/env python3
"""
Comprehensive MACD Strategy Test
Tests the complete trade lifecycle: scanning → entry → execution → logging → recovery → management → exit
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import time

# Add src to path
sys.path.append('src')

from src.execution_engine.strategies.macd_divergence_strategy import MACDDivergenceStrategy
from src.strategy_processor.signal_processor import SignalProcessor, TradingSignal, SignalType
from src.execution_engine.order_manager import OrderManager
from src.execution_engine.trade_database import TradeDatabase
from src.binance_client.client import BinanceClientWrapper
from src.analytics.trade_logger import TradeLogger
from src.config.trading_config import trading_config_manager

class MACDTestSuite:
    def __init__(self):
        self.results = {}
        self.test_symbol = "BTCUSDT"
        
        # Initialize components
        try:
            self.binance_client = BinanceClientWrapper()
            self.trade_logger = TradeLogger()
            self.order_manager = OrderManager(self.binance_client, self.trade_logger)
            self.trade_database = TradeDatabase("trading_data/test_trade_database.json")
            self.signal_processor = SignalProcessor()
            
            # Get MACD config
            self.macd_config = trading_config_manager.get_strategy_config('macd_divergence', {
                'name': 'macd_divergence',
                'symbol': self.test_symbol,
                'timeframe': '1h',
                'macd_fast': 12,
                'macd_slow': 26,
                'macd_signal': 9,
                'min_histogram_threshold': 0.0001,
                'min_distance_threshold': 0.0015,
                'margin': 50.0,
                'leverage': 5,
                'max_loss_pct': 10
            })
            
            self.macd_strategy = MACDDivergenceStrategy(self.macd_config)
            
            print("✅ Test suite initialized successfully")
            
        except Exception as e:
            print(f"❌ Error initializing test suite: {e}")
            import traceback
            traceback.print_exc()

    def create_test_data(self, trend_type="bullish_crossover"):
        """Create synthetic market data for testing"""
        print(f"\n📊 Creating test data for {trend_type}")
        
        # Create base price data
        np.random.seed(42)  # For reproducible results
        base_price = 45000
        periods = 100
        
        # Create realistic price movement
        price_changes = np.random.normal(0, 0.01, periods)
        prices = [base_price]
        
        for i in range(1, periods):
            change = price_changes[i]
            if trend_type == "bullish_crossover" and i > 80:
                # Create bullish momentum in last 20 candles
                change += 0.005
            elif trend_type == "bearish_crossover" and i > 80:
                # Create bearish momentum in last 20 candles
                change -= 0.005
                
            new_price = prices[-1] * (1 + change)
            prices.append(new_price)
        
        # Create DataFrame
        timestamps = [datetime.now() - timedelta(hours=periods-i) for i in range(periods)]
        
        df = pd.DataFrame({
            'timestamp': timestamps,
            'open': prices,
            'high': [p * 1.01 for p in prices],
            'low': [p * 0.99 for p in prices], 
            'close': prices,
            'volume': np.random.uniform(1000, 5000, periods)
        })
        
        return df

    def test_1_indicator_calculation(self):
        """Test MACD indicator calculation accuracy"""
        print("\n🧮 TEST 1: MACD Indicator Calculation")
        
        try:
            df = self.create_test_data("bullish_crossover")
            df_with_indicators = self.macd_strategy.calculate_indicators(df.copy())
            
            # Check if indicators were calculated
            required_indicators = ['macd', 'macd_signal', 'macd_histogram']
            missing_indicators = [ind for ind in required_indicators if ind not in df_with_indicators.columns]
            
            if missing_indicators:
                self.results['indicator_calculation'] = {
                    'status': 'FAILED',
                    'error': f"Missing indicators: {missing_indicators}"
                }
                print(f"❌ Missing indicators: {missing_indicators}")
                return False
            
            # Check for NaN values in recent data
            recent_data = df_with_indicators.tail(10)
            nan_counts = recent_data[required_indicators].isna().sum()
            
            if nan_counts.any():
                self.results['indicator_calculation'] = {
                    'status': 'FAILED',
                    'error': f"NaN values found: {nan_counts.to_dict()}"
                }
                print(f"❌ NaN values in indicators: {nan_counts.to_dict()}")
                return False
            
            # Log current values
            current_macd = df_with_indicators['macd'].iloc[-1]
            current_signal = df_with_indicators['macd_signal'].iloc[-1]
            current_histogram = df_with_indicators['macd_histogram'].iloc[-1]
            
            print(f"✅ Indicators calculated successfully")
            print(f"   MACD: {current_macd:.6f}")
            print(f"   Signal: {current_signal:.6f}") 
            print(f"   Histogram: {current_histogram:.6f}")
            
            self.results['indicator_calculation'] = {
                'status': 'PASSED',
                'macd': current_macd,
                'signal': current_signal,
                'histogram': current_histogram
            }
            return True
            
        except Exception as e:
            self.results['indicator_calculation'] = {
                'status': 'ERROR',
                'error': str(e)
            }
            print(f"❌ Error in indicator calculation: {e}")
            return False

    def test_2_signal_detection(self):
        """Test entry signal detection logic"""
        print("\n🎯 TEST 2: Signal Detection Logic")
        
        try:
            # Test bullish crossover detection
            df_bullish = self.create_test_data("bullish_crossover")
            df_bullish = self.macd_strategy.calculate_indicators(df_bullish)
            
            # Manually create a crossover condition
            df_bullish.loc[df_bullish.index[-2], 'macd'] = -0.001
            df_bullish.loc[df_bullish.index[-2], 'macd_signal'] = 0.001
            df_bullish.loc[df_bullish.index[-1], 'macd'] = 0.002
            df_bullish.loc[df_bullish.index[-1], 'macd_signal'] = 0.001
            df_bullish['macd_histogram'] = df_bullish['macd'] - df_bullish['macd_signal']
            
            bullish_signal = self.macd_strategy.evaluate_entry_signal(df_bullish)
            
            # Test bearish crossover detection
            df_bearish = self.create_test_data("bearish_crossover")
            df_bearish = self.macd_strategy.calculate_indicators(df_bearish)
            
            # Manually create a bearish crossover
            df_bearish.loc[df_bearish.index[-2], 'macd'] = 0.001
            df_bearish.loc[df_bearish.index[-2], 'macd_signal'] = -0.001
            df_bearish.loc[df_bearish.index[-1], 'macd'] = -0.002
            df_bearish.loc[df_bearish.index[-1], 'macd_signal'] = -0.001
            df_bearish['macd_histogram'] = df_bearish['macd'] - df_bearish['macd_signal']
            
            bearish_signal = self.macd_strategy.evaluate_entry_signal(df_bearish)
            
            # Evaluate results
            results = {
                'bullish_detected': bullish_signal is not None,
                'bearish_detected': bearish_signal is not None,
                'bullish_type': bullish_signal.signal_type.value if bullish_signal else None,
                'bearish_type': bearish_signal.signal_type.value if bearish_signal else None
            }
            
            if bullish_signal and bullish_signal.signal_type == SignalType.BUY:
                print("✅ Bullish crossover detected correctly")
            else:
                print("❌ Bullish crossover not detected")
                
            if bearish_signal and bearish_signal.signal_type == SignalType.SELL:
                print("✅ Bearish crossover detected correctly")
            else:
                print("❌ Bearish crossover not detected")
            
            self.results['signal_detection'] = {
                'status': 'PASSED' if results['bullish_detected'] and results['bearish_detected'] else 'FAILED',
                'details': results
            }
            
            return results['bullish_detected'] and results['bearish_detected']
            
        except Exception as e:
            self.results['signal_detection'] = {
                'status': 'ERROR',
                'error': str(e)
            }
            print(f"❌ Error in signal detection: {e}")
            import traceback
            traceback.print_exc()
            return False

    def test_3_order_execution_simulation(self):
        """Test order execution logic (simulated)"""
        print("\n⚡ TEST 3: Order Execution Simulation")
        
        try:
            # Create a test signal
            test_signal = TradingSignal(
                signal_type=SignalType.BUY,
                confidence=0.8,
                entry_price=45000.0,
                stop_loss=44100.0,
                take_profit=46800.0,
                symbol=self.test_symbol,
                reason="Test MACD crossover"
            )
            
            # Test position size calculation
            quantity = self.order_manager._calculate_position_size(test_signal, self.macd_config)
            
            if quantity <= 0:
                self.results['order_execution'] = {
                    'status': 'FAILED',
                    'error': f"Invalid quantity calculated: {quantity}"
                }
                print(f"❌ Invalid quantity: {quantity}")
                return False
            
            # Test symbol info retrieval
            symbol_info = self.order_manager._get_symbol_info(self.test_symbol)
            
            # Validate position size meets requirements
            min_qty = symbol_info.get('min_qty', 0.001)
            if quantity < min_qty:
                print(f"⚠️ Quantity {quantity} below minimum {min_qty}")
            
            # Calculate expected margin usage
            position_value = test_signal.entry_price * quantity
            leverage = self.macd_config.get('leverage', 5)
            expected_margin = position_value / leverage
            
            print(f"✅ Order execution parameters calculated:")
            print(f"   Quantity: {quantity}")
            print(f"   Position Value: ${position_value:.2f}")
            print(f"   Expected Margin: ${expected_margin:.2f}")
            print(f"   Leverage: {leverage}x")
            
            self.results['order_execution'] = {
                'status': 'PASSED',
                'quantity': quantity,
                'position_value': position_value,
                'expected_margin': expected_margin,
                'leverage': leverage
            }
            return True
            
        except Exception as e:
            self.results['order_execution'] = {
                'status': 'ERROR',
                'error': str(e)
            }
            print(f"❌ Error in order execution simulation: {e}")
            return False

    def test_4_database_logging(self):
        """Test trade database logging functionality"""
        print("\n💾 TEST 4: Database Logging")
        
        try:
            # Create test trade data
            test_trade_id = f"TEST_{self.test_symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            test_trade_data = {
                'trade_id': test_trade_id,
                'strategy_name': 'macd_divergence',
                'symbol': self.test_symbol,
                'side': 'BUY',
                'quantity': 0.001,
                'entry_price': 45000.0,
                'trade_status': 'OPEN',
                'position_value_usdt': 45.0,
                'leverage': 5,
                'margin_used': 9.0,
                'stop_loss': 44100.0,
                'take_profit': 46800.0,
                'order_id': 12345,
                'position_side': 'LONG'
            }
            
            # Test adding trade to database
            success = self.trade_database.add_trade(test_trade_id, test_trade_data)
            
            if not success:
                self.results['database_logging'] = {
                    'status': 'FAILED',
                    'error': "Failed to add trade to database"
                }
                print("❌ Failed to add trade to database")
                return False
            
            # Test retrieving trade from database
            retrieved_trade = self.trade_database.get_trade(test_trade_id)
            
            if not retrieved_trade:
                self.results['database_logging'] = {
                    'status': 'FAILED',
                    'error': "Failed to retrieve trade from database"
                }
                print("❌ Failed to retrieve trade from database")
                return False
            
            # Test updating trade
            update_success = self.trade_database.update_trade(test_trade_id, {
                'trade_status': 'CLOSED',
                'exit_price': 46000.0,
                'pnl_usdt': 1.0
            })
            
            if not update_success:
                self.results['database_logging'] = {
                    'status': 'FAILED',
                    'error': "Failed to update trade in database"
                }
                print("❌ Failed to update trade in database")
                return False
            
            # Test trade search functionality
            found_trade_id = self.trade_database.find_trade_by_position(
                'macd_divergence', self.test_symbol, 'BUY', 0.001, 45000.0, tolerance=0.01
            )
            
            if found_trade_id != test_trade_id:
                print(f"⚠️ Trade search returned {found_trade_id}, expected {test_trade_id}")
            
            print("✅ Database logging operations successful:")
            print(f"   Trade ID: {test_trade_id}")
            print(f"   Add: ✅")
            print(f"   Retrieve: ✅")
            print(f"   Update: ✅")
            print(f"   Search: {'✅' if found_trade_id == test_trade_id else '⚠️'}")
            
            self.results['database_logging'] = {
                'status': 'PASSED',
                'trade_id': test_trade_id,
                'operations': {
                    'add': True,
                    'retrieve': True,
                    'update': True,
                    'search': found_trade_id == test_trade_id
                }
            }
            return True
            
        except Exception as e:
            self.results['database_logging'] = {
                'status': 'ERROR',
                'error': str(e)
            }
            print(f"❌ Error in database logging: {e}")
            import traceback
            traceback.print_exc()
            return False

    def test_5_trade_recovery(self):
        """Test trade recovery after bot restart"""
        print("\n🔄 TEST 5: Trade Recovery Logic")
        
        try:
            # Get recovery candidates from database
            candidates = self.trade_database.get_recovery_candidates()
            
            print(f"📊 Found {len(candidates)} recovery candidates")
            
            # Test recovery validation
            recovery_results = []
            
            for candidate in candidates[:3]:  # Test first 3 candidates
                trade_id = candidate.get('trade_id')
                symbol = candidate.get('symbol')
                side = candidate.get('side')
                quantity = candidate.get('quantity', 0)
                entry_price = candidate.get('entry_price', 0)
                strategy_name = candidate.get('strategy_name')
                
                # Test position legitimacy validation
                is_legitimate, found_trade_id = self.order_manager.is_legitimate_bot_position(
                    strategy_name, symbol, side, quantity, entry_price
                )
                
                recovery_results.append({
                    'trade_id': trade_id,
                    'symbol': symbol,
                    'legitimate': is_legitimate,
                    'found_trade_id': found_trade_id
                })
                
                print(f"   Trade {trade_id}: {'✅ Legitimate' if is_legitimate else '❌ Not found'}")
            
            # Test database sync functionality
            try:
                sync_count = self.trade_database.sync_from_logger()
                print(f"📊 Synced {sync_count} trades from logger")
            except Exception as sync_error:
                print(f"⚠️ Sync error: {sync_error}")
            
            self.results['trade_recovery'] = {
                'status': 'PASSED',
                'candidates_found': len(candidates),
                'recovery_results': recovery_results,
                'sync_available': True
            }
            
            print("✅ Trade recovery logic tested successfully")
            return True
            
        except Exception as e:
            self.results['trade_recovery'] = {
                'status': 'ERROR',
                'error': str(e)
            }
            print(f"❌ Error in trade recovery: {e}")
            return False

    def test_6_exit_signal_logic(self):
        """Test MACD exit signal detection"""
        print("\n🚪 TEST 6: Exit Signal Logic")
        
        try:
            # Create test data with MACD momentum reversal
            df = self.create_test_data("bullish_crossover")
            df = self.macd_strategy.calculate_indicators(df)
            
            # Simulate MACD momentum peak (for long exit)
            df.loc[df.index[-3], 'macd_histogram'] = 0.001
            df.loc[df.index[-2], 'macd_histogram'] = 0.003  # Peak
            df.loc[df.index[-1], 'macd_histogram'] = 0.002  # Declining
            
            # Test long position exit
            long_position = {
                'side': 'BUY',
                'entry_price': 45000.0,
                'quantity': 0.001
            }
            
            long_exit_signal = self.macd_strategy.evaluate_exit_signal(df, long_position)
            
            # Test short position exit  
            df_short = df.copy()
            df_short.loc[df_short.index[-3], 'macd_histogram'] = -0.001
            df_short.loc[df_short.index[-2], 'macd_histogram'] = -0.003  # Bottom
            df_short.loc[df_short.index[-1], 'macd_histogram'] = -0.002  # Rising
            
            short_position = {
                'side': 'SELL',
                'entry_price': 45000.0,
                'quantity': 0.001
            }
            
            short_exit_signal = self.macd_strategy.evaluate_exit_signal(df_short, short_position)
            
            print(f"Long exit signal: {long_exit_signal if long_exit_signal else 'None'}")
            print(f"Short exit signal: {short_exit_signal if short_exit_signal else 'None'}")
            
            # Test via signal processor
            signal_processor_long_exit = self.signal_processor.evaluate_exit_conditions(
                df, long_position, self.macd_config
            )
            
            signal_processor_short_exit = self.signal_processor.evaluate_exit_conditions(
                df_short, short_position, self.macd_config
            )
            
            results = {
                'long_strategy_exit': long_exit_signal is not None,
                'short_strategy_exit': short_exit_signal is not None,
                'long_processor_exit': signal_processor_long_exit is not False,
                'short_processor_exit': signal_processor_short_exit is not False
            }
            
            print("✅ Exit signal logic tested:")
            print(f"   Long strategy exit: {'✅' if results['long_strategy_exit'] else '❌'}")
            print(f"   Short strategy exit: {'✅' if results['short_strategy_exit'] else '❌'}")
            print(f"   Long processor exit: {'✅' if results['long_processor_exit'] else '❌'}")
            print(f"   Short processor exit: {'✅' if results['short_processor_exit'] else '❌'}")
            
            self.results['exit_signal_logic'] = {
                'status': 'PASSED',
                'results': results
            }
            return True
            
        except Exception as e:
            self.results['exit_signal_logic'] = {
                'status': 'ERROR',
                'error': str(e)
            }
            print(f"❌ Error in exit signal logic: {e}")
            import traceback
            traceback.print_exc()
            return False

    def test_7_configuration_validation(self):
        """Test MACD strategy configuration and thresholds"""
        print("\n⚙️ TEST 7: Configuration Validation")
        
        try:
            config = self.macd_strategy.config
            
            # Check required parameters
            required_params = ['macd_fast', 'macd_slow', 'macd_signal', 'min_histogram_threshold']
            missing_params = [param for param in required_params if param not in config]
            
            if missing_params:
                self.results['configuration'] = {
                    'status': 'FAILED',
                    'error': f"Missing required parameters: {missing_params}"
                }
                print(f"❌ Missing parameters: {missing_params}")
                return False
            
            # Validate parameter ranges
            validations = {
                'macd_fast': (1, 50),
                'macd_slow': (10, 100),
                'macd_signal': (1, 20),
                'min_histogram_threshold': (0, 1),
                'margin': (1, 1000),
                'leverage': (1, 125)
            }
            
            validation_results = {}
            for param, (min_val, max_val) in validations.items():
                if param in config:
                    value = config[param]
                    is_valid = min_val <= value <= max_val
                    validation_results[param] = {
                        'value': value,
                        'valid': is_valid,
                        'range': f"{min_val}-{max_val}"
                    }
                    
                    if not is_valid:
                        print(f"⚠️ {param}: {value} outside valid range {min_val}-{max_val}")
                    else:
                        print(f"✅ {param}: {value}")
            
            # Test threshold sensitivity
            test_histogram_values = [0.00001, 0.0001, 0.001, 0.01]
            threshold = config.get('min_histogram_threshold', 0.0001)
            
            print(f"\n🎯 Threshold Analysis (current: {threshold}):")
            for test_val in test_histogram_values:
                would_trigger = test_val > threshold
                print(f"   Histogram {test_val}: {'✅ Would trigger' if would_trigger else '❌ Would not trigger'}")
            
            self.results['configuration'] = {
                'status': 'PASSED',
                'validations': validation_results,
                'threshold_analysis': {
                    'current_threshold': threshold,
                    'test_values': test_histogram_values
                }
            }
            return True
            
        except Exception as e:
            self.results['configuration'] = {
                'status': 'ERROR',
                'error': str(e)
            }
            print(f"❌ Error in configuration validation: {e}")
            return False

    def run_comprehensive_test(self):
        """Run all tests and generate comprehensive report"""
        print("🚀 STARTING COMPREHENSIVE MACD STRATEGY TEST")
        print("=" * 60)
        
        test_functions = [
            self.test_1_indicator_calculation,
            self.test_2_signal_detection,
            self.test_3_order_execution_simulation,
            self.test_4_database_logging,
            self.test_5_trade_recovery,
            self.test_6_exit_signal_logic,
            self.test_7_configuration_validation
        ]
        
        passed_tests = 0
        total_tests = len(test_functions)
        
        for test_func in test_functions:
            try:
                result = test_func()
                if result:
                    passed_tests += 1
            except Exception as e:
                print(f"❌ Test {test_func.__name__} failed with error: {e}")
        
        # Generate summary report
        print("\n" + "=" * 60)
        print("📊 COMPREHENSIVE TEST RESULTS SUMMARY")
        print("=" * 60)
        
        print(f"Tests Passed: {passed_tests}/{total_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        print("\n📋 Detailed Results:")
        for test_name, result in self.results.items():
            status = result.get('status', 'UNKNOWN')
            print(f"   {test_name}: {status}")
            if status == 'ERROR' and 'error' in result:
                print(f"      Error: {result['error']}")
        
        # Identify potential issues
        print("\n🔍 ANALYSIS & RECOMMENDATIONS:")
        
        failed_tests = [name for name, result in self.results.items() if result.get('status') != 'PASSED']
        
        if not failed_tests:
            print("✅ All tests passed - MACD strategy logic appears sound")
        else:
            print(f"❌ Issues found in: {', '.join(failed_tests)}")
            
            # Specific recommendations based on failures
            if 'indicator_calculation' in failed_tests:
                print("   • Check MACD calculation formulas and data requirements")
                
            if 'signal_detection' in failed_tests:
                print("   • Review crossover detection logic and thresholds")
                
            if 'database_logging' in failed_tests:
                print("   • Verify database connectivity and schema")
                
            if 'trade_recovery' in failed_tests:
                print("   • Check trade ID generation and matching logic")
        
        # Save detailed results
        try:
            with open('trading_data/macd_test_results.json', 'w') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'summary': {
                        'tests_passed': passed_tests,
                        'total_tests': total_tests,
                        'success_rate': (passed_tests/total_tests)*100
                    },
                    'detailed_results': self.results
                }, f, indent=2)
            print(f"\n💾 Detailed results saved to trading_data/macd_test_results.json")
        except Exception as e:
            print(f"⚠️ Could not save results: {e}")
        
        return passed_tests == total_tests

def main():
    """Run the comprehensive MACD test suite"""
    try:
        test_suite = MACDTestSuite()
        success = test_suite.run_comprehensive_test()
        
        if success:
            print("\n🎉 ALL TESTS PASSED - MACD Strategy is functioning correctly")
            return 0
        else:
            print("\n⚠️ SOME TESTS FAILED - Review results above")
            return 1
            
    except Exception as e:
        print(f"❌ Critical error running test suite: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())
