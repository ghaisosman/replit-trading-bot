
import pandas as pd
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class SignalType(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"

@dataclass
class TradingSignal:
    signal_type: SignalType
    confidence: float
    entry_price: float
    stop_loss: float
    take_profit: float
    reason: str

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
            
            # Route to specific strategy evaluation
            if strategy_name == 'sma_crossover':
                return self._evaluate_sma_crossover(df, current_price, strategy_config)
            elif strategy_name == 'rsi_oversold':
                return self._evaluate_rsi_oversold(df, current_price, strategy_config)
            else:
                self.logger.warning(f"Unknown strategy: {strategy_name}")
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
        """RSI Oversold strategy evaluation"""
        try:
            if 'rsi' not in df.columns:
                return None
            
            rsi_current = df['rsi'].iloc[-1]
            rsi_oversold_level = config.get('rsi_oversold_level', 30)
            
            # Check for oversold condition
            if rsi_current < rsi_oversold_level:
                stop_loss = current_price * (1 - config['max_stop_loss'] / 100)
                take_profit = current_price * (1 + config.get('take_profit_pct', 3) / 100)
                
                return TradingSignal(
                    signal_type=SignalType.BUY,
                    confidence=0.6,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    reason=f"RSI oversold at {rsi_current:.2f}"
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error in RSI oversold evaluation: {e}")
            return None
    
    def evaluate_exit_conditions(self, df: pd.DataFrame, position: Dict, strategy_config: Dict) -> bool:
        """Evaluate if position should be closed"""
        try:
            current_price = df['close'].iloc[-1]
            entry_price = position['entry_price']
            stop_loss = position['stop_loss']
            take_profit = position['take_profit']
            
            # Check stop loss
            if current_price <= stop_loss:
                return True
            
            # Check take profit
            if current_price >= take_profit:
                return True
            
            # Additional strategy-specific exit logic can be added here
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error evaluating exit conditions: {e}")
            return False
