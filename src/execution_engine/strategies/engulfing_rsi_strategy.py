
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, Tuple
import logging

class EngulfingRSIStrategy:
    """Engulfing Pattern with RSI Strategy
    
    Combines candlestick patterns (bullish/bearish engulfing) with RSI momentum 
    and price trend confirmation using ATR for stable candle detection.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.name = "engulfing_rsi"
        
        # Strategy-specific parameters with defaults
        self.rsi_period = config.get('rsi_period', 14)
        self.rsi_long_entry = config.get('rsi_long_entry', 50)
        self.rsi_short_entry = config.get('rsi_short_entry', 50)
        self.rsi_long_exit = config.get('rsi_long_exit', 60)
        self.rsi_short_exit = config.get('rsi_short_exit', 40)
        
        # ATR parameters
        self.atr_period = config.get('atr_period', 14)
        self.stable_candle_ratio = config.get('stable_candle_ratio', 0.5)
        
        # Lookback parameters
        self.price_lookback_period = config.get('price_lookback_period', 5)
        
        # Exit configuration
        self.use_rsi_exit = config.get('use_rsi_exit', True)
        self.use_pattern_exit = config.get('use_pattern_exit', True)
        
        # Take profit/Stop loss multipliers (based on ATR)
        self.tp_atr_multiplier = config.get('tp_atr_multiplier', 2.5)
        self.sl_atr_multiplier = config.get('sl_atr_multiplier', 2.0)
        
        # Minimum candles required for proper calculation
        self.min_candles_required = max(15, self.rsi_period + 1, self.atr_period + 1, self.price_lookback_period + 2)
        
        self.logger.info(f"🎯 ENGULFING RSI Strategy initialized")
        self.logger.info(f"   📊 RSI Period: {self.rsi_period}")
        self.logger.info(f"   📈 RSI Long Entry: {self.rsi_long_entry}")
        self.logger.info(f"   📉 RSI Short Entry: {self.rsi_short_entry}")
        self.logger.info(f"   📏 ATR Period: {self.atr_period}")
        self.logger.info(f"   🎚️ Stable Candle Ratio: {self.stable_candle_ratio}")
        self.logger.info(f"   🔙 Price Lookback: {self.price_lookback_period}")
        self.logger.info(f"   ⚠️ Min Candles Required: {self.min_candles_required}")

    def calculate_rsi(self, closes: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI indicator"""
        delta = closes.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean()
        return atr

    def is_bullish_engulfing(self, df: pd.DataFrame, index: int) -> bool:
        """Check if current candle is bullish engulfing"""
        if index < 1:
            return False
            
        current = df.iloc[index]
        previous = df.iloc[index - 1]
        
        # Previous candle was bearish (red)
        prev_bearish = previous['close'] < previous['open']
        
        # Current candle is bullish (green)
        curr_bullish = current['close'] > current['open']
        
        # Current candle engulfs previous candle
        engulfs = (current['close'] > previous['open'] and 
                  current['open'] < previous['close'])
        
        return prev_bearish and curr_bullish and engulfs

    def is_bearish_engulfing(self, df: pd.DataFrame, index: int) -> bool:
        """Check if current candle is bearish engulfing"""
        if index < 1:
            return False
            
        current = df.iloc[index]
        previous = df.iloc[index - 1]
        
        # Previous candle was bullish (green)
        prev_bullish = previous['close'] > previous['open']
        
        # Current candle is bearish (red)
        curr_bearish = current['close'] < current['open']
        
        # Current candle engulfs previous candle
        engulfs = (current['close'] < previous['open'] and 
                  current['open'] > previous['close'])
        
        return prev_bullish and curr_bearish and engulfs

    def is_stable_candle(self, df: pd.DataFrame, atr_series: pd.Series, index: int) -> bool:
        """Check if candle is stable using ATR-based calculation"""
        if index >= len(df) or index >= len(atr_series):
            return False
            
        current = df.iloc[index]
        atr_value = atr_series.iloc[index]
        
        if pd.isna(atr_value) or atr_value == 0:
            return False
            
        candle_body = abs(current['close'] - current['open'])
        stability_ratio = candle_body / atr_value
        
        return stability_ratio > self.stable_candle_ratio

    def analyze_market_data(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze market data for entry/exit signals"""
        if len(df) < self.min_candles_required:
            return {
                'signal': 'HOLD',
                'confidence': 0.0,
                'reason': f'Insufficient data: need {self.min_candles_required} candles, got {len(df)}'
            }
        
        # Calculate indicators
        rsi_series = self.calculate_rsi(df['close'], self.rsi_period)
        atr_series = self.calculate_atr(df, self.atr_period)
        
        # Get current values (last candle)
        current_index = len(df) - 1
        current_rsi = rsi_series.iloc[current_index]
        current_atr = atr_series.iloc[current_index]
        current_price = df['close'].iloc[current_index]
        
        # Check if we have enough lookback data
        lookback_index = current_index - self.price_lookback_period
        if lookback_index < 0:
            return {
                'signal': 'HOLD',
                'confidence': 0.0,
                'reason': f'Insufficient lookback data: need {self.price_lookback_period} lookback candles'
            }
        
        price_5_bars_ago = df['close'].iloc[lookback_index]
        
        # Check for engulfing patterns
        bullish_engulfing = self.is_bullish_engulfing(df, current_index)
        bearish_engulfing = self.is_bearish_engulfing(df, current_index)
        
        # Check if current candle is stable
        stable_candle = self.is_stable_candle(df, atr_series, current_index)
        
        # Long entry conditions
        if (bullish_engulfing and 
            stable_candle and 
            current_rsi < self.rsi_long_entry and 
            current_price < price_5_bars_ago):
            
            # Calculate TP/SL levels based on ATR
            tp_level = current_price + (current_atr * self.tp_atr_multiplier)
            sl_level = current_price - (current_atr * self.sl_atr_multiplier)
            
            return {
                'signal': 'BUY',
                'confidence': 0.8,
                'reason': f'Bullish engulfing + stable candle + RSI {current_rsi:.1f} < {self.rsi_long_entry} + price down over 5 bars',
                'entry_price': current_price,
                'take_profit': tp_level,
                'stop_loss': sl_level,
                'rsi': current_rsi,
                'atr': current_atr,
                'pattern': 'bullish_engulfing'
            }
        
        # Short entry conditions
        elif (bearish_engulfing and 
              stable_candle and 
              current_rsi > self.rsi_short_entry and 
              current_price > price_5_bars_ago):
            
            # Calculate TP/SL levels based on ATR
            tp_level = current_price - (current_atr * self.tp_atr_multiplier)
            sl_level = current_price + (current_atr * self.sl_atr_multiplier)
            
            return {
                'signal': 'SELL',
                'confidence': 0.8,
                'reason': f'Bearish engulfing + stable candle + RSI {current_rsi:.1f} > {self.rsi_short_entry} + price up over 5 bars',
                'entry_price': current_price,
                'take_profit': tp_level,
                'stop_loss': sl_level,
                'rsi': current_rsi,
                'atr': current_atr,
                'pattern': 'bearish_engulfing'
            }
        
        return {
            'signal': 'HOLD',
            'confidence': 0.0,
            'reason': f'No entry conditions met. RSI: {current_rsi:.1f}, Bullish Engulfing: {bullish_engulfing}, Bearish Engulfing: {bearish_engulfing}, Stable: {stable_candle}',
            'rsi': current_rsi,
            'atr': current_atr,
            'bullish_engulfing': bullish_engulfing,
            'bearish_engulfing': bearish_engulfing,
            'stable_candle': stable_candle
        }

    def should_exit_position(self, df: pd.DataFrame, position_side: str, entry_data: Dict[str, Any]) -> Dict[str, Any]:
        """Check if position should be exited based on RSI or opposite pattern"""
        if len(df) < self.min_candles_required:
            return {'should_exit': False, 'reason': 'Insufficient data for exit analysis'}
        
        # Calculate indicators
        rsi_series = self.calculate_rsi(df['close'], self.rsi_period)
        atr_series = self.calculate_atr(df, self.atr_period)
        
        current_index = len(df) - 1
        current_rsi = rsi_series.iloc[current_index]
        current_price = df['close'].iloc[current_index]
        
        # RSI-based exit conditions
        if self.use_rsi_exit:
            if position_side == 'LONG' and current_rsi >= self.rsi_long_exit:
                return {
                    'should_exit': True,
                    'reason': f'RSI exit: {current_rsi:.1f} >= {self.rsi_long_exit}',
                    'exit_price': current_price,
                    'exit_type': 'rsi_exit'
                }
            elif position_side == 'SHORT' and current_rsi <= self.rsi_short_exit:
                return {
                    'should_exit': True,
                    'reason': f'RSI exit: {current_rsi:.1f} <= {self.rsi_short_exit}',
                    'exit_price': current_price,
                    'exit_type': 'rsi_exit'
                }
        
        # Pattern-based exit conditions (opposite engulfing pattern)
        if self.use_pattern_exit:
            if position_side == 'LONG' and self.is_bearish_engulfing(df, current_index):
                stable_candle = self.is_stable_candle(df, atr_series, current_index)
                if stable_candle:
                    return {
                        'should_exit': True,
                        'reason': 'Opposite pattern exit: Bearish engulfing with stable candle',
                        'exit_price': current_price,
                        'exit_type': 'pattern_exit'
                    }
            elif position_side == 'SHORT' and self.is_bullish_engulfing(df, current_index):
                stable_candle = self.is_stable_candle(df, atr_series, current_index)
                if stable_candle:
                    return {
                        'should_exit': True,
                        'reason': 'Opposite pattern exit: Bullish engulfing with stable candle',
                        'exit_price': current_price,
                        'exit_type': 'pattern_exit'
                    }
        
        return {
            'should_exit': False,
            'reason': f'No exit conditions met. RSI: {current_rsi:.1f}',
            'current_rsi': current_rsi
        }

    def get_strategy_info(self) -> Dict[str, Any]:
        """Return strategy information and current configuration"""
        return {
            'name': self.name,
            'type': 'Pattern + Momentum',
            'description': 'Engulfing candlestick patterns with RSI momentum confirmation',
            'parameters': {
                'rsi_period': self.rsi_period,
                'rsi_long_entry': self.rsi_long_entry,
                'rsi_short_entry': self.rsi_short_entry,
                'rsi_long_exit': self.rsi_long_exit,
                'rsi_short_exit': self.rsi_short_exit,
                'atr_period': self.atr_period,
                'stable_candle_ratio': self.stable_candle_ratio,
                'price_lookback_period': self.price_lookback_period,
                'tp_atr_multiplier': self.tp_atr_multiplier,
                'sl_atr_multiplier': self.sl_atr_multiplier,
                'use_rsi_exit': self.use_rsi_exit,
                'use_pattern_exit': self.use_pattern_exit,
                'min_candles_required': self.min_candles_required
            }
        }
