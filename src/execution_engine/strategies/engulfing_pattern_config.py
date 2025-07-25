"""
Engulfing Pattern Strategy - WEB DASHBOARD IS SINGLE SOURCE OF TRUTH
All configuration is now managed through the web dashboard interface.
"""

def get_engulfing_pattern_config():
    """Get engulfing pattern configuration for all symbols"""
    return {
        'ENGULFING_PATTERN_BTCUSDT': {
            'name': 'ENGULFING_PATTERN_BTCUSDT',
            'symbol': 'BTCUSDT',
            'timeframe': '1h',
            'margin_usdt': 10.0,
            'leverage': 3,
            'rsi_period': 14,
            'rsi_threshold': 50,
            'rsi_long_exit': 70,
            'rsi_short_exit': 30,
            'stable_candle_ratio': 0.2,  # Further relaxed for more pattern detection
            'price_lookback_bars': 5,
            'max_loss_pct': 10
        },
        'ENGULFING_PATTERN_ETHUSDT': {
            'name': 'ENGULFING_PATTERN_ETHUSDT',
            'symbol': 'ETHUSDT',
            'timeframe': '1h',
            'margin_usdt': 10.0,
            'leverage': 3,
            'rsi_period': 14,
            'rsi_threshold': 50,
            'rsi_long_exit': 70,
            'rsi_short_exit': 30,
            'stable_candle_ratio': 0.2,  # Further relaxed for more pattern detection
            'price_lookback_bars': 5,
            'max_loss_pct': 10
        },
        'ENGULFING_PATTERN_ADAUSDT': {
            'name': 'ENGULFING_PATTERN_ADAUSDT',
            'symbol': 'ADAUSDT',
            'timeframe': '1h',
            'margin_usdt': 10.0,
            'leverage': 3,
            'rsi_period': 14,
            'rsi_threshold': 50,
            'rsi_long_exit': 70,
            'rsi_short_exit': 30,
            'stable_candle_ratio': 0.2,  # Further relaxed for more pattern detection
            'price_lookback_bars': 5,
            'max_loss_pct': 10
        }
    }

class EngulfingPatternConfig:
    """Configuration class for Engulfing Pattern Strategy - kept for compatibility"""
    
    @staticmethod
    def get_config():
        """Get default configuration - web dashboard is source of truth"""
        return DEFAULT_PARAMETERS
    
    @staticmethod
    def update_config(updates):
        """Deprecated - use web dashboard"""
        import logging
        logging.getLogger(__name__).warning("Use web dashboard for configuration updates")
        return False

# Strategy description for dashboard display only
STRATEGY_DESCRIPTION = """
**Engulfing Pattern Strategy**

Combines powerful candlestick patterns with momentum and RSI filtering for high-probability entries.

**Key Features:**
- Detects bullish/bearish engulfing patterns
- Filters with RSI momentum (above/below 50)
- Confirms with 5-bar price momentum
- Validates candle stability using True Range
- RSI-based dynamic exits
- Full partial take profit support

**Best Timeframes:** 1H, 4H, 1D
**Recommended Symbols:** Major pairs with good liquidity (BTC, ETH, etc.)
"""

# Default parameters for dashboard initialization only
# All actual configuration comes from web dashboard
DEFAULT_PARAMETERS = {
    'rsi_period': 14,
    'rsi_threshold': 50,
    'rsi_long_exit': 70,
    'rsi_short_exit': 30,
    'stable_candle_ratio': 0.5,
    'price_lookback_bars': 5,
    'partial_tp_pnl_threshold': 0.0,
    'partial_tp_position_percentage': 0.0,
}