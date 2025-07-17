
#!/usr/bin/env python3
"""
Clear Open Trades - FIXED VERSION
Properly clear all open trades from both trade database and trade logger
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.analytics.trade_logger import trade_logger
from src.execution_engine.trade_database import TradeDatabase
from datetime import datetime
import json


def clear_open_trades():
    """Clear all open trades from both trade database and trade logger"""
    print("🧹 CLEARING OPEN TRADES - FIXED VERSION")
    print("=" * 50)

    # 1. Clear from Trade Database (PROPERLY)
    print("\n1️⃣ Clearing Trade Database...")
    trade_db = TradeDatabase()

    open_trades_db = []
    for trade_id, trade_data in trade_db.trades.items():
        if trade_data.get('trade_status') == 'OPEN':
            open_trades_db.append(trade_id)

    print(f"   Found {len(open_trades_db)} open trades in database")

    # Mark all as closed with proper data
    for trade_id in open_trades_db:
        trade_db.trades[trade_id]['trade_status'] = 'CLOSED'
        trade_db.trades[trade_id]['exit_reason'] = 'Manual Cleanup'
        trade_db.trades[trade_id]['exit_price'] = trade_db.trades[trade_id].get('entry_price', 0)
        trade_db.trades[trade_id]['pnl_usdt'] = 0.0
        trade_db.trades[trade_id]['pnl_percentage'] = 0.0
        trade_db.trades[trade_id]['duration_minutes'] = 0
        print(f"   ✅ Marked {trade_id} as CLOSED")

    # Force save the database
    trade_db._save_database()
    print(f"   💾 Database saved with {len(open_trades_db)} trades marked as CLOSED")

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
            trade.exit_price = trade.entry_price
            trade.pnl_usdt = 0.0
            trade.pnl_percentage = 0.0
            trade.duration_minutes = 0
            print(f"   ✅ Marked {trade.trade_id} as CLOSED")

    trade_logger._save_trades()
    print(f"   💾 Trade logger saved with {len(open_trades_logger)} trades marked as CLOSED")

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
        print(f"\n❌ STILL HAVE ISSUES:")
        print(f"   Database still has {open_db_count} open trades")
        print(f"   Logger still has {open_logger_count} open trades")


def main():
    print("🧹 TRADE CLEANUP TOOL - FIXED VERSION")
    print("=" * 40)

    # Show current status first
    print("\n📊 CURRENT STATUS:")
    verify_cleanup()

    # Ask for confirmation
    print("\n" + "="*50)
    confirm = input("Do you want to clear all open trades? (y/N): ")

    if confirm.lower() == 'y':
        clear_open_trades()
        verify_cleanup()
    else:
        print("❌ Operation cancelled")


if __name__ == "__main__":
    main()
