
#!/usr/bin/env python3
"""
Quick Database Status Check
Check current trade counts in the database
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase

def check_database_status():
    """Check current trade database status"""
    print("🔍 CHECKING TRADE DATABASE STATUS")
    print("=" * 40)

    trade_db = TradeDatabase()

    total_trades = len(trade_db.trades)
    open_trades = []
    closed_trades = []

    for trade_id, trade_data in trade_db.trades.items():
        status = trade_data.get('trade_status', 'UNKNOWN')
        if status == 'OPEN':
            open_trades.append((trade_id, trade_data))
        elif status == 'CLOSED':
            closed_trades.append((trade_id, trade_data))

    print(f"📊 TRADE DATABASE SUMMARY:")
    print(f"   📈 Total trades: {total_trades}")
    print(f"   🔓 Open trades: {len(open_trades)}")
    print(f"   ✅ Closed trades: {len(closed_trades)}")

    if open_trades:
        print(f"\n🔓 OPEN TRADES DETAILS:")
        print("-" * 30)
        for trade_id, trade_data in open_trades:
            symbol = trade_data.get('symbol', 'N/A')
            side = trade_data.get('side', 'N/A')
            entry_price = trade_data.get('entry_price', 0)
            strategy = trade_data.get('strategy_name', 'N/A')
            timestamp = trade_data.get('timestamp', 'N/A')
            print(f"   • {trade_id}")
            print(f"     🎯 Strategy: {strategy}")
            print(f"     💱 {symbol} | {side}")
            print(f"     💰 Entry: ${entry_price}")
            print(f"     ⏰ Time: {timestamp}")
            print()

    return {
        'total': total_trades,
        'open': len(open_trades),
        'closed': len(closed_trades),
        'open_trades': open_trades
    }

if __name__ == "__main__":
    result = check_database_status()

    print(f"\n🎯 QUICK SUMMARY:")
    print(f"   Total: {result['total']} | Open: {result['open']} | Closed: {result['closed']}")
