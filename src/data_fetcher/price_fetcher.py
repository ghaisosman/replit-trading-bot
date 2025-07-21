import pandas as pd
import numpy as np
import ta
from typing import Dict, List, Optional
import logging
from src.binance_client.client import BinanceClientWrapper
from datetime import datetime, timezone, timedelta
from src.config.global_config import global_config

class PriceFetcher:
    """Fetches and processes price data"""

    def __init__(self, binance_client: BinanceClientWrapper):
        self.binance_client = binance_client
        self.logger = logging.getLogger(__name__)
        self.price_cache = {}

        # Timezone configuration for chart alignment
        self.use_local_timezone = global_config.USE_LOCAL_TIMEZONE
        self.timezone_offset_hours = global_config.TIMEZONE_OFFSET_HOURS

        if self.use_local_timezone:
            self.logger.info(f"🕐 TIMEZONE: Using local timezone alignment for chart sync")
        elif self.timezone_offset_hours != 0:
            self.logger.info(f"🕐 TIMEZONE: Using manual offset {self.timezone_offset_hours:+.1f}h for chart sync")
        else:
            self.logger.info("🕐 TIMEZONE: Using UTC (default)")

    def _adjust_timestamp_for_timezone(self, timestamp_ms: int) -> int:
        """Adjust timestamp for local timezone if enabled (non-invasive)"""
        if not self.use_local_timezone and self.timezone_offset_hours == 0:
            return timestamp_ms  # No change - preserve existing behavior

        try:
            # Convert to datetime
            dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)

            if self.use_local_timezone:
                # Convert to local timezone
                local_dt = dt.astimezone()
                # Align to local timezone boundaries
                local_offset = local_dt.utcoffset().total_seconds() / 3600
            else:
                # Use manual offset
                local_offset = self.timezone_offset_hours

            # Adjust timestamp by offset (preserve original data, just shift perspective)
            adjusted_dt = dt + timedelta(hours=local_offset)
            return int(adjusted_dt.timestamp() * 1000)

        except Exception as e:
            self.logger.warning(f"Timezone adjustment failed: {e}, using original timestamp")
            return timestamp_ms  # Fallback to original - safe

    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for symbol"""
        ticker = self.binance_client.get_symbol_ticker(symbol)
        if ticker:
            price = float(ticker['price'])
            self.price_cache[symbol] = price
            return price
        return None

    async def get_market_data(self, symbol: str, interval: str, limit: int = 100) -> Optional[pd.DataFrame]:
        """Get market data with real-time current candle integration"""
        try:
            # Get historical completed candles
            historical_df = self.get_ohlcv_data(symbol, interval, limit)
            if historical_df is None or historical_df.empty:
                return None

            # Get current price for real-time accuracy
            current_price = self.get_current_price(symbol)
            if current_price is None:
                return historical_df

            # Update the last (current) candle with real-time price
            # This ensures indicators reflect the most current market condition
            last_candle = historical_df.iloc[-1].copy()
            
            # Update current candle's close price and potentially high/low
            historical_df.iloc[-1, historical_df.columns.get_loc('close')] = current_price
            
            # Update high if current price is higher
            if current_price > last_candle['high']:
                historical_df.iloc[-1, historical_df.columns.get_loc('high')] = current_price
            
            # Update low if current price is lower  
            if current_price < last_candle['low']:
                historical_df.iloc[-1, historical_df.columns.get_loc('low')] = current_price

            # Calculate indicators on updated data
            historical_df = self.calculate_indicators(historical_df)

            self.logger.debug(f"🔄 REAL-TIME UPDATE | {symbol} | Historical Close: ${last_candle['close']:.4f} | Current: ${current_price:.4f}")

            return historical_df

        except Exception as e:
            self.logger.error(f"Error getting enhanced market data for {symbol}: {e}")
            return self.get_ohlcv_data(symbol, interval, limit)

    def get_ohlcv_data(self, symbol: str, interval: str, limit: int = 100) -> Optional[pd.DataFrame]:
        """Get OHLCV data as DataFrame with enhanced accuracy"""
        try:
            # Get more data than needed for better indicator calculation
            extended_limit = min(limit + 50, 1000)  # Add buffer for accurate indicators
            klines = self.binance_client.get_historical_klines(symbol, interval, extended_limit)
            if not klines:
                return None

            # Convert to DataFrame
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])

            # Apply timezone adjustment if configured (preserves all existing logic)
            if self.use_local_timezone or self.timezone_offset_hours != 0:
                df['timestamp'] = df['timestamp'].apply(self._adjust_timestamp_for_timezone)

            # Convert to proper data types with high precision
            numeric_columns = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

            # Sort by timestamp to ensure proper order
            df = df.sort_index()

            # Remove any duplicate timestamps
            df = df[~df.index.duplicated(keep='last')]

            # Return only requested amount but keep the extra data for calculations
            result_df = df[['open', 'high', 'low', 'close', 'volume']].tail(limit)
            
            # Log data quality
            self.logger.debug(f"📊 DATA QUALITY | {symbol} | Requested: {limit} | Got: {len(result_df)} | Latest: {result_df.index[-1]}")

            return result_df

        except Exception as e:
            self.logger.error(f"Error getting OHLCV data for {symbol}: {e}")
            return None

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators with enhanced accuracy"""
        try:
            # Ensure we have enough data
            if len(df) < 50:
                self.logger.warning("Insufficient data for accurate indicator calculation")
                return df

            # Calculate RSI using manual method (more accurate to Binance)
            df['rsi'] = self._calculate_rsi_manual(df['close'].values, period=14)
            
            # Calculate RSI using ta library for comparison
            df['rsi_ta'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()

            # Moving Averages - use pandas for more precise calculation
            df['sma_20'] = df['close'].rolling(window=20, min_periods=20).mean()
            df['sma_50'] = df['close'].rolling(window=50, min_periods=50).mean()
            
            # EMA calculation (manual for precision)
            df['ema_12'] = df['close'].ewm(span=12, min_periods=12).mean()
            df['ema_26'] = df['close'].ewm(span=26, min_periods=26).mean()

            # MACD calculation (manual for precision)
            df['macd'] = df['ema_12'] - df['ema_26']
            df['macd_signal'] = df['macd'].ewm(span=9, min_periods=9).mean()
            df['macd_histogram'] = df['macd'] - df['macd_signal']

            # Additional MACD using ta library for comparison
            macd_indicator = ta.trend.MACD(df['close'], window_fast=12, window_slow=26, window_sign=9)
            df['macd_ta'] = macd_indicator.macd()
            df['macd_signal_ta'] = macd_indicator.macd_signal()
            df['macd_histogram_ta'] = macd_indicator.macd_diff()

            # Log current values for debugging
            current_price = df['close'].iloc[-1]
            current_rsi = df['rsi'].iloc[-1] if not pd.isna(df['rsi'].iloc[-1]) else 0
            current_rsi_ta = df['rsi_ta'].iloc[-1] if not pd.isna(df['rsi_ta'].iloc[-1]) else 0
            
            self.logger.debug(f"📊 INDICATORS | Price: ${current_price:.4f} | RSI(Manual): {current_rsi:.2f} | RSI(TA): {current_rsi_ta:.2f}")

            return df

        except Exception as e:
            self.logger.error(f"Error calculating indicators: {e}")
            return df

    def _calculate_rsi_manual(self, prices, period=14):
        """Manual RSI calculation matching Binance methodology"""
        if len(prices) < period + 1:
            return pd.Series([None] * len(prices))

        # Calculate price changes
        deltas = pd.Series(prices).diff()
        
        # Separate gains and losses
        gains = deltas.where(deltas > 0, 0)
        losses = -deltas.where(deltas < 0, 0)

        # Calculate Wilder's smoothed moving averages (Binance uses this method)
        avg_gains = gains.rolling(window=period, min_periods=period).mean()
        avg_losses = losses.rolling(window=period, min_periods=period).mean()

        # Apply Wilder's smoothing for subsequent periods
        for i in range(period, len(gains)):
            avg_gains.iloc[i] = (avg_gains.iloc[i-1] * (period - 1) + gains.iloc[i]) / period
            avg_losses.iloc[i] = (avg_losses.iloc[i-1] * (period - 1) + losses.iloc[i]) / period

        # Calculate RSI
        rs = avg_gains / avg_losses
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
