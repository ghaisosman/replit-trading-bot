
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
            'rsi_long_entry': 30,  # RSI level for long entry
            'rsi_long_exit': 60,   # RSI level for long take profit
            'rsi_short_entry': 70, # RSI level for short entry  
            'rsi_short_exit': 40,  # RSI level for short take profit
            'assessment_interval': 60,  # 60 seconds
            'enabled': True,
            'description': 'RSI strategy: Long at RSI 30, TP at RSI 60. Short at RSI 70, TP at RSI 40. SL at -10% margin PnL'
        }
    
    @staticmethod
    def update_config(updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update configuration with new values"""
        config = RSIOversoldConfig.get_config()
        config.update(updates)
        return config
