
#!/usr/bin/env python3
"""
Trace Margin Recording Path
Add debugging to trace exactly where margin gets lost during trade recording
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def add_margin_tracing():
    """Add detailed logging to trace margin recording"""
    
    # Read the current order manager code
    order_manager_file = "src/execution_engine/order_manager.py"
    
    with open(order_manager_file, 'r') as f:
        content = f.read()
    
    # Find the execute_signal method and add tracing
    if "# Calculate actual margin used for this specific position" in content:
        print("✅ Margin tracing already added to execute_signal")
    else:
        print("❌ Need to add margin tracing to execute_signal")
    
    # Check trade database add_trade method
    trade_db_file = "src/execution_engine/trade_database.py"
    
    with open(trade_db_file, 'r') as f:
        db_content = f.read()
    
    if "CALCULATED missing margin_used" in db_content:
        print("✅ Margin calculation tracing already added to trade_database")
    else:
        print("❌ Need to add margin calculation tracing to trade_database")
    
    print("\n🔍 MARGIN RECORDING PATH ANALYSIS:")
    print("1. execute_signal() calculates actual_margin_used")
    print("2. Position object stores actual_margin_used")
    print("3. _record_confirmed_trade() uses position.actual_margin_used")
    print("4. TradeDatabase.add_trade() validates and stores margin")
    print("5. Recovery system may overwrite with calculated margin")
    
    print("\n🎯 LIKELY ISSUE LOCATIONS:")
    print("- Recovery trades may not have proper margin calculation")
    print("- Position recovery may be using wrong leverage value")
    print("- Database validation may be overwriting correct margin")

def main():
    print("🔍 TRACING MARGIN RECORDING PATH")
    print("=" * 40)
    
    add_margin_tracing()
    
    # Show current trade flow
    print("\n📋 CURRENT TRADE RECORDING FLOW:")
    print("1. Signal detected → execute_signal()")
    print("2. Calculate position size → _calculate_position_size()")
    print("3. Place Binance order → binance_client.create_order()")
    print("4. Create Position object with actual_margin_used")
    print("5. Record trade → _record_confirmed_trade()")
    print("6. Store in database → TradeDatabase.add_trade()")
    print("7. Store in logger → trade_logger.log_trade_entry()")
    
    print("\n🔧 RECOVERY FLOW (LIKELY ISSUE):")
    print("1. Bot startup → _recover_active_positions()")
    print("2. Find Binance positions → recover_missing_positions()")
    print("3. Match or create database entries")
    print("4. Load into order_manager.active_positions")
    print("⚠️ ISSUE: Recovery may not preserve original margin data")

if __name__ == "__main__":
    main()
