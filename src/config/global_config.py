
import os
import json
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

        # Load environment config from file if exists, otherwise use secrets
        self._load_environment_config()

        # Telegram bot credentials
        self.TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
        self.TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

        # Global trading rules
        self.BALANCE_MULTIPLIER = 2.0  # Available balance must be 2x biggest margin
        self.MAX_CONCURRENT_TRADES_PER_STRATEGY = 1  # No multiple trades per strategy

        # Market data settings
        self.PRICE_UPDATE_INTERVAL = 1  # seconds
        self.BALANCE_CHECK_INTERVAL = 30  # seconds

        # Timezone settings for chart alignment
        self.USE_LOCAL_TIMEZONE = os.getenv('USE_LOCAL_TIMEZONE', 'false').lower() == 'true'
        self.TIMEZONE_OFFSET_HOURS = float(os.getenv('TIMEZONE_OFFSET_HOURS', '0'))  # Manual offset if needed

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
            if self.BINANCE_FUTURES:
                print("🧪 FUTURES TESTNET MODE: Safe for testing")
                print("Using Binance Futures testnet endpoints")
            else:
                print("🧪 SPOT TESTNET MODE: Safe for testing")
            return True
        else:
            mode = "FUTURES" if self.BINANCE_FUTURES else "SPOT"
            print(f"⚠️  {mode} MAINNET MODE: REAL MONEY AT RISK!")
            print("Make sure you have:")
            print("1. Valid API keys with trading permissions")
            print("2. IP whitelisting configured (if enabled)")
            print("3. Sufficient balance for trading")
            print("4. Tested strategies thoroughly on testnet")
            return True

    def _load_environment_config(self):
        """Load environment configuration from file or environment variables"""
        config_file = "trading_data/environment_config.json"

        # Try to load from config file first (web dashboard overrides)
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    env_config = json.load(f)

                self.BINANCE_TESTNET = env_config.get('BINANCE_TESTNET', 'true').lower() == 'true'
                self.BINANCE_FUTURES = env_config.get('BINANCE_FUTURES', 'true').lower() == 'true'

                print(f"🔧 Environment loaded from config file: {'TESTNET' if self.BINANCE_TESTNET else 'MAINNET'}")
                return

            except Exception as e:
                print(f"Warning: Could not load environment config file: {e}")

        # Fallback to environment variables - FORCE MAINNET
        self.BINANCE_TESTNET = False  # Always use mainnet
        self.BINANCE_FUTURES = os.getenv('BINANCE_FUTURES', 'true').lower() == 'true'  # Enable futures trading

        print(f"🔧 Environment loaded from secrets: MAINNET (forced)")

# Global config instance
global_config = GlobalConfig()
