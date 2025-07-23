
"""
Engulfing Pattern Strategy Configuration

This strategy combines:
1. Bullish/Bearish Engulfing candlestick patterns
2. RSI filtering (above/below 50)
3. Price momentum confirmation (5-bar lookback)
4. Stable candle validation using True Range

Entry Conditions:
- Long: Bullish Engulfing + RSI < 50 + Price down over 5 bars + Stable candle
- Short: Bearish Engulfing + RSI > 50 + Price up over 5 bars + Stable candle

Exit Conditions:
- RSI-based exits (configurable levels)
- Stop loss based on max loss percentage
- Partial take profit support
"""

# Default configuration for Engulfing Pattern Strategy
DEFAULT_CONFIG = {
    # Basic trading parameters
    'symbol': 'BTCUSDT',
    'margin': 25.0,
    'leverage': 8,
    'timeframe': '1h',
    'max_loss_pct': 10.0,
    'assessment_interval': 90,  # seconds
    'cooldown_period': 600,     # seconds
    'decimals': 3,
    'min_volume': 2000000,
    
    # Engulfing Pattern specific parameters
    'rsi_period': 14,           # RSI calculation period
    'rsi_threshold': 50,        # RSI threshold for long/short bias
    'rsi_long_exit': 70,        # RSI level to exit long positions
    'rsi_short_exit': 30,       # RSI level to exit short positions
    'stable_candle_ratio': 0.5, # Minimum body-to-range ratio for stable candle
    'price_lookback_bars': 5,   # Number of bars to look back for price momentum
    
    # Partial Take Profit (disabled by default)
    'partial_tp_pnl_threshold': 0.0,      # PnL % threshold to trigger partial TP
    'partial_tp_position_percentage': 0.0, # % of position to close on partial TP
    
    # Advanced parameters
    'enable_volume_filter': False,         # Optional volume filtering
    'min_engulfing_ratio': 1.0,           # Minimum engulfing ratio (1.0 = full engulfing)
    'confirm_with_next_candle': False,     # Wait for next candle confirmation
}

# Parameter validation rules
VALIDATION_RULES = {
    'rsi_period': {'min': 5, 'max': 50, 'default': 14},
    'rsi_threshold': {'min': 30, 'max': 70, 'default': 50},
    'rsi_long_exit': {'min': 50, 'max': 90, 'default': 70},
    'rsi_short_exit': {'min': 10, 'max': 50, 'default': 30},
    'stable_candle_ratio': {'min': 0.1, 'max': 1.0, 'default': 0.5},
    'price_lookback_bars': {'min': 3, 'max': 20, 'default': 5},
    'partial_tp_pnl_threshold': {'min': 0.0, 'max': 50.0, 'default': 0.0},
    'partial_tp_position_percentage': {'min': 0.0, 'max': 90.0, 'default': 0.0},
}

# Strategy description for dashboard
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
