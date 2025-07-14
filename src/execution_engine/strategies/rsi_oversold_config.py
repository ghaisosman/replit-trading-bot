
from typing import Dict, Any

class RSIOversoldConfig:
    """Configuration for RSI Oversold strategy"""
    
    @staticmethod
    def get_config() -> Dict[str, Any]:
        return {
            'name': 'rsi_oversold',
            'symbol': 'ETHUSDT',
            'margin': 50.0,  # USDT
            'leverage': 5,
            'timeframe': '15m',
            'max_stop_loss': 1.5,  # 1.5% stop loss
            'take_profit_pct': 2.5,  # 2.5% take profit
            'rsi_oversold_level': 25,  # RSI level for oversold
            'assessment_interval': 180,  # 3 minutes in seconds
            'enabled': True,
            'description': 'Buy when RSI is oversold below 25'
        }
    
    @staticmethod
    def update_config(updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update configuration with new values"""
        config = RSIOversoldConfig.get_config()
        config.update(updates)
        return config
