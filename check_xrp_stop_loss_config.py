
#!/usr/bin/env python3
"""
Check XRP Trade Stop Loss Configuration
Investigate the stop loss settings for the current XRP trade
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.binance_client.client import BinanceClientWrapper
from src.config.trading_config import trading_config_manager
import json

def check_xrp_stop_loss_config():
    print("🔍 CHECKING XRP TRADE STOP LOSS CONFIGURATION")
    print("=" * 60)
    
    # Initialize components
    trade_db = TradeDatabase()
    binance_client = BinanceClientWrapper()
    
    # Find XRP trade in database
    xrp_trade = None
    xrp_trade_id = None
    xrp_strategy = None
    
    print("📊 SEARCHING FOR XRP TRADE...")
    for trade_id, trade_data in trade_db.trades.items():
        symbol = trade_data.get('symbol', '')
        if 'XRP' in symbol.upper():
            xrp_trade = trade_data
            xrp_trade_id = trade_id
            xrp_strategy = trade_data.get('strategy_name', 'unknown')
            break
    
    if not xrp_trade:
        print("❌ No XRP trade found in database")
        return
    
    print(f"✅ Found XRP trade: {xrp_trade_id}")
    print(f"   Strategy: {xrp_strategy}")
    print(f"   Symbol: {xrp_trade.get('symbol')}")
    print(f"   Status: {xrp_trade.get('trade_status')}")
    
    # 1. DATABASE STOP LOSS CONFIGURATION
    print(f"\n💾 DATABASE STOP LOSS SETTINGS:")
    db_stop_loss = xrp_trade.get('stop_loss')
    db_entry_price = xrp_trade.get('entry_price')
    db_side = xrp_trade.get('side')
    db_margin = xrp_trade.get('margin_used', 0)
    db_max_loss_pct = xrp_trade.get('max_loss_pct', 0)
    
    print(f"   Stop Loss Price: ${db_stop_loss}")
    print(f"   Entry Price: ${db_entry_price}")
    print(f"   Position Side: {db_side}")
    print(f"   Margin Used: ${db_margin}")
    print(f"   Max Loss %: {db_max_loss_pct}%")
    
    # Calculate stop loss percentage
    if db_stop_loss and db_entry_price:
        if db_side == 'BUY':
            sl_distance_pct = ((db_entry_price - db_stop_loss) / db_entry_price) * 100
        else:
            sl_distance_pct = ((db_stop_loss - db_entry_price) / db_entry_price) * 100
        
        print(f"   Stop Loss Distance: {sl_distance_pct:.2f}%")
        
        # Calculate expected loss in USDT
        if db_margin and db_max_loss_pct:
            expected_loss_usdt = db_margin * (db_max_loss_pct / 100)
            print(f"   Expected Max Loss: ${expected_loss_usdt:.2f} USDT")
    
    # 2. STRATEGY CONFIGURATION
    print(f"\n🎯 STRATEGY CONFIGURATION ({xrp_strategy}):")
    try:
        strategy_config = trading_config_manager.get_strategy_config(xrp_strategy, {})
        
        config_margin = strategy_config.get('margin', 'Not set')
        config_leverage = strategy_config.get('leverage', 'Not set')
        config_max_loss_pct = strategy_config.get('max_loss_pct', 'Not set')
        config_symbol = strategy_config.get('symbol', 'Not set')
        
        print(f"   Configured Symbol: {config_symbol}")
        print(f"   Configured Margin: ${config_margin}")
        print(f"   Configured Leverage: {config_leverage}x")
        print(f"   Configured Max Loss %: {config_max_loss_pct}%")
        
        # Show all strategy-specific parameters
        print(f"\n📋 ALL STRATEGY PARAMETERS:")
        for key, value in strategy_config.items():
            if key not in ['symbol', 'margin', 'leverage', 'max_loss_pct']:
                print(f"   {key}: {value}")
                
    except Exception as e:
        print(f"   ❌ Error loading strategy config: {e}")
    
    # 3. BINANCE ACTUAL POSITION (if still open)
    print(f"\n🔗 BINANCE POSITION STATUS:")
    try:
        if xrp_trade.get('trade_status') == 'OPEN':
            symbol = xrp_trade.get('symbol')
            positions = binance_client.get_futures_positions()
            
            xrp_position = None
            for pos in positions:
                if pos['symbol'] == symbol and float(pos['positionAmt']) != 0:
                    xrp_position = pos
                    break
            
            if xrp_position:
                print(f"   ✅ Found active Binance position")
                print(f"   Position Size: {xrp_position['positionAmt']}")
                print(f"   Entry Price: ${xrp_position['entryPrice']}")
                print(f"   Mark Price: ${xrp_position['markPrice']}")
                print(f"   Unrealized PnL: ${xrp_position['unRealizedProfit']}")
                print(f"   Percentage: {xrp_position['percentage']}%")
                
                # Check if there are stop loss orders
                orders = binance_client.get_open_orders(symbol=symbol)
                stop_orders = [order for order in orders if order['type'] == 'STOP_MARKET']
                
                if stop_orders:
                    print(f"   🛑 Active Stop Loss Orders:")
                    for order in stop_orders:
                        print(f"      Order ID: {order['orderId']}")
                        print(f"      Stop Price: ${order['stopPrice']}")
                        print(f"      Quantity: {order['origQty']}")
                else:
                    print(f"   ⚠️ No active stop loss orders found")
            else:
                print(f"   ❌ No active position found on Binance")
        else:
            print(f"   ℹ️ Trade status is {xrp_trade.get('trade_status')} - not checking Binance position")
            
    except Exception as e:
        print(f"   ❌ Error checking Binance position: {e}")
    
    # 4. STOP LOSS CALCULATION ANALYSIS
    print(f"\n🧮 STOP LOSS CALCULATION ANALYSIS:")
    
    if db_margin and db_max_loss_pct and xrp_trade.get('leverage'):
        margin = float(db_margin)
        max_loss_pct = float(db_max_loss_pct)
        leverage = float(xrp_trade.get('leverage'))
        
        # How stop loss should be calculated
        print(f"   Margin: ${margin}")
        print(f"   Max Loss %: {max_loss_pct}%")
        print(f"   Leverage: {leverage}x")
        
        # Expected loss amount
        max_loss_amount = margin * (max_loss_pct / 100)
        print(f"   Expected Max Loss Amount: ${max_loss_amount:.2f}")
        
        # Position value
        position_value = margin * leverage
        print(f"   Position Value: ${position_value:.2f}")
        
        # Stop loss percentage from entry
        stop_loss_pct = (max_loss_amount / position_value) * 100
        print(f"   Stop Loss % from Entry: {stop_loss_pct:.2f}%")
        
        # Theoretical stop loss prices
        if db_entry_price:
            entry = float(db_entry_price)
            if db_side == 'BUY':
                theoretical_sl = entry * (1 - stop_loss_pct / 100)
                print(f"   Theoretical SL Price (LONG): ${theoretical_sl:.6f}")
            else:
                theoretical_sl = entry * (1 + stop_loss_pct / 100)
                print(f"   Theoretical SL Price (SHORT): ${theoretical_sl:.6f}")
            
            # Compare with actual
            if db_stop_loss:
                actual_sl = float(db_stop_loss)
                difference = abs(actual_sl - theoretical_sl)
                print(f"   Actual SL Price: ${actual_sl:.6f}")
                print(f"   Difference: ${difference:.6f}")
                print(f"   Match: {'✅ CLOSE' if difference < 0.001 else '⚠️ DIFFERENT'}")
    
    # 5. RECOMMENDATIONS
    print(f"\n💡 RECOMMENDATIONS:")
    print(f"   • Verify max_loss_pct setting matches your risk tolerance")
    print(f"   • Ensure stop loss is set at appropriate distance from entry")
    print(f"   • Check if Binance stop loss orders are active")
    print(f"   • Monitor unrealized PnL vs expected max loss")

if __name__ == "__main__":
    check_xrp_stop_loss_config()
