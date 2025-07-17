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
    assessment_interval: int = 60  # Market assessment interval in seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'margin': self.margin,
            'leverage': self.leverage,
            'timeframe': self.timeframe,
            'max_loss_pct': self.max_loss_pct,
            'assessment_interval': self.assessment_interval
        }

@dataclass
class TradingConfig:
    """Trading configuration class for web dashboard compatibility"""
    symbol: str = 'BTCUSDT'
    margin: float = 50.0
    leverage: int = 5
    timeframe: str = '15m'
    max_loss_pct: float = 10.0
    assessment_interval: int = 60
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'margin': self.margin,
            'leverage': self.leverage,
            'timeframe': self.timeframe,
            'max_loss_pct': self.max_loss_pct,
            'assessment_interval': self.assessment_interval,
            'enabled': self.enabled
        }

class TradingConfigManager:
    """Manage trading configurations for all strategies"""

    def __init__(self):
        # Default strategy configurations
        self.strategy_overrides = {
            'rsi_oversold': {
                'symbol': 'SOLUSDT',
                'margin': 12.5,
                'leverage': 25,
                'timeframe': '15m',
                'max_loss_pct': 10.0,
                'assessment_interval': 300,
                'enabled': True
            },
            'macd_divergence': {
                'symbol': 'BTCUSDT', 
                'margin': 23.0,
                'leverage': 5,
                'timeframe': '5m',
                'max_loss_pct': 10.0,
                'assessment_interval': 300,
                'enabled': True
            }
        }

    def get_all_strategies(self) -> Dict[str, Dict[str, Any]]:
        """Get all strategy configurations"""
        return self.strategy_overrides.copy()

    def get_strategy_config(self, strategy_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific strategy"""
        return self.strategy_overrides.get(strategy_name)

    def update_strategy_params(self, strategy_name: str, updates: Dict[str, Any]):
        """Update strategy parameters"""
        if strategy_name not in self.strategy_overrides:
            self.strategy_overrides[strategy_name] = {}

        self.strategy_overrides[strategy_name].update(updates)

        # Ensure required fields exist
        defaults = {
            'enabled': True,
            'symbol': 'BTCUSDT',
            'margin': 50.0,
            'leverage': 5,
            'timeframe': '15m',
            'max_loss_pct': 10.0,
            'assessment_interval': 300
        }

        for key, default_value in defaults.items():
            if key not in self.strategy_overrides[strategy_name]:
                self.strategy_overrides[strategy_name][key] = default_value

    def add_strategy(self, strategy_name: str, config: Dict[str, Any]):
        """Add a new strategy configuration"""
        self.strategy_overrides[strategy_name] = config

    def remove_strategy(self, strategy_name: str):
        """Remove a strategy configuration"""
        if strategy_name in self.strategy_overrides:
            del self.strategy_overrides[strategy_name]

    def get_strategy_symbols(self) -> list:
        """Get all symbols being traded"""
        return [config.get('symbol', 'BTCUSDT') for config in self.strategy_overrides.values()]

# Global instance
trading_config_manager = TradingConfigManager()