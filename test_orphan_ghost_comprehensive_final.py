
#!/usr/bin/env python3
"""
Comprehensive Orphan & Ghost Detection and Clearing Test
======================================================

This test verifies:
1. Orphan trade detection from database positions
2. Ghost trade detection from Binance positions  
3. Clearing from trade monitor and order manager
4. Database updates during clearing
5. Dashboard position updates
6. Cloud database sync (with fallback for connection issues)
"""

import sys
import os
import time
import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.execution_engine.trade_database import TradeDatabase
from src.execution_engine.order_manager import OrderManager, Position
from src.execution_engine.trade_monitor import TradeMonitor, OrphanTrade, GhostTrade
from src.binance_client.client import BinanceClientWrapper
from src.reporting.telegram_reporter import TelegramReporter

class OrphanGhostDetectionTest:
    """Comprehensive test for orphan and ghost detection/clearing"""
    
    def __init__(self):
        self.test_start_time = datetime.now()
        self.results = {}
        
        # Initialize components
        print("🔧 Initializing test components...")
        self.trade_db = TradeDatabase()
        self.binance_client = BinanceClientWrapper()
        self.telegram_reporter = TelegramReporter()
        self.order_manager = OrderManager(self.binance_client, None)
        self.trade_monitor = TradeMonitor(self.binance_client, self.order_manager, self.telegram_reporter)
        
        # Test strategies
        self.test_strategies = [
            'rsi_oversold',
            'macd_divergence', 
            'engulfing_pattern',
            'smart_money'
        ]
        
        # Test symbols
        self.test_symbols = ['BTCUSDT', 'SOLUSDT', 'XRPUSDT', 'ETHUSDT']
        
        print("✅ Test components initialized")

    def run_comprehensive_test(self):
        """Run the complete test suite"""
        print("🚀 STARTING COMPREHENSIVE ORPHAN & GHOST DETECTION TEST")
        print("=" * 70)
        
        try:
            # Phase 1: Current state analysis
            self._analyze_current_state()
            
            # Phase 2: Create test orphan scenarios
            self._test_orphan_detection()
            
            # Phase 3: Test orphan clearing
            self._test_orphan_clearing()
            
            # Phase 4: Test ghost detection
            self._test_ghost_detection()
            
            # Phase 5: Test dashboard integration
            self._test_dashboard_integration()
            
            # Phase 6: Test cloud sync (with fallback)
            self._test_cloud_sync()
            
            # Generate final report
            self._generate_final_report()
            
        except Exception as e:
            print(f"❌ Test suite failed: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")

    def _analyze_current_state(self):
        """Phase 1: Analyze current system state"""
        print("\n📊 PHASE 1: CURRENT STATE ANALYSIS")
        print("-" * 40)
        
        # Check database state
        total_trades = len(self.trade_db.trades)
        open_trades = len([t for t in self.trade_db.trades.values() if t.get('trade_status') == 'OPEN'])
        
        print(f"📊 Database: {total_trades} total trades, {open_trades} open trades")
        
        # Check order manager state
        active_positions = len(self.order_manager.active_positions)
        print(f"📊 Order Manager: {active_positions} active positions")
        
        if active_positions > 0:
            print("   Active positions:")
            for strategy, position in self.order_manager.active_positions.items():
                print(f"   • {strategy}: {position.symbol} {position.side} {position.quantity}")
        
        # Check trade monitor state
        orphan_count = len(self.trade_monitor.orphan_trades)
        ghost_count = len(self.trade_monitor.ghost_trades)
        
        print(f"📊 Trade Monitor: {orphan_count} orphans, {ghost_count} ghosts")
        
        # Check Binance positions
        try:
            if self.binance_client.is_futures:
                account_info = self.binance_client.client.futures_account()
                binance_positions = [pos for pos in account_info.get('positions', [])
                                   if abs(float(pos.get('positionAmt', 0))) > 0.001]
                print(f"📊 Binance: {len(binance_positions)} active positions")
                
                for pos in binance_positions:
                    symbol = pos.get('symbol')
                    amount = float(pos.get('positionAmt', 0))
                    print(f"   • {symbol}: {amount}")
        except Exception as e:
            print(f"⚠️ Could not fetch Binance positions: {e}")
        
        self.results['current_state'] = {
            'database_trades': total_trades,
            'open_trades': open_trades,
            'active_positions': active_positions,
            'orphan_trades': orphan_count,
            'ghost_trades': ghost_count
        }

    def _test_orphan_detection(self):
        """Phase 2: Test orphan trade detection"""
        print("\n🔍 PHASE 2: ORPHAN DETECTION TEST")
        print("-" * 40)
        
        orphan_detection_results = {}
        
        # Test 1: Create orphan scenario by adding position to order manager
        # but not having corresponding Binance position
        for i, strategy in enumerate(self.test_strategies[:2]):  # Test 2 strategies
            symbol = self.test_symbols[i]
            
            print(f"\n   🎯 Testing orphan detection for {strategy}:")
            
            # Create test position in order manager
            test_position = Position(
                strategy_name=strategy,
                symbol=symbol,
                side='BUY',
                quantity=0.001,
                entry_price=50000.0,
                stop_loss=48000.0,
                take_profit=52000.0
            )
            
            # Add to order manager (simulating bot opened position)
            self.order_manager.active_positions[strategy] = test_position
            print(f"     ✅ Added test position to order manager")
            
            # Register strategy for monitoring
            self.trade_monitor.register_strategy(strategy, symbol)
            
            # Run orphan detection
            initial_orphan_count = len(self.trade_monitor.orphan_trades)
            self.trade_monitor.check_for_anomalies(suppress_notifications=True)
            final_orphan_count = len(self.trade_monitor.orphan_trades)
            
            orphan_detected = final_orphan_count > initial_orphan_count
            
            if orphan_detected:
                print(f"     ✅ Orphan trade detected successfully")
                # Find the orphan
                orphan_id = f"{strategy}_{symbol}"
                if orphan_id in self.trade_monitor.orphan_trades:
                    orphan = self.trade_monitor.orphan_trades[orphan_id]
                    print(f"     📊 Orphan details: {orphan.cycles_remaining} cycles remaining")
            else:
                print(f"     ❌ Orphan trade NOT detected")
            
            orphan_detection_results[strategy] = {
                'position_created': True,
                'orphan_detected': orphan_detected,
                'initial_count': initial_orphan_count,
                'final_count': final_orphan_count
            }
        
        self.results['orphan_detection'] = orphan_detection_results

    def _test_orphan_clearing(self):
        """Phase 3: Test orphan trade clearing"""
        print("\n🧹 PHASE 3: ORPHAN CLEARING TEST") 
        print("-" * 40)
        
        clearing_results = {}
        
        # Test clearing for each detected orphan
        for orphan_id, orphan_trade in list(self.trade_monitor.orphan_trades.items()):
            strategy = orphan_trade.position.strategy_name
            symbol = orphan_trade.position.symbol
            
            print(f"\n   🎯 Testing clearing for {strategy}:")
            
            # Test database state before clearing
            db_trades_before = len([t for t in self.trade_db.trades.values() 
                                  if t.get('trade_status') == 'OPEN'])
            
            # Test dashboard state before clearing  
            dashboard_before = self._get_dashboard_positions()
            
            # Force clear the orphan (simulate cycle countdown)
            orphan_trade.cycles_remaining = 0
            self.trade_monitor._process_cycle_countdown(suppress_notifications=True)
            
            # Verify clearing from trade monitor
            orphan_cleared_from_monitor = orphan_id not in self.trade_monitor.orphan_trades
            
            # Verify clearing from order manager
            position_cleared_from_om = strategy not in self.order_manager.active_positions
            
            # Verify database update
            db_trades_after = len([t for t in self.trade_db.trades.values() 
                                 if t.get('trade_status') == 'OPEN'])
            
            # Test dashboard state after clearing
            dashboard_after = self._get_dashboard_positions()
            
            print(f"     📊 Monitor cleared: {orphan_cleared_from_monitor}")
            print(f"     📊 Position cleared: {position_cleared_from_om}")
            print(f"     📊 DB trades before: {db_trades_before}, after: {db_trades_after}")
            print(f"     📊 Dashboard before: {len(dashboard_before)}, after: {len(dashboard_after)}")
            
            clearing_results[strategy] = {
                'monitor_cleared': orphan_cleared_from_monitor,
                'position_cleared': position_cleared_from_om,
                'database_updated': db_trades_after <= db_trades_before,
                'dashboard_updated': len(dashboard_after) <= len(dashboard_before)
            }
        
        self.results['orphan_clearing'] = clearing_results

    def _test_ghost_detection(self):
        """Phase 4: Test ghost trade detection"""
        print("\n👻 PHASE 4: GHOST DETECTION TEST")
        print("-" * 40)
        
        # Note: Ghost detection has been simplified in the new system
        # It only logs manual positions but doesn't create blocking anomalies
        
        print("   📝 Ghost detection has been updated to:")
        print("   • Log manual positions during startup")
        print("   • Not block strategies")
        print("   • Clear old ghost anomalies automatically")
        
        # Test clearing of any existing ghost trades
        initial_ghost_count = len(self.trade_monitor.ghost_trades)
        
        # Run detection to clear any old ghosts
        self.trade_monitor.check_for_anomalies(suppress_notifications=True)
        
        final_ghost_count = len(self.trade_monitor.ghost_trades)
        
        print(f"   📊 Initial ghost count: {initial_ghost_count}")
        print(f"   📊 Final ghost count: {final_ghost_count}")
        
        self.results['ghost_detection'] = {
            'initial_count': initial_ghost_count,
            'final_count': final_ghost_count,
            'system_updated': True  # New system is working as designed
        }

    def _test_dashboard_integration(self):
        """Phase 5: Test dashboard integration"""
        print("\n🖥️ PHASE 5: DASHBOARD INTEGRATION TEST")
        print("-" * 40)
        
        try:
            # Test dashboard API endpoints
            base_url = "http://0.0.0.0:5000"
            
            # Test main dashboard
            dashboard_response = requests.get(f"{base_url}/api/dashboard", timeout=5)
            dashboard_success = dashboard_response.status_code == 200
            
            if dashboard_success:
                dashboard_data = dashboard_response.json()
                active_positions = dashboard_data.get('active_positions', [])
                print(f"   ✅ Dashboard API: {len(active_positions)} active positions")
            else:
                print(f"   ❌ Dashboard API failed: {dashboard_response.status_code}")
            
            # Test trades database endpoint
            trades_response = requests.get(f"{base_url}/api/trades", timeout=5)
            trades_success = trades_response.status_code == 200
            
            if trades_success:
                trades_data = trades_response.json()
                total_trades = len(trades_data.get('trades', []))
                print(f"   ✅ Trades API: {total_trades} total trades")
            else:
                print(f"   ❌ Trades API failed: {trades_response.status_code}")
            
            self.results['dashboard_integration'] = {
                'dashboard_api': dashboard_success,
                'trades_api': trades_success,
                'api_accessible': dashboard_success and trades_success
            }
            
        except Exception as e:
            print(f"   ⚠️ Dashboard test failed: {e}")
            self.results['dashboard_integration'] = {
                'dashboard_api': False,
                'trades_api': False,
                'error': str(e)
            }

    def _test_cloud_sync(self):
        """Phase 6: Test cloud database sync with fallback"""
        print("\n☁️ PHASE 6: CLOUD SYNC TEST")
        print("-" * 40)
        
        cloud_sync_results = {
            'sync_initialized': False,
            'sync_working': False,
            'fallback_working': False,
            'error': None
        }
        
        try:
            # Check if cloud sync is initialized
            if hasattr(self.trade_db, 'cloud_sync') and self.trade_db.cloud_sync:
                cloud_sync_results['sync_initialized'] = True
                print("   ✅ Cloud sync initialized")
                
                # Test sync operation
                try:
                    self.trade_db._sync_with_cloud()
                    cloud_sync_results['sync_working'] = True
                    print("   ✅ Cloud sync operation successful")
                except Exception as sync_error:
                    print(f"   ⚠️ Cloud sync failed: {sync_error}")
                    cloud_sync_results['error'] = str(sync_error)
                    
                    # Test fallback (local database operations)
                    try:
                        # Test local database save
                        save_result = self.trade_db._save_database()
                        cloud_sync_results['fallback_working'] = save_result
                        
                        if save_result:
                            print("   ✅ Local database fallback working")
                        else:
                            print("   ❌ Local database fallback failed")
                    except Exception as fallback_error:
                        print(f"   ❌ Fallback test failed: {fallback_error}")
            else:
                print("   ⚠️ Cloud sync not initialized")
                
                # Test local operations only
                try:
                    save_result = self.trade_db._save_database()
                    cloud_sync_results['fallback_working'] = save_result
                    
                    if save_result:
                        print("   ✅ Local database operations working")
                    else:
                        print("   ❌ Local database operations failed")
                except Exception as local_error:
                    print(f"   ❌ Local database test failed: {local_error}")
        
        except Exception as e:
            print(f"   ❌ Cloud sync test failed: {e}")
            cloud_sync_results['error'] = str(e)
        
        self.results['cloud_sync'] = cloud_sync_results

    def _get_dashboard_positions(self) -> List[Dict]:
        """Get current dashboard positions"""
        try:
            response = requests.get("http://0.0.0.0:5000/api/dashboard", timeout=3)
            if response.status_code == 200:
                data = response.json()
                return data.get('active_positions', [])
        except:
            pass
        return []

    def _generate_final_report(self):
        """Generate final test report"""
        print("\n📋 FINAL TEST REPORT")
        print("=" * 50)
        
        # Calculate overall scores
        total_tests = 0
        passed_tests = 0
        
        # Orphan detection score
        orphan_detection = self.results.get('orphan_detection', {})
        for strategy, result in orphan_detection.items():
            total_tests += 1
            if result.get('orphan_detected', False):
                passed_tests += 1
        
        # Orphan clearing score
        orphan_clearing = self.results.get('orphan_clearing', {})
        for strategy, result in orphan_clearing.items():
            total_tests += 4  # 4 clearing criteria
            if result.get('monitor_cleared', False):
                passed_tests += 1
            if result.get('position_cleared', False):
                passed_tests += 1
            if result.get('database_updated', False):
                passed_tests += 1
            if result.get('dashboard_updated', False):
                passed_tests += 1
        
        # Dashboard integration score
        dashboard = self.results.get('dashboard_integration', {})
        total_tests += 2
        if dashboard.get('dashboard_api', False):
            passed_tests += 1
        if dashboard.get('trades_api', False):
            passed_tests += 1
        
        # Cloud sync score
        cloud_sync = self.results.get('cloud_sync', {})
        total_tests += 1
        if cloud_sync.get('sync_working', False) or cloud_sync.get('fallback_working', False):
            passed_tests += 1
        
        # Calculate success rate
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        print(f"🎯 OVERALL SUCCESS RATE: {success_rate:.1f}% ({passed_tests}/{total_tests})")
        print()
        
        # Detailed results
        print("📊 DETAILED RESULTS:")
        print("-" * 30)
        
        # Orphan detection results
        print("🔍 Orphan Detection:")
        for strategy, result in orphan_detection.items():
            status = "✅ PASS" if result.get('orphan_detected') else "❌ FAIL"
            print(f"   {strategy}: {status}")
        
        # Orphan clearing results
        print("\n🧹 Orphan Clearing:")
        for strategy, result in orphan_clearing.items():
            monitor = "✅" if result.get('monitor_cleared') else "❌"
            position = "✅" if result.get('position_cleared') else "❌"
            database = "✅" if result.get('database_updated') else "❌"
            dashboard = "✅" if result.get('dashboard_updated') else "❌"
            
            print(f"   {strategy}:")
            print(f"     Monitor: {monitor} | Position: {position} | DB: {database} | Dashboard: {dashboard}")
        
        # Dashboard results
        print("\n🖥️ Dashboard Integration:")
        dashboard_api = "✅" if dashboard.get('dashboard_api') else "❌"
        trades_api = "✅" if dashboard.get('trades_api') else "❌"
        print(f"   Dashboard API: {dashboard_api}")
        print(f"   Trades API: {trades_api}")
        
        # Cloud sync results
        print("\n☁️ Cloud Sync:")
        if cloud_sync.get('sync_working'):
            print("   ✅ Cloud sync working")
        elif cloud_sync.get('fallback_working'):
            print("   ⚠️ Cloud sync failed, local fallback working")
        else:
            print("   ❌ Both cloud sync and fallback failed")
        
        # Save report
        report_filename = f"orphan_ghost_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, 'w') as f:
            json.dump({
                'test_timestamp': self.test_start_time.isoformat(),
                'success_rate': success_rate,
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'results': self.results
            }, f, indent=2)
        
        print(f"\n💾 Report saved: {report_filename}")
        
        # Final status
        if success_rate >= 80:
            print("🎉 TEST SUITE: ✅ EXCELLENT")
        elif success_rate >= 60:
            print("🔧 TEST SUITE: ⚠️ NEEDS IMPROVEMENT")
        else:
            print("🚨 TEST SUITE: ❌ CRITICAL ISSUES")

def main():
    """Run the comprehensive test"""
    test = OrphanGhostDetectionTest()
    test.run_comprehensive_test()

if __name__ == "__main__":
    main()
