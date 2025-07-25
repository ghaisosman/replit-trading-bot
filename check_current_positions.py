
#!/usr/bin/env python3
"""
Check Current Open Positions and Entry Logic
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.binance_client.client import BinanceClientWrapper
from datetime import datetime
import json

def check_current_positions():
    """Check current open positions and analyze entry logic"""
    print("🔍 CURRENT OPEN POSITIONS ANALYSIS")
    print("=" * 60)
    
    # Initialize components
    trade_db = TradeDatabase()
    binance_client = BinanceClientWrapper()
    
    # Get open trades from database
    open_trades = []
    for trade_id, trade_data in trade_db.trades.items():
        if trade_data.get('trade_status') == 'OPEN':
            open_trades.append((trade_id, trade_data))
    
    print(f"📊 Found {len(open_trades)} open trades in database")
    
    # Get actual Binance positions
    binance_positions = {}
    try:
        if binance_client.is_futures:
            account_info = binance_client.client.futures_account()
            all_positions = account_info.get('positions', [])
            
            for position in all_positions:
                symbol = position.get('symbol')
                position_amt = float(position.get('positionAmt', 0))
                if abs(position_amt) > 0.001:  # Only meaningful positions
                    binance_positions[symbol] = {
                        'symbol': symbol,
                        'position_amt': position_amt,
                        'entry_price': float(position.get('entryPrice', 0)),
                        'unrealized_pnl': float(position.get('unRealizedProfit', 0)),
                        'side': 'LONG' if position_amt > 0 else 'SHORT',
                        'quantity': abs(position_amt)
                    }
    except Exception as e:
        print(f"❌ Error fetching Binance positions: {e}")
    
    print(f"📊 Found {len(binance_positions)} active positions on Binance")
    
    if not open_trades and not binance_positions:
        print("✅ No open positions found")
        return
    
    # Analyze each open trade
    print(f"\n📋 DETAILED POSITION ANALYSIS:")
    print("=" * 60)
    
    for i, (trade_id, trade_data) in enumerate(open_trades, 1):
        print(f"\n📊 POSITION #{i}: {trade_id}")
        print("-" * 40)
        
        # Basic trade info
        strategy_name = trade_data.get('strategy_name', 'Unknown')
        symbol = trade_data.get('symbol', 'Unknown')
        side = trade_data.get('side', 'Unknown')
        quantity = trade_data.get('quantity', 0)
        entry_price = trade_data.get('entry_price', 0)
        margin_used = trade_data.get('margin_used', 0)
        leverage = trade_data.get('leverage', 1)
        timestamp = trade_data.get('created_at', 'Unknown')
        
        print(f"🏷️  Strategy: {strategy_name}")
        print(f"💰 Symbol: {symbol}")
        print(f"📈 Side: {side}")
        print(f"📊 Quantity: {quantity}")
        print(f"💵 Entry Price: ${entry_price}")
        print(f"💸 Margin Used: ${margin_used}")
        print(f"⚡ Leverage: {leverage}x")
        print(f"⏰ Created: {timestamp}")
        
        # Check if position exists on Binance
        binance_match = binance_positions.get(symbol)
        if binance_match:
            print(f"✅ BINANCE MATCH FOUND:")
            print(f"   Position Amount: {binance_match['position_amt']}")
            print(f"   Binance Entry: ${binance_match['entry_price']}")
            print(f"   Unrealized PnL: ${binance_match['unrealized_pnl']:.2f}")
            
            # Check for discrepancies
            quantity_diff = abs(binance_match['quantity'] - float(quantity))
            price_diff = abs(binance_match['entry_price'] - float(entry_price))
            
            if quantity_diff > 0.001:
                print(f"⚠️  QUANTITY MISMATCH: DB={quantity}, Binance={binance_match['quantity']}")
            if price_diff > 0.01:
                print(f"⚠️  PRICE MISMATCH: DB=${entry_price}, Binance=${binance_match['entry_price']}")
        else:
            print(f"❌ NO BINANCE POSITION FOUND - This may be an orphan trade")
        
        # Analyze entry logic based on strategy
        print(f"\n🧠 ENTRY LOGIC ANALYSIS FOR {strategy_name}:")
        analyze_entry_logic(strategy_name, trade_data)
    
    # Check for any unmatched Binance positions
    unmatched_binance = []
    db_symbols = {trade_data.get('symbol') for _, trade_data in open_trades}
    
    for symbol, binance_pos in binance_positions.items():
        if symbol not in db_symbols:
            unmatched_binance.append((symbol, binance_pos))
    
    if unmatched_binance:
        print(f"\n🚨 UNMATCHED BINANCE POSITIONS:")
        print("-" * 40)
        for symbol, pos in unmatched_binance:
            print(f"   {symbol}: {pos['side']} | Qty: {pos['quantity']} | PnL: ${pos['unrealized_pnl']:.2f}")
            print(f"   ⚠️  This position exists on Binance but not in database")

def analyze_entry_logic(strategy_name, trade_data):
    """Analyze the entry logic for each strategy type"""
    
    symbol = trade_data.get('symbol', '')
    entry_price = trade_data.get('entry_price', 0)
    side = trade_data.get('side', '')
    
    if 'rsi' in strategy_name.lower():
        print(f"📊 RSI OVERSOLD STRATEGY:")
        print(f"   • Entry Condition: RSI < 30 (oversold)")
        print(f"   • Side: {side} (BUY when oversold)")
        print(f"   • Symbol: {symbol}")
        print(f"   • Entry Price: ${entry_price}")
        print(f"   • Logic: Bot detected RSI below 30 threshold indicating oversold condition")
        print(f"   • Configuration: Dashboard RSI settings applied")
        
    elif 'macd' in strategy_name.lower():
        print(f"📊 MACD DIVERGENCE STRATEGY:")
        print(f"   • Entry Condition: MACD histogram momentum before crossover")
        print(f"   • Side: {side}")
        print(f"   • Symbol: {symbol}")
        print(f"   • Entry Price: ${entry_price}")
        if side == 'BUY':
            print(f"   • Logic: MACD below signal but histogram growing (pre-bullish crossover)")
        else:
            print(f"   • Logic: MACD above signal but histogram shrinking (pre-bearish crossover)")
        print(f"   • Configuration: Dashboard MACD settings applied")
        
    elif 'engulfing' in strategy_name.lower():
        print(f"📊 ENGULFING PATTERN STRATEGY:")
        print(f"   • Entry Condition: Engulfing candlestick pattern + RSI filter")
        print(f"   • Side: {side}")
        print(f"   • Symbol: {symbol}")
        print(f"   • Entry Price: ${entry_price}")
        if side == 'BUY':
            print(f"   • Logic: Bullish engulfing + RSI < 50 + price down over 5 bars")
        else:
            print(f"   • Logic: Bearish engulfing + RSI > 50 + price up over 5 bars")
        print(f"   • Configuration: Dashboard engulfing pattern settings applied")
        
    elif 'smart_money' in strategy_name.lower():
        print(f"📊 SMART MONEY REVERSAL STRATEGY:")
        print(f"   • Entry Condition: Liquidity sweep detection")
        print(f"   • Side: {side}")
        print(f"   • Symbol: {symbol}")
        print(f"   • Entry Price: ${entry_price}")
        if side == 'BUY':
            print(f"   • Logic: Low sweep detected - hunt for long stop losses, then reversal")
        else:
            print(f"   • Logic: High sweep detected - hunt for short stop losses, then reversal")
        print(f"   • Configuration: Dashboard smart money settings applied")
        
    else:
        print(f"❓ UNKNOWN STRATEGY TYPE:")
        print(f"   • Strategy: {strategy_name}")
        print(f"   • Side: {side}")
        print(f"   • Symbol: {symbol}")
        print(f"   • Entry Price: ${entry_price}")
        print(f"   • Manual analysis required for this strategy type")

if __name__ == "__main__":
    check_current_positions()
