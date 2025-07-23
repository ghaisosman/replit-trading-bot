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

        self.logger.info(f"🆕 MACD DIVERGENCE STRATEGY INITIALIZED: {strategy_name}")
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

    def evaluate_entry_signal(self, df: pd.DataFrame) -> Optional[TradingSignal]:
        """Evaluate entry conditions for MACD Divergence strategy"""
        try:
            if df.empty or len(df) < 50:
                return None

            if 'macd' not in df.columns or 'macd_signal' not in df.columns or 'macd_histogram' not in df.columns:
                return None

            current_price = df['close'].iloc[-1]
            margin = self.config.get('margin', 50.0)
            leverage = self.config.get('leverage', 5)
            max_loss_pct = self.config.get('max_loss_pct', 10)
            max_loss_amount = margin * (max_loss_pct / 100)
            notional_value = margin * leverage
            stop_loss_pct = (max_loss_amount / notional_value) * 100
            stop_loss_pct = max(1.0, min(stop_loss_pct, 15.0))

            lookback_period = self.confirmation_candles + 3
            macd_line = df['macd'].iloc[-lookback_period:]
            signal_line = df['macd_signal'].iloc[-lookback_period:]
            histogram = df['macd_histogram'].iloc[-lookback_period:]

            if len(histogram) < lookback_period:
                return None

            macd_current = macd_line.iloc[-1]
            signal_current = signal_line.iloc[-1]
            histogram_current = histogram.iloc[-1]
            histogram_prev = histogram.iloc[-2]
            line_distance = abs(macd_current - signal_current) / current_price
            histogram_momentum = histogram_current - histogram_prev

            # --- BULLISH ENTRY: Pre-crossover momentum and divergence ---
            if (
                macd_current < signal_current and  # Still below signal (pre-crossover)
                histogram_current > histogram_prev and  # Momentum up
                histogram_current < 0 and  # Still negative
                abs(histogram_momentum) >= self.min_histogram_threshold and
                line_distance >= self.entry_threshold
            ):
                # Optional: Confirm momentum over multiple candles
                momentum_confirmed = True
                if self.confirmation_candles > 1:
                    for i in range(self.confirmation_candles):
                        if histogram.iloc[-i-1] <= histogram.iloc[-i-2]:
                            momentum_confirmed = False
                            break
                if momentum_confirmed:
                    stop_loss = current_price * (1 - stop_loss_pct / 100)
                    take_profit = current_price * 1.05  # Placeholder; TP is handled elsewhere
                    self.logger.info(f"🟢 MACD BULLISH ENTRY: Pre-crossover divergence, histogram rising")
                    return TradingSignal(
                        signal_type=SignalType.BUY,
                        confidence=0.8,
                        entry_price=current_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        symbol=self.config.get('symbol', ''),
                        reason=f"MACD BULLISH PRE-CROSS: Histogram rising ({histogram_current:.6f}→{histogram_prev:.6f})"
                    )

            # --- BEARISH ENTRY: Pre-crossover momentum and divergence ---
            elif (
                macd_current > signal_current and
                histogram_current < histogram_prev and
                histogram_current > 0 and
                abs(histogram_momentum) >= self.min_histogram_threshold and
                line_distance >= self.entry_threshold
            ):
                momentum_confirmed = True
                if self.confirmation_candles > 1:
                    for i in range(self.confirmation_candles):
                        if histogram.iloc[-i-1] >= histogram.iloc[-i-2]:
                            momentum_confirmed = False
                            break
                if momentum_confirmed:
                    stop_loss = current_price * (1 + stop_loss_pct / 100)
                    take_profit = current_price * 0.95  # Placeholder
                    self.logger.info(f"🔴 MACD BEARISH ENTRY: Pre-crossover divergence, histogram falling")
                    return TradingSignal(
                        signal_type=SignalType.SELL,
                        confidence=0.8,
                        entry_price=current_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        symbol=self.config.get('symbol', ''),
                        reason=f"MACD BEARISH PRE-CROSS: Histogram falling ({histogram_current:.6f}→{histogram_prev:.6f})"
                    )

            return None

        except Exception as e:
            self.logger.error(f"Error evaluating entry signal for {self.strategy_name}: {e}")
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
