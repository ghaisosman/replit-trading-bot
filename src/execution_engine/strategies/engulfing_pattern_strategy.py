import pandas as pd
import numpy as np
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from src.strategy_processor.signal_processor import TradingSignal, SignalType

class EngulfingPatternStrategy:
    """
    Engulfing Pattern Strategy with RSI and momentum filtering

    Entry Conditions:
    - Bullish: Bullish engulfing + RSI < 50 + Price down over 5 bars + Stable candle
    - Bearish: Bearish engulfing + RSI > 50 + Price up over 5 bars + Stable candle

    Exit Conditions:
    - RSI-based exits (configurable levels)
    - Stop loss based on max loss percentage
    """

    def __init__(self, strategy_name: str, config: Dict[str, Any]):
        self.strategy_name = strategy_name
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Extract strategy-specific parameters
        self.rsi_period = config.get('rsi_period', 14)
        self.rsi_threshold = config.get('rsi_threshold', 50)
        self.stable_candle_ratio = config.get('stable_candle_ratio', 0.2)  # Use relaxed default
        self.price_lookback_bars = config.get('price_lookback_bars', 5)
        self.rsi_long_exit = config.get('rsi_long_exit', 70)
        self.rsi_short_exit = config.get('rsi_short_exit', 30)

        self.logger.info(f"🆕 ENGULFING PATTERN STRATEGY INITIALIZED: {strategy_name}")
        self.logger.info(f"📊 Config: RSI Period={self.rsi_period}, Threshold={self.rsi_threshold}, Stable Ratio={self.stable_candle_ratio}, Lookback={self.price_lookback_bars}")

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all required indicators for the strategy"""
        try:
            if df.empty or len(df) < max(50, self.rsi_period + self.price_lookback_bars + 5):
                self.logger.warning(f"Insufficient data for indicators: {len(df)} rows")
                return df

            # Ensure data is sorted by timestamp
            if 'timestamp' in df.columns:
                df = df.sort_values('timestamp').reset_index(drop=True)

            # Calculate RSI
            df['rsi'] = self._calculate_rsi(df['close'], self.rsi_period)

            # Calculate True Range
            df['true_range'] = self._calculate_true_range(df)

            # Calculate previous candle data
            df['prev_open'] = df['open'].shift(1)
            df['prev_close'] = df['close'].shift(1)
            df['prev_high'] = df['high'].shift(1)
            df['prev_low'] = df['low'].shift(1)

            # Calculate price lookback data
            df[f'close_{self.price_lookback_bars}_ago'] = df['close'].shift(self.price_lookback_bars)

            # Calculate engulfing patterns (only after we have previous candle data)
            df['bullish_engulfing'] = self._detect_bullish_engulfing(df)
            df['bearish_engulfing'] = self._detect_bearish_engulfing(df)

            # Calculate stable candle condition
            df['stable_candle'] = self._detect_stable_candle(df)

            # Log pattern detection results for debugging
            if len(df) > 10:
                recent_bullish = df['bullish_engulfing'].iloc[-10:].sum()
                recent_bearish = df['bearish_engulfing'].iloc[-10:].sum()
                if recent_bullish > 0 or recent_bearish > 0:
                    self.logger.info(f"🔍 Pattern Detection: {recent_bullish} bullish + {recent_bearish} bearish engulfing in last 10 candles")

            return df

        except Exception as e:
            self.logger.error(f"Error calculating indicators for {self.strategy_name}: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return df

    def _calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate RSI indicator with proper Wilder's smoothing"""
        try:
            delta = prices.diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)

            # Use exponential weighted moving average (Wilder's smoothing)
            # Alpha = 1/period for Wilder's smoothing
            alpha = 1.0 / period

            avg_gain = gain.ewm(alpha=alpha, adjust=False).mean()
            avg_loss = loss.ewm(alpha=alpha, adjust=False).mean()

            # Avoid division by zero
            avg_loss = avg_loss.replace(0, np.finfo(float).eps)

            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

            # Ensure RSI is within valid range
            rsi = rsi.clip(0, 100)

            return rsi

        except Exception as e:
            self.logger.error(f"Error calculating RSI: {e}")
            return pd.Series([np.nan] * len(prices))

    def _calculate_true_range(self, df: pd.DataFrame) -> pd.Series:
        """Calculate True Range for stable candle detection"""
        try:
            high_low = df['high'] - df['low']
            high_close_prev = abs(df['high'] - df['close'].shift(1))
            low_close_prev = abs(df['low'] - df['close'].shift(1))

            true_range = pd.concat([high_low, high_close_prev, low_close_prev], axis=1).max(axis=1)

            return true_range

        except Exception as e:
            self.logger.error(f"Error calculating True Range: {e}")
            return pd.Series([np.nan] * len(df))

    def _detect_bullish_engulfing(self, df: pd.DataFrame) -> pd.Series:
        """Detect bullish engulfing pattern"""
        try:
            # Previous candle was bearish (red)
            prev_bearish = df['prev_close'] < df['prev_open']

            # Current candle is bullish (green)
            curr_bullish = df['close'] > df['open']

            # Current candle body completely engulfs previous candle body
            # Current open is below previous close AND current close is above previous open
            body_engulfing = (df['open'] < df['prev_close']) & (df['close'] > df['prev_open'])

            # Additional validation: ensure significant engulfing (further relaxed)
            prev_body_size = abs(df['prev_open'] - df['prev_close'])
            curr_body_size = abs(df['open'] - df['close'])
            significant_engulfing = curr_body_size > (prev_body_size * 0.3)  # Current body at least 30% of previous (further relaxed)

            # Also ensure both candles have meaningful size (more lenient)
            min_body_threshold = df['close'] * 0.0002  # 0.02% of price (more lenient)
            prev_meaningful = prev_body_size > min_body_threshold
            curr_meaningful = curr_body_size > min_body_threshold

            bullish_engulfing = prev_bearish & curr_bullish & body_engulfing & significant_engulfing & prev_meaningful & curr_meaningful

            return bullish_engulfing

        except Exception as e:
            self.logger.error(f"Error detecting bullish engulfing: {e}")
            return pd.Series([False] * len(df))

    def _detect_bearish_engulfing(self, df: pd.DataFrame) -> pd.Series:
        """Detect bearish engulfing pattern"""
        try:
            # Previous candle was bullish (green)
            prev_bullish = df['prev_close'] > df['prev_open']

            # Current candle is bearish (red)
            curr_bearish = df['close'] < df['open']

            # Current candle body completely engulfs previous candle body
            # Current open is above previous close AND current close is below previous open
            body_engulfing = (df['open'] > df['prev_close']) & (df['close'] < df['prev_open'])

            # Additional validation: ensure significant engulfing (further relaxed)
            prev_body_size = abs(df['prev_open'] - df['prev_close'])
            curr_body_size = abs(df['open'] - df['close'])
            significant_engulfing = curr_body_size > (prev_body_size * 0.3)  # Current body at least 30% of previous (further relaxed)

            # Also ensure both candles have meaningful size (more lenient)
            min_body_threshold = df['close'] * 0.0002  # 0.02% of price (more lenient)
            prev_meaningful = prev_body_size > min_body_threshold
            curr_meaningful = curr_body_size > min_body_threshold

            bearish_engulfing = prev_bullish & curr_bearish & body_engulfing & significant_engulfing & prev_meaningful & curr_meaningful

            return bearish_engulfing

        except Exception as e:
            self.logger.error(f"Error detecting bearish engulfing: {e}")
            return pd.Series([False] * len(df))

    def _detect_stable_candle(self, df: pd.DataFrame) -> pd.Series:
        """Detect stable candle based on body-to-range ratio"""
        try:
            candle_body = abs(df['close'] - df['open'])

            # Avoid division by zero
            true_range_safe = df['true_range'].replace(0, np.finfo(float).eps)

            # Calculate body-to-range ratio
            body_ratio = candle_body / true_range_safe

            # Stable candle: body is significant portion of total range
            # Use the configured ratio from strategy config
            stable = body_ratio > self.stable_candle_ratio

            # Additional validation: ensure candle has meaningful size
            min_body_size = df['close'] * 0.0005  # Minimum 0.05% of price (relaxed)
            meaningful_size = candle_body > min_body_size

            stable = stable & meaningful_size

            # Debug logging to track ratio performance
            if len(df) > 0:
                current_ratio = body_ratio.iloc[-1] if not pd.isna(body_ratio.iloc[-1]) else 0
                self.logger.debug(f"Stable candle check: ratio={current_ratio:.3f}, threshold={self.stable_candle_ratio}, stable={stable.iloc[-1] if len(stable) > 0 else False}")

            return stable

        except Exception as e:
            self.logger.error(f"Error detecting stable candle: {e}")
            return pd.Series([False] * len(df))

    def evaluate_entry_signal(self, df: pd.DataFrame) -> Optional[TradingSignal]:
        """Evaluate entry conditions for Engulfing Pattern strategy"""
        try:
            if df.empty or len(df) < max(50, self.rsi_period + self.price_lookback_bars + 2):
                return None

            # Get current values
            current_idx = -1
            current_price = df['close'].iloc[current_idx]
            current_rsi = df['rsi'].iloc[current_idx]

            # Check for valid data
            if pd.isna(current_rsi) or pd.isna(df[f'close_{self.price_lookback_bars}_ago'].iloc[current_idx]):
                return None

            bullish_engulfing = df['bullish_engulfing'].iloc[current_idx]
            bearish_engulfing = df['bearish_engulfing'].iloc[current_idx]
            stable_candle = df['stable_candle'].iloc[current_idx]

            close_5_ago = df[f'close_{self.price_lookback_bars}_ago'].iloc[current_idx]

            # Calculate stop loss parameters
            margin = self.config.get('margin', 50.0)
            leverage = self.config.get('leverage', 5)
            max_loss_pct = self.config.get('max_loss_pct', 10)

            max_loss_amount = margin * (max_loss_pct / 100)
            notional_value = margin * leverage
            stop_loss_pct = (max_loss_amount / notional_value) * 100
            stop_loss_pct = max(1.0, min(stop_loss_pct, 15.0))

            # LONG ENTRY CONDITIONS
            if (bullish_engulfing and 
                stable_candle and 
                current_rsi < self.rsi_threshold and 
                current_price < close_5_ago):

                stop_loss = current_price * (1 - stop_loss_pct / 100)
                take_profit = current_price * 1.05  # Placeholder, will use RSI-based exits

                self.logger.info(f"🟢 ENGULFING LONG SIGNAL | {self.strategy_name}")
                self.logger.info(f"   📊 RSI: {current_rsi:.1f} < {self.rsi_threshold}")
                self.logger.info(f"   📈 Price down over {self.price_lookback_bars} bars: ${current_price:.4f} < ${close_5_ago:.4f}")
                self.logger.info(f"   🕯️ Bullish Engulfing + Stable Candle confirmed")

                return TradingSignal(
                    signal_type=SignalType.BUY,
                    confidence=0.85,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    symbol=self.config.get('symbol', ''),
                    reason=f"ENGULFING LONG: Bullish Engulfing + RSI {current_rsi:.1f} < {self.rsi_threshold} + Price down {self.price_lookback_bars} bars"
                )

            # SHORT ENTRY CONDITIONS
            elif (bearish_engulfing and 
                  stable_candle and 
                  current_rsi > self.rsi_threshold and 
                  current_price > close_5_ago):

                stop_loss = current_price * (1 + stop_loss_pct / 100)
                take_profit = current_price * 0.95  # Placeholder, will use RSI-based exits

                self.logger.info(f"🔴 ENGULFING SHORT SIGNAL | {self.strategy_name}")
                self.logger.info(f"   📊 RSI: {current_rsi:.1f} > {self.rsi_threshold}")
                self.logger.info(f"   📉 Price up over {self.price_lookback_bars} bars: ${current_price:.4f} > ${close_5_ago:.4f}")
                self.logger.info(f"   🕯️ Bearish Engulfing + Stable Candle confirmed")

                return TradingSignal(
                    signal_type=SignalType.SELL,
                    confidence=0.85,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    symbol=self.config.get('symbol', ''),
                    reason=f"ENGULFING SHORT: Bearish Engulfing + RSI {current_rsi:.1f} > {self.rsi_threshold} + Price up {self.price_lookback_bars} bars"
                )

            return None

        except Exception as e:
            self.logger.error(f"Error evaluating entry signal for {self.strategy_name}: {e}")
            return None

    def evaluate_exit_signal(self, df: pd.DataFrame, position: Dict) -> Optional[str]:
        """Evaluate exit conditions for Engulfing Pattern strategy"""
        try:
            if df.empty or 'rsi' not in df.columns:
                return None

            current_rsi = df['rsi'].iloc[-1]
            position_side = position.get('side', 'BUY')

            if pd.isna(current_rsi):
                return None

            # Long position exit: RSI reaches exit level
            if position_side == 'BUY' and current_rsi >= self.rsi_long_exit:
                self.logger.info(f"🟢→🚪 ENGULFING LONG EXIT: RSI {current_rsi:.1f} >= {self.rsi_long_exit}")
                return f"Take Profit (RSI {self.rsi_long_exit}+)"

            # Short position exit: RSI reaches exit level
            elif position_side == 'SELL' and current_rsi <= self.rsi_short_exit:
                self.logger.info(f"🔴→🚪 ENGULFING SHORT EXIT: RSI {current_rsi:.1f} <= {self.rsi_short_exit}")
                return f"Take Profit (RSI {self.rsi_short_exit}-)"

            return None

        except Exception as e:
            self.logger.error(f"Error evaluating exit signal for {self.strategy_name}: {e}")
            return None

    def get_strategy_status(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Get current strategy status for monitoring"""
        try:
            if df.empty or len(df) < 10:
                return {'status': 'insufficient_data'}

            current_rsi = df['rsi'].iloc[-1] if 'rsi' in df.columns and not df['rsi'].iloc[-1] != df['rsi'].iloc[-1] else None
            current_price = df['close'].iloc[-1]

            bullish_engulfing = df['bullish_engulfing'].iloc[-1] if 'bullish_engulfing' in df.columns else False
            bearish_engulfing = df['bearish_engulfing'].iloc[-1] if 'bearish_engulfing' in df.columns else False
            stable_candle = df['stable_candle'].iloc[-1] if 'stable_candle' in df.columns else False

            status = {
                'price': current_price,
                'rsi': current_rsi,
                'bullish_engulfing': bullish_engulfing,
                'bearish_engulfing': bearish_engulfing,
                'stable_candle': stable_candle,
                'rsi_threshold': self.rsi_threshold,
                'lookback_bars': self.price_lookback_bars
            }

            return status

        except Exception as e:
            self.logger.error(f"Error getting strategy status: {e}")
            return {'status': 'error', 'error': str(e)}