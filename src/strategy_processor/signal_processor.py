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

    def _evaluate_liquidity_reversal(self, df: pd.DataFrame, current_price: float, config: Dict) -> Optional[TradingSignal]:
        """Smart Money Liquidity Reversal strategy evaluation"""
        try:
            # Import strategy config
            from src.execution_engine.strategies.liquidity_reversal_config import liquidity_reversal_config
            
            # Identify liquidity levels
            levels = liquidity_reversal_config.identify_liquidity_levels(df)
            
            # Detect liquidity sweep
            sweep_data = liquidity_reversal_config.detect_liquidity_sweep(df, levels)
            
            if not sweep_data:
                return None
            
            # Check if price has reclaimed the level
            if not liquidity_reversal_config.check_reclaim_confirmation(df, sweep_data):
                return None
            
            # Calculate position parameters
            margin = config.get('margin', 50.0)
            leverage = config.get('leverage', 5)
            
            # Calculate entry/exit levels
            trade_params = liquidity_reversal_config.calculate_entry_exit_levels(
                df, sweep_data, margin, leverage
            )
            
            if not trade_params or trade_params.get('risk_reward_ratio', 0) < 1.5:
                return None
            
            # Create trading signal
            signal_type = SignalType.BUY if trade_params['side'] == 'BUY' else SignalType.SELL
            
            return TradingSignal(
                signal_type=signal_type,
                confidence=0.85,
                entry_price=trade_params['entry_price'],
                stop_loss=trade_params['stop_loss'],
                take_profit=trade_params['take_profit'],
                symbol=config.get('symbol', 'BTCUSDT'),
                reason=f"LIQUIDITY REVERSAL: {sweep_data['type']} at {sweep_data['level']:.2f} | R/R: {trade_params['risk_reward_ratio']:.2f}"
            )

        except Exception as e:
            self.logger.error(f"Error in liquidity reversal evaluation: {e}")
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

            # Fallback to traditional TP/SL for non-RSI strategies
            elif 'rsi' not in strategy_name.lower():
                if current_price >= take_profit:
                    return "Take Profit"

            return False

        except Exception as e:
            self.logger.error(f"Error evaluating exit conditions: {e}")
            return False