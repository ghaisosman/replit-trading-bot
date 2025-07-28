
#!/usr/bin/env python3
"""
Deep Root Cause Investigation
============================
Investigate the EXACT root cause of missing dashboard positions
WITHOUT making any fixes - pure investigation only
"""

import sys
import os
import json
from datetime import datetime
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.binance_client.client import BinanceClientWrapper
from src.bot_manager import BotManager

def deep_investigate_root_cause():
    """
    Deep investigation to understand EXACTLY why positions exist on Binance
    but don't show on dashboard - pure investigation, no fixes
    """
    print("🔍 DEEP ROOT CAUSE INVESTIGATION")
    print("=" * 80)
    print("🚨 INVESTIGATION ONLY - NO FIXES WILL BE APPLIED")
    print("=" * 80)
    
    investigation_report = {
        'timestamp': datetime.now().isoformat(),
        'investigation_type': 'ROOT_CAUSE_ANALYSIS',
        'findings': {},
        'critical_issues': [],
        'data_flow_analysis': {},
        'system_state': {}
    }
    
    # === STEP 1: ACTUAL BINANCE REALITY ===
    print("\n🎯 STEP 1: BINANCE REALITY CHECK")
    print("-" * 50)
    
    binance_reality = analyze_binance_reality()
    investigation_report['findings']['binance_reality'] = binance_reality
    
    # === STEP 2: DATABASE STATE ANALYSIS ===
    print("\n💾 STEP 2: DATABASE STATE DEEP ANALYSIS")
    print("-" * 50)
    
    database_state = analyze_database_state()
    investigation_report['findings']['database_state'] = database_state
    
    # === STEP 3: BOT MANAGER STATE ===
    print("\n🤖 STEP 3: BOT MANAGER STATE ANALYSIS")
    print("-" * 50)
    
    bot_state = analyze_bot_manager_state()
    investigation_report['findings']['bot_manager_state'] = bot_state
    
    # === STEP 4: DATA FLOW TRACING ===
    print("\n🌊 STEP 4: DATA FLOW TRACING")
    print("-" * 50)
    
    data_flow = trace_data_flow()
    investigation_report['data_flow_analysis'] = data_flow
    
    # === STEP 5: CRITICAL DISCONNECT POINTS ===
    print("\n🚨 STEP 5: CRITICAL DISCONNECT ANALYSIS")
    print("-" * 50)
    
    disconnects = analyze_critical_disconnects(binance_reality, database_state, bot_state)
    investigation_report['critical_issues'] = disconnects
    
    # === STEP 6: POSITION LIFECYCLE ANALYSIS ===
    print("\n🔄 STEP 6: POSITION LIFECYCLE ANALYSIS")
    print("-" * 50)
    
    lifecycle = analyze_position_lifecycle()
    investigation_report['findings']['position_lifecycle'] = lifecycle
    
    # === STEP 7: SYSTEM STATE SNAPSHOT ===
    print("\n📸 STEP 7: COMPLETE SYSTEM STATE SNAPSHOT")
    print("-" * 50)
    
    system_snapshot = capture_system_snapshot()
    investigation_report['system_state'] = system_snapshot
    
    # === FINAL ANALYSIS ===
    print("\n🎯 FINAL ROOT CAUSE ANALYSIS")
    print("=" * 80)
    
    final_analysis = perform_final_analysis(investigation_report)
    investigation_report['root_cause_analysis'] = final_analysis
    
    # Save investigation report
    report_filename = f"deep_investigation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_filename, 'w') as f:
        json.dump(investigation_report, f, indent=2, default=str)
    
    print(f"\n📋 INVESTIGATION COMPLETE")
    print(f"   Report saved: {report_filename}")
    print(f"   Critical issues found: {len(investigation_report['critical_issues'])}")
    
    return investigation_report

