
#!/usr/bin/env python3
"""
Stop Loss Enforcement Verification Script
Monitor and verify that stop loss is working correctly in both live trading and backtesting
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.binance_client.client import BinanceClientWrapper
from src.bot_manager import TradingBot
import json
from datetime import datetime

def check_stop_loss_enforcement():
    print("🛑 STOP LOSS ENFORCEMENT VERIFICATION")
    print("=" * 60)
    
    # Initialize components
    trade_db = TradeDatabase()
    binance_client = BinanceClientWrapper()
    
    # 1. CHECK RECENT TRADES FOR STOP LOSS VIOLATIONS
    print("\n📊 ANALYZING RECENT TRADES FOR STOP LOSS VIOLATIONS:")
    
    violations_found = 0
    total_trades_checked = 0
    
    for trade_id, trade_data in trade_db.trades.items():
        if trade_data.get('trade_status') == 'CLOSED':
            total_trades_checked += 1
            
            # Get trade details
            entry_price = float(trade_data.get('entry_price', 0))
            exit_price = float(trade_data.get('exit_price', 0))
            side = trade_data.get('side', '')
            margin_used = float(trade_data.get('margin_used', 0))
            max_loss_pct = float(trade_data.get('max_loss_pct', 10))
            pnl_usdt = float(trade_data.get('pnl_usdt', 0))
            pnl_percentage = float(trade_data.get('pnl_percentage', 0))
            exit_reason = trade_data.get('exit_reason', '')
            
            # Calculate expected max loss
            expected_max_loss = margin_used * (max_loss_pct / 100)
            
            # Check if loss exceeded the configured maximum
            if pnl_usdt < -expected_max_loss and 'Stop Loss' not in exit_reason:
                violations_found += 1
                
                print(f"\n⚠️ VIOLATION #{violations_found} - {trade_id}")
                print(f"   Symbol: {trade_data.get('symbol')}")
                print(f"   Entry: ${entry_price:.4f} | Exit: ${exit_price:.4f} | Side: {side}")
                print(f"   Margin: ${margin_used:.2f} | Max Loss %: {max_loss_pct}%")
                print(f"   Expected Max Loss: ${expected_max_loss:.2f}")
                print(f"   Actual Loss: ${pnl_usdt:.2f} ({pnl_percentage:.2f}%)")
                print(f"   Exit Reason: {exit_reason}")
                print(f"   ❌ LOSS EXCEEDED LIMIT BY: ${abs(pnl_usdt + expected_max_loss):.2f}")
    
    # 2. CHECK CURRENT ACTIVE POSITIONS
    print(f"\n📈 CHECKING CURRENT ACTIVE POSITIONS:")
    
    try:
        # Check if trading bot is running and has active positions
        active_positions_found = False
        
        if binance_client.is_futures:
            positions = binance_client.client.futures_position_information()
            
            for position in positions:
                position_amt = float(position.get('positionAmt', 0))
                if abs(position_amt) > 0.001:  # Active position
                    active_positions_found = True
                    symbol = position['symbol']
                    entry_price = float(position.get('entryPrice', 0))
                    mark_price = float(position.get('markPrice', 0))
                    unrealized_pnl = float(position.get('unRealizedPnL', 0))
                    
                    print(f"\n🔍 ACTIVE POSITION: {symbol}")
                    print(f"   Amount: {position_amt}")
                    print(f"   Entry: ${entry_price:.4f}")
                    print(f"   Mark Price: ${mark_price:.4f}")
                    print(f"   Unrealized PnL: ${unrealized_pnl:.2f}")
                    
                    # Find corresponding trade in database
                    matching_trade = None
                    for trade_id, trade_data in trade_db.trades.items():
                        if (trade_data.get('symbol') == symbol and 
                            trade_data.get('trade_status') == 'OPEN' and
                            abs(float(trade_data.get('entry_price', 0)) - entry_price) < 0.01):
                            matching_trade = trade_data
                            break
                    
                    if matching_trade:
                        margin_used = float(matching_trade.get('margin_used', 50))
                        max_loss_pct = float(matching_trade.get('max_loss_pct', 10))
                        expected_max_loss = margin_used * (max_loss_pct / 100)
                        
                        print(f"   📊 Trade Config: Margin=${margin_used:.2f}, Max Loss={max_loss_pct}%")
                        print(f"   🎯 Expected Max Loss: ${expected_max_loss:.2f}")
                        
                        if unrealized_pnl < -expected_max_loss:
                            print(f"   🚨 STOP LOSS SHOULD TRIGGER! Current loss exceeds limit by ${abs(unrealized_pnl + expected_max_loss):.2f}")
                        else:
                            print(f"   ✅ Position within stop loss limits")
                    else:
                        print(f"   ⚠️ No matching trade found in database")
        
        if not active_positions_found:
            print("   ℹ️ No active positions found")
            
    except Exception as e:
        print(f"   ❌ Error checking active positions: {e}")
    
    # 3. SUMMARY AND RECOMMENDATIONS
    print(f"\n📋 STOP LOSS ENFORCEMENT SUMMARY:")
    print(f"   Total Trades Analyzed: {total_trades_checked}")
    print(f"   Stop Loss Violations Found: {violations_found}")
    
    if violations_found > 0:
        violation_rate = (violations_found / total_trades_checked) * 100 if total_trades_checked > 0 else 0
        print(f"   Violation Rate: {violation_rate:.1f}%")
        print(f"\n🔧 RECOMMENDATIONS:")
        print(f"   1. Stop loss enforcement is NOT working properly")
        print(f"   2. Review exit condition checking in bot_manager.py")
        print(f"   3. Verify stop loss price calculations")
        print(f"   4. Test stop loss with smaller positions first")
    else:
        print(f"   ✅ Stop loss enforcement appears to be working correctly")
    
    # 4. CONFIGURATION ANALYSIS
    print(f"\n⚙️ STOP LOSS CONFIGURATION ANALYSIS:")
    
    strategies_analyzed = set()
    for trade_id, trade_data in trade_db.trades.items():
        strategy_name = trade_data.get('strategy_name', 'unknown')
        if strategy_name not in strategies_analyzed:
            strategies_analyzed.add(strategy_name)
            
            max_loss_pct = trade_data.get('max_loss_pct', 10)
            margin = trade_data.get('margin_used', 50)
            leverage = trade_data.get('leverage', 5)
            
            print(f"\n   Strategy: {strategy_name}")
            print(f"   - Max Loss %: {max_loss_pct}%")
            print(f"   - Margin: ${margin}")
            print(f"   - Leverage: {leverage}x")
            print(f"   - Max Loss Amount: ${margin * (max_loss_pct / 100):.2f}")

if __name__ == "__main__":
    check_stop_loss_enforcement()
