
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

        # Comprehensive parameter validation and cleaning
        validated_updates = {}

        # Basic trading parameters
        if 'symbol' in updates:
            validated_updates['symbol'] = str(updates['symbol']).upper()

        if 'margin' in updates:
            validated_updates['margin'] = float(updates['margin'])
            if validated_updates['margin'] <= 0:
                validated_updates['margin'] = 50.0

        if 'leverage' in updates:
            validated_updates['leverage'] = int(updates['leverage'])
            if validated_updates['leverage'] <= 0 or validated_updates['leverage'] > 125:
                validated_updates['leverage'] = 5

        if 'timeframe' in updates:
            valid_timeframes = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d']
            timeframe = str(updates['timeframe'])
            validated_updates['timeframe'] = timeframe if timeframe in valid_timeframes else '15m'

        if 'max_loss_pct' in updates:
            validated_updates['max_loss_pct'] = float(updates['max_loss_pct'])
            if validated_updates['max_loss_pct'] <= 0 or validated_updates['max_loss_pct'] > 50:
                validated_updates['max_loss_pct'] = 10.0

        if 'assessment_interval' in updates:
            validated_updates['assessment_interval'] = int(updates['assessment_interval'])
            if validated_updates['assessment_interval'] < 5:
                validated_updates['assessment_interval'] = 5
            elif validated_updates['assessment_interval'] > 300:
                validated_updates['assessment_interval'] = 300

        if 'decimals' in updates:
            validated_updates['decimals'] = int(updates['decimals'])
            if validated_updates['decimals'] < 0 or validated_updates['decimals'] > 8:
                validated_updates['decimals'] = 2

        if 'cooldown_period' in updates:
            validated_updates['cooldown_period'] = int(updates['cooldown_period'])
            if validated_updates['cooldown_period'] < 30:
                validated_updates['cooldown_period'] = 30
            elif validated_updates['cooldown_period'] > 3600:
                validated_updates['cooldown_period'] = 3600

        if 'min_volume' in updates:
            validated_updates['min_volume'] = float(updates['min_volume'])
            if validated_updates['min_volume'] < 0:
                validated_updates['min_volume'] = 1000000

        # RSI Strategy Parameters
        if 'rsi_period' in updates:
            validated_updates['rsi_period'] = int(updates['rsi_period'])
            if validated_updates['rsi_period'] < 5 or validated_updates['rsi_period'] > 50:
                validated_updates['rsi_period'] = 14

        if 'rsi_long_entry' in updates:
            validated_updates['rsi_long_entry'] = int(updates['rsi_long_entry'])
            if validated_updates['rsi_long_entry'] < 10 or validated_updates['rsi_long_entry'] > 50:
                validated_updates['rsi_long_entry'] = 40

        if 'rsi_long_exit' in updates:
            validated_updates['rsi_long_exit'] = int(updates['rsi_long_exit'])
            if validated_updates['rsi_long_exit'] < 50 or validated_updates['rsi_long_exit'] > 90:
                validated_updates['rsi_long_exit'] = 70

        if 'rsi_short_entry' in updates:
            validated_updates['rsi_short_entry'] = int(updates['rsi_short_entry'])
            if validated_updates['rsi_short_entry'] < 50 or validated_updates['rsi_short_entry'] > 90:
                validated_updates['rsi_short_entry'] = 60

        if 'rsi_short_exit' in updates:
            validated_updates['rsi_short_exit'] = int(updates['rsi_short_exit'])
            if validated_updates['rsi_short_exit'] < 10 or validated_updates['rsi_short_exit'] > 50:
                validated_updates['rsi_short_exit'] = 30

        # MACD Strategy Parameters
        if 'macd_fast' in updates:
            validated_updates['macd_fast'] = int(updates['macd_fast'])
            if validated_updates['macd_fast'] < 5 or validated_updates['macd_fast'] > 20:
                validated_updates['macd_fast'] = 12

        if 'macd_slow' in updates:
            validated_updates['macd_slow'] = int(updates['macd_slow'])
            if validated_updates['macd_slow'] < 20 or validated_updates['macd_slow'] > 50:
                validated_updates['macd_slow'] = 26

        if 'macd_signal' in updates:
            validated_updates['macd_signal'] = int(updates['macd_signal'])
            if validated_updates['macd_signal'] < 5 or validated_updates['macd_signal'] > 15:
                validated_updates['macd_signal'] = 9

        if 'min_histogram_threshold' in updates:
            validated_updates['min_histogram_threshold'] = float(updates['min_histogram_threshold'])
            if validated_updates['min_histogram_threshold'] < 0.0001 or validated_updates['min_histogram_threshold'] > 0.01:
                validated_updates['min_histogram_threshold'] = 0.0001

        if 'min_distance_threshold' in updates:
            validated_updates['min_distance_threshold'] = float(updates['min_distance_threshold'])
            if validated_updates['min_distance_threshold'] < 0.001 or validated_updates['min_distance_threshold'] > 5.0:
                validated_updates['min_distance_threshold'] = 0.005

        if 'confirmation_candles' in updates:
            validated_updates['confirmation_candles'] = int(updates['confirmation_candles'])
            if validated_updates['confirmation_candles'] < 1 or validated_updates['confirmation_candles'] > 5:
                validated_updates['confirmation_candles'] = 2

        # Liquidity Reversal Strategy Parameters (Complete Set)
        if 'lookback_candles' in updates:
            validated_updates['lookback_candles'] = int(updates['lookback_candles'])
            if validated_updates['lookback_candles'] < 50 or validated_updates['lookback_candles'] > 200:
                validated_updates['lookback_candles'] = 100

        if 'liquidity_threshold' in updates:
            validated_updates['liquidity_threshold'] = float(updates['liquidity_threshold'])
            if validated_updates['liquidity_threshold'] < 0.01 or validated_updates['liquidity_threshold'] > 0.05:
                validated_updates['liquidity_threshold'] = 0.02

        if 'reclaim_timeout' in updates:
            validated_updates['reclaim_timeout'] = int(updates['reclaim_timeout'])
            if validated_updates['reclaim_timeout'] < 2 or validated_updates['reclaim_timeout'] > 10:
                validated_updates['reclaim_timeout'] = 5

        if 'min_volume_spike' in updates:
            validated_updates['min_volume_spike'] = float(updates['min_volume_spike'])
            if validated_updates['min_volume_spike'] < 1.2 or validated_updates['min_volume_spike'] > 3.0:
                validated_updates['min_volume_spike'] = 1.5

        if 'max_risk_per_trade' in updates:
            validated_updates['max_risk_per_trade'] = float(updates['max_risk_per_trade'])
            if validated_updates['max_risk_per_trade'] < 0.1 or validated_updates['max_risk_per_trade'] > 2.0:
                validated_updates['max_risk_per_trade'] = 0.5

        if 'stop_loss_buffer' in updates:
            validated_updates['stop_loss_buffer'] = float(updates['stop_loss_buffer'])
            if validated_updates['stop_loss_buffer'] < 0.05 or validated_updates['stop_loss_buffer'] > 0.5:
                validated_updates['stop_loss_buffer'] = 0.1

        if 'profit_target_multiplier' in updates:
            validated_updates['profit_target_multiplier'] = float(updates['profit_target_multiplier'])
            if validated_updates['profit_target_multiplier'] < 1.0 or validated_updates['profit_target_multiplier'] > 5.0:
                validated_updates['profit_target_multiplier'] = 2.0

        if 'min_wick_ratio' in updates:
            validated_updates['min_wick_ratio'] = float(updates['min_wick_ratio'])
            if validated_updates['min_wick_ratio'] < 0.3 or validated_updates['min_wick_ratio'] > 1.0:
                validated_updates['min_wick_ratio'] = 0.6

        if 'swing_strength' in updates:
            validated_updates['swing_strength'] = int(updates['swing_strength'])
            if validated_updates['swing_strength'] < 2 or validated_updates['swing_strength'] > 5:
                validated_updates['swing_strength'] = 3

        # Universal Strategy Parameters (for any future strategy)
        # This makes the system future-proof for any new strategy type
        universal_float_params = [
            'entry_threshold', 'exit_threshold', 'volatility_filter', 'volume_filter',
            'momentum_threshold', 'trend_strength', 'signal_confidence', 'risk_multiplier',
            'profit_multiplier', 'drawdown_limit', 'correlation_threshold', 'spread_threshold'
        ]
        
        universal_int_params = [
            'lookback_period', 'confirmation_period', 'signal_period', 'trend_period',
            'volume_period', 'momentum_period', 'filter_period', 'threshold_period'
        ]
        
        # Validate universal float parameters (0.001 to 10.0)
        for param in universal_float_params:
            if param in updates:
                validated_updates[param] = float(updates[param])
                if validated_updates[param] < 0.001 or validated_updates[param] > 10.0:
                    validated_updates[param] = 0.1  # Safe default
        
        # Validate universal int parameters (1 to 100)
        for param in universal_int_params:
            if param in updates:
                validated_updates[param] = int(updates[param])
                if validated_updates[param] < 1 or validated_updates[param] > 100:
                    validated_updates[param] = 14  # Safe default

        # WEB DASHBOARD SETTINGS OVERRIDE ALL OTHER SOURCES
        self.strategy_overrides[strategy_name].update(validated_updates)

        # Save to persistent storage
        self._save_web_dashboard_configs()

        # Force update any running bot instance immediately
        self._force_update_running_bot(strategy_name, validated_updates)

        # Log the update for debugging
        import logging
        logging.getLogger(__name__).info(f"🌐 WEB DASHBOARD UPDATE | {strategy_name} | {validated_updates}")
        logging.getLogger(__name__).info(f"🎯 WEB DASHBOARD IS SINGLE SOURCE OF TRUTH - ALL CONFIG FILES IGNORED")
        if 'assessment_interval' in validated_updates:
            logging.getLogger(__name__).info(f"📅 {strategy_name} assessment interval set to {validated_updates['assessment_interval']} seconds")

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

        # If no web dashboard configs exist, provide comprehensive defaults for setup
        if not self.strategy_overrides:
            strategies = {
                'rsi_oversold': {
                    **self.default_params.to_dict(),
                    'symbol': 'SOLUSDT',
                    'margin': 12.5,
                    'leverage': 25,
                    'timeframe': '15m',
                    'assessment_interval': 60,
                    'decimals': 2,
                    'cooldown_period': 300,
                    # RSI Strategy Parameters
                    'rsi_period': 14,
                    'rsi_long_entry': 40,
                    'rsi_long_exit': 70,
                    'rsi_short_entry': 60,
                    'rsi_short_exit': 30,
                    'min_volume': 1000000,
                },
                'macd_divergence': {
                    **self.default_params.to_dict(),
                    'symbol': 'BTCUSDT',
                    'margin': 23.0,
                    'leverage': 5,
                    'timeframe': '5m',
                    'assessment_interval': 30,
                    'decimals': 2,
                    'cooldown_period': 300,
                    # MACD Strategy Parameters
                    'macd_fast': 12,
                    'macd_slow': 26,
                    'macd_signal': 9,
                    'min_histogram_threshold': 0.0001,
                    'min_distance_threshold': 0.005,
                    'confirmation_candles': 2,
                    'min_volume': 1000000,
                },
                'liquidity_reversal': {
                    **self.default_params.to_dict(),
                    'symbol': 'ETHUSDT',
                    'margin': 30.0,
                    'leverage': 10,
                    'timeframe': '5m',
                    'assessment_interval': 20,
                    'decimals': 2,
                    'cooldown_period': 600,
                    # Liquidity Reversal Strategy Parameters
                    'lookback_candles': 100,
                    'liquidity_threshold': 0.02,
                    'reclaim_timeout': 5,
                    'min_volume_spike': 1.5,
                    'max_risk_per_trade': 0.5,
                    'stop_loss_buffer': 0.1,
                    'profit_target_multiplier': 2.0,
                    'swing_strength': 3,
                    'min_wick_ratio': 0.6,
                    'min_volume': 5000000,
                }
            }
        else:
            # Use web dashboard configurations
            for strategy_name, config in self.strategy_overrides.items():
                full_config = {**self.default_params.to_dict(), **config}

                # Add comprehensive strategy-specific defaults based on strategy name/type
                if 'rsi' in strategy_name.lower():
                    # RSI strategy comprehensive defaults
                    full_config.setdefault('rsi_period', 14)
                    full_config.setdefault('rsi_long_entry', 40)
                    full_config.setdefault('rsi_long_exit', 70)
                    full_config.setdefault('rsi_short_entry', 60)
                    full_config.setdefault('rsi_short_exit', 30)
                    full_config.setdefault('min_volume', 1000000)
                    full_config.setdefault('decimals', 2)
                    full_config.setdefault('cooldown_period', 300)
                elif 'macd' in strategy_name.lower():
                    # MACD strategy comprehensive defaults
                    full_config.setdefault('macd_fast', 12)
                    full_config.setdefault('macd_slow', 26)
                    full_config.setdefault('macd_signal', 9)
                    full_config.setdefault('min_histogram_threshold', 0.0001)
                    full_config.setdefault('min_distance_threshold', 0.005)
                    full_config.setdefault('confirmation_candles', 2)
                    full_config.setdefault('min_volume', 1000000)
                    full_config.setdefault('decimals', 2)
                    full_config.setdefault('cooldown_period', 300)
                elif 'liquidity' in strategy_name.lower() or 'reversal' in strategy_name.lower():
                    # Liquidity Reversal strategy comprehensive defaults
                    full_config.setdefault('lookback_candles', 100)
                    full_config.setdefault('liquidity_threshold', 0.02)
                    full_config.setdefault('reclaim_timeout', 5)
                    full_config.setdefault('min_volume_spike', 1.5)
                    full_config.setdefault('max_risk_per_trade', 0.5)
                    full_config.setdefault('stop_loss_buffer', 0.1)
                    full_config.setdefault('profit_target_multiplier', 2.0)
                    full_config.setdefault('swing_strength', 3)
                    full_config.setdefault('min_wick_ratio', 0.6)
                    full_config.setdefault('min_volume', 5000000)
                    full_config.setdefault('decimals', 2)
                    full_config.setdefault('cooldown_period', 600)
                else:
                    # Universal defaults for ANY future strategy type
                    # This ensures the system is future-proof
                    full_config.setdefault('decimals', 2)
                    full_config.setdefault('cooldown_period', 300)
                    full_config.setdefault('min_volume', 1000000)
                    
                    # Add universal strategy parameters with safe defaults
                    full_config.setdefault('entry_threshold', 0.1)
                    full_config.setdefault('exit_threshold', 0.05)
                    full_config.setdefault('signal_period', 14)
                    full_config.setdefault('confirmation_period', 2)

                # Ensure all configs have required base parameters
                full_config.setdefault('assessment_interval', 60)
                full_config.setdefault('max_loss_pct', 10)

                strategies[strategy_name] = full_config

        return strategies

    def update_default_params(self, updates: Dict[str, Any]):
        """Update default trading parameters for all strategies"""
        for key, value in updates.items():
            if hasattr(self.default_params, key):
                setattr(self.default_params, key, value)

# Global config manager instance
trading_config_manager = TradingConfigManager()
