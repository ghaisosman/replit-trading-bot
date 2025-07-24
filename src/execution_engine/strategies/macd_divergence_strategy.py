
import pandas as pd
import numpy as np
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from src.strategy_processor.signal_processor import TradingSignal, SignalType

class MACDDivergenceStrategy:
    """
    MACD Divergence Strategy - True Pre-crossover Momentum Detection
    
    Strategy Logic:
    - BULLISH ENTRY: MACD below signal but histogram growing (approaching crossover from bottom)
    - BEARISH ENTRY: MACD above signal but histogram shrinking (approaching crossover from top)
    - EXIT: When histogram momentum peaks and starts reversing (before actual crossover)
    
    This catches the momentum BEFORE crossovers happen, not after.
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
        """Evaluate MACD divergence before crossover - catching momentum at the bottom/tip"""
        try:
            if len(df) < max(self.macd_slow, self.confirmation_candles + 5):
                return None

            # Get recent MACD values for divergence analysis
            current_macd = df['macd'].iloc[-1]
            current_signal = df['macd_signal'].iloc[-1]
            current_histogram = df['macd_histogram'].iloc[-1]

            prev_histogram = df['macd_histogram'].iloc[-2]
            prev2_histogram = df['macd_histogram'].iloc[-3] if len(df) >= 3 else prev_histogram

            current_price = df['close'].iloc[-1]

            # Calculate momentum trend in histogram (key for divergence)
            momentum_change = current_histogram - prev_histogram
            momentum_trend = current_histogram - prev2_histogram

            # --- BULLISH DIVERGENCE ENTRY (Before Bullish Crossover) ---
            # MACD still below signal BUT histogram is growing (approaching crossover from bottom)
            if (current_macd < current_signal and  # Still below signal line
                current_histogram < 0 and  # Still negative (below zero)
                momentum_change > 0 and  # Histogram growing
                momentum_trend > 0 and  # Consistent upward trend
                abs(momentum_change) >= self.min_histogram_threshold and  # Significant momentum
                abs(current_histogram) <= self.entry_threshold):  # Close enough to signal for entry

                return TradingSignal(
                    signal_type=SignalType.BUY,
                    confidence=0.85,
                    entry_price=current_price,
                    stop_loss=current_price * 0.98,  # 2% stop loss
                    take_profit=current_price * 1.04,  # 4% take profit (2:1 R/R)
                    symbol=self.config.get('symbol', 'BTCUSDT'),
                    reason=f"MACD Bullish Divergence (Pre-Crossover): Histogram growing from bottom, MACD({current_macd:.6f}) approaching Signal({current_signal:.6f}), Momentum: {momentum_change:.6f}",
                    strategy_name=self.config.get('name', 'macd_divergence')
                )

            # --- BEARISH DIVERGENCE ENTRY (Before Bearish Crossover) ---
            # MACD still above signal BUT histogram is shrinking (approaching crossover from top)
            elif (current_macd > current_signal and  # Still above signal line
                  current_histogram > 0 and  # Still positive (above zero)
                  momentum_change < 0 and  # Histogram shrinking
                  momentum_trend < 0 and  # Consistent downward trend
                  abs(momentum_change) >= self.min_histogram_threshold and  # Significant momentum
                  abs(current_histogram) <= self.entry_threshold):  # Close enough to signal for entry

                return TradingSignal(
                    signal_type=SignalType.SELL,
                    confidence=0.85,
                    entry_price=current_price,
                    stop_loss=current_price * 1.02,  # 2% stop loss
                    take_profit=current_price * 0.96,  # 4% take profit (2:1 R/R)
                    symbol=self.config.get('symbol', 'BTCUSDT'),
                    reason=f"MACD Bearish Divergence (Pre-Crossover): Histogram shrinking from top, MACD({current_macd:.6f}) approaching Signal({current_signal:.6f}), Momentum: {momentum_change:.6f}",
                    strategy_name=self.config.get('name', 'macd_divergence')
                )

            return None

        except Exception as e:
            print(f"❌ Error in MACD divergence signal evaluation: {e}")
            return None

    def evaluate_exit_signal(self, df: pd.DataFrame, position: Dict) -> Optional[str]:
        """Exit when momentum peaks and starts reversing (before crossover happens)"""
        try:
            if df.empty or 'macd_histogram' not in df.columns:
                return None

            position_side = position.get('side', 'BUY')
            histogram = df['macd_histogram'].iloc[-4:]  # Look at last 4 candles

            if len(histogram) < 4:
                return None

            current_hist = histogram.iloc[-1]
            prev_hist = histogram.iloc[-2]
            prev2_hist = histogram.iloc[-3]
            prev3_hist = histogram.iloc[-4]

            # Calculate momentum changes
            current_momentum = current_hist - prev_hist
            prev_momentum = prev_hist - prev2_hist

            # --- LONG EXIT: Peak momentum detected before crossover ---
            if position_side == 'BUY':
                # Exit when histogram momentum peaks and starts declining
                # (This happens BEFORE the actual crossover)
                if (current_hist > 0 and  # We're in positive territory
                    prev_hist > prev2_hist and  # Previous candle was still growing
                    current_momentum < prev_momentum and  # Momentum is slowing
                    abs(current_momentum) >= self.exit_threshold):  # Significant momentum change
                    
                    self.logger.info(f"🟢→🔴 LONG EXIT: MACD momentum peak detected before crossover")
                    return "Take Profit (MACD Momentum Peak)"

            # --- SHORT EXIT: Bottom momentum detected before crossover ---
            elif position_side == 'SELL':
                # Exit when histogram momentum bottoms and starts rising
                # (This happens BEFORE the actual crossover)
                if (current_hist < 0 and  # We're in negative territory
                    prev_hist < prev2_hist and  # Previous candle was still falling
                    current_momentum > prev_momentum and  # Momentum is reversing up
                    abs(current_momentum) >= self.exit_threshold):  # Significant momentum change
                    
                    self.logger.info(f"🔴→🟢 SHORT EXIT: MACD momentum bottom detected before crossover")
                    return "Take Profit (MACD Momentum Bottom)"

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

            # Calculate momentum
            momentum = None
            if 'macd_histogram' in df.columns and len(df) >= 2:
                prev_histogram = df['macd_histogram'].iloc[-2]
                momentum = histogram_current - prev_histogram

            status = {
                'price': current_price,
                'macd': macd_current,
                'macd_signal': signal_current,
                'histogram': histogram_current,
                'momentum': momentum,
                'divergence_status': 'bullish_building' if (macd_current < signal_current and momentum and momentum > 0) else 
                                   'bearish_building' if (macd_current > signal_current and momentum and momentum < 0) else 'neutral',
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
