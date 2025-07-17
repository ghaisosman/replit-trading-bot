
#!/usr/bin/env python3
"""
Comprehensive Trade Database Status Checker
Check all trades in the database and show detailed status information
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from datetime import datetime, timedelta
import json

def check_database_status():
    """Check current trade database status with detailed analysis"""
    print("🔍 COMPREHENSIVE TRADE DATABASE STATUS CHECK")
    print("=" * 60)

    try:
        trade_db = TradeDatabase()
        
        if not trade_db.trades:
            print("📊 DATABASE: Empty - No trades found")
            return

        # Basic statistics
        total_trades = len(trade_db.trades)
        open_trades = []
        closed_trades = []
        unknown_trades = []

        # Categorize trades by status
        for trade_id, trade_data in trade_db.trades.items():
            status = trade_data.get('trade_status', 'UNKNOWN')
            if status == 'OPEN':
                open_trades.append((trade_id, trade_data))
            elif status == 'CLOSED':
                closed_trades.append((trade_id, trade_data))
            else:
                unknown_trades.append((trade_id, trade_data))

        # Summary statistics
        print(f"📊 DATABASE SUMMARY:")
        print(f"   📈 Total trades: {total_trades}")
        print(f"   🔓 Open trades: {len(open_trades)}")
        print(f"   ✅ Closed trades: {len(closed_trades)}")
        print(f"   ❓ Unknown status: {len(unknown_trades)}")
        print()

        # Detailed analysis of open trades
        if open_trades:
            print("🔓 OPEN TRADES ANALYSIS:")
            print("-" * 40)
            for i, (trade_id, trade_data) in enumerate(open_trades, 1):
                print(f"   📋 TRADE #{i}: {trade_id}")
                print(f"      🎯 Strategy: {trade_data.get('strategy_name', 'N/A')}")
                print(f"      💱 Symbol: {trade_data.get('symbol', 'N/A')}")
                print(f"      📊 Side: {trade_data.get('side', 'N/A')}")
                print(f"      💰 Entry Price: ${trade_data.get('entry_price', 0)}")
                print(f"      📏 Quantity: {trade_data.get('quantity', 0)}")
                print(f"      ⚡ Leverage: {trade_data.get('leverage', 0)}x")
                print(f"      💵 Margin: ${trade_data.get('margin_used', 0)}")
                
                # Check age of trade
                timestamp = trade_data.get('timestamp', '')
                if timestamp:
                    try:
                        trade_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        age = datetime.now() - trade_time
                        age_hours = age.total_seconds() / 3600
                        print(f"      ⏰ Age: {age_hours:.1f} hours ({trade_time.strftime('%Y-%m-%d %H:%M:%S')})")
                        
                        # Flag stale trades
                        if age_hours > 24:
                            print(f"      ⚠️  WARNING: Trade is {age_hours:.1f} hours old (potentially stale)")
                    except:
                        print(f"      ⏰ Timestamp: {timestamp}")
                
                print(f"      💹 PnL: ${trade_data.get('pnl_usdt', 0)} ({trade_data.get('pnl_percentage', 0)}%)")
                print()

        # Detailed analysis of closed trades
        if closed_trades:
            print("✅ CLOSED TRADES ANALYSIS:")
            print("-" * 40)
            
            # Sort by timestamp (most recent first)
            closed_trades.sort(key=lambda x: x[1].get('timestamp', ''), reverse=True)
            
            total_pnl = 0
            profitable_trades = 0
            loss_trades = 0
            
            for i, (trade_id, trade_data) in enumerate(closed_trades[:10], 1):  # Show last 10
                pnl = trade_data.get('pnl_usdt', 0)
                pnl_pct = trade_data.get('pnl_percentage', 0)
                
                if pnl > 0:
                    profitable_trades += 1
                    pnl_indicator = "✅ PROFIT"
                elif pnl < 0:
                    loss_trades += 1
                    pnl_indicator = "❌ LOSS"
                else:
                    pnl_indicator = "⚪ BREAK-EVEN"
                
                total_pnl += pnl
                
                print(f"   📋 TRADE #{i}: {trade_id}")
                print(f"      🎯 Strategy: {trade_data.get('strategy_name', 'N/A')}")
                print(f"      💱 Symbol: {trade_data.get('symbol', 'N/A')}")
                print(f"      📊 Side: {trade_data.get('side', 'N/A')}")
                print(f"      💰 Entry: ${trade_data.get('entry_price', 0)} → Exit: ${trade_data.get('exit_price', 0)}")
                print(f"      💹 PnL: ${pnl} ({pnl_pct}%) {pnl_indicator}")
                print(f"      🚪 Exit Reason: {trade_data.get('exit_reason', 'N/A')}")
                print(f"      ⏱️  Duration: {trade_data.get('duration_minutes', 0)} minutes")
                print()
            
            if len(closed_trades) > 10:
                print(f"   ... and {len(closed_trades) - 10} more closed trades")
                print()
            
            # Performance summary
            print(f"💰 PERFORMANCE SUMMARY (Closed Trades):")
            print(f"   📈 Profitable trades: {profitable_trades}")
            print(f"   📉 Loss trades: {loss_trades}")
            print(f"   💵 Total PnL: ${total_pnl:.2f}")
            print(f"   📊 Win rate: {(profitable_trades / len(closed_trades) * 100):.1f}%")
            print()

        # Unknown status trades
        if unknown_trades:
            print("❓ UNKNOWN STATUS TRADES:")
            print("-" * 40)
            for i, (trade_id, trade_data) in enumerate(unknown_trades, 1):
                print(f"   📋 TRADE #{i}: {trade_id}")
                print(f"      🎯 Strategy: {trade_data.get('strategy_name', 'N/A')}")
                print(f"      💱 Symbol: {trade_data.get('symbol', 'N/A')}")
                print(f"      📊 Status: {trade_data.get('trade_status', 'UNKNOWN')}")
                print()

        # Database health check
        print("🏥 DATABASE HEALTH CHECK:")
        print("-" * 40)
        
        # Check for stale open trades
        stale_count = 0
        current_time = datetime.now()
        for trade_id, trade_data in trade_db.trades.items():
            if trade_data.get('trade_status') == 'OPEN':
                timestamp = trade_data.get('timestamp', '')
                if timestamp:
                    try:
                        trade_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        age_hours = (current_time - trade_time).total_seconds() / 3600
                        if age_hours > 6:  # Stale after 6 hours
                            stale_count += 1
                    except:
                        pass
        
        print(f"   🔍 Stale open trades (>6h): {stale_count}")
        print(f"   📁 Database file: {trade_db.db_file}")
        print(f"   💾 Database exists: {os.path.exists(trade_db.db_file)}")
        
        if os.path.exists(trade_db.db_file):
            file_size = os.path.getsize(trade_db.db_file)
            print(f"   📊 File size: {file_size} bytes ({file_size / 1024:.1f} KB)")
        
        # Recommendations
        print("\n🔧 RECOMMENDATIONS:")
        print("-" * 40)
        if stale_count > 0:
            print(f"   ⚠️  {stale_count} stale open trades detected")
            print(f"   💡 Consider running: trade_db.cleanup_stale_open_trades()")
        
        if len(closed_trades) > 100:
            print(f"   📦 {len(closed_trades)} closed trades in database")
            print(f"   💡 Consider running: trade_db.cleanup_old_trades(days=30)")
        
        if not open_trades and not closed_trades:
            print(f"   ℹ️  Database is empty - no trades to analyze")
        else:
            print(f"   ✅ Database appears healthy with {total_trades} total trades")

    except Exception as e:
        print(f"❌ ERROR: Failed to check database status: {e}")
        import traceback
        traceback.print_exc()

def show_raw_database_content():
    """Show raw database content for debugging"""
    print("\n🔍 RAW DATABASE CONTENT:")
    print("=" * 60)
    
    try:
        trade_db = TradeDatabase()
        
        if not trade_db.trades:
            print("📊 No trades in database")
            return
        
        print(f"📊 Raw database structure:")
        for trade_id, trade_data in trade_db.trades.items():
            print(f"\n📋 {trade_id}:")
            for key, value in trade_data.items():
                print(f"   {key}: {value}")
    
    except Exception as e:
        print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    check_database_status()
    
    # Ask if user wants to see raw content
    print("\n" + "=" * 60)
    response = input("🔍 Show raw database content? (y/n): ")
    if response.lower() in ['y', 'yes']:
        show_raw_database_content()
