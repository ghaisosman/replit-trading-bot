
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class TradingParameters:
    """Universal trading parameters that can be applied to any strategy"""
    symbol: str = 'BTCUSDT'
    margin: float = 50.0  # USDT
    leverage: int = 5
    timeframe: str = '15m'
    max_loss_pct: float = 10.0  # Stop loss as % of margin
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'margin': self.margin,
            'leverage': self.leverage,
            'timeframe': self.timeframe,
            'max_loss_pct': self.max_loss_pct
        }

class TradingConfigManager:
    """Manages trading configurations for all strategies"""
    
    def __init__(self):
        # Default parameters for easy modification
        self.default_params = TradingParameters()
        
        # Strategy-specific overrides
        self.strategy_overrides = {
            'sma_crossover': {
                'symbol': 'BTCUSDT',
                'margin': 100.0,
                'leverage': 10,
                'timeframe': '15m'
            },
            'rsi_oversold': {
                'symbol': 'ETHUSDT', 
                'margin': 50.0,
                'leverage': 5,
                'timeframe': '15m'
            },
            'macd_divergence': {
                'symbol': 'BTCUSDT',
                'margin': 50.0,
                'leverage': 5,
                'timeframe': '15m'
            }
        }
    
    def get_strategy_config(self, strategy_name: str, base_config: Dict[str, Any]) -> Dict[str, Any]:
        """Get strategy config with applied trading parameters"""
        # Start with base strategy config
        config = base_config.copy()
        
        # Apply default parameters
        default_params = self.default_params.to_dict()
        
        # Apply strategy-specific overrides
        if strategy_name in self.strategy_overrides:
            strategy_params = self.strategy_overrides[strategy_name]
            default_params.update(strategy_params)
        
        # Update config with trading parameters
        config.update(default_params)
        
        return config
    
    def update_strategy_params(self, strategy_name: str, updates: Dict[str, Any]):
        """Update trading parameters for a specific strategy"""
        if strategy_name not in self.strategy_overrides:
            self.strategy_overrides[strategy_name] = {}
        
        self.strategy_overrides[strategy_name].update(updates)
    
    def update_default_params(self, updates: Dict[str, Any]):
        """Update default trading parameters for all strategies"""
        for key, value in updates.items():
            if hasattr(self.default_params, key):
                setattr(self.default_params, key, value)

# Global config manager instance
trading_config_manager = TradingConfigManager()
