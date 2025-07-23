
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.binance_client.client import BinanceClientWrapper
from datetime import datetime

def test_simplified_recovery():
    print("🧪 TESTING SIMPLIFIED RECOVERY SYSTEM")
    print("=" * 60)
    
    try:
        # Initialize components
        trade_db = TradeDatabase()
        binance_client = BinanceClientWrapper()
        
        print(f"📊 Database contains {len(trade_db.trades)} total trades")
        
        # Step 1: Find open trades in database
        open_trades = {}
        for trade_id, trade_data in trade_db.trades.items():
            if trade_data.get('trade_status') == 'OPEN':
                open_trades[trade_id] = trade_data
                print(f"🔍 DEBUG: Open trade in DB: {trade_id}")
                print(f"   Symbol: {trade_data.get('symbol')}")
                print(f"   Side: {trade_data.get('side')}")
                print(f"   Quantity: {trade_data.get('quantity')}")
                print(f"   Entry Price: ${trade_data.get('entry_price')}")
                print(f"   Strategy: {trade_data.get('strategy_name')}")
        
        print(f"\n📈 Found {len(open_trades)} open trades in database")
        
        # Step 2: Get Binance positions
        binance_positions = {}
        if binance_client.is_futures:
            try:
                positions = binance_client.client.futures_position_information()
                for position in positions:
                    symbol = position.get('symbol')
                    position_amt = float(position.get('positionAmt', 0))
                    if abs(position_amt) > 0.001:
                        entry_price = float(position.get('entryPrice', 0))
                        side = 'BUY' if position_amt > 0 else 'SELL'
                        quantity = abs(position_amt)
                        
                        binance_positions[symbol] = {
                            'symbol': symbol,
                            'side': side,
                            'quantity': quantity,
                            'entry_price': entry_price,
                            'position_amt': position_amt
                        }
                        print(f"🔍 DEBUG: Binance position: {symbol}")
                        print(f"   Side: {side}")
                        print(f"   Quantity: {quantity}")
                        print(f"   Entry Price: ${entry_price}")
                        print(f"   Position Amount: {position_amt}")
            except Exception as e:
                print(f"❌ Error fetching Binance positions: {e}")
        
        print(f"\n💹 Found {len(binance_positions)} active positions on Binance")
        
        # Step 3: Match trades with positions
        matches = []
        for trade_id, trade_data in open_trades.items():
            symbol = trade_data.get('symbol')
            db_side = trade_data.get('side')
            db_quantity = float(trade_data.get('quantity', 0))
            db_entry_price = float(trade_data.get('entry_price', 0))
            
            print(f"\n🔍 DEBUG: Matching {trade_id} ({symbol} {db_side})")
            
            binance_pos = binance_positions.get(symbol)
            if binance_pos:
                side_match = binance_pos['side'] == db_side
                qty_tolerance = max(db_quantity * 0.05, 0.001)
                price_tolerance = max(db_entry_price * 0.05, 0.01)
                
                qty_diff = abs(binance_pos['quantity'] - db_quantity)
                price_diff = abs(binance_pos['entry_price'] - db_entry_price)
                
                qty_match = qty_diff <= qty_tolerance
                price_match = price_diff <= price_tolerance
                
                print(f"   Side Match: {side_match}")
                print(f"   Qty Match: {qty_match} (diff: {qty_diff:.6f}, tolerance: {qty_tolerance:.6f})")
                print(f"   Price Match: {price_match} (diff: ${price_diff:.4f}, tolerance: ${price_tolerance:.4f})")
                
                if side_match and qty_match and price_match:
                    matches.append((trade_id, trade_data))
                    print(f"   ✅ PERFECT MATCH: {trade_id} can be recovered")
                else:
                    print(f"   ❌ NO MATCH: {trade_id} doesn't match Binance position")
            else:
                print(f"   ⚠️ NO BINANCE POSITION: {trade_id} has no corresponding Binance position")
        
        print(f"\n🎯 RECOVERY SUMMARY:")
        print(f"   Database Open Trades: {len(open_trades)}")
        print(f"   Binance Positions: {len(binance_positions)}")
        print(f"   Perfect Matches: {len(matches)}")
        
        if matches:
            print(f"\n✅ RECOVERABLE POSITIONS:")
            for trade_id, trade_data in matches:
                print(f"   {trade_id} | {trade_data.get('strategy_name')} | {trade_data.get('symbol')} | {trade_data.get('side')}")
        else:
            print(f"\n⚠️ NO POSITIONS TO RECOVER")
        
        return len(matches)
        
    except Exception as e:
        print(f"❌ Recovery test error: {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        return 0

if __name__ == "__main__":
    test_simplified_recovery()
