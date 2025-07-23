import json
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

class TradeDatabase:
    """Simplified trade database - mirrors trade logger data only"""

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
                    self.logger.info(f"📊 Loaded {len(self.trades)} trades from database")
            else:
                self.logger.info("📊 Trade database file not found, starting with empty database")
                self.trades = {}
        except Exception as e:
            self.logger.error(f"❌ Error loading trade database: {e}")
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
            self.logger.debug(f"💾 Saved {len(self.trades)} trades to database")
        except Exception as e:
            self.logger.error(f"❌ Error saving trade database: {e}")

    def add_trade(self, trade_id: str, trade_data: Dict[str, Any]) -> bool:
        """Add a trade to the database - simplified version"""
        try:
            # Basic validation only
            required_fields = ['strategy_name', 'symbol', 'side', 'quantity', 'entry_price', 'trade_status']
            missing_fields = [field for field in required_fields if field not in trade_data or trade_data[field] is None]

            if missing_fields:
                self.logger.error(f"❌ Missing required fields {missing_fields} in trade {trade_id}")
                return False

            # Calculate missing basic fields if not provided
            entry_price = float(trade_data['entry_price'])
            quantity = float(trade_data['quantity'])

            if 'position_value_usdt' not in trade_data:
                trade_data['position_value_usdt'] = entry_price * quantity

            if 'leverage' not in trade_data:
                trade_data['leverage'] = 1

            if 'margin_used' not in trade_data:
                leverage = trade_data.get('leverage', 1)
                trade_data['margin_used'] = (entry_price * quantity) / leverage

            # Add timestamp
            trade_data['created_at'] = datetime.now().isoformat()
            trade_data['last_updated'] = datetime.now().isoformat()

            # Store the trade
            self.trades[trade_id] = trade_data
            self._save_database()

            self.logger.info(f"✅ Trade added to database: {trade_id} | {trade_data['symbol']} | {trade_data['side']}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error adding trade to database: {e}")
            return False

    def update_trade(self, trade_id: str, updates: Dict[str, Any]) -> bool:
        """Update trade data - simplified version"""
        try:
            if trade_id in self.trades:
                updates['last_updated'] = datetime.now().isoformat()
                self.trades[trade_id].update(updates)
                self._save_database()
                self.logger.info(f"✅ Trade updated in database: {trade_id}")
                return True
            else:
                self.logger.warning(f"⚠️ Trade {trade_id} not found for update")
                return False
        except Exception as e:
            self.logger.error(f"❌ Error updating trade: {e}")
            return False

    def get_trade(self, trade_id: str) -> Optional[Dict[str, Any]]:
        """Get trade data by ID"""
        return self.trades.get(trade_id)

    def get_all_trades(self) -> Dict[str, Dict[str, Any]]:
        """Get all trades"""
        return self.trades.copy()

    def find_trade_by_position(self, strategy_name: str, symbol: str, side: str, 
                             quantity: float, entry_price: float, tolerance: float = 0.01) -> Optional[str]:
        """Find a trade ID by position details with tolerance for price/quantity matching"""
        try:
            for trade_id, trade_data in self.trades.items():
                # If strategy_name is 'UNKNOWN', search across ALL strategies
                strategy_match = (strategy_name == 'UNKNOWN' or 
                                trade_data.get('strategy_name') == strategy_name)

                if (strategy_match and 
                    trade_data.get('symbol') == symbol and
                    trade_data.get('side') == side and
                    trade_data.get('trade_status') == 'OPEN'):

                    # Check quantity and price match with tolerance
                    db_quantity = trade_data.get('quantity', 0)
                    db_entry_price = trade_data.get('entry_price', 0)

                    quantity_diff = abs(db_quantity - quantity)
                    price_diff = abs(db_entry_price - entry_price)

                    quantity_tolerance = max(quantity * tolerance, 0.001)
                    price_tolerance = max(entry_price * tolerance, 0.01)

                    if quantity_diff <= quantity_tolerance and price_diff <= price_tolerance:
                        return trade_id

            return None

        except Exception as e:
            self.logger.error(f"❌ Error searching for trade: {e}")
            return None

    def sync_from_logger(self):
        """Sync database with trade logger - logger is source of truth"""
        try:
            from src.analytics.trade_logger import trade_logger

            logger_trades = {t.trade_id: t for t in trade_logger.trades}
            sync_count = 0

            for trade_id, logger_trade in logger_trades.items():
                # Convert logger trade to dict
                trade_dict = logger_trade.to_dict()

                if trade_id in self.trades:
                    # Update existing trade with logger data
                    self.trades[trade_id].update(trade_dict)
                    self.trades[trade_id]['last_updated'] = datetime.now().isoformat()
                else:
                    # Add missing trade from logger
                    trade_dict['created_at'] = datetime.now().isoformat()
                    trade_dict['last_updated'] = datetime.now().isoformat()
                    self.trades[trade_id] = trade_dict

                sync_count += 1

            self._save_database()
            self.logger.info(f"✅ Synced {sync_count} trades from logger to database")
            return sync_count

        except Exception as e:
            self.logger.error(f"❌ Error syncing from logger: {e}")
            return 0

    def cleanup_old_trades(self, days: int = 30):
        """Clean up trades older than specified days"""
        try:
            current_time = datetime.now()
            trades_to_remove = []

            for trade_id, trade_data in self.trades.items():
                created_at_str = trade_data.get('created_at')
                if created_at_str:
                    try:
                        created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                        if (current_time - created_at).days > days:
                            trades_to_remove.append(trade_id)
                    except ValueError:
                        continue

            for trade_id in trades_to_remove:
                del self.trades[trade_id]

            if trades_to_remove:
                self._save_database()
                self.logger.info(f"🧹 Cleaned up {len(trades_to_remove)} old trades")

        except Exception as e:
            self.logger.error(f"❌ Error cleaning up old trades: {e}")