
import json
import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

class TradeDatabase:
    """Simple trade database for tracking bot trades and validating positions"""
    
    def __init__(self, db_file: str = "trading_data/trade_database.json"):
        self.logger = logging.getLogger(__name__)
        self.db_file = db_file
        self.trades = {}
        self._ensure_directory()
        self._load_database()
    
    def _ensure_directory(self):
        """Ensure the trading_data directory exists"""
        os.makedirs(os.path.dirname(self.db_file), exist_ok=True)
    
    def _load_database(self):
        """Load trades from database file"""
        try:
            if os.path.exists(self.db_file):
                with open(self.db_file, 'r') as f:
                    data = json.load(f)
                    self.trades = data.get('trades', {})
                    self.logger.debug(f"Loaded {len(self.trades)} trades from database")
                    
                    # Automatic cleanup of stale trades on load
                    self.cleanup_stale_open_trades(hours=6)  # Clean trades older than 6 hours
            else:
                self.logger.info("Trade database file not found, starting with empty database")
                self.trades = {}
        except Exception as e:
            self.logger.error(f"Error loading trade database: {e}")
            self.trades = {}
    
    def _save_database(self):
        """Save trades to database file"""
        try:
            data = {
                'trades': self.trades,
                'last_updated': datetime.now().isoformat()
            }
            with open(self.db_file, 'w') as f:
                json.dump(data, f, indent=2)
            self.logger.debug(f"Saved {len(self.trades)} trades to database")
        except Exception as e:
            self.logger.error(f"Error saving trade database: {e}")
    
    def add_trade(self, trade_id: str, trade_data: Dict[str, Any]):
        """Add a trade to the database"""
        try:
            self.trades[trade_id] = trade_data
            self._save_database()
            self.logger.debug(f"Added trade {trade_id} to database")
        except Exception as e:
            self.logger.error(f"Error adding trade to database: {e}")
    
    def find_trade_by_position(self, strategy_name: str, symbol: str, side: str, 
                             quantity: float, entry_price: float, tolerance: float = 0.01) -> Optional[str]:
        """Find a trade ID by position details with tolerance for price/quantity matching"""
        try:
            self.logger.debug(f"Searching for trade: {strategy_name} | {symbol} | {side} | Qty: {quantity} | Entry: ${entry_price}")
            
            for trade_id, trade_data in self.trades.items():
                # Match strategy and symbol
                if (trade_data.get('strategy_name') == strategy_name and 
                    trade_data.get('symbol') == symbol and
                    trade_data.get('side') == side):
                    
                    # Check quantity match with tolerance
                    db_quantity = trade_data.get('quantity', 0)
                    quantity_diff = abs(db_quantity - quantity)
                    quantity_tolerance = max(quantity * tolerance, 0.001)
                    
                    # Check price match with tolerance
                    db_entry_price = trade_data.get('entry_price', 0)
                    price_diff = abs(db_entry_price - entry_price)
                    price_tolerance = max(entry_price * tolerance, 0.01)
                    
                    if quantity_diff <= quantity_tolerance and price_diff <= price_tolerance:
                        self.logger.debug(f"Found matching trade: {trade_id}")
                        return trade_id
                    else:
                        self.logger.debug(f"Trade {trade_id} close but not exact match - "
                                        f"Qty diff: {quantity_diff:.6f} (tol: {quantity_tolerance:.6f}), "
                                        f"Price diff: {price_diff:.4f} (tol: {price_tolerance:.4f})")
            
            self.logger.debug(f"No matching trade found for {strategy_name} | {symbol}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error searching for trade: {e}")
            return None
    
    def get_trade(self, trade_id: str) -> Optional[Dict[str, Any]]:
        """Get trade data by ID"""
        return self.trades.get(trade_id)
    
    def update_trade(self, trade_id: str, updates: Dict[str, Any]):
        """Update trade data"""
        try:
            if trade_id in self.trades:
                self.trades[trade_id].update(updates)
                self._save_database()
                self.logger.debug(f"Updated trade {trade_id}")
            else:
                self.logger.warning(f"Trade {trade_id} not found for update")
        except Exception as e:
            self.logger.error(f"Error updating trade: {e}")
    
    def get_all_trades(self) -> Dict[str, Dict[str, Any]]:
        """Get all trades"""
        return self.trades.copy()
    
    def cleanup_old_trades(self, days: int = 30):
        """Clean up trades older than specified days"""
        try:
            current_time = datetime.now()
            trades_to_remove = []
            
            for trade_id, trade_data in self.trades.items():
                entry_time_str = trade_data.get('entry_time') or trade_data.get('timestamp')
                if entry_time_str:
                    try:
                        entry_time = datetime.fromisoformat(entry_time_str.replace('Z', '+00:00'))
                        if (current_time - entry_time).days > days:
                            trades_to_remove.append(trade_id)
                    except ValueError:
                        continue
            
            for trade_id in trades_to_remove:
                del self.trades[trade_id]
            
            if trades_to_remove:
                self._save_database()
                self.logger.info(f"Cleaned up {len(trades_to_remove)} old trades")
                
        except Exception as e:
            self.logger.error(f"Error cleaning up old trades: {e}")
    
    def cleanup_stale_open_trades(self, hours: int = 24):
        """Clean up stale open trades that are likely already closed"""
        try:
            current_time = datetime.now()
            trades_to_close = []
            
            for trade_id, trade_data in self.trades.items():
                # Check if trade is marked as OPEN but is old
                if trade_data.get('trade_status') == 'OPEN':
                    entry_time_str = trade_data.get('timestamp')
                    if entry_time_str:
                        try:
                            entry_time = datetime.fromisoformat(entry_time_str.replace('Z', '+00:00'))
                            hours_old = (current_time - entry_time).total_seconds() / 3600
                            
                            if hours_old > hours:
                                trades_to_close.append(trade_id)
                        except ValueError:
                            continue
            
            # Mark stale trades as closed with unknown exit
            for trade_id in trades_to_close:
                self.trades[trade_id]['trade_status'] = 'CLOSED'
                self.trades[trade_id]['exit_reason'] = 'Stale Trade - Auto Closed'
                self.trades[trade_id]['pnl_usdt'] = 0
                self.trades[trade_id]['pnl_percentage'] = 0
            
            if trades_to_close:
                self._save_database()
                self.logger.info(f"Marked {len(trades_to_close)} stale open trades as closed")
                
        except Exception as e:
            self.logger.error(f"Error cleaning up stale trades: {e}")
