
import os
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class GlobalConfig:
    """Global configuration for the trading bot"""
    
    def __init__(self):
        # Binance API credentials from secrets
        self.BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
        self.BINANCE_SECRET_KEY = os.getenv('BINANCE_SECRET_KEY')
        self.BINANCE_TESTNET = os.getenv('BINANCE_TESTNET', 'true').lower() == 'true'  # Default to testnet
        
        # Telegram bot credentials
        self.TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
        self.TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
        
        # Global trading rules
        self.BALANCE_MULTIPLIER = 2.0  # Available balance must be 2x biggest margin
        self.MAX_CONCURRENT_TRADES_PER_STRATEGY = 1  # No multiple trades per strategy
        
        # Market data settings
        self.PRICE_UPDATE_INTERVAL = 1  # seconds
        self.BALANCE_CHECK_INTERVAL = 30  # seconds
        
    def validate_config(self) -> bool:
        """Validate that all required config is present"""
        required_vars = [
            'BINANCE_API_KEY', 
            'BINANCE_SECRET_KEY'
        ]
        
        # Telegram is optional for basic trading
        optional_vars = ['TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID']
        
        for var in required_vars:
            if not getattr(self, var):
                print(f"Missing required environment variable: {var}")
                return False
        
        # Warn about missing optional vars
        for var in optional_vars:
            if not getattr(self, var):
                print(f"Warning: Missing optional environment variable: {var} (Telegram reporting disabled)")
        
        return True
    
    def is_live_trading_ready(self) -> bool:
        """Check if configuration is ready for live trading"""
        if self.BINANCE_TESTNET:
            print("🧪 TESTNET MODE: Safe for testing")
            return True
        else:
            print("⚠️  MAINNET MODE: REAL MONEY AT RISK!")
            print("Make sure you have:")
            print("1. Valid API keys with trading permissions")
            print("2. IP whitelisting configured (if enabled)")
            print("3. Sufficient balance for trading")
            print("4. Tested strategies thoroughly on testnet")
            return True

# Global config instance
global_config = GlobalConfig()
