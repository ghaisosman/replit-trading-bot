
#!/usr/bin/env python3
"""
Detailed Trade Investigation
Identify exactly which trades are phantom and why cleanup isn't working
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.binance_client.client import BinanceClientWrapper
from src.config.global_config import global_config
from datetime import datetime
import json

def investigate_phantom_trades():
    """Deep investigation of phantom trades"""
    print("🔍 DETAILED PHANTOM TRADE INVESTIGATION")
    print("=" * 60)
    
    # 1. Load Trade Database and analyze each open trade
    trade_db = TradeDatabase()
    binance_client = BinanceClientWrapper()
    
    # Get actual Binance positions
    account_info = binance_client.client.futures_account()
    positions = account_info.get('positions', [])
    
    actual_binance_positions = {}
    for position in positions:
        symbol = position.get('symbol')
        position_amt = float(position.get('positionAmt', 0))
        if abs(position_amt) > 0.0001:  # Position exists
            actual_binance_positions[symbol] = {
                'position_amt': position_amt,
                'entry_price': float(position.get('entryPrice', 0)),
                'side': 'BUY' if position_amt > 0 else 'SELL',
                'quantity': abs(position_amt)
            }
    
    print(f"📊 ACTUAL BINANCE POSITIONS: {len(actual_binance_positions)}")
    for symbol, pos in actual_binance_positions.items():
        print(f"   🔸 {symbol}: {pos['side']} | Qty: {pos['quantity']} | Entry: ${pos['entry_price']}")
    
    # 2. Analyze each open trade in database
    print(f"\n📊 DATABASE OPEN TRADES ANALYSIS:")
    print("-" * 40)
    
    open_trades = []
    for trade_id, trade_data in trade_db.trades.items():
        if trade_data.get('trade_status') == 'OPEN':
            open_trades.append((trade_id, trade_data))
    
    print(f"Found {len(open_trades)} open trades in database")
    
    legitimate_trades = []
    phantom_trades = []
    
    for i, (trade_id, trade_data) in enumerate(open_trades, 1):
        symbol = trade_data.get('symbol')
        strategy = trade_data.get('strategy_name')
        side = trade_data.get('side')
        quantity = trade_data.get('quantity')
        entry_price = trade_data.get('entry_price')
        timestamp = trade_data.get('timestamp')
        
        print(f"\n📋 TRADE #{i}: {trade_id}")
        print(f"   Strategy: {strategy}")
        print(f"   Symbol: {symbol}")
        print(f"   Side: {side}")
        print(f"   Quantity: {quantity}")
        print(f"   Entry Price: ${entry_price}")
        print(f"   Timestamp: {timestamp}")
        
        # Check if this trade matches any actual Binance position
        matches_binance = False
        match_details = "No match"
        
        if symbol in actual_binance_positions:
            binance_pos = actual_binance_positions[symbol]
            
            # Check quantity match
            quantity_diff = abs(binance_pos['quantity'] - quantity)
            quantity_match = quantity_diff < 0.1
            
            # Check side match
            side_match = binance_pos['side'] == side
            
            # Check entry price match (5% tolerance)
            price_diff = abs(binance_pos['entry_price'] - entry_price)
            price_tolerance = entry_price * 0.05
            price_match = price_diff <= price_tolerance
            
            if quantity_match and side_match and price_match:
                matches_binance = True
                match_details = "✅ PERFECT MATCH"
                legitimate_trades.append(trade_id)
            else:
                match_details = f"❌ MISMATCH: Qty diff: {quantity_diff:.6f}, Side: {binance_pos['side']} vs {side}, Price diff: ${price_diff:.2f}"
                phantom_trades.append((trade_id, f"Position mismatch: {match_details}"))
        else:
            match_details = f"❌ SYMBOL NOT ON BINANCE"
            phantom_trades.append((trade_id, "Symbol not found on Binance"))
        
        print(f"   Binance Match: {match_details}")
        
        # Additional analysis - check why cleanup didn't catch this
        hours_old = 0
        if timestamp:
            try:
                entry_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                hours_old = (datetime.now() - entry_time).total_seconds() / 3600
                print(f"   Age: {hours_old:.1f} hours old")
            except:
                print(f"   Age: Invalid timestamp")
        
        # Check cleanup criteria
        cleanup_reasons = []
        
        if not matches_binance:
            cleanup_reasons.append("Should be closed: No matching Binance position")
        
        if strategy == 'RECOVERY' and hours_old > 1:
            cleanup_reasons.append("Should be closed: RECOVERY trade older than 1 hour")
        
        if hours_old > 6:
            cleanup_reasons.append("Should be closed: Trade older than 6 hours")
        
        if cleanup_reasons:
            print(f"   🚨 CLEANUP ISSUES:")
            for reason in cleanup_reasons:
                print(f"      - {reason}")
        else:
            print(f"   ✅ No cleanup issues detected")
    
    # 3. Summary
    print(f"\n🎯 SUMMARY:")
    print(f"   📊 Total open trades in database: {len(open_trades)}")
    print(f"   ✅ Legitimate trades: {len(legitimate_trades)}")
    print(f"   👻 Phantom trades: {len(phantom_trades)}")
    print(f"   🔸 Expected legitimate trades: {len(actual_binance_positions)}")
    
    if len(legitimate_trades) != len(actual_binance_positions):
        print(f"   🚨 DISCREPANCY: Expected {len(actual_binance_positions)} legitimate trades but found {len(legitimate_trades)}")
    
    # 4. Detailed phantom trade analysis
    if phantom_trades:
        print(f"\n👻 PHANTOM TRADES DETAILED ANALYSIS:")
        print("-" * 40)
        
        for trade_id, reason in phantom_trades:
            print(f"   🚨 {trade_id}: {reason}")
            
            # Check if this trade should have been caught by cleanup
            trade_data = trade_db.trades[trade_id]
            
            print(f"      Strategy: {trade_data.get('strategy_name')}")
            print(f"      Symbol: {trade_data.get('symbol')}")
            print(f"      Why cleanup missed it: INVESTIGATING...")
            
            # Test cleanup logic manually
            symbol = trade_data.get('symbol')
            strategy = trade_data.get('strategy_name')
            timestamp = trade_data.get('timestamp')
            
            cleanup_should_catch = []
            
            # Test Method 1: Binance position check
            if symbol not in actual_binance_positions:
                cleanup_should_catch.append("Method 1: No Binance position")
            
            # Test Method 2: RECOVERY age check
            if strategy == 'RECOVERY' and timestamp:
                try:
                    entry_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    hours_old = (datetime.now() - entry_time).total_seconds() / 3600
                    if hours_old > 1:
                        cleanup_should_catch.append(f"Method 2: RECOVERY {hours_old:.1f}h old")
                except:
                    cleanup_should_catch.append("Method 2: Invalid timestamp")
            
            # Test Method 3: General age check
            if timestamp:
                try:
                    entry_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    hours_old = (datetime.now() - entry_time).total_seconds() / 3600
                    if hours_old > 6:
                        cleanup_should_catch.append(f"Method 3: General {hours_old:.1f}h old")
                except:
                    cleanup_should_catch.append("Method 3: Invalid timestamp")
            
            if cleanup_should_catch:
                print(f"      🔧 CLEANUP SHOULD CATCH via: {', '.join(cleanup_should_catch)}")
                print(f"      🚨 BUG DETECTED: Cleanup logic is not working properly!")
            else:
                print(f"      ❓ UNCLEAR: Why cleanup didn't catch this")
    
    # 5. Recommendations
    print(f"\n🛠️ RECOMMENDATIONS:")
    if phantom_trades:
        print("   1. Run manual cleanup with more aggressive parameters")
        print("   2. Check if cleanup method is actually being called")
        print("   3. Verify cleanup conditions are working correctly")
        print("   4. Force close phantom trades manually")
    else:
        print("   ✅ No phantom trades detected - system is working correctly")

if __name__ == "__main__":
    investigate_phantom_trades()
