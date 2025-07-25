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
        """Get historical market data with WebSocket enhancement"""
        try:
            self.logger.debug(f"Fetching market data for {symbol} | {interval} | limit: {limit}")

            # Use existing rate limiting from binance_client
            klines = self.binance_client.get_historical_klines(symbol, interval, limit)

            if not klines:
                self.logger.warning(f"No kline data received for {symbol}")
                return None

            # Convert to DataFrame
            df = pd.DataFrame(klines, columns=[
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

            # Try to enhance with real-time WebSocket data
            try:
                from src.bot_manager import BotManager
                import sys

                # Get bot manager instance if available
                main_module = sys.modules.get('__main__')
                bot_manager = getattr(main_module, 'bot_manager', None) if main_module else None

                if (bot_manager and hasattr(bot_manager, 'websocket_data') and 
                    symbol in bot_manager.websocket_data and 
                    bot_manager.websocket_data[symbol]['connected']):

                    ws_data = bot_manager.websocket_data[symbol]['latest_kline']
                    if ws_data and bot_manager.websocket_data[symbol]['last_update']:
                        # Check if WebSocket data is recent (less than 30 seconds old)
                        data_age = (datetime.now() - bot_manager.websocket_data[symbol]['last_update']).total_seconds()
                        if data_age < 30:
                            # Convert ws_data timestamp to datetime object
                            latest_timestamp = pd.to_datetime(int(ws_data['timestamp']), unit='ms')

                            # If the latest WebSocket data is newer than our last API data
                            if latest_timestamp > df['timestamp'].iloc[-1]:
                                # Add new row with WebSocket data
                                new_row = pd.DataFrame({
                                    'timestamp': [latest_timestamp],
                                    'open': [ws_data['open']],
                                    'high': [ws_data['high']],
                                    'low': [ws_data['low']],
                                    'close': [ws_data['close']],
                                    'volume': [ws_data['volume']],
                                    'close_time': [ws_data['timestamp']],
                                    'quote_asset_volume': [0],
                                    'number_of_trades': [0],
                                    'taker_buy_base_asset_volume': [0],
                                    'taker_buy_quote_asset_volume': [0],
                                    'ignore': [0]
                                })
                                df = pd.concat([df, new_row], ignore_index=True)
                                self.logger.debug(f"Enhanced {symbol} data with WebSocket (age: {data_age:.1f}s)")
                            else:
                                # Update the last row with current WebSocket data
                                df.iloc[-1, df.columns.get_loc('close')] = ws_data['close']
                                df.iloc[-1, df.columns.get_loc('high')] = max(df.iloc[-1]['high'], ws_data['high'])
                                df.iloc[-1, df.columns.get_loc('low')] = min(df.iloc[-1]['low'], ws_data['low'])
                                df.iloc[-1, df.columns.get_loc('volume')] = ws_data['volume']
                                self.logger.debug(f"Updated {symbol} latest candle with WebSocket data")

            except Exception as ws_error:
                self.logger.debug(f"WebSocket enhancement failed for {symbol}: {ws_error}")
                # Continue with API-only data

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