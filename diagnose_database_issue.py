
#!/usr/bin/env python3
"""
Database Issue Diagnostic Tool
Identify why trades are staying open in database while closed in logger
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.analytics.trade_logger import trade_logger
from datetime import datetime
import json


def diagnose_database_issues():
    """Diagnose inconsistencies between trade database and trade logger"""
    print("🔍 DATABASE ISSUE DIAGNOSTIC")
    print("=" * 50)
    
    # Load both systems
    trade_db = TradeDatabase()
    
    print(f"\n📊 SYSTEM COMPARISON")
    print("-" * 30)
    
    # Get trade IDs from both systems
    db_trade_ids = set(trade_db.trades.keys())
    logger_trade_ids = set(t.trade_id for t in trade_logger.trades)
    
    print(f"Database has {len(db_trade_ids)} trades")
    print(f"Logger has {len(logger_trade_ids)} trades")
    
    # Find inconsistencies
    common_trades = db_trade_ids & logger_trade_ids
    only_in_db = db_trade_ids - logger_trade_ids
    only_in_logger = logger_trade_ids - db_trade_ids
    
    print(f"\n🔍 TRADE ID ANALYSIS")
    print("-" * 25)
    print(f"✅ Common trades: {len(common_trades)}")
    print(f"⚠️  Only in database: {len(only_in_db)}")
    print(f"⚠️  Only in logger: {len(only_in_logger)}")
    
    # Analyze status inconsistencies for common trades
    print(f"\n📋 STATUS INCONSISTENCY ANALYSIS")
    print("-" * 35)
    
    status_mismatches = []
    
    for trade_id in common_trades:
        db_trade = trade_db.trades[trade_id]
        logger_trade = next((t for t in trade_logger.trades if t.trade_id == trade_id), None)
        
        if logger_trade:
            db_status = db_trade.get('trade_status', 'UNKNOWN')
            logger_status = logger_trade.trade_status
            
            if db_status != logger_status:
                status_mismatches.append({
                    'trade_id': trade_id,
                    'db_status': db_status,
                    'logger_status': logger_status,
                    'db_data': db_trade,
                    'logger_data': logger_trade
                })
    
    print(f"❌ Status mismatches found: {len(status_mismatches)}")
    
    if status_mismatches:
        print(f"\n🔍 DETAILED MISMATCH ANALYSIS")
        print("-" * 30)
        
        for i, mismatch in enumerate(status_mismatches[:10]):  # Show first 10
            print(f"\n{i+1}. Trade ID: {mismatch['trade_id']}")
            print(f"   📊 Database Status: {mismatch['db_status']}")
            print(f"   📝 Logger Status: {mismatch['logger_status']}")
            print(f"   💰 DB Entry Price: ${mismatch['db_data'].get('entry_price', 'N/A')}")
            print(f"   💰 Logger Entry Price: ${mismatch['logger_data'].entry_price}")
            print(f"   ⏰ DB Timestamp: {mismatch['db_data'].get('timestamp', 'N/A')}")
            print(f"   ⏰ Logger Timestamp: {mismatch['logger_data'].timestamp}")
    
    # Analyze the trade closing process
    print(f"\n🔧 TRADE CLOSING PROCESS ANALYSIS")
    print("-" * 35)
    
    # Check if trades have exit data in logger but not in database
    exit_data_issues = []
    
    for trade_id in common_trades:
        db_trade = trade_db.trades[trade_id]
        logger_trade = next((t for t in trade_logger.trades if t.trade_id == trade_id), None)
        
        if logger_trade and logger_trade.trade_status == "CLOSED":
            db_has_exit_price = db_trade.get('exit_price') is not None
            logger_has_exit_price = logger_trade.exit_price is not None
            
            if logger_has_exit_price and not db_has_exit_price:
                exit_data_issues.append({
                    'trade_id': trade_id,
                    'logger_exit_price': logger_trade.exit_price,
                    'logger_pnl': logger_trade.pnl_usdt,
                    'db_status': db_trade.get('trade_status')
                })
    
    print(f"❌ Exit data sync issues: {len(exit_data_issues)}")
    
    if exit_data_issues:
        print(f"\n📋 EXIT DATA SYNC ISSUES")
        print("-" * 25)
        for issue in exit_data_issues[:5]:
            print(f"   Trade: {issue['trade_id']}")
            print(f"   Logger has exit: ${issue['logger_exit_price']:.2f}")
            print(f"   Logger PnL: ${issue['logger_pnl']:.2f}")
            print(f"   DB Status: {issue['db_status']}")
            print()
    
    return {
        'status_mismatches': status_mismatches,
        'exit_data_issues': exit_data_issues,
        'only_in_db': only_in_db,
        'only_in_logger': only_in_logger
    }


def identify_root_cause():
    """Identify the root cause of the database synchronization issue"""
    print(f"\n🎯 ROOT CAUSE ANALYSIS")
    print("=" * 30)
    
    print("Potential causes of database sync issues:")
    print("1. 🔄 Trade closing process not updating database")
    print("2. 💾 Database save failures during trade updates")
    print("3. 🔀 Race conditions between logger and database updates")
    print("4. ❌ Error handling preventing database updates")
    print("5. 🧹 Manual cleanup affecting only one system")
    
    # Check recent database modifications
    trade_db = TradeDatabase()
    
    # Check if database file exists and when it was last modified
    import os
    if os.path.exists(trade_db.db_file):
        mod_time = os.path.getmtime(trade_db.db_file)
        mod_datetime = datetime.fromtimestamp(mod_time)
        print(f"\n📁 Database file last modified: {mod_datetime}")
    
    # Check for any error patterns in the trade closing process
    print(f"\n📊 RECOMMENDATIONS")
    print("-" * 20)
    print("1. 🔧 Fix trade closing to update both systems atomically")
    print("2. 🔄 Add database sync verification after each trade close")
    print("3. 📝 Add logging for database update failures")
    print("4. 🛡️ Add retry mechanism for failed database updates")
    print("5. ⚡ Implement periodic sync check between systems")


if __name__ == "__main__":
    print("🔍 DATABASE DIAGNOSTIC TOOL")
    print("Analyzing why trades stay open in database while closed in logger")
    print("=" * 60)
    
    issues = diagnose_database_issues()
    identify_root_cause()
    
    if issues['status_mismatches'] or issues['exit_data_issues']:
        print(f"\n❌ CRITICAL ISSUES FOUND!")
        print("The database recording system has synchronization problems.")
        print("Recommend running fix_database_sync.py to resolve these issues.")
    else:
        print(f"\n✅ NO MAJOR SYNC ISSUES DETECTED")
        print("The systems appear to be in sync currently.")
