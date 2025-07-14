
from binance.client import Client
from binance.exceptions import BinanceAPIException
import logging
from typing import Dict, Any, Optional
from src.config.global_config import global_config

class BinanceClientWrapper:
    """Wrapper for Binance client with error handling"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Binance client"""
        try:
            if global_config.BINANCE_TESTNET:
                # Use testnet URLs
                self.client = Client(
                    api_key=global_config.BINANCE_API_KEY,
                    api_secret=global_config.BINANCE_SECRET_KEY,
                    testnet=True,
                    tld='com'
                )
                self.logger.info("Binance testnet client initialized successfully")
            else:
                self.client = Client(
                    api_key=global_config.BINANCE_API_KEY,
                    api_secret=global_config.BINANCE_SECRET_KEY,
                    testnet=False
                )
                self.logger.info("Binance mainnet client initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Binance client: {e}")
            raise
    
    def test_connection(self) -> bool:
        """Test API connection"""
        try:
            # Test with a simple ping first
            self.client.ping()
            self.logger.info("Binance API connection test successful")
            return True
        except BinanceAPIException as e:
            self.logger.error(f"Binance API connection test failed: {e}")
            if e.code == -2015:
                self.logger.error("API Key invalid or IP not whitelisted. Check your testnet API keys.")
            return False
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False

    def get_account_info(self) -> Optional[Dict[str, Any]]:
        """Get account information"""
        try:
            return self.client.get_account()
        except BinanceAPIException as e:
            self.logger.error(f"Error getting account info: {e}")
            if e.code == -2015:
                if global_config.BINANCE_TESTNET:
                    self.logger.error("❌ TESTNET API Keys need TRADING permissions. Get new keys from https://testnet.binance.vision/")
                else:
                    self.logger.error("❌ MAINNET API Keys invalid or IP not whitelisted. Check your Binance account settings.")
                    self.logger.error("🔧 Solutions:")
                    self.logger.error("   1. Enable trading permissions for API keys")
                    self.logger.error("   2. Disable IP restrictions OR whitelist your IP")
                    self.logger.error("   3. Verify API keys are correct")
            return None
    
    def get_symbol_ticker(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get current price for symbol"""
        try:
            return self.client.get_symbol_ticker(symbol=symbol)
        except BinanceAPIException as e:
            self.logger.error(f"Error getting ticker for {symbol}: {e}")
            return None
    
    def get_historical_klines(self, symbol: str, interval: str, limit: int = 100) -> Optional[list]:
        """Get historical klines"""
        try:
            return self.client.get_historical_klines(symbol, interval, limit=limit)
        except BinanceAPIException as e:
            self.logger.error(f"Error getting klines for {symbol}: {e}")
            return None
    
    def create_order(self, **kwargs) -> Optional[Dict[str, Any]]:
        """Create an order"""
        try:
            return self.client.create_order(**kwargs)
        except BinanceAPIException as e:
            self.logger.error(f"Error creating order: {e}")
            return None
    
    def get_open_orders(self, symbol: str = None) -> Optional[list]:
        """Get open orders"""
        try:
            return self.client.get_open_orders(symbol=symbol)
        except BinanceAPIException as e:
            self.logger.error(f"Error getting open orders: {e}")
            return None
    
    def cancel_order(self, symbol: str, order_id: int) -> Optional[Dict[str, Any]]:
        """Cancel an order"""
        try:
            return self.client.cancel_order(symbol=symbol, orderId=order_id)
        except BinanceAPIException as e:
            self.logger.error(f"Error canceling order: {e}")
            return None
