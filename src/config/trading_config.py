
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
    """Manages trading configurations for all strategies"""
    
    def __init__(self):
        # Default parameters for easy modification
        self.default_params = TradingParameters()
        
        # Strategy-specific overrides
        self.strategy_overrides = {
            'rsi_oversold': {
                'symbol': 'SOLUSDT',
                'margin': 12.5,
                'leverage': 25,
                'timeframe': '15m',
                'rsi_long_entry': 40,
                'rsi_long_exit': 55,
                'rsi_short_entry': 60,  # WEB DASHBOARD SETTING (YOUR SETTING)
                'rsi_short_exit': 45,
                'max_loss_pct': 10,
                'assessment_interval': 60,  # 1 minute for faster response
                # WEB DASHBOARD IS SINGLE SOURCE OF TRUTH - OVERRIDES ALL FILES
            },
            'macd_divergence': {
                'symbol': 'BTCUSDT',
                'margin': 23,
                'leverage': 5,
                'timeframe': '5m',
                'assessment_interval': 30,  # 30 seconds for 5m timeframe
            },
        }
    
    def get_strategy_config(self, strategy_name: str, base_config: Dict[str, Any]) -> Dict[str, Any]:
        """Get strategy config with applied trading parameters - WEB DASHBOARD IS SINGLE SOURCE OF TRUTH"""
        # Start with base strategy config
        config = base_config.copy()
        
        # Apply default parameters
        default_params = self.default_params.to_dict()
        
        # Apply strategy-specific overrides from web dashboard (HIGHEST PRIORITY)
        if strategy_name in self.strategy_overrides:
            strategy_params = self.strategy_overrides[strategy_name]
            default_params.update(strategy_params)
        
        # Web dashboard settings ALWAYS override file-based configs
        config.update(default_params)
        
        # Log the final config being used for debugging
        import logging
        logging.getLogger(__name__).info(f"🎯 FINAL CONFIG for {strategy_name}: {config}")
        
        return config
    
    def update_strategy_params(self, strategy_name: str, updates: Dict[str, Any]):
        """Update trading parameters for a specific strategy - WEB DASHBOARD PRIORITY"""
        if strategy_name not in self.strategy_overrides:
            self.strategy_overrides[strategy_name] = {}
        
        # Ensure assessment_interval is properly handled
        if 'assessment_interval' in updates:
            updates['assessment_interval'] = int(updates['assessment_interval'])
            # Validate assessment interval (5 seconds to 5 minutes)
            if updates['assessment_interval'] < 5:
                updates['assessment_interval'] = 5
            elif updates['assessment_interval'] > 300:
                updates['assessment_interval'] = 300
        
        # WEB DASHBOARD SETTINGS OVERRIDE ALL OTHER SOURCES
        self.strategy_overrides[strategy_name].update(updates)
        
        # Force update any running bot instance immediately
        self._force_update_running_bot(strategy_name, updates)
        
        # Log the update for debugging
        import logging
        logging.getLogger(__name__).info(f"🌐 WEB DASHBOARD UPDATE | {strategy_name} | {updates}")
        logging.getLogger(__name__).info(f"🎯 WEB DASHBOARD IS SINGLE SOURCE OF TRUTH - OVERRIDES ALL FILES")
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
    
    def update_default_params(self, updates: Dict[str, Any]):
        """Update default trading parameters for all strategies"""
        for key, value in updates.items():
            if hasattr(self.default_params, key):
                setattr(self.default_params, key, value)

# Global config manager instance
trading_config_manager = TradingConfigManager()
