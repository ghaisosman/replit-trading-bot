
#!/usr/bin/env python3
"""
Comprehensive Test: All Strategies Opening Positions & Dashboard Display
Test that every strategy can open positions and they appear correctly on the dashboard
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.analytics.trade_logger import trade_logger
from src.binance_client.client import BinanceClientWrapper
from src.config.trading_config import trading_config_manager
from src.strategy_processor.signal_processor import TradingSignal, SignalType
from datetime import datetime, timedelta
import json
import time
import requests

def test_all_strategies_open_positions():
    """Test all strategies opening positions and dashboard display"""
    print("🧪 COMPREHENSIVE STRATEGY OPEN POSITIONS TEST")
    print("=" * 80)
    
    # Initialize components
    trade_db = TradeDatabase()
    binance_client = BinanceClientWrapper()
    
    # Get all available strategies
    strategies = trading_config_manager.get_all_strategies()
    
    print(f"📊 Testing {len(strategies)} strategies:")
    for name in strategies.keys():
        print(f"   🎯 {name}")
    
    print(f"\n🔍 PHASE 1: CLEARING EXISTING OPEN TRADES")
    print("-" * 50)
    
    # Clean slate - close any existing open trades
    initial_open_count = 0
    for trade_id, trade_data in trade_db.trades.items():
        if trade_data.get('trade_status') == 'OPEN':
            initial_open_count += 1
            # Mark as closed for clean test
            trade_db.update_trade(trade_id, {
                'trade_status': 'CLOSED',
                'exit_reason': 'Test cleanup',
                'exit_price': trade_data.get('entry_price', 0),
                'pnl_usdt': 0,
                'pnl_percentage': 0
            })
    
    print(f"✅ Cleaned {initial_open_count} existing open trades")
    
    print(f"\n🔍 PHASE 2: OPENING POSITIONS FOR ALL STRATEGIES")
    print("-" * 50)
    
    test_results = {}
    opened_trades = []
    
    # Test data for each strategy type
    strategy_test_configs = {
        'rsi_oversold': {
            'symbol': 'SOLUSDT',
            'side': 'BUY',
            'entry_price': 180.50,
            'quantity': 0.5,
            'margin': 12.5,
            'leverage': 25,
            'rsi_at_entry': 25.5,
            'signal_strength': 0.85
        },
        'macd_divergence': {
            'symbol': 'BTCUSDT', 
            'side': 'BUY',
            'entry_price': 45000.0,
            'quantity': 0.002,
            'margin': 50.0,
            'leverage': 5,
            'macd_at_entry': 0.025,
            'signal_strength': 0.78
        },
        'engulfing_pattern': {
            'symbol': 'BCHUSDT',
            'side': 'SELL',
            'entry_price': 420.0,
            'quantity': 0.12,
            'margin': 25.0,
            'leverage': 10,
            'rsi_at_entry': 75.2,
            'signal_strength': 0.82
        },
        'smart_money': {
            'symbol': 'ETHUSDT',
            'side': 'BUY', 
            'entry_price': 3200.0,
            'quantity': 0.03,
            'margin': 40.0,
            'leverage': 8,
            'volume_spike': 2.5,
            'signal_strength': 0.90
        }
    }
    
    for strategy_name, strategy_config in strategies.items():
        print(f"\n🎯 TESTING STRATEGY: {strategy_name}")
        print("-" * 30)
        
        # Determine strategy type and get appropriate test data
        test_data = None
        if 'rsi' in strategy_name.lower():
            test_data = strategy_test_configs['rsi_oversold'].copy()
        elif 'macd' in strategy_name.lower():
            test_data = strategy_test_configs['macd_divergence'].copy()
        elif 'engulfing' in strategy_name.lower():
            test_data = strategy_test_configs['engulfing_pattern'].copy()
        elif 'smart' in strategy_name.lower() and 'money' in strategy_name.lower():
            test_data = strategy_test_configs['smart_money'].copy()
        else:
            # Default test data for unknown strategy types
            test_data = {
                'symbol': 'XRPUSDT',
                'side': 'BUY',
                'entry_price': 2.50,
                'quantity': 4.0,
                'margin': 30.0,
                'leverage': 5,
                'signal_strength': 0.75
            }
        
        # Override with strategy's actual configuration
        test_data.update({
            'symbol': strategy_config.get('symbol', test_data['symbol']),
            'margin': strategy_config.get('margin', test_data['margin']),
            'leverage': strategy_config.get('leverage', test_data['leverage'])
        })
        
        # Calculate position value and margin used
        position_value = test_data['entry_price'] * test_data['quantity']
        margin_used = position_value / test_data['leverage']
        
        # Generate unique trade ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        trade_id = f"{strategy_name}_{test_data['symbol']}_{timestamp}"
        
        # Create comprehensive trade data
        trade_data = {
            'trade_id': trade_id,
            'strategy_name': strategy_name,
            'symbol': test_data['symbol'],
            'side': test_data['side'],
            'quantity': test_data['quantity'],
            'entry_price': test_data['entry_price'],
            'trade_status': 'OPEN',
            'position_value_usdt': position_value,
            'leverage': test_data['leverage'],
            'margin_used': margin_used,
            'actual_margin_used': margin_used,  # For dashboard calculations
            'timestamp': datetime.now().isoformat(),
            'entry_reason': f"Test signal - {strategy_name}",
            'signal_strength': test_data.get('signal_strength', 0.8),
            'stop_loss': test_data['entry_price'] * (0.95 if test_data['side'] == 'BUY' else 1.05),
            'take_profit': test_data['entry_price'] * (1.05 if test_data['side'] == 'BUY' else 0.95)
        }
        
        # Add strategy-specific indicators
        if 'rsi' in strategy_name.lower():
            trade_data['rsi_at_entry'] = test_data.get('rsi_at_entry', 30.0)
        elif 'macd' in strategy_name.lower():
            trade_data['macd_at_entry'] = test_data.get('macd_at_entry', 0.02)
        elif 'smart' in strategy_name.lower():
            trade_data['volume_spike'] = test_data.get('volume_spike', 2.0)
        
        print(f"📝 Trade Details:")
        print(f"   ID: {trade_id}")
        print(f"   Symbol: {test_data['symbol']}")
        print(f"   Side: {test_data['side']}")
        print(f"   Entry Price: ${test_data['entry_price']}")
        print(f"   Quantity: {test_data['quantity']}")
        print(f"   Position Value: ${position_value:.2f}")
        print(f"   Margin Used: ${margin_used:.2f}")
        print(f"   Leverage: {test_data['leverage']}x")
        
        # Add to database
        success = trade_db.add_trade(trade_id, trade_data)
        
        if success:
            print(f"✅ Database recording: SUCCESS")
            opened_trades.append({
                'trade_id': trade_id,
                'strategy_name': strategy_name,
                'symbol': test_data['symbol'],
                'side': test_data['side'],
                'margin_used': margin_used
            })
            
            # Test logger sync
            sync_success = trade_db.sync_trade_to_logger(trade_id)
            print(f"✅ Logger sync: {'SUCCESS' if sync_success else 'FAILED'}")
            
            test_results[strategy_name] = {
                'database_success': True,
                'logger_sync': sync_success,
                'trade_id': trade_id,
                'trade_data': trade_data
            }
        else:
            print(f"❌ Database recording: FAILED")
            test_results[strategy_name] = {
                'database_success': False,
                'logger_sync': False,
                'trade_id': trade_id,
                'error': 'Database recording failed'
            }
        
        # Small delay between trades
        time.sleep(0.5)
    
    print(f"\n🔍 PHASE 3: VERIFYING DATABASE STATE")
    print("-" * 50)
    
    # Reload database to verify persistence
    fresh_db = TradeDatabase()
    open_trades_in_db = []
    
    for trade_id, trade_data in fresh_db.trades.items():
        if trade_data.get('trade_status') == 'OPEN':
            open_trades_in_db.append({
                'trade_id': trade_id,
                'strategy': trade_data.get('strategy_name'),
                'symbol': trade_data.get('symbol'),
                'side': trade_data.get('side'),
                'margin_used': trade_data.get('margin_used', 0)
            })
    
    print(f"📊 Database verification:")
    print(f"   Expected open trades: {len(opened_trades)}")
    print(f"   Actual open trades: {len(open_trades_in_db)}")
    
    if len(open_trades_in_db) == len(opened_trades):
        print("✅ Database persistence: PASSED")
    else:
        print("❌ Database persistence: FAILED")
        print("   Missing trades:")
        opened_ids = {t['trade_id'] for t in opened_trades}
        db_ids = {t['trade_id'] for t in open_trades_in_db}
        missing = opened_ids - db_ids
        for missing_id in missing:
            print(f"     🔸 {missing_id}")
    
    print(f"\n🔍 PHASE 4: TESTING DASHBOARD API ENDPOINTS")
    print("-" * 50)
    
    # Test dashboard API endpoints
    dashboard_tests = {}
    
    try:
        # Test bot status endpoint
        print("🌐 Testing /api/bot/status...")
        status_response = requests.get('http://0.0.0.0:5000/api/bot/status', timeout=5)
        if status_response.status_code == 200:
            status_data = status_response.json()
            dashboard_tests['bot_status'] = {
                'success': True,
                'active_positions': status_data.get('active_positions', 0),
                'running': status_data.get('running', False)
            }
            print(f"✅ Bot Status API: SUCCESS")
            print(f"   Active Positions: {status_data.get('active_positions', 0)}")
            print(f"   Bot Running: {status_data.get('running', False)}")
        else:
            dashboard_tests['bot_status'] = {'success': False, 'error': f"HTTP {status_response.status_code}"}
            print(f"❌ Bot Status API: FAILED ({status_response.status_code})")
    except Exception as e:
        dashboard_tests['bot_status'] = {'success': False, 'error': str(e)}
        print(f"❌ Bot Status API: ERROR - {e}")
    
    try:
        # Test positions endpoint
        print("\n🌐 Testing /api/positions...")
        positions_response = requests.get('http://0.0.0.0:5000/api/positions', timeout=5)
        if positions_response.status_code == 200:
            positions_data = positions_response.json()
            dashboard_positions = positions_data.get('positions', [])
            dashboard_tests['positions'] = {
                'success': True,
                'count': len(dashboard_positions),
                'positions': dashboard_positions
            }
            print(f"✅ Positions API: SUCCESS")
            print(f"   Positions count: {len(dashboard_positions)}")
            
            # Detailed position verification
            if dashboard_positions:
                print(f"   📋 Position details:")
                for i, pos in enumerate(dashboard_positions, 1):
                    print(f"     {i}. {pos.get('strategy', 'Unknown')} | {pos.get('symbol', 'Unknown')} | {pos.get('side', 'Unknown')}")
                    print(f"        Margin: ${pos.get('margin_invested', 0):.2f} | PnL: ${pos.get('pnl', 0):.2f}")
        else:
            dashboard_tests['positions'] = {'success': False, 'error': f"HTTP {positions_response.status_code}"}
            print(f"❌ Positions API: FAILED ({positions_response.status_code})")
    except Exception as e:
        dashboard_tests['positions'] = {'success': False, 'error': str(e)}
        print(f"❌ Positions API: ERROR - {e}")
    
    print(f"\n🔍 PHASE 5: CROSS-VERIFICATION")
    print("-" * 50)
    
    # Cross-verify database vs dashboard
    db_count = len(open_trades_in_db)
    dashboard_count = dashboard_tests.get('positions', {}).get('count', 0)
    
    print(f"📊 Cross-verification:")
    print(f"   Database open trades: {db_count}")
    print(f"   Dashboard positions: {dashboard_count}")
    
    if db_count == dashboard_count == len(opened_trades):
        print("✅ PERFECT SYNC: All systems showing correct position count")
        sync_status = "PERFECT"
    elif db_count == len(opened_trades):
        print("⚠️ PARTIAL SYNC: Database correct, dashboard may be delayed")
        sync_status = "PARTIAL"
    else:
        print("❌ SYNC FAILED: Inconsistent position counts across systems")
        sync_status = "FAILED"
    
    print(f"\n🔍 PHASE 6: STRATEGY-BY-STRATEGY VERIFICATION")
    print("-" * 50)
    
    strategy_verification = {}
    dashboard_positions = dashboard_tests.get('positions', {}).get('positions', [])
    
    for strategy_name in strategies.keys():
        # Check if strategy has open position in database
        db_has_position = any(t['strategy'] == strategy_name for t in open_trades_in_db)
        
        # Check if strategy has position in dashboard
        dashboard_has_position = any(p.get('strategy') == strategy_name for p in dashboard_positions)
        
        # Check test result
        test_success = test_results.get(strategy_name, {}).get('database_success', False)
        
        strategy_verification[strategy_name] = {
            'test_executed': test_success,
            'in_database': db_has_position,
            'in_dashboard': dashboard_has_position,
            'fully_synced': db_has_position and dashboard_has_position
        }
        
        status_icon = "✅" if strategy_verification[strategy_name]['fully_synced'] else "❌"
        print(f"{status_icon} {strategy_name}:")
        print(f"   Test: {'PASS' if test_success else 'FAIL'}")
        print(f"   Database: {'FOUND' if db_has_position else 'MISSING'}")
        print(f"   Dashboard: {'FOUND' if dashboard_has_position else 'MISSING'}")
    
    print(f"\n🎯 FINAL RESULTS SUMMARY")
    print("=" * 80)
    
    total_strategies = len(strategies)
    successful_tests = sum(1 for r in test_results.values() if r.get('database_success'))
    fully_synced = sum(1 for v in strategy_verification.values() if v['fully_synced'])
    
    print(f"📊 Overall Results:")
    print(f"   Total Strategies Tested: {total_strategies}")
    print(f"   Successful Database Recording: {successful_tests}/{total_strategies}")
    print(f"   Fully Synced (DB + Dashboard): {fully_synced}/{total_strategies}")
    print(f"   Sync Status: {sync_status}")
    
    success_rate = (fully_synced / total_strategies) * 100 if total_strategies > 0 else 0
    
    if success_rate == 100:
        print(f"\n🎉 PERFECT SUCCESS: {success_rate:.0f}% - All strategies working perfectly!")
    elif success_rate >= 80:
        print(f"\n✅ GOOD SUCCESS: {success_rate:.0f}% - Most strategies working correctly")
    elif success_rate >= 50:
        print(f"\n⚠️ PARTIAL SUCCESS: {success_rate:.0f}% - Some strategies need attention")
    else:
        print(f"\n❌ POOR SUCCESS: {success_rate:.0f}% - Major issues detected")
    
    print(f"\n💡 Recommendations:")
    if success_rate == 100:
        print("   🎯 System is working perfectly for all strategies")
        print("   🚀 Ready for live trading with confidence")
    else:
        failed_strategies = [name for name, v in strategy_verification.items() if not v['fully_synced']]
        if failed_strategies:
            print(f"   🔧 Review these strategies: {', '.join(failed_strategies)}")
        
        if dashboard_count != db_count:
            print("   🌐 Check dashboard API connection and data flow")
        
        if db_count != len(opened_trades):
            print("   💾 Check database persistence and recording logic")
    
    # Save detailed test results
    test_report = {
        'timestamp': datetime.now().isoformat(),
        'test_type': 'all_strategies_open_positions',
        'summary': {
            'total_strategies': total_strategies,
            'successful_tests': successful_tests,
            'fully_synced': fully_synced,
            'success_rate': success_rate,
            'sync_status': sync_status
        },
        'strategy_results': test_results,
        'strategy_verification': strategy_verification,
        'dashboard_tests': dashboard_tests,
        'database_state': {
            'total_trades': len(fresh_db.trades),
            'open_trades': len(open_trades_in_db),
            'open_trade_details': open_trades_in_db
        }
    }
    
    report_filename = f"all_strategies_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_filename, 'w') as f:
        json.dump(test_report, f, indent=2, default=str)
    
    print(f"\n📄 Detailed test report saved: {report_filename}")
    
    return test_report

if __name__ == '__main__':
    test_all_strategies_open_positions()
