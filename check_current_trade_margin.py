
#!/usr/bin/env python3
"""
Check and Fix Current Trade Margin Data
Verify and fix margin information for the current open SOLUSDT trade
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.binance_client.client import BinanceClientWrapper
from datetime import datetime

def check_and_fix_current_trade_margin():
    print("🔍 CHECKING AND FIXING CURRENT TRADE MARGIN DATA")
    print("=" * 60)
    
    # Initialize database and client
    trade_db = TradeDatabase()
    binance_client = BinanceClientWrapper()
    
    # Find the current open SOLUSDT trade
    current_open_trade = None
    current_trade_id = None
    
    for trade_id, trade_data in trade_db.trades.items():
        if (trade_data.get('trade_status') == 'OPEN' and 
            trade_data.get('symbol') == 'SOLUSDT'):
            current_open_trade = trade_data
            current_trade_id = trade_id
            break
    
    if not current_open_trade:
        print("❌ No open SOLUSDT trade found in database")
        return
    
    print(f"📊 Found open trade: {current_trade_id}")
    print(f"   Strategy: {current_open_trade.get('strategy_name')}")
    print(f"   Symbol: {current_open_trade.get('symbol')}")
    print(f"   Side: {current_open_trade.get('side')}")
    print(f"   Quantity: {current_open_trade.get('quantity')}")
    print(f"   Entry Price: ${current_open_trade.get('entry_price')}")
    
    # Check current margin data
    print(f"\n💰 CURRENT MARGIN DATA:")
    position_value_usdt = current_open_trade.get('position_value_usdt')
    leverage = current_open_trade.get('leverage')
    margin_used = current_open_trade.get('margin_used')
    
    print(f"   Position Value USDT: {position_value_usdt}")
    print(f"   Leverage: {leverage}x")
    print(f"   Margin Used: ${margin_used} USDT")
    
    # Check what needs to be fixed
    needs_fix = False
    updates = {}
    
    entry_price = float(current_open_trade.get('entry_price', 0))
    quantity = float(current_open_trade.get('quantity', 0))
    
    # Calculate correct position value
    calculated_position_value = entry_price * quantity
    if position_value_usdt is None or position_value_usdt != calculated_position_value:
        updates['position_value_usdt'] = calculated_position_value
        needs_fix = True
        print(f"   ✅ Will fix Position Value: ${calculated_position_value:.2f} USDT")
    
    # Get actual leverage from Binance
    actual_leverage = leverage
    try:
        if binance_client.is_futures:
            account_info = binance_client.client.futures_account()
            positions = account_info.get('positions', [])
            for pos in positions:
                if pos.get('symbol') == 'SOLUSDT':
                    actual_leverage = int(pos.get('leverage', 1))
                    break
    except Exception as e:
        print(f"   ⚠️ Could not get leverage from Binance: {e}")
    
    if leverage is None or leverage != actual_leverage:
        updates['leverage'] = actual_leverage
        needs_fix = True
        print(f"   ✅ Will fix Leverage: {actual_leverage}x")
    
    # Calculate correct margin used
    final_position_value = updates.get('position_value_usdt', position_value_usdt or calculated_position_value)
    final_leverage = updates.get('leverage', leverage or actual_leverage)
    calculated_margin = final_position_value / final_leverage
    
    if margin_used is None or abs(margin_used - calculated_margin) > 0.01:
        updates['margin_used'] = calculated_margin
        needs_fix = True
        print(f"   ✅ Will fix Margin Used: ${calculated_margin:.2f} USDT")
    
    if needs_fix:
        print(f"\n🔧 APPLYING FIXES...")
        
        # Add update metadata
        updates['last_updated'] = datetime.now().isoformat()
        updates['margin_fix_applied'] = True
        updates['margin_fix_timestamp'] = datetime.now().isoformat()
        
        # Update the trade
        trade_db.trades[current_trade_id].update(updates)
        trade_db._save_database()
        
        print(f"✅ Successfully updated trade {current_trade_id}")
        print(f"\n📊 UPDATED MARGIN DATA:")
        print(f"   Position Value: ${trade_db.trades[current_trade_id]['position_value_usdt']:.2f} USDT")
        print(f"   Leverage: {trade_db.trades[current_trade_id]['leverage']}x")
        print(f"   Margin Used: ${trade_db.trades[current_trade_id]['margin_used']:.2f} USDT")
        
        # Verify the fix worked
        print(f"\n🔍 VERIFICATION:")
        expected_margin = trade_db.trades[current_trade_id]['position_value_usdt'] / trade_db.trades[current_trade_id]['leverage']
        actual_margin = trade_db.trades[current_trade_id]['margin_used']
        if abs(expected_margin - actual_margin) < 0.01:
            print(f"   ✅ Margin calculation is now CORRECT")
        else:
            print(f"   ❌ Margin calculation still incorrect")
        
    else:
        print(f"\n✅ No fixes needed - margin data is already correct!")
    
    print(f"\n🎯 SUMMARY:")
    final_trade = trade_db.trades[current_trade_id]
    print(f"   💰 Position Value: ${final_trade['position_value_usdt']:.2f} USDT")
    print(f"   ⚡ Leverage: {final_trade['leverage']}x")
    print(f"   💵 Margin Invested: ${final_trade['margin_used']:.2f} USDT")
    print(f"   📊 This should now match your 4.9 USDT configuration!")

if __name__ == "__main__":
    check_and_fix_current_trade_margin()
