
import pandas as pd
import numpy as np
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from src.strategy_processor.signal_processor import TradingSignal, SignalType

class SmartMoneyStrategy:
    """
    Smart Money Strategy - Trend following with volume confirmation
    
    Entry Conditions:
    - Long: Price above SMA20, RSI < 40, Volume spike
    - Short: Price below SMA20, RSI > 60, Volume spike
    
    Exit Conditions:
    - Price crosses back through SMA20
    - RSI reaches opposite extreme
    """

    def __init__(self, strategy_name: str, config: Dict[str, Any]):
        self.strategy_name = strategy_name
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Extract strategy-specific parameters
        self.sma_period = config.get('sma_period', 20)
        self.ema_period = config.get('ema_period', 50)
        self.rsi_period = config.get('rsi_period', 14)
        self.rsi_long_threshold = config.get('rsi_long_threshold', 40)
        self.rsi_short_threshold = config.get('rsi_short_threshold', 60)
        self.volume_multiplier = config.get('volume_spike_multiplier', 2.0)
        
        self.logger.info(f"🆕 SMART MONEY STRATEGY INITIALIZED: {strategy_name}")
        self.logger.info(f"📊 Config: SMA={self.sma_period}, RSI={self.rsi_period}, Volume={self.volume_multiplier}x")

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all required indicators for the strategy"""
        try:
            if df.empty or len(df) < max(50, self.sma_period + 10):
                return df

            # Calculate SMA
            df['sma_20'] = df['close'].rolling(window=self.sma_period).mean()
            
            # Calculate EMA
            df['ema_50'] = df['close'].ewm(span=self.ema_period).mean()
            
            # Calculate RSI
            df['rsi'] = self._calculate_rsi(df['close'], self.rsi_period)
            
            # Calculate volume average
            df['volume_sma'] = df['volume'].rolling(window=20).mean()
            df['volume_spike'] = df['volume'] > (df['volume_sma'] * self.volume_multiplier)
            
            return df

        except Exception as e:
            self.logger.error(f"Error calculating indicators for {self.strategy_name}: {e}")
            return df

    def _calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate RSI indicator"""
        try:
            delta = prices.diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)
            
            avg_gain = gain.rolling(window=period).mean()
            avg_loss = loss.rolling(window=period).mean()
            
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            return rsi

        except Exception as e:
            self.logger.error(f"Error calculating RSI: {e}")
            return pd.Series([np.nan] * len(prices))

    def evaluate_entry_signal(self, df: pd.DataFrame) -> Optional[TradingSignal]:
        """Evaluate entry conditions for Smart Money strategy"""
        try:
            if df.empty or len(df) < 50:
                return None

            # Check required columns
            required_cols = ['rsi', 'sma_20', 'volume_spike']
            if not all(col in df.columns for col in required_cols):
                return None

            current_price = df['close'].iloc[-1]
            current_rsi = df['rsi'].iloc[-1]
            current_sma20 = df['sma_20'].iloc[-1]
            volume_spike = df['volume_spike'].iloc[-1]

            if pd.isna(current_rsi) or pd.isna(current_sma20):
                return None

            # Calculate position parameters
            margin = self.config.get('margin', 75.0)
            leverage = self.config.get('leverage', 3)
            max_loss_pct = self.config.get('max_loss_pct', 15)
            
            max_loss_amount = margin * (max_loss_pct / 100)
            notional_value = margin * leverage
            stop_loss_pct = (max_loss_amount / notional_value) * 100

            # LONG ENTRY CONDITIONS
            if (current_price > current_sma20 and 
                current_rsi < self.rsi_long_threshold and
                volume_spike):
                
                stop_loss = current_price * (1 - stop_loss_pct / 100)
                take_profit = current_price * 1.04  # 4% target
                
                self.logger.info(f"🟢 SMART MONEY LONG SIGNAL")
                self.logger.info(f"   📊 Price: ${current_price:.4f} > SMA20: ${current_sma20:.4f}")
                self.logger.info(f"   📊 RSI: {current_rsi:.1f} < {self.rsi_long_threshold}")
                self.logger.info(f"   📊 Volume spike: {volume_spike}")
                
                return TradingSignal(
                    signal_type=SignalType.BUY,
                    confidence=0.8,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    symbol=self.config.get('symbol', ''),
                    reason=f"SMART MONEY LONG: Price > SMA20 + RSI {current_rsi:.1f} < {self.rsi_long_threshold} + Volume Spike"
                )

            # SHORT ENTRY CONDITIONS
            elif (current_price < current_sma20 and 
                  current_rsi > self.rsi_short_threshold and
                  volume_spike):
                
                stop_loss = current_price * (1 + stop_loss_pct / 100)
                take_profit = current_price * 0.96  # 4% target
                
                self.logger.info(f"🔴 SMART MONEY SHORT SIGNAL")
                self.logger.info(f"   📊 Price: ${current_price:.4f} < SMA20: ${current_sma20:.4f}")
                self.logger.info(f"   📊 RSI: {current_rsi:.1f} > {self.rsi_short_threshold}")
                self.logger.info(f"   📊 Volume spike: {volume_spike}")
                
                return TradingSignal(
                    signal_type=SignalType.SELL,
                    confidence=0.8,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    symbol=self.config.get('symbol', ''),
                    reason=f"SMART MONEY SHORT: Price < SMA20 + RSI {current_rsi:.1f} > {self.rsi_short_threshold} + Volume Spike"
                )

            return None

        except Exception as e:
            self.logger.error(f"Error evaluating entry signal for {self.strategy_name}: {e}")
            return None

    def evaluate_exit_signal(self, df: pd.DataFrame, position: Dict) -> Optional[str]:
        """Evaluate exit conditions for Smart Money strategy"""
        try:
            if df.empty or 'sma_20' not in df.columns or 'rsi' not in df.columns:
                return None

            current_price = df['close'].iloc[-1]
            current_sma20 = df['sma_20'].iloc[-1]
            current_rsi = df['rsi'].iloc[-1]
            position_side = position.get('side', 'BUY')

            if pd.isna(current_sma20) or pd.isna(current_rsi):
                return None

            # Long position exits
            if position_side == 'BUY':
                # Exit when price crosses below SMA20
                if current_price < current_sma20:
                    self.logger.info(f"🟢→🚪 SMART MONEY LONG EXIT: Price crossed below SMA20")
                    return "Smart Money Exit (Price < SMA20)"
                
                # Exit when RSI reaches high levels
                elif current_rsi >= 70:
                    self.logger.info(f"🟢→🚪 SMART MONEY LONG EXIT: RSI overbought")
                    return "Take Profit (RSI 70+)"

            # Short position exits
            elif position_side == 'SELL':
                # Exit when price crosses above SMA20
                if current_price > current_sma20:
                    self.logger.info(f"🔴→🚪 SMART MONEY SHORT EXIT: Price crossed above SMA20")
                    return "Smart Money Exit (Price > SMA20)"
                
                # Exit when RSI reaches low levels
                elif current_rsi <= 30:
                    self.logger.info(f"🔴→🚪 SMART MONEY SHORT EXIT: RSI oversold")
                    return "Take Profit (RSI 30-)"

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
            current_rsi = df['rsi'].iloc[-1] if 'rsi' in df.columns and not pd.isna(df['rsi'].iloc[-1]) else None
            current_sma20 = df['sma_20'].iloc[-1] if 'sma_20' in df.columns and not pd.isna(df['sma_20'].iloc[-1]) else None
            volume_spike = df['volume_spike'].iloc[-1] if 'volume_spike' in df.columns else False

            status = {
                'price': current_price,
                'rsi': current_rsi,
                'sma_20': current_sma20,
                'volume_spike': volume_spike,
                'price_vs_sma': 'above' if current_sma20 and current_price > current_sma20 else 'below',
                'rsi_long_threshold': self.rsi_long_threshold,
                'rsi_short_threshold': self.rsi_short_threshold
            }

            return status

        except Exception as e:
            self.logger.error(f"Error getting strategy status: {e}")
            return {'status': 'error', 'error': str(e)}
