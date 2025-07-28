import json
import csv
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import pandas as pd

@dataclass
class TradeRecord:
    """Complete trade record for analytics"""
    trade_id: str
    timestamp: datetime
    strategy_name: str
    symbol: str
    side: str  # BUY/SELL
    entry_price: float
    quantity: float
    margin_used: float
    leverage: int
    position_value_usdt: float
    exit_price: Optional[float] = None

    # Technical indicators at entry
    rsi_at_entry: Optional[float] = None
    macd_at_entry: Optional[float] = None
    sma_20_at_entry: Optional[float] = None
    sma_50_at_entry: Optional[float] = None
    volume_at_entry: Optional[float] = None

    # Trade outcome
    pnl_usdt: Optional[float] = None
    pnl_percentage: Optional[float] = None
    exit_reason: Optional[str] = None
    duration_minutes: Optional[int] = None

    # Market conditions
    market_trend: Optional[str] = None  # BULLISH/BEARISH/SIDEWAYS
    volatility_score: Optional[float] = None

    # Performance metrics
    risk_reward_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None

    # Additional metadata
    entry_signal_strength: Optional[float] = None
    market_phase: Optional[str] = None  # TRENDING/RANGING
    trade_status: str = "OPEN"  # OPEN/CLOSED/STOPPED

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON/CSV export"""
        data = asdict(self)
        # Convert datetime to ISO string
        data['timestamp'] = self.timestamp.isoformat()
        return data

class TradeLogger:
    """Logs trading activities"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.trades = []
        self.logger.info("📊 Trade Logger initialized")
    
    def log_trade(self, trade_data: dict) -> bool:
        """Log a new trade"""
        try:
            self.logger.info(f"📝 Logging trade: {trade_data.get('trade_id', 'unknown')}")
            self.trades.append(trade_data)
            return True
        except Exception as e:
            self.logger.error(f"❌ Error logging trade: {e}")
            return False
    
    def log_trade_exit(self, trade_id: str, exit_price: float, exit_reason: str, pnl_usdt: float, pnl_percentage: float, max_drawdown: float = 0) -> bool:
        """Log trade exit"""
        try:
            self.logger.info(f"📝 Logging trade exit: {trade_id}")
            # Find and update existing trade
            for trade in self.trades:
                if trade.get('trade_id') == trade_id:
                    trade.update({
                        'exit_price': exit_price,
                        'exit_reason': exit_reason,
                        'pnl_usdt': pnl_usdt,
                        'pnl_percentage': pnl_percentage,
                        'max_drawdown': max_drawdown
                    })
                    return True
            return False
        except Exception as e:
            self.logger.error(f"❌ Error logging trade exit: {e}")
            return False
    
    def get_trades(self) -> list:
        """Get all logged trades"""
        return self.trades.copy()
    
    def get_trade(self, trade_id: str) -> dict:
        """Get specific trade by ID"""
        for trade in self.trades:
            if trade.get('trade_id') == trade_id:
                return trade
        return {}

# Global instance
trade_logger = TradeLogger()