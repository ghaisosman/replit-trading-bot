
from typing import Dict, Any

class SMACrossoverConfig:
    """Configuration for SMA Crossover strategy"""
    
    @staticmethod
    def get_config() -> Dict[str, Any]:
        return {
            'name': 'sma_crossover',
            'symbol': 'BTCUSDT',
            'margin': 100.0,  # USDT
            'leverage': 10,
            'timeframe': '1h',
            'max_stop_loss': 2.0,  # 2% stop loss
            'take_profit_pct': 3.0,  # 3% take profit
            'assessment_interval': 300,  # 5 minutes in seconds
            'enabled': True,
            'description': 'Buy when SMA 20 crosses above SMA 50'
        }
    
    @staticmethod
    def update_config(updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update configuration with new values"""
        config = SMACrossoverConfig.get_config()
        config.update(updates)
        return config