def analyze_binance_reality():
    """Get the absolute truth from Binance"""
    print("🔍 Analyzing Binance reality...")
    
    try:
        binance_client = BinanceClientWrapper()
        reality = {
            'connection_status': 'unknown',
            'account_accessible': False,
            'positions': [],
            'position_count': 0,
            'api_errors': [],
            'raw_data': {}
        }
        
        # Test connection
        try:
            if binance_client.is_futures:
                account_info = binance_client.client.futures_account()
                reality['connection_status'] = 'connected'
                reality['account_accessible'] = True
                reality['raw_data']['account_info'] = account_info
                
                # Get all positions
                all_positions = account_info.get('positions', [])
                reality['raw_data']['all_positions'] = all_positions
                
                active_positions = []
                for pos in all_positions:
                    position_amt = float(pos.get('positionAmt', 0))
                    if abs(position_amt) > 0.000001:
                        symbol = pos.get('symbol')
                        entry_price = float(pos.get('entryPrice', 0))
                        side = 'BUY' if position_amt > 0 else 'SELL'
                        quantity = abs(position_amt)
                        pnl = float(pos.get('unRealizedProfit', 0))
                        
                        position_data = {
                            'symbol': symbol,
                            'side': side,
                            'quantity': quantity,
                            'entry_price': entry_price,
                            'position_amt': position_amt,
                            'unrealized_pnl': pnl,
                            'raw_position': pos
                        }
                        active_positions.append(position_data)
                        
                        print(f"   ✅ ACTIVE: {symbol} | {side} | Qty: {quantity} | Entry: ${entry_price:.4f} | PnL: ${pnl:.2f}")
                
                reality['positions'] = active_positions
                reality['position_count'] = len(active_positions)
                
            else:
                reality['api_errors'].append("Not using futures trading")
                
        except Exception as e:
            reality['connection_status'] = 'error'
            reality['api_errors'].append(str(e))
            print(f"   ❌ Binance error: {e}")
        
        print(f"   📊 Total active positions: {reality['position_count']}")
        return reality
        
    except Exception as e:
        print(f"   ❌ Critical Binance analysis error: {e}")
        return {'error': str(e)}

def analyze_database_state():
    """Deep analysis of database state"""
    print("🔍 Analyzing database state...")
    
    try:
        trade_db = TradeDatabase()
        state = {
            'total_trades': len(trade_db.trades),
            'open_trades': [],
            'closed_trades': [],
            'trade_statuses': {},
            'data_integrity': {},
            'raw_data': trade_db.trades.copy()
        }
        
        # Categorize trades
        for trade_id, trade_data in trade_db.trades.items():
            status = trade_data.get('trade_status', 'UNKNOWN')
            
            if status not in state['trade_statuses']:
                state['trade_statuses'][status] = 0
            state['trade_statuses'][status] += 1
            
            if status == 'OPEN':
                open_trade = {
                    'trade_id': trade_id,
                    'symbol': trade_data.get('symbol'),
                    'side': trade_data.get('side'),
                    'quantity': trade_data.get('quantity'),
                    'entry_price': trade_data.get('entry_price'),
                    'strategy_name': trade_data.get('strategy_name'),
                    'created_at': trade_data.get('created_at'),
                    'last_updated': trade_data.get('last_updated'),
                    'full_data': trade_data
                }
                state['open_trades'].append(open_trade)
                print(f"   📊 OPEN: {trade_id} | {open_trade['symbol']} | {open_trade['side']}")
            else:
                state['closed_trades'].append({
                    'trade_id': trade_id,
                    'status': status,
                    'symbol': trade_data.get('symbol'),
                    'side': trade_data.get('side')
                })
        
        # Data integrity checks
        state['data_integrity'] = {
            'trades_with_missing_fields': [],
            'trades_with_invalid_data': [],
            'duplicate_symbols': {}
        }
        
        # Check for data integrity issues
        for trade_id, trade_data in trade_db.trades.items():
            required_fields = ['symbol', 'side', 'quantity', 'entry_price', 'trade_status']
            missing_fields = [field for field in required_fields if field not in trade_data]
            
            if missing_fields:
                state['data_integrity']['trades_with_missing_fields'].append({
                    'trade_id': trade_id,
                    'missing_fields': missing_fields
                })
        
        print(f"   📊 Total trades: {state['total_trades']}")
        print(f"   📊 Open trades: {len(state['open_trades'])}")
        print(f"   📊 Closed trades: {len(state['closed_trades'])}")
        print(f"   📊 Status breakdown: {state['trade_statuses']}")
        
        return state
        
    except Exception as e:
        print(f"   ❌ Database analysis error: {e}")
        return {'error': str(e)}

