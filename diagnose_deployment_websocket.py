
#!/usr/bin/env python3
"""
Diagnose WebSocket Status in Deployment
Check why WebSocket isn't preventing rate limits
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.data_fetcher.websocket_manager import websocket_manager
from src.binance_client.client import BinanceClientWrapper
from src.data_fetcher.price_fetcher import PriceFetcher
import time
import asyncio

async def diagnose_websocket():
    print("🔍 DEPLOYMENT WEBSOCKET DIAGNOSIS")
    print("=" * 50)
    
    # Check if WebSocket manager is initialized
    print(f"📡 WebSocket manager instance: {websocket_manager}")
    print(f"🔗 Connection status: {websocket_manager.is_connected}")
    print(f"🏃 Running status: {websocket_manager.is_running}")
    print(f"📊 Subscribed streams: {len(websocket_manager.subscribed_streams)}")
    
    if websocket_manager.subscribed_streams:
        print("📋 Active streams:")
        for stream in websocket_manager.subscribed_streams:
            print(f"   • {stream}")
    
    # Check statistics
    stats = websocket_manager.get_statistics()
    print(f"\n📊 WEBSOCKET STATISTICS:")
    print(f"   Messages received: {stats.get('messages_received', 0)}")
    print(f"   Klines processed: {stats.get('klines_processed', 0)}")
    print(f"   Connection uptime: {stats.get('uptime_seconds', 0):.1f}s")
    print(f"   Last message: {stats.get('last_message_time', 'Never')}")
    
    # Test WebSocket startup
    print(f"\n🚀 TESTING WEBSOCKET STARTUP:")
    
    if not websocket_manager.is_running:
        print("📡 Starting WebSocket for ADAUSDT...")
        websocket_manager.add_symbol_interval('ADAUSDT', '1m')
        websocket_manager.start()
        
        # Wait for connection
        for i in range(10):
            if websocket_manager.is_connected:
                print(f"✅ Connected in {i+1} seconds")
                break
            await asyncio.sleep(1)
            print(f"   ⏳ Waiting... {i+1}/10")
        
        if not websocket_manager.is_connected:
            print("❌ WebSocket failed to connect!")
            return False
    
    # Test price fetching
    print(f"\n💰 TESTING PRICE FETCHING:")
    binance_client = BinanceClientWrapper()
    price_fetcher = PriceFetcher(binance_client)
    
    # This should use WebSocket if available
    price = price_fetcher.get_current_price('ADAUSDT')
    print(f"🏷️ ADAUSDT price: ${price}")
    
    # Check if WebSocket data is being used
    cached_data = websocket_manager.get_cached_klines('ADAUSDT', '1m', 5)
    if cached_data:
        print(f"✅ WebSocket cache has {len(cached_data)} klines")
        latest = cached_data[-1]
        print(f"   Latest: ${latest['close']:.6f} at {latest['timestamp']}")
    else:
        print("❌ No WebSocket cache data - REST API fallback likely")
    
    # Monitor API calls
    print(f"\n📞 API CALL MONITORING:")
    initial_calls = getattr(binance_client, '_request_count', 0)
    
    # Simulate bot operations
    for i in range(3):
        price = price_fetcher.get_current_price('ADAUSDT')
        print(f"   Test {i+1}: ${price}")
        await asyncio.sleep(1)
    
    final_calls = getattr(binance_client, '_request_count', 0)
    api_calls_made = final_calls - initial_calls
    
    print(f"📊 API calls made during test: {api_calls_made}")
    
    if api_calls_made == 0:
        print("✅ EXCELLENT: No API calls - WebSocket working perfectly!")
    elif api_calls_made <= 1:
        print("✅ GOOD: Minimal API calls - WebSocket mostly working")
    else:
        print("⚠️ WARNING: Too many API calls - WebSocket not preventing REST fallback")
    
    return api_calls_made == 0

if __name__ == "__main__":
    asyncio.run(diagnose_websocket())
