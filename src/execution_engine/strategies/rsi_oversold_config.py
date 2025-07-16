from typing import Dict, Any

# DEPRECATED: WEB DASHBOARD IS NOW SINGLE SOURCE OF TRUTH
# This file is kept for backwards compatibility only
# All configurations are now managed through the web dashboard

class RSIOversoldConfig:
    """Configuration for RSI Oversold Strategy"""

    _config_file = "src/execution_engine/strategies/rsi_config_data.json"

    @staticmethod
    def get_config():
        """Get RSI strategy configuration"""
        import json
        import os

        default_config = {
            'max_loss_pct': 10,  # Maximum loss percentage before stop loss
            'rsi_period': 14,    # RSI calculation period
            'rsi_long_entry': 40,  # RSI level for long entry
            'rsi_long_exit': 70,   # RSI level for long exit
            'rsi_short_entry': 60, # RSI level for short entry  
            'rsi_short_exit': 30,  # RSI level for short exit
            'min_volume': 1000000, # Minimum 24h volume
            'cooldown_period': 300 # Cooldown in seconds between trades
        }

        # Try to load from file
        try:
            if os.path.exists(RSIOversoldConfig._config_file):
                with open(RSIOversoldConfig._config_file, 'r') as f:
                    saved_config = json.load(f)
                    default_config.update(saved_config)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Could not load RSI config from file: {e}")

        return default_config

    @staticmethod
    def update_config(updates):
        """Update and save RSI strategy configuration"""
        import json
        import os

        # Get current config
        current_config = RSIOversoldConfig.get_config()

        # Update with new values
        current_config.update(updates)

        # Ensure directory exists
        os.makedirs(os.path.dirname(RSIOversoldConfig._config_file), exist_ok=True)

        # Save to file
        try:
            with open(RSIOversoldConfig._config_file, 'w') as f:
                json.dump(current_config, f, indent=2)

            import logging
            logging.getLogger(__name__).info(f"✅ RSI config saved: {updates}")
            return True
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"❌ Failed to save RSI config: {e}")
            return False