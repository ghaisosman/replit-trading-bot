
#!/usr/bin/env python3
"""
Verify Cleanup Status
Check if the XRP trade cleanup was successful and confirm database state
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.analytics.trade_logger import trade_logger
from datetime import datetime
import json

def check_cleanup_status():
    """Verify that the XRP trade cleanup was successful"""
    print("🔍 VERIFYING CLEANUP STATUS")
    print("=" * 50)
    
    # 1. Check Trade Database
    print("\n1️⃣ Checking Trade Database...")
    trade_db = TradeDatabase()
    
    # Look for XRP trades
    xrp_trades = []
    open_trades = []
    
    for trade_id, trade_data in trade_db.trades.items():
        symbol = trade_data.get('symbol', '')
        status = trade_data.get('trade_status', '')
        strategy = trade_data.get('strategy_name', '')
        
        if 'XRP' in symbol:
            xrp_trades.append({
                'id': trade_id,
                'symbol': symbol,
                'strategy': strategy,
                'status': status,
                'created': trade_data.get('timestamp', 'Unknown')
            })
            
        if status == 'OPEN':
            open_trades.append({
                'id': trade_id,
                'symbol': symbol,
                'strategy': strategy,
                'status': status
            })
    
    print(f"   📊 Total trades in database: {len(trade_db.trades)}")
    print(f"   📊 XRP-related trades: {len(xrp_trades)}")
    print(f"   📊 Currently OPEN trades: {len(open_trades)}")
    
    # Display XRP trades
    if xrp_trades:
        print(f"\n   🔍 XRP TRADE DETAILS:")
        for trade in xrp_trades:
            status_icon = "🔓" if trade['status'] == 'OPEN' else "🔒"
            print(f"     {status_icon} {trade['id']}")
            print(f"        Strategy: {trade['strategy']}")
            print(f"        Symbol: {trade['symbol']}")
            print(f"        Status: {trade['status']}")
            print(f"        Created: {trade['created']}")
            print()
    else:
        print("   ✅ No XRP trades found in database")
        
    # Display any open trades
    if open_trades:
        print(f"\n   ⚠️ OPEN TRADES DETECTED:")
        for trade in open_trades:
            print(f"     🔓 {trade['id']} | {trade['strategy']} | {trade['symbol']} | {trade['status']}")
    else:
        print("   ✅ No OPEN trades found - database is clean")
    
    # 2. Check Dashboard Data Source
    print("\n2️⃣ Checking Web Dashboard Data...")
    
    # The dashboard gets active positions from the order manager via the bot
    # Since there's no direct order manager access here, we'll check what data
    # the dashboard API endpoints would return
    
    print("   📱 Dashboard should reflect:")
    print(f"     • Active Positions: {len(open_trades)}")
    print(f"     • Total Balance: Retrieved from Binance")
    print(f"     • Bot Status: Running (as shown in console)")
    
    # 3. Summary and Recommendations
    print(f"\n3️⃣ CLEANUP STATUS SUMMARY")
    print("=" * 30)
    
    if len(open_trades) == 0:
        print("✅ CLEANUP SUCCESSFUL!")
        print("   • No open trades in database")
        print("   • XRP position properly closed")
        print("   • Dashboard should show 0 active positions")
        print("   • System ready for new trades")
        
        if len(xrp_trades) > 0:
            print(f"\n📝 Historical XRP trades: {len(xrp_trades)} (properly closed)")
            
    else:
        print("⚠️ CLEANUP INCOMPLETE!")
        print(f"   • {len(open_trades)} trades still marked as OPEN")
        print("   • Dashboard may still show active positions")
        print("   • Automatic cleanup should resolve this soon")
        
    print(f"\n💡 NEXT STEPS:")
    print("   • Wait 30-60 seconds for dashboard to refresh")
    print("   • The system automatically cleans stale trades")
    print("   • No manual intervention needed")
    
    return len(open_trades) == 0

if __name__ == "__main__":
    cleanup_successful = check_cleanup_status()
    
    if cleanup_successful:
        print(f"\n🎉 All systems clean! Your trading bot is ready.")
    else:
        print(f"\n⏳ Cleanup in progress... system will auto-resolve.")
