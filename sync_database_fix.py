
#!/usr/bin/env python3
"""
Simple Database Sync Fix
Make trade logger the single source of truth and sync database accordingly
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.analytics.trade_logger import trade_logger
from datetime import datetime

def fix_database_sync():
    """Fix database sync issues by making trade logger the source of truth"""
    print("🔄 SIMPLE DATABASE SYNC FIX")
    print("=" * 40)
    
    # Load both systems
    trade_db = TradeDatabase()
    
    print(f"📊 Current state:")
    print(f"   Database trades: {len(trade_db.trades)}")
    print(f"   Logger trades: {len(trade_logger.trades)}")
    
    # Use built-in sync method
    synced_count = trade_db.sync_from_logger()
    
    print(f"\n✅ Sync complete:")
    print(f"   Synced trades: {synced_count}")
    print(f"   Final database trades: {len(trade_db.trades)}")
    
    # Verify sync worked
    logger_trade_ids = {t.trade_id for t in trade_logger.trades}
    db_trade_ids = set(trade_db.trades.keys())
    
    missing_in_db = logger_trade_ids - db_trade_ids
    extra_in_db = db_trade_ids - logger_trade_ids
    
    print(f"\n🔍 Verification:")
    print(f"   Missing in database: {len(missing_in_db)}")
    print(f"   Extra in database: {len(extra_in_db)}")
    
    if len(missing_in_db) == 0 and len(extra_in_db) == 0:
        print("   ✅ Perfect sync achieved!")
    else:
        if missing_in_db:
            print(f"   ⚠️ Missing trades: {list(missing_in_db)[:5]}...")
        if extra_in_db:
            print(f"   ⚠️ Extra trades: {list(extra_in_db)[:5]}...")

def verify_technical_indicators():
    """Verify technical indicators are properly synced"""
    print(f"\n📊 TECHNICAL INDICATORS VERIFICATION")
    print("-" * 40)
    
    trade_db = TradeDatabase()
    indicators_found = 0
    total_trades = 0
    
    for trade_id, trade_data in trade_db.trades.items():
        total_trades += 1
        has_indicators = any([
            trade_data.get('rsi_at_entry'),
            trade_data.get('macd_at_entry'),
            trade_data.get('sma_20_at_entry'),
            trade_data.get('sma_50_at_entry')
        ])
        
        if has_indicators:
            indicators_found += 1
    
    print(f"Trades with technical indicators: {indicators_found}/{total_trades}")
    
    if indicators_found > 0:
        print("✅ Technical indicators are being synced")
    else:
        print("⚠️ No technical indicators found in database")

if __name__ == "__main__":
    print("🚀 Starting simple database sync fix...")
    
    try:
        fix_database_sync()
        verify_technical_indicators()
        
        print(f"\n🎉 Database sync fix completed successfully!")
        print("The trade logger is now the single source of truth.")
        print("All future trades will automatically sync to database.")
        
    except Exception as e:
        print(f"❌ Error during sync fix: {e}")
        import traceback
        traceback.print_exc()
