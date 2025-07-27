
#!/usr/bin/env python3
"""
Diagnose WebSocket Data Accumulation Issues
Check why indicators still show insufficient data after 3+ hours
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.data_fetcher.websocket_manager import websocket_manager
from src.binance_client.client import BinanceClientWrapper
from datetime import datetime, timedelta
import time

def diagnose_websocket_data_accumulation():
    """Comprehensive WebSocket data accumulation diagnosis"""
    print("🔍 WEBSOCKET DATA ACCUMULATION DIAGNOSIS")
    print("=" * 60)
    
    # Check WebSocket manager status
    print(f"\n📡 WebSocket Connection Status")
    print(f"   Connected: {websocket_manager.is_connected}")
    print(f"   Running: {websocket_manager.is_running}")
    print(f"   Subscribed Streams: {len(websocket_manager.subscribed_streams)}")
    
    # Get WebSocket statistics
    stats = websocket_manager.get_statistics()
    print(f"\n📊 WebSocket Statistics")
    print(f"   Messages Received: {stats.get('messages_received', 0)}")
    print(f"   Klines Processed: {stats.get('klines_processed', 0)}")
    print(f"   Uptime: {stats.get('uptime_seconds', 0):.1f} seconds")
    print(f"   Reconnections: {stats.get('reconnections', 0)}")
    
    if stats.get('last_message_time'):
        last_msg_age = (datetime.now() - stats['last_message_time']).total_seconds()
        print(f"   Last Message: {last_msg_age:.1f} seconds ago")
    
    # Check cache status for each symbol
    cache_status = websocket_manager.get_cache_status()
    print(f"\n🗄️ Cache Status by Symbol")
    
    for symbol, intervals in cache_status.items():
        print(f"\n   📈 {symbol}:")
        for interval, data in intervals.items():
            cached_count = data.get('cached_klines', 0)
            is_fresh = data.get('is_fresh', False)
            last_update = data.get('last_update', 'Never')
            
            # Determine if sufficient for indicators
            sufficient_for_rsi = cached_count >= 14
            sufficient_for_macd = cached_count >= 26
            sufficient_for_sma50 = cached_count >= 50
            
            print(f"      {interval}: {cached_count} klines | Fresh: {is_fresh}")
            print(f"         RSI Ready: {'✅' if sufficient_for_rsi else '❌'}")
            print(f"         MACD Ready: {'✅' if sufficient_for_macd else '❌'}")
            print(f"         SMA50 Ready: {'✅' if sufficient_for_sma50 else '❌'}")
            print(f"         Last Update: {last_update}")
    
    # Test current price fetching
    print(f"\n💰 Current Price Test")
    test_symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
    
    for symbol in test_symbols:
        current_price = websocket_manager.get_current_price(symbol)
        if current_price:
            print(f"   {symbol}: ${current_price:.4f} ✅")
        else:
            print(f"   {symbol}: No price data ❌")
    
    # Check specific kline data
    print(f"\n🕯️ Recent Kline Data Test")
    
    for symbol in test_symbols:
        recent_klines = websocket_manager.get_cached_klines(symbol, '1m', 10)
        if recent_klines:
            latest_kline = recent_klines[-1]
            kline_age = time.time() - latest_kline.get('received_at', 0)
            print(f"   {symbol}: {len(recent_klines)} recent klines")
            print(f"      Latest: ${latest_kline['close']:.4f} ({kline_age:.1f}s ago)")
            print(f"      Closed: {'Yes' if latest_kline.get('is_closed') else 'No'}")
        else:
            print(f"   {symbol}: No cached klines ❌")
    
    # Recommendations
    print(f"\n💡 RECOMMENDATIONS")
    print("=" * 30)
    
    total_klines = stats.get('klines_processed', 0)
    if total_klines < 100:
        print("❌ ISSUE: Very low kline reception")
        print("   • WebSocket may have connection issues")
        print("   • Check network connectivity")
        print("   • Consider restarting WebSocket manager")
    elif total_klines < 500:
        print("⚠️ ISSUE: Low kline reception for 3+ hours")
        print("   • Expected 180+ klines per symbol per hour")
        print("   • WebSocket experiencing intermittent issues")
    else:
        print("✅ Kline reception appears normal")
        print("   • Issue may be with indicator calculation")
        print("   • Check strategy implementation")
    
    # Check if strategies are getting data
    print(f"\n🎯 Strategy Data Access Test")
    
    from src.execution_engine.strategies.rsi_oversold_config import RSIOversoldConfig
    try:
        rsi_config = RSIOversoldConfig.get_config()
        rsi_period = rsi_config.get('rsi_period', 14)
        print(f"   RSI Strategy configured for {rsi_period}-period RSI")
        
        # Check if we have enough data for RSI
        btc_klines = websocket_manager.get_cached_klines('BTCUSDT', '1m', rsi_period + 5)
        if btc_klines and len(btc_klines) >= rsi_period:
            print(f"   ✅ Sufficient data for RSI calculation ({len(btc_klines)} klines)")
        else:
            print(f"   ❌ Insufficient data for RSI calculation")
            if btc_klines:
                print(f"      Only {len(btc_klines)} klines available, need {rsi_period}")
            else:
                print(f"      No klines available for BTCUSDT")
    
    except Exception as e:
        print(f"   ❌ Error testing strategy data access: {e}")

if __name__ == "__main__":
    diagnose_websocket_data_accumulation()
