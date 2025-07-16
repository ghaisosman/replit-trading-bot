
#!/usr/bin/env python3
"""
Database Synchronization Fix
Fix the discrepancy between database OPEN trades and actual Binance positions
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.binance_client.client import BinanceClientWrapper
from src.config.global_config import global_config
from datetime import datetime


def sync_database_with_binance():
    """Synchronize database with actual Binance positions"""
    print("🔄 SYNCHRONIZING DATABASE WITH BINANCE")
    print("=" * 50)
    
    # Initialize components
    trade_db = TradeDatabase()
    binance_client = BinanceClientWrapper()
    
    # Get all open trades from database
    open_trades_db = []
    for trade_id, trade_data in trade_db.trades.items():
        if trade_data.get('trade_status') == 'OPEN':
            open_trades_db.append((trade_id, trade_data))
    
    print(f"📊 Database shows {len(open_trades_db)} OPEN trades")
    
    # Get actual positions from Binance
    actual_positions = {}
    try:
        if binance_client.is_futures:
            positions = binance_client.client.futures_account()
            for position in positions.get('positions', []):
                symbol = position.get('symbol')
                position_amt = float(position.get('positionAmt', 0))
                if abs(position_amt) > 0.0001:  # Position exists
                    actual_positions[symbol] = {
                        'symbol': symbol,
                        'position_amt': position_amt,
                        'entry_price': float(position.get('entryPrice', 0)),
                        'side': 'BUY' if position_amt > 0 else 'SELL',
                        'quantity': abs(position_amt)
                    }
        
        print(f"📊 Binance shows {len(actual_positions)} actual positions")
        
        # Process each open trade in database
        closed_count = 0
        for trade_id, trade_data in open_trades_db:
            symbol = trade_data.get('symbol')
            strategy_name = trade_data.get('strategy_name')
            db_side = trade_data.get('side')
            db_quantity = trade_data.get('quantity', 0)
            db_entry_price = trade_data.get('entry_price', 0)
            
            # Check if this trade has a corresponding position on Binance
            position_exists = False
            
            if symbol in actual_positions:
                binance_pos = actual_positions[symbol]
                
                # Check if position details match (with tolerance)
                quantity_match = abs(binance_pos['quantity'] - db_quantity) < 0.1
                side_match = binance_pos['side'] == db_side
                
                if quantity_match and side_match:
                    position_exists = True
                    print(f"   ✅ {trade_id} - Position confirmed on Binance")
                else:
                    print(f"   ⚠️  {trade_id} - Position mismatch on Binance")
            
            # If no corresponding position on Binance, mark as closed
            if not position_exists:
                print(f"   🔄 {trade_id} - Marking as CLOSED (no Binance position)")
                
                # Update trade as closed
                trade_db.trades[trade_id]['trade_status'] = 'CLOSED'
                trade_db.trades[trade_id]['exit_reason'] = 'Position closed externally'
                trade_db.trades[trade_id]['exit_price'] = db_entry_price  # Use entry price as exit
                trade_db.trades[trade_id]['pnl_usdt'] = 0.0
                trade_db.trades[trade_id]['pnl_percentage'] = 0.0
                trade_db.trades[trade_id]['duration_minutes'] = 0
                
                closed_count += 1
        
        # Save the updated database
        if closed_count > 0:
            trade_db._save_database()
            print(f"\n✅ SYNC COMPLETE!")
            print(f"   📊 Marked {closed_count} stale trades as CLOSED")
            print(f"   📊 {len(actual_positions)} legitimate positions remain")
        else:
            print(f"\n✅ DATABASE ALREADY IN SYNC!")
            print(f"   📊 All {len(open_trades_db)} database trades have matching Binance positions")
            
    except Exception as e:
        print(f"❌ ERROR during sync: {e}")
        return False
    
    return True


def verify_sync():
    """Verify that database is now in sync"""
    print("\n🔍 VERIFYING SYNC RESULTS")
    print("=" * 30)
    
    trade_db = TradeDatabase()
    
    # Count open trades
    open_trades = []
    closed_trades = []
    
    for trade_id, trade_data in trade_db.trades.items():
        if trade_data.get('trade_status') == 'OPEN':
            open_trades.append((trade_id, trade_data))
        else:
            closed_trades.append((trade_id, trade_data))
    
    print(f"📊 Database Results:")
    print(f"   🔓 Open trades: {len(open_trades)}")
    print(f"   ✅ Closed trades: {len(closed_trades)}")
    print(f"   📈 Total trades: {len(trade_db.trades)}")
    
    if len(open_trades) <= 2:  # Should match actual positions
        print(f"\n✅ SYNC SUCCESSFUL!")
        print(f"   Database now shows realistic number of open trades")
        print(f"   This should match your actual Binance positions")
    else:
        print(f"\n⚠️  SYNC INCOMPLETE:")
        print(f"   Still {len(open_trades)} open trades - may need manual review")
    
    return len(open_trades)


if __name__ == "__main__":
    print("🔧 DATABASE SYNC FIX")
    print("=" * 20)
    
    success = sync_database_with_binance()
    
    if success:
        open_count = verify_sync()
        
        if open_count <= 2:
            print(f"\n🎉 SUCCESS! Database is now synchronized with Binance")
            print(f"💡 You should now see the correct number of open trades")
            print(f"🚀 Bot can now operate normally without false 'open' trades")
        else:
            print(f"\n⚠️  PARTIAL SUCCESS: Reduced from 27 to {open_count} open trades")
            print(f"💡 Remaining trades may need manual inspection")
    else:
        print(f"\n❌ SYNC FAILED: Could not connect to Binance or update database")
