
#!/usr/bin/env python3
"""
Clean Database for Fresh Start
Completely clear the trade database after manually closing Binance positions
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.analytics.trade_logger import trade_logger
import json

def clean_database_completely():
    """Completely clean the trade database for fresh start"""
    print("🧹 CLEANING DATABASE FOR FRESH START")
    print("=" * 50)
    
    # 1. Clear Trade Database completely
    print("1️⃣ Clearing Trade Database...")
    trade_db = TradeDatabase()
    
    old_count = len(trade_db.trades)
    trade_db.trades = {}  # Completely empty the database
    trade_db._save_database()
    
    print(f"   ✅ Cleared {old_count} trades from database")
    print(f"   📊 Database now has 0 trades")
    
    # 2. Clear Trade Logger
    print("\n2️⃣ Clearing Trade Logger...")
    
    old_logger_count = len(trade_logger.trades)
    trade_logger.trades = []  # Completely empty the logger
    trade_logger._save_trades()
    
    print(f"   ✅ Cleared {old_logger_count} trades from logger")
    print(f"   📊 Logger now has 0 trades")
    
    # 3. Clear any anomaly records
    print("\n3️⃣ Clearing Anomaly Records...")
    try:
        anomalies_file = "trading_data/anomalies.json"
        if os.path.exists(anomalies_file):
            with open(anomalies_file, 'w') as f:
                json.dump({"anomalies": [], "last_updated": "2025-01-20T14:30:00"}, f, indent=2)
            print("   ✅ Cleared anomaly records")
        else:
            print("   ℹ️  No anomaly file found")
    except Exception as e:
        print(f"   ⚠️ Could not clear anomalies: {e}")
    
    return True

def verify_clean_database():
    """Verify the database is completely clean"""
    print("\n🔍 VERIFYING CLEAN DATABASE")
    print("=" * 30)
    
    # Check Trade Database
    trade_db = TradeDatabase()
    db_count = len(trade_db.trades)
    
    # Check Trade Logger  
    logger_count = len(trade_logger.trades)
    
    print(f"📊 Trade Database: {db_count} trades")
    print(f"📊 Trade Logger: {logger_count} trades") 
    
    if db_count == 0 and logger_count == 0:
        print("\n✅ SUCCESS! Database is completely clean")
        print("🚀 Ready for fresh start with new duplicate prevention system")
        return True
    else:
        print(f"\n❌ CLEANUP INCOMPLETE:")
        print(f"   Database still has {db_count} trades")
        print(f"   Logger still has {logger_count} trades")
        return False

def main():
    print("🧹 FRESH START DATABASE CLEANUP")
    print("=" * 40)
    print("⚠️  This will completely clear all trade records")
    print("⚠️  Make sure you've manually closed all Binance positions first!")
    print("=" * 40)
    
    confirm = input("\nType 'CLEAN START' to confirm complete database cleanup: ")
    
    if confirm != "CLEAN START":
        print("❌ Cleanup cancelled")
        return
    
    success = clean_database_completely()
    
    if success:
        clean = verify_clean_database()
        
        if clean:
            print("\n🎉 FRESH START READY!")
            print("✅ Database completely cleaned")
            print("🛡️ New duplicate prevention system is active")
            print("🚀 Start the bot with 'python main.py'")
            print("💡 All new trades will have proper unique tracking")
        else:
            print("\n⚠️ Cleanup may need to be run again")
    else:
        print("\n❌ Cleanup failed")

if __name__ == "__main__":
    main()
