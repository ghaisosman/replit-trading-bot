
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
import os

class SharedTradeDatabase:
    """Shared database using Replit Key-Value Store for cross-deployment sync"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.db = None
        self._initialize_db()

    def _initialize_db(self):
        """Initialize Replit database connection"""
        try:
            from replit import db
            self.db = db
            self.logger.info("✅ Connected to Replit shared database")
            
            # Initialize trades structure if not exists
            if "trades" not in self.db:
                self.db["trades"] = {}
                self.logger.info("📊 Initialized trades structure in shared database")
                
        except ImportError:
            self.logger.warning("⚠️ Replit database not available, falling back to local storage")
            self.db = None
        except Exception as e:
            self.logger.error(f"❌ Error initializing shared database: {e}")
            self.db = None

    def add_trade(self, trade_id: str, trade_data: Dict[str, Any]) -> bool:
        """Add trade to shared database"""
        try:
            if not self.db:
                self.logger.warning("❌ Shared database not available")
                return False

            # Add timestamp for sync tracking
            trade_data['shared_db_created'] = datetime.now().isoformat()
            trade_data['shared_db_updated'] = datetime.now().isoformat()
            
            # Get current trades
            trades = dict(self.db.get("trades", {}))
            trades[trade_id] = trade_data
            
            # Update database
            self.db["trades"] = trades
            
            self.logger.info(f"✅ Trade added to shared database: {trade_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error adding trade to shared database: {e}")
            return False

    def update_trade(self, trade_id: str, updates: Dict[str, Any]) -> bool:
        """Update trade in shared database"""
        try:
            if not self.db:
                return False

            trades = dict(self.db.get("trades", {}))
            
            if trade_id not in trades:
                self.logger.warning(f"⚠️ Trade {trade_id} not found in shared database")
                return False

            # Add update timestamp
            updates['shared_db_updated'] = datetime.now().isoformat()
            
            # Update trade data
            trades[trade_id].update(updates)
            self.db["trades"] = trades
            
            self.logger.info(f"✅ Trade updated in shared database: {trade_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error updating trade in shared database: {e}")
            return False

    def get_trade(self, trade_id: str) -> Optional[Dict[str, Any]]:
        """Get trade from shared database"""
        try:
            if not self.db:
                return None

            trades = dict(self.db.get("trades", {}))
            return trades.get(trade_id)
            
        except Exception as e:
            self.logger.error(f"❌ Error getting trade from shared database: {e}")
            return None

    def get_all_trades(self) -> Dict[str, Dict[str, Any]]:
        """Get all trades from shared database"""
        try:
            if not self.db:
                return {}

            return dict(self.db.get("trades", {}))
            
        except Exception as e:
            self.logger.error(f"❌ Error getting all trades from shared database: {e}")
            return {}

    def delete_trade(self, trade_id: str) -> bool:
        """Delete trade from shared database"""
        try:
            if not self.db:
                return False

            trades = dict(self.db.get("trades", {}))
            
            if trade_id in trades:
                del trades[trade_id]
                self.db["trades"] = trades
                self.logger.info(f"✅ Trade deleted from shared database: {trade_id}")
                return True
            else:
                self.logger.warning(f"⚠️ Trade {trade_id} not found for deletion")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error deleting trade from shared database: {e}")
            return False

    def sync_from_local(self, local_trades: Dict[str, Dict[str, Any]]) -> int:
        """Sync local trades to shared database"""
        try:
            if not self.db:
                return 0

            synced_count = 0
            shared_trades = dict(self.db.get("trades", {}))

            for trade_id, trade_data in local_trades.items():
                # Check if trade needs syncing
                local_updated = trade_data.get('last_updated', '')
                shared_updated = shared_trades.get(trade_id, {}).get('shared_db_updated', '')

                if trade_id not in shared_trades or local_updated > shared_updated:
                    trade_data['shared_db_updated'] = datetime.now().isoformat()
                    shared_trades[trade_id] = trade_data
                    synced_count += 1

            if synced_count > 0:
                self.db["trades"] = shared_trades
                self.logger.info(f"✅ Synced {synced_count} trades to shared database")

            return synced_count
            
        except Exception as e:
            self.logger.error(f"❌ Error syncing to shared database: {e}")
            return 0

    def sync_to_local(self) -> Dict[str, Dict[str, Any]]:
        """Get latest trades from shared database for local sync"""
        try:
            if not self.db:
                return {}

            shared_trades = dict(self.db.get("trades", {}))
            self.logger.info(f"📊 Retrieved {len(shared_trades)} trades from shared database")
            return shared_trades
            
        except Exception as e:
            self.logger.error(f"❌ Error syncing from shared database: {e}")
            return {}

    def get_sync_status(self) -> Dict[str, Any]:
        """Get synchronization status"""
        try:
            if not self.db:
                return {"status": "unavailable", "message": "Shared database not connected"}

            trades = dict(self.db.get("trades", {}))
            open_trades = sum(1 for t in trades.values() if t.get('trade_status') == 'OPEN')
            closed_trades = sum(1 for t in trades.values() if t.get('trade_status') == 'CLOSED')

            return {
                "status": "connected",
                "total_trades": len(trades),
                "open_trades": open_trades,
                "closed_trades": closed_trades,
                "last_check": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def clear_all_trades(self) -> bool:
        """Clear all trades from shared database (use with caution)"""
        try:
            if not self.db:
                return False

            self.db["trades"] = {}
            self.logger.info("🧹 Cleared all trades from shared database")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error clearing shared database: {e}")
            return False

# Global shared database instance
shared_db = SharedTradeDatabase()
