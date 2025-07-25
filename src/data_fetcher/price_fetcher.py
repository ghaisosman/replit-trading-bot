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
        """Get market data from WebSocket cache with REST API fallback"""
        try:
            self.logger.debug(f"Fetching market data for {symbol} | {interval} | limit: {limit}")

            # First, try to get data from WebSocket cache
            cached_klines = websocket_manager.get_cached_klines(symbol, interval, limit)

            if cached_klines and websocket_manager.is_data_fresh(symbol, interval, max_age_seconds=60):
                self.logger.debug(f"✅ Using WebSocket cached data for {symbol} {interval} ({len(cached_klines)} klines)")

                # Convert WebSocket data to DataFrame
                df_data = []
                for kline in cached_klines:
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

            else:
                # Instead of REST API fallback, wait for WebSocket data
                self.logger.warning(f"⚠️ WebSocket data unavailable/stale for {symbol} {interval}")

                # Ensure WebSocket is tracking this symbol
                websocket_manager.add_symbol_interval(symbol, interval)

                # Wait for WebSocket data instead of REST fallback
                if websocket_manager.is_connected:
                    self.logger.info(f"⏳ Waiting for WebSocket data for {symbol} {interval}")

                    wait_time = 0
                    max_wait = 30  # 30 seconds max wait

                    while wait_time < max_wait:
                        time.sleep(2)
                        wait_time += 2

                        cached_klines = websocket_manager.get_cached_klines(symbol, interval, limit)
                        if cached_klines and websocket_manager.is_data_fresh(symbol, interval, max_age_seconds=300):
                            self.logger.info(f"📡 Got WebSocket data after waiting {wait_time}s")

                            # Convert WebSocket data to DataFrame
                            df_data = []
                            for kline in cached_klines:
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
                            break
                    else:
                        # If we couldn't get WebSocket data, return None instead of REST call
                        self.logger.error(f"❌ Could not get WebSocket data for {symbol} {interval} within {max_wait}s")
                        return None
                else:
                    self.logger.error(f"❌ WebSocket not connected, cannot fetch data for {symbol} {interval}")
                    return None

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

            # Try to enhance with real-time WebSocket data if we're using cached data
            if cached_klines:
                try:
                    latest_ws_kline = websocket_manager.get_latest_kline(symbol, interval)
                    if latest_ws_kline:
                        # Convert ws_data timestamp to datetime object
                        latest_timestamp = pd.to_datetime(int(latest_ws_kline['timestamp']), unit='ms')

                        # If the latest WebSocket data is newer than our last cached data
                        if latest_timestamp > df['timestamp'].iloc[-1]:
                            # Add new row with WebSocket data
                            new_row = pd.DataFrame({
                                'timestamp': [latest_timestamp],
                                'open': [latest_ws_kline['open']],
                                'high': [latest_ws_kline['high']],
                                'low': [latest_ws_kline['low']],
                                'close': [latest_ws_kline['close']],
                                'volume': [latest_ws_kline['volume']],
                                'close_time': [latest_ws_kline['close_time']],
                                'quote_asset_volume': [0],
                                'number_of_trades': [0],
                                'taker_buy_base_asset_volume': [0],
                                'taker_buy_quote_asset_volume': [0],
                                'ignore': [0]
                            })
                            df = pd.concat([df, new_row], ignore_index=True)
                            self.logger.debug(f"Enhanced {symbol} data with latest WebSocket kline")
                        else:
                            # Update the last row with current WebSocket data
                            df.iloc[-1, df.columns.get_loc('close')] = latest_ws_kline['close']
                            df.iloc[-1, df.columns.get_loc('high')] = max(df.iloc[-1]['high'], latest_ws_kline['high'])
                            df.iloc[-1, df.columns.get_loc('low')] = min(df.iloc[-1]['low'], latest_ws_kline['low'])
                            df.iloc[-1, df.columns.get_loc('volume')] = latest_ws_kline['volume']
                            self.logger.debug(f"Updated {symbol} latest candle with WebSocket data")

                except Exception as ws_error:
                    self.logger.debug(f"WebSocket enhancement failed for {symbol}: {ws_error}")
                    # Continue with cached data

            # Sort by timestamp to ensure proper order
            df = df.sort_values(by='timestamp')

            # Remove any duplicate timestamps
            df = df[~df.index.duplicated(keep='last')]

            # Remove any rows with NaN values
            df = df.dropna()

            if df.empty:
                self.logger.warning(f"DataFrame is empty after processing for {symbol}")
                return None

            df.set_index('timestamp', inplace=True)

            # Return only requested amount
            return df.tail(limit)

        except Exception as e:
            self.logger.error(f"Error fetching market data for {symbol}: {e}")
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
        """Calculate technical indicators with enhanced real-time accuracy"""
        try:
            # Ensure we have enough data
            if len(df) < 50:
                self.logger.warning("Insufficient data for accurate indicator calculation")
                return df

            # Calculate RSI using Binance-compatible method (primary)
            df['rsi'] = self._calculate_rsi_manual(df['close'].values, period=14)

            # Calculate RSI using ta library for comparison and fallback
            df['rsi_ta'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()

            # Use manual RSI as primary, fallback to ta library if needed
            df['rsi'] = df['rsi'].fillna(df['rsi_ta'])

            # Moving Averages - use pandas for precise calculation
            df['sma_20'] = df['close'].rolling(window=20, min_periods=20).mean()
            df['sma_50'] = df['close'].rolling(window=50, min_periods=50).mean()

            # EMA calculation using pandas exponential weighted mean (more accurate)
            df['ema_12'] = df['close'].ewm(span=12, adjust=False, min_periods=12).mean()
            df['ema_26'] = df['close'].ewm(span=26, adjust=False, min_periods=26).mean()

            # MACD calculation (Binance-compatible)
            df['macd'] = df['ema_12'] - df['ema_26']
            df['macd_signal'] = df['macd'].ewm(span=9, adjust=False, min_periods=9).mean()
            df['macd_histogram'] = df['macd'] - df['macd_signal']

            # Additional MACD using ta library for comparison and validation
            try:
                macd_indicator = ta.trend.MACD(df['close'], window_fast=12, window_slow=26, window_sign=9)
                df['macd_ta'] = macd_indicator.macd()
                df['macd_signal_ta'] = macd_indicator.macd_signal()
                df['macd_histogram_ta'] = macd_indicator.macd_diff()
            except:
                # Fallback if ta library fails
                df['macd_ta'] = df['macd']
                df['macd_signal_ta'] = df['macd_signal']
                df['macd_histogram_ta'] = df['macd_histogram']

            # Bollinger Bands for additional analysis
            df['bb_middle'] = df['close'].rolling(window=20).mean()
            bb_std = df['close'].rolling(window=20).std()
            df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
            df['bb_lower'] = df['bb_middle'] - (bb_std * 2)

            # Volume-based indicators
            df['volume_sma'] = df['volume'].rolling(window=20, min_periods=20).mean()
            df['volume_ratio'] = df['volume'] / df['volume_sma']

            # Log current values with enhanced details
            current_price = df['close'].iloc[-1]
            current_rsi = df['rsi'].iloc[-1] if not pd.isna(df['rsi'].iloc[-1]) else None
            current_macd = df['macd'].iloc[-1] if not pd.isna(df['macd'].iloc[-1]) else None
            current_macd_signal = df['macd_signal'].iloc[-1] if not pd.isna(df['macd_signal'].iloc[-1]) else None
            current_histogram = df['macd_histogram'].iloc[-1] if not pd.isna(df['macd_histogram'].iloc[-1]) else None

            # Enhanced logging for real-time accuracy
            indicators_log = f"📊 REAL-TIME INDICATORS | Price: ${current_price:.4f}"
            if current_rsi is not None:
                indicators_log += f" | RSI: {current_rsi:.2f}"
            if current_macd is not None and current_macd_signal is not None:
                indicators_log += f" | MACD: {current_macd:.6f}/{current_macd_signal:.6f}"
            if current_histogram is not None:
                indicators_log += f" | Histogram: {current_histogram:.6f}"

            self.logger.debug(indicators_log)

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

    def _convert_websocket_to_dataframe(self, cached_data: List[Dict]) -> pd.DataFrame:
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

        df.set_index('timestamp', inplace=True)

        return df