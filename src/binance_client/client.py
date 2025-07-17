from binance.client import Client
from binance.exceptions import BinanceAPIException
import logging
from typing import Dict, Any, Optional, List
from src.config.global_config import global_config
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import random

class BinanceClientWrapper:
    """Wrapper for Binance client with error handling (supports both Spot and Futures)"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.client = None
        self.is_futures = global_config.BINANCE_FUTURES
        self._last_request_time = 0
        self._min_request_interval = 0.1  # Minimum 100ms between requests
        self.proxy_session = None
        self.active_proxy = None
        self._setup_proxy_session()
        self._initialize_client()

    def _initialize_client(self):
        """Initialize Binance client for Spot or Futures"""
        try:
            if global_config.BINANCE_TESTNET:
                if self.is_futures:
                    # Use futures testnet
                    self.client = Client(
                        api_key=global_config.BINANCE_API_KEY,
                        api_secret=global_config.BINANCE_SECRET_KEY,
                        testnet=True
                    )
                    # Override base URLs for futures testnet
                    self.client.API_URL = 'https://testnet.binancefuture.com'
                    self.client.FUTURES_URL = 'https://testnet.binancefuture.com'
                    self.logger.info("Binance FUTURES testnet client initialized successfully")
                    self.logger.info(f"Using futures testnet URL: {self.client.FUTURES_URL}")
                else:
                    # Use spot testnet
                    self.client = Client(
                        api_key=global_config.BINANCE_API_KEY,
                        api_secret=global_config.BINANCE_SECRET_KEY,
                        testnet=True
                    )
                    self.logger.info("Binance SPOT testnet client initialized successfully")
                    self.logger.info(f"Using spot testnet URL: {self.client.API_URL}")
            else:
                # Mainnet
                self.client = Client(
                    api_key=global_config.BINANCE_API_KEY,
                    api_secret=global_config.BINANCE_SECRET_KEY,
                    testnet=False
                )
                mode = "FUTURES" if self.is_futures else "SPOT"
                self.logger.info(f"Binance {mode} mainnet client initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize Binance client: {e}")
            raise

    def _setup_proxy_session(self):
        """Setup proxy session for geographic restriction bypass"""
        try:
            # Check if proxy is enabled in deployment
            import os
            is_deployment = os.environ.get('REPLIT_DEPLOYMENT') == '1'
            proxy_enabled = os.getenv('PROXY_ENABLED', 'false').lower() == 'true'
            
            if is_deployment and proxy_enabled:
                proxy_urls = os.getenv('PROXY_URLS', '').split(',')
                proxy_urls = [url.strip() for url in proxy_urls if url.strip()]
                
                if proxy_urls:
                    self.active_proxy = random.choice(proxy_urls)
                    self.proxy_session = requests.Session()
                    
                    # Setup retry strategy
                    retry_strategy = Retry(
                        total=3,
                        backoff_factor=1,
                        status_forcelist=[429, 500, 502, 503, 504],
                    )
                    adapter = HTTPAdapter(max_retries=retry_strategy)
                    self.proxy_session.mount("http://", adapter)
                    self.proxy_session.mount("https://", adapter)
                    
                    # Configure proxy
                    proxies = {
                        'http': self.active_proxy,
                        'https': self.active_proxy
                    }
                    self.proxy_session.proxies.update(proxies)
                    
                    self.logger.info(f"🌍 PROXY ENABLED: Using {self.active_proxy} for geographic bypass")
                    
                    # Test proxy connection
                    if self._test_proxy_connection():
                        self.logger.info("✅ PROXY CONNECTION: Verified and active")
                    else:
                        self.logger.warning("⚠️ PROXY WARNING: Connection test failed, but continuing")
                else:
                    self.logger.warning("⚠️ PROXY_ENABLED=true but no PROXY_URLS configured")
            else:
                self.logger.info("🏠 DEVELOPMENT MODE: Direct connection (no proxy needed)")
                
        except Exception as e:
            self.logger.error(f"Error setting up proxy: {e}")
            self.proxy_session = None

    def _test_proxy_connection(self) -> bool:
        """Test if proxy is working"""
        try:
            if not self.proxy_session:
                return False
                
            # Test with a simple HTTP request
            response = self.proxy_session.get('https://httpbin.org/ip', timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.logger.info(f"🌍 PROXY IP: {data.get('origin', 'Unknown')}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Proxy test failed: {e}")
            return False

    def _rotate_proxy(self):
        """Rotate to next available proxy"""
        try:
            proxy_urls = os.getenv('PROXY_URLS', '').split(',')
            proxy_urls = [url.strip() for url in proxy_urls if url.strip()]
            
            if len(proxy_urls) > 1:
                # Remove current proxy and pick a new one
                available_proxies = [p for p in proxy_urls if p != self.active_proxy]
                if available_proxies:
                    self.active_proxy = random.choice(available_proxies)
                    proxies = {
                        'http': self.active_proxy,
                        'https': self.active_proxy
                    }
                    self.proxy_session.proxies.update(proxies)
                    self.logger.info(f"🔄 PROXY ROTATED: Now using {self.active_proxy}")
                    return True
            return False
        except Exception as e:
            self.logger.error(f"Error rotating proxy: {e}")
            return False

    def _rate_limit(self):
        """Simple rate limiting to prevent API spam"""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        if time_since_last < self._min_request_interval:
            time.sleep(self._min_request_interval - time_since_last)
        self._last_request_time = time.time()

    def test_connection(self) -> bool:
        """Test API connection with improved error handling"""
        try:
            self._rate_limit()
            if self.is_futures:
                # Test futures connection
                self.client.futures_ping()
                env = "FUTURES TESTNET" if global_config.BINANCE_TESTNET else "FUTURES MAINNET"
                url = self.client.FUTURES_URL if global_config.BINANCE_TESTNET else "https://fapi.binance.com"
            else:
                # Test spot connection
                self.client.ping()
                env = "SPOT TESTNET" if global_config.BINANCE_TESTNET else "SPOT MAINNET"
                url = self.client.API_URL

            self.logger.info(f"✅ Connected to {env}: {url}")
            self.logger.info("✅ Binance API connection test successful")
            return True

        except BinanceAPIException as e:
            self.logger.error(f"❌ Binance API connection test failed: {e}")
            
            # Check if this is a deployment environment with geo-restrictions
            import os
            is_deployment = os.environ.get('REPLIT_DEPLOYMENT') == '1'
            
            if is_deployment and not global_config.BINANCE_TESTNET:
                proxy_enabled = os.getenv('PROXY_ENABLED', 'false').lower() == 'true'
                if proxy_enabled and self.proxy_session:
                    self.logger.info("🔄 PROXY RETRY: Attempting connection through proxy...")
                    # Try rotating proxy and retry
                    if self._rotate_proxy():
                        return self.test_connection()  # Recursive retry with new proxy
                    else:
                        self.logger.error("🚨 ALL PROXIES FAILED: No working proxies available")
                else:
                    self.logger.error("🚨 DEPLOYMENT GEOGRAPHICAL RESTRICTION DETECTED")
                    self.logger.error("⚠️  Binance mainnet is blocked from Replit's deployment servers")
                    self.logger.error("🔧 SOLUTION: Set PROXY_ENABLED=true and PROXY_URLS in Secrets")
                    self.logger.error("💡 Example: PROXY_URLS=http://proxy1:8080,socks5://proxy2:1080")
                    self.logger.error("🌐 Web dashboard will remain active for monitoring")
                return False
            
            if e.code == -2015:
                if global_config.BINANCE_TESTNET:
                    if self.is_futures:
                        self.logger.error("❌ API Key invalid for FUTURES testnet. Common issues:")
                        self.logger.error("1. Keys are from SPOT testnet (testnet.binance.vision)")
                        self.logger.error("   → This bot needs FUTURES testnet keys from https://testnet.binancefuture.com/")
                        self.logger.error("2. Keys don't have futures trading permissions")
                        self.logger.error("3. Keys are expired or invalid")
                        self.logger.error("")
                        self.logger.error("🔧 SOLUTION: Get new FUTURES testnet API keys:")
                        self.logger.error("   • Go to https://testnet.binancefuture.com/")
                        self.logger.error("   • Create API Key with futures trading permissions")
                        self.logger.error("   • Update your Replit Secrets")
                    else:
                        self.logger.error("❌ API Key invalid for SPOT testnet. Get keys from https://testnet.binance.vision/")
                else:
                    self.logger.error("API Key invalid or IP not whitelisted for mainnet")
            return False
        except Exception as e:
            self.logger.error(f"❌ Connection test failed: {e}")
            
            # Check if this is a deployment environment
            import os
            is_deployment = os.environ.get('REPLIT_DEPLOYMENT') == '1'
            
            if is_deployment and not global_config.BINANCE_TESTNET:
                self.logger.error("🚨 DEPLOYMENT CONNECTION ISSUE")
                self.logger.error("⚠️  Unable to connect to Binance mainnet from deployment environment")
                self.logger.error("🌍 This is due to geographical restrictions on Replit's servers")
                self.logger.error("🔄 NEXT STEP: Implement proxy solution from Instructions.md")
                self.logger.error("🌐 Web dashboard will remain active for monitoring")
                
            return False

    def validate_api_permissions(self) -> Dict[str, bool]:
        """Validate API key permissions for trading with improved error handling"""
        permissions = {
            'ping': False,
            'account_access': False,
            'trading': False,
            'market_data': False
        }

        try:
            self._rate_limit()
            if self.is_futures:
                # Test futures permissions
                self.client.futures_ping()
                permissions['ping'] = True
                self.logger.info("✅ API PING SUCCESSFUL")

                # Test futures market data
                ticker = self.client.futures_symbol_ticker(symbol='BTCUSDT')
                if ticker:
                    permissions['market_data'] = True
                    self.logger.info("✅ MARKET DATA ACCESS GRANTED")

                # Test futures account access
                account = self.client.futures_account()
                if account:
                    permissions['account_access'] = True
                    permissions['trading'] = True  # Futures account access implies trading
                    self.logger.info("✅ ACCOUNT ACCESS VERIFIED")
                    self.logger.info("✅ TRADING PERMISSIONS ACTIVE")
            else:
                # Test spot permissions (existing code)
                self.client.ping()
                permissions['ping'] = True
                self.logger.info("✅ API Ping: SUCCESS")

                ticker = self.client.get_symbol_ticker(symbol='BTCUSDT')
                if ticker:
                    permissions['market_data'] = True
                    self.logger.info("✅ Market Data: SUCCESS")

                account = self.client.get_account()
                if account:
                    permissions['account_access'] = True
                    self.logger.info("✅ Account Access: SUCCESS")

                    if account.get('canTrade', False):
                        permissions['trading'] = True
                        self.logger.info("✅ Trading Permission: SUCCESS")
                    else:
                        self.logger.error("❌ Trading Permission: DISABLED")

        except BinanceAPIException as e:
            if e.code == -2015:
                self.logger.error("❌ API Key Permission Error")
                if global_config.BINANCE_TESTNET:
                    env = "FUTURES" if self.is_futures else "SPOT"
                    url = "https://testnet.binancefuture.com/" if self.is_futures else "https://testnet.binance.vision/"
                    self.logger.error(f"🔧 Create new {env} testnet API keys at {url}")
                else:
                    self.logger.error("🔧 Check your mainnet API key permissions")
            else:
                self.logger.error(f"❌ API Error: {e}")
        except Exception as e:
            self.logger.error(f"❌ Validation Error: {e}")

        return permissions

    def get_account_info(self) -> Optional[Dict[str, Any]]:
        """Get account information with rate limiting"""
        try:
            self._rate_limit()
            if self.is_futures:
                return self.client.futures_account()
            else:
                return self.client.get_account()
        except BinanceAPIException as e:
            if e.code == -2015:
                if global_config.BINANCE_TESTNET:
                    env = "FUTURES" if self.is_futures else "SPOT"
                    opposite_env = "SPOT" if self.is_futures else "FUTURES"
                    url = "https://testnet.binancefuture.com/" if self.is_futures else "https://testnet.binance.vision/"
                    opposite_url = "https://testnet.binance.vision/" if self.is_futures else "https://testnet.binancefuture.com/"

                    self.logger.error(f"❌ {env} TESTNET API PERMISSION ERROR")
                    self.logger.error(f"🔧 SOLUTION: You likely have {opposite_env} testnet keys, but need {env} testnet keys:")
                    self.logger.error(f"   1. Go to {url} (NOT {opposite_url})")
                    self.logger.error("   2. API Management → Create API Key")
                    self.logger.error(f"   3. Enable: Reading + {env} Trading")
                    self.logger.error("   4. Disable IP restrictions for testing")
                    self.logger.error(f"   5. Update your Replit Secrets with new {env} testnet keys")
                    self.logger.error("")
                    self.logger.error(f"ℹ️  Current keys appear to be from {opposite_env} testnet (different endpoint)")
                else:
                    self.logger.error("❌ MAINNET API Keys invalid or IP not whitelisted")
            else:
                self.logger.error(f"Error getting account info: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error getting account info: {e}")
            return None

    def get_symbol_ticker(self, symbol: str) -> Optional[Dict]:
        """Get ticker information for a symbol"""
        try:
            if self.is_futures:
                return self.client.futures_symbol_ticker(symbol=symbol)
            else:
                return self.client.get_symbol_ticker(symbol=symbol)
        except Exception as e:
            self.logger.error(f"Error getting ticker for {symbol}: {e}")
            return None

    def get_klines(self, symbol: str, interval: str, limit: int = 500) -> Optional[List]:
        """Get kline/candlestick data for a symbol"""
        try:
            if self.is_futures:
                return self.client.futures_klines(symbol=symbol, interval=interval, limit=limit)
            else:
                return self.client.get_klines(symbol=symbol, interval=interval, limit=limit)
        except Exception as e:
            self.logger.error(f"Error getting klines for {symbol}: {e}")
            return None

    def get_historical_klines(self, symbol: str, interval: str, limit: int = 100) -> Optional[list]:
        """Get historical klines with rate limiting"""
        try:
            self._rate_limit()
            if self.is_futures:
                return self.client.futures_klines(symbol=symbol, interval=interval, limit=limit)
            else:
                return self.client.get_historical_klines(symbol, interval, limit=limit)
        except BinanceAPIException as e:
            self.logger.error(f"Error getting klines for {symbol}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error getting klines for {symbol}: {e}")
            return None

    def create_order(self, **kwargs) -> Optional[Dict[str, Any]]:
        """Create an order with rate limiting"""
        try:
            self._rate_limit()
            if self.is_futures:
                return self.client.futures_create_order(**kwargs)
            else:
                return self.client.create_order(**kwargs)
        except BinanceAPIException as e:
            self.logger.error(f"Error creating order: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error creating order: {e}")
            return None

    def get_open_orders(self, symbol: str = None) -> Optional[list]:
        """Get open orders with rate limiting"""
        try:
            self._rate_limit()
            if self.is_futures:
                return self.client.futures_get_open_orders(symbol=symbol)
            else:
                return self.client.get_open_orders(symbol=symbol)
        except BinanceAPIException as e:
            self.logger.error(f"Error getting open orders: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error getting open orders: {e}")
            return None

    def cancel_order(self, symbol: str, order_id: int) -> Optional[Dict[str, Any]]:
        """Cancel an order with rate limiting"""
        try:
            self._rate_limit()
            if self.is_futures:
                return self.client.futures_cancel_order(symbol=symbol, orderId=order_id)
            else:
                return self.client.cancel_order(symbol=symbol, orderId=order_id)
        except BinanceAPIException as e:
            self.logger.error(f"Error canceling order: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error canceling order: {e}")
            return None

    def set_leverage(self, symbol: str, leverage: int) -> Optional[Dict[str, Any]]:
        """Set leverage for futures trading with rate limiting"""
        try:
            self._rate_limit()
            if self.is_futures:
                return self.client.futures_change_leverage(symbol=symbol, leverage=leverage)
            else:
                self.logger.warning("Leverage setting not available for spot trading")
                return None
        except BinanceAPIException as e:
            self.logger.error(f"Error setting leverage {leverage}x for {symbol}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error setting leverage for {symbol}: {e}")
            return None

    def set_margin_type(self, symbol: str, margin_type: str = "CROSSED") -> Optional[Dict[str, Any]]:
        """Set margin type for futures trading with rate limiting"""
        try:
            self._rate_limit()
            if self.is_futures:
                return self.client.futures_change_margin_type(symbol=symbol, marginType=margin_type)
            else:
                self.logger.warning("Margin type setting not available for spot trading")
                return None
        except BinanceAPIException as e:
            # Error -4046 means margin type is already set to the requested type
            if e.code == -4046:
                self.logger.info(f"Margin type for {symbol} already set to {margin_type}")
                return {"msg": f"Margin type already {margin_type}"}
            else:
                self.logger.error(f"Error setting margin type {margin_type} for {symbol}: {e}")
                return None
        except Exception as e:
            self.logger.error(f"Unexpected error setting margin type for {symbol}: {e}")
            return None