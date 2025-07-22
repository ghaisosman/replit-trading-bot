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
            elif 'smart' in strategy_name.lower() and 'money' in strategy_name.lower():
                # Smart Money strategy is handled directly by the strategy class
                # Signal processor doesn't need to generate signals for it
                return None
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
        """MACD Divergence strategy evaluation - FOLLOWS DASHBOARD CONFIGURATION"""
        try:
            if 'macd' not in df.columns or 'macd_signal' not in df.columns or 'macd_histogram' not in df.columns:
                return None

            # Get configuration parameters FROM DASHBOARD
            margin = config.get('margin', 50.0)
            leverage = config.get('leverage', 5)
            max_loss_pct = config.get('max_loss_pct', 10)
            min_histogram_threshold = config.get('min_histogram_threshold', 0.0001)
            confirmation_candles = config.get('confirmation_candles', 1)

            # FIXED: Use correct dashboard parameters
            entry_threshold = config.get('macd_entry_threshold', config.get('min_distance_threshold', 0.0015))
            exit_threshold = config.get('macd_exit_threshold', 0.002)

            self.logger.debug(f"🔧 MACD Config: entry_threshold={entry_threshold}, histogram_threshold={min_histogram_threshold}, confirmation={confirmation_candles}")

            # Calculate stop loss based on PnL
            max_loss_amount = margin * (max_loss_pct / 100)
            notional_value = margin * leverage
            stop_loss_pct = (max_loss_amount / notional_value) * 100

            # Ensure stop loss percentage is properly bounded
            stop_loss_pct = max(1.0, min(stop_loss_pct, 15.0))

            # Get recent MACD data
            lookback_period = confirmation_candles + 3  # Need extra data for trend analysis
            macd_line = df['macd'].iloc[-lookback_period:]
            signal_line = df['macd_signal'].iloc[-lookback_period:]
            histogram = df['macd_histogram'].iloc[-lookback_period:]

            # Check if we have enough data
            if len(histogram) < lookback_period:
                return None

            # Current values
            macd_current = macd_line.iloc[-1]
            signal_current = signal_line.iloc[-1]
            histogram_current = histogram.iloc[-1]

            # Previous values for trend detection
            histogram_prev = histogram.iloc[-2]

            # Calculate momentum strength (histogram change rate)
            histogram_momentum = abs(histogram_current - histogram_prev)

            # Calculate distance between MACD lines (normalized by price for consistency)
            line_distance = abs(macd_current - signal_current) / current_price

            self.logger.debug(f"📊 MACD Analysis: MACD={macd_current:.6f}, Signal={signal_current:.6f}, Histogram={histogram_current:.6f}")
            self.logger.debug(f"📊 Entry Logic: distance={line_distance:.6f} vs threshold={entry_threshold}, momentum={histogram_momentum:.6f} vs {min_histogram_threshold}")

            # YOUR STRATEGY LOGIC: Enter when divergence starts BEFORE crossover

            # BULLISH ENTRY: MACD below signal but gaining momentum (approaching crossover from below)
            if (macd_current < signal_current and  # Still below signal (before crossover)
                histogram_current > histogram_prev and  # Momentum building (divergence starting)
                histogram_current < 0 and  # Still negative (confirms no crossover yet)
                histogram_momentum >= min_histogram_threshold and  # Significant momentum change
                line_distance >= entry_threshold):  # Sufficient separation for meaningful signal

                # Check confirmation over specified candles
                if confirmation_candles > 1:
                    momentum_confirmed = all(
                        histogram.iloc[-i-1] > histogram.iloc[-i-2] 
                        for i in range(confirmation_candles)
                    )
                else:
                    momentum_confirmed = True

                if momentum_confirmed:
                    stop_loss = current_price * (1 - stop_loss_pct / 100)
                    take_profit = current_price * 1.05  # Will be overridden by exit logic

                    self.logger.info(f"🟢 MACD BULLISH ENTRY: Divergence momentum building before crossover")
                    self.logger.info(f"📊 Entry Details: Histogram {histogram_current:.6f} → {histogram_prev:.6f} (momentum: {histogram_momentum:.6f})")

                    return TradingSignal(
                        signal_type=SignalType.BUY,
                        confidence=0.8,
                        entry_price=current_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        reason=f"MACD BULLISH DIVERGENCE: Pre-crossover momentum building (H:{histogram_current:.6f}→{histogram_prev:.6f})"
                    )

            # BEARISH ENTRY: MACD above signal but losing momentum (approaching crossover from above)
            elif (macd_current > signal_current and  # Still above signal (before crossover)
                  histogram_current < histogram_prev and  # Momentum weakening (divergence starting)
                  histogram_current > 0 and  # Still positive (confirms no crossover yet)
                  histogram_momentum >= min_histogram_threshold and  # Significant momentum change
                  line_distance >= entry_threshold):  # Sufficient separation for meaningful signal

                # Check confirmation over specified candles
                if confirmation_candles > 1:
                    momentum_confirmed = all(
                        histogram.iloc[-i-1] < histogram.iloc[-i-2] 
                        for i in range(confirmation_candles)
                    )
                else:
                    momentum_confirmed = True

                if momentum_confirmed:
                    stop_loss = current_price * (1 + stop_loss_pct / 100)
                    take_profit = current_price * 0.95  # Will be overridden by exit logic

                    self.logger.info(f"🔴 MACD BEARISH ENTRY: Divergence momentum building before crossover")
                    self.logger.info(f"📊 Entry Details: Histogram {histogram_current:.6f} → {histogram_prev:.6f} (momentum: {histogram_momentum:.6f})")

                    return TradingSignal(
                        signal_type=SignalType.SELL,
                        confidence=0.8,
                        entry_price=current_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        reason=f"MACD BEARISH DIVERGENCE: Pre-crossover momentum building (H:{histogram_current:.6f}→{histogram_prev:.6f})"
                    )

            return None

        except Exception as e:
            self.logger.error(f"Error in MACD divergence evaluation: {e}")
            return None

    def _evaluate_engulfing_rsi(self, df: pd.DataFrame, current_price: float, config: Dict) -> Optional[TradingSignal]:
        """Engulfing RSI strategy evaluation with validation"""
        try:
            from src.execution_engine.strategies.engulfing_rsi_strategy import EngulfingRSIStrategy

            strategy = EngulfingRSIStrategy(config)
            result = strategy.analyze_market_data(df)

            if result['signal'] in ['BUY', 'SELL']:
                # Validate signal data before creating TradingSignal
                entry_price = result.get('entry_price', 0)
                stop_loss = result.get('stop_loss', 0)
                take_profit = result.get('take_profit', 0)

                if entry_price <= 0:
                    self.logger.error(f"🚨 ENGULFING RSI: Invalid entry price {entry_price}")
                    return None

                if stop_loss <= 0:
                    self.logger.error(f"🚨 ENGULFING RSI: Invalid stop loss {stop_loss}")
                    return None

                if take_profit <= 0:
                    self.logger.error(f"🚨 ENGULFING RSI: Invalid take profit {take_profit}")
                    return None

                signal_type = SignalType.BUY if result['signal'] == 'BUY' else SignalType.SELL

                signal = TradingSignal(
                    signal_type=signal_type,
                    confidence=result['confidence'],
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    reason=result['reason']
                )

                self.logger.info(f"✅ ENGULFING RSI: Valid signal generated - {result['signal']} @ ${entry_price:.4f}")
                return signal

            return None

        except Exception as e:
            self.logger.error(f"Error in Engulfing RSI strategy evaluation: {e}")
            import traceback
            self.logger.error(f"Engulfing RSI error traceback: {traceback.format_exc()}")
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

            # MACD-based exit conditions - FOLLOWS YOUR STRATEGY LOGIC
            elif 'macd' in strategy_name.lower() and 'macd_histogram' in df.columns:
                # Get exit threshold from dashboard configuration
                exit_threshold = strategy_config.get('macd_exit_threshold', 0.002)

                histogram = df['macd_histogram'].iloc[-3:]  # Get last 3 values for better trend detection

                if len(histogram) >= 3:
                    histogram_current = histogram.iloc[-1]
                    histogram_prev = histogram.iloc[-2]
                    histogram_prev2 = histogram.iloc[-3]

                    # Calculate momentum change strength
                    momentum_change = abs(histogram_current - histogram_prev)

                    # YOUR EXIT LOGIC: Exit when divergence starts turning in opposite direction

                    # LONG POSITION EXIT: When bullish momentum starts reversing (peak detection)
                    if (position_side == 'BUY' and 
                        histogram_current < histogram_prev and  # Momentum decreasing
                        histogram_prev > histogram_prev2 and  # Previous was increasing (confirms peak)
                        momentum_change >= exit_threshold):    # Significant change per dashboard config

                        self.logger.info(f"🟢→🔴 LONG TAKE PROFIT: MACD momentum reversing at peak")
                        self.logger.info(f"📊 Exit Details: Histogram peak detected {histogram_prev2:.6f}→{histogram_prev:.6f}→{histogram_current:.6f}")
                        return "Take Profit (MACD Peak - Momentum Reversal)"

                    # SHORT POSITION EXIT: When bearish momentum starts reversing (bottom detection)
                    elif (position_side == 'SELL' and 
                          histogram_current > histogram_prev and  # Momentum increasing
                          histogram_prev < histogram_prev2 and  # Previous was decreasing (confirms bottom)
                          momentum_change >= exit_threshold):    # Significant change per dashboard config

                        self.logger.info(f"🔴→🟢 SHORT TAKE PROFIT: MACD momentum reversing at bottom")
                        self.logger.info(f"📊 Exit Details: Histogram bottom detected {histogram_prev2:.6f}→{histogram_prev:.6f}→{histogram_current:.6f}")
                        return "Take Profit (MACD Bottom - Momentum Reversal)"

            # Fallback to traditional TP/SL for non-RSI strategies
            elif 'rsi' not in strategy_name.lower():
                if current_price >= take_profit:
                    return "Take Profit"

            return False

        except Exception as e:
            self.logger.error(f"Error evaluating exit conditions: {e}")
            return False