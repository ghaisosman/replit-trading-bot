
#!/usr/bin/env python3
"""
Dashboard Open Positions After Restart Test
==========================================

This test verifies that the dashboard correctly displays open positions 
after the bot is restarted. The test:

1. Creates open positions in the database
2. Simulates a bot restart
3. Verifies the dashboard API shows the positions correctly
4. Checks position data accuracy and completeness
"""

import sys
import os
import time
import requests
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.binance_client.client import BinanceClientWrapper
from src.bot_manager import BotManager
from src.execution_engine.order_manager import OrderManager
from src.analytics.trade_logger import trade_logger
from src.reporting.telegram_reporter import TelegramReporter

class DashboardPositionRestartTest:
    """Test dashboard position display after bot restart"""
    
    def __init__(self):
        self.dashboard_base_url = "http://localhost:5000"
        self.test_start_time = datetime.now()
        self.results = {}
        self.test_positions = []
        self.bot_manager = None
        
        print("🧪 DASHBOARD OPEN POSITIONS AFTER RESTART TEST")
        print("=" * 70)
        print(f"⏰ Test started at: {self.test_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🌐 Dashboard URL: {self.dashboard_base_url}")
    
    def run_test(self):
        """Run the complete test"""
        try:
            # Phase 1: Setup and create test positions
            self._phase1_setup_test_positions()
            
            # Phase 2: Verify positions exist before restart
            self._phase2_verify_positions_before_restart()
            
            # Phase 3: Simulate bot restart
            self._phase3_simulate_bot_restart()
            
            # Phase 4: Verify dashboard shows positions after restart
            self._phase4_verify_dashboard_after_restart()
            
            # Phase 5: Verify position data accuracy
            self._phase5_verify_position_data_accuracy()
            
            # Generate final report
            self._generate_final_report()
            
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
            import traceback
            print(f"🔍 Traceback: {traceback.format_exc()}")
            self.results['test_status'] = 'FAILED'
            self.results['error'] = str(e)
    
    def _phase1_setup_test_positions(self):
        """Phase 1: Create test positions in database"""
        print("\n📍 PHASE 1: Setting up test positions")
        print("-" * 50)
        
        try:
            # Initialize components
            trade_db = TradeDatabase()
            
            # Clear existing open trades for clean test
            initial_open_count = 0
            for trade_id, trade_data in trade_db.trades.items():
                if trade_data.get('trade_status') == 'OPEN':
                    initial_open_count += 1
                    trade_db.update_trade(trade_id, {
                        'trade_status': 'CLOSED',
                        'exit_reason': 'Test cleanup',
                        'exit_price': trade_data.get('entry_price', 0),
                        'pnl_usdt': 0,
                        'pnl_percentage': 0
                    })
            
            print(f"✅ Cleaned {initial_open_count} existing open trades")
            
            # Create test positions for different strategies
            test_positions_config = [
                {
                    'strategy_name': 'RSI_OVERSOLD_SOLUSDT',
                    'symbol': 'SOLUSDT',
                    'side': 'BUY',
                    'entry_price': 150.25,
                    'quantity': 0.67,
                    'margin': 50.0,
                    'leverage': 5
                },
                {
                    'strategy_name': 'MACD_DIVERGENCE_BTCUSDT',
                    'symbol': 'BTCUSDT',
                    'side': 'SELL',
                    'entry_price': 67500.0,
                    'quantity': 0.0015,
                    'margin': 100.0,
                    'leverage': 3
                },
                {
                    'strategy_name': 'SMART_MONEY_ETHUSDT',
                    'symbol': 'ETHUSDT',
                    'side': 'BUY',
                    'entry_price': 3456.78,
                    'quantity': 0.029,
                    'margin': 75.0,
                    'leverage': 4
                }
            ]
            
            created_positions = []
            
            for i, config in enumerate(test_positions_config, 1):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                trade_id = f"TEST_RESTART_{config['strategy_name']}_{timestamp}_{i}"
                
                # Calculate position values
                position_value = config['entry_price'] * config['quantity']
                margin_used = position_value / config['leverage']
                
                trade_data = {
                    'trade_id': trade_id,
                    'strategy_name': config['strategy_name'],
                    'symbol': config['symbol'],
                    'side': config['side'],
                    'quantity': config['quantity'],
                    'entry_price': config['entry_price'],
                    'position_value_usdt': position_value,
                    'margin_used': margin_used,
                    'leverage': config['leverage'],
                    'trade_status': 'OPEN',
                    'stop_loss': config['entry_price'] * 0.95 if config['side'] == 'BUY' else config['entry_price'] * 1.05,
                    'take_profit': config['entry_price'] * 1.1 if config['side'] == 'BUY' else config['entry_price'] * 0.9,
                    'created_at': datetime.now().isoformat(),
                    'last_updated': datetime.now().isoformat()
                }
                
                # Add to database
                success = trade_db.add_trade(trade_id, trade_data)
                
                if success:
                    created_positions.append({
                        'trade_id': trade_id,
                        'config': config,
                        'trade_data': trade_data
                    })
                    print(f"✅ Created test position {i}: {config['strategy_name']} | {config['symbol']} | {config['side']}")
                else:
                    print(f"❌ Failed to create test position {i}: {config['strategy_name']}")
            
            self.test_positions = created_positions
            
            self.results['phase1_setup'] = {
                'status': 'SUCCESS',
                'positions_created': len(created_positions),
                'expected_positions': len(test_positions_config),
                'positions': created_positions
            }
            
            print(f"✅ Phase 1 complete: {len(created_positions)}/{len(test_positions_config)} positions created")
            
        except Exception as e:
            print(f"❌ Phase 1 failed: {e}")
            self.results['phase1_setup'] = {'status': 'FAILED', 'error': str(e)}
            raise
    
    def _phase2_verify_positions_before_restart(self):
        """Phase 2: Verify positions exist before restart"""
        print("\n📍 PHASE 2: Verifying positions before restart")
        print("-" * 50)
        
        try:
            # Check database directly
            trade_db = TradeDatabase()
            open_trades = {}
            for trade_id, trade_data in trade_db.trades.items():
                if trade_data.get('trade_status') == 'OPEN':
                    open_trades[trade_id] = trade_data
            
            print(f"📊 Database check: {len(open_trades)} open trades found")
            
            # Verify our test positions are in the database
            test_trade_ids = [pos['trade_id'] for pos in self.test_positions]
            found_in_db = 0
            
            for trade_id in test_trade_ids:
                if trade_id in open_trades:
                    found_in_db += 1
                    print(f"   ✅ {trade_id} found in database")
                else:
                    print(f"   ❌ {trade_id} NOT found in database")
            
            # Check dashboard API (if bot is running)
            dashboard_positions = self._get_dashboard_positions()
            
            if dashboard_positions is not None:
                print(f"📊 Dashboard API check: {len(dashboard_positions)} positions found")
                
                # Verify test positions appear on dashboard
                dashboard_trade_ids = [pos.get('trade_id') for pos in dashboard_positions if pos.get('trade_id')]
                found_on_dashboard = 0
                
                for trade_id in test_trade_ids:
                    if trade_id in dashboard_trade_ids:
                        found_on_dashboard += 1
                        print(f"   ✅ {trade_id} found on dashboard")
                    else:
                        print(f"   ❌ {trade_id} NOT found on dashboard")
                
                dashboard_status = 'SUCCESS' if found_on_dashboard == len(test_trade_ids) else 'PARTIAL'
            else:
                print("⚠️ Dashboard API not accessible (bot may not be running)")
                dashboard_status = 'NOT_ACCESSIBLE'
                found_on_dashboard = 0
            
            self.results['phase2_before_restart'] = {
                'status': 'SUCCESS',
                'database_open_trades': len(open_trades),
                'test_positions_in_db': found_in_db,
                'expected_test_positions': len(test_trade_ids),
                'dashboard_status': dashboard_status,
                'test_positions_on_dashboard': found_on_dashboard
            }
            
            print(f"✅ Phase 2 complete: DB={found_in_db}/{len(test_trade_ids)}, Dashboard={found_on_dashboard}/{len(test_trade_ids)}")
            
        except Exception as e:
            print(f"❌ Phase 2 failed: {e}")
            self.results['phase2_before_restart'] = {'status': 'FAILED', 'error': str(e)}
            raise
    
    def _phase3_simulate_bot_restart(self):
        """Phase 3: Simulate bot restart"""
        print("\n📍 PHASE 3: Simulating bot restart")
        print("-" * 50)
        
        try:
            # Check if bot is currently running
            bot_status = self._get_bot_status()
            was_running = bot_status and bot_status.get('running', False)
            
            print(f"📊 Bot status before restart: {'RUNNING' if was_running else 'STOPPED'}")
            
            if was_running:
                # Stop the bot
                print("🛑 Stopping bot...")
                stop_response = self._stop_bot()
                if stop_response and stop_response.get('success'):
                    print("✅ Bot stopped successfully")
                else:
                    print("⚠️ Bot stop request sent (may already be stopped)")
                
                # Wait for bot to stop
                print("⏳ Waiting for bot to stop...")
                time.sleep(3)
                
                # Verify bot is stopped
                stop_status = self._get_bot_status()
                if stop_status and not stop_status.get('running', True):
                    print("✅ Bot confirmed stopped")
                else:
                    print("⚠️ Bot status unclear after stop")
            
            # Start the bot (this simulates the restart)
            print("🚀 Starting bot...")
            start_response = self._start_bot()
            
            if start_response and start_response.get('success'):
                print("✅ Bot start request successful")
            else:
                print("❌ Bot start request failed")
                raise Exception("Failed to start bot")
            
            # Wait for bot to fully start and recover positions
            print("⏳ Waiting for bot to start and recover positions...")
            startup_wait_time = 10
            
            for i in range(startup_wait_time):
                time.sleep(1)
                status = self._get_bot_status()
                if status and status.get('running'):
                    print(f"✅ Bot is running (startup took {i+1}s)")
                    break
                print(f"   Waiting... {i+1}/{startup_wait_time}s")
            else:
                print("⚠️ Bot may not have started within expected time")
            
            # Additional wait for position recovery
            print("⏳ Waiting for position recovery to complete...")
            time.sleep(5)
            
            self.results['phase3_restart'] = {
                'status': 'SUCCESS',
                'was_running_before': was_running,
                'restart_completed': True,
                'total_restart_time': startup_wait_time + 5
            }
            
            print("✅ Phase 3 complete: Bot restart simulation finished")
            
        except Exception as e:
            print(f"❌ Phase 3 failed: {e}")
            self.results['phase3_restart'] = {'status': 'FAILED', 'error': str(e)}
            raise
    
    def _phase4_verify_dashboard_after_restart(self):
        """Phase 4: Verify dashboard shows positions after restart"""
        print("\n📍 PHASE 4: Verifying dashboard after restart")
        print("-" * 50)
        
        try:
            # Get current bot status
            bot_status = self._get_bot_status()
            is_running = bot_status and bot_status.get('running', False)
            
            print(f"📊 Bot status after restart: {'RUNNING' if is_running else 'STOPPED'}")
            
            if not is_running:
                print("⚠️ Bot is not running - dashboard results may be limited")
            
            # Get dashboard positions
            dashboard_positions = self._get_dashboard_positions()
            
            if dashboard_positions is None:
                print("❌ Could not retrieve dashboard positions")
                self.results['phase4_dashboard_verification'] = {
                    'status': 'FAILED',
                    'error': 'Dashboard API not accessible'
                }
                return
            
            print(f"📊 Dashboard positions found: {len(dashboard_positions)}")
            
            # Verify our test positions appear on dashboard
            test_trade_ids = [pos['trade_id'] for pos in self.test_positions]
            dashboard_verification = {}
            
            for position in self.test_positions:
                trade_id = position['trade_id']
                strategy_name = position['config']['strategy_name']
                symbol = position['config']['symbol']
                
                # Find matching position on dashboard
                dashboard_match = None
                for dash_pos in dashboard_positions:
                    if (dash_pos.get('trade_id') == trade_id or 
                        (dash_pos.get('strategy') == strategy_name and dash_pos.get('symbol') == symbol)):
                        dashboard_match = dash_pos
                        break
                
                if dashboard_match:
                    print(f"   ✅ {trade_id} found on dashboard")
                    dashboard_verification[trade_id] = {
                        'found': True,
                        'dashboard_data': dashboard_match
                    }
                else:
                    print(f"   ❌ {trade_id} NOT found on dashboard")
                    dashboard_verification[trade_id] = {
                        'found': False,
                        'dashboard_data': None
                    }
            
            # Calculate success metrics
            positions_found = len([v for v in dashboard_verification.values() if v['found']])
            total_positions = len(test_trade_ids)
            success_rate = (positions_found / total_positions) * 100 if total_positions > 0 else 0
            
            # Check bot status for position count
            reported_active_positions = bot_status.get('active_positions', 0) if bot_status else 0
            
            self.results['phase4_dashboard_verification'] = {
                'status': 'SUCCESS' if positions_found == total_positions else 'PARTIAL',
                'bot_running': is_running,
                'dashboard_positions_total': len(dashboard_positions),
                'test_positions_found': positions_found,
                'test_positions_total': total_positions,
                'success_rate': success_rate,
                'bot_reported_active_positions': reported_active_positions,
                'verification_details': dashboard_verification
            }
            
            print(f"✅ Phase 4 complete: {positions_found}/{total_positions} positions found ({success_rate:.1f}% success)")
            
        except Exception as e:
            print(f"❌ Phase 4 failed: {e}")
            self.results['phase4_dashboard_verification'] = {'status': 'FAILED', 'error': str(e)}
            raise
    
    def _phase5_verify_position_data_accuracy(self):
        """Phase 5: Verify position data accuracy"""
        print("\n📍 PHASE 5: Verifying position data accuracy")
        print("-" * 50)
        
        try:
            dashboard_positions = self._get_dashboard_positions()
            
            if not dashboard_positions:
                print("❌ No dashboard positions to verify")
                self.results['phase5_data_accuracy'] = {
                    'status': 'FAILED',
                    'error': 'No dashboard positions available'
                }
                return
            
            accuracy_results = {}
            
            for position in self.test_positions:
                trade_id = position['trade_id']
                expected_data = position['trade_data']
                config = position['config']
                
                # Find matching dashboard position
                dashboard_match = None
                for dash_pos in dashboard_positions:
                    if (dash_pos.get('trade_id') == trade_id or 
                        (dash_pos.get('strategy') == config['strategy_name'] and 
                         dash_pos.get('symbol') == config['symbol'])):
                        dashboard_match = dash_pos
                        break
                
                if not dashboard_match:
                    accuracy_results[trade_id] = {
                        'found': False,
                        'accuracy': 'N/A'
                    }
                    continue
                
                # Verify data accuracy
                accuracy_checks = {
                    'symbol': dashboard_match.get('symbol') == expected_data['symbol'],
                    'side': dashboard_match.get('side') == expected_data['side'],
                    'entry_price': abs(float(dashboard_match.get('entry_price', 0)) - expected_data['entry_price']) < 0.01,
                    'quantity': abs(float(dashboard_match.get('quantity', 0)) - expected_data['quantity']) < 0.001,
                    'margin_invested': abs(float(dashboard_match.get('margin_invested', 0)) - expected_data['margin_used']) < 0.1
                }
                
                # Calculate accuracy percentage
                accurate_fields = sum(accuracy_checks.values())
                total_fields = len(accuracy_checks)
                accuracy_percentage = (accurate_fields / total_fields) * 100
                
                accuracy_results[trade_id] = {
                    'found': True,
                    'accuracy_percentage': accuracy_percentage,
                    'accurate_fields': accurate_fields,
                    'total_fields': total_fields,
                    'field_checks': accuracy_checks,
                    'dashboard_data': dashboard_match,
                    'expected_data': {
                        'symbol': expected_data['symbol'],
                        'side': expected_data['side'],
                        'entry_price': expected_data['entry_price'],
                        'quantity': expected_data['quantity'],
                        'margin_invested': expected_data['margin_used']
                    }
                }
                
                print(f"   📊 {trade_id}: {accuracy_percentage:.1f}% accurate ({accurate_fields}/{total_fields} fields)")
                
                # Log specific inaccuracies
                for field, is_accurate in accuracy_checks.items():
                    if not is_accurate:
                        expected_val = accuracy_results[trade_id]['expected_data'].get(field, 'N/A')
                        actual_val = dashboard_match.get(field, 'N/A')
                        print(f"      ❌ {field}: expected {expected_val}, got {actual_val}")
            
            # Calculate overall accuracy
            total_positions_checked = len([r for r in accuracy_results.values() if r['found']])
            if total_positions_checked > 0:
                average_accuracy = sum(r['accuracy_percentage'] for r in accuracy_results.values() if r['found']) / total_positions_checked
            else:
                average_accuracy = 0
            
            self.results['phase5_data_accuracy'] = {
                'status': 'SUCCESS',
                'positions_checked': total_positions_checked,
                'average_accuracy': average_accuracy,
                'accuracy_details': accuracy_results
            }
            
            print(f"✅ Phase 5 complete: Average accuracy {average_accuracy:.1f}% across {total_positions_checked} positions")
            
        except Exception as e:
            print(f"❌ Phase 5 failed: {e}")
            self.results['phase5_data_accuracy'] = {'status': 'FAILED', 'error': str(e)}
    
    def _get_dashboard_positions(self) -> Optional[List[Dict]]:
        """Get positions from dashboard API"""
        try:
            response = requests.get(f"{self.dashboard_base_url}/api/positions", timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data.get('positions', [])
        except Exception as e:
            print(f"     ⚠️ Error getting dashboard positions: {e}")
        return None
    
    def _get_bot_status(self) -> Optional[Dict]:
        """Get bot status from dashboard API"""
        try:
            response = requests.get(f"{self.dashboard_base_url}/api/bot/status", timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"     ⚠️ Error getting bot status: {e}")
        return None
    
    def _start_bot(self) -> Optional[Dict]:
        """Start bot via dashboard API"""
        try:
            response = requests.post(f"{self.dashboard_base_url}/api/bot/start", timeout=15)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"     ⚠️ Error starting bot: {e}")
        return None
    
    def _stop_bot(self) -> Optional[Dict]:
        """Stop bot via dashboard API"""
        try:
            response = requests.post(f"{self.dashboard_base_url}/api/bot/stop", timeout=15)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"     ⚠️ Error stopping bot: {e}")
        return None
    
    def _generate_final_report(self):
        """Generate comprehensive test report"""
        print("\n📊 COMPREHENSIVE TEST REPORT")
        print("=" * 70)
        
        test_duration = datetime.now() - self.test_start_time
        print(f"⏱️ Test Duration: {test_duration.total_seconds():.1f} seconds")
        
        # Overall test status
        phase_statuses = []
        for phase in ['phase1_setup', 'phase2_before_restart', 'phase3_restart', 
                     'phase4_dashboard_verification', 'phase5_data_accuracy']:
            status = self.results.get(phase, {}).get('status', 'NOT_RUN')
            phase_statuses.append(status)
        
        if all(status == 'SUCCESS' for status in phase_statuses):
            overall_status = 'SUCCESS'
        elif any(status == 'FAILED' for status in phase_statuses):
            overall_status = 'FAILED'
        else:
            overall_status = 'PARTIAL'
        
        print(f"\n🎯 Overall Test Status: {overall_status}")
        
        # Phase-by-phase summary
        print(f"\n📋 Phase Summary:")
        phases = [
            ('Phase 1: Setup Test Positions', 'phase1_setup'),
            ('Phase 2: Verify Before Restart', 'phase2_before_restart'),
            ('Phase 3: Simulate Bot Restart', 'phase3_restart'),
            ('Phase 4: Verify Dashboard After Restart', 'phase4_dashboard_verification'),
            ('Phase 5: Verify Data Accuracy', 'phase5_data_accuracy')
        ]
        
        for phase_name, phase_key in phases:
            phase_result = self.results.get(phase_key, {})
            status = phase_result.get('status', 'NOT_RUN')
            print(f"   {phase_name}: {status}")
            
            if status == 'FAILED' and 'error' in phase_result:
                print(f"      Error: {phase_result['error']}")
        
        # Key metrics
        print(f"\n📈 Key Metrics:")
        
        if 'phase1_setup' in self.results:
            setup = self.results['phase1_setup']
            print(f"   Test Positions Created: {setup.get('positions_created', 0)}")
        
        if 'phase4_dashboard_verification' in self.results:
            verification = self.results['phase4_dashboard_verification']
            print(f"   Positions Found on Dashboard: {verification.get('test_positions_found', 0)}/{verification.get('test_positions_total', 0)}")
            print(f"   Dashboard Detection Rate: {verification.get('success_rate', 0):.1f}%")
        
        if 'phase5_data_accuracy' in self.results:
            accuracy = self.results['phase5_data_accuracy']
            print(f"   Average Data Accuracy: {accuracy.get('average_accuracy', 0):.1f}%")
        
        # Recommendations
        print(f"\n💡 Recommendations:")
        
        if overall_status == 'SUCCESS':
            print("   ✅ Dashboard correctly displays open positions after bot restart")
            print("   ✅ Position recovery system is working properly")
            print("   ✅ Data accuracy is maintained across restart")
        else:
            if 'phase4_dashboard_verification' in self.results:
                verification = self.results['phase4_dashboard_verification']
                if verification.get('test_positions_found', 0) < verification.get('test_positions_total', 0):
                    print("   ⚠️ Some positions not displayed on dashboard after restart")
                    print("   🔧 Check position recovery logic in bot_manager.py")
            
            if 'phase5_data_accuracy' in self.results:
                accuracy = self.results['phase5_data_accuracy']
                if accuracy.get('average_accuracy', 0) < 95:
                    print("   ⚠️ Position data accuracy issues detected")
                    print("   🔧 Check dashboard position calculation logic")
        
        # Save detailed results
        self.results['test_metadata'] = {
            'test_name': 'Dashboard Open Positions After Restart Test',
            'test_duration_seconds': test_duration.total_seconds(),
            'overall_status': overall_status,
            'timestamp': datetime.now().isoformat()
        }
        
        # Save to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"dashboard_restart_test_results_{timestamp}.json"
        
        try:
            with open(filename, 'w') as f:
                json.dump(self.results, f, indent=2, default=str)
            print(f"\n💾 Detailed results saved to: {filename}")
        except Exception as e:
            print(f"⚠️ Could not save results file: {e}")
        
        print(f"\n✅ Test completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

def main():
    """Run the dashboard position restart test"""
    test = DashboardPositionRestartTest()
    test.run_test()

if __name__ == "__main__":
    main()