def analyze_bot_manager_state():
    """Analyze bot manager internal state"""
    print("🔍 Analyzing bot manager state...")
    
    try:
        # Try to access bot manager state
        state = {
            'bot_running': False,
            'active_positions': {},
            'strategies_loaded': [],
            'order_manager_state': {},
            'recovery_system_state': {},
            'errors': []
        }
        
        # Check if we can instantiate bot manager
        try:
            bot_manager = BotManager()
            state['bot_running'] = True
            
            # Get active positions
            if hasattr(bot_manager, 'order_manager') and bot_manager.order_manager:
                active_positions = bot_manager.order_manager.get_active_positions()
                state['active_positions'] = {
                    strategy: {
                        'symbol': pos.symbol,
                        'side': pos.side,
                        'quantity': pos.quantity,
                        'entry_price': pos.entry_price,
                        'trade_id': getattr(pos, 'trade_id', None),
                        'status': pos.status
                    } for strategy, pos in active_positions.items()
                }
                
                print(f"   📊 Bot manager active positions: {len(active_positions)}")
                for strategy, pos in active_positions.items():
                    print(f"      • {strategy}: {pos.symbol} {pos.side}")
            
            # Check strategies
            if hasattr(bot_manager, 'strategies'):
                state['strategies_loaded'] = list(bot_manager.strategies.keys()) if bot_manager.strategies else []
                print(f"   📊 Loaded strategies: {len(state['strategies_loaded'])}")
            
        except Exception as e:
            state['bot_running'] = False
            state['errors'].append(f"Bot manager instantiation error: {e}")
            print(f"   ❌ Bot manager error: {e}")
        
        return state
        
    except Exception as e:
        print(f"   ❌ Bot manager analysis error: {e}")
        return {'error': str(e)}

