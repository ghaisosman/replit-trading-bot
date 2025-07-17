
#!/usr/bin/env python3
"""
Live Trading Setup Script
This script helps configure the bot for live trading on Binance.
"""

import os
from src.config.global_config import global_config

def main():
    print("🚀 BINANCE TRADING BOT - LIVE TRADING SETUP")
    print("=" * 50)

    # Check current configuration
    print("\n📋 CURRENT CONFIGURATION:")
    print(f"Mode: {'TESTNET' if global_config.BINANCE_TESTNET else 'MAINNET'}")
    print(f"API Key: {'✅ Set' if global_config.BINANCE_API_KEY else '❌ Missing'}")
    print(f"Secret Key: {'✅ Set' if global_config.BINANCE_SECRET_KEY else '❌ Missing'}")
    print(f"Telegram Token: {'✅ Set' if global_config.TELEGRAM_BOT_TOKEN else '❌ Missing'}")
    print(f"Telegram Chat ID: {'✅ Set' if global_config.TELEGRAM_CHAT_ID else '❌ Missing'}")

    print("\n🔧 SETUP OPTIONS:")
    print("1. Configure for TESTNET (Recommended for testing)")
    print("2. Configure for MAINNET (REAL MONEY - Use with caution!)")
    print("3. Test current configuration")
    print("4. Exit")

    choice = input("\nSelect option (1-4): ")

    if choice == "1":
        setup_testnet()
    elif choice == "2":
        setup_mainnet()
    elif choice == "3":
        test_configuration()
    else:
        print("Exiting...")

def setup_testnet():
    print("\n🧪 TESTNET SETUP")
    print("=" * 30)
    print("1. Go to https://testnet.binance.vision/")
    print("2. Create an account (if you don't have one)")
    print("3. Generate API Keys with TRADING permissions")
    print("4. Add these to your Replit Secrets:")
    print("   - BINANCE_API_KEY")
    print("   - BINANCE_SECRET_KEY")
    print("   - BINANCE_TESTNET=true")
    print("\n✅ Testnet is SAFE - no real money involved!")

def setup_mainnet():
    print("\n⚠️  MAINNET SETUP - REAL MONEY AT RISK!")
    print("=" * 40)
    print("Before proceeding, ensure you:")
    print("1. ✅ Tested thoroughly on testnet")
    print("2. ✅ Understand the risks")
    print("3. ✅ Have proper risk management")
    print("4. ✅ Start with small amounts")

    confirm = input("\nType 'I UNDERSTAND THE RISKS' to continue: ")
    if confirm != "I UNDERSTAND THE RISKS":
        print("❌ Setup cancelled for safety")
        return

    print("\n📝 MAINNET CONFIGURATION:")
    print("Add these to your Replit Secrets:")
    print("   - BINANCE_API_KEY (from your real Binance account)")
    print("   - BINANCE_SECRET_KEY (from your real Binance account)")
    print("   - BINANCE_TESTNET=false")
    print("\n🔧 API Key Requirements:")
    print("   - Enable 'Enable Trading' permission")
    print("   - Either disable IP restrictions OR whitelist your IP")
    print("   - Enable futures trading if using futures")

def test_configuration():
    print("\n🧪 TESTING CONFIGURATION...")
    from src.binance_client.client import BinanceClientWrapper

    try:
        client = BinanceClientWrapper()
        if client.test_connection():
            print("✅ API Connection: SUCCESS")

            account = client.get_account_info()
            if account:
                print("✅ Account Access: SUCCESS")
                print("🎉 Configuration is ready for trading!")
            else:
                print("❌ Account Access: FAILED")
                print("🔧 Check API key permissions")
        else:
            print("❌ API Connection: FAILED")
            print("🔧 Check API keys and internet connection")

    except Exception as e:
        print(f"❌ Configuration Error: {e}")

if __name__ == "__main__":
    main()
