
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

class TradingConfigManager:
    """Manages trading configurations for all strategies - WEB DASHBOARD IS SINGLE SOURCE OF TRUTH"""

    def __init__(self):
        # Default parameters only as fallback - WEB DASHBOARD OVERRIDES EVERYTHING
        self.default_params = TradingParameters()

        # WEB DASHBOARD IS THE ONLY SOURCE OF TRUTH
        # All configurations come from web dashboard updates
        self.strategy_overrides = {}

        # Load any existing web dashboard configurations
        self._load_web_dashboard_configs()

    def _load_web_dashboard_configs(self):
        """Load configurations previously set via web dashboard"""
        import os
        import json

        config_file = "trading_data/web_dashboard_configs.json"
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    self.strategy_overrides = json.load(f)

                import logging
                logging.getLogger(__name__).info(f"🌐 WEB DASHBOARD: Loaded saved configurations for {len(self.strategy_overrides)} strategies")
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Could not load web dashboard configs: {e}")

    def _save_web_dashboard_configs(self):
        """Save web dashboard configurations to persistent storage"""
        import os
        import json

        config_file = "trading_data/web_dashboard_configs.json"
        os.makedirs(os.path.dirname(config_file), exist_ok=True)

        try:
            with open(config_file, 'w') as f:
                json.dump(self.strategy_overrides, f, indent=2)

            import logging
            logging.getLogger(__name__).info(f"💾 WEB DASHBOARD: Saved configurations to {config_file}")
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"❌ Failed to save web dashboard configs: {e}")

    def get_strategy_config(self, strategy_name: str, base_config: Dict[str, Any]) -> Dict[str, Any]:
        """Get strategy config - WEB DASHBOARD IS SINGLE SOURCE OF TRUTH"""
        # Start with minimal base strategy config (only technical parameters)
        config = {
            'name': strategy_name,
            'enabled': True
        }

        # Apply default parameters as absolute fallback
        default_params = self.default_params.to_dict()
        config.update(default_params)

        # WEB DASHBOARD SETTINGS OVERRIDE EVERYTHING
        if strategy_name in self.strategy_overrides:
            web_config = self.strategy_overrides[strategy_name]
            config.update(web_config)

            import logging
            logging.getLogger(__name__).info(f"🌐 WEB DASHBOARD: Using web config for {strategy_name}")
        else:
            import logging
            logging.getLogger(__name__).info(f"⚠️ {strategy_name}: No web dashboard config found, using defaults")

        # Log the final config being used for debugging
        import logging
        logging.getLogger(__name__).info(f"🎯 FINAL CONFIG for {strategy_name}: {config}")

        return config

    def update_strategy_params(self, strategy_name: str, updates: Dict[str, Any]):
        """Update trading parameters for a specific strategy - WEB DASHBOARD IS SINGLE SOURCE OF TRUTH"""
        if strategy_name not in self.strategy_overrides:
            self.strategy_overrides[strategy_name] = {}

        # Validate and clean parameters
        if 'assessment_interval' in updates:
            updates['assessment_interval'] = int(updates['assessment_interval'])
            # Validate assessment interval (5 seconds to 5 minutes)
            if updates['assessment_interval'] < 5:
                updates['assessment_interval'] = 5
            elif updates['assessment_interval'] > 300:
                updates['assessment_interval'] = 300

        if 'margin' in updates:
            updates['margin'] = float(updates['margin'])
            if updates['margin'] <= 0:
                updates['margin'] = 50.0

        if 'leverage' in updates:
            updates['leverage'] = int(updates['leverage'])
            if updates['leverage'] <= 0 or updates['leverage'] > 125:
                updates['leverage'] = 5

        # WEB DASHBOARD SETTINGS OVERRIDE ALL OTHER SOURCES
        self.strategy_overrides[strategy_name].update(updates)

        # Save to persistent storage
        self._save_web_dashboard_configs()

        # Force update any running bot instance immediately
        self._force_update_running_bot(strategy_name, updates)

        # Log the update for debugging
        import logging
        logging.getLogger(__name__).info(f"🌐 WEB DASHBOARD UPDATE | {strategy_name} | {updates}")
        logging.getLogger(__name__).info(f"🎯 WEB DASHBOARD IS SINGLE SOURCE OF TRUTH - ALL CONFIG FILES IGNORED")
        if 'assessment_interval' in updates:
            logging.getLogger(__name__).info(f"📅 {strategy_name} assessment interval set to {updates['assessment_interval']} seconds")

    def _force_update_running_bot(self, strategy_name: str, updates: Dict[str, Any]):
        """Force update running bot with web dashboard settings"""
        try:
            import sys
            main_module = sys.modules.get('__main__')
            bot_manager = getattr(main_module, 'bot_manager', None) if main_module else None

            if bot_manager and hasattr(bot_manager, 'strategies') and strategy_name in bot_manager.strategies:
                # Force update the running bot's strategy config
                bot_manager.strategies[strategy_name].update(updates)

                import logging
                logging.getLogger(__name__).info(f"🔄 LIVE UPDATE | {strategy_name} config updated in running bot")
                logging.getLogger(__name__).info(f"📊 New Config: {bot_manager.strategies[strategy_name]}")
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Could not update running bot: {e}")

    def get_all_strategies(self) -> Dict[str, Dict[str, Any]]:
        """Get all strategy configurations from web dashboard"""
        strategies = {}

        # If no web dashboard configs exist, provide minimal defaults for setup
        if not self.strategy_overrides:
            strategies = {
                'rsi_oversold': {
                    **self.default_params.to_dict(),
                    'symbol': 'SOLUSDT',
                    'margin': 12.5,
                    'leverage': 25,
                    'rsi_long_entry': 40,
                    'rsi_long_exit': 70,
                    'rsi_short_entry': 60,
                    'rsi_short_exit': 30,
                },
                'macd_divergence': {
                    **self.default_params.to_dict(),
                    'symbol': 'BTCUSDT',
                    'margin': 23.0,
                    'leverage': 5,
                    'timeframe': '5m',
                    'assessment_interval': 30,
                    'macd_fast': 12,
                    'macd_slow': 26,
                    'macd_signal': 9,
                    'min_histogram_threshold': 0.0001,
                    'min_distance_threshold': 0.005,
                    'confirmation_candles': 2,
                }
            }
        else:
            # Use web dashboard configurations
            for strategy_name, config in self.strategy_overrides.items():
                full_config = {**self.default_params.to_dict(), **config}

                # Add strategy-specific defaults based on strategy name/type
                if 'rsi' in strategy_name.lower():
                    # RSI strategy defaults
                    full_config.setdefault('rsi_long_entry', 30)
                    full_config.setdefault('rsi_long_exit', 60)
                    full_config.setdefault('rsi_short_entry', 70)
                    full_config.setdefault('rsi_short_exit', 40)
                elif 'macd' in strategy_name.lower():
                    # MACD strategy defaults
                    full_config.setdefault('macd_fast', 12)
                    full_config.setdefault('macd_slow', 26)
                    full_config.setdefault('macd_signal', 9)
                    full_config.setdefault('min_histogram_threshold', 0.0001)
                    full_config.setdefault('min_distance_threshold', 0.001)
                    full_config.setdefault('confirmation_candles', 2)

                strategies[strategy_name] = full_config

        return strategies

    def update_default_params(self, updates: Dict[str, Any]):
        """Update default trading parameters for all strategies"""
        for key, value in updates.items():
            if hasattr(self.default_params, key):
                setattr(self.default_params, key, value)

# Global config manager instance
trading_config_manager = TradingConfigManager()
