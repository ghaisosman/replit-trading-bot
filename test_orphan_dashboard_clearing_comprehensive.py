
#!/usr/bin/env python3
"""
Comprehensive Orphan Trade Dashboard Clearing Test
==================================================

Tests that orphan trades are properly cleared from the dashboard for all strategies:
1. RSI Oversold Strategy
2. MACD Divergence Strategy  
3. Engulfing Pattern Strategy
4. Smart Money Strategy

This test verifies:
- Orphan trade detection creates dashboard entries
- Dashboard shows orphan trades correctly
- Orphan clearing removes trades from dashboard
- All strategies behave consistently
- Web dashboard API reflects changes immediately
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

class OrphanDashboardClearingTest:
    """Comprehensive test for orphan trade dashboard clearing"""
    
    def __init__(self):
        self.test_start_time = datetime.now()
        self.strategies = ['rsi_oversold', 'macd_divergence', 'engulfing_pattern', 'smart_money']
        self.results = {}
        
        # Initialize components
        self.trade_db = TradeDatabase()
        self.binance_client = BinanceClientWrapper()
        self.order_manager = OrderManager(self.binance_client, None)  # No strategy processor needed for test
        self.telegram_reporter = TelegramReporter()
        self.trade_monitor = TradeMonitor(self.binance_client, self.order_manager, self.telegram_reporter)
        
        # Dashboard API endpoint (assuming standard Flask development server)
        self.dashboard_base_url = "http://localhost:5000"
        
        print("🧪 COMPREHENSIVE ORPHAN DASHBOARD CLEARING TEST")
        print("=" * 70)
        print(f"⏰ Test started: {self.test_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🎯 Testing strategies: {', '.join(self.strategies)}")
        
    def run_test(self):
        """Execute complete test sequence"""
        try:
            print("\n🔧 TEST 1: Environment Setup")
            self._setup_test_environment()
            
            print("\n👻 TEST 2: Create Orphan Trades")
            self._create_orphan_trades()
            
            print("\n📊 TEST 3: Verify Dashboard Shows Orphans")
            self._verify_dashboard_shows_orphans()
            
            print("\n🧹 TEST 4: Clear Orphan Trades")
            self._clear_orphan_trades()
            
            print("\n✅ TEST 5: Verify Dashboard Clearing")
            self._verify_dashboard_clearing()
            
            print("\n📈 TEST 6: Final Verification")
            self._final_verification()
            
            print("\n📊 GENERATING TEST REPORT")
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
            
            # Clear any existing active positions in order manager
            self.order_manager.active_positions.clear()
            print("   ✅ Cleared order manager positions")
            
            # Register strategies with trade monitor
            strategy_symbols = {
                'rsi_oversold': 'SOLUSDT',
                'macd_divergence': 'BTCUSDT', 
                'engulfing_pattern': 'ETHUSDT',
                'smart_money': 'XRPUSDT'
            }
            
            for strategy, symbol in strategy_symbols.items():
                self.trade_monitor.register_strategy(strategy, symbol)
                print(f"   📈 Registered {strategy} for {symbol}")
            
            # Test dashboard connectivity
            dashboard_available = self._test_dashboard_connectivity()
            if dashboard_available:
                print("   ✅ Dashboard connectivity verified")
            else:
                print("   ⚠️ Dashboard not available - will test core functionality only")
            
            self.results['environment_setup'] = {
                'status': 'SUCCESS',
                'dashboard_available': dashboard_available,
                'strategies_registered': len(strategy_symbols),
                'timestamp': datetime.now().isoformat()
            }
            
            print("✅ Environment setup completed")
            
        except Exception as e:
            print(f"❌ Environment setup failed: {e}")
            self.results['environment_setup'] = {'status': 'ERROR', 'error': str(e)}
    
    def _create_orphan_trades(self):
        """Create orphan trades for all strategies"""
        try:
            print("👻 Creating orphan trades for all strategies...")
            
            orphan_creation_results = {}
            
            # Strategy configurations for creating realistic orphan trades
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
            
            for strategy in self.strategies:
                print(f"\n   🎯 Creating orphan trade for {strategy}:")
                
                config = strategy_configs[strategy]
                
                # Create position in order manager (simulating bot opened position)
                position = Position(
                    symbol=config['symbol'],
                    side=config['side'],
                    quantity=config['quantity'],
                    entry_price=config['entry_price'],
                    timestamp=datetime.now()
                )
                
                # Add to order manager's active positions
                self.order_manager.active_positions[strategy] = position
                print(f"     ✅ Created position: {config['symbol']} {config['side']} {config['quantity']} @ ${config['entry_price']}")
                
                # Create corresponding database record (for dashboard display)
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
                    'created_at': datetime.now().isoformat(),
                    'last_updated': datetime.now().isoformat()
                }
                
                # Add to database
                db_success = self.trade_db.add_trade(trade_id, trade_data)
                if db_success:
                    print(f"     ✅ Added database record: {trade_id}")
                else:
                    print(f"     ❌ Failed to add database record: {trade_id}")
                
                # Manually create orphan trade (simulating detection)
                orphan_trade = OrphanTrade(
                    position=position,
                    detected_at=datetime.now(),
                    cycles_remaining=5,  # Give enough cycles for testing
                    detection_notified=False,
                    clearing_notified=False
                )
                
                orphan_id = f"{strategy}_{config['symbol']}"
                self.trade_monitor.orphan_trades[orphan_id] = orphan_trade
                print(f"     ✅ Created orphan trade: {orphan_id}")
                
                orphan_creation_results[strategy] = {
                    'position_created': True,
                    'database_record_added': db_success,
                    'orphan_trade_created': True,
                    'orphan_id': orphan_id,
                    'trade_id': trade_id,
                    'config': config
                }
            
            self.results['orphan_creation'] = {
                'status': 'SUCCESS',
                'strategies_tested': len(self.strategies),
                'successful_creations': len([r for r in orphan_creation_results.values() if r['orphan_trade_created']]),
                'results': orphan_creation_results,
                'timestamp': datetime.now().isoformat()
            }
            
            print(f"\n✅ Orphan trade creation completed: {len(orphan_creation_results)} orphans created")
            
        except Exception as e:
            print(f"❌ Orphan trade creation failed: {e}")
            self.results['orphan_creation'] = {'status': 'ERROR', 'error': str(e)}
    
    def _verify_dashboard_shows_orphans(self):
        """Verify dashboard correctly shows orphan trades"""
        try:
            print("📊 Verifying dashboard shows orphan trades...")
            
            dashboard_verification = {}
            
            if not self.results.get('environment_setup', {}).get('dashboard_available', False):
                print("   ⚠️ Dashboard not available - skipping dashboard verification")
                self.results['dashboard_verification'] = {
                    'status': 'SKIPPED',
                    'reason': 'Dashboard not available'
                }
                return
            
            # Wait a moment for dashboard to update
            print("   ⏳ Waiting for dashboard to update...")
            time.sleep(2)
            
            # Check active positions endpoint
            positions_response = self._get_dashboard_positions()
            if positions_response:
                print(f"   📊 Dashboard shows {len(positions_response)} active positions")
                
                # Verify each strategy's orphan appears
                for strategy in self.strategies:
                    strategy_found = False
                    for position in positions_response:
                        if position.get('strategy') == strategy:
                            strategy_found = True
                            print(f"     ✅ {strategy} orphan visible on dashboard")
                            break
                    
                    if not strategy_found:
                        print(f"     ❌ {strategy} orphan NOT visible on dashboard")
                    
                    dashboard_verification[strategy] = {
                        'visible_on_dashboard': strategy_found,
                        'position_data': next((p for p in positions_response if p.get('strategy') == strategy), None)
                    }
            else:
                print("   ❌ Could not retrieve dashboard positions")
                for strategy in self.strategies:
                    dashboard_verification[strategy] = {
                        'visible_on_dashboard': False,
                        'error': 'Could not retrieve positions'
                    }
            
            # Check bot status endpoint
            status_response = self._get_dashboard_status()
            if status_response:
                active_positions_count = status_response.get('active_positions', 0)
                print(f"   📊 Dashboard reports {active_positions_count} active positions")
                
                expected_count = len(self.strategies)
                if active_positions_count == expected_count:
                    print(f"     ✅ Position count matches expected ({expected_count})")
                else:
                    print(f"     ❌ Position count mismatch: expected {expected_count}, got {active_positions_count}")
            
            self.results['dashboard_verification'] = {
                'status': 'SUCCESS',
                'verification_results': dashboard_verification,
                'positions_retrieved': positions_response is not None,
                'status_retrieved': status_response is not None,
                'timestamp': datetime.now().isoformat()
            }
            
            print("✅ Dashboard verification completed")
            
        except Exception as e:
            print(f"❌ Dashboard verification failed: {e}")
            self.results['dashboard_verification'] = {'status': 'ERROR', 'error': str(e)}
    
    def _clear_orphan_trades(self):
        """Clear all orphan trades and verify clearing mechanism"""
        try:
            print("🧹 Clearing orphan trades...")
            
            clearing_results = {}
            
            # Process each orphan trade individually
            for strategy in self.strategies:
                print(f"\n   🎯 Clearing orphan trade for {strategy}:")
                
                orphan_id = f"{strategy}_{self.trade_monitor.strategy_symbols.get(strategy, 'UNKNOWN')}"
                
                if orphan_id in self.trade_monitor.orphan_trades:
                    orphan_trade = self.trade_monitor.orphan_trades[orphan_id]
                    
                    print(f"     🔍 Found orphan: {orphan_id} (cycles: {orphan_trade.cycles_remaining})")
                    
                    # Force cycles to 0 to trigger immediate clearing
                    orphan_trade.cycles_remaining = 0
                    print(f"     ⏱️ Set cycles to 0 for immediate clearing")
                    
                    # Process cycle countdown to trigger clearing
                    initial_count = len(self.trade_monitor.orphan_trades)
                    self.trade_monitor._process_cycle_countdown(suppress_notifications=True)
                    final_count = len(self.trade_monitor.orphan_trades)
                    
                    # Check if orphan was cleared
                    if orphan_id not in self.trade_monitor.orphan_trades:
                        print(f"     ✅ Orphan trade cleared successfully")
                        
                        # Verify position was cleared from order manager
                        if strategy not in self.order_manager.active_positions:
                            print(f"     ✅ Position cleared from order manager")
                            position_cleared = True
                        else:
                            print(f"     ⚠️ Position still exists in order manager")
                            position_cleared = False
                        
                        # Update database record to closed
                        creation_results = self.results.get('orphan_creation', {}).get('results', {})
                        if strategy in creation_results:
                            trade_id = creation_results[strategy].get('trade_id')
                            if trade_id:
                                self.trade_db.update_trade(trade_id, {
                                    'trade_status': 'CLOSED',
                                    'exit_reason': 'Orphan trade cleared',
                                    'exit_price': creation_results[strategy]['config']['entry_price'],
                                    'pnl_usdt': 0,
                                    'pnl_percentage': 0
                                })
                                print(f"     ✅ Database record updated to CLOSED")
                        
                        clearing_results[strategy] = {
                            'orphan_cleared': True,
                            'position_cleared': position_cleared,
                            'database_updated': True,
                            'cycles_before': 0,
                            'cycles_after': 0
                        }
                    else:
                        print(f"     ❌ Orphan trade NOT cleared")
                        clearing_results[strategy] = {
                            'orphan_cleared': False,
                            'cycles_remaining': orphan_trade.cycles_remaining,
                            'error': 'Clearing mechanism failed'
                        }
                else:
                    print(f"     ❌ Orphan trade not found: {orphan_id}")
                    clearing_results[strategy] = {
                        'orphan_cleared': False,
                        'error': f'Orphan trade not found: {orphan_id}'
                    }
            
            self.results['orphan_clearing'] = {
                'status': 'SUCCESS',
                'clearing_results': clearing_results,
                'total_cleared': len([r for r in clearing_results.values() if r.get('orphan_cleared', False)]),
                'total_strategies': len(self.strategies),
                'timestamp': datetime.now().isoformat()
            }
            
            print(f"\n✅ Orphan clearing completed: {self.results['orphan_clearing']['total_cleared']}/{len(self.strategies)} cleared")
            
        except Exception as e:
            print(f"❌ Orphan clearing failed: {e}")
            self.results['orphan_clearing'] = {'status': 'ERROR', 'error': str(e)}
    
    def _verify_dashboard_clearing(self):
        """Verify dashboard no longer shows cleared orphan trades"""
        try:
            print("✅ Verifying dashboard clearing...")
            
            if not self.results.get('environment_setup', {}).get('dashboard_available', False):
                print("   ⚠️ Dashboard not available - skipping dashboard clearing verification")
                self.results['dashboard_clearing_verification'] = {
                    'status': 'SKIPPED',
                    'reason': 'Dashboard not available'
                }
                return
            
            # Wait for dashboard to update after clearing
            print("   ⏳ Waiting for dashboard to update after clearing...")
            time.sleep(3)
            
            clearing_verification = {}
            
            # Check active positions endpoint
            positions_response = self._get_dashboard_positions()
            if positions_response:
                print(f"   📊 Dashboard now shows {len(positions_response)} active positions")
                
                # Verify each strategy's orphan is no longer visible
                for strategy in self.strategies:
                    strategy_found = False
                    for position in positions_response:
                        if position.get('strategy') == strategy:
                            strategy_found = True
                            print(f"     ❌ {strategy} still visible on dashboard (should be cleared)")
                            break
                    
                    if not strategy_found:
                        print(f"     ✅ {strategy} no longer visible on dashboard")
                    
                    clearing_verification[strategy] = {
                        'cleared_from_dashboard': not strategy_found,
                        'position_data': next((p for p in positions_response if p.get('strategy') == strategy), None)
                    }
            else:
                print("   ❌ Could not retrieve dashboard positions for verification")
                for strategy in self.strategies:
                    clearing_verification[strategy] = {
                        'cleared_from_dashboard': 'unknown',
                        'error': 'Could not retrieve positions'
                    }
            
            # Check bot status endpoint
            status_response = self._get_dashboard_status()
            if status_response:
                active_positions_count = status_response.get('active_positions', 0)
                print(f"   📊 Dashboard reports {active_positions_count} active positions")
                
                if active_positions_count == 0:
                    print(f"     ✅ Position count is 0 (all orphans cleared)")
                else:
                    print(f"     ⚠️ Position count is {active_positions_count} (expected 0)")
            
            # Calculate success rate
            successfully_cleared = len([r for r in clearing_verification.values() if r.get('cleared_from_dashboard') == True])
            total_strategies = len(self.strategies)
            success_rate = (successfully_cleared / total_strategies) * 100 if total_strategies > 0 else 0
            
            self.results['dashboard_clearing_verification'] = {
                'status': 'SUCCESS',
                'clearing_verification': clearing_verification,
                'successfully_cleared': successfully_cleared,
                'total_strategies': total_strategies,
                'success_rate': success_rate,
                'positions_retrieved': positions_response is not None,
                'final_position_count': len(positions_response) if positions_response else 0,
                'timestamp': datetime.now().isoformat()
            }
            
            print(f"✅ Dashboard clearing verification completed: {success_rate:.1f}% success rate")
            
        except Exception as e:
            print(f"❌ Dashboard clearing verification failed: {e}")
            self.results['dashboard_clearing_verification'] = {'status': 'ERROR', 'error': str(e)}
    
    def _final_verification(self):
        """Final comprehensive verification"""
        try:
            print("📈 Running final verification...")
            
            # Verify trade monitor state
            orphan_count = len(self.trade_monitor.orphan_trades)
            print(f"   📊 Trade monitor orphan count: {orphan_count}")
            
            # Verify order manager state  
            position_count = len(self.order_manager.active_positions)
            print(f"   📊 Order manager position count: {position_count}")
            
            # Verify database state
            open_trades_count = 0
            for trade_id, trade_data in self.trade_db.trades.items():
                if trade_data.get('trade_status') == 'OPEN':
                    open_trades_count += 1
            print(f"   📊 Database open trades count: {open_trades_count}")
            
            # Overall verification
            all_systems_clean = (orphan_count == 0 and position_count == 0 and open_trades_count == 0)
            
            if all_systems_clean:
                print("   ✅ All systems clean - no orphan trades remaining")
            else:
                print("   ⚠️ Some orphan traces remain in system")
            
            self.results['final_verification'] = {
                'status': 'SUCCESS',
                'orphan_count': orphan_count,
                'position_count': position_count,
                'open_trades_count': open_trades_count,
                'all_systems_clean': all_systems_clean,
                'timestamp': datetime.now().isoformat()
            }
            
            print("✅ Final verification completed")
            
        except Exception as e:
            print(f"❌ Final verification failed: {e}")
            self.results['final_verification'] = {'status': 'ERROR', 'error': str(e)}
    
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
    
    def _get_dashboard_status(self) -> Optional[Dict]:
        """Get bot status from dashboard API"""
        try:
            response = requests.get(f"{self.dashboard_base_url}/api/bot/status", timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"     ⚠️ Error getting dashboard status: {e}")
        return None
    
    def _generate_test_report(self):
        """Generate comprehensive test report"""
        try:
            print("📊 COMPREHENSIVE TEST REPORT")
            print("=" * 70)
            
            test_duration = datetime.now() - self.test_start_time
            print(f"⏱️ Test Duration: {test_duration.total_seconds():.1f} seconds")
            
            # Environment Setup
            env_status = self.results.get('environment_setup', {}).get('status', 'UNKNOWN')
            print(f"\n🔧 Environment Setup: {env_status}")
            if env_status == 'SUCCESS':
                dashboard_available = self.results['environment_setup'].get('dashboard_available', False)
                print(f"   📊 Dashboard Available: {'✅ Yes' if dashboard_available else '❌ No'}")
                print(f"   📈 Strategies Registered: {self.results['environment_setup'].get('strategies_registered', 0)}")
            
            # Orphan Creation
            creation_status = self.results.get('orphan_creation', {}).get('status', 'UNKNOWN')
            print(f"\n👻 Orphan Creation: {creation_status}")
            if creation_status == 'SUCCESS':
                successful = self.results['orphan_creation'].get('successful_creations', 0)
                total = self.results['orphan_creation'].get('strategies_tested', 0)
                print(f"   📊 Success Rate: {successful}/{total} ({(successful/total)*100:.1f}%)")
            
            # Dashboard Verification
            dash_verify_status = self.results.get('dashboard_verification', {}).get('status', 'UNKNOWN')
            print(f"\n📊 Dashboard Verification: {dash_verify_status}")
            if dash_verify_status == 'SUCCESS':
                verification_results = self.results['dashboard_verification'].get('verification_results', {})
                visible_count = len([r for r in verification_results.values() if r.get('visible_on_dashboard', False)])
                print(f"   📈 Orphans Visible: {visible_count}/{len(self.strategies)}")
            
            # Orphan Clearing  
            clearing_status = self.results.get('orphan_clearing', {}).get('status', 'UNKNOWN')
            print(f"\n🧹 Orphan Clearing: {clearing_status}")
            if clearing_status == 'SUCCESS':
                cleared = self.results['orphan_clearing'].get('total_cleared', 0)
                total = self.results['orphan_clearing'].get('total_strategies', 0)
                print(f"   📊 Clearing Rate: {cleared}/{total} ({(cleared/total)*100:.1f}%)")
            
            # Dashboard Clearing Verification
            clear_verify_status = self.results.get('dashboard_clearing_verification', {}).get('status', 'UNKNOWN')
            print(f"\n✅ Dashboard Clearing Verification: {clear_verify_status}")
            if clear_verify_status == 'SUCCESS':
                success_rate = self.results['dashboard_clearing_verification'].get('success_rate', 0)
                final_count = self.results['dashboard_clearing_verification'].get('final_position_count', 0)
                print(f"   📊 Clearing Success Rate: {success_rate:.1f}%")
                print(f"   📈 Final Position Count: {final_count}")
            
            # Final Verification
            final_status = self.results.get('final_verification', {}).get('status', 'UNKNOWN')
            print(f"\n📈 Final Verification: {final_status}")
            if final_status == 'SUCCESS':
                all_clean = self.results['final_verification'].get('all_systems_clean', False)
                print(f"   🧹 All Systems Clean: {'✅ Yes' if all_clean else '❌ No'}")
            
            # Overall Test Result
            print(f"\n🎯 OVERALL TEST RESULT")
            print("-" * 50)
            
            # Calculate overall success
            successful_phases = 0
            total_phases = 0
            
            for phase_name, phase_data in self.results.items():
                if isinstance(phase_data, dict) and 'status' in phase_data:
                    total_phases += 1
                    if phase_data['status'] == 'SUCCESS':
                        successful_phases += 1
            
            overall_success_rate = (successful_phases / total_phases) * 100 if total_phases > 0 else 0
            
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
            
            print(f"{result_emoji} Overall Success Rate: {overall_success_rate:.1f}% ({result_text})")
            print(f"📊 Successful Phases: {successful_phases}/{total_phases}")
            
            # Key Findings
            print(f"\n🔍 KEY FINDINGS:")
            if self.results.get('dashboard_clearing_verification', {}).get('success_rate', 0) == 100:
                print("   ✅ Dashboard perfectly reflects orphan trade clearing")
            elif self.results.get('dashboard_clearing_verification', {}).get('success_rate', 0) > 0:
                print("   ⚠️ Dashboard partially reflects orphan trade clearing")
            else:
                print("   ❌ Dashboard does not reflect orphan trade clearing")
            
            if self.results.get('final_verification', {}).get('all_systems_clean', False):
                print("   ✅ All systems properly cleaned after orphan clearing")
            else:
                print("   ⚠️ Some orphan traces remain in system")
            
            # Save detailed results
            report_filename = f"orphan_dashboard_clearing_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(report_filename, 'w') as f:
                json.dump(self.results, f, indent=2, default=str)
            print(f"\n💾 Detailed results saved to: {report_filename}")
            
            print("\n" + "=" * 70)
            print("🧪 ORPHAN DASHBOARD CLEARING TEST COMPLETED")
            
        except Exception as e:
            print(f"❌ Report generation failed: {e}")

def main():
    """Run the comprehensive orphan dashboard clearing test"""
    test = OrphanDashboardClearingTest()
    test.run_test()

if __name__ == "__main__":
    main()
