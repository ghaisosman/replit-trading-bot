"""
Engulfing Pattern Strategy - WEB DASHBOARD IS SINGLE SOURCE OF TRUTH
All configuration is now managed through the web dashboard interface.
"""

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