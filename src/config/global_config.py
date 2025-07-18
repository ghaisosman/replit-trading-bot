
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

        # ExpressVPN proxy configuration for geographic restriction bypass
        self.PROXY_ENABLED = os.getenv('PROXY_ENABLED', 'false').lower() == 'true'
        self.EXPRESSVPN_ENABLED = os.getenv('EXPRESSVPN_ENABLED', 'false').lower() == 'true'
        
        # ExpressVPN SOCKS5 proxy settings (default ExpressVPN SOCKS5 endpoints)
        self.EXPRESSVPN_SOCKS5_HOST = os.getenv('EXPRESSVPN_SOCKS5_HOST', 'socks5-us-newyork-1.expressnetw.com')
        self.EXPRESSVPN_SOCKS5_PORT = int(os.getenv('EXPRESSVPN_SOCKS5_PORT', '1080'))
        self.EXPRESSVPN_USERNAME = os.getenv('EXPRESSVPN_USERNAME')
        self.EXPRESSVPN_PASSWORD = os.getenv('EXPRESSVPN_PASSWORD')
        
        # Fallback to generic proxy configuration
        self.PROXY_URLS = os.getenv('PROXY_URLS', '').split(',') if os.getenv('PROXY_URLS') else []
        self.PROXY_USERNAME = os.getenv('PROXY_USERNAME')
        self.PROXY_PASSWORD = os.getenv('PROXY_PASSWORD')
        self.PROXY_ROTATION_INTERVAL = int(os.getenv('PROXY_ROTATION_INTERVAL', '300'))  # 5 minutes
        self.PROXY_MAX_RETRIES = int(os.getenv('PROXY_MAX_RETRIES', '3'))
        
        # Auto-enable proxy if ExpressVPN is configured
        if self.EXPRESSVPN_ENABLED and self.EXPRESSVPN_USERNAME and self.EXPRESSVPN_PASSWORD:
            self.PROXY_ENABLED = True

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

        # Validate proxy configuration if enabled
        if self.PROXY_ENABLED:
            if self.EXPRESSVPN_ENABLED:
                # Validate ExpressVPN configuration
                if not self.EXPRESSVPN_USERNAME or not self.EXPRESSVPN_PASSWORD:
                    print("Warning: ExpressVPN enabled but missing credentials")
                    self.PROXY_ENABLED = False
                    self.EXPRESSVPN_ENABLED = False
                else:
                    print(f"✅ ExpressVPN proxy configured: {self.EXPRESSVPN_SOCKS5_HOST}:{self.EXPRESSVPN_SOCKS5_PORT}")
            elif not self.PROXY_URLS or not any(self.PROXY_URLS):
                print("Warning: PROXY_ENABLED=true but no PROXY_URLS or ExpressVPN provided")
                self.PROXY_ENABLED = False
            else:
                # Validate proxy URLs format
                valid_proxies = []
                for proxy_url in self.PROXY_URLS:
                    proxy_url = proxy_url.strip()
                    if proxy_url and ('http://' in proxy_url or 'https://' in proxy_url or 'socks5://' in proxy_url):
                        valid_proxies.append(proxy_url)
                
                if not valid_proxies:
                    print("Warning: No valid proxy URLs found, disabling proxy")
                    self.PROXY_ENABLED = False
                else:
                    self.PROXY_URLS = valid_proxies
                    print(f"✅ Proxy configuration validated: {len(valid_proxies)} proxies")

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

                self.BINANCE_TESTNET = env_config.get('BINANCE_TESTNET', 'false').lower() == 'true'
                self.BINANCE_FUTURES = env_config.get('BINANCE_FUTURES', 'true').lower() == 'true'

                print(f"🔧 Environment loaded from config file: {'TESTNET' if self.BINANCE_TESTNET else 'MAINNET'}")
                return

            except Exception as e:
                print(f"Warning: Could not load environment config file: {e}")

        # Force mainnet for all environments (no more testnet switching)
        self.BINANCE_TESTNET = False
        self.BINANCE_FUTURES = os.getenv('BINANCE_FUTURES', 'true').lower() == 'true'
        
        # Check if proxy should be enabled for geographic restrictions
        is_deployment = os.environ.get('REPLIT_DEPLOYMENT') == '1'
        if is_deployment and not self.PROXY_ENABLED:
            print("🚨 DEPLOYMENT MODE: Consider enabling proxy to bypass geographic restrictions")
            print("   Set EXPRESSVPN_ENABLED=true and ExpressVPN credentials in your Replit Secrets")
        
        proxy_status = 'disabled'
        if self.PROXY_ENABLED:
            if self.EXPRESSVPN_ENABLED:
                proxy_status = 'ExpressVPN'
            else:
                proxy_status = 'custom proxy'
        
        print(f"🔧 Environment loaded: MAINNET (proxy: {proxy_status})")

# Global config instance
global_config = GlobalConfig()
