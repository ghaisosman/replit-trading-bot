
#!/usr/bin/env python3
"""
Quick WebSocket Validation
==========================
Lightweight test that validates WebSocket without overwhelming the connection
"""

import sys
import os
import asyncio
import time
from datetime import datetime

sys.path.append('src')

async def quick_validation():
    """Quick validation that works within connection limits"""
    print("🚀 QUICK WEBSOCKET VALIDATION")
    print("=" * 50)
    
    try:
        from src.data_fetcher.websocket_manager import WebSocketKlineManager
        from src.binance_client.client import BinanceClientWrapper
        
        # Initialize components
        ws_manager = WebSocketKlineManager()
        binance_client = BinanceClientWrapper()
        
        # Test 1: Basic Connection
        print("\n📡 Testing Basic Connection...")
        ws_manager.add_symbol_interval('BTCUSDT', '1m')
        ws_manager.add_symbol_interval('ETHUSDT', '1m')
        
        ws_manager.start()
        
        # Wait for connection
        for i in range(10):
            if ws_manager.is_connected:
                print(f"✅ Connected in {i+1} seconds")
                break
            await asyncio.sleep(1)
        
        if not ws_manager.is_connected:
            print("❌ Connection failed")
            return False
        
        # Test 2: Data Reception (lightweight)
        print("\n📊 Testing Data Reception...")
        await asyncio.sleep(5)  # Wait for some data
        
        stats = ws_manager.get_statistics()
        messages = stats.get('messages_received', 0)
        klines = stats.get('klines_processed', 0)
        
        print(f"   Messages: {messages}")
        print(f"   Klines: {klines}")
        
        if messages > 0 and klines > 0:
            print("✅ Data reception working")
        else:
            print("❌ No data received")
            return False
        
        # Test 3: Current Prices
        print("\n💰 Testing Current Prices...")
        btc_price = ws_manager.get_current_price('BTCUSDT')
        eth_price = ws_manager.get_current_price('ETHUSDT')
        
        if btc_price and eth_price:
            print(f"   BTC: ${btc_price:,.2f}")
            print(f"   ETH: ${eth_price:,.2f}")
            print("✅ Price fetching working")
        else:
            print("❌ Price fetching failed")
            return False
        
        # Test 4: REST API Fallback
        print("\n🔄 Testing REST API Backup...")
        try:
            connection_test = await binance_client.test_connection()
            if connection_test:
                print("✅ REST API working as backup")
            else:
                print("❌ REST API not working")
                return False
        except Exception as e:
            print(f"❌ REST API error: {e}")
            return False
        
        # Cleanup
        ws_manager.stop()
        
        print("\n🎉 QUICK VALIDATION PASSED!")
        print("✅ WebSocket: Working")
        print("✅ Data Flow: Working") 
        print("✅ Price Updates: Working")
        print("✅ REST Backup: Working")
        
        return True
        
    except Exception as e:
        print(f"❌ Validation failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(quick_validation())
    if success:
        print("\n🚀 READY FOR TRADING!")
    else:
        print("\n⚠️ Need to address issues before trading")
