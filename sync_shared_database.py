
#!/usr/bin/env python3
"""
Shared Database Sync Utility
Manually sync trades between local database and Replit shared database
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.execution_engine.shared_database import shared_db
from datetime import datetime

def check_shared_database_status():
    """Check status of shared database"""
    print("🔍 CHECKING SHARED DATABASE STATUS")
    print("=" * 50)
    
    status = shared_db.get_sync_status()
    print(f"📊 Status: {status['status']}")
    
    if status['status'] == 'connected':
        print(f"📈 Total trades: {status['total_trades']}")
        print(f"🔓 Open trades: {status['open_trades']}")
        print(f"✅ Closed trades: {status['closed_trades']}")
        print(f"⏰ Last check: {status['last_check']}")
    else:
        print(f"❌ Message: {status.get('message', 'Unknown error')}")

def sync_databases():
    """Perform bidirectional sync between local and shared databases"""
    print("\n🔄 SYNCING DATABASES")
    print("=" * 30)
    
    # Initialize local database
    trade_db = TradeDatabase()
    
    print(f"📊 Local database: {len(trade_db.trades)} trades")
    
    # Get shared database trades
    shared_trades = shared_db.get_all_trades()
    print(f"📊 Shared database: {len(shared_trades)} trades")
    
    # Perform sync
    sync_results = trade_db.sync_with_shared_database("both")
    
    print(f"\n✅ SYNC RESULTS:")
    print(f"   📤 To shared: {sync_results.get('to_shared', 0)} trades")
    print(f"   📥 From shared: {sync_results.get('from_shared', 0)} trades")
    print(f"   ⚠️ Conflicts: {sync_results.get('conflicts', 0)} trades")
    
    if 'error' in sync_results:
        print(f"   ❌ Error: {sync_results['error']}")

def compare_databases():
    """Compare local and shared databases"""
    print("\n🔍 COMPARING DATABASES")
    print("=" * 30)
    
    trade_db = TradeDatabase()
    shared_trades = shared_db.get_all_trades()
    
    local_ids = set(trade_db.trades.keys())
    shared_ids = set(shared_trades.keys())
    
    only_local = local_ids - shared_ids
    only_shared = shared_ids - local_ids
    common = local_ids & shared_ids
    
    print(f"📊 Only in local: {len(only_local)}")
    if only_local:
        print(f"   {list(only_local)[:5]}...")
    
    print(f"📊 Only in shared: {len(only_shared)}")
    if only_shared:
        print(f"   {list(only_shared)[:5]}...")
    
    print(f"📊 In both: {len(common)}")
    
    # Check for status differences in common trades
    status_diffs = 0
    for trade_id in common:
        local_status = trade_db.trades[trade_id].get('trade_status')
        shared_status = shared_trades[trade_id].get('trade_status')
        if local_status != shared_status:
            status_diffs += 1
    
    print(f"📊 Status differences: {status_diffs}")

def force_sync_to_shared():
    """Force sync all local trades to shared database"""
    print("\n🚀 FORCE SYNC TO SHARED DATABASE")
    print("=" * 40)
    
    trade_db = TradeDatabase()
    synced_count = shared_db.sync_from_local(trade_db.trades)
    
    print(f"✅ Force synced {synced_count} trades to shared database")

def main():
    """Main execution function"""
    print("🔄 SHARED DATABASE SYNC UTILITY")
    print("=" * 50)
    
    # Step 1: Check status
    check_shared_database_status()
    
    # Step 2: Compare databases
    compare_databases()
    
    # Step 3: Perform sync
    sync_databases()
    
    # Step 4: Final status check
    print("\n📊 FINAL STATUS:")
    check_shared_database_status()
    
    print("\n🎯 SYNC COMPLETE!")
    print("Both development and deployment should now see the same trades")

if __name__ == "__main__":
    main()
