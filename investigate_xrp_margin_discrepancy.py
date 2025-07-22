
#!/usr/bin/env python3
"""
Investigate XRP Margin Discrepancy
Check why recovered XRP trade shows different margin than actual Binance position
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.binance_client.client import BinanceClientWrapper
from datetime import datetime

def investigate_xrp_margin_discrepancy():
    print("🔍 INVESTIGATING XRP MARGIN DISCREPANCY")
    print("=" * 60)
    
    # Initialize components
    trade_db = TradeDatabase()
    binance_client = BinanceClientWrapper()
    
    # Find the XRP trade in database
    xrp_trade = None
    xrp_trade_id = None
    
    for trade_id, trade_data in trade_db.trades.items():
        if (trade_data.get('trade_status') == 'OPEN' and 
            'XRP' in trade_data.get('symbol', '')):
            xrp_trade = trade_data
            xrp_trade_id = trade_id
            break
    
    if not xrp_trade:
        print("❌ No open XRP trade found in database")
        return
    
    print(f"📊 Found XRP trade: {xrp_trade_id}")
    print(f"   Strategy: {xrp_trade.get('strategy_name')}")
    print(f"   Symbol: {xrp_trade.get('symbol')}")
    print(f"   Side: {xrp_trade.get('side')}")
    print(f"   Quantity: {xrp_trade.get('quantity')}")
    print(f"   Entry Price: ${xrp_trade.get('entry_price')}")
    
    # Database values
    print(f"\n💾 DATABASE VALUES:")
    db_position_value = xrp_trade.get('position_value_usdt', 0)
    db_leverage = xrp_trade.get('leverage', 1)
    db_margin = xrp_trade.get('margin_used', 0)
    
    print(f"   Position Value USDT: ${db_position_value}")
    print(f"   Leverage: {db_leverage}x")
    print(f"   Margin Used: ${db_margin}")
    
    # Calculate what margin should be
    calculated_margin = db_position_value / db_leverage if db_leverage > 0 else 0
    print(f"   Calculated Margin (Position/Leverage): ${calculated_margin:.2f}")
    
    # Get actual Binance position
    print(f"\n🔗 BINANCE POSITION DATA:")
    try:
        account_info = binance_client.client.futures_account()
        positions = account_info.get('positions', [])
        
        binance_position = None
        for position in positions:
            if position.get('symbol') == 'XRPUSDT':
                position_amt = float(position.get('positionAmt', 0))
                if abs(position_amt) > 0.001:
                    binance_position = position
                    break
        
        if binance_position:
            binance_entry_price = float(binance_position.get('entryPrice', 0))
            binance_quantity = abs(float(binance_position.get('positionAmt', 0)))
            binance_position_value = binance_entry_price * binance_quantity
            binance_leverage = int(binance_position.get('leverage', 1))
            
            # Calculate actual margin from Binance data
            actual_margin_from_binance = binance_position_value / binance_leverage
            
            print(f"   Entry Price: ${binance_entry_price}")
            print(f"   Quantity: {binance_quantity}")
            print(f"   Position Value: ${binance_position_value:.2f} USDT")
            print(f"   Leverage: {binance_leverage}x")
            print(f"   Calculated Margin: ${actual_margin_from_binance:.2f} USDT")
            
            # Get actual margin used from Binance (if available)
            initial_margin = float(binance_position.get('initialMargin', 0))
            if initial_margin > 0:
                print(f"   Actual Initial Margin: ${initial_margin:.2f} USDT")
            
            # ANALYSIS
            print(f"\n🔍 DISCREPANCY ANALYSIS:")
            print(f"   Database Margin: ${db_margin:.2f}")
            print(f"   Binance Calculated: ${actual_margin_from_binance:.2f}")
            if initial_margin > 0:
                print(f"   Binance Actual: ${initial_margin:.2f}")
            
            # Check for issues
            margin_difference = abs(db_margin - actual_margin_from_binance)
            print(f"   Difference: ${margin_difference:.2f}")
            
            if margin_difference > 0.5:
                print(f"\n❌ SIGNIFICANT MARGIN DISCREPANCY DETECTED!")
                
                # Possible causes
                print(f"\n🔍 POSSIBLE CAUSES:")
                
                # 1. Leverage mismatch
                if db_leverage != binance_leverage:
                    print(f"   1. ❌ LEVERAGE MISMATCH: DB={db_leverage}x vs Binance={binance_leverage}x")
                else:
                    print(f"   1. ✅ Leverage matches: {db_leverage}x")
                
                # 2. Position value calculation
                db_calculated_position = float(xrp_trade.get('entry_price', 0)) * float(xrp_trade.get('quantity', 0))
                if abs(db_calculated_position - binance_position_value) > 1:
                    print(f"   2. ❌ POSITION VALUE MISMATCH: DB=${db_calculated_position:.2f} vs Binance=${binance_position_value:.2f}")
                else:
                    print(f"   2. ✅ Position value matches: ${db_calculated_position:.2f}")
                
                # 3. Recovery calculation error
                recovery_source = xrp_trade.get('recovery_source', 'UNKNOWN')
                if 'RECOVERY' in recovery_source:
                    print(f"   3. ⚠️ RECOVERY TRADE: May have incorrect default leverage")
                    print(f"      Recovery used: {db_leverage}x leverage")
                    print(f"      Actual leverage: {binance_leverage}x")
                
                # 4. Database corruption
                if db_position_value != db_calculated_position:
                    print(f"   4. ❌ DATABASE INCONSISTENCY: stored position_value_usdt != calculated")
                
                # FIX THE ISSUE
                print(f"\n🔧 FIXING MARGIN DISCREPANCY:")
                
                # Use actual Binance data for correction
                correct_margin = actual_margin_from_binance
                if initial_margin > 0 and abs(initial_margin - actual_margin_from_binance) < 0.1:
                    correct_margin = initial_margin  # Use actual if very close
                
                updates = {
                    'margin_used': correct_margin,
                    'position_value_usdt': binance_position_value,
                    'leverage': binance_leverage,
                    'entry_price': binance_entry_price,
                    'quantity': binance_quantity,
                    'margin_fix_applied': True,
                    'margin_fix_timestamp': datetime.now().isoformat(),
                    'original_margin': db_margin,
                    'binance_verified_margin': correct_margin
                }
                
                # Apply the fix
                trade_db.update_trade(xrp_trade_id, updates)
                
                print(f"   ✅ MARGIN CORRECTED:")
                print(f"      Old Margin: ${db_margin:.2f}")
                print(f"      New Margin: ${correct_margin:.2f}")
                print(f"      Leverage: {binance_leverage}x")
                print(f"      Position Value: ${binance_position_value:.2f}")
                
                # Verify the fix
                updated_trade = trade_db.get_trade(xrp_trade_id)
                print(f"\n✅ VERIFICATION:")
                print(f"   Updated Margin: ${updated_trade.get('margin_used'):.2f}")
                print(f"   Updated Leverage: {updated_trade.get('leverage')}x")
                print(f"   Updated Position Value: ${updated_trade.get('position_value_usdt'):.2f}")
                
            else:
                print(f"✅ Margin values are within acceptable range")
        else:
            print("❌ No matching XRP position found on Binance")
            
    except Exception as e:
        print(f"❌ Error fetching Binance data: {e}")
    
    # ROOT CAUSE ANALYSIS
    print(f"\n🎯 ROOT CAUSE ANALYSIS:")
    recovery_source = xrp_trade.get('recovery_source', 'UNKNOWN')
    strategy_name = xrp_trade.get('strategy_name', 'UNKNOWN')
    
    if 'RECOVERY' in recovery_source or 'AUTO_RECOVERED' in strategy_name:
        print(f"   📋 RECOVERY TRADE DETECTED")
        print(f"      Source: {recovery_source}")
        print(f"      Strategy: {strategy_name}")
        print(f"   ")
        print(f"   🔍 LIKELY ISSUE: Recovery system used default leverage")
        print(f"      instead of actual Binance leverage setting")
        print(f"   ")
        print(f"   💡 SOLUTION: Recovery should query actual leverage")
        print(f"      from Binance position data, not use defaults")
    
    print(f"\n📋 SUMMARY:")
    print(f"   • Database margin calculation should match Binance exactly")
    print(f"   • Recovery trades need to use actual Binance leverage")
    print(f"   • Position value should be calculated from actual entry price & quantity")
    print(f"   • Margin = Position Value ÷ Actual Leverage")

if __name__ == "__main__":
    investigate_xrp_margin_discrepancy()
