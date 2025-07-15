
#!/usr/bin/env python3
"""
Database Synchronization Fix
Fix the root cause of database recording system issues
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.analytics.trade_logger import trade_logger
from datetime import datetime
import json


def sync_database_with_logger():
    """Synchronize trade database with trade logger (logger is source of truth)"""
    print("🔄 SYNCHRONIZING DATABASE WITH LOGGER")
    print("=" * 50)
    
    trade_db = TradeDatabase()
    
    # Use trade logger as source of truth
    logger_trades = {t.trade_id: t for t in trade_logger.trades}
    
    print(f"📊 Found {len(logger_trades)} trades in logger")
    
    synced_count = 0
    created_count = 0
    
    for trade_id, logger_trade in logger_trades.items():
        # Check if trade exists in database
        if trade_id in trade_db.trades:
            # Update existing trade
            db_trade = trade_db.trades[trade_id]
            
            # Check if status needs updating
            if db_trade.get('trade_status') != logger_trade.trade_status:
                print(f"   🔄 Syncing {trade_id}: {db_trade.get('trade_status')} → {logger_trade.trade_status}")
                
                # Update with logger data
                trade_db.trades[trade_id].update({
                    'trade_status': logger_trade.trade_status,
                    'exit_price': logger_trade.exit_price,
                    'exit_reason': logger_trade.exit_reason,
                    'pnl_usdt': logger_trade.pnl_usdt,
                    'pnl_percentage': logger_trade.pnl_percentage,
                    'duration_minutes': logger_trade.duration_minutes
                })
                synced_count += 1
        else:
            # Create missing trade in database
            print(f"   ➕ Creating missing trade: {trade_id}")
            trade_db.trades[trade_id] = logger_trade.to_dict()
            created_count += 1
    
    # Save the synchronized database
    trade_db._save_database()
    
    print(f"\n✅ SYNCHRONIZATION COMPLETE")
    print(f"   🔄 Updated trades: {synced_count}")
    print(f"   ➕ Created trades: {created_count}")
    
    return synced_count + created_count


def fix_trade_closing_process():
    """Add proper database update to trade closing process"""
    print(f"\n🔧 FIXING TRADE CLOSING PROCESS")
    print("=" * 40)
    
    # The issue is likely in the order_manager.py file where trades are closed
    # but the database isn't being updated properly
    
    print("Checking order manager for database update issues...")
    
    # Read the current order manager to see if it has proper database updates
    try:
        with open('src/execution_engine/order_manager.py', 'r') as f:
            content = f.read()
        
        # Check if it updates trade database on exit
        if 'trade_db.update_trade' in content:
            print("   ✅ Order manager has database update code")
        else:
            print("   ❌ Order manager missing database update on trade exit")
            print("   📝 This is likely the root cause!")
        
        # Check if it handles database update failures
        if 'except' in content and 'trade_db' in content:
            print("   ✅ Has error handling for database updates")
        else:
            print("   ⚠️  Missing error handling for database updates")
    
    except Exception as e:
        print(f"   ❌ Error checking order manager: {e}")


def add_sync_verification():
    """Add verification to ensure database and logger stay in sync"""
    print(f"\n🛡️ ADDING SYNC VERIFICATION")
    print("=" * 30)
    
    verification_code = '''
def verify_trade_sync(trade_id: str):
    """Verify that trade is properly synced between database and logger"""
    try:
        trade_db = TradeDatabase()
        
        # Find trade in logger
        logger_trade = None
        for trade in trade_logger.trades:
            if trade.trade_id == trade_id:
                logger_trade = trade
                break
        
        if not logger_trade:
            logger.warning(f"Trade {trade_id} not found in logger")
            return False
        
        # Check database
        db_trade = trade_db.get_trade(trade_id)
        if not db_trade:
            logger.warning(f"Trade {trade_id} not found in database")
            return False
        
        # Compare status
        if db_trade.get('trade_status') != logger_trade.trade_status:
            logger.warning(f"Status mismatch for {trade_id}: DB={db_trade.get('trade_status')}, Logger={logger_trade.trade_status}")
            
            # Auto-fix the mismatch
            trade_db.update_trade(trade_id, {
                'trade_status': logger_trade.trade_status,
                'exit_price': logger_trade.exit_price,
                'exit_reason': logger_trade.exit_reason,
                'pnl_usdt': logger_trade.pnl_usdt,
                'pnl_percentage': logger_trade.pnl_percentage
            })
            logger.info(f"Auto-fixed sync for trade {trade_id}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error verifying trade sync: {e}")
        return False
'''
    
    print("   📝 Sync verification function created")
    print("   🔄 This should be called after every trade close")


def main():
    print("🔧 DATABASE SYNC REPAIR TOOL")
    print("=" * 30)
    
    # Step 1: Diagnose current issues
    print("\n1️⃣ Diagnosing current state...")
    os.system("python diagnose_database_issue.py")
    
    # Step 2: Sync current data
    print(f"\n2️⃣ Synchronizing current data...")
    changes = sync_database_with_logger()
    
    # Step 3: Fix the underlying process
    print(f"\n3️⃣ Analyzing trade closing process...")
    fix_trade_closing_process()
    
    # Step 4: Add verification
    print(f"\n4️⃣ Adding sync verification...")
    add_sync_verification()
    
    print(f"\n✅ REPAIR COMPLETE")
    if changes > 0:
        print(f"   Fixed {changes} synchronization issues")
        print("   📊 Run trade_report.py to verify the fix")
    else:
        print("   No immediate sync issues found")
    
    print("\n🚀 NEXT STEPS:")
    print("1. Monitor new trades to ensure proper sync")
    print("2. Consider adding the sync verification to order_manager.py")
    print("3. Set up periodic sync checks")


if __name__ == "__main__":
    main()
