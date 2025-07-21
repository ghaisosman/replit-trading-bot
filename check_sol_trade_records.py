
#!/usr/bin/env python3
"""
Check SOL Trade Records
Investigate the old SOL trade and new trade data completeness
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.analytics.trade_logger import trade_logger
from datetime import datetime
import json

def check_sol_trade_records():
    """Check SOL trade records for completeness"""
    print("🔍 SOL TRADE RECORDS INVESTIGATION")
    print("=" * 50)

    # Load trade database
    trade_db = TradeDatabase()
    
    print(f"📊 Total trades in database: {len(trade_db.trades)}")
    
    # Find all SOL-related trades
    sol_trades = []
    for trade_id, trade_data in trade_db.trades.items():
        symbol = trade_data.get('symbol', '')
        if 'SOL' in symbol.upper():
            sol_trades.append((trade_id, trade_data))
    
    print(f"\n🪙 SOL TRADES FOUND: {len(sol_trades)}")
    print("-" * 30)
    
    # Analyze each SOL trade
    for i, (trade_id, trade_data) in enumerate(sol_trades, 1):
        print(f"\n{i}. Trade ID: {trade_id}")
        print(f"   Symbol: {trade_data.get('symbol', 'N/A')}")
        print(f"   Status: {trade_data.get('trade_status', 'N/A')}")
        print(f"   Strategy: {trade_data.get('strategy_name', 'N/A')}")
        print(f"   Created: {trade_data.get('created_at', 'N/A')}")
        print(f"   Timestamp: {trade_data.get('timestamp', 'N/A')}")
        
        # Check for missing critical fields
        critical_fields = ['margin_used', 'leverage', 'position_value_usdt']
        missing_fields = []
        for field in critical_fields:
            if field not in trade_data or trade_data[field] is None:
                missing_fields.append(field)
        
        if missing_fields:
            print(f"   ❌ Missing fields: {missing_fields}")
        else:
            print(f"   ✅ All critical fields present")
            print(f"   💰 Margin used: ${trade_data.get('margin_used', 0):.2f}")
            print(f"   🔢 Leverage: {trade_data.get('leverage', 0)}x")
            print(f"   💵 Position value: ${trade_data.get('position_value_usdt', 0):.2f}")
        
        # Check technical indicators
        tech_indicators = ['rsi_at_entry', 'macd_at_entry', 'sma_20_at_entry', 'sma_50_at_entry']
        missing_tech = []
        for field in tech_indicators:
            if field not in trade_data or trade_data[field] is None:
                missing_tech.append(field)
        
        if missing_tech:
            print(f"   📊 Missing indicators: {missing_tech}")
        else:
            print(f"   📊 Technical indicators complete")
        
        # If closed, check exit data
        if trade_data.get('trade_status') == 'CLOSED':
            exit_fields = ['exit_price', 'pnl_usdt', 'exit_reason']
            missing_exit = []
            for field in exit_fields:
                if field not in trade_data or trade_data[field] is None:
                    missing_exit.append(field)
            
            if missing_exit:
                print(f"   🚪 Missing exit data: {missing_exit}")
            else:
                print(f"   🚪 Exit data complete")
                print(f"   💰 P&L: ${trade_data.get('pnl_usdt', 0):.2f}")
                print(f"   🚪 Exit reason: {trade_data.get('exit_reason', 'N/A')}")
    
    # Check trade logger for SOL trades
    print(f"\n📝 TRADE LOGGER SOL TRADES:")
    print("-" * 30)
    
    logger_sol_trades = []
    for trade in trade_logger.trades:
        if 'SOL' in trade.symbol.upper():
            logger_sol_trades.append(trade)
    
    print(f"Found {len(logger_sol_trades)} SOL trades in logger")
    
    for i, trade in enumerate(logger_sol_trades, 1):
        print(f"\n{i}. Logger Trade ID: {trade.trade_id}")
        print(f"   Symbol: {trade.symbol}")
        print(f"   Status: {trade.trade_status}")
        print(f"   Strategy: {trade.strategy_name}")
        print(f"   Entry Price: ${trade.entry_price}")
        print(f"   Quantity: {trade.quantity}")
        
        # Check if this trade exists in database
        db_trade = trade_db.trades.get(trade.trade_id)
        if db_trade:
            print(f"   🔗 Linked to database trade")
            
            # Compare completeness
            db_has_margin = db_trade.get('margin_used') is not None
            db_has_leverage = db_trade.get('leverage') is not None
            db_has_position_value = db_trade.get('position_value_usdt') is not None
            
            logger_has_margin = trade.margin_used is not None
            logger_has_leverage = trade.leverage is not None
            logger_has_position_value = trade.position_value_usdt is not None
            
            print(f"   📊 Database completeness: Margin:{db_has_margin} Leverage:{db_has_leverage} Value:{db_has_position_value}")
            print(f"   📊 Logger completeness: Margin:{logger_has_margin} Leverage:{logger_has_leverage} Value:{logger_has_position_value}")
            
        else:
            print(f"   ⚠️ NOT found in database")

    # Summary analysis
    print(f"\n📋 SUMMARY ANALYSIS:")
    print("-" * 20)
    
    open_sol_trades = [t for _, t in sol_trades if t.get('trade_status') == 'OPEN']
    closed_sol_trades = [t for _, t in sol_trades if t.get('trade_status') == 'CLOSED']
    
    print(f"📊 Open SOL trades: {len(open_sol_trades)}")
    print(f"📊 Closed SOL trades: {len(closed_sol_trades)}")
    
    # Check if new trades (after fix) have complete data
    print(f"\n🔧 POST-FIX TRADE ANALYSIS:")
    print("-" * 25)
    
    # Trades created today are likely post-fix
    today = datetime.now().strftime('%Y-%m-%d')
    recent_trades = []
    
    for trade_id, trade_data in sol_trades:
        created_at = trade_data.get('created_at', '')
        if today in created_at:
            recent_trades.append((trade_id, trade_data))
    
    print(f"📅 Recent SOL trades (today): {len(recent_trades)}")
    
    for trade_id, trade_data in recent_trades:
        print(f"\n🆕 Recent Trade: {trade_id}")
        
        # Check completeness of recent trade
        critical_fields = ['margin_used', 'leverage', 'position_value_usdt']
        complete_fields = 0
        total_fields = len(critical_fields)
        
        for field in critical_fields:
            if field in trade_data and trade_data[field] is not None:
                complete_fields += 1
                print(f"   ✅ {field}: {trade_data[field]}")
            else:
                print(f"   ❌ {field}: Missing")
        
        completeness_pct = (complete_fields / total_fields) * 100
        print(f"   📊 Completeness: {completeness_pct:.1f}% ({complete_fields}/{total_fields})")
        
        if completeness_pct < 100:
            print(f"   🚨 ISSUE: Recent trade still missing data after database fix!")
        else:
            print(f"   ✅ GOOD: Recent trade has complete data")

if __name__ == "__main__":
    check_sol_trade_records()
