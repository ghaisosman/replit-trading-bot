
from typing import Dict, Any, Optional
from dataclasses import dataclass
import os
import json
import logging

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
    """Clean trading configuration manager - WEB DASHBOARD IS SINGLE SOURCE OF TRUTH"""

    def __init__(self):
        """Initialize clean trading configuration manager"""
        self.logger = logging.getLogger(__name__)
        
        # WEB DASHBOARD IS THE ONLY SOURCE OF TRUTH
        self.strategy_configs = {}
        
        # Simple default parameters as absolute fallback only
        self.default_params = TradingParameters()
        
        # Required parameters for each strategy type
        self.required_parameters = self._define_required_parameters()
        
        # Load web dashboard configurations (single source)
        self._load_web_dashboard_configs()

    def _define_required_parameters(self) -> Dict[str, Dict[str, Any]]:
        """Define required parameters for each strategy type"""
        return {
            'rsi': {
                'rsi_period': 14,
                'rsi_long_entry': 30,
                'rsi_long_exit': 70,
                'rsi_short_entry': 70,
                'rsi_short_exit': 30,
                'decimals': 2,
                'cooldown_period': 300
            },
            'macd': {
                'macd_fast': 12,
                'macd_slow': 26,
                'macd_signal': 9,
                'min_histogram_threshold': 0.0001,
                'macd_entry_threshold': 0.05,
                'macd_exit_threshold': 0.02,
                'confirmation_candles': 2,
                'decimals': 3,
                'cooldown_period': 300
            },
            'engulfing': {
                'rsi_period': 14,
                'rsi_threshold': 50,
                'rsi_long_exit': 70,
                'rsi_short_exit': 30,
                'stable_candle_ratio': 0.5,
                'price_lookback_bars': 5,
                'partial_tp_pnl_threshold': 0.0,
                'partial_tp_position_percentage': 0.0,
                'decimals': 2,
                'cooldown_period': 300
            },
            'smart_money': {
                'swing_lookback_period': 25,
                'sweep_threshold_pct': 0.1,
                'reversion_candles': 3,
                'volume_spike_multiplier': 2.0,
                'min_swing_distance_pct': 1.0,
                'max_daily_trades': 3,
                'session_filter_enabled': True,
                'allowed_sessions': ['LONDON', 'NEW_YORK'],
                'trend_filter_enabled': True,
                'min_volume': 100000,
                'decimals': 2,
                'cooldown_period': 300
            }
        }

    def _load_web_dashboard_configs(self):
        """Load configurations from web dashboard storage (single source)"""
        config_file = "trading_data/web_dashboard_configs.json"
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    self.strategy_configs = json.load(f)
                self.logger.info(f"🌐 WEB DASHBOARD: Loaded {len(self.strategy_configs)} strategy configurations")
            except Exception as e:
                self.logger.warning(f"Could not load web dashboard configs: {e}")
                self.strategy_configs = {}
        else:
            self.strategy_configs = {}
            self.logger.info(f"🌐 WEB DASHBOARD: No existing configs found")

    def _save_web_dashboard_configs(self):
        """Save web dashboard configurations (single persistent storage)"""
        config_file = "trading_data/web_dashboard_configs.json"
        os.makedirs(os.path.dirname(config_file), exist_ok=True)

        try:
            with open(config_file, 'w') as f:
                json.dump(self.strategy_configs, f, indent=2)
            self.logger.info(f"💾 WEB DASHBOARD: Saved configurations")
        except Exception as e:
            self.logger.error(f"❌ Failed to save web dashboard configs: {e}")

    def _get_strategy_type(self, strategy_name: str) -> str:
        """Determine strategy type from name"""
        name_lower = strategy_name.lower()
        if 'rsi' in name_lower:
            return 'rsi'
        elif 'macd' in name_lower:
            return 'macd'
        elif 'engulfing' in name_lower:
            return 'engulfing'
        elif 'smart' in name_lower and 'money' in name_lower:
            return 'smart_money'
        return 'unknown'

    def _validate_strategy_completeness(self, strategy_name: str, config: Dict[str, Any]) -> tuple:
        """Validate that strategy has all required parameters"""
        strategy_type = self._get_strategy_type(strategy_name)
        
        if strategy_type == 'unknown':
            return False, f"Unknown strategy type for {strategy_name}"
        
        required_params = self.required_parameters.get(strategy_type, {})
        missing_params = []
        
        # Check core parameters
        core_params = ['symbol', 'margin', 'leverage', 'timeframe', 'max_loss_pct', 'assessment_interval']
        for param in core_params:
            if param not in config or config[param] is None:
                missing_params.append(param)
        
        # Check strategy-specific parameters
        for param in required_params:
            if param not in config or config[param] is None:
                missing_params.append(param)
        
        if missing_params:
            return False, f"Missing required parameters: {', '.join(missing_params)}"
        
        return True, "Complete"

    def get_strategy_config(self, strategy_name: str, base_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get strategy config - WEB DASHBOARD IS SINGLE SOURCE OF TRUTH"""
        # Start with default parameters
        config = self.default_params.to_dict()
        config['name'] = strategy_name
        config['enabled'] = True
        config['operational'] = False
        config['validation_message'] = ""

        # WEB DASHBOARD OVERRIDES EVERYTHING
        if strategy_name in self.strategy_configs:
            config.update(self.strategy_configs[strategy_name])
            
            # Validate completeness
            is_complete, message = self._validate_strategy_completeness(strategy_name, config)
            config['operational'] = is_complete
            config['validation_message'] = message
            
            if is_complete:
                self.logger.info(f"🌐 WEB DASHBOARD: Using complete config for {strategy_name}")
            else:
                self.logger.warning(f"🌐 WEB DASHBOARD: {strategy_name} NOT OPERATIONAL - {message}")
        else:
            # Strategy not configured via dashboard - not operational
            config['operational'] = False
            config['validation_message'] = "Strategy not configured via web dashboard"
            self.logger.warning(f"⚠️ {strategy_name}: NOT OPERATIONAL - No web dashboard configuration")

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

        # Auto-complete missing parameters with defaults
        self._ensure_complete_configuration(strategy_name)

        # Save to persistent storage
        self._save_web_dashboard_configs()

        # Update running bot if available
        self._update_running_bot(strategy_name, validated_updates)

        self.logger.info(f"🌐 WEB DASHBOARD: Updated {strategy_name} with {len(validated_updates)} parameters")

    def _ensure_complete_configuration(self, strategy_name: str):
        """Ensure strategy has all required parameters"""
        strategy_type = self._get_strategy_type(strategy_name)
        
        if strategy_type != 'unknown':
            config = self.strategy_configs[strategy_name]
            required_params = self.required_parameters.get(strategy_type, {})
            
            # Add missing core parameters
            core_defaults = self.default_params.to_dict()
            for param, default_value in core_defaults.items():
                if param not in config:
                    config[param] = default_value
            
            # Add missing strategy-specific parameters
            for param, default_value in required_params.items():
                if param not in config:
                    config[param] = default_value

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

        # Strategy-specific parameters (pass through with type conversion)
        strategy_params = [
            'decimals', 'cooldown_period', 'min_volume',
            'rsi_period', 'rsi_long_entry', 'rsi_long_exit', 'rsi_short_entry', 'rsi_short_exit',
            'macd_fast', 'macd_slow', 'macd_signal', 'macd_entry_threshold', 'macd_exit_threshold',
            'min_histogram_threshold', 'confirmation_candles', 'rsi_threshold', 'stable_candle_ratio',
            'price_lookback_bars', 'partial_tp_pnl_threshold', 'partial_tp_position_percentage',
            'swing_lookback_period', 'sweep_threshold_pct', 'reversion_candles', 'volume_spike_multiplier',
            'min_swing_distance_pct', 'max_daily_trades', 'session_filter_enabled', 'trend_filter_enabled'
        ]

        for param in strategy_params:
            if param in updates:
                try:
                    if param in ['session_filter_enabled', 'trend_filter_enabled']:
                        validated[param] = bool(updates[param])
                    elif param in ['allowed_sessions']:
                        validated[param] = updates[param] if isinstance(updates[param], list) else ['LONDON', 'NEW_YORK']
                    else:
                        # Try to convert to appropriate type
                        if isinstance(updates[param], (int, float)):
                            validated[param] = updates[param]
                        else:
                            validated[param] = float(updates[param]) if '.' in str(updates[param]) else int(updates[param])
                except (ValueError, TypeError):
                    self.logger.warning(f"Invalid value for {param}: {updates[param]}")

        return validated

    def _update_running_bot(self, strategy_name: str, updates: Dict[str, Any]):
        """Update running bot with new configuration"""
        try:
            import sys
            main_module = sys.modules.get('__main__')
            bot_manager = getattr(main_module, 'bot_manager', None) if main_module else None

            if bot_manager and hasattr(bot_manager, 'strategies') and strategy_name in bot_manager.strategies:
                bot_manager.strategies[strategy_name].update(updates)
                self.logger.info(f"🔄 LIVE UPDATE: {strategy_name} updated in running bot")
        except Exception as e:
            self.logger.debug(f"Could not update running bot: {e}")

    def get_all_strategies(self) -> Dict[str, Dict[str, Any]]:
        """Get all strategy configurations from web dashboard"""
        strategies = {}

        # Load from web dashboard configurations ONLY
        for strategy_name, config in self.strategy_configs.items():
            base_config = {**self.default_params.to_dict()}
            base_config.update(config)
            
            # Validate completeness
            is_complete, message = self._validate_strategy_completeness(strategy_name, base_config)
            base_config['operational'] = is_complete
            base_config['validation_message'] = message
            
            strategies[strategy_name] = base_config

        return strategies

    def get_strategy_validation_status(self) -> Dict[str, Dict[str, Any]]:
        """Get validation status for all strategies"""
        validation_status = {}
        
        for strategy_name in self.strategy_configs:
            config = self.get_strategy_config(strategy_name)
            validation_status[strategy_name] = {
                'operational': config.get('operational', False),
                'validation_message': config.get('validation_message', ''),
                'strategy_type': self._get_strategy_type(strategy_name)
            }
        
        return validation_status

    def create_complete_strategy(self, strategy_name: str, strategy_type: str) -> Dict[str, Any]:
        """Create a complete strategy configuration with all required parameters"""
        if strategy_type not in self.required_parameters:
            raise ValueError(f"Unknown strategy type: {strategy_type}")
        
        # Start with core parameters
        complete_config = self.default_params.to_dict()
        
        # Add strategy-specific parameters
        complete_config.update(self.required_parameters[strategy_type])
        
        # Set appropriate defaults based on strategy type
        if strategy_type == 'rsi':
            complete_config.update({
                'symbol': 'SOLUSDT',
                'margin': 12.5,
                'leverage': 25,
                'timeframe': '15m'
            })
        elif strategy_type == 'macd':
            complete_config.update({
                'symbol': 'BTCUSDT',
                'margin': 50.0,
                'leverage': 5,
                'timeframe': '15m'
            })
        elif strategy_type == 'engulfing':
            complete_config.update({
                'symbol': 'ETHUSDT',
                'margin': 25.0,
                'leverage': 10,
                'timeframe': '1h'
            })
        elif strategy_type == 'smart_money':
            complete_config.update({
                'symbol': 'BTCUSDT',
                'margin': 100.0,
                'leverage': 3,
                'timeframe': '15m'
            })
        
        return complete_config

    def update_default_params(self, updates: Dict[str, Any]):
        """Update default trading parameters"""
        for key, value in updates.items():
            if hasattr(self.default_params, key):
                setattr(self.default_params, key, value)

    def _clear_cache(self):
        """Clear any cached data - placeholder for compatibility"""
        pass

# Global config manager instance
trading_config_manager = TradingConfigManager()
