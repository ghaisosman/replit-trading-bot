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
    strategy_name: str = ""  # Add strategy_name parameter
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
            if 'rsi' in strategy_name.lower() and 'engulfing' not in strategy_name.lower():
                return self._evaluate_rsi_oversold(df, current_price, strategy_config)
            elif 'macd' in strategy_name.lower():
                return self._evaluate_macd_divergence(df, current_price, strategy_config)
            elif 'engulfing' in strategy_name.lower():
                return self._evaluate_engulfing_pattern(df, current_price, strategy_config)
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
                self.logger.warning("❌ RSI column not found in dataframe")
                return None

            rsi_current = df['rsi'].iloc[-1]
            margin = config.get('margin', 50.0)
            leverage = config.get('leverage', 5)
            max_loss_pct = config.get('max_loss_pct', 5)

            # Get configurable RSI levels with validation
            rsi_long_entry = config.get('rsi_long_entry', 30)
            rsi_short_entry = config.get('rsi_short_entry', 70)
            rsi_long_exit = config.get('rsi_long_exit', 70)
            rsi_short_exit = config.get('rsi_short_exit', 30)

            # Log current configuration for debugging
            self.logger.info(f"🔍 RSI SIGNAL EVALUATION:")
            self.logger.info(f"   Current RSI: {rsi_current:.2f}")
            self.logger.info(f"   Long Entry: {rsi_long_entry} | Long Exit: {rsi_long_exit}")
            self.logger.info(f"   Short Entry: {rsi_short_entry} | Short Exit: {rsi_short_exit}")
            self.logger.info(f"   Margin: {margin} | Leverage: {leverage} | Max Loss: {max_loss_pct}%")

            # Validate configuration logic
            if rsi_long_entry >= 50:
                self.logger.error(f"❌ INVALID CONFIG: RSI Long Entry ({rsi_long_entry}) should be < 50 for oversold")
                return None
                
            if rsi_short_entry <= 50:
                self.logger.error(f"❌ INVALID CONFIG: RSI Short Entry ({rsi_short_entry}) should be > 50 for overbought")
                return None

            # Calculate stop loss based on margin percentage
            max_loss_amount = margin * (max_loss_pct / 100)
            notional_value = margin * leverage
            stop_loss_pct = (max_loss_amount / notional_value) * 100

            # Long signal: RSI reaches oversold level (truly oversold)
            if rsi_current <= rsi_long_entry:
                stop_loss = current_price * (1 - stop_loss_pct / 100)
                take_profit = current_price * 1.05  # Placeholder, real TP is RSI-based

                self.logger.info(f"✅ RSI LONG SIGNAL GENERATED:")
                self.logger.info(f"   RSI {rsi_current:.2f} <= {rsi_long_entry} (OVERSOLD)")
                self.logger.info(f"   Entry: ${current_price:.4f} | SL: ${stop_loss:.4f} | SL%: {stop_loss_pct:.2f}%")

                return TradingSignal(
                    signal_type=SignalType.BUY,
                    confidence=0.8,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    reason=f"RSI OVERSOLD ENTRY at {rsi_current:.2f} (RSI <= {rsi_long_entry})"
                )

            # Short signal: RSI reaches overbought level (truly overbought)
            elif rsi_current >= rsi_short_entry:
                stop_loss = current_price * (1 + stop_loss_pct / 100)
                take_profit = current_price * 0.95  # Placeholder, real TP is RSI-based

                self.logger.info(f"✅ RSI SHORT SIGNAL GENERATED:")
                self.logger.info(f"   RSI {rsi_current:.2f} >= {rsi_short_entry} (OVERBOUGHT)")
                self.logger.info(f"   Entry: ${current_price:.4f} | SL: ${stop_loss:.4f} | SL%: {stop_loss_pct:.2f}%")

                return TradingSignal(
                    signal_type=SignalType.SELL,
                    confidence=0.8,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    reason=f"RSI OVERBOUGHT ENTRY at {rsi_current:.2f} (RSI >= {rsi_short_entry})"
                )

            else:
                # Log why no signal was generated
                self.logger.debug(f"🔍 RSI NO SIGNAL: {rsi_current:.2f} (between {rsi_long_entry} and {rsi_short_entry})")

            return None

        except Exception as e:
            self.logger.error(f"Error in RSI strategy evaluation: {e}")
            return None

    def _evaluate_macd_divergence(self, df: pd.DataFrame, current_price: float, config: Dict) -> Optional[TradingSignal]:
        """MACD Divergence strategy evaluation - Uses dedicated strategy class"""
        try:
            from src.execution_engine.strategies.macd_divergence_strategy import MACDDivergenceStrategy

            strategy = MACDDivergenceStrategy(config)

            # Calculate indicators
            df_with_indicators = strategy.calculate_indicators(df.copy())

            # Evaluate signal
            signal = strategy.evaluate_entry_signal(df_with_indicators)

            return signal

        except Exception as e:
            self.logger.error(f"Error in MACD divergence evaluation: {e}")
            return None

    def _evaluate_engulfing_pattern(self, df: pd.DataFrame, current_price: float, config: Dict) -> Optional[TradingSignal]:
        """Engulfing Pattern strategy evaluation"""
        try:
            from src.execution_engine.strategies.engulfing_pattern_strategy import EngulfingPatternStrategy

            strategy_name = config.get('name', 'engulfing_pattern')
            strategy = EngulfingPatternStrategy(strategy_name, config)

            # Calculate indicators
            df_with_indicators = strategy.calculate_indicators(df.copy())

            # Evaluate signal
            signal = strategy.evaluate_entry_signal(df_with_indicators)

            return signal

        except Exception as e:
            self.logger.error(f"Error in Engulfing Pattern evaluation: {e}")
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

            # RSI-based exit conditions for RSI strategies (excluding engulfing)
            if 'rsi' in strategy_name.lower() and 'engulfing' not in strategy_name.lower() and 'rsi' in df.columns:
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

            # Engulfing Pattern exit conditions
            elif 'engulfing' in strategy_name.lower():
                try:
                    from src.execution_engine.strategies.engulfing_pattern_strategy import EngulfingPatternStrategy

                    strategy = EngulfingPatternStrategy(strategy_name, strategy_config)
                    exit_reason = strategy.evaluate_exit_signal(df, position)

                    if exit_reason:
                        return exit_reason

                except Exception as e:
                    self.logger.error(f"Error in Engulfing Pattern exit evaluation: {e}")

            # MACD-based exit conditions - Uses dedicated strategy class
            elif 'macd' in strategy_name.lower():
                try:
                    from src.execution_engine.strategies.macd_divergence_strategy import MACDDivergenceStrategy

                    strategy = MACDDivergenceStrategy(strategy_config)
                    exit_reason = strategy.evaluate_exit_signal(df, position)

                    if exit_reason:
                        return exit_reason

                except Exception as e:
                    self.logger.error(f"Error in MACD exit evaluation: {e}")

            # Fallback to traditional TP/SL for non-RSI strategies
            elif 'rsi' not in strategy_name.lower():
                if current_price >= take_profit:
                    return "Take Profit"

            return False

        except Exception as e:
            self.logger.error(f"Error evaluating exit conditions: {e}")
            return False