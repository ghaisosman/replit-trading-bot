
#!/usr/bin/env python3
"""
Database Synchronization Investigation
Identify root cause of discrepancy between database and active positions
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.execution_engine.order_manager import OrderManager
from src.binance_client.client import BinanceClientWrapper
from src.config.global_config import global_config
from datetime import datetime
import json

def investigate_database_sync():
    """Comprehensive investigation of database sync issues"""
    print("🔍 DATABASE SYNCHRONIZATION INVESTIGATION")
    print("=" * 60)
    
    # 1. Load Trade Database
    print("\n📊 STEP 1: ANALYZING TRADE DATABASE")
    print("-" * 40)
    
    trade_db = TradeDatabase()
    
    if not trade_db.trades:
        print("❌ Trade database is empty")
        return
    
    # Analyze database trades by status
    open_trades_db = []
    closed_trades_db = []
    
    for trade_id, trade_data in trade_db.trades.items():
        status = trade_data.get('trade_status', 'UNKNOWN')
        if status == 'OPEN':
            open_trades_db.append((trade_id, trade_data))
        elif status == 'CLOSED':
            closed_trades_db.append((trade_id, trade_data))
    
    print(f"📈 Total trades in database: {len(trade_db.trades)}")
    print(f"🔓 Open trades in database: {len(open_trades_db)}")
    print(f"✅ Closed trades in database: {len(closed_trades_db)}")
    
    # Show open trades details
    if open_trades_db:
        print(f"\n🔍 OPEN TRADES IN DATABASE:")
        for i, (trade_id, trade_data) in enumerate(open_trades_db, 1):
            symbol = trade_data.get('symbol', 'N/A')
            strategy = trade_data.get('strategy_name', 'N/A')
            side = trade_data.get('side', 'N/A')
            entry_price = trade_data.get('entry_price', 0)
            quantity = trade_data.get('quantity', 0)
            timestamp = trade_data.get('timestamp', 'N/A')
            
            print(f"   {i}. Trade ID: {trade_id}")
            print(f"      Strategy: {strategy}")
            print(f"      Symbol: {symbol}")
            print(f"      Side: {side}")
            print(f"      Entry Price: ${entry_price}")
            print(f"      Quantity: {quantity}")
            print(f"      Timestamp: {timestamp}")
            
            # Check if this is one of the ETH trades
            if 'ETH' in symbol.upper():
                print(f"      🔸 ETH TRADE DETECTED")
            print()
    
    # 2. Check if bot manager exists and get active positions
    print("📊 STEP 2: ANALYZING ACTIVE POSITIONS FROM BOT")
    print("-" * 40)
    
    try:
        # Try to get shared bot manager from main.py
        main_module = sys.modules.get('__main__')
        bot_manager = getattr(main_module, 'bot_manager', None) if main_module else None
        
        if not bot_manager:
            print("❌ No bot manager found - bot may not be running")
            active_positions = {}
        else:
            print("✅ Bot manager found")
            
            if hasattr(bot_manager, 'order_manager') and bot_manager.order_manager:
                active_positions = bot_manager.order_manager.active_positions
                print(f"📈 Active positions in bot: {len(active_positions)}")
                
                for strategy_name, position in active_positions.items():
                    print(f"   🔸 {strategy_name}: {position.symbol} | {position.side} | Entry: ${position.entry_price} | Qty: {position.quantity}")
            else:
                print("❌ Bot manager has no order manager")
                active_positions = {}
    
    except Exception as e:
        print(f"❌ Error accessing bot manager: {e}")
        active_positions = {}
    
    # 3. Check Binance actual positions
    print("\n📊 STEP 3: CHECKING ACTUAL BINANCE POSITIONS")
    print("-" * 40)
    
    try:
        binance_client = BinanceClientWrapper()
        
        if binance_client.is_futures:
            account_info = binance_client.client.futures_account()
            all_positions = account_info.get('positions', [])
            
            # Filter for positions with non-zero amounts
            actual_positions = []
            for pos in all_positions:
                position_amt = float(pos.get('positionAmt', 0))
                if abs(position_amt) > 0.00001:
                    actual_positions.append({
                        'symbol': pos.get('symbol'),
                        'positionAmt': position_amt,
                        'entryPrice': float(pos.get('entryPrice', 0)),
                        'markPrice': float(pos.get('markPrice', 0)),
                        'unRealizedProfit': float(pos.get('unRealizedProfit', 0))
                    })
            
            print(f"📈 Actual positions on Binance: {len(actual_positions)}")
            
            for pos in actual_positions:
                side = 'LONG' if pos['positionAmt'] > 0 else 'SHORT'
                print(f"   🔸 {pos['symbol']}: {side} | Entry: ${pos['entryPrice']} | Qty: {abs(pos['positionAmt'])} | PnL: ${pos['unRealizedProfit']}")
        
        else:
            print("❌ Not using futures - cannot check positions")
            actual_positions = []
    
    except Exception as e:
        print(f"❌ Error checking Binance positions: {e}")
        actual_positions = []
    
    # 4. Cross-reference analysis
    print("\n🔍 STEP 4: CROSS-REFERENCE ANALYSIS")
    print("-" * 40)
    
    # Count by symbol
    db_symbols = {}
    bot_symbols = {}
    binance_symbols = {}
    
    # Database symbol count
    for trade_id, trade_data in open_trades_db:
        symbol = trade_data.get('symbol', 'UNKNOWN')
        db_symbols[symbol] = db_symbols.get(symbol, 0) + 1
    
    # Bot active positions symbol count
    for strategy_name, position in active_positions.items():
        symbol = position.symbol
        bot_symbols[symbol] = bot_symbols.get(symbol, 0) + 1
    
    # Binance actual positions symbol count
    for pos in actual_positions:
        symbol = pos['symbol']
        binance_symbols[symbol] = binance_symbols.get(symbol, 0) + 1
    
    print("📊 SYMBOL COUNT COMPARISON:")
    all_symbols = set(list(db_symbols.keys()) + list(bot_symbols.keys()) + list(binance_symbols.keys()))
    
    for symbol in sorted(all_symbols):
        db_count = db_symbols.get(symbol, 0)
        bot_count = bot_symbols.get(symbol, 0)
        binance_count = binance_symbols.get(symbol, 0)
        
        print(f"   {symbol}:")
        print(f"      Database: {db_count} open trades")
        print(f"      Bot Memory: {bot_count} active positions")
        print(f"      Binance: {binance_count} actual positions")
        
        # Identify discrepancies
        if db_count != bot_count or bot_count != binance_count or db_count != binance_count:
            print(f"      🚨 DISCREPANCY DETECTED!")
            
            if db_count > bot_count:
                print(f"         ⚠️ Database has {db_count - bot_count} more {symbol} trades than bot memory")
            elif bot_count > db_count:
                print(f"         ⚠️ Bot memory has {bot_count - db_count} more {symbol} positions than database")
            
            if bot_count > binance_count:
                print(f"         ⚠️ Bot thinks it has {bot_count - binance_count} more {symbol} positions than actually exist on Binance")
            elif binance_count > bot_count:
                print(f"         ⚠️ Binance has {binance_count - bot_count} more {symbol} positions than bot knows about")
            
            if db_count > binance_count:
                print(f"         ⚠️ Database shows {db_count - binance_count} more {symbol} trades than actually exist on Binance")
        else:
            print(f"      ✅ All sources match")
        print()
    
    # 5. Detailed ETH analysis (since that's where the issue is)
    print("🔍 STEP 5: DETAILED ETH ANALYSIS")
    print("-" * 40)
    
    eth_trades_db = [(tid, td) for tid, td in open_trades_db if 'ETH' in td.get('symbol', '').upper()]
    eth_positions_bot = {sn: pos for sn, pos in active_positions.items() if 'ETH' in pos.symbol.upper()}
    eth_positions_binance = [pos for pos in actual_positions if 'ETH' in pos['symbol'].upper()]
    
    print(f"📊 ETH BREAKDOWN:")
    print(f"   Database: {len(eth_trades_db)} open ETH trades")
    print(f"   Bot Memory: {len(eth_positions_bot)} active ETH positions")
    print(f"   Binance: {len(eth_positions_binance)} actual ETH positions")
    
    if len(eth_trades_db) > 1:
        print(f"\n🚨 ROOT CAUSE IDENTIFIED: Database has {len(eth_trades_db)} ETH trades marked as OPEN")
        print("   This suggests either:")
        print("   1. Multiple ETH trades were opened but some closed positions weren't updated in database")
        print("   2. Database cleanup/sync is not working properly")
        print("   3. Trade status updates are failing")
        
        print(f"\n🔍 DETAILED ETH TRADES IN DATABASE:")
        for i, (trade_id, trade_data) in enumerate(eth_trades_db, 1):
            print(f"   ETH Trade #{i}: {trade_id}")
            print(f"      Strategy: {trade_data.get('strategy_name')}")
            print(f"      Entry Price: ${trade_data.get('entry_price')}")
            print(f"      Quantity: {trade_data.get('quantity')}")
            print(f"      Timestamp: {trade_data.get('timestamp')}")
            
            # Check if this trade matches any actual Binance position
            matches_binance = False
            for pos in eth_positions_binance:
                if abs(float(trade_data.get('entry_price', 0)) - pos['entryPrice']) < 1.0:  # Within $1
                    matches_binance = True
                    print(f"      ✅ MATCHES Binance position")
                    break
            
            if not matches_binance:
                print(f"      ❌ NO MATCHING Binance position - likely stale trade")
            print()
    
    # 6. Investigate trade closing mechanism
    print("🔍 STEP 6: INVESTIGATING TRADE CLOSING MECHANISM")
    print("-" * 40)
    
    # Check if there are any recently closed trades that might reveal the pattern
    recent_closed = []
    now = datetime.now()
    
    for trade_id, trade_data in closed_trades_db:
        timestamp_str = trade_data.get('timestamp', '')
        if timestamp_str:
            try:
                trade_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                hours_ago = (now - trade_time).total_seconds() / 3600
                if hours_ago <= 24:  # Last 24 hours
                    recent_closed.append((trade_id, trade_data, hours_ago))
            except:
                pass
    
    print(f"📊 Recently closed trades (last 24h): {len(recent_closed)}")
    
    if recent_closed:
        print("🔍 Recent closed trades:")
        for trade_id, trade_data, hours_ago in recent_closed[-5:]:  # Last 5
            symbol = trade_data.get('symbol', 'N/A')
            exit_reason = trade_data.get('exit_reason', 'N/A')
            print(f"   {trade_id}: {symbol} | Closed {hours_ago:.1f}h ago | Reason: {exit_reason}")
    
    # 7. Final diagnosis
    print("\n🎯 STEP 7: ROOT CAUSE DIAGNOSIS")
    print("-" * 40)
    
    if len(open_trades_db) > len(actual_positions):
        print("🚨 PRIMARY ISSUE: Database contains stale open trades")
        print("   The database has more open trades than actual positions on Binance")
        print("   This indicates that when positions were closed (manually or automatically),")
        print("   the database was not updated to reflect the closure.")
        print()
        print("🔍 LIKELY CAUSES:")
        print("   1. Trade closing process is not updating database status")
        print("   2. Manual position closures on Binance are not detected")
        print("   3. Database sync mechanism is not working")
        print("   4. Exception handling during trade closure is silently failing")
        
        if len(eth_trades_db) == 2 and len(eth_positions_binance) == 1:
            print(f"\n🎯 SPECIFIC ETH ISSUE:")
            print(f"   Database shows 2 open ETH trades but only 1 exists on Binance")
            print(f"   This means 1 ETH trade was closed but database wasn't updated")
    
    elif len(active_positions) > len(actual_positions):
        print("🚨 PRIMARY ISSUE: Bot memory is out of sync with Binance")
        print("   The bot thinks it has more positions than actually exist")
        print("   This suggests positions were closed externally (manually)")
    
    else:
        print("✅ No major sync issues detected")
    
    print(f"\n" + "=" * 60)
    print("🎯 INVESTIGATION COMPLETE")

if __name__ == "__main__":
    investigate_database_sync()
