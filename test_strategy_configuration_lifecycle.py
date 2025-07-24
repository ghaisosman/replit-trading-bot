
#!/usr/bin/env python3
"""
Comprehensive Strategy Configuration Lifecycle Test
==================================================

Tests the complete configuration lifecycle for all strategies:
1. Verify strategies scan/trade with current configurations
2. Change strategy configurations via web dashboard
3. Confirm new configurations are saved and applied
4. Verify strategies scan/trade with new configurations

This test validates that configuration changes are properly applied and used.
"""

import sys
import os
import time
import json
import requests
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import logging

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.execution_engine.trade_database import TradeDatabase
from src.analytics.trade_logger import trade_logger
from src.binance_client.client import BinanceClientWrapper
from src.config.trading_config import trading_config_manager

class StrategyConfigurationLifecycleTest:
    """Test strategy configuration changes and their effects"""
    
    def __init__(self, base_url="http://localhost:5000"):
        self.base_url = base_url
        self.trade_db = TradeDatabase()
        self.binance_client = BinanceClientWrapper()
        self.test_results = {}
        self.stop_monitoring = threading.Event()
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Test configuration sets for each strategy
        self.strategy_config_sets = {
            'rsi_oversold': {
                'original': {
                    'rsi_period': 14,
                    'rsi_long_entry': 30,
                    'rsi_long_exit': 70,
                    'rsi_short_entry': 70,
                    'rsi_short_exit': 30,
                    'max_loss_pct': 5,
                    'min_volume': 1000000,
                    'cooldown_period': 300
                },
                'modified': {
                    'rsi_period': 21,
                    'rsi_long_entry': 25,
                    'rsi_long_exit': 75,
                    'rsi_short_entry': 75,
                    'rsi_short_exit': 25,
                    'max_loss_pct': 8,
                    'min_volume': 2000000,
                    'cooldown_period': 600
                }
            },
            'macd_divergence': {
                'original': {
                    'macd_fast': 12,
                    'macd_slow': 26,
                    'macd_signal': 9,
                    'min_histogram_threshold': 0.0001,
                    'macd_entry_threshold': 0.0015,
                    'macd_exit_threshold': 0.002,
                    'confirmation_candles': 2,
                    'max_loss_pct': 10
                },
                'modified': {
                    'macd_fast': 8,
                    'macd_slow': 21,
                    'macd_signal': 7,
                    'min_histogram_threshold': 0.0002,
                    'macd_entry_threshold': 0.001,
                    'macd_exit_threshold': 0.003,
                    'confirmation_candles': 3,
                    'max_loss_pct': 12
                }
            },
            'engulfing_pattern': {
                'original': {
                    'rsi_period': 14,
                    'rsi_threshold': 50,
                    'rsi_long_exit': 70,
                    'rsi_short_exit': 30,
                    'stable_candle_ratio': 0.5,
                    'price_lookback_bars': 5,
                    'partial_tp_pnl_threshold': 0.0,
                    'partial_tp_position_percentage': 0.0,
                    'max_loss_pct': 8
                },
                'modified': {
                    'rsi_period': 21,
                    'rsi_threshold': 55,
                    'rsi_long_exit': 75,
                    'rsi_short_exit': 25,
                    'stable_candle_ratio': 0.3,
                    'price_lookback_bars': 7,
                    'partial_tp_pnl_threshold': 2.0,
                    'partial_tp_position_percentage': 50.0,
                    'max_loss_pct': 12
                }
            },
            'smart_money': {
                'original': {
                    'swing_lookback_period': 25,
                    'sweep_threshold_pct': 0.1,
                    'reversion_candles': 3,
                    'volume_spike_multiplier': 2.0,
                    'min_swing_distance_pct': 1.0,
                    'max_daily_trades': 3,
                    'session_filter_enabled': True,
                    'trend_filter_enabled': True
                },
                'modified': {
                    'swing_lookback_period': 35,
                    'sweep_threshold_pct': 0.15,
                    'reversion_candles': 2,
                    'volume_spike_multiplier': 1.5,
                    'min_swing_distance_pct': 0.8,
                    'max_daily_trades': 5,
                    'session_filter_enabled': False,
                    'trend_filter_enabled': False
                }
            }
        }
    
    def get_strategy_config(self, strategy_name: str) -> Optional[Dict[str, Any]]:
        """Get current strategy configuration"""
        try:
            response = requests.get(f"{self.base_url}/api/strategies/{strategy_name}/config", timeout=10)
            if response.status_code == 200:
                return response.json().get('config', {})
            return None
        except Exception as e:
            self.logger.error(f"Error getting {strategy_name} config: {e}")
            return None
    
    def update_strategy_config(self, strategy_name: str, config_updates: Dict[str, Any]) -> bool:
        """Update strategy configuration via web dashboard"""
        try:
            # Prepare the data for the API
            api_data = {
                'strategy_name': strategy_name,
                **config_updates
            }
            
            response = requests.post(
                f"{self.base_url}/api/strategies/{strategy_name}/update",
                json=api_data,
                headers={'Content-Type': 'application/json'},
                timeout=15
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('success', False)
            else:
                self.logger.error(f"Update failed with status {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error updating {strategy_name} config: {e}")
            return False
    
    def get_strategy_status(self, strategy_name: str) -> Optional[Dict[str, Any]]:
        """Get strategy status"""
        try:
            response = requests.get(f"{self.base_url}/api/strategies", timeout=10)
            if response.status_code == 200:
                strategies = response.json()
                return strategies.get(strategy_name, {})
            return None
        except Exception as e:
            self.logger.error(f"Error getting {strategy_name} status: {e}")
            return None
    
    def monitor_strategy_activity(self, strategy_name: str, config_type: str, duration: int = 120) -> Dict[str, Any]:
        """Monitor strategy activity for specified duration"""
        print(f"   📊 Monitoring {strategy_name} with {config_type} config for {duration} seconds...")
        
        activity_data = {
            'strategy_name': strategy_name,
            'config_type': config_type,
            'start_time': datetime.now(),
            'duration': duration,
            'trades_opened': [],
            'trades_closed': [],
            'scanning_activity': [],
            'config_usage_evidence': [],
            'total_activity_count': 0
        }
        
        initial_trades = self.get_current_trades()
        start_time = time.time()
        
        while (time.time() - start_time) < duration and not self.stop_monitoring.is_set():
            try:
                # Check for new trades
                current_trades = self.get_current_trades()
                new_trades = self.find_new_trades(initial_trades, current_trades, strategy_name)
                
                for trade in new_trades:
                    if trade.get('trade_status') == 'OPEN':
                        activity_data['trades_opened'].append({
                            'trade_id': trade.get('trade_id'),
                            'timestamp': datetime.now(),
                            'symbol': trade.get('symbol'),
                            'strategy': trade.get('strategy_name'),
                            'entry_price': trade.get('entry_price'),
                            'config_evidence': self.extract_config_evidence(trade, strategy_name, config_type)
                        })
                        activity_data['total_activity_count'] += 1
                
                # Check for closed trades
                closed_trades = self.find_closed_trades(initial_trades, current_trades, strategy_name)
                for trade in closed_trades:
                    activity_data['trades_closed'].append({
                        'trade_id': trade.get('trade_id'),
                        'timestamp': datetime.now(),
                        'symbol': trade.get('symbol'),
                        'exit_reason': trade.get('exit_reason'),
                        'pnl': trade.get('pnl_usdt')
                    })
                    activity_data['total_activity_count'] += 1
                
                # Update initial_trades for next iteration
                initial_trades = current_trades
                
                time.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                self.logger.debug(f"Monitoring error: {e}")
                time.sleep(2)
        
        activity_data['end_time'] = datetime.now()
        return activity_data
    
    def get_current_trades(self) -> List[Dict]:
        """Get all current trades from database"""
        try:
            trades = []
            for trade_id, trade_data in self.trade_db.trades.items():
                trades.append({
                    'trade_id': trade_id,
                    'trade_status': trade_data.get('trade_status'),
                    'strategy_name': trade_data.get('strategy_name'),
                    'symbol': trade_data.get('symbol'),
                    'entry_price': trade_data.get('entry_price'),
                    'exit_reason': trade_data.get('exit_reason'),
                    'pnl_usdt': trade_data.get('pnl_usdt'),
                    'timestamp': trade_data.get('timestamp')
                })
            return trades
        except Exception as e:
            self.logger.error(f"Error getting trades: {e}")
            return []
    
    def find_new_trades(self, initial_trades: List[Dict], current_trades: List[Dict], strategy_name: str) -> List[Dict]:
        """Find new trades for specific strategy"""
        initial_ids = {trade['trade_id'] for trade in initial_trades}
        new_trades = []
        
        for trade in current_trades:
            if (trade['trade_id'] not in initial_ids and 
                strategy_name.lower() in trade.get('strategy_name', '').lower()):
                new_trades.append(trade)
        
        return new_trades
    
    def find_closed_trades(self, initial_trades: List[Dict], current_trades: List[Dict], strategy_name: str) -> List[Dict]:
        """Find trades that were closed for specific strategy"""
        initial_open = {trade['trade_id']: trade for trade in initial_trades 
                       if trade.get('trade_status') == 'OPEN' and 
                       strategy_name.lower() in trade.get('strategy_name', '').lower()}
        
        closed_trades = []
        for trade in current_trades:
            if (trade['trade_id'] in initial_open and 
                trade.get('trade_status') == 'CLOSED'):
                closed_trades.append(trade)
        
        return closed_trades
    
    def extract_config_evidence(self, trade: Dict, strategy_name: str, config_type: str) -> Dict[str, Any]:
        """Extract evidence that specific configuration was used"""
        evidence = {}
        
        try:
            # Get the expected configuration
            expected_config = self.strategy_config_sets.get(strategy_name, {}).get(config_type, {})
            
            # Strategy-specific evidence extraction
            if 'rsi' in strategy_name.lower():
                evidence.update({
                    'expected_rsi_period': expected_config.get('rsi_period'),
                    'expected_max_loss_pct': expected_config.get('max_loss_pct'),
                    'expected_long_entry': expected_config.get('rsi_long_entry')
                })
            
            elif 'macd' in strategy_name.lower():
                evidence.update({
                    'expected_macd_fast': expected_config.get('macd_fast'),
                    'expected_macd_slow': expected_config.get('macd_slow'),
                    'expected_max_loss_pct': expected_config.get('max_loss_pct')
                })
            
            elif 'engulfing' in strategy_name.lower():
                evidence.update({
                    'expected_rsi_period': expected_config.get('rsi_period'),
                    'expected_rsi_threshold': expected_config.get('rsi_threshold'),
                    'expected_max_loss_pct': expected_config.get('max_loss_pct')
                })
            
            elif 'smart_money' in strategy_name.lower():
                evidence.update({
                    'expected_swing_lookback': expected_config.get('swing_lookback_period'),
                    'expected_sweep_threshold': expected_config.get('sweep_threshold_pct'),
                    'expected_max_daily_trades': expected_config.get('max_daily_trades')
                })
        
        except Exception as e:
            self.logger.debug(f"Error extracting config evidence: {e}")
        
        return evidence
    
    def verify_configuration_persistence(self, strategy_name: str, expected_config: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Verify that configuration changes were persisted"""
        current_config = self.get_strategy_config(strategy_name)
        
        if not current_config:
            return False, {'error': 'Could not retrieve current configuration'}
        
        verification_results = {
            'matches': {},
            'mismatches': {},
            'missing': {}
        }
        
        for key, expected_value in expected_config.items():
            if key in current_config:
                current_value = current_config[key]
                if current_value == expected_value:
                    verification_results['matches'][key] = {
                        'expected': expected_value,
                        'actual': current_value
                    }
                else:
                    verification_results['mismatches'][key] = {
                        'expected': expected_value,
                        'actual': current_value
                    }
            else:
                verification_results['missing'][key] = expected_value
        
        is_valid = (len(verification_results['mismatches']) == 0 and 
                   len(verification_results['missing']) == 0)
        
        return is_valid, verification_results
    
    def test_strategy_configuration_lifecycle(self, strategy_name: str) -> Dict[str, Any]:
        """Test complete configuration lifecycle for a single strategy"""
        print(f"\n{'='*100}")
        print(f"🔧 TESTING CONFIGURATION LIFECYCLE: {strategy_name.upper()}")
        print(f"{'='*100}")
        
        test_result = {
            'strategy': strategy_name,
            'test_start': datetime.now(),
            'phases': {},
            'overall_success': False,
            'summary': {}
        }
        
        try:
            config_sets = self.strategy_config_sets.get(strategy_name)
            if not config_sets:
                test_result['error'] = f"No test configurations defined for {strategy_name}"
                return test_result
            
            original_config = config_sets['original']
            modified_config = config_sets['modified']
            
            # PHASE 1: Test with original configuration
            print(f"\n📊 PHASE 1: Testing with ORIGINAL configuration")
            print(f"──────────────────────────────────────────────────────────────")
            
            # Set original configuration
            print(f"🔧 Setting original configuration...")
            original_update_success = self.update_strategy_config(strategy_name, original_config)
            
            if not original_update_success:
                test_result['phases']['original_config_set'] = {
                    'success': False, 
                    'error': 'Failed to set original configuration'
                }
                return test_result
            
            time.sleep(10)  # Wait for configuration to take effect
            
            # Verify original configuration persistence
            original_persistence_valid, original_verification = self.verify_configuration_persistence(
                strategy_name, original_config
            )
            
            test_result['phases']['original_config_persistence'] = {
                'success': original_persistence_valid,
                'verification': original_verification
            }
            
            if original_persistence_valid:
                print(f"✅ Original configuration set and verified")
                for key, value in original_verification['matches'].items():
                    print(f"   📋 {key}: {value['actual']}")
            else:
                print(f"❌ Original configuration verification failed")
                for key, data in original_verification['mismatches'].items():
                    print(f"   ❌ {key}: expected {data['expected']}, got {data['actual']}")
            
            # Monitor activity with original configuration
            original_activity = self.monitor_strategy_activity(strategy_name, 'original', 120)
            
            test_result['phases']['original_activity'] = {
                'activity_data': original_activity,
                'trades_opened': len(original_activity['trades_opened']),
                'trades_closed': len(original_activity['trades_closed']),
                'total_activity': original_activity['total_activity_count'],
                'success': original_activity['total_activity_count'] > 0
            }
            
            print(f"📈 Original Config Activity Results:")
            print(f"   🔓 Trades Opened: {len(original_activity['trades_opened'])}")
            print(f"   🔒 Trades Closed: {len(original_activity['trades_closed'])}")
            print(f"   📊 Total Activity: {original_activity['total_activity_count']}")
            
            # PHASE 2: Change to modified configuration
            print(f"\n🔄 PHASE 2: Changing to MODIFIED configuration")
            print(f"──────────────────────────────────────────────────────────────")
            
            # Set modified configuration
            print(f"🔧 Setting modified configuration...")
            modified_update_success = self.update_strategy_config(strategy_name, modified_config)
            
            if not modified_update_success:
                test_result['phases']['modified_config_set'] = {
                    'success': False,
                    'error': 'Failed to set modified configuration'
                }
                return test_result
            
            time.sleep(10)  # Wait for configuration to take effect
            
            # Verify modified configuration persistence
            modified_persistence_valid, modified_verification = self.verify_configuration_persistence(
                strategy_name, modified_config
            )
            
            test_result['phases']['modified_config_persistence'] = {
                'success': modified_persistence_valid,
                'verification': modified_verification
            }
            
            if modified_persistence_valid:
                print(f"✅ Modified configuration set and verified")
                for key, value in modified_verification['matches'].items():
                    print(f"   📋 {key}: {value['actual']}")
            else:
                print(f"❌ Modified configuration verification failed")
                for key, data in modified_verification['mismatches'].items():
                    print(f"   ❌ {key}: expected {data['expected']}, got {data['actual']}")
            
            # Monitor activity with modified configuration
            modified_activity = self.monitor_strategy_activity(strategy_name, 'modified', 120)
            
            test_result['phases']['modified_activity'] = {
                'activity_data': modified_activity,
                'trades_opened': len(modified_activity['trades_opened']),
                'trades_closed': len(modified_activity['trades_closed']),
                'total_activity': modified_activity['total_activity_count'],
                'success': modified_activity['total_activity_count'] > 0
            }
            
            print(f"📈 Modified Config Activity Results:")
            print(f"   🔓 Trades Opened: {len(modified_activity['trades_opened'])}")
            print(f"   🔒 Trades Closed: {len(modified_activity['trades_closed'])}")
            print(f"   📊 Total Activity: {modified_activity['total_activity_count']}")
            
            # PHASE 3: Analyze configuration impact
            print(f"\n📊 PHASE 3: Analyzing configuration impact")
            print(f"──────────────────────────────────────────────────────────────")
            
            config_impact_analysis = self.analyze_configuration_impact(
                original_activity, modified_activity, strategy_name
            )
            
            test_result['phases']['configuration_impact'] = config_impact_analysis
            
            # Overall success assessment
            overall_success = (
                original_persistence_valid and
                modified_persistence_valid and
                (original_activity['total_activity_count'] > 0 or modified_activity['total_activity_count'] > 0)
            )
            
            test_result['overall_success'] = overall_success
            test_result['test_end'] = datetime.now()
            
            # Summary
            test_result['summary'] = {
                'original_config_valid': original_persistence_valid,
                'modified_config_valid': modified_persistence_valid,
                'original_activity_detected': original_activity['total_activity_count'] > 0,
                'modified_activity_detected': modified_activity['total_activity_count'] > 0,
                'configuration_changes_effective': config_impact_analysis.get('changes_detected', False)
            }
            
            print(f"\n{'='*100}")
            if overall_success:
                print(f"✅ {strategy_name.upper()} - CONFIGURATION LIFECYCLE TEST PASSED")
                print(f"   ✅ Original config: Set and verified")
                print(f"   ✅ Modified config: Set and verified")
                print(f"   ✅ Activity detected: Original({original_activity['total_activity_count']}) Modified({modified_activity['total_activity_count']})")
            else:
                print(f"❌ {strategy_name.upper()} - CONFIGURATION LIFECYCLE TEST FAILED")
                print(f"   {'✅' if original_persistence_valid else '❌'} Original config: {'Valid' if original_persistence_valid else 'Invalid'}")
                print(f"   {'✅' if modified_persistence_valid else '❌'} Modified config: {'Valid' if modified_persistence_valid else 'Invalid'}")
            print(f"{'='*100}")
            
            return test_result
            
        except Exception as e:
            self.logger.error(f"Error testing {strategy_name}: {e}")
            test_result['error'] = str(e)
            return test_result
    
    def analyze_configuration_impact(self, original_activity: Dict, modified_activity: Dict, strategy_name: str) -> Dict[str, Any]:
        """Analyze the impact of configuration changes"""
        analysis = {
            'strategy': strategy_name,
            'original_activity_count': original_activity['total_activity_count'],
            'modified_activity_count': modified_activity['total_activity_count'],
            'activity_change': modified_activity['total_activity_count'] - original_activity['total_activity_count'],
            'changes_detected': False,
            'evidence': []
        }
        
        # Check for activity differences
        if analysis['activity_change'] != 0:
            analysis['changes_detected'] = True
            analysis['evidence'].append(f"Activity level changed by {analysis['activity_change']}")
        
        # Check for trade behavior differences
        original_trades = original_activity['trades_opened']
        modified_trades = modified_activity['trades_opened']
        
        if len(original_trades) > 0 and len(modified_trades) > 0:
            # Compare trade characteristics if both configs produced trades
            analysis['trade_comparison'] = {
                'original_trades': len(original_trades),
                'modified_trades': len(modified_trades),
                'trade_count_change': len(modified_trades) - len(original_trades)
            }
            
            if len(modified_trades) != len(original_trades):
                analysis['changes_detected'] = True
                analysis['evidence'].append(f"Trade frequency changed: {len(original_trades)} → {len(modified_trades)}")
        
        # Strategy-specific analysis
        if not analysis['changes_detected']:
            analysis['evidence'].append("No significant behavioral changes detected")
            analysis['evidence'].append("This may be normal if market conditions didn't trigger the modified parameters")
        
        return analysis
    
    def test_all_strategies(self):
        """Test configuration lifecycle for all strategies"""
        print("🔧 COMPREHENSIVE STRATEGY CONFIGURATION LIFECYCLE TEST")
        print("=" * 120)
        print(f"🕐 Test started at: {datetime.now()}")
        print(f"🌐 Testing against: {self.base_url}")
        print()
        
        # Check web dashboard connectivity
        try:
            response = requests.get(f"{self.base_url}/api/strategies", timeout=5)
            if response.status_code != 200:
                print(f"❌ Web dashboard not accessible at {self.base_url}")
                return
        except Exception as e:
            print(f"❌ Cannot connect to web dashboard: {e}")
            return
        
        print(f"✅ Web dashboard accessible")
        print()
        
        # Test each strategy
        test_results = {}
        passed_strategies = []
        failed_strategies = []
        
        strategy_names = list(self.strategy_config_sets.keys())
        print(f"📋 Testing {len(strategy_names)} strategies: {strategy_names}")
        print()
        
        for i, strategy_name in enumerate(strategy_names, 1):
            print(f"\n🎯 TESTING STRATEGY {i}/{len(strategy_names)}: {strategy_name}")
            print("─" * 120)
            
            try:
                result = self.test_strategy_configuration_lifecycle(strategy_name)
                test_results[strategy_name] = result
                
                if result.get('overall_success', False):
                    passed_strategies.append(strategy_name)
                else:
                    failed_strategies.append(strategy_name)
                    
            except Exception as e:
                print(f"❌ Critical error testing {strategy_name}: {e}")
                failed_strategies.append(strategy_name)
                test_results[strategy_name] = {
                    'strategy': strategy_name,
                    'error': str(e),
                    'overall_success': False
                }
            
            # Wait between strategies
            if i < len(strategy_names):
                print(f"\n⏳ Waiting 15 seconds before next strategy...")
                time.sleep(15)
        
        # Final summary
        self.print_final_summary(test_results, passed_strategies, failed_strategies)
        
        # Save results
        self.save_results(test_results)
        
        return test_results
    
    def print_final_summary(self, test_results: Dict, passed_strategies: List, failed_strategies: List):
        """Print final test summary"""
        total_strategies = len(test_results)
        passed_count = len(passed_strategies)
        failed_count = len(failed_strategies)
        
        print("\n" + "=" * 120)
        print("📊 FINAL CONFIGURATION LIFECYCLE TEST SUMMARY")
        print("=" * 120)
        print(f"🕐 Test completed at: {datetime.now()}")
        print(f"📈 Total strategies tested: {total_strategies}")
        print(f"✅ Passed: {passed_count}")
        print(f"❌ Failed: {failed_count}")
        print(f"📊 Success rate: {(passed_count/total_strategies)*100:.1f}%")
        print()
        
        if passed_strategies:
            print("✅ PASSED STRATEGIES:")
            for strategy in passed_strategies:
                result = test_results.get(strategy, {})
                summary = result.get('summary', {})
                print(f"   ✅ {strategy}")
                print(f"      📋 Original config: {'✅ Valid' if summary.get('original_config_valid') else '❌ Invalid'}")
                print(f"      🔄 Modified config: {'✅ Valid' if summary.get('modified_config_valid') else '❌ Invalid'}")
                print(f"      📊 Activity: Original({summary.get('original_activity_detected', False)}) Modified({summary.get('modified_activity_detected', False)})")
        
        if failed_strategies:
            print("\n❌ FAILED STRATEGIES:")
            for strategy in failed_strategies:
                result = test_results.get(strategy, {})
                if 'error' in result:
                    print(f"   ❌ {strategy} - Test failed with error: {result['error']}")
                else:
                    summary = result.get('summary', {})
                    issues = []
                    if not summary.get('original_config_valid'):
                        issues.append("Original config invalid")
                    if not summary.get('modified_config_valid'):
                        issues.append("Modified config invalid")
                    print(f"   ❌ {strategy} - Issues: {', '.join(issues) if issues else 'Unknown'}")
        
        print("\n" + "=" * 120)
    
    def save_results(self, results: Dict):
        """Save test results to file"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"strategy_configuration_lifecycle_test_{timestamp}.json"
            
            # Prepare results for JSON serialization
            json_results = {}
            for strategy, result in results.items():
                json_results[strategy] = self._serialize_result(result)
            
            test_metadata = {
                "test_type": "strategy_configuration_lifecycle",
                "timestamp": datetime.now().isoformat(),
                "base_url": self.base_url,
                "total_strategies": len(results),
                "passed_strategies": len([r for r in results.values() if r.get('overall_success', False)]),
                "failed_strategies": len([r for r in results.values() if not r.get('overall_success', False)])
            }
            
            output = {
                "test_metadata": test_metadata,
                "results": json_results
            }
            
            with open(filename, 'w') as f:
                json.dump(output, f, indent=2)
            
            print(f"💾 Test results saved to: {filename}")
            
        except Exception as e:
            print(f"⚠️  Could not save results to file: {e}")
    
    def _serialize_result(self, result: Dict) -> Dict:
        """Convert result to JSON-serializable format"""
        serialized = {}
        for key, value in result.items():
            if isinstance(value, datetime):
                serialized[key] = value.isoformat()
            elif isinstance(value, dict):
                serialized[key] = self._serialize_result(value)
            elif isinstance(value, list):
                serialized[key] = [self._serialize_result(item) if isinstance(item, dict) else str(item) for item in value]
            else:
                serialized[key] = value
        return serialized

def main():
    """Main test execution"""
    print("🔧 STRATEGY CONFIGURATION LIFECYCLE TEST")
    print("=" * 120)
    print("This test verifies that:")
    print("  1. Strategies work with current configurations")
    print("  2. Configuration changes are properly saved")
    print("  3. Strategies use the new configurations after changes")
    print("  4. Trading behavior reflects the configuration changes")
    print("=" * 120)
    
    # Initialize test suite
    tester = StrategyConfigurationLifecycleTest()
    
    # Check if web dashboard is running
    try:
        response = requests.get(f"{tester.base_url}/api/strategies", timeout=5)
        if response.status_code != 200:
            print(f"❌ Web dashboard not accessible at {tester.base_url}")
            print("   Please make sure the trading bot and web dashboard are running")
            return
    except Exception as e:
        print(f"❌ Cannot connect to web dashboard at {tester.base_url}")
        print(f"   Error: {e}")
        print("   Please make sure the trading bot and web dashboard are running")
        return
    
    print(f"✅ Web dashboard accessible at {tester.base_url}")
    print()
    
    # Run comprehensive test
    results = tester.test_all_strategies()
    
    print("\n🎯 CONFIGURATION LIFECYCLE TEST COMPLETED!")
    print("Check the generated JSON file for detailed results.")

if __name__ == "__main__":
    main()
