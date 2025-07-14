import pandas as pd
import numpy as np
import ta
from typing import Dict, List, Optional
import logging
from src.binance_client.client import BinanceClientWrapper

class PriceFetcher:
    """Fetches and processes price data"""

    def __init__(self, binance_client: BinanceClientWrapper):
        self.binance_client = binance_client
        self.logger = logging.getLogger(__name__)
        self.price_cache = {}

    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for symbol"""
        ticker = self.binance_client.get_symbol_ticker(symbol)
        if ticker:
            price = float(ticker['price'])
            self.price_cache[symbol] = price
            return price
        return None

    def get_ohlcv_data(self, symbol: str, interval: str, limit: int = 100) -> Optional[pd.DataFrame]:
        """Get OHLCV data as DataFrame"""
        try:
            klines = self.binance_client.get_historical_klines(symbol, interval, limit)
            if not klines:
                return None

            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])

            # Convert to proper data types
            numeric_columns = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_columns:
                df[col] = pd.to_numeric(df[col])

            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

            return df[['open', 'high', 'low', 'close', 'volume']]

        except Exception as e:
            self.logger.error(f"Error getting OHLCV data for {symbol}: {e}")
            return None

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators"""
        try:
            # Moving Averages
            df['sma_20'] = ta.trend.sma_indicator(df['close'], window=20)
            df['sma_50'] = ta.trend.sma_indicator(df['close'], window=50)
            df['ema_12'] = ta.trend.ema_indicator(df['close'], window=12)
            df['ema_26'] = ta.trend.ema_indicator(df['close'], window=26)

            # MACD
            df['macd'] = ta.trend.macd_diff(df['close'])
            df['macd_signal'] = ta.trend.macd_signal(df['close'])

            # RSI
            df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()

            # MACD
            macd_indicator = ta.trend.MACD(df['close'], window_fast=12, window_slow=26, window_sign=9)
            df['macd'] = macd_indicator.macd()
            df['macd_signal'] = macd_indicator.macd_signal()
            df['macd_histogram'] = macd_indicator.macd_diff()

            return df

        except Exception as e:
            self.logger.error(f"Error calculating indicators: {e}")
            return df