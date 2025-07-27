import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import hashlib
import time

class CloudDatabaseSync:
    """Synchronize database between Replit development and Render deployment using PostgreSQL"""

    def __init__(self, database_url: str = None):
        self.logger = logging.getLogger(__name__)

        # PostgreSQL Database URL - only use actual PostgreSQL URLs
        self.database_url = database_url or os.getenv('DATABASE_URL')

        # Check if REPLIT_DB_URL exists but is not PostgreSQL format 
        replit_db_url = os.getenv('REPLIT_DB_URL')
        if replit_db_url and replit_db_url.startswith('https://kv.replit.com'):
            self.logger.warning("REPLIT_DB_URL detected but it's a KV store, not PostgreSQL - cloud sync disabled")
            self.enabled = False
            return

        if not self.database_url:
            self.logger.warning("No PostgreSQL DATABASE_URL found - cloud sync disabled")
            self.enabled = False
            return

        self.enabled = True

        # Environment detection
        self.is_deployment = os.environ.get('RENDER') == 'true' or os.environ.get('REPLIT_DEPLOYMENT') == '1'
        self.environment = "RENDER_DEPLOYMENT" if self.is_deployment else "REPLIT_DEVELOPMENT"

        # Sync configuration
        self.sync_interval = 30  # seconds
        self.last_sync_time = None
        self.local_hash = None
        self.remote_hash = None

        # Initialize database connection
        self._init_database()

        self.logger.info(f"🌐 PostgreSQL Cloud Database Sync initialized for {self.environment}")

    def _init_database(self):
        """Initialize PostgreSQL database connection and create tables if needed"""
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor

            # Clean the database URL - remove any trailing path components
            clean_url = self.database_url
            if clean_url.endswith('/trading_database'):
                clean_url = clean_url.replace('/trading_database', '')

            # Create connection
            self.conn = psycopg2.connect(clean_url)
            self.conn.autocommit = True

            # Create trading_database table if it doesn't exist
            with self.conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS trading_database (
                        id SERIAL PRIMARY KEY,
                        data JSONB NOT NULL,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_by VARCHAR(50),
                        trade_count INTEGER,
                        data_hash VARCHAR(32)
                    )
                """)

            self.logger.info("✅ PostgreSQL database initialized")

        except ImportError:
            self.logger.error("❌ psycopg2 not installed - install with: pip install psycopg2-binary")
            self.enabled = False
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize PostgreSQL: {e}")
            self.enabled = False

    def _calculate_data_hash(self, data: Dict) -> str:
        """Calculate hash of data for change detection"""
        try:
            data_str = json.dumps(data, sort_keys=True, default=str)
            return hashlib.md5(data_str.encode()).hexdigest()
        except Exception as e:
            self.logger.error(f"Error calculating hash: {e}")
            return "unknown"

    def upload_database_to_cloud(self, local_trades: Dict[str, Any]) -> bool:
        """Upload local database to PostgreSQL cloud database"""
        if not self.enabled:
            return False

        try:
            self.logger.info(f"📤 Uploading {len(local_trades)} trades to PostgreSQL cloud database")

            # Prepare data with metadata
            cloud_data = {
                'trades': local_trades,
                'last_updated': datetime.now().isoformat(),
                'updated_by': self.environment,
                'trade_count': len(local_trades),
                'data_hash': self._calculate_data_hash(local_trades)
            }

            # Clear existing data and insert new
            with self.conn.cursor() as cur:
                cur.execute("DELETE FROM trading_database")
                cur.execute("""
                    INSERT INTO trading_database (data, updated_by, trade_count, data_hash)
                    VALUES (%s, %s, %s, %s)
                """, (
                    json.dumps(cloud_data),
                    self.environment,
                    len(local_trades),
                    cloud_data['data_hash']
                ))

            self.remote_hash = cloud_data['data_hash']
            self.last_sync_time = datetime.now()
            self.logger.info(f"✅ Successfully uploaded database to PostgreSQL cloud")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error uploading to PostgreSQL cloud: {e}")
            return False

    def download_database_from_cloud(self) -> Optional[Dict[str, Any]]:
        """Download database from PostgreSQL cloud database"""
        if not self.enabled:
            return {}

        try:
            self.logger.debug("📥 Downloading database from PostgreSQL cloud")

            # Get data from cloud
            with self.conn.cursor() as cur:
                cur.execute("SELECT data FROM trading_database ORDER BY last_updated DESC LIMIT 1")
                result = cur.fetchone()

            if not result:
                self.logger.debug("📊 No cloud database found - will create new one")
                return {}

            cloud_data = result[0]

            if 'trades' not in cloud_data:
                self.logger.warning("⚠️ Invalid cloud data format")
                return {}

            trades = cloud_data['trades']
            self.remote_hash = cloud_data.get('data_hash', 'unknown')
            self.last_sync_time = datetime.now()

            self.logger.debug(f"✅ Downloaded {len(trades)} trades from PostgreSQL cloud database")
            self.logger.debug(f"📊 Last updated by: {cloud_data.get('updated_by', 'unknown')}")

            return trades

        except Exception as e:
            self.logger.error(f"❌ Error downloading from PostgreSQL cloud: {e}")
            return None

    def sync_database(self, local_trades: Dict[str, Any]) -> Dict[str, Any]:
        """Intelligent bidirectional sync between local and PostgreSQL cloud database"""
        if not self.enabled:
            return local_trades

        try:
            self.logger.debug(f"🔄 Starting PostgreSQL database sync from {self.environment}")

            # Calculate local hash
            local_hash = self._calculate_data_hash(local_trades)

            # Download cloud data
            cloud_trades = self.download_database_from_cloud()

            if cloud_trades is None:
                self.logger.error("❌ Could not access PostgreSQL cloud database")
                return local_trades

            # If cloud is empty, upload local data
            if not cloud_trades:
                self.logger.debug("📤 PostgreSQL cloud database empty - uploading local data")
                if self.upload_database_to_cloud(local_trades):
                    return local_trades
                else:
                    self.logger.error("❌ Failed to initialize PostgreSQL cloud database")
                    return local_trades

            # Compare hashes to detect changes
            cloud_hash = self._calculate_data_hash(cloud_trades)

            if local_hash == cloud_hash:
                self.logger.debug("✅ Local and PostgreSQL cloud databases are in sync")
                return local_trades

            # Determine which is more recent based on trade count and timestamps
            local_count = len(local_trades)
            cloud_count = len(cloud_trades)

            self.logger.debug(f"📊 PostgreSQL sync comparison:")
            self.logger.debug(f"   Local: {local_count} trades")
            self.logger.debug(f"   Cloud: {cloud_count} trades")

            # Merge strategy: combine both and deduplicate
            merged_trades = {}

            # Start with cloud data as base
            merged_trades.update(cloud_trades)

            # Add/update with local data (local takes precedence for conflicts)
            for trade_id, trade_data in local_trades.items():
                if trade_id in merged_trades:
                    # Compare timestamps to determine which is more recent
                    local_updated = trade_data.get('last_updated', trade_data.get('created_at', ''))
                    cloud_updated = merged_trades[trade_id].get('last_updated', merged_trades[trade_id].get('created_at', ''))

                    try:
                        local_time = datetime.fromisoformat(local_updated.replace('Z', '+00:00'))
                        cloud_time = datetime.fromisoformat(cloud_updated.replace('Z', '+00:00'))

                        if local_time >= cloud_time:
                            merged_trades[trade_id] = trade_data
                            self.logger.debug(f"🔄 Updated {trade_id} with local version (newer)")
                        else:
                            self.logger.debug(f"🔄 Kept {trade_id} with cloud version (newer)")
                    except:
                        # If timestamp comparison fails, prefer local
                        merged_trades[trade_id] = trade_data
                        self.logger.debug(f"🔄 Updated {trade_id} with local version (timestamp parse failed)")
                else:
                    merged_trades[trade_id] = trade_data
                    self.logger.debug(f"➕ Added new trade {trade_id} from local")

            # Upload merged result to cloud
            final_count = len(merged_trades)
            self.logger.debug(f"🔄 Merged PostgreSQL database: {final_count} trades")

            if self.upload_database_to_cloud(merged_trades):
                self.logger.debug(f"✅ PostgreSQL database sync completed successfully")
                return merged_trades
            else:
                self.logger.error("❌ Failed to upload merged database to PostgreSQL")
                return local_trades

        except Exception as e:
            self.logger.error(f"❌ Error during PostgreSQL database sync: {e}")
            import traceback
            self.logger.error(f"🔍 PostgreSQL sync error traceback: {traceback.format_exc()}")
            return local_trades

    def should_sync(self) -> bool:
        """Check if it's time to sync"""
        if not self.enabled:
            return False

        if self.last_sync_time is None:
            return True

        time_since_sync = (datetime.now() - self.last_sync_time).total_seconds()
        return time_since_sync >= self.sync_interval

    def get_sync_status(self) -> Dict[str, Any]:
        """Get current sync status"""
        return {
            'enabled': self.enabled,
            'environment': self.environment,
            'database_type': 'PostgreSQL',
            'last_sync_time': self.last_sync_time.isoformat() if self.last_sync_time else None,
            'local_hash': self.local_hash,
            'remote_hash': self.remote_hash,
            'sync_interval': self.sync_interval,
            'should_sync': self.should_sync()
        }

# Global cloud sync instance
cloud_sync = None

def initialize_cloud_sync(database_url: str = None) -> CloudDatabaseSync:
    """Initialize global cloud sync instance"""
    global cloud_sync
    if cloud_sync is None:
        cloud_sync = CloudDatabaseSync(database_url)
    return cloud_sync

def get_cloud_sync() -> Optional[CloudDatabaseSync]:
    """Get global cloud sync instance"""
    return cloud_sync