
#!/usr/bin/env python3
"""
Anomaly Management Script
View and manage orphan/ghost trade anomalies
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.anomaly_detector import AnomalyDatabase, AnomalyType, AnomalyStatus
from datetime import datetime


def display_anomalies():
    """Display all anomalies"""
    db = AnomalyDatabase()

    print("\n🔍 ANOMALY DATABASE STATUS")
    print("=" * 50)

    active_anomalies = db.get_active_anomalies()
    all_anomalies = list(db.anomalies.values())

    print(f"Total anomalies: {len(all_anomalies)}")
    print(f"Active anomalies: {len(active_anomalies)}")

    if not active_anomalies:
        print("✅ No active anomalies found")
        return

    print("\n📊 ACTIVE ANOMALIES:")
    print("-" * 50)

    for anomaly in active_anomalies:
        print(f"\n🔍 {anomaly.type.value.upper()} | {anomaly.id}")
        print(f"   Strategy: {anomaly.strategy_name}")
        print(f"   Symbol: {anomaly.symbol}")
        print(f"   Side: {anomaly.side}")
        print(f"   Quantity: {anomaly.quantity}")
        print(f"   Detected: {anomaly.detected_at}")
        print(f"   Cycles Remaining: {anomaly.cycles_remaining}")
        print(f"   Notified: {anomaly.notified}")
        if anomaly.entry_price:
            print(f"   Entry Price: ${anomaly.entry_price:.4f}")
        if anomaly.binance_position_amt:
            print(f"   Binance Position: {anomaly.binance_position_amt}")


def clear_anomaly():
    """Clear a specific anomaly"""
    db = AnomalyDatabase()

    active_anomalies = db.get_active_anomalies()
    if not active_anomalies:
        print("No active anomalies to clear")
        return

    print("\nActive anomalies:")
    for i, anomaly in enumerate(active_anomalies, 1):
        print(f"{i}. {anomaly.type.value.upper()} | {anomaly.strategy_name} | {anomaly.symbol}")

    try:
        choice = int(input("\nEnter anomaly number to clear (0 to cancel): "))
        if choice == 0:
            return

        if 1 <= choice <= len(active_anomalies):
            anomaly = active_anomalies[choice - 1]
            confirm = input(f"Clear {anomaly.type.value} anomaly for {anomaly.strategy_name}/{anomaly.symbol}? (y/N): ")

            if confirm.lower() == 'y':
                db.update_anomaly(anomaly.id, 
                                status=AnomalyStatus.CLEARED,
                                cleared_at=datetime.now())
                print(f"✅ Cleared anomaly: {anomaly.id}")
            else:
                print("❌ Cancelled")
        else:
            print("Invalid choice")

    except ValueError:
        print("Invalid input")


def cleanup_old_anomalies():
    """Clean up old anomalies"""
    db = AnomalyDatabase()

    days = input("Enter number of days to keep cleared anomalies (default 7): ")
    try:
        days = int(days) if days else 7
    except ValueError:
        days = 7

    old_count = len(db.anomalies)
    db.cleanup_old_anomalies(days)
    new_count = len(db.anomalies)

    print(f"✅ Cleaned up {old_count - new_count} old anomalies")


def show_statistics():
    """Show anomaly statistics"""
    db = AnomalyDatabase()

    print("\n📈 ANOMALY STATISTICS")
    print("=" * 30)

    all_anomalies = list(db.anomalies.values())

    if not all_anomalies:
        print("No anomalies found")
        return

    # Count by type
    orphan_count = len([a for a in all_anomalies if a.type == AnomalyType.ORPHAN])
    ghost_count = len([a for a in all_anomalies if a.type == AnomalyType.GHOST])

    # Count by status
    active_count = len([a for a in all_anomalies if a.status == AnomalyStatus.ACTIVE])
    cleared_count = len([a for a in all_anomalies if a.status == AnomalyStatus.CLEARED])

    print(f"Total anomalies: {len(all_anomalies)}")
    print(f"Orphan trades: {orphan_count}")
    print(f"Ghost trades: {ghost_count}")
    print(f"Active: {active_count}")
    print(f"Cleared: {cleared_count}")

    # Most common strategies
    strategies = {}
    for anomaly in all_anomalies:
        strategies[anomaly.strategy_name] = strategies.get(anomaly.strategy_name, 0) + 1

    if strategies:
        print("\nMost affected strategies:")
        for strategy, count in sorted(strategies.items(), key=lambda x: x[1], reverse=True):
            print(f"  {strategy}: {count} anomalies")


def check_database_status():
    """Check trade database status"""
    from src.execution_engine.trade_database import TradeDatabase

    print("\n🔍 DATABASE STATUS CHECK")
    print("=" * 40)

    db = TradeDatabase()

    open_trades = []
    closed_trades = []

    for trade_id, trade_data in db.trades.items():
        if trade_data.get('trade_status') == 'OPEN':
            open_trades.append((trade_id, trade_data))
        else:
            closed_trades.append((trade_id, trade_data))

    print(f"📊 Total trades: {len(db.trades)}")
    print(f"🔓 Open trades: {len(open_trades)}")
    print(f"✅ Closed trades: {len(closed_trades)}")

    if open_trades:
        print("\n🔓 OPEN TRADES:")
        for trade_id, trade_data in open_trades:
            print(f"  {trade_id}")
            print(f"    Strategy: {trade_data.get('strategy_name')}")
            print(f"    Symbol: {trade_data.get('symbol')}")
            print(f"    Side: {trade_data.get('side')}")
            print(f"    Entry: ${trade_data.get('entry_price')}")
            print(f"    Quantity: {trade_data.get('quantity')}")
            print(f"    Timestamp: {trade_data.get('timestamp')}")
            print()

    return open_trades


def main():
    print("🔍 ANOMALY MANAGER")
    print("=" * 20)

    while True:
        print("\nOptions:")
        print("1. Display active anomalies")
        print("2. Clear specific anomaly")
        print("3. Show statistics")
        print("4. Cleanup old anomalies")
        print("5. Check database status")
        print("6. Exit")

        choice = input("\nSelect option (1-6): ")

        if choice == "1":
            display_anomalies()
        elif choice == "2":
            clear_anomaly()
        elif choice == "3":
            show_statistics()
        elif choice == "4":
            cleanup_old_anomalies()
        elif choice == "5":
            check_database_status()
        elif choice == "6":
            break
        else:
            print("Invalid option")


if __name__ == "__main__":
    main()
