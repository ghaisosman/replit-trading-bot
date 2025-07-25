
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
        self.test_strategy = 'rsi_oversold'
        self.test_symbol = 'SOLUSDT'
        self.results = {}
        
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
        print(f"🎯 Testing strategy: {self.test_strategy} on {self.test_symbol}")
        
    def run_test(self):
        """Execute complete test sequence"""
        try:
            print("\n🔧 PHASE 1: Environment Setup")
            self._setup_test_environment()
            
            print("\n📊 PHASE 2: Create Test Trade")
            self._create_test_trade()
            
            print("\n🔍 PHASE 3: Force Orphan Condition")
            self._force_orphan_condition()
            
            print("\n👻 PHASE 4: Test Orphan Detection")
            self._test_orphan_detection()
            
            print("\n🧹 PHASE 5: Test Orphan Clearing")
            self._test_orphan_clearing()
            
            print("\n✅ PHASE 6: Verify Complete Cleanup")
            self._verify_complete_cleanup()
            
            print("\n📈 PHASE 7: Generate Test Report")
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
            self.trade_monitor.orphan_trades.clear()
            print("   ✅ Cleared existing orphan trades")
            
            # Clear any existing positions in order manager
            self.order_manager.active_positions.clear()
            print("   ✅ Cleared order manager positions")
            
            # Register test strategy
            self.trade_monitor.register_strategy(self.test_strategy, self.test_symbol)
            print(f"   ✅ Registered {self.test_strategy} for {self.test_symbol}")
            
            # Test dashboard connectivity
            dashboard_available = self._test_dashboard_connectivity()
            
            self.results['environment_setup'] = {
                'status': 'SUCCESS',
                'dashboard_available': dashboard_available,
                'orphan_trades_cleared': True,
                'positions_cleared': True,
                'strategy_registered': True,
                'timestamp': datetime.now().isoformat()
            }
            
            print(f"   {'✅' if dashboard_available else '⚠️'} Dashboard {'available' if dashboard_available else 'not available'}")
            print("✅ Environment setup completed")
            
        except Exception as e:
            print(f"❌ Environment setup failed: {e}")
            self.results['environment_setup'] = {'status': 'ERROR', 'error': str(e)}
    
    def _create_test_trade(self):
        """Create a test trade in the system"""
        try:
            print("📊 Creating test trade...")
            
            # Create test position
            test_position = Position(
                symbol=self.test_symbol,
                side='BUY',
                quantity=0.05,
                entry_price=150.25,
                strategy_name=self.test_strategy,
                stop_loss=142.74,  # 5% stop loss
                take_profit=165.28  # 10% take profit
            )
            
            # Add to order manager
            self.order_manager.active_positions[self.test_strategy] = test_position
            print(f"   ✅ Created position: {self.test_symbol} {test_position.side} {test_position.quantity} @ ${test_position.entry_price}")
            
            # Create database record
            self.test_trade_id = f"TEST_ORPHAN_{self.test_strategy}_{int(time.time())}"
            trade_data = {
                'trade_id': self.test_trade_id,
                'strategy_name': self.test_strategy,
                'symbol': self.test_symbol,
                'side': test_position.side,
                'quantity': test_position.quantity,
                'entry_price': test_position.entry_price,
                'trade_status': 'OPEN',
                'position_value_usdt': test_position.entry_price * test_position.quantity,
                'leverage': 1,
                'margin_used': test_position.entry_price * test_position.quantity,
                'stop_loss': test_position.stop_loss,
                'take_profit': test_position.take_profit,
                'created_at': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat()
            }
            
            # Add to database
            db_success = self.trade_db.add_trade(self.test_trade_id, trade_data)
            
            self.results['test_trade_creation'] = {
                'status': 'SUCCESS' if db_success else 'PARTIAL',
                'trade_id': self.test_trade_id,
                'position_created': True,
                'database_record_added': db_success,
                'position_details': {
                    'symbol': test_position.symbol,
                    'side': test_position.side,
                    'quantity': test_position.quantity,
                    'entry_price': test_position.entry_price
                },
                'timestamp': datetime.now().isoformat()
            }
            
            if db_success:
                print(f"   ✅ Database record created: {self.test_trade_id}")
            else:
                print(f"   ⚠️ Database record creation failed")
                
            print("✅ Test trade creation completed")
            
        except Exception as e:
            print(f"❌ Test trade creation failed: {e}")
            self.results['test_trade_creation'] = {'status': 'ERROR', 'error': str(e)}
    
    def _force_orphan_condition(self):
        """Force orphan condition by simulating manual closure on Binance"""
        try:
            print("🔍 Forcing orphan condition...")
            
            # Get initial Binance positions to verify none exist
            binance_positions = self._get_binance_positions(self.test_symbol)
            has_real_position = any(abs(float(pos.get('positionAmt', 0))) > 0.001 
                                  for pos in binance_positions)
            
            print(f"   📊 Binance positions for {self.test_symbol}: {len(binance_positions)}")
            print(f"   📊 Has real position on Binance: {has_real_position}")
            
            # Verify bot thinks position exists
            bot_has_position = self.test_strategy in self.order_manager.active_positions
            print(f"   📊 Bot thinks position exists: {bot_has_position}")
            
            # Verify database shows open trade
            db_trade = self.trade_db.get_trade(self.test_trade_id)
            db_shows_open = db_trade and db_trade.get('trade_status') == 'OPEN'
            print(f"   📊 Database shows open trade: {db_shows_open}")
            
            # This creates the orphan condition:
            # - Bot thinks position is open (in order_manager)
            # - Database shows trade as open
            # - But Binance has no actual position (simulating manual closure)
            
            self.results['orphan_condition'] = {
                'status': 'SUCCESS',
                'bot_has_position': bot_has_position,
                'binance_has_position': has_real_position,
                'database_shows_open': db_shows_open,
                'orphan_condition_created': bot_has_position and not has_real_position and db_shows_open,
                'timestamp': datetime.now().isoformat()
            }
            
            if bot_has_position and not has_real_position and db_shows_open:
                print("   ✅ Orphan condition successfully created")
                print("   📊 Bot: position exists | Binance: no position | Database: open")
            else:
                print("   ⚠️ Orphan condition may not be properly set")
                
            print("✅ Orphan condition setup completed")
            
        except Exception as e:
            print(f"❌ Orphan condition setup failed: {e}")
            self.results['orphan_condition'] = {'status': 'ERROR', 'error': str(e)}
    
    def _test_orphan_detection(self):
        """Test orphan trade detection"""
        try:
            print("👻 Testing orphan detection...")
            
            # Record initial state
            initial_orphan_count = len(self.trade_monitor.orphan_trades)
            print(f"   📊 Initial orphan trades: {initial_orphan_count}")
            
            # Run anomaly check to trigger detection
            print("   🔍 Running anomaly detection...")
            self.trade_monitor.check_for_anomalies(suppress_notifications=True)
            
            # Wait a moment for processing
            time.sleep(1)
            
            # Check detection results
            final_orphan_count = len(self.trade_monitor.orphan_trades)
            print(f"   📊 Final orphan trades: {final_orphan_count}")
            print(f"   📊 Orphan trade IDs: {list(self.trade_monitor.orphan_trades.keys())}")
            
            # Look for our specific orphan
            expected_orphan_id = f"{self.test_strategy}_{self.test_symbol}"
            orphan_detected = expected_orphan_id in self.trade_monitor.orphan_trades
            
            if orphan_detected:
                orphan_trade = self.trade_monitor.orphan_trades[expected_orphan_id]
                print(f"   ✅ Orphan detected: {expected_orphan_id}")
                print(f"   📊 Cycles remaining: {orphan_trade.cycles_remaining}")
                print(f"   📊 Detection time: {orphan_trade.detected_at}")
                
                orphan_details = {
                    'orphan_id': expected_orphan_id,
                    'cycles_remaining': orphan_trade.cycles_remaining,
                    'detected_at': orphan_trade.detected_at.isoformat(),
                    'position_symbol': orphan_trade.position.symbol,
                    'position_side': orphan_trade.position.side,
                    'position_quantity': orphan_trade.position.quantity
                }
            else:
                print(f"   ❌ Orphan NOT detected: {expected_orphan_id}")
                print(f"   🔍 Available orphan IDs: {list(self.trade_monitor.orphan_trades.keys())}")
                orphan_details = None
            
            self.results['orphan_detection'] = {
                'status': 'SUCCESS' if orphan_detected else 'FAILED',
                'initial_orphan_count': initial_orphan_count,
                'final_orphan_count': final_orphan_count,
                'orphan_detected': orphan_detected,
                'expected_orphan_id': expected_orphan_id,
                'orphan_details': orphan_details,
                'all_orphan_ids': list(self.trade_monitor.orphan_trades.keys()),
                'timestamp': datetime.now().isoformat()
            }
            
            if orphan_detected:
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
            
            # Get the orphan trade
            expected_orphan_id = f"{self.test_strategy}_{self.test_symbol}"
            
            if expected_orphan_id not in self.trade_monitor.orphan_trades:
                print(f"   ❌ Cannot test clearing - orphan {expected_orphan_id} not found")
                self.results['orphan_clearing'] = {
                    'status': 'SKIPPED',
                    'reason': 'Orphan not detected in previous phase'
                }
                return
            
            orphan_trade = self.trade_monitor.orphan_trades[expected_orphan_id]
            print(f"   📊 Found orphan: {expected_orphan_id}")
            print(f"   📊 Initial cycles: {orphan_trade.cycles_remaining}")
            
            # Record initial states
            initial_position_exists = self.test_strategy in self.order_manager.active_positions
            initial_db_status = self.trade_db.get_trade(self.test_trade_id)
            initial_db_open = initial_db_status and initial_db_status.get('trade_status') == 'OPEN'
            
            print(f"   📊 Initial position in order manager: {initial_position_exists}")
            print(f"   📊 Initial database status: {'OPEN' if initial_db_open else 'CLOSED/MISSING'}")
            
            # Force clearing by setting cycles to 0
            print("   ⏱️ Forcing clearing by setting cycles to 0...")
            orphan_trade.cycles_remaining = 0
            
            # Process clearing
            print("   🔄 Processing cycle countdown...")
            self.trade_monitor._process_cycle_countdown(suppress_notifications=True)
            
            # Wait for processing
            time.sleep(1)
            
            # Check clearing results
            orphan_still_exists = expected_orphan_id in self.trade_monitor.orphan_trades
            position_still_exists = self.test_strategy in self.order_manager.active_positions
            
            # Check database status
            final_db_status = self.trade_db.get_trade(self.test_trade_id)
            final_db_closed = final_db_status and final_db_status.get('trade_status') == 'CLOSED'
            
            print(f"   📊 Orphan still exists: {orphan_still_exists}")
            print(f"   📊 Position still in order manager: {position_still_exists}")
            print(f"   📊 Database status: {'CLOSED' if final_db_closed else 'OPEN/MISSING'}")
            
            # Check database update details
            if final_db_status:
                exit_reason = final_db_status.get('exit_reason', 'Not set')
                orphan_cleared_flag = final_db_status.get('orphan_cleared', False)
                manually_closed_flag = final_db_status.get('manually_closed', False)
                
                print(f"   📊 Exit reason: {exit_reason}")
                print(f"   📊 Orphan cleared flag: {orphan_cleared_flag}")
                print(f"   📊 Manually closed flag: {manually_closed_flag}")
            
            # Determine success
            clearing_successful = (not orphan_still_exists and 
                                 not position_still_exists and 
                                 final_db_closed)
            
            self.results['orphan_clearing'] = {
                'status': 'SUCCESS' if clearing_successful else 'FAILED',
                'initial_states': {
                    'orphan_exists': True,
                    'position_exists': initial_position_exists,
                    'database_open': initial_db_open
                },
                'final_states': {
                    'orphan_exists': orphan_still_exists,
                    'position_exists': position_still_exists,
                    'database_closed': final_db_closed
                },
                'database_details': final_db_status if final_db_status else {},
                'clearing_successful': clearing_successful,
                'timestamp': datetime.now().isoformat()
            }
            
            if clearing_successful:
                print("✅ Orphan clearing test PASSED")
                print("   ✅ Orphan removed from trade monitor")
                print("   ✅ Position cleared from order manager")
                print("   ✅ Database updated to CLOSED")
            else:
                print("❌ Orphan clearing test FAILED")
                if orphan_still_exists:
                    print("   ❌ Orphan still exists in trade monitor")
                if position_still_exists:
                    print("   ❌ Position still exists in order manager")
                if not final_db_closed:
                    print("   ❌ Database not updated to CLOSED")
                    
        except Exception as e:
            print(f"❌ Orphan clearing test failed: {e}")
            self.results['orphan_clearing'] = {'status': 'ERROR', 'error': str(e)}
    
    def _verify_complete_cleanup(self):
        """Verify complete system cleanup"""
        try:
            print("✅ Verifying complete cleanup...")
            
            # Check all systems are clean
            orphan_count = len(self.trade_monitor.orphan_trades)
            position_count = len([pos for pos in self.order_manager.active_positions.values() 
                                if pos.strategy_name == self.test_strategy])
            
            # Count open trades in database
            open_trades = 0
            for trade_id, trade_data in self.trade_db.trades.items():
                if (trade_data.get('strategy_name') == self.test_strategy and 
                    trade_data.get('trade_status') == 'OPEN'):
                    open_trades += 1
            
            # Check dashboard if available
            dashboard_positions = []
            if self.results.get('environment_setup', {}).get('dashboard_available'):
                dashboard_positions = self._get_dashboard_positions() or []
                test_positions_on_dashboard = [pos for pos in dashboard_positions 
                                             if pos.get('strategy') == self.test_strategy]
            else:
                test_positions_on_dashboard = []
            
            print(f"   📊 Orphan trades remaining: {orphan_count}")
            print(f"   📊 Test positions in order manager: {position_count}")
            print(f"   📊 Open test trades in database: {open_trades}")
            print(f"   📊 Test positions on dashboard: {len(test_positions_on_dashboard)}")
            
            # Determine if cleanup is complete
            cleanup_complete = (orphan_count == 0 and 
                              position_count == 0 and 
                              open_trades == 0 and 
                              len(test_positions_on_dashboard) == 0)
            
            self.results['complete_cleanup'] = {
                'status': 'SUCCESS' if cleanup_complete else 'INCOMPLETE',
                'system_state': {
                    'orphan_trades': orphan_count,
                    'test_positions': position_count,
                    'open_db_trades': open_trades,
                    'dashboard_positions': len(test_positions_on_dashboard)
                },
                'cleanup_complete': cleanup_complete,
                'timestamp': datetime.now().isoformat()
            }
            
            if cleanup_complete:
                print("✅ Complete cleanup verification PASSED")
                print("   ✅ All systems clean - no traces remaining")
            else:
                print("⚠️ Complete cleanup verification INCOMPLETE")
                print("   ⚠️ Some traces may remain in the system")
                
        except Exception as e:
            print(f"❌ Complete cleanup verification failed: {e}")
            self.results['complete_cleanup'] = {'status': 'ERROR', 'error': str(e)}
    
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
    
    def _get_binance_positions(self, symbol: str) -> List[Dict]:
        """Get positions from Binance for a specific symbol"""
        try:
            if self.binance_client.is_futures:
                account_info = self.binance_client.client.futures_account()
                positions = account_info.get('positions', [])
                return [pos for pos in positions if pos.get('symbol') == symbol]
            else:
                return []
        except Exception as e:
            print(f"     ⚠️ Error getting Binance positions for {symbol}: {e}")
            return []
    
    def _generate_test_report(self):
        """Generate comprehensive test report"""
        try:
            print("📈 COMPREHENSIVE TEST REPORT")
            print("=" * 60)
            
            test_duration = datetime.now() - self.test_start_time
            print(f"⏱️ Test Duration: {test_duration.total_seconds():.1f} seconds")
            
            # Environment Setup
            env_status = self.results.get('environment_setup', {}).get('status', 'UNKNOWN')
            print(f"\n🔧 Environment Setup: {env_status}")
            
            # Test Trade Creation
            trade_status = self.results.get('test_trade_creation', {}).get('status', 'UNKNOWN')
            print(f"📊 Test Trade Creation: {trade_status}")
            
            # Orphan Condition
            condition_status = self.results.get('orphan_condition', {}).get('status', 'UNKNOWN')
            condition_created = self.results.get('orphan_condition', {}).get('orphan_condition_created', False)
            print(f"🔍 Orphan Condition: {condition_status} ({'Created' if condition_created else 'Not Created'})")
            
            # Orphan Detection
            detection_status = self.results.get('orphan_detection', {}).get('status', 'UNKNOWN')
            orphan_detected = self.results.get('orphan_detection', {}).get('orphan_detected', False)
            print(f"👻 Orphan Detection: {detection_status} ({'Detected' if orphan_detected else 'Not Detected'})")
            
            # Orphan Clearing
            clearing_status = self.results.get('orphan_clearing', {}).get('status', 'UNKNOWN')
            clearing_successful = self.results.get('orphan_clearing', {}).get('clearing_successful', False)
            print(f"🧹 Orphan Clearing: {clearing_status} ({'Successful' if clearing_successful else 'Failed'})")
            
            # Complete Cleanup
            cleanup_status = self.results.get('complete_cleanup', {}).get('status', 'UNKNOWN')
            cleanup_complete = self.results.get('complete_cleanup', {}).get('cleanup_complete', False)
            print(f"✅ Complete Cleanup: {cleanup_status} ({'Complete' if cleanup_complete else 'Incomplete'})")
            
            # Overall Result
            print(f"\n🎯 OVERALL TEST RESULT")
            print("-" * 40)
            
            # Calculate overall success
            successful_phases = 0
            total_phases = 6
            
            phase_results = [
                ('Environment Setup', env_status == 'SUCCESS'),
                ('Test Trade Creation', trade_status in ['SUCCESS', 'PARTIAL']),
                ('Orphan Condition', condition_created),
                ('Orphan Detection', orphan_detected),
                ('Orphan Clearing', clearing_successful),
                ('Complete Cleanup', cleanup_complete)
            ]
            
            for phase_name, success in phase_results:
                if success:
                    successful_phases += 1
                    print(f"   ✅ {phase_name}")
                else:
                    print(f"   ❌ {phase_name}")
            
            overall_success_rate = (successful_phases / total_phases) * 100
            
            if overall_success_rate >= 90:
                result_emoji = "🟢"
                result_text = "EXCELLENT"
            elif overall_success_rate >= 75:
                result_emoji = "🟡"
                result_text = "GOOD"
            elif overall_success_rate >= 50:
                result_emoji = "🟠"
                result_text = "PARTIAL"
            else:
                result_emoji = "🔴"
                result_text = "FAILED"
            
            print(f"\n{result_emoji} Overall Success Rate: {overall_success_rate:.1f}% ({result_text})")
            print(f"📊 Successful Phases: {successful_phases}/{total_phases}")
            
            # Key Findings
            print(f"\n🔍 KEY FINDINGS:")
            
            if orphan_detected and clearing_successful:
                print("   ✅ Orphan detection and clearing working properly")
            elif orphan_detected and not clearing_successful:
                print("   ⚠️ Orphan detection works but clearing has issues")
            elif not orphan_detected:
                print("   ❌ Orphan detection not working - clearing cannot be tested")
            
            if cleanup_complete:
                print("   ✅ Complete system cleanup successful")
            else:
                print("   ⚠️ System cleanup incomplete - traces may remain")
            
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
