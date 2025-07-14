
from typing import Dict, Any

class MACDDivergenceConfig:
    """Configuration for MACD Divergence strategy"""
    
    @staticmethod
    def get_config() -> Dict[str, Any]:
        return {
            'name': 'macd_divergence',
            'symbol': 'BTCUSDT',  # Easily changeable
            'margin': 50.0,  # USDT - easily adjustable
            'leverage': 5,   # Easily adjustable
            'timeframe': '15m',  # Easily changeable
            'max_loss_pct': 10,  # 10% of margin for stop loss
            
            # MACD Parameters
            'macd_fast': 12,
            'macd_slow': 26, 
            'macd_signal': 9,
            
            # Noise filtering parameters
            'min_histogram_threshold': 0.0001,  # Minimum histogram change to consider
            'confirmation_candles': 2,  # Max 2 candles confirmation
            'min_distance_threshold': 0.005,  # 0.5% minimum distance between MACD lines
            
            'assessment_interval': 60,  # 60 seconds
            'enabled': True,
            'description': 'MACD divergence strategy: Long on bullish divergence before cross, Short on bearish divergence before cross'
        }
    
    @staticmethod
    def update_config(updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update configuration with new values"""
        config = MACDDivergenceConfig.get_config()
        config.update(updates)
        return config
