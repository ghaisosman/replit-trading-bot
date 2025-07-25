
import logging
from typing import Dict, Optional
from src.binance_client.client import BinanceClientWrapper

class BalanceFetcher:
    """Fetches account balance and position information"""

    def __init__(self, binance_client: BinanceClientWrapper):
        self.binance_client = binance_client
        self.logger = logging.getLogger(__name__)

    def get_account_balance(self) -> Optional[Dict[str, float]]:
        """Get account balances"""
        try:
            account_info = self.binance_client.get_account_info()
            if not account_info:
                return None

            balances = {}

            if self.binance_client.is_futures:
                # Futures account structure
                for balance in account_info['assets']:
                    asset = balance['asset']
                    free = float(balance['availableBalance'])
                    locked = float(balance['initialMargin']) + float(balance['maintMargin'])
                    total = free + locked

                    if total > 0:  # Only include assets with balance
                        balances[asset] = {
                            'free': free,
                            'locked': locked,
                            'total': total
                        }
            else:
                # Spot account structure
                for balance in account_info['balances']:
                    asset = balance['asset']
                    free = float(balance['free'])
                    locked = float(balance['locked'])
                    total = free + locked

                    if total > 0:  # Only include assets with balance
                        balances[asset] = {
                            'free': free,
                            'locked': locked,
                            'total': total
                        }

            return balances

        except Exception as e:
            self.logger.error(f"Error getting account balance: {e}")
            return None

    def get_usdt_balance(self) -> float:
        """Get available USDT balance"""
        try:
            balances = self.get_account_balance()
            if balances and 'USDT' in balances:
                return float(balances['USDT']['free'])

            # For testnet, if no USDT balance, return a mock balance
            from src.config.global_config import global_config
            if global_config.BINANCE_TESTNET:
                self.logger.warning("No USDT balance found in testnet. Using mock balance for testing.")
                return 1000.0  # Mock testnet balance
            else:
                self.logger.error("No USDT balance found in mainnet account!")
                return 0.0
        except Exception as e:
            self.logger.error(f"Error getting USDT balance: {e}")
            # Return safe fallback value
            from src.config.global_config import global_config
            return 1000.0 if global_config.BINANCE_TESTNET else 0.0

    def check_sufficient_balance(self, required_margin: float, balance_multiplier: float = 2.0) -> bool:
        """Check if there's sufficient balance for trading"""
        usdt_balance = self.get_usdt_balance()
        if usdt_balance is None:
            return False

        required_balance = required_margin * balance_multiplier
        return usdt_balance >= required_balance
