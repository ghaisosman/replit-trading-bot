
#!/usr/bin/env python3
"""
Fix Database Issues
Fix margin recording and P&L calculation issues in existing trades
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.binance_client.client import BinanceClientWrapper
from datetime import datetime

def fix_database_issues():
    print("🔧 FIXING DATABASE ISSUES")
    print("=" * 60)
    
    # Initialize components
    trade_db = TradeDatabase()
    binance_client = BinanceClientWrapper()
    
    print(f"📊 Found {len(trade_db.trades)} trades in database")
    
    fixed_margin_count = 0
    fixed_pnl_count = 0
    
    # Fix existing trades
    for trade_id, trade_data in trade_db.trades.items():
        needs_update = False
        updates = {}
        
        # Fix 1: Missing margin_used
        if 'margin_used' not in trade_data or trade_data['margin_used'] is None:
            entry_price = float(trade_data.get('entry_price', 0))
            quantity = float(trade_data.get('quantity', 0))
            leverage = trade_data.get('leverage', 1)
            
            if entry_price > 0 and quantity > 0:
                position_value = entry_price * quantity
                margin_used = position_value / leverage
                updates['margin_used'] = margin_used
                needs_update = True
                fixed_margin_count += 1
                print(f"   🔧 Fixed margin for {trade_id}: ${margin_used:.2f} USDT")
        
        # Fix 2: Missing P&L for closed trades
        if (trade_data.get('trade_status') == 'CLOSED' and 
            ('pnl_usdt' not in trade_data or trade_data['pnl_usdt'] is None)):
            
            entry_price = float(trade_data.get('entry_price', 0))
            exit_price = float(trade_data.get('exit_price', entry_price))
            quantity = float(trade_data.get('quantity', 0))
            side = trade_data.get('side', 'BUY')
            
            if entry_price > 0 and quantity > 0:
                # Calculate P&L
                if side == 'BUY':
                    pnl_usdt = (exit_price - entry_price) * quantity
                else:
                    pnl_usdt = (entry_price - exit_price) * quantity
                
                # Calculate P&L percentage against margin
                margin_used = trade_data.get('margin_used', 0)
                if margin_used > 0:
                    pnl_percentage = (pnl_usdt / margin_used) * 100
                else:
                    pnl_percentage = 0
                
                updates['pnl_usdt'] = pnl_usdt
                updates['pnl_percentage'] = pnl_percentage
                needs_update = True
                fixed_pnl_count += 1
                print(f"   💰 Fixed P&L for {trade_id}: ${pnl_usdt:.2f} USDT ({pnl_percentage:+.2f}%)")
        
        # Apply updates
        if needs_update:
            updates['last_updated'] = datetime.now().isoformat()
            updates['data_fix_applied'] = True
            trade_db.trades[trade_id].update(updates)
    
    # Save changes
    if fixed_margin_count > 0 or fixed_pnl_count > 0:
        trade_db._save_database()
        print(f"\n✅ DATABASE FIXES APPLIED:")
        print(f"   🔧 Fixed margin data: {fixed_margin_count} trades")
        print(f"   💰 Fixed P&L data: {fixed_pnl_count} trades")
    else:
        print(f"\n✅ No fixes needed - database is already correct")
    
    # Verify current ETH trade if exists
    print(f"\n🔍 CHECKING CURRENT ETH TRADE:")
    eth_trade = None
    for trade_id, trade_data in trade_db.trades.items():
        if (trade_data.get('trade_status') == 'OPEN' and 
            'ETH' in trade_data.get('symbol', '')):
            eth_trade = trade_data
            break
    
    if eth_trade:
        print(f"   📊 Current ETH Trade Found:")
        print(f"   💰 Margin Used: ${eth_trade.get('margin_used', 'MISSING')}")
        print(f"   📈 Position Value: ${eth_trade.get('position_value_usdt', 'MISSING')}")
        print(f"   ⚡ Leverage: {eth_trade.get('leverage', 'MISSING')}x")
        
        # Verify calculation
        if all(k in eth_trade for k in ['margin_used', 'position_value_usdt', 'leverage']):
            expected_margin = eth_trade['position_value_usdt'] / eth_trade['leverage']
            actual_margin = eth_trade['margin_used']
            if abs(expected_margin - actual_margin) < 0.01:
                print(f"   ✅ Margin calculation is correct")
            else:
                print(f"   ❌ Margin calculation mismatch: Expected ${expected_margin:.2f}, Got ${actual_margin:.2f}")
    else:
        print(f"   ❌ No open ETH trade found")

if __name__ == "__main__":
    fix_database_issues()
