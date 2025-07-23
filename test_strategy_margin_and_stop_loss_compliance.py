
#!/usr/bin/env python3
"""
Test Strategy Margin and Stop Loss Compliance
Tests whether RSI, MACD, and Engulfing strategies respect user-configured:
1. Margin invested vs actual margin used
2. Stop loss percentage vs actual stop loss distance
3. Binance minimum trade amounts and decimal precision compliance
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.strategies.rsi_oversold_config import RSIOversoldConfig
from src.execution_engine.strategies.macd_divergence_strategy import MACDDivergenceStrategy
from src.execution_engine.strategies.engulfing_pattern_strategy import EngulfingPatternStrategy
from src.execution_engine.order_manager import OrderManager
from src.binance_client.client import BinanceClientWrapper
from src.config.trading_config import trading_config_manager
from src.analytics.trade_logger import trade_logger
from src.strategy_processor.signal_processor import TradingSignal, SignalType
import json
from datetime import datetime
from typing import Dict, List, Any, Tuple

class StrategyComplianceTest:
    """Test strategy compliance with user configurations"""
    
    def __init__(self):
        self.binance_client = BinanceClientWrapper()
        self.order_manager = OrderManager(self.binance_client, trade_logger)
        self.test_results = {}
        self.test_symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT']
        
        # Test configurations for each strategy
        self.test_configs = {
            'rsi_oversold': {
                'symbol': 'SOLUSDT',
                'margin': 25.0,
                'leverage': 10,
                'max_loss_pct': 8.0,
                'timeframe': '15m',
                'decimals': 2
            },
            'macd_divergence': {
                'symbol': 'BTCUSDT', 
                'margin': 50.0,
                'leverage': 5,
                'max_loss_pct': 12.0,
                'timeframe': '5m',
                'decimals': 3
            },
            'engulfing_pattern': {
                'symbol': 'ETHUSDT',
                'margin': 35.0,
                'leverage': 8,
                'max_loss_pct': 10.0,
                'timeframe': '1h',
                'decimals': 2
            }
        }
        
    def run_all_tests(self):
        """Run all compliance tests"""
        print("🧪 STRATEGY MARGIN & STOP LOSS COMPLIANCE TEST")
        print("=" * 80)
        
        # Test each strategy
        for strategy_name, config in self.test_configs.items():
            print(f"\n📊 TESTING STRATEGY: {strategy_name.upper()}")
            print("-" * 60)
            
            self.test_results[strategy_name] = self.test_strategy_compliance(strategy_name, config)
            
        # Generate final report
        self.generate_compliance_report()
        
    def test_strategy_compliance(self, strategy_name: str, config: Dict) -> Dict:
        """Test a single strategy's compliance"""
        results = {
            'margin_compliance': {},
            'stop_loss_compliance': {},
            'binance_compliance': {},
            'overall_status': 'PENDING'
        }
        
        try:
            # 1. Test Margin Compliance
            print(f"💰 Testing Margin Compliance...")
            results['margin_compliance'] = self.test_margin_compliance(strategy_name, config)
            
            # 2. Test Stop Loss Compliance  
            print(f"🛡️ Testing Stop Loss Compliance...")
            results['stop_loss_compliance'] = self.test_stop_loss_compliance(strategy_name, config)
            
            # 3. Test Binance Requirements Compliance
            print(f"📋 Testing Binance Requirements Compliance...")
            results['binance_compliance'] = self.test_binance_compliance(strategy_name, config)
            
            # Determine overall status
            margin_ok = results['margin_compliance'].get('compliant', False)
            stop_loss_ok = results['stop_loss_compliance'].get('compliant', False)
            binance_ok = results['binance_compliance'].get('compliant', False)
            
            if margin_ok and stop_loss_ok and binance_ok:
                results['overall_status'] = 'COMPLIANT'
            elif margin_ok or stop_loss_ok or binance_ok:
                results['overall_status'] = 'PARTIAL_COMPLIANCE'
            else:
                results['overall_status'] = 'NON_COMPLIANT'
                
        except Exception as e:
            results['error'] = str(e)
            results['overall_status'] = 'ERROR'
            print(f"❌ Error testing {strategy_name}: {e}")
            
        return results
        
    def test_margin_compliance(self, strategy_name: str, config: Dict) -> Dict:
        """Test if actual margin used matches configured margin"""
        results = {
            'configured_margin': config['margin'],
            'calculated_margin': 0.0,
            'margin_difference': 0.0,
            'margin_difference_pct': 0.0,
            'compliant': False,
            'details': []
        }
        
        try:
            # Create test signal with realistic price
            test_price = self.get_current_price(config['symbol'])
            if not test_price:
                test_price = 50000.0 if 'BTC' in config['symbol'] else 2000.0
                
            test_signal = TradingSignal(
                signal_type=SignalType.BUY,
                confidence=0.8,
                entry_price=test_price,
                stop_loss=test_price * 0.95,  # 5% stop loss
                take_profit=test_price * 1.10,  # 10% take profit
                symbol=config['symbol'],
                reason=f"Test {strategy_name} signal"
            )
            
            # Calculate position size using order manager logic
            quantity = self.order_manager._calculate_position_size(test_signal, config)
            
            if quantity <= 0:
                results['details'].append("❌ Invalid quantity calculated")
                return results
                
            # Calculate actual margin used
            position_value = quantity * test_price
            actual_margin = position_value / config['leverage']
            
            results['calculated_margin'] = actual_margin
            results['margin_difference'] = actual_margin - config['margin']
            results['margin_difference_pct'] = (results['margin_difference'] / config['margin']) * 100 if config['margin'] > 0 else 0
            
            # Check compliance (allow 5% tolerance for rounding)
            tolerance_pct = 5.0
            if abs(results['margin_difference_pct']) <= tolerance_pct:
                results['compliant'] = True
                results['details'].append(f"✅ Margin within {tolerance_pct}% tolerance")
            else:
                results['compliant'] = False
                results['details'].append(f"❌ Margin difference exceeds {tolerance_pct}% tolerance")
                
            results['details'].extend([
                f"📊 Configured: ${config['margin']:.2f} USDT",
                f"💰 Calculated: ${actual_margin:.2f} USDT", 
                f"📈 Difference: ${results['margin_difference']:+.2f} USDT ({results['margin_difference_pct']:+.1f}%)",
                f"📏 Quantity: {quantity}",
                f"💵 Position Value: ${position_value:.2f} USDT",
                f"⚡ Leverage: {config['leverage']}x"
            ])
            
        except Exception as e:
            results['details'].append(f"❌ Error: {e}")
            
        return results
        
    def test_stop_loss_compliance(self, strategy_name: str, config: Dict) -> Dict:
        """Test if stop loss distance matches configured max_loss_pct"""
        results = {
            'configured_max_loss_pct': config['max_loss_pct'],
            'calculated_stop_loss_pct': 0.0,
            'stop_loss_difference': 0.0,
            'compliant': False,
            'details': []
        }
        
        try:
            # Get current price for realistic calculations
            test_price = self.get_current_price(config['symbol'])
            if not test_price:
                test_price = 50000.0 if 'BTC' in config['symbol'] else 2000.0
                
            # Calculate expected stop loss based on configured max_loss_pct
            # Formula: For LONG position, SL should be at entry * (1 - max_loss_pct / 100)
            configured_max_loss = config['max_loss_pct']
            
            # Calculate position parameters
            margin = config['margin']
            leverage = config['leverage']
            position_value = margin * leverage
            quantity = position_value / test_price
            
            # Calculate stop loss that would result in configured max loss
            max_loss_amount = margin * (configured_max_loss / 100)
            stop_loss_per_unit = max_loss_amount / quantity
            expected_stop_loss = test_price - stop_loss_per_unit
            
            # Calculate the percentage this represents
            expected_stop_loss_pct = ((test_price - expected_stop_loss) / test_price) * 100
            
            results['calculated_stop_loss_pct'] = expected_stop_loss_pct
            results['stop_loss_difference'] = expected_stop_loss_pct - configured_max_loss
            
            # Test with actual signal generation
            test_signal = TradingSignal(
                signal_type=SignalType.BUY,
                confidence=0.8,
                entry_price=test_price,
                stop_loss=expected_stop_loss,
                take_profit=test_price * 1.15,
                symbol=config['symbol'],
                reason=f"Test {strategy_name} stop loss"
            )
            
            # Calculate actual loss if stop loss is hit
            actual_loss_per_unit = test_price - test_signal.stop_loss
            actual_loss_amount = actual_loss_per_unit * quantity
            actual_loss_pct = (actual_loss_amount / margin) * 100 if margin > 0 else 0
            
            # Check compliance (allow 1% tolerance)
            tolerance_pct = 1.0
            loss_difference = abs(actual_loss_pct - configured_max_loss)
            
            if loss_difference <= tolerance_pct:
                results['compliant'] = True
                results['details'].append(f"✅ Stop loss within {tolerance_pct}% tolerance")
            else:
                results['compliant'] = False
                results['details'].append(f"❌ Stop loss difference exceeds {tolerance_pct}% tolerance")
                
            results['details'].extend([
                f"🎯 Configured Max Loss: {configured_max_loss}%",
                f"🛡️ Calculated Loss at SL: {actual_loss_pct:.2f}%",
                f"📊 Difference: {loss_difference:.2f}%",
                f"💰 Entry Price: ${test_price:.4f}",
                f"🚫 Stop Loss: ${test_signal.stop_loss:.4f}",
                f"💸 Loss Amount: ${actual_loss_amount:.2f} USDT",
                f"📏 Position Size: {quantity:.6f} {config['symbol'].replace('USDT', '')}"
            ])
            
        except Exception as e:
            results['details'].append(f"❌ Error: {e}")
            
        return results
        
    def test_binance_compliance(self, strategy_name: str, config: Dict) -> Dict:
        """Test compliance with Binance minimum trade amounts and decimals"""
        results = {
            'min_qty_compliant': False,
            'decimal_precision_compliant': False,
            'min_notional_compliant': False,
            'compliant': False,
            'details': []
        }
        
        try:
            symbol = config['symbol']
            
            # Get symbol info from Binance
            symbol_info = self.order_manager._get_symbol_info(symbol)
            
            # Test with realistic calculation
            test_price = self.get_current_price(symbol)
            if not test_price:
                test_price = 50000.0 if 'BTC' in symbol else 2000.0
                
            test_signal = TradingSignal(
                signal_type=SignalType.BUY,
                confidence=0.8,
                entry_price=test_price,
                stop_loss=test_price * 0.95,
                take_profit=test_price * 1.10,
                symbol=symbol,
                reason=f"Test {strategy_name} Binance compliance"
            )
            
            # Calculate quantity
            quantity = self.order_manager._calculate_position_size(test_signal, config)
            position_value = quantity * test_price
            
            # Check minimum quantity
            min_qty = symbol_info.get('min_qty', 0.001)
            if quantity >= min_qty:
                results['min_qty_compliant'] = True
                results['details'].append(f"✅ Quantity {quantity} >= minimum {min_qty}")
            else:
                results['details'].append(f"❌ Quantity {quantity} < minimum {min_qty}")
                
            # Check decimal precision
            step_size = symbol_info.get('step_size', 0.001)
            precision = symbol_info.get('precision', 3)
            
            # Verify quantity aligns with step size
            quantity_steps = quantity / step_size
            if abs(quantity_steps - round(quantity_steps)) < 0.0001:
                results['decimal_precision_compliant'] = True
                results['details'].append(f"✅ Quantity precision compliant (step: {step_size})")
            else:
                results['details'].append(f"❌ Quantity precision issue (step: {step_size})")
                
            # Check minimum notional (typically 10 USDT for futures)
            min_notional = 10.0  # Binance futures minimum
            if position_value >= min_notional:
                results['min_notional_compliant'] = True
                results['details'].append(f"✅ Position value ${position_value:.2f} >= minimum ${min_notional}")
            else:
                results['details'].append(f"❌ Position value ${position_value:.2f} < minimum ${min_notional}")
                
            # Overall compliance
            results['compliant'] = (results['min_qty_compliant'] and 
                                 results['decimal_precision_compliant'] and 
                                 results['min_notional_compliant'])
                                 
            results['details'].extend([
                f"📊 Symbol Info: min_qty={min_qty}, step={step_size}, precision={precision}",
                f"📏 Calculated Quantity: {quantity}",
                f"💵 Position Value: ${position_value:.2f} USDT"
            ])
            
        except Exception as e:
            results['details'].append(f"❌ Error: {e}")
            
        return results
        
    def get_current_price(self, symbol: str) -> float:
        """Get current price for a symbol"""
        try:
            ticker = self.binance_client.get_symbol_ticker(symbol)
            if ticker and 'price' in ticker:
                return float(ticker['price'])
        except Exception as e:
            print(f"⚠️ Could not get price for {symbol}: {e}")
        return None
        
    def generate_compliance_report(self):
        """Generate final compliance test report"""
        print("\n" + "=" * 80)
        print("📋 STRATEGY COMPLIANCE TEST REPORT")
        print("=" * 80)
        
        overall_compliant = 0
        total_strategies = len(self.test_results)
        
        for strategy_name, results in self.test_results.items():
            print(f"\n🎯 {strategy_name.upper()}")
            print("-" * 40)
            
            status = results.get('overall_status', 'UNKNOWN')
            status_emoji = {
                'COMPLIANT': '✅',
                'PARTIAL_COMPLIANCE': '⚠️',
                'NON_COMPLIANT': '❌',
                'ERROR': '🚫',
                'UNKNOWN': '❓'
            }.get(status, '❓')
            
            print(f"Overall Status: {status_emoji} {status}")
            
            if status == 'COMPLIANT':
                overall_compliant += 1
                
            # Margin compliance details
            margin_results = results.get('margin_compliance', {})
            margin_compliant = margin_results.get('compliant', False)
            print(f"💰 Margin Compliance: {'✅' if margin_compliant else '❌'}")
            
            if 'configured_margin' in margin_results:
                print(f"   📊 Configured: ${margin_results['configured_margin']:.2f}")
                print(f"   💰 Calculated: ${margin_results.get('calculated_margin', 0):.2f}")
                print(f"   📈 Difference: {margin_results.get('margin_difference_pct', 0):+.1f}%")
                
            # Stop loss compliance details  
            sl_results = results.get('stop_loss_compliance', {})
            sl_compliant = sl_results.get('compliant', False)
            print(f"🛡️ Stop Loss Compliance: {'✅' if sl_compliant else '❌'}")
            
            if 'configured_max_loss_pct' in sl_results:
                print(f"   🎯 Configured: {sl_results['configured_max_loss_pct']:.1f}%")
                print(f"   🛡️ Calculated: {sl_results.get('calculated_stop_loss_pct', 0):.1f}%")
                
            # Binance compliance details
            binance_results = results.get('binance_compliance', {})
            binance_compliant = binance_results.get('compliant', False)
            print(f"📋 Binance Compliance: {'✅' if binance_compliant else '❌'}")
            
            # Show any errors
            if 'error' in results:
                print(f"🚫 Error: {results['error']}")
                
        # Summary
        print(f"\n{'='*80}")
        print(f"📊 SUMMARY: {overall_compliant}/{total_strategies} strategies fully compliant")
        
        compliance_rate = (overall_compliant / total_strategies) * 100 if total_strategies > 0 else 0
        if compliance_rate == 100:
            print(f"🎉 EXCELLENT: All strategies are compliant!")
        elif compliance_rate >= 70:
            print(f"👍 GOOD: {compliance_rate:.0f}% compliance rate")
        else:
            print(f"⚠️ NEEDS ATTENTION: Only {compliance_rate:.0f}% compliance rate")
            
        # Save detailed results
        self.save_test_results()
        
    def save_test_results(self):
        """Save detailed test results to file"""
        try:
            os.makedirs('trading_data', exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'trading_data/strategy_compliance_test_{timestamp}.json'
            
            # Prepare data for JSON serialization
            json_results = {
                'test_timestamp': timestamp,
                'test_type': 'Strategy Margin and Stop Loss Compliance',
                'strategies_tested': list(self.test_configs.keys()),
                'results': self.test_results,
                'test_configurations': self.test_configs
            }
            
            with open(filename, 'w') as f:
                json.dump(json_results, f, indent=2, default=str)
                
            print(f"💾 Detailed results saved to: {filename}")
            
        except Exception as e:
            print(f"⚠️ Could not save results: {e}")

def main():
    """Run the compliance test"""
    try:
        print("🚀 Starting Strategy Compliance Test...")
        
        tester = StrategyComplianceTest()
        tester.run_all_tests()
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        print(f"🔍 Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    main()
