
#!/usr/bin/env python3
"""
XRP Double Logging Investigation
Investigate why the RSI strategy on XRP creates 2 database entries when opening a trade
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.analytics.trade_logger import trade_logger
from src.binance_client.client import BinanceClientWrapper
from datetime import datetime, timedelta
import json

def investigate_xrp_double_logging():
    """Investigate why XRP RSI strategy creates duplicate database entries"""
    print("🔍 INVESTIGATING XRP DOUBLE LOGGING ISSUE")
    print("=" * 60)
    
    # Load systems
    trade_db = TradeDatabase()
    binance_client = BinanceClientWrapper()
    
    print(f"📊 CURRENT STATE:")
    print(f"   Database trades: {len(trade_db.trades)}")
    print(f"   Logger trades: {len(trade_logger.trades)}")
    
    # 1. FIND ALL XRP TRADES
    print(f"\n🔍 STEP 1: ANALYZING XRP TRADES")
    print("-" * 40)
    
    xrp_trades_db = []
    xrp_trades_logger = []
    
    # Database XRP trades
    for trade_id, trade_data in trade_db.trades.items():
        symbol = trade_data.get('symbol', '')
        if 'XRP' in symbol.upper():
            xrp_trades_db.append((trade_id, trade_data))
    
    # Logger XRP trades
    for trade in trade_logger.trades:
        if 'XRP' in trade.symbol.upper():
            xrp_trades_logger.append(trade)
    
    print(f"📈 XRP trades in database: {len(xrp_trades_db)}")
    print(f"📈 XRP trades in logger: {len(xrp_trades_logger)}")
    
    # Show all XRP trades with details
    if xrp_trades_db:
        print(f"\n🔍 DATABASE XRP TRADES:")
        for i, (trade_id, trade_data) in enumerate(xrp_trades_db, 1):
            strategy = trade_data.get('strategy_name', 'N/A')
            status = trade_data.get('trade_status', 'N/A')
            entry_price = trade_data.get('entry_price', 0)
            quantity = trade_data.get('quantity', 0)
            timestamp = trade_data.get('timestamp', 'N/A')
            created_at = trade_data.get('created_at', 'N/A')
            
            print(f"   {i}. Trade ID: {trade_id}")
            print(f"      Strategy: {strategy}")
            print(f"      Status: {status}")
            print(f"      Entry Price: ${entry_price}")
            print(f"      Quantity: {quantity}")
            print(f"      Timestamp: {timestamp}")
            print(f"      Created At: {created_at}")
            
            # Check if this is RSI strategy
            if 'rsi' in strategy.lower():
                print(f"      🎯 RSI STRATEGY DETECTED")
            print()
    
    if xrp_trades_logger:
        print(f"\n🔍 LOGGER XRP TRADES:")
        for i, trade in enumerate(xrp_trades_logger, 1):
            print(f"   {i}. Trade ID: {trade.trade_id}")
            print(f"      Strategy: {trade.strategy_name}")
            print(f"      Status: {trade.trade_status}")
            print(f"      Entry Price: ${trade.entry_price}")
            print(f"      Quantity: {trade.quantity}")
            print(f"      Timestamp: {trade.timestamp}")
            
            if 'rsi' in trade.strategy_name.lower():
                print(f"      🎯 RSI STRATEGY DETECTED")
            print()
    
    # 2. CHECK FOR DUPLICATE PATTERNS
    print(f"\n🔍 STEP 2: ANALYZING DUPLICATE PATTERNS")
    print("-" * 40)
    
    # Group XRP trades by similar characteristics
    trade_groups = {}
    
    for trade_id, trade_data in xrp_trades_db:
        # Create a signature for similar trades
        signature = (
            trade_data.get('strategy_name', ''),
            trade_data.get('symbol', ''),
            trade_data.get('side', ''),
            round(float(trade_data.get('entry_price', 0)), 4),
            round(float(trade_data.get('quantity', 0)), 6)
        )
        
        if signature not in trade_groups:
            trade_groups[signature] = []
        trade_groups[signature].append((trade_id, trade_data))
    
    duplicates_found = False
    print(f"📊 Found {len(trade_groups)} unique trade signatures")
    
    for signature, trades in trade_groups.items():
        if len(trades) > 1:
            duplicates_found = True
            strategy, symbol, side, entry_price, quantity = signature
            print(f"\n🚨 DUPLICATE GROUP FOUND:")
            print(f"   Strategy: {strategy}")
            print(f"   Symbol: {symbol}")
            print(f"   Side: {side}")
            print(f"   Entry Price: ${entry_price}")
            print(f"   Quantity: {quantity}")
            print(f"   Number of duplicates: {len(trades)}")
            
            print(f"   📋 DUPLICATE DETAILS:")
            for j, (trade_id, trade_data) in enumerate(trades, 1):
                timestamp = trade_data.get('timestamp', 'N/A')
                created_at = trade_data.get('created_at', 'N/A')
                status = trade_data.get('trade_status', 'N/A')
                
                print(f"      {j}. ID: {trade_id}")
                print(f"         Status: {status}")
                print(f"         Timestamp: {timestamp}")
                print(f"         Created At: {created_at}")
                
                # Parse timestamps to find time difference
                try:
                    if timestamp != 'N/A' and created_at != 'N/A':
                        ts1 = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        ts2 = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        time_diff = abs((ts2 - ts1).total_seconds())
                        print(f"         Time difference: {time_diff:.2f} seconds")
                except:
                    pass
                print()
    
    if not duplicates_found:
        print("✅ No exact duplicates found in database")
    
    # 3. CHECK BINANCE ACTUAL POSITIONS
    print(f"\n🔍 STEP 3: CHECKING ACTUAL BINANCE POSITIONS")
    print("-" * 40)
    
    try:
        account_info = binance_client.client.futures_account()
        positions = account_info.get('positions', [])
        
        xrp_positions = []
        for position in positions:
            if 'XRP' in position.get('symbol', '').upper():
                position_amt = float(position.get('positionAmt', 0))
                if abs(position_amt) > 0.001:  # Filter out zero positions
                    xrp_positions.append({
                        'symbol': position.get('symbol'),
                        'positionAmt': position_amt,
                        'entryPrice': float(position.get('entryPrice', 0)),
                        'markPrice': float(position.get('markPrice', 0)),
                        'unrealizedProfit': float(position.get('unRealizedProfit', 0))
                    })
        
        print(f"📊 Actual XRP positions on Binance: {len(xrp_positions)}")
        
        for i, pos in enumerate(xrp_positions, 1):
            side = 'LONG' if pos['positionAmt'] > 0 else 'SHORT'
            print(f"   {i}. {pos['symbol']}: {side}")
            print(f"      Position Size: {abs(pos['positionAmt'])}")
            print(f"      Entry Price: ${pos['entryPrice']}")
            print(f"      Mark Price: ${pos['markPrice']}")
            print(f"      Unrealized PnL: ${pos['unrealizedProfit']}")
            print()
        
        # Compare with database trades
        if len(xrp_trades_db) != len(xrp_positions):
            print(f"🚨 MISMATCH DETECTED:")
            print(f"   Database shows {len(xrp_trades_db)} XRP trades")
            print(f"   Binance shows {len(xrp_positions)} actual XRP positions")
            print(f"   Difference: {len(xrp_trades_db) - len(xrp_positions)} extra database entries")
    
    except Exception as e:
        print(f"❌ Error checking Binance positions: {e}")
    
    # 4. ANALYZE LOGGING FLOW
    print(f"\n🔍 STEP 4: ANALYZING LOGGING FLOW")
    print("-" * 40)
    
    print("🔍 CHECKING TRADE LOGGING MECHANISMS:")
    
    # Check if there are multiple entry points for trade logging
    print("   📝 Trade Logger entry points:")
    print("      - log_trade_entry() method")
    print("      - log_trade() method")
    print("      - _sync_to_database() method")
    
    print("   💾 Database entry points:")
    print("      - add_trade() method")
    print("      - update_trade() method")
    print("      - sync_from_logger() method")
    
    # 5. RECENT ACTIVITY ANALYSIS
    print(f"\n🔍 STEP 5: RECENT ACTIVITY ANALYSIS")
    print("-" * 40)
    
    # Look for recent XRP trades (last 24 hours)
    cutoff_time = datetime.now() - timedelta(hours=24)
    recent_xrp_trades = []
    
    for trade_id, trade_data in xrp_trades_db:
        timestamp_str = trade_data.get('timestamp', '')
        if timestamp_str:
            try:
                trade_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                if trade_time > cutoff_time:
                    recent_xrp_trades.append((trade_id, trade_data, trade_time))
            except:
                pass
    
    if recent_xrp_trades:
        print(f"📊 Recent XRP trades (last 24h): {len(recent_xrp_trades)}")
        
        # Sort by timestamp
        recent_xrp_trades.sort(key=lambda x: x[2])
        
        for i, (trade_id, trade_data, trade_time) in enumerate(recent_xrp_trades):
            strategy = trade_data.get('strategy_name', 'N/A')
            status = trade_data.get('trade_status', 'N/A')
            hours_ago = (datetime.now() - trade_time).total_seconds() / 3600
            
            print(f"   {i+1}. {trade_id}")
            print(f"      Strategy: {strategy}")
            print(f"      Status: {status}")
            print(f"      Time: {hours_ago:.1f} hours ago")
            
            if 'rsi' in strategy.lower():
                print(f"      🎯 RSI STRATEGY - POTENTIAL DUPLICATE SOURCE")
            print()
    else:
        print("📊 No recent XRP trades found in last 24 hours")
    
    # 6. SUMMARY AND DIAGNOSIS
    print(f"\n🎯 STEP 6: DIAGNOSIS SUMMARY")
    print("-" * 40)
    
    print("🔍 ROOT CAUSE ANALYSIS:")
    
    if duplicates_found:
        print("   🚨 CONFIRMED: Duplicate trades found in database")
        print("   📋 LIKELY CAUSES:")
        print("      1. Trade logger calling _sync_to_database() multiple times")
        print("      2. Strategy processor triggering multiple trade entries")
        print("      3. Race condition in trade logging flow")
        print("      4. Error handling causing retry logic to create duplicates")
    else:
        print("   ✅ No exact duplicates found")
        print("   📋 POSSIBLE ISSUES:")
        print("      1. Stale trades from previous sessions")
        print("      2. Failed position closures not updating database")
        print("      3. Manual position management outside bot")
    
    if len(xrp_trades_db) > len(xrp_positions):
        print(f"\n   🚨 DATABASE BLOAT DETECTED:")
        print(f"      Database has {len(xrp_trades_db) - len(xrp_positions)} more XRP entries than actual positions")
        print(f"      This suggests incomplete trade lifecycle management")
    
    print(f"\n🔧 RECOMMENDED INVESTIGATION STEPS:")
    print("   1. Monitor next XRP RSI trade opening in real-time")
    print("   2. Add debug logging to trace exact call flow")
    print("   3. Check for race conditions in multi-threaded execution")
    print("   4. Verify RSI strategy configuration for duplicate signals")
    
    print(f"\n" + "=" * 60)
    print("🎯 INVESTIGATION COMPLETE")

if __name__ == "__main__":
    investigate_xrp_double_logging()
