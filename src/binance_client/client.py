import requests
import logging
from typing import Dict, Any, Optional

class BinanceClientWrapper:
    """Simplified Binance API client wrapper"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.base_url = "https://testnet.binance.vision"  # Default to testnet
        self.api_key = None
        self.secret_key = None
        self.logger.info("🔗 Binance Client Wrapper initialized")
    
    def set_credentials(self, api_key: str, secret_key: str):
        """Set API credentials"""
        self.api_key = api_key
        self.secret_key = secret_key
        self.logger.info("🔑 API credentials set")
    
    def test_connection(self) -> bool:
        """Test connection to Binance API"""
        try:
            response = requests.get(f"{self.base_url}/api/v3/ping", timeout=10)
            if response.status_code == 200:
                self.logger.info("✅ Binance connection test successful")
                return True
            else:
                self.logger.error(f"❌ Binance connection test failed: {response.status_code}")
                return False
        except Exception as e:
            self.logger.error(f"❌ Binance connection test error: {e}")
            return False
    
    def get_account_info(self) -> Optional[Dict[str, Any]]:
        """Get account information"""
        try:
            # Simplified account info for testing
            return {
                "makerCommission": 15,
                "takerCommission": 15,
                "buyerCommission": 0,
                "sellerCommission": 0,
                "canTrade": True,
                "canWithdraw": True,
                "canDeposit": True,
                "updateTime": 0,
                "accountType": "SPOT",
                "balances": []
            }
        except Exception as e:
            self.logger.error(f"❌ Error getting account info: {e}")
            return None
    
    def get_balance(self, symbol: str = "USDT") -> Optional[float]:
        """Get balance for a specific symbol"""
        try:
            # Simplified balance for testing
            return 1000.0
        except Exception as e:
            self.logger.error(f"❌ Error getting balance for {symbol}: {e}")
            return None
    
    def get_price(self, symbol: str) -> Optional[float]:
        """Get current price for a symbol"""
        try:
            # Simplified price for testing
            return 50000.0 if "BTC" in symbol else 3000.0
        except Exception as e:
            self.logger.error(f"❌ Error getting price for {symbol}: {e}")
            return None