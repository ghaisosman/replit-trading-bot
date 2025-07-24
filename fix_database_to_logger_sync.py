
#!/usr/bin/env python3
"""
Fix Database to Logger Sync
Ensure all trades in database are properly synced to trade logger
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.analytics.trade_logger import trade_logger

def main():
    print("🔄 FIXING DATABASE TO LOGGER SYNC")
    print("=" * 50)
    
    # Initialize database and logger
    trade_db = TradeDatabase()
    
    print(f"📊 Database has {len(trade_db.trades)} trades")
    print(f"📊 Logger has {len(trade_logger.trades)} trades")
    
    # Find trades in database that are NOT in logger
    db_trade_ids = set(trade_db.trades.keys())
    logger_trade_ids = set(t.trade_id for t in trade_logger.trades)
    
    missing_in_logger = db_trade_ids - logger_trade_ids
    
    print(f"🔍 Found {len(missing_in_logger)} trades in database missing from logger")
    
    if missing_in_logger:
        print("\n📝 Syncing missing trades to logger:")
        
        synced_count = 0
        for trade_id in missing_in_logger:
            print(f"   🔄 Syncing {trade_id}...")
            success = trade_db.sync_trade_to_logger(trade_id)
            if success:
                synced_count += 1
                print(f"   ✅ {trade_id} synced successfully")
            else:
                print(f"   ❌ {trade_id} sync failed")
        
        print(f"\n✅ Successfully synced {synced_count}/{len(missing_in_logger)} trades")
    else:
        print("✅ All database trades are already in logger")
    
    # Verify sync
    print(f"\n📊 After sync:")
    print(f"   Database: {len(trade_db.trades)} trades")
    print(f"   Logger: {len(trade_logger.trades)} trades")

if __name__ == "__main__":
    main()
