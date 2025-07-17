# Adding the symbol attribute to the TradingSignal dataclass.
import pandas as pd
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

class SignalType(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"

@dataclass
class TradingSignal:
    signal_type: SignalType
    entry_price: float
    stop_loss: float
    take_profit: float
    symbol: str = ""  # Add symbol attribute
    confidence: float = 0.0
    reason: str = ""
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

class SignalProcessor:
    """Processes market data and generates trading signals"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def evaluate_entry_conditions(self, df: pd.DataFrame, strategy_config: Dict) -> Optional[TradingSignal]:
        """Evaluate entry conditions based on strategy"""
        try:
            if df.empty or len(df) < 50:
                return None

            current_price = df['close'].iloc[-1]
            strategy_name = strategy_config.get('name', 'unknown')

            # Route to specific strategy evaluation based on strategy type (not exact name)
            if 'rsi' in strategy_name.lower():
                return self._evaluate_rsi_oversold(df, current_price, strategy_config)
            elif 'macd' in strategy_name.lower():
                return self._evaluate_macd_divergence(df, current_price, strategy_config)
            elif 'liquidity' in strategy_name.lower() or 'reversal' in strategy_name.lower():
                return self._evaluate_liquidity_reversal(df, current_price, strategy_config)
            else:
                self.logger.warning(f"Unknown strategy type: {strategy_name}")
                return None

        except Exception as e:
            self.logger.error(f"Error evaluating entry conditions: {e}")
            return None

    def _evaluate_sma_crossover(self, df: pd.DataFrame, current_price: float, config: Dict) -> Optional[TradingSignal]:
        """SMA Crossover strategy evaluation"""
        try:
            if 'sma_20' not in df.columns or 'sma_50' not in df.columns:
                return None

            sma_20_current = df['sma_20'].iloc[-1]
            sma_50_current = df['sma_50'].iloc[-1]
            sma_20_prev = df['sma_20'].iloc[-2]
            sma_50_prev = df['sma_50'].iloc[-2]

            # Check for bullish crossover
            if (sma_20_prev <= sma_50_prev and sma_20_current > sma_50_current):
                stop_loss = current_price * (1 - config['max_stop_loss'] / 100)
                take_profit = current_price * (1 + config.get('take_profit_pct', 2) / 100)

                return TradingSignal(
                    signal_type=SignalType.BUY,
                    confidence=0.7,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    reason="SMA 20 crossed above SMA 50"
                )

            return None

        except Exception as e:
            self.logger.error(f"Error in SMA crossover evaluation: {e}")
            return None

    def _evaluate_rsi_oversold(self, df: pd.DataFrame, current_price: float, config: Dict) -> Optional[TradingSignal]:
        """RSI strategy evaluation for both long and short signals"""
        try:
            if 'rsi' not in df.columns:
                return None

            rsi_current = df['rsi'].iloc[-1]
            margin = config.get('margin', 50.0)
            leverage = config.get('leverage', 5)
            max_loss_pct = config.get('max_loss_pct', 10)  # 10% of margin

            # Get configurable RSI levels
            rsi_long_entry = config.get('rsi_long_entry', 40)
            rsi_short_entry = config.get('rsi_short_entry', 60)

            # Calculate stop loss based on PnL (10% of margin)
            max_loss_amount = margin * (max_loss_pct / 100)
            notional_value = margin * leverage
            stop_loss_pct = (max_loss_amount / notional_value) * 100

            # Long signal: RSI reaches configured entry level
            if rsi_current <= rsi_long_entry:
                stop_loss = current_price * (1 - stop_loss_pct / 100)
                # Take profit will be determined by RSI level in exit conditions
                take_profit = current_price * 1.05  # Placeholder, real TP is RSI-based

                return TradingSignal(
                    signal_type=SignalType.BUY,
                    confidence=0.8,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    reason=f"RSI LONG ENTRY at {rsi_current:.2f} (RSI <= {rsi_long_entry})"
                )

            # Short signal: RSI reaches configured entry level
            elif rsi_current >= rsi_short_entry:
                stop_loss = current_price * (1 + stop_loss_pct / 100)
                # Take profit will be determined by RSI level in exit conditions
                take_profit = current_price * 0.95  # Placeholder, real TP is RSI-based

                self.logger.info(f"🔍 RSI SHORT SIGNAL CALC | Entry: ${current_price:.4f} | SL%: {stop_loss_pct:.2f}% | SL: ${stop_loss:.4f}")

                return TradingSignal(
                    signal_type=SignalType.SELL,
                    confidence=0.8,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    reason=f"RSI SHORT ENTRY at {rsi_current:.2f} (RSI >= {rsi_short_entry})"
                )

            return None

        except Exception as e:
            self.logger.error(f"Error in RSI strategy evaluation: {e}")
            return None

    def _evaluate_macd_divergence(self, df: pd.DataFrame, current_price: float, config: Dict) -> Optional[TradingSignal]:
        """MACD Divergence strategy evaluation"""
        try:
            if 'macd' not in df.columns or 'macd_signal' not in df.columns or 'macd_histogram' not in df.columns:
                return None

            # Get configuration parameters
            margin = config.get('margin', 50.0)
            leverage = config.get('leverage', 5)
            max_loss_pct = config.get('max_loss_pct', 10)
            min_histogram_threshold = config.get('min_histogram_threshold', 0.0001)
            confirmation_candles = config.get('confirmation_candles', 2)
            min_distance_threshold = config.get('min_distance_threshold', 0.005)

            # Calculate stop loss based on PnL (8% of margin by default)
            max_loss_amount = margin * (max_loss_pct / 100)
            notional_value = margin * leverage
            stop_loss_pct = (max_loss_amount / notional_value) * 100

            # Ensure stop loss percentage is properly bounded
            if stop_loss_pct < 1.0:
                stop_loss_pct = 1.0  # Minimum 1% stop loss
            elif stop_loss_pct > 15.0:
                stop_loss_pct = 15.0  # Maximum 15% stop loss

            # Get recent MACD data
            macd_line = df['macd'].iloc[-confirmation_candles-1:]
            signal_line = df['macd_signal'].iloc[-confirmation_candles-1:]
            histogram = df['macd_histogram'].iloc[-confirmation_candles-1:]

            # Check if we have enough data
            if len(histogram) < confirmation_candles + 1:
                return None

            # Calculate distance between MACD lines (as percentage of price)
            current_distance = abs(macd_line.iloc[-1] - signal_line.iloc[-1]) / current_price

            # Apply distance filter - avoid trading when lines are too close (noisy)
            if current_distance < min_distance_threshold:
                return None

            # Check for bullish divergence (before crossing)
            # MACD line moving toward signal line from below, but hasn't crossed yet
            macd_current = macd_line.iloc[-1]
            macd_prev = macd_line.iloc[-2]
            signal_current = signal_line.iloc[-1]
            signal_prev = signal_line.iloc[-2]
            histogram_current = histogram.iloc[-1]
            histogram_prev = histogram.iloc[-2]

            # Bullish divergence: histogram increasing (but still negative) - approaching cross from below
            if (macd_current < signal_current and  # MACD still below signal (no cross yet)
                histogram_current > histogram_prev and  # Histogram increasing (bullish momentum)
                histogram_current < 0 and  # Still negative (no cross yet)
                abs(histogram_current - histogram_prev) > min_histogram_threshold):  # Significant change

                # Check confirmation over multiple candles
                bullish_confirmation = all(
                    histogram.iloc[i] > histogram.iloc[i-1] 
                    for i in range(-confirmation_candles, 0)
                    if i < 0
                )

                if bullish_confirmation:
                    stop_loss = current_price * (1 - stop_loss_pct / 100)
                    take_profit = current_price * 1.05  # Placeholder, real TP is MACD-based

                    return TradingSignal(
                        signal_type=SignalType.BUY,
                        confidence=0.8,
                        entry_price=current_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        reason=f"MACD BULLISH DIVERGENCE: Histogram increasing {histogram_current:.6f} (approaching cross from below)"
                    )

            # Bearish divergence: histogram decreasing (but still positive) - approaching cross from above
            elif (macd_current > signal_current and  # MACD still above signal (no cross yet)
                  histogram_current < histogram_prev and  # Histogram decreasing (bearish momentum)
                  histogram_current > 0 and  # Still positive (no cross yet)
                  abs(histogram_current - histogram_prev) > min_histogram_threshold):  # Significant change

                # Check confirmation over multiple candles
                bearish_confirmation = all(
                    histogram.iloc[i] < histogram.iloc[i-1] 
                    for i in range(-confirmation_candles, 0)
                    if i < 0
                )

                if bearish_confirmation:
                    stop_loss = current_price * (1 + stop_loss_pct / 100)
                    take_profit = current_price * 0.95  # Placeholder, real TP is MACD-based

                    return TradingSignal(
                        signal_type=SignalType.SELL,
                        confidence=0.8,
                        entry_price=current_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        reason=f"MACD BEARISH DIVERGENCE: Histogram decreasing {histogram_current:.6f} (approaching cross from above)"
                    )

            return None

        except Exception as e:
            self.logger.error(f"Error in MACD divergence evaluation: {e}")
            return None

    def evaluate_exit_conditions(self, df: pd.DataFrame, position: Dict, strategy_config: Dict) -> bool:
        """Evaluate if position should be closed"""
        try:
            current_price = df['close'].iloc[-1]
            entry_price = position['entry_price']
            stop_loss = position['stop_loss']
            take_profit = position['take_profit']
            position_side = position.get('side', 'BUY')
            side = position.get('side')

            # Note: Stop loss is now handled by bot_manager using Binance's actual unrealized PnL
            # This is more accurate than calculating it here with estimated values%)"

            # Strategy-specific exit conditions
            strategy_name = strategy_config.get('name', '')

            # RSI-based exit conditions for any RSI strategy
            if 'rsi' in strategy_name.lower() and 'rsi' in df.columns:
                rsi_current = df['rsi'].iloc[-1]

                # Get configurable RSI exit levels
                rsi_long_exit = strategy_config.get('rsi_long_exit', 70)
                rsi_short_exit = strategy_config.get('rsi_short_exit', 30)

                # Long position: Take profit when RSI reaches configured exit level
                if position_side == 'BUY' and rsi_current >= rsi_long_exit:
                    self.logger.info(f"LONG TAKE PROFIT: RSI {rsi_current:.2f} >= {rsi_long_exit}")
                    return f"Take Profit (RSI {rsi_long_exit}+)"

                # Short position: Take profit when RSI reaches configured exit level
                elif position_side == 'SELL' and rsi_current <= rsi_short_exit:
                    self.logger.info(f"SHORT TAKE PROFIT: RSI {rsi_current:.2f} <= {rsi_short_exit}")
                    return f"Take Profit (RSI {rsi_short_exit}-)"

            # MACD-based exit conditions for any MACD strategy
            elif 'macd' in strategy_name.lower() and 'macd_histogram' in df.columns:
                histogram = df['macd_histogram'].iloc[-2:]  # Get last 2 values

                if len(histogram) >= 2:
                    histogram_current = histogram.iloc[-1]
                    histogram_prev = histogram.iloc[-2]

                    # Long position: Take profit when histogram starts decreasing (diverging bearish)
                    if position_side == 'BUY' and histogram_current < histogram_prev and histogram_current > 0:
                        self.logger.info(f"LONG TAKE PROFIT: MACD histogram decreasing {histogram_current:.6f} (bearish divergence detected)")
                        return "Take Profit (MACD Bearish Divergence)"

                    # Short position: Take profit when histogram starts increasing (diverging bullish)
                    elif position_side == 'SELL' and histogram_current > histogram_prev and histogram_current < 0:
                        self.logger.info(f"SHORT TAKE PROFIT: MACD histogram increasing {histogram_current:.6f} (bullish divergence detected)")
                        return "Take Profit (MACD Bullish Divergence)"

            # Liquidity Reversal exit conditions
            elif ('liquidity' in strategy_name.lower() or 'reversal' in strategy_name.lower()):
                # Get configurable take profit parameters
                profit_method = strategy_config.get('profit_target_method', 'mean_reversion')
                
                # Method 1: Fixed Percentage Target
                if profit_method == 'fixed_percent':
                    fixed_profit_pct = strategy_config.get('fixed_profit_percent', 2.0)
                    
                    if position_side == 'BUY' and current_price >= entry_price * (1 + fixed_profit_pct/100):
                        self.logger.info(f"LONG TAKE PROFIT: Fixed target {fixed_profit_pct}% reached at {current_price:.4f}")
                        return f"Take Profit (Fixed {fixed_profit_pct}%)"
                    elif position_side == 'SELL' and current_price <= entry_price * (1 - fixed_profit_pct/100):
                        self.logger.info(f"SHORT TAKE PROFIT: Fixed target {fixed_profit_pct}% reached at {current_price:.4f}")
                        return f"Take Profit (Fixed {fixed_profit_pct}%)"
                
                # Method 2: Mean Reversion Target (default)
                elif profit_method == 'mean_reversion':
                    mean_reversion_periods = strategy_config.get('mean_reversion_periods', 50)
                    buffer_pct = strategy_config.get('mean_reversion_buffer', 0.5)
                    
                    if len(df) >= mean_reversion_periods:
                        sma = df['close'].tail(mean_reversion_periods).mean()
                        buffer_multiplier = buffer_pct / 100
                        
                        # Long: profit when within buffer of SMA
                        if position_side == 'BUY' and current_price >= sma * (1 - buffer_multiplier):
                            self.logger.info(f"LONG TAKE PROFIT: Mean reversion target reached at {current_price:.4f} (SMA: {sma:.4f})")
                            return "Take Profit (Mean Reversion)"
                        # Short: profit when within buffer of SMA
                        elif position_side == 'SELL' and current_price <= sma * (1 + buffer_multiplier):
                            self.logger.info(f"SHORT TAKE PROFIT: Mean reversion target reached at {current_price:.4f} (SMA: {sma:.4f})")
                            return "Take Profit (Mean Reversion)"
                
                # Method 3: RSI-Based Exit
                elif profit_method == 'rsi_based' and 'rsi' in df.columns:
                    rsi_current = df['rsi'].iloc[-1]
                    rsi_overbought = strategy_config.get('rsi_exit_overbought', 70)
                    rsi_oversold = strategy_config.get('rsi_exit_oversold', 30)
                    
                    if position_side == 'BUY' and rsi_current >= rsi_overbought:
                        self.logger.info(f"LONG TAKE PROFIT: RSI overbought at {rsi_current:.2f}")
                        return f"Take Profit (RSI {rsi_overbought}+)"
                    elif position_side == 'SELL' and rsi_current <= rsi_oversold:
                        self.logger.info(f"SHORT TAKE PROFIT: RSI oversold at {rsi_current:.2f}")
                        return f"Take Profit (RSI {rsi_oversold}-)"
                
                # Method 4: Dynamic Target (based on volatility)
                elif profit_method == 'dynamic':
                    min_profit = strategy_config.get('dynamic_profit_min', 1.0)
                    max_profit = strategy_config.get('dynamic_profit_max', 4.0)
                    
                    # Calculate recent volatility (simplified)
                    if len(df) >= 20:
                        volatility = df['close'].tail(20).std() / df['close'].iloc[-1] * 100
                        # Higher volatility = higher profit target
                        dynamic_target = min(max_profit, max(min_profit, volatility * 2))
                        
                        if position_side == 'BUY' and current_price >= entry_price * (1 + dynamic_target/100):
                            self.logger.info(f"LONG TAKE PROFIT: Dynamic target {dynamic_target:.1f}% reached")
                            return f"Take Profit (Dynamic {dynamic_target:.1f}%)"
                        elif position_side == 'SELL' and current_price <= entry_price * (1 - dynamic_target/100):
                            self.logger.info(f"SHORT TAKE PROFIT: Dynamic target {dynamic_target:.1f}% reached")
                            return f"Take Profit (Dynamic {dynamic_target:.1f}%)"
                
            # Fallback to traditional TP/SL for non-RSI strategies
            elif 'rsi' not in strategy_name.lower():
                if current_price >= take_profit:
                    return "Take Profit"

            return False

        except Exception as e:
            self.logger.error(f"Error evaluating exit conditions: {e}")
            return False

    def _evaluate_liquidity_reversal(self, df: pd.DataFrame, current_price: float, config: Dict) -> Optional[TradingSignal]:
        """Smart Money Liquidity Reversal strategy evaluation"""
        try:
            # Get configuration parameters
            margin = config.get('margin', 50.0)
            leverage = config.get('leverage', 5)
            max_loss_pct = config.get('max_loss_pct', 8.0)
            swing_lookback = config.get('swing_lookback_periods', 20)
            round_number_proximity = config.get('round_number_proximity', 0.002)
            sweep_wick_threshold = config.get('sweep_wick_threshold', 0.005)
            volume_surge_multiplier = config.get('volume_surge_multiplier', 2.0)
            reclaim_candles = config.get('reclaim_candles', 3)
            reclaim_threshold = config.get('reclaim_threshold', 0.001)
            confirmation_timeout = config.get('confirmation_timeout', 5)

            # Calculate stop loss based on margin
            max_loss_amount = margin * (max_loss_pct / 100)
            notional_value = margin * leverage
            stop_loss_pct = (max_loss_amount / notional_value) * 100

            # Ensure we have enough data
            if len(df) < swing_lookback + reclaim_candles:
                return None

            # Step 1: Identify liquidity levels (swing highs/lows + round numbers)
            liquidity_levels = self._identify_liquidity_levels(df, swing_lookback, round_number_proximity)
            
            if not liquidity_levels:
                return None

            # Step 2: Detect liquidity sweeps
            sweep_data = self._detect_liquidity_sweep(df, liquidity_levels, sweep_wick_threshold, volume_surge_multiplier)
            
            if not sweep_data:
                return None

            # Step 3: Check for reversal confirmation
            reversal_confirmed = self._check_reversal_confirmation(df, sweep_data, reclaim_candles, reclaim_threshold, confirmation_timeout)
            
            if not reversal_confirmed:
                return None

            # Step 4: Apply sentiment filtering (simplified - would need funding rate data)
            sentiment_signal = self._apply_sentiment_filter(config, sweep_data['direction'])
            
            if not sentiment_signal:
                return None

            # Generate trading signal
            signal_type = SignalType.BUY if sentiment_signal == 'LONG' else SignalType.SELL
            
            # Calculate stop loss and take profit
            if signal_type == SignalType.BUY:
                stop_loss = current_price * (1 - stop_loss_pct / 100)
                # Target mean reversion (simplified - could use actual MA)
                take_profit = current_price * 1.02  # 2% target
            else:
                stop_loss = current_price * (1 + stop_loss_pct / 100)
                take_profit = current_price * 0.98  # 2% target

            return TradingSignal(
                signal_type=signal_type,
                confidence=0.85,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                reason=f"LIQUIDITY REVERSAL: {sweep_data['level_type']} sweep at {sweep_data['level']:.4f}, reclaimed with {sentiment_signal} sentiment"
            )

        except Exception as e:
            self.logger.error(f"Error in liquidity reversal evaluation: {e}")
            return None

    def _identify_liquidity_levels(self, df: pd.DataFrame, lookback: int, round_proximity: float) -> List[Dict]:
        """Identify key liquidity levels"""
        try:
            levels = []
            
            # Get recent price data
            recent_df = df.tail(lookback + 10)
            
            # Find swing highs and lows
            for i in range(lookback//2, len(recent_df) - lookback//2):
                current_high = recent_df['high'].iloc[i]
                current_low = recent_df['low'].iloc[i]
                
                # Check if it's a swing high
                left_highs = recent_df['high'].iloc[i-lookback//2:i]
                right_highs = recent_df['high'].iloc[i+1:i+lookback//2+1]
                
                if len(left_highs) > 0 and len(right_highs) > 0:
                    if current_high > left_highs.max() and current_high > right_highs.max():
                        levels.append({
                            'level': current_high,
                            'type': 'swing_high',
                            'strength': 1.0
                        })
                
                # Check if it's a swing low
                left_lows = recent_df['low'].iloc[i-lookback//2:i]
                right_lows = recent_df['low'].iloc[i+1:i+lookback//2+1]
                
                if len(left_lows) > 0 and len(right_lows) > 0:
                    if current_low < left_lows.min() and current_low < right_lows.min():
                        levels.append({
                            'level': current_low,
                            'type': 'swing_low',
                            'strength': 1.0
                        })
            
            # Add round number levels
            current_price = df['close'].iloc[-1]
            round_levels = self._get_round_number_levels(current_price, round_proximity)
            levels.extend(round_levels)
            
            return levels[-10:]  # Return most recent 10 levels
            
        except Exception as e:
            self.logger.error(f"Error identifying liquidity levels: {e}")
            return []

    def _get_round_number_levels(self, current_price: float, proximity: float) -> List[Dict]:
        """Get nearby round number levels"""
        try:
            levels = []
            
            # Define round number intervals based on price level
            if current_price > 100000:
                intervals = [1000, 5000, 10000]
            elif current_price > 10000:
                intervals = [100, 500, 1000]
            elif current_price > 1000:
                intervals = [10, 50, 100]
            else:
                intervals = [1, 5, 10]
            
            for interval in intervals:
                # Find nearest round numbers
                lower_round = (current_price // interval) * interval
                upper_round = lower_round + interval
                
                # Check if they're within proximity
                if abs(current_price - lower_round) / current_price <= proximity:
                    levels.append({
                        'level': lower_round,
                        'type': 'round_number',
                        'strength': 0.8
                    })
                
                if abs(current_price - upper_round) / current_price <= proximity:
                    levels.append({
                        'level': upper_round,
                        'type': 'round_number',
                        'strength': 0.8
                    })
            
            return levels
            
        except Exception as e:
            self.logger.error(f"Error getting round number levels: {e}")
            return []

    def _detect_liquidity_sweep(self, df: pd.DataFrame, levels: List[Dict], wick_threshold: float, volume_multiplier: float) -> Optional[Dict]:
        """Detect liquidity sweeps through key levels"""
        try:
            recent_candles = df.tail(5)  # Check last 5 candles
            avg_volume = df['volume'].tail(20).mean()
            
            for _, candle in recent_candles.iterrows():
                candle_high = candle['high']
                candle_low = candle['low']
                candle_close = candle['close']
                candle_volume = candle['volume']
                
                # Check volume surge
                if candle_volume < avg_volume * volume_multiplier:
                    continue
                
                # Check each liquidity level
                for level_data in levels:
                    level = level_data['level']
                    level_type = level_data['type']
                    
                    # Check for upward sweep (through resistance)
                    if candle_high > level * (1 + wick_threshold):
                        # Check if price closed back below the level
                        if candle_close < level * (1 + wick_threshold/2):
                            return {
                                'level': level,
                                'level_type': level_type,
                                'direction': 'sweep_up',
                                'wick_extent': (candle_high - level) / level,
                                'volume_surge': candle_volume / avg_volume,
                                'reclaim_price': level,
                                'swept_candle': candle
                            }
                    
                    # Check for downward sweep (through support)
                    elif candle_low < level * (1 - wick_threshold):
                        # Check if price closed back above the level
                        if candle_close > level * (1 - wick_threshold/2):
                            return {
                                'level': level,
                                'level_type': level_type,
                                'direction': 'sweep_down',
                                'wick_extent': (level - candle_low) / level,
                                'volume_surge': candle_volume / avg_volume,
                                'reclaim_price': level,
                                'swept_candle': candle
                            }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error detecting liquidity sweep: {e}")
            return None

    def _check_reversal_confirmation(self, df: pd.DataFrame, sweep_data: Dict, reclaim_candles: int, reclaim_threshold: float, timeout: int) -> bool:
        """Check for reversal confirmation after liquidity sweep"""
        try:
            level = sweep_data['level']
            direction = sweep_data['direction']
            
            # Get candles after the sweep
            recent_candles = df.tail(min(timeout, len(df)))
            
            confirmed_candles = 0
            
            for _, candle in recent_candles.iterrows():
                if direction == 'sweep_up':
                    # For upward sweep, look for price staying below level (bearish reversal)
                    if candle['close'] < level * (1 - reclaim_threshold):
                        confirmed_candles += 1
                    else:
                        confirmed_candles = 0  # Reset if broken
                        
                elif direction == 'sweep_down':
                    # For downward sweep, look for price staying above level (bullish reversal)
                    if candle['close'] > level * (1 + reclaim_threshold):
                        confirmed_candles += 1
                    else:
                        confirmed_candles = 0  # Reset if broken
                
                # If we have enough confirmation candles
                if confirmed_candles >= reclaim_candles:
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking reversal confirmation: {e}")
            return False

    def _apply_sentiment_filter(self, config: Dict, sweep_direction: str) -> Optional[str]:
        """Apply sentiment filtering (simplified without funding rate data)"""
        try:
            # Simplified sentiment filter - in full implementation would use funding rates
            # For now, we'll use a basic counter-trend approach
            
            if sweep_direction == 'sweep_up':
                # Upward sweep suggests selling pressure, favor shorts
                return 'SHORT'
            elif sweep_direction == 'sweep_down':
                # Downward sweep suggests buying pressure, favor longs
                return 'LONG'
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error applying sentiment filter: {e}")
            return None