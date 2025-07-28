import json
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

class Position:
    def __init__(self, trade_id: str, strategy_name: str, symbol: str, side: str, 
                 entry_price: float, quantity: float, stop_loss: float = None, 
                 take_profit: float = None, created_at: str = None):
        self.trade_id = trade_id
        self.strategy_name = strategy_name
        self.symbol = symbol
        self.side = side
        self.entry_price = entry_price
        self.quantity = quantity
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.created_at = created_at or datetime.now().isoformat()

class TradeDatabase:
    """Simplified trade database with local storage only"""

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
        """Load trades from database file with improved error handling"""
        try:
            if os.path.exists(self.db_file):
                with open(self.db_file, 'r') as f:
                    data = json.load(f)

                    # Handle different data formats with robust error handling
                    if isinstance(data, dict):
                        if 'trades' in data:
                            trades_data = data['trades']
                            # Ensure trades_data is a dict with proper validation
                            if isinstance(trades_data, dict):
                                # Validate that all keys are strings and values are dicts
                                valid_trades = {}
                                for key, value in trades_data.items():
                                    if isinstance(key, str) and isinstance(value, dict):
                                        valid_trades[key] = value
                                    else:
                                        self.logger.warning(f"📊 Skipping invalid trade entry: key={type(key)}, value={type(value)}")
                                self.trades = valid_trades
                                self.logger.info(f"📊 Loaded {len(valid_trades)} valid trades from {len(trades_data)} entries")
                            else:
                                self.logger.warning("📊 Invalid trades format, starting with empty database")
                                self.trades = {}
                        else:
                            # If data is directly the trades dict, validate it thoroughly
                            if (isinstance(data, dict) and 
                                all(isinstance(key, str) for key in data.keys()) and
                                all(isinstance(value, dict) for value in data.values())):
                                self.trades = data
                                self.logger.info(f"📊 Loaded {len(self.trades)} trades directly from database")
                            else:
                                self.logger.warning("📊 Invalid database format, starting with empty database")
                                self.trades = {}
                    else:
                        self.logger.warning("📊 Database file contains invalid data, starting with empty database")
                        self.trades = {}
            else:
                self.logger.info("📊 No existing database file found, starting with empty database")
                self.trades = {}

        except json.JSONDecodeError as e:
            self.logger.error(f"❌ JSON decode error in database file: {e}")
            self.logger.info("📊 Starting with empty database due to corruption")
            self.trades = {}
        except Exception as e:
            self.logger.error(f"❌ Error loading database: {e}")
            self.logger.info("📊 Starting with empty database due to error")
            self.trades = {}

    def _save_database(self):
        """Save trades to database file with error handling"""
        try:
            # Create backup of existing file
            if os.path.exists(self.db_file):
                backup_file = f"{self.db_file}.backup"
                try:
                    with open(self.db_file, 'r') as f:
                        backup_data = f.read()
                    with open(backup_file, 'w') as f:
                        f.write(backup_data)
                except Exception as e:
                    self.logger.warning(f"⚠️ Could not create backup: {e}")

            # Save current data
            data = {
                'trades': self.trades,
                'last_updated': datetime.now().isoformat(),
                'total_trades': len(self.trades)
            }

            with open(self.db_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)

            self.logger.info(f"✅ Database saved successfully: {len(self.trades)} trades")

        except Exception as e:
            self.logger.error(f"❌ Error saving database: {e}")
            return False

        return True

    def add_trade(self, trade_id: str, trade_data: Dict[str, Any]) -> bool:
        """Add a new trade to the database"""
        try:
            if not trade_id or not trade_data:
                self.logger.error("❌ Invalid trade data provided")
                return False

            # Add timestamp if not present
            if 'timestamp' not in trade_data:
                trade_data['timestamp'] = datetime.now().isoformat()

            # Add trade status if not present
            if 'trade_status' not in trade_data:
                trade_data['trade_status'] = 'OPEN'

            self.trades[trade_id] = trade_data
            self._save_database()
            
            self.logger.info(f"✅ Trade added: {trade_id} - {trade_data.get('symbol', 'N/A')}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error adding trade: {e}")
            return False

    def update_trade(self, trade_id: str, updates: Dict[str, Any]) -> bool:
        """Update an existing trade"""
        try:
            if trade_id not in self.trades:
                self.logger.error(f"❌ Trade not found: {trade_id}")
                return False

            # Update the trade data
            self.trades[trade_id].update(updates)
            
            # Add update timestamp
            self.trades[trade_id]['last_updated'] = datetime.now().isoformat()
            
            self._save_database()
            
            self.logger.info(f"✅ Trade updated: {trade_id}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error updating trade: {e}")
            return False

    def get_trade(self, trade_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific trade by ID"""
        return self.trades.get(trade_id)

    def get_all_trades(self) -> Dict[str, Dict[str, Any]]:
        """Get all trades"""
        return self.trades.copy()

    def find_trade_by_position(self, strategy_name: str, symbol: str, side: str, 
                              quantity: float, entry_price: float, tolerance: float = 0.01) -> Optional[str]:
        """Find a trade by position details"""
        try:
            for trade_id, trade_data in self.trades.items():
                if (trade_data.get('strategy_name') == strategy_name and
                    trade_data.get('symbol') == symbol and
                    trade_data.get('side') == side and
                    abs(trade_data.get('quantity', 0) - quantity) <= tolerance and
                    abs(trade_data.get('entry_price', 0) - entry_price) <= tolerance):
                    return trade_id
            return None
        except Exception as e:
            self.logger.error(f"❌ Error finding trade by position: {e}")
            return None

    def get_open_trades(self) -> Dict[str, Dict[str, Any]]:
        """Get all open trades"""
        return {trade_id: trade_data for trade_id, trade_data in self.trades.items() 
                if trade_data.get('trade_status') == 'OPEN'}

    def get_closed_trades(self) -> Dict[str, Dict[str, Any]]:
        """Get all closed trades"""
        return {trade_id: trade_data for trade_id, trade_data in self.trades.items() 
                if trade_data.get('trade_status') == 'CLOSED'}

    def cleanup_old_trades(self, days: int = 30):
        """Clean up old closed trades"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            trades_to_remove = []

            for trade_id, trade_data in self.trades.items():
                if trade_data.get('trade_status') == 'CLOSED':
                    timestamp = trade_data.get('timestamp')
                    if timestamp:
                        try:
                            trade_date = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            if trade_date < cutoff_date:
                                trades_to_remove.append(trade_id)
                        except:
                            continue

            for trade_id in trades_to_remove:
                del self.trades[trade_id]

            if trades_to_remove:
                self._save_database()
                self.logger.info(f"✅ Cleaned up {len(trades_to_remove)} old trades")

        except Exception as e:
            self.logger.error(f"❌ Error cleaning up old trades: {e}")

    def search_trades(self, **criteria) -> Dict[str, Dict[str, Any]]:
        """Search trades by criteria"""
        try:
            results = {}
            for trade_id, trade_data in self.trades.items():
                match = True
                for key, value in criteria.items():
                    if trade_data.get(key) != value:
                        match = False
                        break
                if match:
                    results[trade_id] = trade_data
            return results
        except Exception as e:
            self.logger.error(f"❌ Error searching trades: {e}")
            return {}