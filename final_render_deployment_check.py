
#!/usr/bin/env python3
"""
Final Render Deployment Readiness Check
======================================
"""

import asyncio
import sys
import os
import time
from datetime import datetime

# Add src to path
sys.path.append('src')

async def final_deployment_check():
    """Final check before Render deployment"""
    print("🚀 FINAL RENDER DEPLOYMENT READINESS CHECK")
    print("=" * 60)
    
    try:
        from src.data_fetcher.websocket_manager import websocket_manager
        from src.binance_client.client import BinanceClientWrapper
        from src.data_fetcher.price_fetcher import PriceFetcher
        from src.config.global_config import global_config
        
        # Check configuration
        print(f"\n🔧 CONFIGURATION CHECK:")
        print(f"   Binance Mainnet: {not global_config.BINANCE_TESTNET}")
        print(f"   Futures Trading: {global_config.BINANCE_FUTURES}")
        print(f"   Environment: {'DEPLOYMENT' if os.environ.get('RENDER') else 'DEVELOPMENT'}")
        
        # Test WebSocket connection
        print(f"\n📡 WEBSOCKET CONNECTIVITY TEST:")
        
        # Add test symbols
        test_symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
        for symbol in test_symbols:
            websocket_manager.add_symbol_interval(symbol, '1m')
            websocket_manager.add_symbol_interval(symbol, '5m')
        
        if not websocket_manager.is_running:
            websocket_manager.start()
        
        # Wait for connection
        connection_wait = 0
        while not websocket_manager.is_connected and connection_wait < 30:
            await asyncio.sleep(1)
            connection_wait += 1
            if connection_wait % 5 == 0:
                print(f"   ⏳ Connecting... {connection_wait}/30s")
        
        if websocket_manager.is_connected:
            print("   ✅ WebSocket connected successfully")
            
            # Wait for initial data
            print("   ⏳ Waiting for market data...")
            await asyncio.sleep(10)
            
            # Check data reception
            stats = websocket_manager.get_statistics()
            cache_status = websocket_manager.get_cache_status()
            
            print(f"   📊 Messages received: {stats.get('messages_received', 0)}")
            print(f"   📈 Klines processed: {stats.get('klines_processed', 0)}")
            print(f"   🔗 Active streams: {stats.get('subscribed_streams', 0)}")
            
            # Test price fetching
            print(f"\n💰 PRICE FETCHING TEST:")
            binance_client = BinanceClientWrapper()
            price_fetcher = PriceFetcher(binance_client)
            
            prices_received = 0
            for symbol in test_symbols:
                current_price = price_fetcher.get_current_price(symbol)
                if current_price:
                    print(f"   ✅ {symbol}: ${current_price:.4f}")
                    prices_received += 1
                else:
                    print(f"   ❌ {symbol}: No price data")
            
            # Final assessment
            print(f"\n🎯 DEPLOYMENT READINESS ASSESSMENT:")
            
            connection_ready = websocket_manager.is_connected
            data_ready = stats.get('klines_processed', 0) > 0
            prices_ready = prices_received >= 2
            
            if connection_ready and data_ready and prices_ready:
                print("   ✅ READY FOR RENDER DEPLOYMENT")
                print("   ✅ WebSocket system fully operational")
                print("   ✅ Real-time price data flowing")
                print("   ✅ All systems validated")
                
                print(f"\n🚀 DEPLOYMENT INSTRUCTIONS:")
                print("   1. Commit your current code")
                print("   2. Deploy to Render")
                print("   3. Monitor initial connection logs")
                print("   4. Verify WebSocket data reception")
                print("   5. Start trading via dashboard")
                
                return True
            else:
                print("   ⚠️ NEEDS ATTENTION BEFORE DEPLOYMENT")
                if not connection_ready:
                    print("   ❌ WebSocket connection issues")
                if not data_ready:
                    print("   ❌ No market data received")
                if not prices_ready:
                    print("   ❌ Price fetching issues")
                
                return False
                
        else:
            print("   ❌ WebSocket connection failed")
            return False
            
    except Exception as e:
        print(f"❌ Deployment check failed: {e}")
        return False
    
    finally:
        # Cleanup
        if websocket_manager.is_running:
            websocket_manager.stop()

if __name__ == "__main__":
    success = asyncio.run(final_deployment_check())
    sys.exit(0 if success else 1)
