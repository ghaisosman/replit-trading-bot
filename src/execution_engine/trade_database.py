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
            self.logger.info(f"🔍 DEBUG: Starting database save to {self.db_file}")
            self.logger.info(f"🔍 DEBUG: Saving {len(self.trades)} trades")

            data = {
                'trades': self.trades,
                'last_updated': datetime.now().isoformat()
            }

            # Check if directory exists
            import os
            db_dir = os.path.dirname(self.db_file)
            if not os.path.exists(db_dir):
                self.logger.info(f"🔍 DEBUG: Creating directory {db_dir}")
                os.makedirs(db_dir, exist_ok=True)

            self.logger.info(f"🔍 DEBUG: Writing data to file")
            with open(self.db_file, 'w') as f:
                json.dump(data, f, indent=2)

            # Verify file was written
            if os.path.exists(self.db_file):
                file_size = os.path.getsize(self.db_file)
                self.logger.info(f"🔍 DEBUG: File written successfully, size: {file_size} bytes")

                # Try to read back the data to verify
                with open(self.db_file, 'r') as f:
                    saved_data = json.load(f)
                    saved_trades_count = len(saved_data.get('trades', {}))
                    self.logger.info(f"🔍 DEBUG: Verification read - {saved_trades_count} trades in file")
            else:
                self.logger.error(f"🔍 DEBUG: File was not created: {self.db_file}")

            self.logger.debug(f"💾 Saved {len(self.trades)} trades to database")
        except Exception as e:
            self.logger.error(f"❌ Error saving trade database: {e}")
            import traceback
            self.logger.error(f"🔍 DEBUG: Save traceback: {traceback.format_exc()}")

    def add_trade(self, trade_id: str, trade_data: Dict[str, Any]) -> bool:
        """Add a trade to the database - simplified version"""
        try:
            self.logger.info(f"🔍 DEBUG: Adding trade {trade_id} to database")
            self.logger.info(f"🔍 DEBUG: Input trade data keys: {list(trade_data.keys())}")

            # Basic validation only
            required_fields = ['strategy_name', 'symbol', 'side', 'quantity', 'entry_price', 'trade_status']
            missing_fields = [field for field in required_fields if field not in trade_data or trade_data[field] is None]

            if missing_fields:
                self.logger.error(f"❌ Missing required fields {missing_fields} in trade {trade_id}")
                return False

            self.logger.info(f"🔍 DEBUG: All required fields present")

            # Calculate missing basic fields if not provided
            entry_price = float(trade_data['entry_price'])
            quantity = float(trade_data['quantity'])

            self.logger.info(f"🔍 DEBUG: Entry price: {entry_price}, Quantity: {quantity}")

            if 'position_value_usdt' not in trade_data:
                trade_data['position_value_usdt'] = entry_price * quantity
                self.logger.info(f"🔍 DEBUG: Calculated position_value_usdt: {trade_data['position_value_usdt']}")

            if 'leverage' not in trade_data:
                trade_data['leverage'] = 1
                self.logger.info(f"🔍 DEBUG: Set default leverage: 1")

            if 'margin_used' not in trade_data:
                leverage = trade_data.get('leverage', 1)
                trade_data['margin_used'] = (entry_price * quantity) / leverage
                self.logger.info(f"🔍 DEBUG: Calculated margin_used: {trade_data['margin_used']}")

            # Add timestamp
            trade_data['created_at'] = datetime.now().isoformat()
            trade_data['last_updated'] = datetime.now().isoformat()

            self.logger.info(f"🔍 DEBUG: Added timestamps")

            # Store the trade
            trades_before = len(self.trades)
            self.trades[trade_id] = trade_data
            trades_after = len(self.trades)

            self.logger.info(f"🔍 DEBUG: Trades count before: {trades_before}, after: {trades_after}")

            # Verify trade was stored
            if trade_id in self.trades:
                self.logger.info(f"🔍 DEBUG: Trade {trade_id} successfully stored in memory")
            else:
                self.logger.error(f"🔍 DEBUG: Trade {trade_id} NOT stored in memory")
                return False

            # Save to file
            self.logger.info(f"🔍 DEBUG: Calling _save_database()")
            save_result = self._save_database()
            self.logger.info(f"🔍 DEBUG: _save_database() completed")

            self.logger.info(f"✅ Trade added to database: {trade_id} | {trade_data['symbol']} | {trade_data['side']}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error adding trade to database: {e}")
            import traceback
            self.logger.error(f"🔍 DEBUG: Full traceback: {traceback.format_exc()}")
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

    def find_trade_by_position(self, strategy_name: str, symbol: str, side: str, quantity: float, entry_price: float, tolerance: float = 0.01) -> Optional[str]:
        """Find trade by position details with tolerance"""
        try:
            # First try exact match for test scenarios
            for trade_id, trade_data in self.trades.items():
                if (trade_data.get('strategy_name') == strategy_name and
                    trade_data.get('symbol') == symbol and
                    trade_data.get('side') == side and
                    trade_data.get('quantity') == quantity and
                    trade_data.get('entry_price') == entry_price):
                    return trade_id

            # Then try tolerance-based match
            for trade_id, trade_data in self.trades.items():
                if (trade_data.get('strategy_name') == strategy_name and
                    trade_data.get('symbol') == symbol and
                    trade_data.get('side') == side and
                    abs(trade_data.get('quantity', 0) - quantity) <= tolerance and
                    abs(trade_data.get('entry_price', 0) - entry_price) <= abs(entry_price * tolerance)):
                    return trade_id
            return None
        except Exception as e:
            logging.getLogger(__name__).error(f"Error finding trade by position: {e}")
            return None

    def sync_trade_to_logger(self, trade_id: str):
        """Sync a specific trade from database to logger"""
        try:
            if trade_id not in self.trades:
                self.logger.warning(f"Trade {trade_id} not found in database for sync")
                return False

            trade_data = self.trades[trade_id]

            # Import logger
            from src.analytics.trade_logger import trade_logger

            # Sync the trade
            success = trade_logger.log_trade(trade_data)
            
            if success:
                self.logger.info(f"✅ Synced trade {trade_id} from database to logger")
            else:
                self.logger.error(f"❌ Failed to sync trade {trade_id} to logger")
                
            return success

        except Exception as e:
            self.logger.error(f"❌ Error syncing trade {trade_id} to logger: {e}")
            return False

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

    def get_recovery_candidates(self):
        """Get open trades that could be recovered - simplified approach"""
        try:
            candidates = []
            for trade_id, trade_data in self.trades.items():
                if trade_data.get('trade_status') == 'OPEN':
                    candidates.append({
                        'trade_id': trade_id,
                        'symbol': trade_data.get('symbol'),
                        'side': trade_data.get('side'),
                        'quantity': trade_data.get('quantity'),
                        'entry_price': trade_data.get('entry_price'),
                        'strategy_name': trade_data.get('strategy_name')
                    })

            self.logger.info(f"🔍 Found {len(candidates)} recovery candidates in database")
            return candidates

        except Exception as e:
            self.logger.error(f"❌ Error getting recovery candidates: {e}")
            return []

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