
#!/usr/bin/env python3
"""
Check Latest Trade Data Completeness
Verify if the most recent trade has complete data in database
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.analytics.trade_logger import trade_logger
from datetime import datetime, timedelta
import json

def check_latest_trade_data():
    """Check if the latest trade has complete data"""
    print("🔍 CHECKING LATEST TRADE DATA COMPLETENESS")
    print("=" * 50)

    # Load both systems
    trade_db = TradeDatabase()

    # Find ALL open trades first
    open_trades = []
    for trade_id, trade_data in trade_db.trades.items():
        if trade_data.get('trade_status') == 'OPEN':
            timestamp_str = trade_data.get('timestamp', trade_data.get('created_at', ''))
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00')) if timestamp_str else datetime.min
            except:
                timestamp = datetime.min
            open_trades.append((trade_id, trade_data, timestamp))

    if not open_trades:
        print("❌ No open trades found in database")
        return False

    # Sort by timestamp (newest first) 
    open_trades.sort(key=lambda x: x[2], reverse=True)

    print(f"📊 FOUND {len(open_trades)} OPEN TRADES")
    print("-" * 30)

    # Show all open trades for analysis
    for i, (trade_id, trade_data, timestamp) in enumerate(open_trades, 1):
        print(f"\n🔍 TRADE #{i}: {trade_id}")
        print(f"   Strategy: {trade_data.get('strategy_name', 'N/A')}")
        print(f"   Symbol: {trade_data.get('symbol', 'N/A')}")
        print(f"   Side: {trade_data.get('side', 'N/A')}")
        print(f"   Entry Price: ${trade_data.get('entry_price', 0):.4f}")
        print(f"   Quantity: {trade_data.get('quantity', 0)}")
        print(f"   Timestamp: {timestamp}")

    # Use the most recent trade for detailed analysis
    latest_trade_id, latest_trade, latest_timestamp = open_trades[0]

    print(f"📊 LATEST TRADE ANALYSIS")
    print("-" * 30)
    print(f"Trade ID: {latest_trade_id}")

    latest_trade = trade_db.trades[latest_trade_id]
    
    # Basic trade info
    print(f"Strategy: {latest_trade.get('strategy_name', 'N/A')}")
    print(f"Symbol: {latest_trade.get('symbol', 'N/A')}")
    print(f"Side: {latest_trade.get('side', 'N/A')}")
    print(f"Status: {latest_trade.get('trade_status', 'N/A')}")
    print(f"Entry Price: ${latest_trade.get('entry_price', 0):.4f}")
    print(f"Quantity: {latest_trade.get('quantity', 0)}")
    print(f"Timestamp: {latest_trade.get('timestamp', 'N/A')}")

    # Check required fields
    required_fields = [
        'strategy_name', 'symbol', 'side', 'quantity', 'entry_price', 
        'trade_status', 'position_value_usdt', 'leverage', 'margin_used'
    ]

    print(f"\n📋 REQUIRED FIELDS CHECK")
    print("-" * 25)
    missing_required = []
    for field in required_fields:
        if field in latest_trade and latest_trade[field] is not None:
            print(f"✅ {field}: {latest_trade[field]}")
        else:
            print(f"❌ {field}: MISSING")
            missing_required.append(field)

    # Check technical indicators
    technical_fields = [
        'rsi_at_entry', 'macd_at_entry', 'sma_20_at_entry', 'sma_50_at_entry',
        'volume_at_entry', 'entry_signal_strength'
    ]

    print(f"\n📊 TECHNICAL INDICATORS CHECK")
    print("-" * 30)
    missing_technical = []
    for field in technical_fields:
        if field in latest_trade and latest_trade[field] is not None:
            print(f"✅ {field}: {latest_trade[field]}")
        else:
            print(f"❌ {field}: MISSING")
            missing_technical.append(field)

    # Check market conditions
    market_fields = [
        'market_trend', 'volatility_score', 'market_phase'
    ]

    print(f"\n🌍 MARKET CONDITIONS CHECK")
    print("-" * 27)
    missing_market = []
    for field in market_fields:
        if field in latest_trade and latest_trade[field] is not None:
            print(f"✅ {field}: {latest_trade[field]}")
        else:
            print(f"❌ {field}: MISSING")
            missing_market.append(field)

    # Summary
    print(f"\n📈 DATA COMPLETENESS SUMMARY")
    print("-" * 30)
    total_expected = len(required_fields) + len(technical_fields) + len(market_fields)
    total_missing = len(missing_required) + len(missing_technical) + len(missing_market)
    completeness_percent = ((total_expected - total_missing) / total_expected) * 100

    print(f"📊 Data completeness: {completeness_percent:.1f}%")
    print(f"✅ Fields present: {total_expected - total_missing}/{total_expected}")
    
    if missing_required:
        print(f"🚨 CRITICAL: Missing required fields: {missing_required}")
    
    if missing_technical:
        print(f"⚠️ Missing technical indicators: {missing_technical}")
    
    if missing_market:
        print(f"⚠️ Missing market conditions: {missing_market}")

    # Check if trade also exists in trade logger
    print(f"\n🔄 TRADE LOGGER SYNC CHECK")
    print("-" * 25)
    
    logger_trade = None
    for trade in trade_logger.trades:
        if trade.trade_id == latest_trade_id:
            logger_trade = trade
            break

    if logger_trade:
        print(f"✅ Trade found in logger: {latest_trade_id}")
        print(f"   Status: {logger_trade.trade_status}")
        print(f"   Entry Price: ${logger_trade.entry_price:.4f}")
        print(f"   RSI at Entry: {logger_trade.rsi_at_entry}")
        print(f"   MACD at Entry: {logger_trade.macd_at_entry}")
    else:
        print(f"❌ Trade NOT found in logger: {latest_trade_id}")

    # Overall assessment
    print(f"\n🎯 ASSESSMENT")
    print("-" * 15)
    
    if missing_required:
        print(f"🚨 CRITICAL ISSUE: Missing required fields - trade recording is incomplete")
        return False
    elif missing_technical or missing_market:
        print(f"⚠️ PARTIAL ISSUE: Some optional data missing - ML features may be limited")
        return True
    else:
        print(f"✅ SUCCESS: Trade data is complete!")
        return True

if __name__ == "__main__":
    success = check_latest_trade_data()
    
    if not success:
        print(f"\n🔧 NEXT STEPS:")
        print(f"1. Check order_manager._log_trade_entry() function")
        print(f"2. Verify technical indicator calculation")
        print(f"3. Check database add_trade() method")
    else:
        print(f"\n🚀 READY FOR TEST 2: Check anomaly detection behavior")
