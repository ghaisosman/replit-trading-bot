
#!/usr/bin/env python3
"""
Comprehensive Trade Report
Analyze all trades in the system and provide detailed insights
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.analytics.trade_logger import trade_logger
from datetime import datetime
import json


def analyze_all_trades():
    """Generate comprehensive analysis of all trades"""
    print("📊 COMPREHENSIVE TRADE ANALYSIS")
    print("=" * 50)
    
    # Load data from both sources
    trade_db = TradeDatabase()
    
    print(f"\n📈 TRADE DATABASE OVERVIEW")
    print("-" * 30)
    print(f"Total trades in database: {len(trade_db.trades)}")
    
    # Analyze database trades
    db_open = []
    db_closed = []
    
    for trade_id, trade_data in trade_db.trades.items():
        status = trade_data.get('trade_status', 'UNKNOWN')
        if status == 'OPEN':
            db_open.append((trade_id, trade_data))
        elif status == 'CLOSED':
            db_closed.append((trade_id, trade_data))
    
    print(f"🔓 Open trades: {len(db_open)}")
    print(f"✅ Closed trades: {len(db_closed)}")
    
    # Analyze logger trades
    print(f"\n📊 TRADE LOGGER OVERVIEW")
    print("-" * 30)
    print(f"Total trades in logger: {len(trade_logger.trades)}")
    
    logger_open = [t for t in trade_logger.trades if t.trade_status == "OPEN"]
    logger_closed = [t for t in trade_logger.trades if t.trade_status == "CLOSED"]
    
    print(f"🔓 Open trades: {len(logger_open)}")
    print(f"✅ Closed trades: {len(logger_closed)}")
    
    # Show open trades details
    if logger_open:
        print(f"\n🔓 OPEN TRADES DETAILS")
        print("-" * 40)
        for trade in logger_open:
            hours_open = (datetime.now() - trade.timestamp).total_seconds() / 3600
            print(f"📝 {trade.trade_id}")
            print(f"   💱 {trade.symbol} | {trade.side}")
            print(f"   💰 Entry: ${trade.entry_price:.2f} | Qty: {trade.quantity}")
            print(f"   💵 Position Value: ${trade.position_value_usdt:.2f}")
            print(f"   ⏰ Open for: {hours_open:.1f} hours")
            print(f"   🎯 Strategy: {trade.strategy_name}")
            print()
    
    # Analyze closed trades performance
    if logger_closed:
        print(f"\n✅ CLOSED TRADES PERFORMANCE")
        print("-" * 40)
        
        # Calculate metrics
        winning_trades = [t for t in logger_closed if t.pnl_usdt and t.pnl_usdt > 0]
        losing_trades = [t for t in logger_closed if t.pnl_usdt and t.pnl_usdt < 0]
        
        total_pnl = sum(t.pnl_usdt for t in logger_closed if t.pnl_usdt)
        win_rate = (len(winning_trades) / len(logger_closed)) * 100 if logger_closed else 0
        
        avg_win = sum(t.pnl_usdt for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t.pnl_usdt for t in losing_trades) / len(losing_trades) if losing_trades else 0
        
        print(f"📊 Total closed trades: {len(logger_closed)}")
        print(f"🏆 Winning trades: {len(winning_trades)}")
        print(f"❌ Losing trades: {len(losing_trades)}")
        print(f"📈 Win rate: {win_rate:.1f}%")
        print(f"💰 Total P&L: ${total_pnl:.2f}")
        print(f"📊 Average win: ${avg_win:.2f}")
        print(f"📉 Average loss: ${avg_loss:.2f}")
        
        if avg_loss != 0:
            profit_factor = abs(avg_win / avg_loss) if avg_loss < 0 else 0
            print(f"🎯 Profit factor: {profit_factor:.2f}")
        
        # Strategy breakdown
        strategy_stats = {}
        for trade in logger_closed:
            strategy = trade.strategy_name
            if strategy not in strategy_stats:
                strategy_stats[strategy] = {
                    'trades': 0,
                    'wins': 0,
                    'losses': 0,
                    'pnl': 0
                }
            
            strategy_stats[strategy]['trades'] += 1
            if trade.pnl_usdt:
                strategy_stats[strategy]['pnl'] += trade.pnl_usdt
                if trade.pnl_usdt > 0:
                    strategy_stats[strategy]['wins'] += 1
                else:
                    strategy_stats[strategy]['losses'] += 1
        
        print(f"\n🎯 STRATEGY BREAKDOWN")
        print("-" * 30)
        for strategy, stats in strategy_stats.items():
            win_rate_strategy = (stats['wins'] / stats['trades']) * 100 if stats['trades'] else 0
            print(f"📈 {strategy}:")
            print(f"   Trades: {stats['trades']} | Wins: {stats['wins']} | Losses: {stats['losses']}")
            print(f"   Win Rate: {win_rate_strategy:.1f}% | P&L: ${stats['pnl']:.2f}")
            print()
        
        # Recent trades (last 10)
        recent_trades = sorted(logger_closed, key=lambda x: x.timestamp, reverse=True)[:10]
        print(f"\n📝 RECENT CLOSED TRADES (Last 10)")
        print("-" * 40)
        for trade in recent_trades:
            duration_min = trade.duration_minutes or 0
            duration_hours = duration_min / 60
            print(f"🔹 {trade.symbol} | {trade.side} | ${trade.pnl_usdt:+.2f} ({trade.pnl_percentage:+.2f}%)")
            print(f"   Time: {trade.timestamp.strftime('%Y-%m-%d %H:%M')} | Duration: {duration_hours:.1f}h")
            print(f"   Exit: {trade.exit_reason}")
            print()
    
    # Data consistency check
    print(f"\n🔍 DATA CONSISTENCY CHECK")
    print("-" * 30)
    
    # Check for mismatches
    db_trade_ids = set(trade_db.trades.keys())
    logger_trade_ids = set(t.trade_id for t in trade_logger.trades)
    
    only_in_db = db_trade_ids - logger_trade_ids
    only_in_logger = logger_trade_ids - db_trade_ids
    
    print(f"✅ Trades in both systems: {len(db_trade_ids & logger_trade_ids)}")
    print(f"⚠️  Only in database: {len(only_in_db)}")
    print(f"⚠️  Only in logger: {len(only_in_logger)}")
    
    if only_in_db:
        print(f"\n🔍 Trades only in database:")
        for trade_id in list(only_in_db)[:5]:  # Show first 5
            print(f"   - {trade_id}")
    
    if only_in_logger:
        print(f"\n🔍 Trades only in logger:")
        for trade_id in list(only_in_logger)[:5]:  # Show first 5
            print(f"   - {trade_id}")


def show_file_sizes():
    """Show size of trade data files"""
    print(f"\n📁 FILE INFORMATION")
    print("-" * 20)
    
    files_to_check = [
        "trading_data/trades/all_trades.json",
        "trading_data/trades/all_trades.csv", 
        "trading_data/trade_database.json"
    ]
    
    for file_path in files_to_check:
        if os.path.exists(file_path):
            size_bytes = os.path.getsize(file_path)
            size_kb = size_bytes / 1024
            print(f"📄 {file_path}: {size_kb:.1f} KB ({size_bytes} bytes)")
        else:
            print(f"❌ {file_path}: Not found")


if __name__ == "__main__":
    analyze_all_trades()
    show_file_sizes()
    
    print(f"\n" + "=" * 50)
    print(f"🎯 SUMMARY: Analysis complete!")
    print(f"💡 This report shows your complete trading history and performance.")
    print(f"=" * 50)
