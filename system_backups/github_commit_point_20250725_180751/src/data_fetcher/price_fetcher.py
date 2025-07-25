import pandas as pd
import numpy as np
import ta
from typing import Dict, List, Optional
import logging
from src.binance_client.client import BinanceClientWrapper
from datetime import datetime, timezone, timedelta
from src.config.global_config import global_config
from src.data_fetcher.websocket_manager import websocket_manager
import time
import asyncio

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
        """Get current price for symbol from WebSocket cache or REST fallback"""
        try:
            # First try WebSocket cache
            ws_price = websocket_manager.get_current_price(symbol)
            if ws_price and websocket_manager.is_data_fresh(symbol, '1m', max_age_seconds=30):
                self.price_cache[symbol] = ws_price
                return ws_price

            # Fallback to REST API if WebSocket data is unavailable
            self.logger.debug(f"Using REST API fallback for {symbol} current price")
            ticker = self.binance_client.get_symbol_ticker(symbol)
            if ticker:
                price = float(ticker['price'])
                self.price_cache[symbol] = price
                return price
            return None

        except Exception as e:
            self.logger.error(f"Error getting current price for {symbol}: {e}")
            return None

    async def get_market_data(self, symbol: str, interval: str, limit: int = 100) -> Optional[pd.DataFrame]:
        """Get market data with enhanced historical data bootstrapping"""
        try:
            # Always ensure minimum data requirements for indicators
            min_required = max(limit, 200)  # MACD needs 26, RSI needs 14, plus buffer for accuracy

            # Try WebSocket data first
            websocket_data = websocket_manager.get_cached_klines(symbol, interval, min_required)

            if websocket_data and len(websocket_data) >= min_required:
                if websocket_manager.is_data_fresh(symbol, interval, max_age_seconds=120):
                    df = self._convert_websocket_to_dataframe(websocket_data)
                    if len(df) >= min_required:
                        self.logger.debug(f"✅ Using WebSocket data: {symbol} {interval} ({len(df)} candles)")
                        return df

            # If WebSocket data is insufficient, bootstrap with REST API
            self.logger.info(f"🔄 Bootstrapping historical data for {symbol} {interval}")

            # Fetch comprehensive historical data
            enhanced_limit = max(min_required, 500)  # Get plenty of historical data

            if self.binance_client.is_futures:
                klines = self.binance_client.client.futures_klines(
                    symbol=symbol,
                    interval=interval,
                    limit=enhanced_limit
                )
            else:
                klines = self.binance_client.client.get_klines(
                    symbol=symbol,
                    interval=interval,
                    limit=enhanced_limit
                )

            if not klines:
                self.logger.warning(f"No REST API data received for {symbol} {interval}")
                return None

            # Convert to DataFrame
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])

            # Convert data types
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df = df.set_index('timestamp')

            # Validate we have sufficient data
            if len(df) >= min_required:
                self.logger.info(f"✅ Historical data loaded: {symbol} {interval} ({len(df)} candles)")
            else:
                self.logger.warning(f"⚠️ Still insufficient data: {len(df)} candles (need {min_required}+)")

            return df

        except Exception as e:
            self.logger.error(f"Error fetching market data for {symbol} {interval}: {e}")
            return None

    def get_ohlcv_data(self, symbol: str, interval: str, limit: int = 100) -> Optional[pd.DataFrame]:
        """Get OHLCV data as DataFrame with enhanced accuracy"""
        try:
            # First, ensure WebSocket is tracking this symbol/interval
            websocket_manager.add_symbol_interval(symbol, interval)

            # WebSocket integration - ensure WebSocket manager is properly started
            if not websocket_manager.is_running:
                self.logger.info("🚀 Starting WebSocket manager for real-time data...")
                websocket_manager.start()

                # Wait for connection with timeout
                connection_timeout = 15  # 15 seconds
                wait_start = time.time()

                while not websocket_manager.is_connected and (time.time() - wait_start) < connection_timeout:
                    time.sleep(1)

                if websocket_manager.is_connected:
                    self.logger.info("✅ WebSocket connection established")
                else:
                    self.logger.warning("⚠️ WebSocket connection timeout - will rely on REST API")

            elif not websocket_manager.is_connected:
                self.logger.warning("⚠️ WebSocket manager running but not connected")

            # Check if WebSocket is connected first
            if not websocket_manager.is_connected:
                self.logger.info(f"🔄 WebSocket not connected, starting for {symbol} {interval}")
                websocket_manager.start()

                # Wait for connection with better patience
                max_wait = 45  # Increased wait time
                wait_time = 0
                while wait_time < max_wait and not websocket_manager.is_connected:
                    time.sleep(1)
                    wait_time += 1
                    if wait_time % 10 == 0:  # Log every 10 seconds
                        self.logger.info(f"⏳ Waiting for WebSocket connection... {wait_time}/{max_wait}s")

            # Try to get cached data with more flexible freshness requirements
            cached_data = websocket_manager.get_cached_klines(symbol, interval, limit)

            if cached_data and len(cached_data) > 0:
                self.logger.info(f"📡 Using WebSocket data for {symbol} {interval} ({len(cached_data)} klines)")
                return self._convert_websocket_to_dataframe(cached_data)

            # If WebSocket is connected but no data yet, wait for initial data
            if websocket_manager.is_connected:
                self.logger.info(f"⏳ WebSocket connected, waiting for initial data for {symbol} {interval}")

                # Wait for initial data with patience
                data_wait = 0
                max_data_wait = 60  # 1 minute to get initial data

                while data_wait < max_data_wait:
                    time.sleep(2)  # Check every 2 seconds
                    data_wait += 2

                    cached_data = websocket_manager.get_cached_klines(symbol, interval, limit)
                    if cached_data and len(cached_data) > 0:
                        self.logger.info(f"📡 Got initial WebSocket data for {symbol} {interval} after {data_wait}s")
                        return self._convert_websocket_to_dataframe(cached_data)

                    if data_wait % 10 == 0:  # Log every 10 seconds
                        self.logger.info(f"⏳ Waiting for WebSocket data... {data_wait}/{max_data_wait}s")

            # CRITICAL: During IP ban period, return None instead of making REST calls
            self.logger.error(f"❌ WebSocket data unavailable for {symbol} {interval} - Avoiding REST API during IP ban")
            self.logger.error(f"💡 Recommendation: Wait for WebSocket data or check connection status")

            return None

        except Exception as e:
            self.logger.error(f"Error getting OHLCV data for {symbol}: {e}")
            return None

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators with enhanced validation and error handling"""
        try:
            df = df.copy()

            if len(df) < 26:  # Need at least 26 for MACD
                self.logger.warning("Insufficient data for accurate indicator calculation")
                # Still calculate what we can with available data
                if len(df) >= 14:
                    # Calculate RSI with available data
                    delta = df['close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=min(14, len(df)-1)).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=min(14, len(df)-1)).mean()
                    rs = gain / loss
                    df['rsi'] = 100 - (100 / (1 + rs))

                return df

            # RSI (14-period) - Enhanced calculation
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()

            # Avoid division by zero
            rs = gain / loss.replace(0, 0.000001)
            df['rsi'] = 100 - (100 / (1 + rs))

            # MACD (12, 26, 9) - Enhanced calculation
            exp1 = df['close'].ewm(span=12, adjust=False).mean()
            exp2 = df['close'].ewm(span=26, adjust=False).mean()

            df['macd'] = exp1 - exp2
            df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
            df['macd_histogram'] = df['macd'] - df['macd_signal']

            # Simple Moving Averages
            if len(df) >= 20:
                df['sma_20'] = df['close'].rolling(window=20).mean()
            if len(df) >= 50:
                df['sma_50'] = df['close'].rolling(window=50).mean()

            # Bollinger Bands (20-period)
            if len(df) >= 20:
                sma20 = df['close'].rolling(window=20).mean()
                std20 = df['close'].rolling(window=20).std()
                df['bb_upper'] = sma20 + (std20 * 2)
                df['bb_lower'] = sma20 - (std20 * 2)
                df['bb_middle'] = sma20

            # Candlestick patterns (requires at least 2 candles)
            if len(df) >= 2:
                # Bullish Engulfing
                df['bullish_engulfing'] = (
                    (df['close'].shift(1) < df['open'].shift(1)) &  # Previous candle was bearish
                    (df['close'] > df['open']) &  # Current candle is bullish
                    (df['open'] < df['close'].shift(1)) &  # Current open below previous close
                    (df['close'] > df['open'].shift(1))  # Current close above previous open
                )

                # Bearish Engulfing
                df['bearish_engulfing'] = (
                    (df['close'].shift(1) > df['open'].shift(1)) &  # Previous candle was bullish
                    (df['close'] < df['open']) &  # Current candle is bearish
                    (df['open'] > df['close'].shift(1)) &  # Current open above previous close
                    (df['close'] < df['open'].shift(1))  # Current close below previous open
                )

            # Log successful indicator calculation
            indicators_calculated = []
            if 'rsi' in df.columns and not df['rsi'].isna().all():
                indicators_calculated.append('RSI')
            if 'macd' in df.columns and not df['macd'].isna().all():
                indicators_calculated.append('MACD')
            if 'sma_20' in df.columns and not df['sma_20'].isna().all():
                indicators_calculated.append('SMA20')

            if indicators_calculated:
                self.logger.debug(f"✅ Calculated indicators: {', '.join(indicators_calculated)} ({len(df)} candles)")

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

    def _convert_websocket_to_dataframe(self, cached_data: List[Dict], limit: int = None) -> pd.DataFrame:
        """Convert WebSocket data to DataFrame format"""
        df_data = []
        for kline in cached_data:
            df_data.append([
                kline['timestamp'], kline['open'], kline['high'], kline['low'],
                kline['close'], kline['volume'], kline['close_time'],
                0, 0, 0, 0, 0  # Placeholder values for additional columns
            ])

        df = pd.DataFrame(df_data, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])

        # Apply timezone adjustment if configured (preserves all existing logic)
        if self.use_local_timezone or self.timezone_offset_hours != 0:
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df['timestamp'] = df['timestamp'].apply(lambda x: self._adjust_timestamp_for_timezone(int(x.timestamp() * 1000)))
        else:
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

        # Convert to proper data types with high precision
        numeric_columns = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # Sort by timestamp to ensure proper order
        df = df.sort_values(by='timestamp')

        # Remove any duplicate timestamps
        df = df.drop_duplicates(subset=['timestamp'], keep='last')

        # Remove any rows with NaN values
        df = df.dropna()

        if df.empty:
            self.logger.warning(f"DataFrame is empty after processing")
            return None

        df.set_index('timestamp', inplace=True)

        # Return only requested amount if limit specified
        if limit:
            return df.tail(limit)
        return df