
#!/usr/bin/env python3
"""
Missing Dashboard Position Investigation
=======================================
Investigate why a legitimate Binance position is not showing on the dashboard
"""

import sys
import os
import requests
import json
from datetime import datetime
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.binance_client.client import BinanceClientWrapper
from src.execution_engine.trade_database import TradeDatabase
from src.bot_manager import BotManager

def investigate_missing_dashboard_position():
    """Comprehensive investigation of missing dashboard position"""
    print("🔍 MISSING DASHBOARD POSITION INVESTIGATION")
    print("=" * 60)
    
    # Step 1: Check Binance positions directly
    print("\n📊 STEP 1: DIRECT BINANCE POSITION CHECK")
    print("-" * 40)
    
    try:
        binance_client = BinanceClientWrapper()
        
        if binance_client.is_futures:
            account_info = binance_client.client.futures_account()
            all_positions = account_info.get('positions', [])
            
            active_positions = []
            for position in all_positions:
                position_amt = float(position.get('positionAmt', 0))
                if abs(position_amt) > 0.000001:  # Has actual position
                    symbol = position.get('symbol')
                    entry_price = float(position.get('entryPrice', 0))
                    side = 'BUY' if position_amt > 0 else 'SELL'
                    quantity = abs(position_amt)
                    unrealized_pnl = float(position.get('unRealizedProfit', 0))
                    
                    active_positions.append({
                        'symbol': symbol,
                        'side': side,
                        'quantity': quantity,
                        'entry_price': entry_price,
                        'position_amt': position_amt,
                        'unrealized_pnl': unrealized_pnl,
                        'raw_data': position
                    })
                    
                    print(f"✅ FOUND ACTIVE POSITION:")
                    print(f"   Symbol: {symbol}")
                    print(f"   Side: {side}")
                    print(f"   Quantity: {quantity}")
                    print(f"   Entry Price: ${entry_price}")
                    print(f"   Position Amount: {position_amt}")
                    print(f"   Unrealized PnL: ${unrealized_pnl:.2f}")
            
            print(f"\n📊 Total active positions on Binance: {len(active_positions)}")
            
            if not active_positions:
                print("❌ NO ACTIVE POSITIONS FOUND ON BINANCE")
                print("   This contradicts your statement - please double-check Binance directly")
                return
                
        else:
            print("❌ Not using futures trading - spot positions not supported")
            return
    
    except Exception as e:
        print(f"❌ Error checking Binance positions: {e}")
        return
    
    # Step 2: Check database for matching trades
    print(f"\n📊 STEP 2: DATABASE TRADE MATCHING")
    print("-" * 40)
    
    try:
        trade_db = TradeDatabase()
        
        print(f"📊 Total trades in database: {len(trade_db.trades)}")
        
        # Check for open trades
        open_trades = []
        closed_trades = []
        
        for trade_id, trade_data in trade_db.trades.items():
            status = trade_data.get('trade_status', 'UNKNOWN')
            if status == 'OPEN':
                open_trades.append((trade_id, trade_data))
            else:
                closed_trades.append((trade_id, trade_data))
        
        print(f"📊 Open trades in database: {len(open_trades)}")
        print(f"📊 Closed trades in database: {len(closed_trades)}")
        
        # Check if any Binance positions match database trades
        for binance_pos in active_positions:
            symbol = binance_pos['symbol']
            side = binance_pos['side']
            quantity = binance_pos['quantity']
            entry_price = binance_pos['entry_price']
            
            print(f"\n🔍 SEARCHING FOR MATCH: {symbol} {side}")
            
            # Look for matching trades (open or closed)
            matches_found = []
            
            for trade_id, trade_data in trade_db.trades.items():
                db_symbol = trade_data.get('symbol')
                db_side = trade_data.get('side')
                db_quantity = float(trade_data.get('quantity', 0))
                db_entry_price = float(trade_data.get('entry_price', 0))
                db_status = trade_data.get('trade_status')
                
                # Check for match with tolerance
                symbol_match = db_symbol == symbol
                side_match = db_side == side
                quantity_match = abs(db_quantity - quantity) < 0.1
                price_match = abs(db_entry_price - entry_price) <= entry_price * 0.05
                
                if symbol_match and side_match and quantity_match and price_match:
                    matches_found.append({
                        'trade_id': trade_id,
                        'status': db_status,
                        'trade_data': trade_data
                    })
            
            if matches_found:
                print(f"✅ FOUND {len(matches_found)} MATCHING TRADES:")
                for match in matches_found:
                    print(f"   Trade ID: {match['trade_id']}")
                    print(f"   Status: {match['status']}")
                    print(f"   Strategy: {match['trade_data'].get('strategy_name')}")
                    
                    if match['status'] == 'CLOSED':
                        print(f"   🚨 ISSUE: Trade marked as CLOSED but position still exists on Binance!")
                        print(f"   🔧 SOLUTION: This trade should be marked as OPEN or recovered")
            else:
                print(f"❌ NO MATCHING TRADES FOUND IN DATABASE")
                print(f"   🚨 ISSUE: Position exists on Binance but no database record")
                print(f"   🔧 SOLUTION: Create recovery trade record or manual position tracking")
    
    except Exception as e:
        print(f"❌ Error checking database: {e}")
    
    # Step 3: Check bot manager active positions
    print(f"\n📊 STEP 3: BOT MANAGER ACTIVE POSITIONS")
    print("-" * 40)
    
    try:
        # Access the global bot manager if available
        bot_active_positions = {}
        
        # Try to get from web dashboard API
        try:
            response = requests.get('http://localhost:5000/api/positions', timeout=5)
            if response.status_code == 200:
                api_data = response.json()
                bot_active_positions = api_data.get('positions', {})
                print(f"📊 Active positions from API: {len(bot_active_positions)}")
                
                if bot_active_positions:
                    for strategy_name, position_data in bot_active_positions.items():
                        print(f"   Strategy: {strategy_name}")
                        print(f"   Symbol: {position_data.get('symbol')}")
                        print(f"   Side: {position_data.get('side')}")
                        print(f"   Entry: ${position_data.get('entry_price')}")
                else:
                    print("❌ No active positions in bot manager")
            else:
                print(f"❌ API request failed: {response.status_code}")
        
        except Exception as api_error:
            print(f"❌ Could not access dashboard API: {api_error}")
    
    except Exception as e:
        print(f"❌ Error checking bot manager: {e}")
    
    # Step 4: Check dashboard API directly
    print(f"\n📊 STEP 4: DASHBOARD API DIRECT CHECK")
    print("-" * 40)
    
    try:
        response = requests.get('http://localhost:5000/api/dashboard', timeout=10)
        if response.status_code == 200:
            dashboard_data = response.json()
            
            active_positions_dash = dashboard_data.get('active_positions', {})
            print(f"📊 Dashboard active positions: {len(active_positions_dash)}")
            
            if active_positions_dash:
                for strategy, pos_data in active_positions_dash.items():
                    print(f"   {strategy}: {pos_data.get('symbol')} | {pos_data.get('side')}")
            else:
                print("❌ Dashboard shows no active positions")
                
            # Check bot status
            bot_status = dashboard_data.get('bot_status', 'unknown')
            print(f"🤖 Bot status: {bot_status}")
            
            if bot_status != 'running':
                print("🚨 ISSUE: Bot is not running - positions won't be tracked!")
                print("🔧 SOLUTION: Start the bot to enable position tracking")
        
        else:
            print(f"❌ Dashboard API failed: {response.status_code}")
    
    except Exception as e:
        print(f"❌ Error checking dashboard API: {e}")
    
    # Step 5: Recovery recommendations
    print(f"\n💡 RECOVERY RECOMMENDATIONS")
    print("-" * 40)
    
    if active_positions:
        print("🔧 RECOMMENDED ACTIONS:")
        print("1. Check if bot is running (should show 'running' status)")
        print("2. If bot is stopped, restart it to enable position recovery")
        print("3. If bot is running but not showing positions:")
        print("   a. Check if trade exists in database but marked as CLOSED")
        print("   b. Manually update trade status to OPEN if needed")
        print("   c. Create recovery trade record if no database entry exists")
        print("4. Force refresh dashboard after making changes")
        
        print(f"\n📋 POSITION DETAILS FOR MANUAL RECOVERY:")
        for i, pos in enumerate(active_positions, 1):
            print(f"Position {i}:")
            print(f"  Symbol: {pos['symbol']}")
            print(f"  Side: {pos['side']}")
            print(f"  Quantity: {pos['quantity']}")
            print(f"  Entry Price: ${pos['entry_price']}")
            print(f"  Current PnL: ${pos['unrealized_pnl']:.2f}")
            print()

if __name__ == "__main__":
    investigate_missing_dashboard_position()
