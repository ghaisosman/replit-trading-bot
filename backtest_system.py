#!/usr/bin/env python3
"""
Comprehensive Backtesting System
Tests strategies with real historical data and strategy-specific configurations
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
import json
from pathlib import Path
import asyncio
import logging

# Add src to path for imports
sys.path.append('src')

from src.binance_client.client import BinanceClientWrapper
from src.data_fetcher.price_fetcher import PriceFetcher
from src.strategy_processor.signal_processor import SignalProcessor, TradingSignal, SignalType
from src.execution_engine.strategies.macd_divergence_strategy import MACDDivergenceStrategy
from src.execution_engine.strategies.engulfing_pattern_strategy import EngulfingPatternStrategy

class BacktestEngine:
    """Comprehensive backtesting engine for all strategies"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.binance_client = BinanceClientWrapper()
        self.price_fetcher = PriceFetcher(self.binance_client)
        self.signal_processor = SignalProcessor()

        # Backtest results storage
        self.results = {
            'trades': [],
            'summary': {},
            'strategy_performance': {}
        }

        # Strategy configurations templates
        self.strategy_configs = {
            'rsi_oversold': {
                'name': 'rsi_oversold',
                'symbol': 'BTCUSDT',
                'margin': 50.0,
                'leverage': 5,
                'timeframe': '15m',
                'max_loss_pct': 10.0,
                'assessment_interval': 60,
                'cooldown_period': 300,
                'decimals': 3,
                'rsi_period': 14,
                'rsi_long_entry': 30,
                'rsi_long_exit': 70,
                'rsi_short_entry': 70,
                'rsi_short_exit': 30,
                'partial_tp_pnl_threshold': 0.0,
                'partial_tp_position_percentage': 0.0
            },
            'macd_divergence': {
                'name': 'macd_divergence',
                'symbol': 'BTCUSDT',
                'margin': 50.0,
                'leverage': 5,
                'timeframe': '15m',
                'max_loss_pct': 10.0,
                'assessment_interval': 30,
                'cooldown_period': 300,
                'decimals': 3,
                'macd_fast': 12,
                'macd_slow': 26,
                'macd_signal': 9,
                'min_histogram_threshold': 0.0001,
                'macd_entry_threshold': 0.0015,
                'macd_exit_threshold': 0.002,
                'confirmation_candles': 1,
                'divergence_strength_min': 0.6,
                'histogram_divergence_lookback': 10,
                'price_divergence_lookback': 10
            },
            'engulfing_pattern': {
                'name': 'engulfing_pattern',
                'symbol': 'BTCUSDT',
                'margin': 50.0,
                'leverage': 5,
                'timeframe': '1h',
                'max_loss_pct': 10.0,
                'assessment_interval': 120,
                'cooldown_period': 600,
                'decimals': 3,
                'rsi_period': 14,
                'rsi_threshold': 50,
                'rsi_long_exit': 70,
                'rsi_short_exit': 30,
                'stable_candle_ratio': 0.5,
                'price_lookback_bars': 5,
                'partial_tp_pnl_threshold': 0.0,
                'partial_tp_position_percentage': 0.0
            },
            'smart_money': {
                'name': 'smart_money',
                'symbol': 'ETHUSDT',
                'margin': 75.0,
                'leverage': 3,
                'timeframe': '15m',
                'max_loss_pct': 15.0,
                'assessment_interval': 45,
                'cooldown_period': 900,
                'decimals': 2,
                'swing_lookback_period': 25,
                'sweep_threshold_pct': 0.1,
                'reversion_candles': 3,
                'volume_spike_multiplier': 2.0,
                'min_swing_distance_pct': 1.0
            }
        }

    def get_historical_data(self, symbol: str, interval: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Get historical data for backtesting period with proper error handling"""
        try:
            # Validate inputs
            if not symbol or not interval or not start_date or not end_date:
                raise ValueError("Missing required parameters: symbol, interval, start_date, or end_date")

            # Parse dates
            try:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            except ValueError as e:
                raise ValueError(f"Invalid date format. Use YYYY-MM-DD. Error: {e}")

            # Validate date range
            if start_dt >= end_dt:
                raise ValueError("Start date must be before end date")

            if end_dt > datetime.now():
                raise ValueError("End date cannot be in the future")

            # Convert to milliseconds
            start_ms = int(start_dt.timestamp() * 1000)
            end_ms = int(end_dt.timestamp() * 1000)

            # Generate unique identifier for this data request
            data_request_id = f"{symbol}_{interval}_{start_date}_{end_date}_{hash(str(datetime.now().timestamp()))}"
            self.logger.info(f"📅 Fetching historical data for {symbol} {interval} from {start_date} to {end_date}")
            self.logger.info(f"🆔 Data Request ID: {data_request_id}")

            # Test API connection first
            try:
                if self.binance_client.is_futures:
                    test_call = self.binance_client.client.futures_klines(
                        symbol=symbol,
                        interval=interval,
                        limit=1
                    )
                else:
                    test_call = self.binance_client.client.get_klines(
                        symbol=symbol,
                        interval=interval,
                        limit=1
                    )
                if not test_call:
                    raise Exception(f"API test failed - no data returned for {symbol}")
            except Exception as api_error:
                raise Exception(f"Binance API connection failed: {api_error}")

            # Calculate interval in milliseconds
            interval_ms = self._interval_to_ms(interval)
            max_candles_per_request = 1000

            # Calculate expected number of candles
            total_duration_ms = end_ms - start_ms
            expected_candles = total_duration_ms // interval_ms
            self.logger.info(f"📊 Expected approximately {expected_candles} candles for this period")

            # Get historical data in chunks
            all_klines = []
            current_start = start_ms
            chunk_count = 0
            failed_chunks = 0

            while current_start < end_ms and chunk_count < 100:  # Safety limit
                chunk_count += 1
                current_end = min(current_start + (max_candles_per_request * interval_ms), end_ms)

                self.logger.info(f"🔄 Fetching chunk {chunk_count}: {datetime.fromtimestamp(current_start/1000)} to {datetime.fromtimestamp(current_end/1000)}")

                try:
                    # Use proper Binance API call with start and end times
                    if self.binance_client.is_futures:
                        klines = self.binance_client.client.futures_klines(
                            symbol=symbol,
                            interval=interval,
                            startTime=current_start,
                            endTime=current_end,
                            limit=max_candles_per_request
                        )
                    else:
                        klines = self.binance_client.client.get_historical_klines(
                            symbol=symbol,
                            interval=interval,
                            start_str=str(current_start),
                            end_str=str(current_end),
                            limit=max_candles_per_request
                        )

                    if not klines:
                        failed_chunks += 1
                        self.logger.warning(f"⚠️ No data returned for chunk {chunk_count}")
                        if failed_chunks > 5:  # Too many failures
                            raise Exception(f"Too many failed chunks ({failed_chunks}). Data may not be available for this period.")
                    else:
                        # Filter klines to exact date range
                        filtered_klines = []
                        for kline in klines:
                            kline_timestamp = int(kline[0])
                            if start_ms <= kline_timestamp <= end_ms:
                                filtered_klines.append(kline)

                        all_klines.extend(filtered_klines)
                        self.logger.info(f"✅ Added {len(filtered_klines)} candles from chunk {chunk_count}")

                        # Update current_start based on the last kline timestamp
                        if filtered_klines:
                            last_timestamp = int(filtered_klines[-1][0])
                            current_start = last_timestamp + interval_ms
                        else:
                            current_start = current_end

                except Exception as chunk_error:
                    failed_chunks += 1
                    self.logger.error(f"❌ Error fetching chunk {chunk_count}: {chunk_error}")
                    if failed_chunks > 5:
                        raise Exception(f"Too many API failures. Cannot fetch reliable data for {symbol}")
                    current_start = current_end

                # Rate limiting
                import time
                time.sleep(0.1)

            # Validate we got meaningful data
            if not all_klines:
                raise Exception(f"No historical data available for {symbol} in the period {start_date} to {end_date}. This could be due to: 1) Symbol not existing during this period, 2) Invalid symbol name, 3) API restrictions, or 4) Market was closed/not trading.")

            if len(all_klines) < 50:
                raise Exception(f"Insufficient data: Only {len(all_klines)} candles found. Need at least 50 for reliable backtesting. Try a longer time period or different timeframe.")

            # Validate data uniqueness to prevent cached/identical results
            unique_prices = len(set([float(kline[4]) for kline in all_klines]))  # close prices
            if unique_prices < len(all_klines) * 0.7:  # Less than 70% unique prices suggests bad data
                self.logger.warning(f"⚠️ Data quality issue: Only {unique_prices}/{len(all_klines)} unique prices found")

            # Log first and last few candles for validation
            self.logger.info(f"📊 Data Sample Validation:")
            self.logger.info(f"   First candle: {datetime.fromtimestamp(int(all_klines[0][0])/1000)} | Close: ${float(all_klines[0][4]):.2f}")
            self.logger.info(f"   Last candle: {datetime.fromtimestamp(int(all_klines[-1][0])/1000)} | Close: ${float(all_klines[-1][4]):.2f}")
            self.logger.info(f"   Price range: ${min([float(k[4]) for k in all_klines]):.2f} - ${max([float(k[4]) for k in all_klines]):.2f}")

            # Convert to DataFrame
            df = pd.DataFrame(all_klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])

            # Validate data integrity
            if df.empty:
                raise Exception("DataFrame is empty after conversion")

            # Convert data types with error checking
            numeric_columns = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                if df[col].isna().all():
                    raise Exception(f"All values in column '{col}' are invalid")

            # Check for data quality issues
            nan_count = df[numeric_columns].isna().sum().sum()
            if nan_count > 0:
                self.logger.warning(f"⚠️ Found {nan_count} NaN values in price data - filling with forward fill")
                df[numeric_columns] = df[numeric_columns].fillna(method='ffill')

            # Timestamp processing
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

            # Remove duplicates and sort
            df = df.sort_index()
            df = df[~df.index.duplicated(keep='last')]

            # Keep only OHLCV columns
            df = df[['open', 'high', 'low', 'close', 'volume']]

            # Validate price data makes sense
            if (df['close'] <= 0).any():
                raise Exception("Invalid price data: Found zero or negative prices")

            if (df['volume'] < 0).any():
                raise Exception("Invalid volume data: Found negative volume")

            # Calculate indicators using the same method as live trading
            try:
                df_with_indicators = self.price_fetcher.calculate_indicators(df.copy())
                if df_with_indicators is None or df_with_indicators.empty:
                    raise Exception("Indicator calculation failed - no data returned")
                df = df_with_indicators

                # Validate that we have all required indicators
                self.logger.info(f"📊 Available indicators: {list(df.columns)}")

            except Exception as indicator_error:
                raise Exception(f"Failed to calculate indicators: {indicator_error}")

            # Add strategy-specific indicators if needed
            try:
                # Ensure MACD indicators are calculated
                if 'macd' not in df.columns:
                    self.logger.info("🔧 Calculating MACD indicators...")
                    df = self._calculate_macd_indicators(df)

                # Ensure additional indicators for Smart Money
                if 'sma_20' not in df.columns:
                    self.logger.info("🔧 Calculating SMA indicators...")
                    df['sma_20'] = df['close'].rolling(window=20).mean()

                if 'ema_50' not in df.columns:
                    self.logger.info("🔧 Calculating EMA indicators...")
                    df['ema_50'] = df['close'].ewm(span=50).mean()

                self.logger.info(f"📊 Final indicators available: {list(df.columns)}")

            except Exception as additional_indicator_error:
                self.logger.warning(f"⚠️ Failed to calculate additional indicators: {additional_indicator_error}")

            # Final validation
            actual_data_range = f"{df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')}"
            requested_range = f"{start_date} to {end_date}"

            if len(df) < expected_candles * 0.8:  # Less than 80% of expected data
                self.logger.warning(f"⚠️ Got {len(df)} candles, expected ~{expected_candles}. Some data may be missing.")

            self.logger.info(f"✅ Historical data processed successfully:")
            self.logger.info(f"   📊 Candles: {len(df)}")
            self.logger.info(f"   📅 Actual range: {actual_data_range}")
            self.logger.info(f"   📅 Requested range: {requested_range}")
            self.logger.info(f"   💲 Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")

            return df

        except Exception as e:
            error_msg = f"Failed to fetch historical data for {symbol}: {str(e)}"
            self.logger.error(f"❌ {error_msg}")
            raise Exception(error_msg)

    def _interval_to_ms(self, interval: str) -> int:
        """Convert interval string to milliseconds"""
        interval_map = {
            '1m': 60 * 1000,
            '3m': 3 * 60 * 1000,
            '5m': 5 * 60 * 1000,
            '15m': 15 * 60 * 1000,
            '30m': 30 * 60 * 1000,
            '1h': 60 * 60 * 1000,
            '2h': 2 * 60 * 60 * 1000,
            '4h': 4 * 60 * 60 * 1000,
            '6h': 6 * 60 * 60 * 1000,
            '8h': 8 * 60 * 60 * 1000,
            '12h': 12 * 60 * 60 * 1000,
            '1d': 24 * 60 * 60 * 1000
        }
        return interval_map.get(interval, 15 * 60 * 1000)

    def _calculate_macd_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate MACD indicators manually if not present"""
        try:
            # Default MACD parameters
            fast = 12
            slow = 26
            signal = 9

            # Calculate EMAs
            ema_fast = df['close'].ewm(span=fast).mean()
            ema_slow = df['close'].ewm(span=slow).mean()

            # Calculate MACD line
            df['macd'] = ema_fast - ema_slow

            # Calculate Signal line
            df['macd_signal'] = df['macd'].ewm(span=signal).mean()

            # Calculate Histogram
            df['macd_histogram'] = df['macd'] - df['macd_signal']

            self.logger.info(f"✅ MACD indicators calculated successfully")
            return df

        except Exception as e:
            self.logger.error(f"❌ Failed to calculate MACD indicators: {e}")
            return df

    def backtest_strategy(self, strategy_name: str, config: Dict[str, Any], start_date: str, end_date: str) -> Dict[str, Any]:
        """Backtest a specific strategy with given configuration"""
        try:
            # FORCE CLEAR ALL CACHES to ensure fresh data
            self.logger.info(f"🧹 CLEARING ALL CACHES for fresh backtest")

            # Clear strategy handler cache
            if hasattr(self, '_strategy_handler_cache'):
                delattr(self, '_strategy_handler_cache')

            # Clear signal processor cache
            if hasattr(self.signal_processor, '_config_cache'):
                self.signal_processor._config_cache = {}

            # Generate unique backtest ID to prevent result caching
            import hashlib
            import time
            backtest_id = hashlib.md5(f"{strategy_name}_{config}_{start_date}_{end_date}_{time.time()}".encode()).hexdigest()[:12]

            self.logger.info(f"🚀 Starting backtest for {strategy_name}")
            self.logger.info(f"🆔 Backtest ID: {backtest_id}")
            self.logger.info(f"📅 Period: {start_date} to {end_date}")

            # DEEP CONFIGURATION VALIDATION - Log every parameter
            self.logger.info(f"🔍 COMPLETE CONFIG VALIDATION for {strategy_name}:")
            for key, value in sorted(config.items()):
                self.logger.info(f"   {key}: {value} (type: {type(value).__name__})")

            # Validate configuration
            if not config.get('symbol'):
                return {'error': 'Missing symbol in configuration'}
            if not config.get('timeframe'):
                return {'error': 'Missing timeframe in configuration'}

            # CRITICAL: Validate that key strategy parameters are set and different from defaults
            template_config = self.strategy_configs.get(strategy_name, {})

            # Check parameter differences from template
            changed_params = []
            critical_params = ['margin', 'leverage', 'max_loss_pct', 'symbol', 'timeframe']

            if 'rsi' in strategy_name.lower():
                critical_params.extend(['rsi_long_entry', 'rsi_short_entry', 'rsi_long_exit', 'rsi_short_exit'])
            elif 'macd' in strategy_name.lower():
                critical_params.extend(['macd_fast', 'macd_slow', 'macd_signal'])
            elif 'smart_money' in strategy_name.lower():
                critical_params.extend(['swing_lookback_period', 'sweep_threshold_pct'])

            for param in critical_params:
                if param in config and param in template_config:
                    if config[param] != template_config[param]:
                        changed_params.append(f"{param}: {template_config[param]} → {config[param]}")

            if changed_params:
                self.logger.info(f"✅ PARAMETER CHANGES DETECTED: {', '.join(changed_params)}")
            else:
                self.logger.warning(f"⚠️ NO PARAMETER CHANGES - may be using cached/template values!")

            # Validate specific strategy parameters
            if 'rsi' in strategy_name.lower():
                rsi_long_entry = config.get('rsi_long_entry')
                rsi_short_entry = config.get('rsi_short_entry')
                rsi_long_exit = config.get('rsi_long_exit')
                rsi_short_exit = config.get('rsi_short_exit')

                self.logger.info(f"🎯 RSI STRATEGY PARAMETERS:")
                self.logger.info(f"   Long Entry: {rsi_long_entry}")
                self.logger.info(f"   Short Entry: {rsi_short_entry}")
                self.logger.info(f"   Long Exit: {rsi_long_exit}")
                self.logger.info(f"   Short Exit: {rsi_short_exit}")

            # Validate margin and leverage
            margin = config.get('margin')
            leverage = config.get('leverage')
            max_loss_pct = config.get('max_loss_pct')

            self.logger.info(f"💰 TRADING PARAMETERS:")
            self.logger.info(f"   Margin: ${margin}")
            self.logger.info(f"   Leverage: {leverage}x")
            self.logger.info(f"   Max Loss: {max_loss_pct}%")

            symbol = config['symbol']
            timeframe = config['timeframe']

            # Get historical data with proper error handling
            try:
                df = self.get_historical_data(symbol, timeframe, start_date, end_date)
                if df is None or df.empty:
                    return {'error': f'No historical data available for {symbol} on {timeframe} timeframe between {start_date} and {end_date}'}
            except Exception as data_error:
                return {'error': f'Data fetch failed: {str(data_error)}'}

            # Validate we have enough data for backtesting
            if len(df) < 100:
                return {'error': f'Insufficient data for backtesting. Got {len(df)} candles, need at least 100. Try a longer time period.'}

            # FORCE FRESH STRATEGY HANDLER - No caching allowed
            strategy_handler = None
            try:
                self.logger.info(f"🔧 Creating FRESH strategy handler for {strategy_name}")
                strategy_handler = self._get_strategy_handler_fresh(strategy_name, config, backtest_id)

                # Validate handler received correct config
                if strategy_handler and hasattr(strategy_handler, 'config'):
                    self.logger.info(f"✅ Strategy handler config validation:")
                    for key in ['margin', 'leverage', 'symbol', 'timeframe']:
                        if key in config:
                            handler_value = getattr(strategy_handler.config, key, None) if hasattr(strategy_handler.config, key) else strategy_handler.config.get(key)
                            config_value = config[key]
                            if handler_value == config_value:
                                self.logger.info(f"   ✅ {key}: {config_value}")
                            else:
                                self.logger.warning(f"   ⚠️ {key}: CONFIG={config_value} vs HANDLER={handler_value}")

            except Exception as strategy_error:
                return {'error': f'Strategy initialization failed: {str(strategy_error)}'}

            # Validate indicators are calculated
            required_indicators = self._get_required_indicators(strategy_name)
            missing_indicators = [ind for ind in required_indicators if ind not in df.columns]
            if missing_indicators:
                return {'error': f'Missing required indicators for {strategy_name}: {missing_indicators}'}

            # Backtest variables with fresh state
            trades = []
            current_position = None
            last_trade_exit_time = None
            cooldown_seconds = config.get('cooldown_period', 300)
            # Ensure cooldown_period is an integer
            if isinstance(cooldown_seconds, str):
                cooldown_seconds = int(float(cooldown_seconds))
            cooldown_period = timedelta(seconds=cooldown_seconds)
            signals_generated = 0

            # Log cooldown period to verify config is being used
            self.logger.info(f"📊 Processing {len(df)} candles for backtesting...")
            self.logger.info(f"⏱️ Cooldown period: {cooldown_period.total_seconds()}s")

            # Process each candle
            for i in range(50, len(df)):  # Start from 50 to ensure indicators are calculated
                current_time = df.index[i]
                current_data = df.iloc[:i+1]  # Data up to current candle
                current_price = df.iloc[i]['close']

                # Skip if in cooldown period
                if last_trade_exit_time and current_time < last_trade_exit_time + cooldown_period:
                    continue

                # Check for exit conditions if we have a position
                if current_position:
                    try:
                        exit_result = self._check_exit_conditions(
                            current_position, current_data, current_price, strategy_handler, config
                        )

                        if exit_result:
                            # Close position
                            trade_result = self._close_position(
                                current_position, current_price, current_time, exit_result['reason']
                            )
                            trades.append(trade_result)
                            current_position = None
                            last_trade_exit_time = current_time

                            self.logger.info(f"📊 Trade #{len(trades)} closed: {trade_result['exit_reason']} | PnL: ${trade_result['pnl_usdt']:.2f}")
                            continue
                    except Exception as exit_error:
                        self.logger.error(f"Error checking exit conditions: {exit_error}")
                        continue

                # Check for entry conditions if no position
                if not current_position:
                    try:
                        entry_signal = self._check_entry_conditions(current_data, strategy_handler, config)

                        if entry_signal:
                            signals_generated += 1
                            # Open position
                            current_position = self._open_position(
                                entry_signal, current_price, current_time, config
                            )

                            self.logger.info(f"🟢 Position #{signals_generated} opened: {entry_signal.signal_type.value} | Entry: ${current_price:.4f} | Reason: {entry_signal.reason}")
                    except Exception as entry_error:
                        self.logger.error(f"Error checking entry conditions: {entry_error}")
                        continue

            # Close any remaining position at the end
            if current_position:
                final_price = df.iloc[-1]['close']
                final_time = df.index[-1]
                trade_result = self._close_position(
                    current_position, final_price, final_time, "End of backtest period"
                )
                trades.append(trade_result)
                self.logger.info(f"📊 Final trade closed at backtest end | PnL: ${trade_result['pnl_usdt']:.2f}")

            # Log backtest summary
            self.logger.info(f"✅ Backtest completed:")
            self.logger.info(f"   📊 Total signals generated: {signals_generated}")
            self.logger.info(f"   📊 Total trades completed: {len(trades)}")
            self.logger.info(f"   📅 Data period: {df.index[0].strftime('%Y-%m-%d %H:%M')} to {df.index[-1].strftime('%Y-%m-%d %H:%M')}")

            # Validate we had some trading activity
            if signals_generated == 0:
                return {'error': f'No trading signals generated during the backtest period. This could indicate: 1) Strategy conditions were never met, 2) Configuration parameters are too restrictive, or 3) Market conditions were not suitable for this strategy.'}

            # Calculate strategy performance
            try:
                performance = self._calculate_performance(trades, config)
            except Exception as perf_error:
                return {'error': f'Performance calculation failed: {str(perf_error)}'}

            # Generate configuration hash to track uniqueness
            import hashlib
            config_str = json.dumps(config, sort_keys=True)
            config_hash = hashlib.md5(config_str.encode()).hexdigest()[:8]

            self.logger.info(f"🔍 BACKTEST RESULT SUMMARY:")
            self.logger.info(f"   Config Hash: {config_hash}")
            self.logger.info(f"   Total Trades: {len(trades)}")
            self.logger.info(f"   Signals Generated: {signals_generated}")
            if len(trades) > 0:
                total_pnl = sum(t['pnl_usdt'] for t in trades)
                self.logger.info(f"   Total PnL: ${total_pnl:.2f}")

            return {
                'strategy_name': strategy_name,
                'symbol': symbol,
                'timeframe': timeframe,
                'period': f"{start_date} to {end_date}",
                'config': config,
                'config_hash': config_hash,
                'trades': trades,
                'performance': performance,
                'total_candles': len(df),
                'signals_generated': signals_generated,
                'data_range': f"{df.index[0].strftime('%Y-%m-%d %H:%M')} to {df.index[-1].strftime('%Y-%m-%d %H:%M')}",
                'price_range': f"${df['close'].min():.2f} - ${df['close'].max():.2f}",
                'success': True
            }

        except Exception as e:
            error_msg = f"Backtest failed for {strategy_name}: {str(e)}"
            self.logger.error(f"❌ {error_msg}")
            import traceback
            traceback.print_exc()
            return {'error': error_msg, 'success': False}

    def _get_strategy_handler_fresh(self, strategy_name: str, config: Dict[str, Any], backtest_id: str):
        """Get fresh strategy-specific handler without any caching"""
        try:
            self.logger.info(f"🔧 Creating strategy handler for {strategy_name} | ID: {backtest_id}")

            # Log the config being passed to strategy
            self.logger.info(f"📋 Handler Config Check:")
            for key, value in config.items():
                if key in ['margin', 'leverage', 'symbol', 'timeframe', 'max_loss_pct']:
                    self.logger.info(f"   {key}: {value}")

            if 'macd' in strategy_name.lower():
                # Force fresh MACD handler
                handler = MACDDivergenceStrategy(strategy_name, config.copy())
                self.logger.info(f"✅ Created FRESH MACD strategy handler | ID: {backtest_id}")
                return handler
            elif 'engulfing' in strategy_name.lower():
                # Force fresh Engulfing handler
                handler = EngulfingPatternStrategy(strategy_name, config.copy())
                self.logger.info(f"✅ Created FRESH Engulfing Pattern strategy handler | ID: {backtest_id}")
                return handler
            elif 'smart_money' in strategy_name.lower():
                # Force fresh Smart Money handler
                try:
                    from src.execution_engine.strategies.smart_money_strategy import SmartMoneyStrategy
                    handler = SmartMoneyStrategy(strategy_name, config.copy())
                    self.logger.info(f"✅ Created FRESH Smart Money strategy handler | ID: {backtest_id}")
                    return handler
                except ImportError:
                    self.logger.warning(f"⚠️ Smart Money strategy not available, will use signal processor")
                    return None
            else:
                # RSI and other strategies use signal processor with fresh config
                self.logger.info(f"✅ Using FRESH signal processor for {strategy_name} | ID: {backtest_id}")
                # Clear any signal processor cache
                if hasattr(self.signal_processor, '_strategy_cache'):
                    self.signal_processor._strategy_cache = {}
                return None
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize strategy handler for {strategy_name}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _get_strategy_handler(self, strategy_name: str, config: Dict[str, Any]):
        """Legacy method - redirects to fresh handler"""
        return self._get_strategy_handler_fresh(strategy_name, config, "legacy")

    def _get_required_indicators(self, strategy_name: str) -> List[str]:
        """Get required indicators for each strategy"""
        if 'macd' in strategy_name.lower():
            return ['macd', 'macd_signal', 'macd_histogram']
        elif 'engulfing' in strategy_name.lower() or 'rsi' in strategy_name.lower():
            return ['rsi']
        elif 'smart_money' in strategy_name.lower():
            return ['rsi', 'sma_20', 'ema_50']
        else:
            return ['rsi']  # Default requirement

    def _check_entry_conditions(self, df: pd.DataFrame, strategy_handler, config: Dict[str, Any]) -> Optional[TradingSignal]:
        """Check entry conditions for strategy with fresh configuration"""
        try:
            strategy_name = config.get('name', 'unknown')

            # Log current candle data for debugging
            current_candle = df.iloc[-1]
            if 'rsi' in df.columns:
                current_rsi = current_candle['rsi']
                self.logger.debug(f"📊 Entry Check | RSI: {current_rsi:.2f} | Price: ${current_candle['close']:.4f}")

                # For RSI strategies, log the thresholds being used
                if 'rsi' in strategy_name.lower():
                    rsi_long_entry = config.get('rsi_long_entry', 30)
                    rsi_short_entry = config.get('rsi_short_entry', 70)
                    self.logger.debug(f"🎯 RSI Thresholds | Long Entry: {rsi_long_entry} | Short Entry: {rsi_short_entry}")

            if strategy_handler and hasattr(strategy_handler, 'evaluate_entry_signal'):
                # Use strategy-specific entry evaluation with fresh config
                self.logger.debug(f"🔄 Using strategy handler for {strategy_name} entry evaluation")

                # Force fresh indicator calculation
                if hasattr(strategy_handler, 'calculate_indicators'):
                    df_fresh = df.copy()
                    df_with_strategy_indicators = strategy_handler.calculate_indicators(df_fresh)
                    signal = strategy_handler.evaluate_entry_signal(df_with_strategy_indicators)
                else:
                    signal = strategy_handler.evaluate_entry_signal(df.copy())

                if signal:
                    self.logger.info(f"✅ Strategy handler generated signal for {strategy_name}: {signal.signal_type.value} | Reason: {signal.reason}")

                return signal
            else:
                # Use signal processor for RSI and other strategies with fresh config
                self.logger.debug(f"🔄 Using signal processor for {strategy_name} entry evaluation")

                # Create fresh copy of config to prevent caching issues
                fresh_config = config.copy()

                # For RSI strategies, explicitly log the parameters being used
                if 'rsi' in strategy_name.lower():
                    self.logger.debug(f"🔍 RSI Config being passed to signal processor:")
                    for param in ['rsi_long_entry', 'rsi_short_entry', 'rsi_long_exit', 'rsi_short_exit']:
                        value = fresh_config.get(param)
                        self.logger.debug(f"   {param}: {value}")

                signal = self.signal_processor.evaluate_entry_conditions(df.copy(), fresh_config)

                if signal:
                    self.logger.info(f"✅ Signal processor generated signal for {strategy_name}: {signal.signal_type.value} | Reason: {signal.reason}")
                else:
                    # Log why no signal was generated for RSI strategies
                    if 'rsi' in strategy_name.lower() and 'rsi' in df.columns:
                        current_rsi = df['rsi'].iloc[-1]
                        rsi_long_entry = fresh_config.get('rsi_long_entry', 30)
                        rsi_short_entry = fresh_config.get('rsi_short_entry', 70)
                        self.logger.debug(f"❌ No RSI signal | RSI: {current_rsi:.2f} | Not <= {rsi_long_entry} or >= {rsi_short_entry}")

                return signal

        except Exception as e:
            self.logger.error(f"Error checking entry conditions: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _check_exit_conditions(self, position: Dict, df: pd.DataFrame, current_price: float, 
                              strategy_handler, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check exit conditions for current position with ACCURATE stop loss enforcement"""
        try:
            # CRITICAL: Get actual margin used for this position (not config margin)
            actual_margin_used = position.get('actual_margin_used') or position.get('margin_used')

            # Fallback to config margin if not available
            if not actual_margin_used:
                actual_margin_used = config.get('margin', 50.0)
                self.logger.warning(f"⚠️ Using fallback margin ${actual_margin_used:.2f} - actual margin not found")

            max_loss_pct = config.get('max_loss_pct', 10.0)
            leverage = config.get('leverage', 5)

            # Calculate current PnL correctly
            entry_price = position['entry_price']
            quantity = position['quantity']
            side = position['side']

            # Calculate PnL in USDT
            if side == 'BUY':
                pnl_usdt = (current_price - entry_price) * quantity
            else:  # SELL
                pnl_usdt = (entry_price - current_price) * quantity

            # CRITICAL: Calculate PnL percentage against ACTUAL margin invested (exactly like live trading)
            pnl_percentage = (pnl_usdt / actual_margin_used) * 100

            # ENHANCED: Also check stop loss price directly for validation
            stop_loss_price = position.get('stop_loss')
            stop_loss_triggered_by_price = False

            if stop_loss_price is not None:
                if side == 'BUY' and current_price <= stop_loss_price:
                    stop_loss_triggered_by_price = True
                elif side == 'SELL' and current_price >= stop_loss_price:
                    stop_loss_triggered_by_price = True

            # CRITICAL: Stop loss check matches live trading exactly - percentage based on actual margin
            if pnl_percentage <= -max_loss_pct or stop_loss_triggered_by_price:
                if pnl_percentage <= -max_loss_pct:
                    reason = f'Stop Loss (Max Loss {max_loss_pct}%)'
                else:
                    # Only format stop_loss_price if it's not None
                    reason = f'Stop Loss (Price: ${stop_loss_price:.4f})' if stop_loss_price is not None else 'Stop Loss (Price Check)'

                self.logger.info(f"🛑 STOP LOSS TRIGGERED | {side} | Entry: ${entry_price:.4f} | Current: ${current_price:.4f}")
                self.logger.info(f"   💰 PnL: ${pnl_usdt:.2f} ({pnl_percentage:.2f}%) | Margin: ${actual_margin_used:.2f}")
                
                # Safe logging of stop loss price
                sl_price_str = f"${stop_loss_price:.4f}" if stop_loss_price is not None else "None"
                self.logger.info(f"   🎯 SL Price: {sl_price_str} | Price Trigger: {stop_loss_triggered_by_price}")

                return {
                    'reason': reason,
                    'type': 'stop_loss',
                    'pnl_percentage': pnl_percentage,
                    'pnl_usdt': pnl_usdt
                }

            # Check partial take profit if enabled
            partial_tp_threshold = config.get('partial_tp_pnl_threshold', 0.0)
            partial_tp_percentage = config.get('partial_tp_position_percentage', 0.0)

            if (partial_tp_threshold > 0 and partial_tp_percentage > 0 and 
                not position.get('partial_tp_triggered', False)):
                pnl_percentage = (pnl / margin) * 100
                if pnl_percentage >= partial_tp_threshold:
                    position['partial_tp_triggered'] = True
                    position['quantity'] *= (1 - partial_tp_percentage / 100)
                    return {
                        'reason': f'Partial Take Profit ({partial_tp_percentage}% at {partial_tp_threshold}% profit)',
                        'type': 'partial_tp',
                        'partial': True
                    }

            # Check strategy-specific exit conditions
            if strategy_handler and hasattr(strategy_handler, 'evaluate_exit_signal'):
                try:
                    # Ensure strategy has proper indicators for exit evaluation
                    if hasattr(strategy_handler, 'calculate_indicators'):
                        df_with_strategy_indicators = strategy_handler.calculate_indicators(df.copy())
                        exit_reason = strategy_handler.evaluate_exit_signal(df_with_strategy_indicators, position)
                    else:
                        exit_reason = strategy_handler.evaluate_exit_signal(df, position)

                    if exit_reason:
                        self.logger.debug(f"🔄 Strategy handler exit: {exit_reason}")
                        return {
                            'reason': exit_reason,
                            'type': 'strategy_exit'
                        }
                except Exception as e:
                    self.logger.error(f"Error in strategy handler exit evaluation: {e}")

            # Use signal processor or manual exit conditions
            try:
                # Get current values for exit evaluation
                strategy_name = config.get('name', '').lower()

                # RSI-based exit conditions
                if 'rsi' in df.columns and len(df) > 0:
                    current_rsi = df['rsi'].iloc[-1]

                    # RSI exit conditions for RSI-based strategies
                    if 'rsi' in strategy_name:
                        rsi_long_exit = config.get('rsi_long_exit', 70)
                        rsi_short_exit = config.get('rsi_short_exit', 30)

                        # Long position: exit when RSI reaches overbought
                        if side == 'BUY' and current_rsi >= rsi_long_exit:
                            return {
                                'reason': f'Take Profit (RSI {rsi_long_exit}+)',
                                'type': 'strategy_exit'
                            }

                        # Short position: exit when RSI reaches oversold
                        elif side == 'SELL' and current_rsi <= rsi_short_exit:
                            return {
                                'reason': f'Take Profit (RSI {rsi_short_exit}-)',
                                'type': 'strategy_exit'
                            }

                # Smart Money exit conditions
                elif 'smart_money' in strategy_name and 'sma_20' in df.columns:
                    current_sma20 = df['sma_20'].iloc[-1]

                    # Exit when price crosses back through SMA20
                    if side == 'BUY' and current_price < current_sma20:
                        return {
                            'reason': 'Smart Money Exit (Price < SMA20)',
                            'type': 'strategy_exit'
                        }
                    elif side == 'SELL' and current_price > current_sma20:
                        return {
                            'reason': 'Smart Money Exit (Price > SMA20)',
                            'type': 'strategy_exit'
                        }

            except Exception as e:
                self.logger.error(f"Error in manual exit evaluation: {e}")

            # Fallback to signal processor
            try:
                exit_reason = self.signal_processor.evaluate_exit_conditions(df, position, config)
                if exit_reason:
                    return {
                        'reason': exit_reason,
                        'type': 'strategy_exit'
                    }
            except Exception as e:
                self.logger.error(f"Error in signal processor exit evaluation: {e}")

            return None

        except Exception as e:
            self.logger.error(f"Error checking exit conditions: {e}")
            return None

    def _open_position(self, signal: TradingSignal, price: float, timestamp: datetime, config: Dict[str, Any]) -> Dict[str, Any]:
        """Open a new position"""
        margin = config.get('margin', 50.0)
        leverage = config.get('leverage', 5)

        # Calculate position size - quantity should represent the actual coins/tokens
        # For futures trading: notional_value = margin * leverage, quantity = notional_value / price
        notional_value = margin * leverage
        quantity = notional_value / price

        # Validate position size
        if quantity <= 0:
            raise ValueError(f"Invalid quantity calculated: {quantity}")

        self.logger.info(f"📊 Position Details: Margin=${margin} | Leverage={leverage}x | Notional=${notional_value} | Price=${price} | Qty={quantity:.8f}")

        return {
            'entry_time': timestamp,
            'entry_price': price,
            'side': signal.signal_type.value,
            'quantity': quantity,
            'margin_used': margin,
            'leverage': leverage,
            'notional_value': notional_value,
            'entry_reason': signal.reason,
            'partial_tp_triggered': False
        }

    def _close_position(self, position: Dict, price: float, timestamp: datetime, reason: str) -> Dict[str, Any]:
        """Close position and calculate results"""
        entry_price = position['entry_price']
        quantity = position['quantity']
        side = position['side']
        margin_used = position['margin_used']
        leverage = position['leverage']

        # Calculate PnL in USDT - this is the actual profit/loss
        if side == 'BUY':
            pnl_usdt = (price - entry_price) * quantity
        else:  # SELL
            pnl_usdt = (entry_price - price) * quantity

        # Calculate percentage returns against margin (what trader actually risked)
        pnl_percentage = (pnl_usdt / margin_used) * 100

        # Calculate price change percentage for validation
        if side == 'BUY':
            price_change_pct = ((price - entry_price) / entry_price) * 100
        else:  # SELL
            price_change_pct = ((entry_price - price) / entry_price) * 100

        # Log detailed calculation for debugging
        self.logger.info(f"📊 Trade Calculation Details:")
        self.logger.info(f"   Entry: ${entry_price:.4f} | Exit: ${price:.4f} | Side: {side}")
        self.logger.info(f"   Quantity: {quantity:.8f} | Margin: ${margin_used} | Leverage: {leverage}x")
        self.logger.info(f"   Price Change: {price_change_pct:+.2f}% | PnL: ${pnl_usdt:+.2f} | PnL%: {pnl_percentage:+.2f}%")

        # Calculate duration
        duration = timestamp - position['entry_time']
        duration_minutes = duration.total_seconds() / 60

        return {
            'entry_time': position['entry_time'],
            'exit_time': timestamp,
            'duration_minutes': duration_minutes,
            'entry_price': entry_price,
            'exit_price': price,
            'side': side,
            'quantity': quantity,
            'margin_used': margin_used,
            'leverage': position['leverage'],
            'entry_reason': position['entry_reason'],
            'exit_reason': reason,
            'pnl_usdt': pnl_usdt,
            'pnl_percentage': pnl_percentage,
            'trade_status': 'CLOSED'
        }

    def _calculate_performance(self, trades: List[Dict], config: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate comprehensive performance metrics"""
        if not trades:
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'total_pnl_percentage': 0.0,
                'avg_pnl_per_trade': 0.0,
                'max_win': 0.0,
                'max_loss': 0.0,
                'avg_duration_minutes': 0.0,
                'profitable_trades': 0,
                'losing_trades': 0
            }

        # Basic statistics
        total_trades = len(trades)
        profitable_trades = len([t for t in trades if t['pnl_usdt'] > 0])
        losing_trades = len([t for t in trades if t['pnl_usdt'] < 0])
        break_even_trades = total_trades - profitable_trades - losing_trades

        # PnL statistics
        total_pnl = sum(t['pnl_usdt'] for t in trades)
        total_pnl_percentage = sum(t['pnl_percentage'] for t in trades)
        avg_pnl_per_trade = total_pnl / total_trades
        avg_pnl_percentage = total_pnl_percentage / total_trades

        # Win/Loss statistics
        win_rate = (profitable_trades / total_trades) * 100
        max_win = max(t['pnl_usdt'] for t in trades)
        max_loss = min(t['pnl_usdt'] for t in trades)

        # Duration statistics
        avg_duration = sum(t['duration_minutes'] for t in trades) / total_trades

        # Risk metrics
        margin_per_trade = config.get('margin', 50.0)
        max_loss_pct = config.get('max_loss_pct', 10.0)
        max_risk_per_trade = margin_per_trade * (max_loss_pct / 100)

        # Calculate drawdown
        running_pnl = 0
        peak_pnl = 0
        max_drawdown = 0

        for trade in trades:
            running_pnl += trade['pnl_usdt']
            if running_pnl > peak_pnl:
                peak_pnl = running_pnl
            drawdown = peak_pnl - running_pnl
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        # Sharpe ratio approximation (using trade PnL standard deviation)
        if len(trades) > 1:
            pnl_values = [t['pnl_usdt'] for t in trades]
            pnl_std = np.std(pnl_values)
            sharpe_ratio = avg_pnl_per_trade / pnl_std if pnl_std > 0 else 0
        else:
            sharpe_ratio = 0

        return {
            'total_trades': total_trades,
            'profitable_trades': profitable_trades,
            'losing_trades': losing_trades,
            'break_even_trades': break_even_trades,
            'win_rate': win_rate,
            'total_pnl_usdt': total_pnl,
            'total_pnl_percentage': total_pnl_percentage,
            'avg_pnl_per_trade_usdt': avg_pnl_per_trade,
            'avg_pnl_percentage': avg_pnl_percentage,
            'max_win_usdt': max_win,
            'max_loss_usdt': max_loss,
            'avg_duration_minutes': avg_duration,
            'max_drawdown_usdt': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'max_risk_per_trade': max_risk_per_trade,
            'risk_reward_ratio': abs(max_win / max_loss) if max_loss < 0 else 0,
            'profit_factor': sum(t['pnl_usdt'] for t in trades if t['pnl_usdt'] > 0) / abs(sum(t['pnl_usdt'] for t in trades if t['pnl_usdt'] < 0)) if any(t['pnl_usdt'] < 0 for t in trades) else float('inf')
        }

    def run_comprehensive_backtest(self, test_configs: List[Dict[str, Any]], start_date: str, end_date: str) -> Dict[str, Any]:
        """Run comprehensive backtest for multiple strategies and configurations"""
        self.logger.info(f"🚀 Starting comprehensive backtest")
        self.logger.info(f"📅 Period: {start_date} to {end_date}")
        self.logger.info(f"📊 Testing {len(test_configs)} strategy configurations")

        all_results = []

        for config in test_configs:
            strategy_name = config.get('strategy_name')
            self.logger.info(f"\n🔄 Testing {strategy_name} on {config.get('symbol')} {config.get('timeframe')}")

            result = self.backtest_strategy(strategy_name, config, start_date, end_date)
            all_results.append(result)

        # Generate comprehensive summary
        summary = self._generate_summary_report(all_results)

        return {
            'backtest_period': f"{start_date} to {end_date}",
            'test_configs': test_configs,
            'individual_results': all_results,
            'summary': summary,
            'generated_at': datetime.now().isoformat()
        }

    def _generate_summary_report(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate comprehensive summary report"""
        if not results:
            return {}

        valid_results = [r for r in results if 'error' not in r]

        if not valid_results:
            return {'error': 'No valid backtest results'}

        # Overall statistics
        total_strategies_tested = len(valid_results)
        total_trades_all = sum(len(r.get('trades', [])) for r in valid_results)

        # Aggregate performance
        all_trades = []
        for result in valid_results:
            all_trades.extend(result.get('trades', []))

        if all_trades:
            total_pnl = sum(t['pnl_usdt'] for t in all_trades)
            profitable_trades = len([t for t in all_trades if t['pnl_usdt'] > 0])
            overall_win_rate = (profitable_trades / len(all_trades)) * 100
        else:
            total_pnl = 0
            overall_win_rate = 0

        # Best and worst performing strategies
        strategy_performance = []
        for result in valid_results:
            if result.get('performance'):
                perf = result['performance']
                strategy_performance.append({
                    'strategy_name': result['strategy_name'],
                    'symbol': result['symbol'],
                    'timeframe': result['timeframe'],
                    'total_trades': perf['total_trades'],
                    'win_rate': perf['win_rate'],
                    'total_pnl': perf['total_pnl_usdt'],
                    'avg_pnl_per_trade': perf['avg_pnl_per_trade_usdt'],
                    'max_drawdown': perf['max_drawdown_usdt'],
                    'sharpe_ratio': perf['sharpe_ratio']
                })

        # Sort by total PnL
        strategy_performance.sort(key=lambda x: x['total_pnl'], reverse=True)

        best_strategy = strategy_performance[0] if strategy_performance else None
        worst_strategy = strategy_performance[-1] if strategy_performance else None

        return {
            'total_strategies_tested': total_strategies_tested,
            'total_trades_all_strategies': total_trades_all,
            'overall_pnl_usdt': total_pnl,
            'overall_win_rate': overall_win_rate,
            'best_performing_strategy': best_strategy,
            'worst_performing_strategy': worst_strategy,
            'strategy_rankings': strategy_performance,
            'recommendations': self._generate_recommendations(strategy_performance)
        }

    def _generate_recommendations(self, strategy_performance: List[Dict]) -> List[str]:
        """Generate trading recommendations based on backtest results"""
        recommendations = []

        if not strategy_performance:
            return ["No strategy performance data available for recommendations"]

        # Top performing strategy
        best = strategy_performance[0]
        if best['total_pnl'] > 0:
            recommendations.append(
                f"✅ {best['strategy_name']} on {best['symbol']} ({best['timeframe']}) shows best performance "
                f"with ${best['total_pnl']:.2f} total PnL and {best['win_rate']:.1f}% win rate"
            )

        # Strategies with high win rates
        high_win_rate_strategies = [s for s in strategy_performance if s['win_rate'] >= 60]
        if high_win_rate_strategies:
            recommendations.append(
                f"🎯 Strategies with 60%+ win rate: " + 
                ", ".join([f"{s['strategy_name']} ({s['win_rate']:.1f}%)" for s in high_win_rate_strategies[:3]])
            )

        # Risk warnings
        high_drawdown_strategies = [s for s in strategy_performance if s['max_drawdown'] > 100]
        if high_drawdown_strategies:
            recommendations.append(
                f"⚠️ High risk strategies (>$100 max drawdown): " + 
                ", ".join([f"{s['strategy_name']} (${s['max_drawdown']:.2f})" for s in high_drawdown_strategies[:3]])
            )

        # General recommendations
        profitable_count = len([s for s in strategy_performance if s['total_pnl'] > 0])
        if profitable_count > 0:
            recommendations.append(f"📊 {profitable_count}/{len(strategy_performance)} strategies showed profitability")

        if any(s['sharpe_ratio'] > 1.0 for s in strategy_performance):
            recommendations.append("🏆 Some strategies show excellent risk-adjusted returns (Sharpe > 1.0)")

        return recommendations

    def export_results(self, results: Dict[str, Any], filename: str = None) -> str:
        """Export backtest results to JSON file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"backtest_results_{timestamp}.json"

        # Ensure trading_data directory exists
        os.makedirs("trading_data", exist_ok=True)

        filepath = f"trading_data/{filename}"

        # Convert datetime objects to strings for JSON serialization
        def convert_datetime(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, dict):
                return {k: convert_datetime(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_datetime(item) for item in obj]
            return obj

        serializable_results = convert_datetime(results)

        with open(filepath, 'w') as f:
            json.dump(serializable_results, f, indent=2)

        self.logger.info(f"📁 Results exported to: {filepath}")
        return filepath

class BacktestWebInterface:
    """Web interface for the backtesting system"""

    def __init__(self):
        self.engine = BacktestEngine()

    def get_strategy_templates(self) -> Dict[str, Any]:
        """Get strategy configuration templates for the web interface"""
        return self.engine.strategy_configs

    def run_backtest_from_web(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run backtest from web form data with forced cache clearing"""
        try:
            # FORCE CLEAR ALL CACHES before starting
            import time
            cache_bust_id = str(int(time.time() * 1000))

            print(f"🧹 CACHE BUST ID: {cache_bust_id}")
            print(f"🔄 CLEARING ALL CACHES for fresh backtest")

            # Clear engine caches
            if hasattr(self.engine, '_config_cache'):
                self.engine._config_cache = {}
            if hasattr(self.engine, '_strategy_handler_cache'):
                self.engine._strategy_handler_cache = {}

            # Clear signal processor caches
            if hasattr(self.engine.signal_processor, '_config_cache'):
                self.engine.signal_processor._config_cache = {}
            if hasattr(self.engine.signal_processor, '_strategy_cache'):
                self.engine.signal_processor._strategy_cache = {}

            # Extract required form data
            strategy_name = form_data.get('strategy_name')
            start_date = form_data.get('start_date')
            end_date = form_data.get('end_date')

            if not strategy_name:
                return {'success': False, 'error': 'Strategy name is required'}
            if not start_date:
                return {'success': False, 'error': 'Start date is required'}
            if not end_date:
                return {'success': False, 'error': 'End date is required'}

            # Build configuration starting COMPLETELY FRESH - NO TEMPLATE CACHE
            base_config = {
                'name': strategy_name,
                'cache_bust_id': cache_bust_id  # Add cache busting ID
            }

            # Add minimal required defaults
            template_config = self.engine.strategy_configs.get(strategy_name, {})
            base_config.update(template_config.copy())

            # CRITICAL: Extract symbol and timeframe FIRST from form data
            symbol = form_data.get('symbol', '').strip().upper()
            timeframe = form_data.get('timeframe', '').strip()

            # Set critical fields with validation
            if symbol:
                base_config['symbol'] = symbol
            elif 'symbol' not in base_config or not base_config['symbol']:
                base_config['symbol'] = 'BTCUSDT'  # Default fallback

            if timeframe:
                base_config['timeframe'] = timeframe
            elif 'timeframe' not in base_config or not base_config['timeframe']:
                base_config['timeframe'] = '15m'  # Default fallback

            # DEBUG: Log original template values
            print(f"🔍 ORIGINAL TEMPLATE CONFIG for {strategy_name} | Cache Bust: {cache_bust_id}:")
            for key, value in sorted(base_config.items()):
                print(f"   {key}: {value} (type: {type(value).__name__})")

            # LOG ALL FORM DATA RECEIVED
            print(f"📥 RAW FORM DATA RECEIVED:")
            for key, value in sorted(form_data.items()):
                print(f"   {key}: {value} (type: {type(value).__name__})")

            # Override with form values - FORCE TYPE CONVERSION
            conversion_count = 0
            for key, value in form_data.items():
                if key not in ['strategy_name', 'start_date', 'end_date'] and value is not None:
                    # Clean string values
                    if isinstance(value, str):
                        value = value.strip()
                        if not value:  # Skip empty strings
                            continue

                    # Force type conversion based on parameter type
                    old_value = base_config.get(key, 'NOT_SET')

                    try:
                        # Determine target type and convert
                        if key in ['margin', 'max_loss_pct', 'rsi_long_entry', 'rsi_long_exit', 'rsi_short_entry', 'rsi_short_exit']:
                            base_config[key] = float(value)
                            conversion_count += 1
                        elif key in ['leverage', 'macd_fast', 'macd_slow', 'macd_signal', 'assessment_interval']:
                            base_config[key] = int(value)
                            conversion_count += 1
                        else:
                            base_config[key] = str(value)
                            conversion_count += 1

                        print(f"✅ CONVERTED {key}: {old_value} → {base_config[key]} (type: {type(base_config[key]).__name__})")

                    except (ValueError, TypeError) as e:
                        print(f"⚠️ CONVERSION FAILED for {key}: {value} | Error: {e}")
                        # Don't update if conversion failed

            print(f"🔧 TOTAL CONVERSIONS: {conversion_count} parameters updated")

            # Final validation
            required_fields = ['symbol', 'timeframe', 'margin', 'leverage', 'max_loss_pct']
            missing_fields = []
            for field in required_fields:
                if field not in base_config or base_config[field] is None:
                    missing_fields.append(field)

            if missing_fields:
                return {
                    'success': False,
                    'error': f'Configuration missing required fields: {", ".join(missing_fields)}'
                }

            # DEBUG: Log configuration changes
            print(f"🔍 FORM DATA RECEIVED:")
            for key, value in form_data.items():
                if key not in ['strategy_name', 'start_date', 'end_date'] and value is not None and str(value).strip():
                    print(f"   {key}: {value} (type: {type(value).__name__})")

            # DEBUG: Log final configuration with type verification
            print(f"🔍 FINAL BACKTEST CONFIG for {strategy_name}:")
            for key, value in base_config.items():
                print(f"   {key}: {value} (type: {type(value).__name__})")

            # VERIFY: Check if critical parameters actually changed
            changed_params = []
            original_config = self.engine.strategy_configs.get(strategy_name, {})
            for key in ['margin', 'leverage', 'max_loss_pct', 'rsi_long_entry', 'rsi_short_entry', 'rsi_long_exit', 'rsi_short_exit']:
                if key in base_config and key in original_config:
                    if base_config[key] != original_config[key]:
                        changed_params.append(f"{key}: {original_config[key]} → {base_config[key]}")

            if changed_params:
                print(f"✅ PARAMETERS CHANGED: {', '.join(changed_params)}")
            else:
                print(f"⚠️ NO PARAMETERS CHANGED - using template defaults")

            # Run single strategy backtest
            result = self.engine.backtest_strategy(strategy_name, base_config, start_date, end_date)

            # Check if backtest failed
            if not result.get('success', True) or 'error' in result:
                return {
                    'success': False,
                    'error': result.get('error', 'Backtest execution failed'),
                    'result': result
                }

            # Export results
            try:
                filename = self.engine.export_results({
                    'backtest_type': 'single_strategy',
                    'result': result
                })
            except Exception as export_error:
                print(f"⚠️ Export failed: {export_error}")
                filename = None

            return {
                'success': True,
                'result': result,
                'exported_file': filename
            }

        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': f'Backtest failed: {str(e)}'
            }

# Web interface integration
web_interface = BacktestWebInterface()

if __name__ == "__main__":
    # Example usage
    engine = BacktestEngine()

    # Example configuration
    test_configs = [
        {
            'strategy_name': 'rsi_oversold',
            'symbol': 'BTCUSDT',
            'timeframe': '15m',
            'margin': 50.0,
            'leverage': 5,
            'max_loss_pct': 10.0,
            'rsi_long_entry': 30,
            'rsi_long_exit': 70,
            'rsi_short_entry': 70,
            'rsi_short_exit': 30
        },
        {
            'strategy_name': 'macd_divergence',
            'symbol': 'ETHUSDT',
            'timeframe': '15m',
            'margin': 75.0,
            'leverage': 3,
            'max_loss_pct': 15.0,
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9
        }
    ]

    # Run backtest
    print("🚀 Starting backtest example...")
    results = engine.run_comprehensive_backtest(
        test_configs, 
        start_date="2024-01-01", 
        end_date="2024-01-31"
    )

    # Export results
    filename = engine.export_results(results)
    print(f"✅ Backtest completed! Results saved to: {filename}")