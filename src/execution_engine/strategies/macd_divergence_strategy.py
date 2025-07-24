import pandas as pd
import numpy as np
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from src.strategy_processor.signal_processor import TradingSignal, SignalType

class MACDDivergenceStrategy:
    """
    MACD Divergence Strategy - Enhanced Pre-crossover Momentum Detection

    Entry Conditions:
    - Bullish: MACD below signal, histogram rising, momentum growing (pre-crossover)
    - Bearish: MACD above signal, histogram falling, momentum dropping (pre-crossover)
    - (Bonus pro entry: optional zero-line rejection entry, if config allows)

    Exit Conditions:
    - Histogram momentum peak or reversal
    - Histogram crosses zero (optional extra safety)
    - Stop loss by config/max_loss_pct
    """

    def __init__(self, config: Dict[str, Any]):
        self.strategy_name = config.get('name', 'macd_divergence')
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Extract strategy-specific parameters
        self.macd_fast = config.get('macd_fast', 12)
        self.macd_slow = config.get('macd_slow', 26)
        self.macd_signal = config.get('macd_signal', 9)
        self.min_histogram_threshold = config.get('min_histogram_threshold', 0.0001)
        self.entry_threshold = config.get('macd_entry_threshold', config.get('min_distance_threshold', 0.0015))
        self.exit_threshold = config.get('macd_exit_threshold', 0.002)
        self.confirmation_candles = config.get('confirmation_candles', 1)

        self.logger.info(f"🆕 MACD DIVERGENCE STRATEGY INITIALIZED: {self.strategy_name}")
        self.logger.info(f"📊 Config: Fast={self.macd_fast}, Slow={self.macd_slow}, Signal={self.macd_signal}")
        self.logger.info(f"🎯 Thresholds: Entry={self.entry_threshold}, Exit={self.exit_threshold}, Histogram={self.min_histogram_threshold}")

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate MACD indicators for the strategy"""
        try:
            if df.empty or len(df) < max(50, self.macd_slow + self.macd_signal):
                return df

            df['ema_fast'] = df['close'].ewm(span=self.macd_fast).mean()
            df['ema_slow'] = df['close'].ewm(span=self.macd_slow).mean()
            df['macd'] = df['ema_fast'] - df['ema_slow']
            df['macd_signal'] = df['macd'].ewm(span=self.macd_signal).mean()
            df['macd_histogram'] = df['macd'] - df['macd_signal']

            return df

        except Exception as e:
            self.logger.error(f"Error calculating MACD indicators for {self.strategy_name}: {e}")
            return df

    def evaluate_entry_signal(self, df):
        """Evaluate if current conditions meet entry criteria with enhanced crossover detection"""
        try:
            if len(df) < max(self.macd_slow, self.confirmation_candles + 5):
                return None

            # Get recent MACD values (check last 3 candles for crossover)
            current_macd = df['macd'].iloc[-1]
            current_signal = df['macd_signal'].iloc[-1]
            current_histogram = df['macd_histogram'].iloc[-1]

            prev_macd = df['macd'].iloc[-2]
            prev_signal = df['macd_signal'].iloc[-2]
            prev_histogram = df['macd_histogram'].iloc[-2]

            # Look back one more candle for stronger confirmation
            prev2_macd = df['macd'].iloc[-3] if len(df) >= 3 else prev_macd
            prev2_signal = df['macd_signal'].iloc[-3] if len(df) >= 3 else prev_signal

            current_price = df['close'].iloc[-1]

            # Enhanced Bullish Crossover Detection
            bullish_crossover = False
            if current_macd > current_signal:  # Currently above signal
                # Check if we just crossed over (within last 2 candles)
                if (prev_macd <= prev_signal or prev2_macd <= prev2_signal):
                    bullish_crossover = True

            # Enhanced Bearish Crossover Detection  
            bearish_crossover = False
            if current_macd < current_signal:  # Currently below signal
                # Check if we just crossed under (within last 2 candles)
                if (prev_macd >= prev_signal or prev2_macd >= prev2_signal):
                    bearish_crossover = True

            # Check histogram threshold and momentum
            histogram_significant = abs(current_histogram) >= self.min_histogram_threshold

            # BULLISH SIGNAL
            if bullish_crossover and histogram_significant:
                # Ensure we have upward momentum
                momentum_building = current_histogram > prev_histogram

                if momentum_building or abs(current_histogram) >= self.entry_threshold:
                    return TradingSignal(
                        signal_type=SignalType.BUY,
                        confidence=0.85,
                        entry_price=current_price,
                        stop_loss=current_price * 0.98,  # 2% stop loss
                        take_profit=current_price * 1.04,  # 4% take profit (2:1 R/R)
                        symbol=self.config.get('symbol', 'BTCUSDT'),
                        reason=f"MACD Bullish Crossover: MACD({current_macd:.6f}) > Signal({current_signal:.6f}), Histogram: {current_histogram:.6f}",
                        strategy_name=self.config.get('name', 'macd_divergence')
                    )

            # BEARISH SIGNAL
            elif bearish_crossover and histogram_significant:
                # Ensure we have downward momentum
                momentum_building = current_histogram < prev_histogram

                if momentum_building or abs(current_histogram) >= self.entry_threshold:
                    return TradingSignal(
                        signal_type=SignalType.SELL,
                        confidence=0.85,
                        entry_price=current_price,
                        stop_loss=current_price * 1.02,  # 2% stop loss
                        take_profit=current_price * 0.96,  # 4% take profit (2:1 R/R)
                        symbol=self.config.get('symbol', 'BTCUSDT'),
                        reason=f"MACD Bearish Crossover: MACD({current_macd:.6f}) < Signal({current_signal:.6f}), Histogram: {current_histogram:.6f}",
                        strategy_name=self.config.get('name', 'macd_divergence')
                    )

            return None

        except Exception as e:
            print(f"❌ Error in MACD entry signal evaluation: {e}")
            return None

    def evaluate_exit_signal(self, df: pd.DataFrame, position: Dict) -> Optional[str]:
        """Evaluate exit conditions for MACD Divergence strategy"""
        try:
            if df.empty or 'macd_histogram' not in df.columns:
                return None

            position_side = position.get('side', 'BUY')
            histogram = df['macd_histogram'].iloc[-3:]

            if len(histogram) < 3:
                return None

            histogram_current = histogram.iloc[-1]
            histogram_prev = histogram.iloc[-2]
            histogram_prev2 = histogram.iloc[-3]
            momentum_change = histogram_current - histogram_prev

            # --- LONG EXIT: Peak detected or histogram crosses zero ---
            if (
                position_side == 'BUY' and (
                    (histogram_prev > histogram_prev2 and histogram_current < histogram_prev and abs(momentum_change) >= self.exit_threshold)
                    or (histogram_current >= 0 and histogram_prev < 0)  # Crosses zero up (bonus protection)
                )
            ):
                self.logger.info(f"🟢→🔴 LONG EXIT: MACD momentum reversal or zero cross")
                return "Take Profit (MACD Peak or Zero Cross)"

            # --- SHORT EXIT: Bottom detected or histogram crosses zero ---
            elif (
                position_side == 'SELL' and (
                    (histogram_prev < histogram_prev2 and histogram_current > histogram_prev and abs(momentum_change) >= self.exit_threshold)
                    or (histogram_current <= 0 and histogram_prev > 0)  # Crosses zero down (bonus protection)
                )
            ):
                self.logger.info(f"🔴→🟢 SHORT EXIT: MACD momentum reversal or zero cross")
                return "Take Profit (MACD Bottom or Zero Cross)"

            return None

        except Exception as e:
            self.logger.error(f"Error evaluating exit signal for {self.strategy_name}: {e}")
            return None

    def get_strategy_status(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Get current strategy status for monitoring"""
        try:
            if df.empty or len(df) < 10:
                return {'status': 'insufficient_data'}

            current_price = df['close'].iloc[-1]
            macd_current = df['macd'].iloc[-1] if 'macd' in df.columns and not pd.isna(df['macd'].iloc[-1]) else None
            signal_current = df['macd_signal'].iloc[-1] if 'macd_signal' in df.columns and not pd.isna(df['macd_signal'].iloc[-1]) else None
            histogram_current = df['macd_histogram'].iloc[-1] if 'macd_histogram' in df.columns and not pd.isna(df['macd_histogram'].iloc[-1]) else None

            status = {
                'price': current_price,
                'macd': macd_current,
                'macd_signal': signal_current,
                'histogram': histogram_current,
                'fast_period': self.macd_fast,
                'slow_period': self.macd_slow,
                'signal_period': self.macd_signal,
                'entry_threshold': self.entry_threshold,
                'exit_threshold': self.exit_threshold
            }

            return status

        except Exception as e:
            self.logger.error(f"Error getting strategy status: {e}")
            return {'status': 'error', 'error': str(e)}