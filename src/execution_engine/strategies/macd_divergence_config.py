# DEPRECATED: This file is kept for backwards compatibility only
# MACD Divergence strategy now uses dedicated strategy class:
# src/execution_engine/strategies/macd_divergence_strategy.py

import logging

class MACDDivergenceConfig:
    """DEPRECATED: Use MACDDivergenceStrategy class instead"""

    @staticmethod
    def get_config():
        """DEPRECATED: Use web dashboard for configuration"""
        logging.getLogger(__name__).warning(
            "DEPRECATED: MACDDivergenceConfig.get_config() is deprecated. "
            "Use web dashboard for strategy configuration."
        )

        return {
            'max_loss_pct': 10,
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            'min_histogram_threshold': 0.0001,
            'min_distance_threshold': 0.005,
            'confirmation_candles': 2,
            'min_volume': 1000000,
            'cooldown_period': 300
        }

    @staticmethod
    def update_config(updates):
        """DEPRECATED: Use web dashboard for configuration updates"""
        logging.getLogger(__name__).warning(
            "DEPRECATED: MACDDivergenceConfig.update_config() is deprecated. "
            "Use web dashboard for strategy configuration updates."
        )
        return False