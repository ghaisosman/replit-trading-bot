
#!/usr/bin/env python3
"""
Check Indicator Data Sufficiency
Verify if strategies have enough data for accurate calculations
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.data_fetcher.websocket_manager import websocket_manager
from src.execution_engine.strategies.rsi_oversold_config import RSIOversoldConfig
import logging

def check_and_fix_indicator_data():
    """Check if each strategy has sufficient data for indicators"""
    print("🔍 CHECKING INDICATOR DATA SUFFICIENCY")
    print("=" * 50)
    
    # Define data requirements
    requirements = {
        'RSI': 14,
        'MACD': 26,
        'SMA_20': 20,
        'SMA_50': 50
    }
    
    # Active trading symbols
    active_symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
    intervals = ['1m', '5m', '15m', '1h']
    
    all_sufficient = True
    insufficient_data = []
    
    for symbol in active_symbols:
        print(f"\n📈 {symbol}")
        print("-" * 20)
        
        for interval in intervals:
            cached_klines = websocket_manager.get_cached_klines(symbol, interval, 100)
            
            if not cached_klines:
                print(f"   {interval}: ❌ No data")
                insufficient_data.append(f"{symbol}@{interval}")
                all_sufficient = False
                continue
            
            data_count = len(cached_klines)
            print(f"   {interval}: {data_count} klines")
            
            # Check each indicator requirement
            for indicator, required_count in requirements.items():
                if data_count >= required_count:
                    status = "✅"
                else:
                    status = "❌"
                    all_sufficient = False
                    insufficient_data.append(f"{symbol}@{interval} for {indicator}")
                
                print(f"      {indicator}: {status} ({data_count}/{required_count})")
    
    # Summary and fix recommendations
    print(f"\n📊 SUMMARY")
    print("=" * 20)
    
    if all_sufficient:
        print("✅ All indicators have sufficient data")
        print("💡 Issue may be in strategy implementation")
        
        # Check strategy configuration
        print(f"\n🎯 Strategy Configuration Check")
        try:
            rsi_config = RSIOversoldConfig.get_config()
            rsi_period = rsi_config.get('rsi_period', 14)
            print(f"   RSI Period: {rsi_period}")
            
            # Verify we have enough data for configured RSI period
            btc_data = websocket_manager.get_cached_klines('BTCUSDT', '1m', rsi_period + 10)
            if btc_data and len(btc_data) >= rsi_period:
                print(f"   ✅ BTCUSDT has {len(btc_data)} klines for RSI-{rsi_period}")
            else:
                print(f"   ❌ BTCUSDT insufficient for RSI-{rsi_period}")
                
        except Exception as e:
            print(f"   ❌ Error checking strategy config: {e}")
    else:
        print(f"❌ {len(insufficient_data)} data insufficiencies found:")
        for item in insufficient_data[:10]:  # Show first 10
            print(f"   • {item}")
        
        if len(insufficient_data) > 10:
            print(f"   ... and {len(insufficient_data) - 10} more")
    
    # Recommendations
    print(f"\n💡 RECOMMENDATIONS")
    print("=" * 25)
    
    if not websocket_manager.is_connected:
        print("1. ❌ WebSocket is disconnected - restart required")
        print("   Run: websocket_manager.start()")
    elif not all_sufficient:
        print("1. ⏳ Wait for more data accumulation (15-30 minutes)")
        print("2. 🔄 Consider restarting WebSocket manager")
        print("3. 📊 Check if specific symbols are problematic")
    else:
        print("1. 🔍 Check strategy indicator calculation logic")
        print("2. 🎯 Verify strategy is using WebSocket data correctly")
        print("3. 📝 Check if strategies are throwing calculation errors")

if __name__ == "__main__":
    check_and_fix_indicator_data()
