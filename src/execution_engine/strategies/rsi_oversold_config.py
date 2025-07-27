from typing import Dict, Any

class RSIOversoldConfig:
    """Configuration for RSI Oversold Strategy - Now syncs with dashboard"""

    @staticmethod
    def get_config():
        """Get RSI strategy configuration from dashboard or fallback to proper defaults"""
        import json
        import os
        import logging

        # Proper RSI oversold/overbought default configuration
        default_config = {
            'max_loss_pct': 5,      # Maximum loss percentage before stop loss
            'rsi_period': 14,       # RSI calculation period
            'rsi_long_entry': 30,   # RSI level for long entry (truly oversold)
            'rsi_long_exit': 70,    # RSI level for long exit (overbought)
            'rsi_short_entry': 70,  # RSI level for short entry (truly overbought)  
            'rsi_short_exit': 30,   # RSI level for short exit (oversold)
            'min_volume': 1000000,  # Minimum 24h volume
            'cooldown_period': 300, # Cooldown in seconds between trades
            'margin': 50.0,         # Default margin
            'leverage': 5           # Default leverage
        }

        logger = logging.getLogger(__name__)
        
        # First try to get from dashboard API (if running)
        try:
            import requests
            response = requests.get('http://localhost:5000/api/strategies', timeout=2)
            if response.status_code == 200:
                strategies = response.json().get('strategies', [])
                for strategy in strategies:
                    if 'rsi' in strategy.get('name', '').lower() and strategy.get('enabled', False):
                        # Use dashboard configuration
                        dashboard_config = strategy.get('config', {})
                        default_config.update(dashboard_config)
                        logger.info(f"✅ RSI config loaded from dashboard: {dashboard_config}")
                        return default_config
        except Exception as e:
            logger.debug(f"Dashboard not available, using file config: {e}")

        # Fallback to file-based config
        config_file = "src/execution_engine/strategies/rsi_config_data.json"
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    saved_config = json.load(f)
                    # Validate RSI levels make sense
                    if saved_config.get('rsi_long_entry', 0) > 50:
                        logger.warning("⚠️  RSI long entry > 50, this is not oversold! Using defaults.")
                        return default_config
                    if saved_config.get('rsi_short_entry', 0) < 50:
                        logger.warning("⚠️  RSI short entry < 50, this is not overbought! Using defaults.")
                        return default_config
                    default_config.update(saved_config)
                    logger.info(f"✅ RSI config loaded from file: {saved_config}")
        except Exception as e:
            logger.warning(f"Could not load RSI config from file: {e}")

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