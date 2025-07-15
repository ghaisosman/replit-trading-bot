
import json
import os
from datetime import datetime
from typing import Dict, Optional, Any
from dataclasses import dataclass, asdict
import uuid
import logging

@dataclass
class TradeRecord:
    trade_id: str
    strategy_name: str
    symbol: str
    side: str
    quantity: float
    entry_price: float
    entry_time: datetime
    order_id: Optional[int] = None
    status: str = "OPEN"
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_reason: Optional[str] = None
    pnl: Optional[float] = None

class TradeDatabase:
    """Persistent trade database for position recovery"""
    
    def __init__(self, db_file: str = "trading_data/trades.json"):
        self.db_file = db_file
        self.logger = logging.getLogger(__name__)
        self.trades: Dict[str, TradeRecord] = {}
        self._ensure_directory()
        self._load_trades()
    
    def _ensure_directory(self):
        """Ensure trading_data directory exists"""
        os.makedirs(os.path.dirname(self.db_file), exist_ok=True)
    
    def _load_trades(self):
        """Load trades from JSON file"""
        try:
            if os.path.exists(self.db_file):
                with open(self.db_file, 'r') as f:
                    data = json.load(f)
                
                for trade_id, trade_data in data.items():
                    # Convert datetime strings back to datetime objects
                    if 'entry_time' in trade_data and trade_data['entry_time']:
                        trade_data['entry_time'] = datetime.fromisoformat(trade_data['entry_time'])
                    if 'exit_time' in trade_data and trade_data['exit_time']:
                        trade_data['exit_time'] = datetime.fromisoformat(trade_data['exit_time'])
                    
                    self.trades[trade_id] = TradeRecord(**trade_data)
                
                self.logger.info(f"✅ TRADE DB: Loaded {len(self.trades)} trades from database")
            else:
                self.logger.info("📊 TRADE DB: No existing trade database found, starting fresh")
        except Exception as e:
            self.logger.error(f"❌ TRADE DB: Error loading trades: {e}")
            self.trades = {}
    
    def _save_trades(self):
        """Save trades to JSON file"""
        try:
            data = {}
            for trade_id, trade_record in self.trades.items():
                trade_data = asdict(trade_record)
                # Convert datetime objects to strings for JSON serialization
                if trade_data['entry_time']:
                    trade_data['entry_time'] = trade_data['entry_time'].isoformat()
                if trade_data['exit_time']:
                    trade_data['exit_time'] = trade_data['exit_time'].isoformat()
                
                data[trade_id] = trade_data
            
            with open(self.db_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            self.logger.debug(f"💾 TRADE DB: Saved {len(self.trades)} trades to database")
        except Exception as e:
            self.logger.error(f"❌ TRADE DB: Error saving trades: {e}")
    
    def create_trade(self, strategy_name: str, symbol: str, side: str, 
                    quantity: float, entry_price: float, order_id: Optional[int] = None) -> str:
        """Create a new trade record and return trade ID"""
        trade_id = str(uuid.uuid4())
        
        trade_record = TradeRecord(
            trade_id=trade_id,
            strategy_name=strategy_name,
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            entry_time=datetime.now(),
            order_id=order_id,
            status="OPEN"
        )
        
        self.trades[trade_id] = trade_record
        self._save_trades()
        
        self.logger.info(f"📊 TRADE DB: Created trade {trade_id} | {strategy_name} | {symbol} | {side} | {quantity}")
        return trade_id
    
    def close_trade(self, trade_id: str, exit_price: float, exit_reason: str, pnl: float):
        """Close a trade record"""
        if trade_id in self.trades:
            trade = self.trades[trade_id]
            trade.exit_price = exit_price
            trade.exit_time = datetime.now()
            trade.exit_reason = exit_reason
            trade.pnl = pnl
            trade.status = "CLOSED"
            
            self._save_trades()
            self.logger.info(f"📊 TRADE DB: Closed trade {trade_id} | PnL: ${pnl:.2f}")
        else:
            self.logger.warning(f"❌ TRADE DB: Trade ID {trade_id} not found for closing")
    
    def get_open_trades(self) -> Dict[str, TradeRecord]:
        """Get all open trades"""
        return {tid: trade for tid, trade in self.trades.items() if trade.status == "OPEN"}
    
    def find_trade_by_position(self, strategy_name: str, symbol: str, side: str, 
                              quantity: float, entry_price: float, tolerance: float = 0.01) -> Optional[str]:
        """Find a trade ID that matches the given position parameters"""
        for trade_id, trade in self.trades.items():
            if (trade.status == "OPEN" and
                trade.strategy_name == strategy_name and
                trade.symbol == symbol and
                trade.side == side and
                abs(trade.quantity - quantity) < tolerance and
                abs(trade.entry_price - entry_price) < tolerance):
                
                self.logger.info(f"✅ TRADE DB: Found matching trade {trade_id} for {strategy_name} {symbol}")
                return trade_id
        
        self.logger.debug(f"❌ TRADE DB: No matching trade found for {strategy_name} {symbol} {side} {quantity}")
        return None
    
    def get_trade(self, trade_id: str) -> Optional[TradeRecord]:
        """Get a specific trade by ID"""
        return self.trades.get(trade_id)

# Global trade database instance
trade_db = TradeDatabase()
