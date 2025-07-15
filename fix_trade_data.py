
#!/usr/bin/env python3
"""
Fix Trade Data Issues
Clean up stale open trades and recalculate incorrect P&L values
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.analytics.trade_logger import trade_logger
from src.execution_engine.trade_database import TradeDatabase
from datetime import datetime
import json

def fix_trade_data():
    """Fix existing trade data issues"""
    print("🔧 FIXING TRADE DATA ISSUES")
    print("=" * 50)
    
    # 1. Clean up stale open trades in database
    print("\n1️⃣ Cleaning up stale open trades...")
    trade_db = TradeDatabase()
    trade_db.cleanup_stale_open_trades(hours=12)  # Mark trades older than 12 hours as closed
    
    # 2. Fix P&L calculations in trade logger data
    print("\n2️⃣ Fixing P&L calculations...")
    fixed_count = 0
    
    for trade in trade_logger.trades:
        if trade.trade_status == "CLOSED" and trade.exit_price and trade.pnl_usdt is not None:
            # Recalculate correct P&L
            if trade.side == "BUY":
                correct_pnl = (trade.exit_price - trade.entry_price) * trade.quantity
            else:
                correct_pnl = (trade.entry_price - trade.exit_price) * trade.quantity
            
            # Check if P&L is incorrect
            if abs(trade.pnl_usdt - correct_pnl) > 0.01:  # More than 1 cent difference
                print(f"   📝 Fixing {trade.trade_id}")
                print(f"      Old P&L: ${trade.pnl_usdt:.2f}")
                print(f"      New P&L: ${correct_pnl:.2f}")
                
                # Fix P&L
                trade.pnl_usdt = correct_pnl
                trade.pnl_percentage = (correct_pnl / trade.position_value_usdt) * 100
                fixed_count += 1
    
    if fixed_count > 0:
        trade_logger._save_trades()
        print(f"   ✅ Fixed {fixed_count} trade P&L calculations")
    else:
        print("   ✅ No P&L fixes needed")
    
    # 3. Display current status
    print("\n3️⃣ Current Trade Status:")
    
    # Count trades by status
    open_trades = len([t for t in trade_logger.trades if t.trade_status == "OPEN"])
    closed_trades = len([t for t in trade_logger.trades if t.trade_status == "CLOSED"])
    
    print(f"   📊 Total trades: {len(trade_logger.trades)}")
    print(f"   🔓 Open trades: {open_trades}")
    print(f"   ✅ Closed trades: {closed_trades}")
    
    # Show recent closed trades with corrected data
    recent_closed = [t for t in trade_logger.trades 
                    if t.trade_status == "CLOSED" and t.pnl_usdt is not None]
    recent_closed.sort(key=lambda x: x.timestamp, reverse=True)
    
    print(f"\n4️⃣ Recent Closed Trades (Last 5):")
    for trade in recent_closed[:5]:
        duration_hours = trade.duration_minutes / 60 if trade.duration_minutes else 0
        print(f"   📝 {trade.trade_id}")
        print(f"      💰 P&L: ${trade.pnl_usdt:.2f} ({trade.pnl_percentage:+.2f}%)")
        print(f"      ⏱️  Duration: {trade.duration_minutes}min ({duration_hours:.1f}h)")
        print(f"      🎯 Exit: {trade.exit_reason}")
        print()
    
    print("✅ Trade data fixes completed!")

if __name__ == "__main__":
    fix_trade_data()
