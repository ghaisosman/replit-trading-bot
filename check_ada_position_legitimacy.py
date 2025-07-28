
#!/usr/bin/env python3
"""
Check ADA Position Legitimacy
Verify if the open ADA position in database matches actual Binance position
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.binance_client.client import BinanceClientWrapper
from datetime import datetime
import json

def check_ada_position_legitimacy():
    """Check if ADA position in database is legitimate"""
    print("🔍 ADA POSITION LEGITIMACY CHECK")
    print("=" * 50)
    
    # Initialize components
    trade_db = TradeDatabase()
    binance_client = BinanceClientWrapper()
    
    print(f"📊 Total trades in database: {len(trade_db.trades)}")
    
    # Find open trades
    open_trades = []
    ada_trades = []
    
    for trade_id, trade_data in trade_db.trades.items():
        if trade_data.get('trade_status') == 'OPEN':
            open_trades.append((trade_id, trade_data))
            
            # Check for ADA specifically
            symbol = trade_data.get('symbol', '')
            if 'ADA' in symbol.upper():
                ada_trades.append((trade_id, trade_data))
    
    print(f"🔓 Total open trades: {len(open_trades)}")
    print(f"💰 ADA trades: {len(ada_trades)}")
    
    # Display all open trades
    if open_trades:
        print(f"\n📋 ALL OPEN TRADES:")
        print("-" * 40)
        for i, (trade_id, trade_data) in enumerate(open_trades, 1):
            symbol = trade_data.get('symbol', 'Unknown')
            strategy = trade_data.get('strategy_name', 'Unknown')
            side = trade_data.get('side', 'Unknown')
            quantity = trade_data.get('quantity', 0)
            entry_price = trade_data.get('entry_price', 0)
            timestamp = trade_data.get('created_at', 'Unknown')
            
            print(f"   #{i}: {trade_id}")
            print(f"      Symbol: {symbol}")
            print(f"      Strategy: {strategy}")
            print(f"      Side: {side}")
            print(f"      Quantity: {quantity}")
            print(f"      Entry Price: ${entry_price}")
            print(f"      Created: {timestamp}")
            print()
    
    # Get actual Binance positions
    print(f"🌐 CHECKING BINANCE POSITIONS:")
    print("-" * 40)
    
    binance_positions = {}
    try:
        if binance_client.is_futures:
            account_info = binance_client.client.futures_account()
            all_positions = account_info.get('positions', [])
            
            print(f"📊 Retrieved {len(all_positions)} total positions from Binance")
            
            # Filter active positions
            active_count = 0
            for position in all_positions:
                symbol = position.get('symbol')
                position_amt = float(position.get('positionAmt', 0))
                
                if abs(position_amt) > 0.001:  # Has actual position
                    active_count += 1
                    entry_price = float(position.get('entryPrice', 0))
                    unrealized_pnl = float(position.get('unRealizedProfit', 0))
                    side = 'LONG' if position_amt > 0 else 'SHORT'
                    
                    binance_positions[symbol] = {
                        'symbol': symbol,
                        'position_amt': position_amt,
                        'quantity': abs(position_amt),
                        'entry_price': entry_price,
                        'unrealized_pnl': unrealized_pnl,
                        'side': side
                    }
                    
                    print(f"   ✅ {symbol}: {side} | Qty: {abs(position_amt)} | Entry: ${entry_price} | PnL: ${unrealized_pnl:.2f}")
            
            print(f"📊 Found {active_count} active positions on Binance")
            
    except Exception as e:
        print(f"❌ Error fetching Binance positions: {e}")
        binance_positions = {}
    
    # Match database trades with Binance positions
    print(f"\n🔍 LEGITIMACY ANALYSIS:")
    print("-" * 40)
    
    legitimate_trades = []
    orphan_trades = []
    
    for trade_id, trade_data in open_trades:
        symbol = trade_data.get('symbol')
        db_side = trade_data.get('side')
        db_quantity = float(trade_data.get('quantity', 0))
        db_entry_price = float(trade_data.get('entry_price', 0))
        
        print(f"\n📊 ANALYZING: {trade_id}")
        print(f"   Database: {symbol} {db_side} Qty:{db_quantity} Entry:${db_entry_price}")
        
        # Check if position exists on Binance
        if symbol in binance_positions:
            binance_pos = binance_positions[symbol]
            
            # Check matches
            quantity_diff = abs(binance_pos['quantity'] - db_quantity)
            price_diff = abs(binance_pos['entry_price'] - db_entry_price)
            side_match = (
                (db_side == 'BUY' and binance_pos['side'] == 'LONG') or
                (db_side == 'SELL' and binance_pos['side'] == 'SHORT')
            )
            
            print(f"   Binance: {symbol} {binance_pos['side']} Qty:{binance_pos['quantity']} Entry:${binance_pos['entry_price']}")
            print(f"   Quantity diff: {quantity_diff}")
            print(f"   Price diff: ${price_diff}")
            print(f"   Side match: {side_match}")
            
            # Determine legitimacy (allow some tolerance)
            is_legitimate = (
                quantity_diff < 0.1 and  # Small quantity tolerance
                price_diff < (db_entry_price * 0.05) and  # 5% price tolerance
                side_match
            )
            
            if is_legitimate:
                print(f"   ✅ LEGITIMATE: Position confirmed on Binance")
                legitimate_trades.append(trade_id)
            else:
                print(f"   ⚠️  MISMATCH: Position exists but details don't match")
                orphan_trades.append(trade_id)
        else:
            print(f"   ❌ ORPHAN: No corresponding position on Binance")
            orphan_trades.append(trade_id)
    
    # Specific ADA analysis
    print(f"\n💰 ADA SPECIFIC ANALYSIS:")
    print("-" * 40)
    
    ada_legitimate = False
    if ada_trades:
        for trade_id, trade_data in ada_trades:
            symbol = trade_data.get('symbol')
            if trade_id in legitimate_trades:
                print(f"✅ ADA POSITION IS LEGITIMATE")
                print(f"   Trade ID: {trade_id}")
                print(f"   Symbol: {symbol}")
                print(f"   Database and Binance positions match")
                ada_legitimate = True
            else:
                print(f"❌ ADA POSITION IS ORPHAN")
                print(f"   Trade ID: {trade_id}")
                print(f"   Symbol: {symbol}")
                print(f"   No matching position on Binance")
    else:
        # Check if ADA position exists on Binance but not in database
        ada_on_binance = [pos for symbol, pos in binance_positions.items() if 'ADA' in symbol]
        if ada_on_binance:
            print(f"⚠️  ADA POSITION ON BINANCE BUT NOT IN DATABASE")
            for pos in ada_on_binance:
                print(f"   Binance: {pos['symbol']} {pos['side']} Qty:{pos['quantity']}")
        else:
            print(f"ℹ️  NO ADA POSITIONS FOUND")
            print(f"   Neither in database nor on Binance")
    
    # Summary
    print(f"\n📋 SUMMARY:")
    print("-" * 20)
    print(f"Total open trades in database: {len(open_trades)}")
    print(f"Legitimate trades: {len(legitimate_trades)}")
    print(f"Orphan trades: {len(orphan_trades)}")
    print(f"Active Binance positions: {len(binance_positions)}")
    
    if ada_legitimate:
        print(f"💰 ADA Status: LEGITIMATE ✅")
    elif ada_trades:
        print(f"💰 ADA Status: ORPHAN ❌")
    else:
        print(f"💰 ADA Status: NOT FOUND")
    
    # Recommendations
    print(f"\n💡 RECOMMENDATIONS:")
    print("-" * 25)
    
    if orphan_trades:
        print(f"🧹 Clear {len(orphan_trades)} orphan trade(s) from database")
        print(f"   These exist in database but not on Binance")
    
    if len(binance_positions) > len(legitimate_trades):
        unmatched_binance = len(binance_positions) - len(legitimate_trades)
        print(f"📝 Create {unmatched_binance} missing database record(s)")
        print(f"   These exist on Binance but not in database")
    
    if len(legitimate_trades) == len(open_trades) and len(open_trades) == len(binance_positions):
        print(f"✅ Database and Binance are perfectly synchronized")
    
    return {
        'ada_legitimate': ada_legitimate,
        'total_open_db': len(open_trades),
        'legitimate_trades': len(legitimate_trades),
        'orphan_trades': len(orphan_trades),
        'binance_positions': len(binance_positions)
    }

if __name__ == "__main__":
    result = check_ada_position_legitimacy()
    
    print(f"\n" + "=" * 50)
    if result['ada_legitimate']:
        print(f"🎯 RESULT: ADA position in database is LEGITIMATE")
    else:
        print(f"🎯 RESULT: No legitimate ADA position found")
