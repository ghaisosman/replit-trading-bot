from typing import Dict, Any

class MACDDivergenceConfig:
    """Configuration for MACD Divergence Strategy"""

    _config_file = "src/execution_engine/strategies/macd_config_data.json"

    @staticmethod
    def get_config():
        """Get MACD strategy configuration"""
        import json
        import os

        default_config = {
            'max_loss_pct': 10,    # Maximum loss percentage before stop loss
            'macd_fast': 12,       # MACD fast EMA period
            'macd_slow': 26,       # MACD slow EMA period
            'macd_signal': 9,      # MACD signal line EMA period
            'min_histogram_threshold': 0.0001,  # Minimum histogram value for signal
            'min_distance_threshold': 0.005,    # Minimum distance between MACD and signal (%)
            'confirmation_candles': 2,          # Number of confirmation candles
            'min_volume': 1000000,             # Minimum 24h volume
            'cooldown_period': 300             # Cooldown in seconds between trades
        }

        # Try to load from file
        try:
            if os.path.exists(MACDDivergenceConfig._config_file):
                with open(MACDDivergenceConfig._config_file, 'r') as f:
                    saved_config = json.load(f)
                    default_config.update(saved_config)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Could not load MACD config from file: {e}")

        return default_config

    @staticmethod
    def update_config(updates):
        """Update and save MACD strategy configuration"""
        import json
        import os

        # Get current config
        current_config = MACDDivergenceConfig.get_config()

        # Update with new values
        current_config.update(updates)

        # Ensure directory exists
        os.makedirs(os.path.dirname(MACDDivergenceConfig._config_file), exist_ok=True)

        # Save to file
        try:
            with open(MACDDivergenceConfig._config_file, 'w') as f:
                json.dump(current_config, f, indent=2)

            import logging
            logging.getLogger(__name__).info(f"✅ MACD config saved: {updates}")
            return True
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"❌ Failed to save MACD config: {e}")
            return False