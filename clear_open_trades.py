
#!/usr/bin/env python3
"""
Clear Open Trades Script
Manually clear all open trades from the database for a fresh start
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.analytics.trade_logger import trade_logger
import json


def clear_open_trades():
    """Clear all open trades from both trade database and trade logger"""
    print("🧹 CLEARING OPEN TRADES")
    print("=" * 40)
    
    # 1. Clear from Trade Database
    print("\n1️⃣ Clearing Trade Database...")
    trade_db = TradeDatabase()
    
    open_trades_db = []
    for trade_id, trade_data in trade_db.trades.items():
        if trade_data.get('trade_status') == 'OPEN':
            open_trades_db.append(trade_id)
    
    print(f"   Found {len(open_trades_db)} open trades in database")
    
    # Mark all as closed
    for trade_id in open_trades_db:
        trade_db.trades[trade_id]['trade_status'] = 'CLOSED'
        trade_db.trades[trade_id]['exit_reason'] = 'Manual Cleanup'
        trade_db.trades[trade_id]['pnl_usdt'] = 0
        trade_db.trades[trade_id]['pnl_percentage'] = 0
        print(f"   ✅ Marked {trade_id} as closed")
    
    trade_db._save_database()
    print(f"   💾 Saved database with {len(open_trades_db)} trades marked as closed")
    
    # 2. Clear from Trade Logger
    print("\n2️⃣ Clearing Trade Logger...")
    
    open_trades_logger = []
    for trade in trade_logger.trades:
        if trade.trade_status == "OPEN":
            open_trades_logger.append(trade.trade_id)
    
    print(f"   Found {len(open_trades_logger)} open trades in logger")
    
    # Mark all as closed
    for trade in trade_logger.trades:
        if trade.trade_status == "OPEN":
            trade.trade_status = "CLOSED"
            trade.exit_reason = "Manual Cleanup"
            trade.pnl_usdt = 0
            trade.pnl_percentage = 0
            print(f"   ✅ Marked {trade.trade_id} as closed")
    
    trade_logger._save_trades()
    print(f"   💾 Saved trade logger with {len(open_trades_logger)} trades marked as closed")
    
    print(f"\n✅ CLEANUP COMPLETE!")
    print(f"   📊 Database: {len(open_trades_db)} trades cleared")
    print(f"   📊 Logger: {len(open_trades_logger)} trades cleared")


def verify_cleanup():
    """Verify that all trades are now marked as closed"""
    print("\n🔍 VERIFYING CLEANUP")
    print("=" * 30)
    
    # Check Trade Database
    trade_db = TradeDatabase()
    open_db_count = len([t for t in trade_db.trades.values() if t.get('trade_status') == 'OPEN'])
    closed_db_count = len([t for t in trade_db.trades.values() if t.get('trade_status') == 'CLOSED'])
    
    print(f"📊 Trade Database:")
    print(f"   🔓 Open trades: {open_db_count}")
    print(f"   ✅ Closed trades: {closed_db_count}")
    print(f"   📈 Total trades: {len(trade_db.trades)}")
    
    # Check Trade Logger
    open_logger_count = len([t for t in trade_logger.trades if t.trade_status == "OPEN"])
    closed_logger_count = len([t for t in trade_logger.trades if t.trade_status == "CLOSED"])
    
    print(f"\n📊 Trade Logger:")
    print(f"   🔓 Open trades: {open_logger_count}")
    print(f"   ✅ Closed trades: {closed_logger_count}")
    print(f"   📈 Total trades: {len(trade_logger.trades)}")
    
    if open_db_count == 0 and open_logger_count == 0:
        print(f"\n✅ SUCCESS! All trades are now marked as closed")
        print(f"🚀 You now have a clean slate for fresh trading!")
    else:
        print(f"\n⚠️  Warning: Still have open trades that need attention")


if __name__ == "__main__":
    print("🧹 MANUAL TRADE CLEANUP TOOL")
    print("This will mark ALL open trades as closed")
    print("=" * 50)
    
    confirm = input("Are you sure you want to proceed? (yes/no): ")
    if confirm.lower() == 'yes':
        clear_open_trades()
        verify_cleanup()
    else:
        print("❌ Cleanup cancelled")
