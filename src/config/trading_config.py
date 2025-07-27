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
    """Simplified trading configuration manager - WEB DASHBOARD IS SINGLE SOURCE OF TRUTH"""

    def __init__(self):
        """Initialize simplified trading configuration manager"""
        # WEB DASHBOARD IS THE ONLY SOURCE OF TRUTH
        self.strategy_configs = {}

        # Simple default parameters as absolute fallback only
        self.default_params = TradingParameters()

        # Load web dashboard configurations (single source)
        self._load_web_dashboard_configs()

    def _load_web_dashboard_configs(self):
        """Load configurations from web dashboard storage (single source)"""
        import os
        import json

        config_file = "trading_data/web_dashboard_configs.json"
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    self.strategy_configs = json.load(f)

                import logging
                logging.getLogger(__name__).info(f"🌐 WEB DASHBOARD: Loaded {len(self.strategy_configs)} strategy configurations")
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Could not load web dashboard configs: {e}")
                self.strategy_configs = {}
        else:
            self.strategy_configs = {}
            import logging
            logging.getLogger(__name__).info(f"🌐 WEB DASHBOARD: No existing configs found - using defaults")

    def _save_web_dashboard_configs(self):
        """Save web dashboard configurations (single persistent storage)"""
        import os
        import json

        config_file = "trading_data/web_dashboard_configs.json"
        os.makedirs(os.path.dirname(config_file), exist_ok=True)

        try:
            with open(config_file, 'w') as f:
                json.dump(self.strategy_configs, f, indent=2)

            import logging
            logging.getLogger(__name__).info(f"💾 WEB DASHBOARD: Saved configurations")
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"❌ Failed to save web dashboard configs: {e}")

    def get_strategy_config(self, strategy_name: str, base_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get strategy config - WEB DASHBOARD IS SINGLE SOURCE OF TRUTH"""
        # Start with default parameters
        config = self.default_params.to_dict()
        config['name'] = strategy_name
        config['enabled'] = True

        # WEB DASHBOARD OVERRIDES EVERYTHING
        if strategy_name in self.strategy_configs:
            config.update(self.strategy_configs[strategy_name])

            import logging
            logging.getLogger(__name__).info(f"🌐 WEB DASHBOARD: Using config for {strategy_name}")
        else:
            # Set strategy-specific defaults only if no web config exists
            if 'rsi' in strategy_name.lower():
                config.update({
                    'symbol': 'SOLUSDT',
                    'margin': 12.5,
                    'leverage': 25,
                    'timeframe': '15m',
                    'rsi_period': 14,
                    'rsi_long_entry': 40,
                    'rsi_long_exit': 70,
                    'rsi_short_entry': 60,
                    'rsi_short_exit': 30
                })
            elif 'macd' in strategy_name.lower():
                config.update({
                    'symbol': 'BTCUSDT',
                    'margin': 23.0,
                    'leverage': 5,
                    'timeframe': '5m',
                    'macd_fast': 12,
                    'macd_slow': 26,
                    'macd_signal': 9,
                    'macd_entry_threshold': 0.05,
                    'macd_exit_threshold': 0.02
                })

            import logging
            logging.getLogger(__name__).info(f"⚠️ {strategy_name}: Using default config - no web dashboard config found")

        return config

    def update_strategy_params(self, strategy_name: str, updates: Dict[str, Any]):
        """Update strategy parameters - WEB DASHBOARD IS SINGLE SOURCE OF TRUTH"""
        # Validate and clean parameters
        validated_updates = self._validate_parameters(updates)

        # Initialize strategy config if not exists
        if strategy_name not in self.strategy_configs:
            self.strategy_configs[strategy_name] = {}

        # Update configuration
        self.strategy_configs[strategy_name].update(validated_updates)

        # Save to persistent storage
        self._save_web_dashboard_configs()

        # Update running bot if available
        self._update_running_bot(strategy_name, validated_updates)

        import logging
        logging.getLogger(__name__).info(f"🌐 WEB DASHBOARD: Updated {strategy_name} with {len(validated_updates)} parameters")

    def _validate_parameters(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean parameters with safety checks"""
        validated = {}

        # Core trading parameters with safety validation
        if 'symbol' in updates:
            validated['symbol'] = str(updates['symbol']).upper()

        if 'margin' in updates:
            margin = float(updates['margin'])
            validated['margin'] = max(1.0, margin)  # Minimum 1 USDT

        if 'leverage' in updates:
            leverage = int(updates['leverage'])
            validated['leverage'] = max(1, min(125, leverage))  # 1-125x range

        if 'timeframe' in updates:
            valid_timeframes = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d']
            timeframe = str(updates['timeframe'])
            validated['timeframe'] = timeframe if timeframe in valid_timeframes else '15m'

        if 'max_loss_pct' in updates:
            max_loss = float(updates['max_loss_pct'])
            validated['max_loss_pct'] = max(1.0, min(50.0, max_loss))  # 1-50% range

        if 'assessment_interval' in updates:
            interval = int(updates['assessment_interval'])
            validated['assessment_interval'] = max(5, min(3600, interval))  # 5s-1h range

        # Strategy-specific parameters
        strategy_params = [
            'decimals', 'cooldown_period', 'min_volume',
            'rsi_period', 'rsi_long_entry', 'rsi_long_exit', 'rsi_short_entry', 'rsi_short_exit',
            'macd_fast', 'macd_slow', 'macd_signal', 'macd_entry_threshold', 'macd_exit_threshold',
            'min_histogram_threshold', 'confirmation_candles'
        ]

        for param in strategy_params:
            if param in updates:
                validated[param] = updates[param]

        return validated

    def _update_running_bot(self, strategy_name: str, updates: Dict[str, Any]):
        """Update running bot with new configuration"""
        try:
            import sys
            main_module = sys.modules.get('__main__')
            bot_manager = getattr(main_module, 'bot_manager', None) if main_module else None

            if bot_manager and hasattr(bot_manager, 'strategies') and strategy_name in bot_manager.strategies:
                bot_manager.strategies[strategy_name].update(updates)

                import logging
                logging.getLogger(__name__).info(f"🔄 LIVE UPDATE: {strategy_name} updated in running bot")
        except Exception as e:
            import logging
            logging.getLogger(__name__).debug(f"Could not update running bot: {e}")

    def get_all_strategies(self) -> Dict[str, Dict[str, Any]]:
        """Get all strategy configurations from web dashboard"""
        strategies = {}

        # Load from web dashboard configurations first
        for strategy_name, config in self.strategy_configs.items():
            strategies[strategy_name] = {**self.default_params.to_dict()}
            strategies[strategy_name].update(config)

        # Add default strategies if they don't exist
        default_strategies = {
            'rsi_oversold': {
                **self.default_params.to_dict(),
                'symbol': 'SOLUSDT',
                'margin': 12.5,
                'leverage': 25,
                'timeframe': '15m',
                'rsi_period': 14,
                'rsi_long_entry': 40,
                'rsi_long_exit': 70,
                'rsi_short_entry': 60,
                'rsi_short_exit': 30,
                'decimals': 2,
                'cooldown_period': 300
            },
            'macd_divergence': {
                **self.default_params.to_dict(),
                'symbol': 'BTCUSDT',
                'margin': 23.0,
                'leverage': 5,
                'timeframe': '5m',
                'macd_fast': 12,
                'macd_slow': 26,
                'macd_signal': 9,
                'macd_entry_threshold': 0.05,
                'macd_exit_threshold': 0.02,
                'decimals': 3,
                'cooldown_period': 300
            }
        }

        # Only add defaults if not configured via web dashboard
        for strategy_name, default_config in default_strategies.items():
            if strategy_name not in strategies:
                strategies[strategy_name] = default_config

        return strategies

    def update_default_params(self, updates: Dict[str, Any]):
        """Update default trading parameters"""
        for key, value in updates.items():
            if hasattr(self.default_params, key):
                setattr(self.default_params, key, value)

    def update_strategy_config(self, strategy_name, updates):
        """Update strategy configuration with new values"""
        import logging
        try:
            if strategy_name not in self.strategy_configs:
                logging.getLogger(__name__).error(f"Strategy '{strategy_name}' not found in configuration")
                return False

            # Update the strategy configuration
            if self.strategy_configs[strategy_name] is None:
                 self.strategy_configs[strategy_name] = {}
            for key, value in updates.items():
                self.strategy_configs[strategy_name][key] = value

            # Save the updated configuration
            self._save_web_dashboard_configs()
            logging.getLogger(__name__).info(f"Updated strategy '{strategy_name}' configuration: {updates}")
            return True

        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to update strategy configuration for '{strategy_name}': {e}")
            return False

    def enable_strategy(self, strategy_name):
        """Enable a specific strategy"""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Ensure strategy exists in configuration
            if strategy_name not in self.strategy_configs:
                # Initialize with default configuration if not exists
                all_strategies = self.get_all_strategies()
                if strategy_name in all_strategies:
                    self.strategy_configs[strategy_name] = all_strategies[strategy_name].copy()
                else:
                    self.strategy_configs[strategy_name] = {'enabled': True, 'assessment_interval': 60}
            
            success = self.update_strategy_config(strategy_name, {
                'enabled': True,
                'assessment_interval': 60  # Restore normal assessment interval
            })
            
            if success:
                logger.info(f"🟢 Strategy '{strategy_name}' enabled successfully")
            return success
            
        except Exception as e:
            logger.error(f"Failed to enable strategy '{strategy_name}': {e}")
            return False

    def disable_strategy(self, strategy_name):
        """Disable a specific strategy"""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Ensure strategy exists in configuration
            if strategy_name not in self.strategy_configs:
                # Initialize with default configuration if not exists
                all_strategies = self.get_all_strategies()
                if strategy_name in all_strategies:
                    self.strategy_configs[strategy_name] = all_strategies[strategy_name].copy()
                else:
                    self.strategy_configs[strategy_name] = {'enabled': False, 'assessment_interval': 0}
            
            success = self.update_strategy_config(strategy_name, {
                'enabled': False,
                'assessment_interval': 0  # Stop all assessments
            })
            
            if success:
                logger.info(f"🔴 Strategy '{strategy_name}' disabled successfully")
            return success
            
        except Exception as e:
            logger.error(f"Failed to disable strategy '{strategy_name}': {e}")
            return False

    def is_strategy_enabled(self, strategy_name):
        """Check if a strategy is enabled"""
        try:
            config = self.strategy_configs.get(strategy_name, {})
            enabled = config.get('enabled', False)
            assessment_interval = config.get('assessment_interval', 0)
            
            # Strategy is enabled if both enabled=True AND assessment_interval > 0
            return enabled and assessment_interval > 0
        except Exception:
            return False

# Global config manager instance
trading_config_manager = TradingConfigManager()