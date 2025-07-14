
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
            'max_loss_pct': 10,  # 10% of margin for stop loss
            'rsi_long_entry': 40,  # RSI level for long entry (relaxed for testing)
            'rsi_long_exit': 70,   # RSI level for long take profit (relaxed for testing)
            'rsi_short_entry': 60, # RSI level for short entry (relaxed for testing)
            'rsi_short_exit': 30,  # RSI level for short take profit (relaxed for testing)
            'assessment_interval': 60,  # 60 seconds
            'enabled': True,
            'description': 'RSI strategy: Long at RSI 40, TP at RSI 70. Short at RSI 60, TP at RSI 30. SL at -10% margin PnL (RELAXED FOR TESTING)'
        }
    
    @staticmethod
    def update_config(updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update configuration with new values"""
        config = RSIOversoldConfig.get_config()
        config.update(updates)
        return config
