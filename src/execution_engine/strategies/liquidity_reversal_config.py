
import json
from typing import Dict, Any

class LiquidityReversalConfig:
    """Configuration for Smart Money Liquidity Reversal Strategy"""
    
    def __init__(self):
        self.strategy_name = "LIQUIDITY_REVERSAL"
        self.default_config = {
            "symbol": "BTCUSDT",
            "margin": 50.0,
            "leverage": 5,
            "timeframe": "15m",
            "max_loss_pct": 8.0,
            "assessment_interval": 30,
            "cooldown_period": 300,
            "decimals": 3,
            
            # Liquidity sweep detection parameters
            "swing_lookback_periods": 20,
            "round_number_proximity": 0.002,  # 0.2% proximity to round numbers
            "sweep_wick_threshold": 0.005,    # 0.5% wick beyond level
            "volume_surge_multiplier": 2.0,   # 2x average volume
            
            # Reversal confirmation parameters
            "reclaim_candles": 3,             # Candles to confirm reclaim
            "reclaim_threshold": 0.001,       # 0.1% above/below swept level
            
            # Funding rate sentiment filter
            "funding_bullish_threshold": -0.001,  # -0.1% funding favors longs
            "funding_bearish_threshold": 0.001,   # +0.1% funding favors shorts
            
            # Risk management
            "confirmation_timeout": 5,        # Max candles to wait for confirmation
            "position_sizing_method": "fixed_margin",
            "max_daily_trades": 3,
            
            # Exit conditions
            "profit_target_method": "mean_reversion",
            "mean_reversion_periods": 50,     # MA period for mean reversion target
            "max_hold_duration": 240,        # Max hold time in minutes
        }
    
    def get_config(self) -> Dict[str, Any]:
        """Get strategy configuration"""
        return self.default_config.copy()
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate strategy configuration"""
        required_keys = [
            'symbol', 'margin', 'leverage', 'timeframe',
            'swing_lookback_periods', 'sweep_wick_threshold',
            'volume_surge_multiplier', 'reclaim_candles'
        ]
        
        for key in required_keys:
            if key not in config:
                return False
        
        # Validate ranges
        if not (1 <= config['leverage'] <= 125):
            return False
        if not (0.1 <= config['margin'] <= 10000):
            return False
        if not (5 <= config['swing_lookback_periods'] <= 100):
            return False
        
        return True
    
    def get_strategy_description(self) -> str:
        """Get strategy description"""
        return """
        Smart Money Liquidity Reversal Strategy
        
        Core Thesis: Exploit retail crowd behavior by trading against stop hunts 
        and fakeouts at high-liquidity inflection points.
        
        Entry Logic:
        1. Detect liquidity sweeps through swing highs/lows or round numbers
        2. Confirm price reclaims the swept level quickly
        3. Filter with funding rate sentiment
        4. Enter counter-trend with tight stops
        
        Exit Logic:
        - Target mean reversion to moving average
        - Stop loss just beyond sweep level
        - Time-based exit if no momentum
        """

# Save default configuration to JSON file
if __name__ == "__main__":
    config = LiquidityReversalConfig()
    
    with open('src/execution_engine/strategies/liquidity_reversal_config_data.json', 'w') as f:
        json.dump({
            "strategy_name": config.strategy_name,
            "description": config.get_strategy_description(),
            "default_config": config.get_config()
        }, f, indent=2)
    
    print("✅ Liquidity Reversal strategy configuration created")
