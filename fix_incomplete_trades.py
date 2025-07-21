
#!/usr/bin/env python3
"""
Fix Incomplete Trade Data
Repair existing trades that are missing margin_used, leverage, or position_value_usdt
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.binance_client.client import BinanceClientWrapper
from datetime import datetime

def fix_incomplete_trades():
    """Fix existing trades with incomplete data"""
    print("🔧 FIXING INCOMPLETE TRADE DATA")
    print("=" * 50)

    trade_db = TradeDatabase()
    binance_client = BinanceClientWrapper()
    
    print(f"📊 Found {len(trade_db.trades)} trades in database")
    
    fixed_count = 0
    
    for trade_id, trade_data in trade_db.trades.items():
        needs_fix = False
        updates = {}
        
        # Check for missing fields
        missing_fields = []
        if 'margin_used' not in trade_data or trade_data['margin_used'] is None:
            missing_fields.append('margin_used')
        if 'leverage' not in trade_data or trade_data['leverage'] is None:
            missing_fields.append('leverage')
        if 'position_value_usdt' not in trade_data or trade_data['position_value_usdt'] is None:
            missing_fields.append('position_value_usdt')
        
        if missing_fields:
            print(f"\n🔧 Fixing {trade_id}")
            print(f"   Missing: {', '.join(missing_fields)}")
            needs_fix = True
            
            # Get basic trade data
            entry_price = float(trade_data.get('entry_price', 0))
            quantity = float(trade_data.get('quantity', 0))
            symbol = trade_data.get('symbol', '')
            
            # Calculate position value
            if 'position_value_usdt' not in trade_data or trade_data['position_value_usdt'] is None:
                position_value_usdt = entry_price * quantity
                updates['position_value_usdt'] = position_value_usdt
                print(f"   ✅ Position Value: ${position_value_usdt:.2f} USDT")
            else:
                position_value_usdt = trade_data['position_value_usdt']
            
            # Set leverage (try to get from Binance, default to 1x)
            if 'leverage' not in trade_data or trade_data['leverage'] is None:
                leverage = 1  # Default
                
                # Try to get actual leverage from Binance for futures
                try:
                    if binance_client.is_futures:
                        account_info = binance_client.client.futures_account()
                        positions = account_info.get('positions', [])
                        for pos in positions:
                            if pos.get('symbol') == symbol:
                                leverage = int(pos.get('leverage', 1))
                                break
                except:
                    pass
                
                updates['leverage'] = leverage
                print(f"   ✅ Leverage: {leverage}x")
            else:
                leverage = trade_data['leverage']
            
            # Calculate margin used
            if 'margin_used' not in trade_data or trade_data['margin_used'] is None:
                margin_used = position_value_usdt / leverage
                updates['margin_used'] = margin_used
                print(f"   ✅ Margin Used: ${margin_used:.2f} USDT")
        
        if needs_fix:
            # Update the trade
            trade_db.trades[trade_id].update(updates)
            fixed_count += 1
    
    if fixed_count > 0:
        # Save updated database
        trade_db._save_database()
        print(f"\n✅ FIXED {fixed_count} INCOMPLETE TRADES")
    else:
        print(f"\n✅ ALL TRADES ALREADY HAVE COMPLETE DATA")
    
    # Show summary of database state
    print(f"\n📊 DATABASE SUMMARY:")
    print(f"   Total trades: {len(trade_db.trades)}")
    
    open_trades = [t for t in trade_db.trades.values() if t.get('trade_status') == 'OPEN']
    closed_trades = [t for t in trade_db.trades.values() if t.get('trade_status') == 'CLOSED']
    
    print(f"   Open trades: {len(open_trades)}")
    print(f"   Closed trades: {len(closed_trades)}")
    
    # Check completeness
    complete_trades = 0
    for trade_data in trade_db.trades.values():
        if all(field in trade_data and trade_data[field] is not None 
               for field in ['margin_used', 'leverage', 'position_value_usdt']):
            complete_trades += 1
    
    print(f"   Complete trades: {complete_trades}/{len(trade_db.trades)}")
    
    if complete_trades < len(trade_db.trades):
        print(f"   ⚠️ {len(trade_db.trades) - complete_trades} trades still missing data")
    else:
        print(f"   ✅ All trades have complete data")

if __name__ == "__main__":
    fix_incomplete_trades()
