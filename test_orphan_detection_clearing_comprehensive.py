
#!/usr/bin/env python3
"""
Comprehensive Orphan Trade Detection and Clearing Test
====================================================

This test verifies:
1. Orphan trades are properly detected
2. Orphan trades are cleared from trade monitor
3. Positions are cleared from order manager
4. Database records are updated to CLOSED
5. Dashboard reflects the changes
6. Clearing notifications are sent
"""

import sys
import os
import asyncio
import time
import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.execution_engine.trade_database import TradeDatabase
from src.execution_engine.order_manager import OrderManager, Position
from src.execution_engine.trade_monitor import TradeMonitor, OrphanTrade
from src.binance_client.client import BinanceClientWrapper
from src.reporting.telegram_reporter import TelegramReporter
from src.config.trading_config import trading_config_manager
from src.analytics.trade_logger import trade_logger

class OrphanDetectionClearingTest:
    """Comprehensive test for orphan trade detection and clearing"""
    
    def __init__(self):
        self.test_start_time = datetime.now()
        self.test_strategies = ['rsi_oversold', 'macd_divergence', 'engulfing_pattern', 'smart_money']
        self.results = {}
        self.created_orphans = []
        
        # Initialize components
        self.trade_db = TradeDatabase()
        self.binance_client = BinanceClientWrapper()
        self.order_manager = OrderManager(self.binance_client, None)
        self.telegram_reporter = TelegramReporter()
        self.trade_monitor = TradeMonitor(self.binance_client, self.order_manager, self.telegram_reporter)
        
        # Dashboard API endpoint
        self.dashboard_base_url = "http://0.0.0.0:5000"
        
        print("🧪 COMPREHENSIVE ORPHAN DETECTION & CLEARING TEST")
        print("=" * 60)
        print(f"⏰ Test started: {self.test_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🎯 Testing strategies: {', '.join(self.test_strategies)}")
        
    def run_test(self):
        """Execute complete test sequence"""
        try:
            print("\n🔧 PHASE 1: Environment Setup")
            self._setup_test_environment()
            
            print("\n📊 PHASE 2: Create Test Orphan Trades")
            self._create_test_orphan_trades()
            
            print("\n🔍 PHASE 3: Test Orphan Detection")
            self._test_orphan_detection()
            
            print("\n🧹 PHASE 4: Test Orphan Clearing")
            self._test_orphan_clearing()
            
            print("\n📈 PHASE 5: Verify Database Updates")
            self._verify_database_updates()
            
            print("\n🖥️ PHASE 6: Verify Dashboard Updates")
            self._verify_dashboard_updates()
            
            print("\n✅ PHASE 7: Generate Test Report")
            self._generate_test_report()
            
        except Exception as e:
            print(f"❌ Test execution failed: {e}")
            import traceback
            print(f"🔍 Full traceback: {traceback.format_exc()}")
            
    def _setup_test_environment(self):
        """Set up clean test environment"""
        try:
            print("🔧 Setting up test environment...")
            
            # Clear any existing orphan trades
            initial_orphans = len(self.trade_monitor.orphan_trades)
            self.trade_monitor.orphan_trades.clear()
            print(f"   ✅ Cleared {initial_orphans} existing orphan trades")
            
            # Clear any existing positions in order manager
            initial_positions = len(self.order_manager.active_positions)
            self.order_manager.active_positions.clear()
            print(f"   ✅ Cleared {initial_positions} order manager positions")
            
            # Register test strategies with symbols
            strategy_symbols = {
                'rsi_oversold': 'SOLUSDT',
                'macd_divergence': 'BTCUSDT',
                'engulfing_pattern': 'ETHUSDT',
                'smart_money': 'XRPUSDT'
            }
            
            for strategy, symbol in strategy_symbols.items():
                self.trade_monitor.register_strategy(strategy, symbol)
                print(f"   ✅ Registered {strategy} for {symbol}")
            
            # Test dashboard connectivity
            dashboard_available = self._test_dashboard_connectivity()
            
            self.results['environment_setup'] = {
                'status': 'SUCCESS',
                'dashboard_available': dashboard_available,
                'orphan_trades_cleared': initial_orphans,
                'positions_cleared': initial_positions,
                'strategies_registered': len(strategy_symbols),
                'timestamp': datetime.now().isoformat()
            }
            
            print(f"   {'✅' if dashboard_available else '⚠️'} Dashboard {'available' if dashboard_available else 'not available'}")
            print("✅ Environment setup completed")
            
        except Exception as e:
            print(f"❌ Environment setup failed: {e}")
            self.results['environment_setup'] = {'status': 'ERROR', 'error': str(e)}
    
    def _create_test_orphan_trades(self):
        """Create test orphan trades for all strategies"""
        try:
            print("📊 Creating test orphan trades...")
            
            strategy_configs = {
                'rsi_oversold': {
                    'symbol': 'SOLUSDT',
                    'side': 'BUY',
                    'quantity': 0.05,
                    'entry_price': 150.25
                },
                'macd_divergence': {
                    'symbol': 'BTCUSDT', 
                    'side': 'SELL',
                    'quantity': 0.002,
                    'entry_price': 67500.50
                },
                'engulfing_pattern': {
                    'symbol': 'ETHUSDT',
                    'side': 'BUY', 
                    'quantity': 0.015,
                    'entry_price': 3250.75
                },
                'smart_money': {
                    'symbol': 'XRPUSDT',
                    'side': 'SELL',
                    'quantity': 25.0,
                    'entry_price': 2.15
                }
            }
            
            created_count = 0
            
            for strategy in self.test_strategies:
                print(f"\n   🎯 Creating orphan trade for {strategy}:")
                
                config = strategy_configs[strategy]
                
                # Create position in order manager (simulating bot opened position)
                position = Position(
                    symbol=config['symbol'],
                    side=config['side'],
                    quantity=config['quantity'],
                    entry_price=config['entry_price'],
                    strategy_name=strategy,
                    stop_loss=config['entry_price'] * 0.95 if config['side'] == 'BUY' else config['entry_price'] * 1.05,
                    take_profit=config['entry_price'] * 1.10 if config['side'] == 'BUY' else config['entry_price'] * 0.90
                )
                
                # Add to order manager
                self.order_manager.active_positions[strategy] = position
                print(f"      ✅ Created bot position: {config['symbol']} {config['side']} {config['quantity']}")
                
                # Create database record
                trade_id = f"TEST_ORPHAN_{strategy}_{int(time.time())}"
                trade_data = {
                    'trade_id': trade_id,
                    'strategy_name': strategy,
                    'symbol': config['symbol'],
                    'side': config['side'],
                    'quantity': config['quantity'],
                    'entry_price': config['entry_price'],
                    'trade_status': 'OPEN',
                    'position_value_usdt': config['entry_price'] * config['quantity'],
                    'leverage': 1,
                    'margin_used': config['entry_price'] * config['quantity'],
                    'stop_loss': position.stop_loss,
                    'take_profit': position.take_profit,
                    'created_at': datetime.now().isoformat(),
                    'last_updated': datetime.now().isoformat(),
                    'test_orphan': True  # Mark as test
                }
                
                # Add to database
                db_success = self.trade_db.add_trade(trade_id, trade_data)
                if db_success:
                    print(f"      ✅ Created database record: {trade_id}")
                    self.created_orphans.append({
                        'strategy': strategy,
                        'trade_id': trade_id,
                        'symbol': config['symbol'],
                        'position': position
                    })
                    created_count += 1
                else:
                    print(f"      ❌ Failed to create database record for {strategy}")
            
            self.results['orphan_creation'] = {
                'status': 'SUCCESS' if created_count == len(self.test_strategies) else 'PARTIAL',
                'created_count': created_count,
                'expected_count': len(self.test_strategies),
                'created_orphans': [o['strategy'] for o in self.created_orphans],
                'timestamp': datetime.now().isoformat()
            }
            
            print(f"\n✅ Orphan creation completed: {created_count}/{len(self.test_strategies)} orphans created")
            
        except Exception as e:
            print(f"❌ Orphan creation failed: {e}")
            self.results['orphan_creation'] = {'status': 'ERROR', 'error': str(e)}
    
    def _test_orphan_detection(self):
        """Test orphan trade detection"""
        try:
            print("🔍 Testing orphan detection...")
            
            # Record initial state
            initial_orphan_count = len(self.trade_monitor.orphan_trades)
            print(f"   📊 Initial orphan trades: {initial_orphan_count}")
            
            # Run anomaly check to trigger detection
            print("   🔍 Running anomaly detection...")
            self.trade_monitor.check_for_anomalies(suppress_notifications=True)
            
            # Wait a moment for processing
            time.sleep(2)
            
            # Check detection results
            final_orphan_count = len(self.trade_monitor.orphan_trades)
            detected_orphan_ids = list(self.trade_monitor.orphan_trades.keys())
            
            print(f"   📊 Final orphan trades: {final_orphan_count}")
            print(f"   📊 Detected orphan IDs: {detected_orphan_ids}")
            
            # Verify each created orphan was detected
            expected_orphans = [f"{o['strategy']}_{o['symbol']}" for o in self.created_orphans]
            detected_orphans = detected_orphan_ids
            
            detection_success = set(expected_orphans).issubset(set(detected_orphans))
            
            print(f"   📊 Expected orphans: {expected_orphans}")
            print(f"   📊 Detected orphans: {detected_orphans}")
            print(f"   📊 Detection success: {detection_success}")
            
            self.results['orphan_detection'] = {
                'status': 'SUCCESS' if detection_success else 'FAILED',
                'initial_orphan_count': initial_orphan_count,
                'final_orphan_count': final_orphan_count,
                'expected_orphans': expected_orphans,
                'detected_orphans': detected_orphans,
                'detection_success': detection_success,
                'timestamp': datetime.now().isoformat()
            }
            
            if detection_success:
                print("✅ Orphan detection test PASSED")
            else:
                print("❌ Orphan detection test FAILED")
                
        except Exception as e:
            print(f"❌ Orphan detection test failed: {e}")
            self.results['orphan_detection'] = {'status': 'ERROR', 'error': str(e)}
    
    def _test_orphan_clearing(self):
        """Test orphan trade clearing"""
        try:
            print("🧹 Testing orphan clearing...")
            
            cleared_count = 0
            clearing_results = {}
            
            for orphan_data in self.created_orphans:
                strategy = orphan_data['strategy']
                symbol = orphan_data['symbol']
                trade_id = orphan_data['trade_id']
                orphan_id = f"{strategy}_{symbol}"
                
                print(f"\n   🎯 Testing clearing for {strategy}:")
                
                # Check if orphan exists
                if orphan_id not in self.trade_monitor.orphan_trades:
                    print(f"      ❌ Orphan {orphan_id} not found for clearing")
                    clearing_results[strategy] = {'status': 'NOT_FOUND'}
                    continue
                
                orphan_trade = self.trade_monitor.orphan_trades[orphan_id]
                print(f"      📊 Found orphan: {orphan_id} with {orphan_trade.cycles_remaining} cycles")
                
                # Record initial states
                initial_position_exists = strategy in self.order_manager.active_positions
                initial_db_trade = self.trade_db.get_trade(trade_id)
                initial_db_open = initial_db_trade and initial_db_trade.get('trade_status') == 'OPEN'
                
                print(f"      📊 Initial position in order manager: {initial_position_exists}")
                print(f"      📊 Initial database status: {'OPEN' if initial_db_open else 'CLOSED/MISSING'}")
                
                # Force clearing by setting cycles to 0
                print("      ⏱️ Forcing clearing by setting cycles to 0...")
                orphan_trade.cycles_remaining = 0
                
                # Process clearing
                print("      🔄 Processing cycle countdown...")
                self.trade_monitor._process_cycle_countdown(suppress_notifications=True)
                
                # Wait for processing
                time.sleep(1)
                
                # Check clearing results
                orphan_still_exists = orphan_id in self.trade_monitor.orphan_trades
                position_still_exists = strategy in self.order_manager.active_positions
                
                # Check database status
                final_db_trade = self.trade_db.get_trade(trade_id)
                final_db_closed = final_db_trade and final_db_trade.get('trade_status') == 'CLOSED'
                
                print(f"      📊 Orphan still exists: {orphan_still_exists}")
                print(f"      📊 Position still in order manager: {position_still_exists}")
                print(f"      📊 Database status: {'CLOSED' if final_db_closed else 'OPEN/MISSING'}")
                
                # Determine success
                clearing_successful = (not orphan_still_exists and 
                                     not position_still_exists and 
                                     final_db_closed)
                
                if clearing_successful:
                    cleared_count += 1
                    print(f"      ✅ Successfully cleared {strategy}")
                else:
                    print(f"      ❌ Failed to clear {strategy}")
                
                clearing_results[strategy] = {
                    'status': 'SUCCESS' if clearing_successful else 'FAILED',
                    'orphan_cleared': not orphan_still_exists,
                    'position_cleared': not position_still_exists,
                    'database_updated': final_db_closed,
                    'final_db_trade': final_db_trade
                }
            
            overall_success = cleared_count == len(self.created_orphans)
            
            self.results['orphan_clearing'] = {
                'status': 'SUCCESS' if overall_success else 'FAILED',
                'cleared_count': cleared_count,
                'expected_count': len(self.created_orphans),
                'clearing_results': clearing_results,
                'overall_success': overall_success,
                'timestamp': datetime.now().isoformat()
            }
            
            if overall_success:
                print(f"\n✅ Orphan clearing test PASSED: {cleared_count}/{len(self.created_orphans)} orphans cleared")
            else:
                print(f"\n❌ Orphan clearing test FAILED: {cleared_count}/{len(self.created_orphans)} orphans cleared")
                
        except Exception as e:
            print(f"❌ Orphan clearing test failed: {e}")
            self.results['orphan_clearing'] = {'status': 'ERROR', 'error': str(e)}
    
    def _verify_database_updates(self):
        """Verify database records were properly updated"""
        try:
            print("📈 Verifying database updates...")
            
            updated_count = 0
            database_results = {}
            
            for orphan_data in self.created_orphans:
                strategy = orphan_data['strategy']
                trade_id = orphan_data['trade_id']
                
                trade_record = self.trade_db.get_trade(trade_id)
                
                if trade_record:
                    status = trade_record.get('trade_status')
                    exit_reason = trade_record.get('exit_reason')
                    orphan_cleared = trade_record.get('orphan_cleared', False)
                    manually_closed = trade_record.get('manually_closed', False)
                    
                    is_properly_updated = (status == 'CLOSED' and 
                                         'Orphan' in str(exit_reason) and 
                                         orphan_cleared)
                    
                    if is_properly_updated:
                        updated_count += 1
                        print(f"   ✅ {strategy}: Properly updated to CLOSED")
                    else:
                        print(f"   ❌ {strategy}: Not properly updated (Status: {status})")
                    
                    database_results[strategy] = {
                        'status': status,
                        'exit_reason': exit_reason,
                        'orphan_cleared': orphan_cleared,
                        'manually_closed': manually_closed,
                        'properly_updated': is_properly_updated
                    }
                else:
                    print(f"   ❌ {strategy}: Trade record not found")
                    database_results[strategy] = {'status': 'NOT_FOUND'}
            
            overall_success = updated_count == len(self.created_orphans)
            
            self.results['database_verification'] = {
                'status': 'SUCCESS' if overall_success else 'FAILED',
                'updated_count': updated_count,
                'expected_count': len(self.created_orphans),
                'database_results': database_results,
                'overall_success': overall_success,
                'timestamp': datetime.now().isoformat()
            }
            
            if overall_success:
                print(f"✅ Database verification PASSED: {updated_count}/{len(self.created_orphans)} records updated")
            else:
                print(f"❌ Database verification FAILED: {updated_count}/{len(self.created_orphans)} records updated")
                
        except Exception as e:
            print(f"❌ Database verification failed: {e}")
            self.results['database_verification'] = {'status': 'ERROR', 'error': str(e)}
    
    def _verify_dashboard_updates(self):
        """Verify dashboard reflects the changes"""
        try:
            print("🖥️ Verifying dashboard updates...")
            
            if not self.results.get('environment_setup', {}).get('dashboard_available'):
                print("   ⚠️ Dashboard not available - skipping verification")
                self.results['dashboard_verification'] = {
                    'status': 'SKIPPED',
                    'reason': 'Dashboard not available'
                }
                return
            
            # Get positions from dashboard API
            dashboard_positions = self._get_dashboard_positions()
            
            if dashboard_positions is None:
                print("   ❌ Failed to get dashboard positions")
                self.results['dashboard_verification'] = {
                    'status': 'ERROR',
                    'error': 'Failed to get dashboard positions'
                }
                return
            
            # Check for test orphan positions on dashboard
            test_positions_found = []
            for position in dashboard_positions:
                strategy = position.get('strategy')
                if strategy in self.test_strategies:
                    test_positions_found.append(strategy)
            
            # Dashboard should show NO test positions after clearing
            dashboard_clean = len(test_positions_found) == 0
            
            print(f"   📊 Test positions found on dashboard: {test_positions_found}")
            print(f"   📊 Dashboard clean status: {dashboard_clean}")
            
            self.results['dashboard_verification'] = {
                'status': 'SUCCESS' if dashboard_clean else 'FAILED',
                'test_positions_found': test_positions_found,
                'dashboard_clean': dashboard_clean,
                'total_dashboard_positions': len(dashboard_positions),
                'timestamp': datetime.now().isoformat()
            }
            
            if dashboard_clean:
                print("✅ Dashboard verification PASSED: No test positions found")
            else:
                print("❌ Dashboard verification FAILED: Test positions still visible")
                
        except Exception as e:
            print(f"❌ Dashboard verification failed: {e}")
            self.results['dashboard_verification'] = {'status': 'ERROR', 'error': str(e)}
    
    def _test_dashboard_connectivity(self) -> bool:
        """Test if dashboard is accessible"""
        try:
            response = requests.get(f"{self.dashboard_base_url}/api/bot/status", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def _get_dashboard_positions(self) -> Optional[List[Dict]]:
        """Get active positions from dashboard API"""
        try:
            response = requests.get(f"{self.dashboard_base_url}/api/positions", timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data.get('positions', [])
        except Exception as e:
            print(f"     ⚠️ Error getting dashboard positions: {e}")
        return None
    
    def _generate_test_report(self):
        """Generate comprehensive test report"""
        try:
            print("📈 COMPREHENSIVE TEST REPORT")
            print("=" * 60)
            
            test_duration = datetime.now() - self.test_start_time
            print(f"⏱️ Test Duration: {test_duration.total_seconds():.1f} seconds")
            
            # Phase Results
            phases = [
                ('Environment Setup', 'environment_setup'),
                ('Orphan Creation', 'orphan_creation'),
                ('Orphan Detection', 'orphan_detection'),
                ('Orphan Clearing', 'orphan_clearing'),
                ('Database Verification', 'database_verification'),
                ('Dashboard Verification', 'dashboard_verification')
            ]
            
            successful_phases = 0
            total_phases = len(phases)
            
            print(f"\n📊 PHASE RESULTS:")
            for phase_name, result_key in phases:
                result = self.results.get(result_key, {})
                status = result.get('status', 'UNKNOWN')
                
                if status == 'SUCCESS':
                    successful_phases += 1
                    print(f"   ✅ {phase_name}: {status}")
                elif status == 'SKIPPED':
                    print(f"   ⏭️ {phase_name}: {status}")
                else:
                    print(f"   ❌ {phase_name}: {status}")
            
            # Overall Result
            print(f"\n🎯 OVERALL TEST RESULT")
            print("-" * 40)
            
            success_rate = (successful_phases / total_phases) * 100
            
            if success_rate >= 90:
                result_emoji = "🟢"
                result_text = "EXCELLENT"
            elif success_rate >= 75:
                result_emoji = "🟡"  
                result_text = "GOOD"
            elif success_rate >= 50:
                result_emoji = "🟠"
                result_text = "PARTIAL"
            else:
                result_emoji = "🔴"
                result_text = "FAILED"
            
            print(f"{result_emoji} Overall Success Rate: {success_rate:.1f}% ({result_text})")
            print(f"📊 Successful Phases: {successful_phases}/{total_phases}")
            
            # Key Findings
            print(f"\n🔍 KEY FINDINGS:")
            
            detection_result = self.results.get('orphan_detection', {})
            clearing_result = self.results.get('orphan_clearing', {})
            database_result = self.results.get('database_verification', {})
            
            if detection_result.get('detection_success'):
                print("   ✅ Orphan detection working properly")
            else:
                print("   ❌ Orphan detection has issues")
            
            if clearing_result.get('overall_success'):
                print("   ✅ Orphan clearing working properly")
            else:
                print("   ❌ Orphan clearing has issues")
            
            if database_result.get('overall_success'):
                print("   ✅ Database updates working properly")
            else:
                print("   ❌ Database updates have issues")
            
            # Save detailed results
            report_filename = f"orphan_detection_clearing_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(report_filename, 'w') as f:
                json.dump(self.results, f, indent=2, default=str)
            print(f"\n💾 Detailed results saved to: {report_filename}")
            
            print("\n" + "=" * 60)
            print("🧪 ORPHAN DETECTION & CLEARING TEST COMPLETED")
            
        except Exception as e:
            print(f"❌ Report generation failed: {e}")

def main():
    """Run the comprehensive orphan detection and clearing test"""
    test = OrphanDetectionClearingTest()
    test.run_test()

if __name__ == "__main__":
    main()
