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

    def evaluate_entry_signal(self, df: pd.DataFrame) -> Optional[TradingSignal]:
        """Evaluate entry conditions for MACD Divergence strategy - Fixed crossover detection"""
        try:
            if df.empty or len(df) < 50:
                return None

            # Calculate indicators if not present
            if 'macd' not in df.columns:
                df = self.calculate_indicators(df)
                
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

            # Get recent data (need at least 2 candles for crossover detection)
            if len(df) < 2:
                return None

            # Current values
            macd_current = df['macd'].iloc[-1]
            signal_current = df['macd_signal'].iloc[-1]
            histogram_current = df['macd_histogram'].iloc[-1]
            
            # Previous values
            macd_prev = df['macd'].iloc[-2]
            signal_prev = df['macd_signal'].iloc[-2]
            histogram_prev = df['macd_histogram'].iloc[-2]

            # Check for NaN values
            if pd.isna(macd_current) or pd.isna(signal_current) or pd.isna(macd_prev) or pd.isna(signal_prev):
                return None

            self.logger.info(f"🔍 MACD Crossover Check:")
            self.logger.info(f"   Current: MACD={macd_current:.6f}, Signal={signal_current:.6f}, Histogram={histogram_current:.6f}")
            self.logger.info(f"   Previous: MACD={macd_prev:.6f}, Signal={signal_prev:.6f}, Histogram={histogram_prev:.6f}")
            self.logger.info(f"   Data Length: {len(df)}, Close Price: ${current_price:.2f}")
            self.logger.info(f"   Config Thresholds: Histogram={self.min_histogram_threshold}, Entry={self.entry_threshold}")

            # --- BULLISH CROSSOVER: MACD crosses above Signal ---
            bullish_cross = (macd_prev <= signal_prev and macd_current > signal_current)
            crossover_distance = abs(macd_current - signal_current)
            distance_meets_threshold = crossover_distance >= self.min_histogram_threshold
            
            # Additional momentum confirmation for better signal quality
            momentum_building = histogram_current > histogram_prev if not pd.isna(histogram_prev) else True
            
            self.logger.info(f"   Bullish Cross Check: {bullish_cross} (prev: {macd_prev:.6f} <= {signal_prev:.6f}, curr: {macd_current:.6f} > {signal_current:.6f})")
            self.logger.info(f"   Crossover Distance: {crossover_distance:.6f}")
            self.logger.info(f"   Distance Threshold Check: {distance_meets_threshold} ({crossover_distance:.6f} > {self.min_histogram_threshold})")
            
            if bullish_cross and distance_meets_threshold and momentum_building:
                stop_loss = current_price * (1 - stop_loss_pct / 100)
                take_profit = current_price * 1.05
                
                self.logger.info(f"🟢 MACD BULLISH CROSSOVER DETECTED!")
                self.logger.info(f"   MACD crossed from {macd_prev:.6f} to {macd_current:.6f}")
                self.logger.info(f"   Signal: {signal_prev:.6f} to {signal_current:.6f}")
                self.logger.info(f"   Histogram: {histogram_current:.6f} (threshold: {self.min_histogram_threshold})")
                
                return TradingSignal(
                    signal_type=SignalType.BUY,
                    confidence=0.8,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    symbol=self.config.get('symbol', ''),
                    reason=f"MACD BULLISH CROSSOVER: MACD {macd_current:.6f} > Signal {signal_current:.6f}",
                    strategy_name=self.strategy_name
                )

            # --- BEARISH CROSSOVER: MACD crosses below Signal ---
            bearish_cross = (macd_prev >= signal_prev and macd_current < signal_current)
            crossover_distance_bear = abs(macd_current - signal_current)
            distance_meets_threshold_bear = crossover_distance_bear >= self.min_histogram_threshold
            
            # Additional momentum confirmation for better signal quality
            momentum_declining = histogram_current < histogram_prev if not pd.isna(histogram_prev) else True
            
            self.logger.info(f"   Bearish Cross Check: {bearish_cross} (prev: {macd_prev:.6f} >= {signal_prev:.6f}, curr: {macd_current:.6f} < {signal_current:.6f})")
            self.logger.info(f"   Bearish Crossover Distance: {crossover_distance_bear:.6f}")
            self.logger.info(f"   Bearish Distance Threshold Check: {distance_meets_threshold_bear} ({crossover_distance_bear:.6f} > {self.min_histogram_threshold})")
            
            if bearish_cross and distance_meets_threshold_bear and momentum_declining:
                stop_loss = current_price * (1 + stop_loss_pct / 100)
                take_profit = current_price * 0.95
                
                self.logger.info(f"🔴 MACD BEARISH CROSSOVER DETECTED!")
                self.logger.info(f"   MACD crossed from {macd_prev:.6f} to {macd_current:.6f}")
                self.logger.info(f"   Signal: {signal_prev:.6f} to {signal_current:.6f}")
                self.logger.info(f"   Histogram: {histogram_current:.6f} (threshold: {self.min_histogram_threshold})")
                
                return TradingSignal(
                    signal_type=SignalType.SELL,
                    confidence=0.8,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    symbol=self.config.get('symbol', ''),
                    reason=f"MACD BEARISH CROSSOVER: MACD {macd_current:.6f} < Signal {signal_current:.6f}",
                    strategy_name=self.strategy_name
                )

            self.logger.info(f"   No crossover detected (Bullish: {bullish_cross}, Bearish: {bearish_cross})")
            return None

        except Exception as e:
            self.logger.error(f"Error evaluating entry signal for {self.strategy_name}: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
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