
#!/usr/bin/env python3
"""
Fix Current XRPUSDT Trade Margin Recording
Diagnose and fix the margin recording issue for the current open trade
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.binance_client.client import BinanceClientWrapper
from datetime import datetime

def main():
    print("🔧 FIXING CURRENT XRPUSDT TRADE MARGIN RECORDING")
    print("=" * 60)
    
    # Initialize components
    trade_db = TradeDatabase()
    binance_client = BinanceClientWrapper()
    
    # Find the current XRPUSDT trade
    current_xrp_trade = None
    current_trade_id = None
    
    print("🔍 SEARCHING for current XRPUSDT trade...")
    for trade_id, trade_data in trade_db.trades.items():
        if (trade_data.get('trade_status') == 'OPEN' and 
            'XRP' in trade_data.get('symbol', '')):
            current_xrp_trade = trade_data
            current_trade_id = trade_id
            break
    
    if not current_xrp_trade:
        print("❌ No open XRPUSDT trade found in database")
        return
    
    print(f"✅ Found current trade: {current_trade_id}")
    print(f"   Symbol: {current_xrp_trade.get('symbol')}")
    print(f"   Side: {current_xrp_trade.get('side')}")
    print(f"   Quantity: {current_xrp_trade.get('quantity')}")
    print(f"   Entry Price: ${current_xrp_trade.get('entry_price')}")
    print(f"   Current Margin: ${current_xrp_trade.get('margin_used', 'MISSING')}")
    print(f"   Leverage: {current_xrp_trade.get('leverage', 'MISSING')}")
    
    # Get current Binance position for verification
    print("\n🔍 FETCHING Binance position...")
    try:
        positions = binance_client.client.futures_position_information(symbol='XRPUSDT')
        binance_position = None
        for position in positions:
            position_amt = float(position.get('positionAmt', 0))
            if abs(position_amt) > 0.001:
                binance_position = position
                break
        
        if binance_position:
            print(f"✅ Binance position found:")
            print(f"   Position Amount: {binance_position.get('positionAmt')}")
            print(f"   Entry Price: ${binance_position.get('entryPrice')}")
            print(f"   Mark Price: ${binance_position.get('markPrice')}")
            print(f"   PnL: ${binance_position.get('unrealizedPnl')}")
        else:
            print("❌ No matching position found on Binance")
            return
            
    except Exception as e:
        print(f"❌ Error fetching Binance position: {e}")
        return
    
    # Calculate correct margin values
    print("\n🔧 CALCULATING correct margin values...")
    
    entry_price = float(current_xrp_trade.get('entry_price', 0))
    quantity = float(current_xrp_trade.get('quantity', 0))
    leverage = current_xrp_trade.get('leverage', 3)  # Default from your config
    
    if leverage == 0 or leverage is None:
        leverage = 3  # Default leverage
        print(f"⚠️ Using default leverage: {leverage}x")
    
    # Calculate position value and margin
    position_value_usdt = entry_price * quantity
    correct_margin = position_value_usdt / leverage
    
    print(f"📊 CALCULATIONS:")
    print(f"   Entry Price: ${entry_price}")
    print(f"   Quantity: {quantity}")
    print(f"   Position Value: ${position_value_usdt:.2f} USDT")
    print(f"   Leverage: {leverage}x")
    print(f"   Correct Margin: ${correct_margin:.2f} USDT")
    
    # Check if margin is incorrect
    current_margin = current_xrp_trade.get('margin_used', 0)
    if abs(current_margin - correct_margin) > 0.01:
        print(f"\n❌ MARGIN MISMATCH DETECTED!")
        print(f"   Database Margin: ${current_margin}")
        print(f"   Correct Margin: ${correct_margin:.2f}")
        print(f"   Difference: ${correct_margin - current_margin:.2f}")
        
        # Fix the margin
        print(f"\n🔧 FIXING margin in database...")
        updates = {
            'margin_used': correct_margin,
            'position_value_usdt': position_value_usdt,
            'leverage': leverage,
            'data_fixed': True,
            'fix_timestamp': datetime.now().isoformat(),
            'fix_reason': 'Zero margin recording bug fix'
        }
        
        trade_db.update_trade(current_trade_id, updates)
        print(f"✅ Trade margin FIXED successfully!")
        
        # Verify the fix
        updated_trade = trade_db.get_trade(current_trade_id)
        print(f"✅ VERIFICATION:")
        print(f"   Updated Margin: ${updated_trade.get('margin_used')}")
        print(f"   Updated Position Value: ${updated_trade.get('position_value_usdt')}")
        print(f"   Updated Leverage: {updated_trade.get('leverage')}")
        
    else:
        print(f"\n✅ Margin is already correct: ${current_margin:.2f} USDT")
    
    # Show route analysis
    print(f"\n🔍 ROUTE ANALYSIS:")
    print(f"   Trade ID: {current_trade_id}")
    print(f"   Strategy: {current_xrp_trade.get('strategy_name', 'UNKNOWN')}")
    print(f"   Created: {current_xrp_trade.get('created_at', 'UNKNOWN')}")
    print(f"   Last Updated: {current_xrp_trade.get('last_updated', 'UNKNOWN')}")
    print(f"   Order ID: {current_xrp_trade.get('order_id', 'UNKNOWN')}")
    
    # Check for recovery indicators
    if 'RECOVERED' in current_trade_id:
        print(f"⚠️ This trade was RECOVERED from Binance - may have incomplete data")
        print(f"   Recovery Source: {current_xrp_trade.get('recovery_source', 'Unknown')}")
    
    print(f"\n✅ DIAGNOSIS COMPLETE")

if __name__ == "__main__":
    main()
