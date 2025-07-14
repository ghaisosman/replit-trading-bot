
#!/usr/bin/env python3
"""
Quick API Test Script
Run this to validate your testnet API setup
"""

import asyncio
import logging
from src.utils.logger import setup_logger
from src.binance_client.client import BinanceClientWrapper
from src.config.global_config import global_config

async def test_api():
    setup_logger()
    logger = logging.getLogger(__name__)
    
    print("🧪 TESTING BINANCE TESTNET API")
    print("=" * 40)
    print(f"Mode: {'TESTNET' if global_config.BINANCE_TESTNET else 'MAINNET'}")
    print(f"API Key: {'✅ Set' if global_config.BINANCE_API_KEY else '❌ Missing'}")
    print(f"Secret: {'✅ Set' if global_config.BINANCE_SECRET_KEY else '❌ Missing'}")
    print()
    
    if not global_config.BINANCE_API_KEY or not global_config.BINANCE_SECRET_KEY:
        print("❌ Missing API credentials. Check your Replit Secrets.")
        return
    
    try:
        client = BinanceClientWrapper()
        
        # Test connection
        print("🔍 Testing connection...")
        if client.test_connection():
            print("✅ Connection successful")
        else:
            print("❌ Connection failed")
            return
        
        # Validate permissions
        print("\n🔍 Validating permissions...")
        permissions = client.validate_api_permissions()
        
        print("\n📊 PERMISSION SUMMARY:")
        for perm, status in permissions.items():
            status_icon = "✅" if status else "❌"
            print(f"{status_icon} {perm.replace('_', ' ').title()}: {status}")
        
        if all(permissions.values()):
            print("\n🎉 ALL TESTS PASSED! Your API is ready for trading.")
        else:
            print("\n⚠️  Some permissions missing. Check the logs above.")
            
    except Exception as e:
        logger.error(f"Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_api())
