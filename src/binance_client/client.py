
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
            self.client = Client(
                api_key=global_config.BINANCE_API_KEY,
                api_secret=global_config.BINANCE_SECRET_KEY,
                testnet=global_config.BINANCE_TESTNET
            )
            self.logger.info("Binance client initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Binance client: {e}")
            raise
    
    def get_account_info(self) -> Optional[Dict[str, Any]]:
        """Get account information"""
        try:
            return self.client.get_account()
        except BinanceAPIException as e:
            self.logger.error(f"Error getting account info: {e}")
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
