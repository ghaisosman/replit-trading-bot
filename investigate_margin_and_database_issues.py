
#!/usr/bin/env python3
"""
Investigate Margin Configuration and Database Recording Issues
1. Check if margin config vs actual position value matches
2. Verify database recording completeness for trades
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.binance_client.client import BinanceClientWrapper
from src.config.trading_config import trading_config_manager
from datetime import datetime, timedelta

def investigate_margin_issue():
    """Investigate margin configuration vs actual position size"""
    print("🔍 INVESTIGATING MARGIN CONFIGURATION ISSUE")
    print("=" * 60)
    
    # Get current strategy configurations from web dashboard
    all_strategies = trading_config_manager.get_all_strategies()
    
    print("📊 CURRENT STRATEGY CONFIGURATIONS:")
    for strategy_name, config in all_strategies.items():
        if 'ETH' in config.get('symbol', '').upper():
            margin = config.get('margin', 0)
            leverage = config.get('leverage', 1)
            symbol = config.get('symbol', '')
            
            print(f"\n🎯 {strategy_name}:")
            print(f"   💰 Configured Margin: ${margin} USDT")
            print(f"   ⚡ Configured Leverage: {leverage}x")
            print(f"   💱 Symbol: {symbol}")
            print(f"   📊 Expected Position Value: ${margin * leverage} USDT")
            
            # Check if there are web dashboard overrides
            if strategy_name in trading_config_manager.strategy_overrides:
                web_config = trading_config_manager.strategy_overrides[strategy_name]
                print(f"   🌐 Web Dashboard Overrides: {web_config}")

def investigate_database_recording():
    """Investigate database recording completeness"""
    print("\n\n🔍 INVESTIGATING DATABASE RECORDING ISSUES")
    print("=" * 60)
    
    trade_db = TradeDatabase()
    
    # Find recent ETH trades
    eth_trades = []
    for trade_id, trade_data in trade_db.trades.items():
        if 'ETH' in trade_data.get('symbol', '').upper():
            eth_trades.append((trade_id, trade_data))
    
    print(f"📊 Found {len(eth_trades)} ETH trades in database")
    
    # Analyze the most recent ETH trades
    eth_trades.sort(key=lambda x: x[1].get('timestamp', ''), reverse=True)
    
    for i, (trade_id, trade_data) in enumerate(eth_trades[:3]):  # Check last 3 ETH trades
        print(f"\n📋 ETH Trade #{i+1}: {trade_id}")
        print(f"   Strategy: {trade_data.get('strategy_name', 'Unknown')}")
        print(f"   Symbol: {trade_data.get('symbol', 'Unknown')}")
        print(f"   Status: {trade_data.get('trade_status', 'Unknown')}")
        print(f"   Timestamp: {trade_data.get('timestamp', 'Unknown')}")
        
        # Check for missing critical data
        missing_fields = []
        critical_fields = {
            'margin_used': 'Margin Used',
            'leverage': 'Leverage',
            'position_value_usdt': 'Position Value USDT',
            'entry_price': 'Entry Price',
            'quantity': 'Quantity'
        }
        
        print(f"   🔍 CRITICAL DATA ANALYSIS:")
        for field, description in critical_fields.items():
            value = trade_data.get(field)
            if value is None or value == 0:
                missing_fields.append(description)
                print(f"   ❌ {description}: MISSING")
            else:
                print(f"   ✅ {description}: {value}")
        
        # Check closure data if trade is closed
        if trade_data.get('trade_status') == 'CLOSED':
            print(f"   🔒 CLOSURE DATA ANALYSIS:")
            closure_fields = {
                'exit_price': 'Exit Price',
                'pnl_usdt': 'P&L USDT',
                'pnl_percentage': 'P&L Percentage',
                'exit_reason': 'Exit Reason',
                'duration_minutes': 'Duration (minutes)'
            }
            
            closure_missing = []
            for field, description in closure_fields.items():
                value = trade_data.get(field)
                if value is None:
                    closure_missing.append(description)
                    print(f"   ❌ {description}: MISSING")
                else:
                    print(f"   ✅ {description}: {value}")
            
            if closure_missing:
                print(f"   🚨 MISSING CLOSURE DATA: {', '.join(closure_missing)}")
        
        # Calculate what the data SHOULD be based on available info
        print(f"   🧮 CALCULATED EXPECTATIONS:")
        entry_price = trade_data.get('entry_price', 0)
        quantity = trade_data.get('quantity', 0)
        leverage = trade_data.get('leverage', 1)
        
        if entry_price and quantity:
            expected_position_value = entry_price * quantity
            expected_margin = expected_position_value / leverage if leverage > 0 else expected_position_value
            
            print(f"   📊 Expected Position Value: ${expected_position_value:.2f} USDT")
            print(f"   💰 Expected Margin Used: ${expected_margin:.2f} USDT")
            
            # Compare with recorded values
            recorded_position_value = trade_data.get('position_value_usdt', 0)
            recorded_margin = trade_data.get('margin_used', 0)
            
            if recorded_position_value != expected_position_value:
                print(f"   ⚠️ POSITION VALUE MISMATCH: Recorded ${recorded_position_value:.2f} vs Expected ${expected_position_value:.2f}")
            
            if recorded_margin != expected_margin:
                print(f"   ⚠️ MARGIN MISMATCH: Recorded ${recorded_margin:.2f} vs Expected ${expected_margin:.2f}")

def check_position_size_calculation_logic():
    """Analyze the position size calculation logic in order manager"""
    print("\n\n🔍 ANALYZING POSITION SIZE CALCULATION LOGIC")
    print("=" * 60)
    
    # This simulates what happens in order manager when calculating position size
    print("📊 POSITION SIZE CALCULATION SIMULATION:")
    
    # Example with ETH configuration
    margin = 10.0  # Dashboard configured margin
    leverage = 5   # Example leverage
    entry_price = 3500.0  # Example ETH price
    
    print(f"   💰 Configured Margin: ${margin} USDT")
    print(f"   ⚡ Leverage: {leverage}x")
    print(f"   💵 Entry Price: ${entry_price}")
    
    # Calculate position value and quantity (this mirrors order_manager logic)
    position_value_usdt = margin * leverage
    quantity = position_value_usdt / entry_price
    
    print(f"   📊 Calculated Position Value: ${position_value_usdt} USDT")
    print(f"   🔢 Calculated Quantity: {quantity:.6f} ETH")
    
    # Apply symbol precision (simulating what order manager does)
    # ETH typically has 2 decimal precision
    precision = 2
    quantity_rounded = round(quantity, precision)
    
    print(f"   🔧 Rounded Quantity (precision {precision}): {quantity_rounded} ETH")
    
    # Calculate actual position value with rounded quantity
    actual_position_value = quantity_rounded * entry_price
    actual_margin_used = actual_position_value / leverage
    
    print(f"   💰 ACTUAL Position Value: ${actual_position_value:.2f} USDT")
    print(f"   💸 ACTUAL Margin Used: ${actual_margin_used:.2f} USDT")
    
    if abs(actual_margin_used - margin) > 0.1:
        print(f"   🚨 MARGIN DEVIATION: ${abs(actual_margin_used - margin):.2f} USDT from configured")
        print(f"   ⚠️ This explains why position was ${actual_margin_used:.0f} USDT instead of ${margin:.0f} USDT")
    else:
        print(f"   ✅ Margin calculation matches configuration")

def check_database_recording_methods():
    """Check what methods are used for database recording"""
    print("\n\n🔍 ANALYZING DATABASE RECORDING METHODS")
    print("=" * 60)
    
    print("📊 TRADE RECORDING FLOW ANALYSIS:")
    print("1. Order Manager executes trade")
    print("2. Position object is created with trade_id")
    print("3. _record_trade_immediately() is called")
    print("4. TradeDatabase.add_trade() is called")
    print("5. Database verification occurs")
    
    print("\n🔍 POTENTIAL RECORDING ISSUES:")
    print("1. ❓ Missing margin_used field in trade data")
    print("2. ❓ Database save verification may fail silently")
    print("3. ❓ Manual closure doesn't trigger database update")
    print("4. ❓ Emergency fallback not preserving all fields")

def main():
    print("🔍 COMPREHENSIVE MARGIN AND DATABASE INVESTIGATION")
    print("=" * 80)
    print("Investigating two reported issues:")
    print("1. Margin config vs actual position size mismatch")
    print("2. Missing database recording for trades")
    print("=" * 80)
    
    try:
        investigate_margin_issue()
        investigate_database_recording()
        check_position_size_calculation_logic()
        check_database_recording_methods()
        
        print("\n\n📋 INVESTIGATION SUMMARY")
        print("=" * 40)
        print("✅ Investigation completed")
        print("📊 Check the analysis above for detailed findings")
        print("🔧 Recommendations will be provided based on findings")
        
    except Exception as e:
        print(f"❌ Error during investigation: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    main()
