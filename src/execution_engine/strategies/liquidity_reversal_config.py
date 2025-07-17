
import json
from typing import Dict, Any

class LiquidityReversalConfig:
    """Configuration for Smart Money Liquidity Reversal Strategy"""
    
    def __init__(self):
        self.strategy_name = "LIQUIDITY_REVERSAL"
        self.default_config = {
            "symbol": "BTCUSDT",
            "margin": 50.0,
            "leverage": 5,
            "timeframe": "15m",
            "max_loss_pct": 8.0,
            "assessment_interval": 30,
            "cooldown_period": 300,
            "decimals": 3,
            
            # Liquidity sweep detection parameters
            "swing_lookback_periods": 20,
            "round_number_proximity": 0.002,  # 0.2% proximity to round numbers
            "sweep_wick_threshold": 0.005,    # 0.5% wick beyond level
            "volume_surge_multiplier": 2.0,   # 2x average volume
            
            # Reversal confirmation parameters
            "reclaim_candles": 3,             # Candles to confirm reclaim
            "reclaim_threshold": 0.001,       # 0.1% above/below swept level
            
            # Funding rate sentiment filter
            "funding_bullish_threshold": -0.001,  # -0.1% funding favors longs
            "funding_bearish_threshold": 0.001,   # +0.1% funding favors shorts
            
            # Risk management
            "confirmation_timeout": 5,        # Max candles to wait for confirmation
            "position_sizing_method": "fixed_margin",
            "max_daily_trades": 3,
            
            # Exit conditions
            "profit_target_method": "mean_reversion",  # Options: "fixed_percent", "mean_reversion", "rsi_based", "dynamic"
            "fixed_profit_percent": 2.0,      # Fixed % profit target (when method is "fixed_percent")
            "mean_reversion_periods": 50,     # MA period for mean reversion target
            "mean_reversion_buffer": 0.5,     # % buffer around MA (0.5% = within 0.5% of MA triggers exit)
            "rsi_exit_overbought": 70,        # RSI level for profit taking on longs
            "rsi_exit_oversold": 30,          # RSI level for profit taking on shorts
            "dynamic_profit_min": 1.0,        # Minimum profit % for dynamic targeting
            "dynamic_profit_max": 4.0,        # Maximum profit % for dynamic targeting
            "trailing_stop_enabled": False,   # Enable trailing stop loss
            "trailing_stop_percent": 1.5,     # Trailing stop distance %
            "max_hold_duration": 240,        # Max hold time in minutes
        }
    
    def get_config(self) -> Dict[str, Any]:
        """Get strategy configuration"""
        return self.default_config.copy()
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate strategy configuration"""
        required_keys = [
            'symbol', 'margin', 'leverage', 'timeframe',
            'swing_lookback_periods', 'sweep_wick_threshold',
            'volume_surge_multiplier', 'reclaim_candles'
        ]
        
        for key in required_keys:
            if key not in config:
                return False
        
        # Validate ranges
        if not (1 <= config['leverage'] <= 125):
            return False
        if not (0.1 <= config['margin'] <= 10000):
            return False
        if not (5 <= config['swing_lookback_periods'] <= 100):
            return False
        
        return True
    
    def get_strategy_description(self) -> str:
        """Get strategy description"""
        return """
        Smart Money Liquidity Reversal Strategy
        
        Core Thesis: Exploit retail crowd behavior by trading against stop hunts 
        and fakeouts at high-liquidity inflection points.
        
        Entry Logic:
        1. Detect liquidity sweeps through swing highs/lows or round numbers
        2. Confirm price reclaims the swept level quickly
        3. Filter with funding rate sentiment
        4. Enter counter-trend with tight stops
        
        Exit Logic:
        - Target mean reversion to moving average
        - Stop loss just beyond sweep level
        - Time-based exit if no momentum
        """

# Save default configuration to JSON file
if __name__ == "__main__":
    config = LiquidityReversalConfig()
    
    with open('src/execution_engine/strategies/liquidity_reversal_config_data.json', 'w') as f:
        json.dump({
            "strategy_name": config.strategy_name,
            "description": config.get_strategy_description(),
            "default_config": config.get_config()
        }, f, indent=2)
    
    print("✅ Liquidity Reversal strategy configuration created")
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

class LiquidityReversalConfig:
    """Smart Money Liquidity Reversal Strategy Configuration"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Strategy Parameters
        self.strategy_name = "liquidity_reversal"
        self.lookback_candles = 100  # For identifying swing highs/lows
        self.liquidity_threshold = 0.02  # 2% move to consider a sweep
        self.reclaim_timeout = 5  # Maximum candles to wait for reclaim
        self.min_volume_spike = 1.5  # Volume must be 1.5x average
        
        # Risk Management
        self.max_risk_per_trade = 0.5  # 0.5% of account per trade
        self.stop_loss_buffer = 0.1  # 0.1% beyond the sweep point
        self.profit_target_multiplier = 2.0  # 2:1 reward/risk ratio
        
        # Liquidity Level Detection
        self.swing_strength = 3  # Minimum candles on each side for swing
        self.round_number_levels = [0, 25, 50, 75, 100]  # Round number endings
        
        # Confirmation Requirements
        self.min_wick_ratio = 0.6  # Wick must be 60% of candle body
        self.volume_confirmation = True
        self.funding_filter = True
        self.oi_filter = True
        
    def identify_liquidity_levels(self, df: pd.DataFrame) -> List[float]:
        """Identify key liquidity levels (swing highs/lows, round numbers)"""
        levels = []
        
        # Find swing highs and lows
        highs = df['high'].rolling(window=self.swing_strength*2+1, center=True).max()
        lows = df['low'].rolling(window=self.swing_strength*2+1, center=True).min()
        
        # Swing highs
        swing_highs = df[df['high'] == highs]['high'].dropna().unique()
        levels.extend(swing_highs[-10:])  # Last 10 swing highs
        
        # Swing lows  
        swing_lows = df[df['low'] == lows]['low'].dropna().unique()
        levels.extend(swing_lows[-10:])  # Last 10 swing lows
        
        # Round number levels
        current_price = df['close'].iloc[-1]
        price_range = current_price * 0.1  # 10% range around current price
        
        for level in self.round_number_levels:
            base = int(current_price / 100) * 100
            round_level = base + level
            if abs(round_level - current_price) <= price_range:
                levels.append(round_level)
        
        return sorted(list(set(levels)))
    
    def detect_liquidity_sweep(self, df: pd.DataFrame, levels: List[float]) -> Optional[Dict]:
        """Detect if a liquidity sweep has occurred"""
        if len(df) < 5:
            return None
            
        recent_candles = df.tail(3)  # Check last 3 candles
        
        for i, candle in recent_candles.iterrows():
            high = candle['high']
            low = candle['low']
            open_price = candle['open']
            close = candle['close']
            volume = candle['volume']
            
            # Calculate average volume
            avg_volume = df['volume'].tail(20).mean()
            
            # Check for volume spike
            volume_spike = volume > (avg_volume * self.min_volume_spike)
            
            # Check for significant wick
            body_size = abs(close - open_price)
            upper_wick = high - max(open_price, close)
            lower_wick = min(open_price, close) - low
            
            # Check each liquidity level
            for level in levels:
                # Upward sweep (stop hunt above resistance)
                if (high > level and close < level and 
                    upper_wick > (body_size * self.min_wick_ratio) and 
                    volume_spike):
                    
                    return {
                        'type': 'upward_sweep',
                        'level': level,
                        'sweep_high': high,
                        'close': close,
                        'candle_index': i,
                        'volume_spike': volume_spike,
                        'wick_ratio': upper_wick / body_size if body_size > 0 else float('inf')
                    }
                
                # Downward sweep (stop hunt below support)
                elif (low < level and close > level and 
                      lower_wick > (body_size * self.min_wick_ratio) and 
                      volume_spike):
                    
                    return {
                        'type': 'downward_sweep',
                        'level': level,
                        'sweep_low': low,
                        'close': close,
                        'candle_index': i,
                        'volume_spike': volume_spike,
                        'wick_ratio': lower_wick / body_size if body_size > 0 else float('inf')
                    }
        
        return None
    
    def check_reclaim_confirmation(self, df: pd.DataFrame, sweep_data: Dict) -> bool:
        """Check if price has reclaimed the swept level"""
        if not sweep_data:
            return False
            
        current_price = df['close'].iloc[-1]
        level = sweep_data['level']
        sweep_type = sweep_data['type']
        
        # For upward sweep, we want price to reclaim above the level
        if sweep_type == 'upward_sweep':
            return current_price > level
        
        # For downward sweep, we want price to reclaim below the level
        elif sweep_type == 'downward_sweep':
            return current_price < level
            
        return False
    
    def calculate_entry_exit_levels(self, df: pd.DataFrame, sweep_data: Dict, 
                                   margin: float, leverage: int) -> Dict:
        """Calculate entry, stop loss, and take profit levels"""
        current_price = df['close'].iloc[-1]
        level = sweep_data['level']
        sweep_type = sweep_data['type']
        
        # Calculate position size based on risk
        account_value = margin * leverage
        risk_amount = account_value * (self.max_risk_per_trade / 100)
        
        if sweep_type == 'upward_sweep':
            # Short position after upward sweep
            entry_price = current_price
            stop_loss = sweep_data['sweep_high'] * (1 + self.stop_loss_buffer / 100)
            
            # Calculate position size
            risk_per_unit = stop_loss - entry_price
            position_size = risk_amount / risk_per_unit if risk_per_unit > 0 else 0
            
            # Take profit at mean reversion levels
            take_profit = level * 0.995  # Slightly below the swept level
            
            return {
                'side': 'SELL',
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'position_size': position_size,
                'risk_reward_ratio': abs(take_profit - entry_price) / risk_per_unit if risk_per_unit > 0 else 0
            }
        
        elif sweep_type == 'downward_sweep':
            # Long position after downward sweep
            entry_price = current_price
            stop_loss = sweep_data['sweep_low'] * (1 - self.stop_loss_buffer / 100)
            
            # Calculate position size
            risk_per_unit = entry_price - stop_loss
            position_size = risk_amount / risk_per_unit if risk_per_unit > 0 else 0
            
            # Take profit at mean reversion levels
            take_profit = level * 1.005  # Slightly above the swept level
            
            return {
                'side': 'BUY',
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'position_size': position_size,
                'risk_reward_ratio': abs(take_profit - entry_price) / risk_per_unit if risk_per_unit > 0 else 0
            }
        
        return {}

# Global instance for strategy access
liquidity_reversal_config = LiquidityReversalConfig()