def trace_data_flow():
    """Trace how data flows through the system"""
    print("🔍 Tracing data flow...")
    
    flow = {
        'binance_to_bot': 'unknown',
        'bot_to_database': 'unknown',
        'database_to_dashboard': 'unknown',
        'recovery_system': 'unknown',
        'position_sync': 'unknown',
        'api_endpoints': {},
        'data_consistency': {}
    }
    
    # Test API endpoints
    try:
        import requests
        
        # Test dashboard API
        try:
            response = requests.get('http://localhost:5000/api/positions', timeout=5)
            flow['api_endpoints']['positions'] = {
                'status_code': response.status_code,
                'data': response.json() if response.status_code == 200 else None,
                'accessible': response.status_code == 200
            }
            print(f"   📡 /api/positions: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                positions = data.get('positions', {})
                print(f"      Positions returned: {len(positions)}")
                
        except Exception as e:
            flow['api_endpoints']['positions'] = {'error': str(e)}
            print(f"   ❌ API positions error: {e}")
        
        # Test dashboard endpoint
        try:
            response = requests.get('http://localhost:5000/api/dashboard', timeout=5)
            flow['api_endpoints']['dashboard'] = {
                'status_code': response.status_code,
                'accessible': response.status_code == 200
            }
            print(f"   📡 /api/dashboard: {response.status_code}")
            
        except Exception as e:
            flow['api_endpoints']['dashboard'] = {'error': str(e)}
            print(f"   ❌ API dashboard error: {e}")
        
    except Exception as e:
        flow['api_endpoints']['error'] = str(e)
        print(f"   ❌ API testing error: {e}")
    
    return flow

def analyze_critical_disconnects(binance_reality, database_state, bot_state):
    """Find critical disconnection points"""
    print("🔍 Analyzing critical disconnects...")
    
    disconnects = []
    
    # Compare Binance vs Database
    binance_positions = binance_reality.get('positions', [])
    db_open_trades = database_state.get('open_trades', [])
    
    print(f"   📊 Binance positions: {len(binance_positions)}")
    print(f"   📊 Database open trades: {len(db_open_trades)}")
    
    if len(binance_positions) > 0 and len(db_open_trades) == 0:
        disconnects.append({
            'type': 'CRITICAL_MISMATCH',
            'issue': 'Binance has positions but database shows no open trades',
            'severity': 'HIGH',
            'binance_count': len(binance_positions),
            'database_count': len(db_open_trades),
            'details': {
                'binance_symbols': [pos['symbol'] for pos in binance_positions],
                'database_symbols': []
            }
        })
        print("   🚨 CRITICAL: Binance has positions but database is empty!")
    
    # Check bot manager disconnect
    bot_positions = bot_state.get('active_positions', {})
    if len(binance_positions) > 0 and len(bot_positions) == 0:
        disconnects.append({
            'type': 'BOT_DISCONNECT',
            'issue': 'Binance has positions but bot manager has no active positions',
            'severity': 'HIGH',
            'binance_count': len(binance_positions),
            'bot_count': len(bot_positions)
        })
        print("   🚨 CRITICAL: Bot manager not tracking Binance positions!")
    
    # Check database vs bot disconnect
    if len(db_open_trades) != len(bot_positions):
        disconnects.append({
            'type': 'DATABASE_BOT_MISMATCH',
            'issue': 'Database open trades don\'t match bot active positions',
            'severity': 'MEDIUM',
            'database_count': len(db_open_trades),
            'bot_count': len(bot_positions)
        })
        print("   ⚠️  Database and bot manager out of sync!")
    
    return disconnects

def analyze_position_lifecycle():
    """Analyze position lifecycle to understand where things break"""
    print("🔍 Analyzing position lifecycle...")
    
    lifecycle = {
        'position_creation_flow': 'unknown',
        'position_tracking_flow': 'unknown',
        'position_recovery_flow': 'unknown',
        'dashboard_display_flow': 'unknown',
        'critical_breakpoints': []
    }
    
    # Analyze potential breakpoints
    try:
        trade_db = TradeDatabase()
        
        # Check if trades were created but marked as closed
        recently_closed = []
        for trade_id, trade_data in trade_db.trades.items():
            if trade_data.get('trade_status') == 'CLOSED':
                closed_time = trade_data.get('last_updated', trade_data.get('created_at'))
                recently_closed.append({
                    'trade_id': trade_id,
                    'symbol': trade_data.get('symbol'),
                    'closed_time': closed_time,
                    'exit_reason': trade_data.get('exit_reason', 'unknown')
                })
        
        lifecycle['recently_closed_trades'] = recently_closed
        print(f"   📊 Recently closed trades: {len(recently_closed)}")
        
        # Check for recovery attempts
        recovery_trades = []
        for trade_id, trade_data in trade_db.trades.items():
            if trade_data.get('recovery_trade') or 'RECOVERY_' in trade_id:
                recovery_trades.append({
                    'trade_id': trade_id,
                    'symbol': trade_data.get('symbol'),
                    'recovery_reason': trade_data.get('recovery_reason', 'unknown')
                })
        
        lifecycle['recovery_attempts'] = recovery_trades
        print(f"   📊 Recovery trade attempts: {len(recovery_trades)}")
        
    except Exception as e:
        lifecycle['analysis_error'] = str(e)
        print(f"   ❌ Lifecycle analysis error: {e}")
    
    return lifecycle

def capture_system_snapshot():
    """Capture complete system state snapshot"""
    print("🔍 Capturing system snapshot...")
    
    snapshot = {
        'timestamp': datetime.now().isoformat(),
        'system_components': {},
        'process_status': {},
        'file_status': {},
        'environment': {}
    }
    
    # Check file existence and sizes
    important_files = [
        'trading_data/trade_database.json',
        'src/execution_engine/trade_database.py',
        'src/bot_manager.py',
        'main.py'
    ]
    
    for file_path in important_files:
        if os.path.exists(file_path):
            snapshot['file_status'][file_path] = {
                'exists': True,
                'size': os.path.getsize(file_path),
                'modified': os.path.getmtime(file_path)
            }
        else:
            snapshot['file_status'][file_path] = {'exists': False}
    
    # Environment variables
    important_env_vars = ['DATABASE_URL', 'BINANCE_API_KEY', 'BINANCE_TESTNET']
    for env_var in important_env_vars:
        value = os.getenv(env_var)
        snapshot['environment'][env_var] = 'SET' if value else 'NOT_SET'
    
    print(f"   📊 System snapshot captured")
    return snapshot

def perform_final_analysis(investigation_report):
    """Perform final root cause analysis"""
    print("🔍 Performing final analysis...")
    
    analysis = {
        'primary_root_cause': 'unknown',
        'contributing_factors': [],
        'evidence': {},
        'confidence_level': 'low',
        'next_investigation_steps': []
    }
    
    # Analyze the evidence
    binance_positions = investigation_report['findings']['binance_reality'].get('position_count', 0)
    db_open_trades = len(investigation_report['findings']['database_state'].get('open_trades', []))
    critical_issues = len(investigation_report['critical_issues'])
    
    print(f"   📊 Evidence Summary:")
    print(f"      Binance positions: {binance_positions}")
    print(f"      Database open trades: {db_open_trades}")
    print(f"      Critical issues: {critical_issues}")
    
    # Determine primary root cause
    if binance_positions > 0 and db_open_trades == 0:
        analysis['primary_root_cause'] = 'DATABASE_POSITION_DISCONNECT'
        analysis['confidence_level'] = 'high'
        analysis['evidence']['main'] = 'Binance has positions but database shows no open trades'
        
        print("   🎯 PRIMARY ROOT CAUSE: Database position disconnect")
        print("       Binance has positions that are not recorded in database")
        
    elif binance_positions == 0 and db_open_trades > 0:
        analysis['primary_root_cause'] = 'STALE_DATABASE_RECORDS'
        analysis['confidence_level'] = 'high'
        analysis['evidence']['main'] = 'Database has open trades but no Binance positions exist'
        
        print("   🎯 PRIMARY ROOT CAUSE: Stale database records")
        print("       Database shows open trades but positions don't exist on Binance")
        
    elif binance_positions > 0 and db_open_trades > 0:
        analysis['primary_root_cause'] = 'DATA_SYNC_MISMATCH'
        analysis['confidence_level'] = 'medium'
        analysis['evidence']['main'] = 'Both have positions but they don\'t match'
        
        print("   🎯 PRIMARY ROOT CAUSE: Data synchronization mismatch")
        print("       Both systems have data but they don't align")
        
    else:
        analysis['primary_root_cause'] = 'SYSTEM_STATE_UNKNOWN'
        analysis['confidence_level'] = 'low'
        analysis['evidence']['main'] = 'Both systems show no positions'
        
        print("   🎯 PRIMARY ROOT CAUSE: System state unclear")
        print("       Both systems show no positions - need deeper investigation")
    
    # Add next steps
    analysis['next_investigation_steps'] = [
        'Trace exact moment when position was created',
        'Check bot restart/crash logs around position creation time',
        'Analyze database write operations during position creation',
        'Investigate recovery system failure points',
        'Check dashboard API data retrieval logic'
    ]
    
    return analysis

if __name__ == "__main__":
    investigation_report = deep_investigate_root_cause()
    
    print("\n" + "=" * 80)
    print("🎯 ROOT CAUSE INVESTIGATION COMPLETE")
    print("=" * 80)
    
    # Print key findings
    primary_cause = investigation_report.get('root_cause_analysis', {}).get('primary_root_cause', 'unknown')
    confidence = investigation_report.get('root_cause_analysis', {}).get('confidence_level', 'unknown')
    
    print(f"PRIMARY ROOT CAUSE: {primary_cause}")
    print(f"CONFIDENCE LEVEL: {confidence.upper()}")
    print(f"CRITICAL ISSUES: {len(investigation_report.get('critical_issues', []))}")
    
    print("\n🔍 This investigation provides the data needed to understand the exact problem.")
    print("🚨 NO FIXES APPLIED - Pure investigation only as requested.")
