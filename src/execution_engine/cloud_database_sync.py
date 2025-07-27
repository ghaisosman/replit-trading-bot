
import json
import os
import requests
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import hashlib
import time

class CloudDatabaseSync:
    """Synchronize database between Replit development and Render deployment"""
    
    def __init__(self, replit_db_url: str = None):
        self.logger = logging.getLogger(__name__)
        
        # Replit Database URL (get from environment or parameter)
        self.replit_db_url = replit_db_url or os.getenv('REPLIT_DB_URL')
        
        if not self.replit_db_url:
            raise ValueError("REPLIT_DB_URL environment variable is required")
        
        # Environment detection
        self.is_deployment = os.environ.get('RENDER') == 'true'
        self.environment = "RENDER_DEPLOYMENT" if self.is_deployment else "REPLIT_DEVELOPMENT"
        
        # Sync configuration
        self.sync_interval = 30  # seconds
        self.last_sync_time = None
        self.local_hash = None
        self.remote_hash = None
        
        self.logger.info(f"🌐 Cloud Database Sync initialized for {self.environment}")
    
    def _calculate_data_hash(self, data: Dict) -> str:
        """Calculate hash of data for change detection"""
        try:
            data_str = json.dumps(data, sort_keys=True, default=str)
            return hashlib.md5(data_str.encode()).hexdigest()
        except Exception as e:
            self.logger.error(f"Error calculating hash: {e}")
            return "unknown"
    
    def _make_db_request(self, method: str, key: str = "", data: Any = None) -> Optional[Any]:
        """Make request to Replit Database"""
        try:
            url = f"{self.replit_db_url}/{key}" if key else self.replit_db_url
            
            headers = {'Content-Type': 'application/json'} if data else {}
            
            if method == 'GET':
                response = requests.get(url, timeout=10)
            elif method == 'POST':
                response = requests.post(url, data=json.dumps(data) if data else None, headers=headers, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, timeout=10)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            if response.status_code == 200:
                return response.json() if response.content else None
            elif response.status_code == 404:
                return None
            else:
                self.logger.warning(f"Database request failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"Database request error: {e}")
            return None
    
    def upload_database_to_cloud(self, local_trades: Dict[str, Any]) -> bool:
        """Upload local database to Replit cloud database"""
        try:
            self.logger.info(f"📤 Uploading {len(local_trades)} trades to cloud database")
            
            # Prepare data with metadata
            cloud_data = {
                'trades': local_trades,
                'last_updated': datetime.now().isoformat(),
                'updated_by': self.environment,
                'trade_count': len(local_trades),
                'data_hash': self._calculate_data_hash(local_trades)
            }
            
            # Upload to cloud
            result = self._make_db_request('POST', 'trading_database', cloud_data)
            
            if result is not None:
                self.remote_hash = cloud_data['data_hash']
                self.last_sync_time = datetime.now()
                self.logger.info(f"✅ Successfully uploaded database to cloud")
                return True
            else:
                self.logger.error(f"❌ Failed to upload database to cloud")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error uploading to cloud: {e}")
            return False
    
    def download_database_from_cloud(self) -> Optional[Dict[str, Any]]:
        """Download database from Replit cloud database"""
        try:
            self.logger.info("📥 Downloading database from cloud")
            
            # Get data from cloud
            cloud_data = self._make_db_request('GET', 'trading_database')
            
            if cloud_data is None:
                self.logger.info("📊 No cloud database found - will create new one")
                return {}
            
            if 'trades' not in cloud_data:
                self.logger.warning("⚠️ Invalid cloud data format")
                return {}
            
            trades = cloud_data['trades']
            self.remote_hash = cloud_data.get('data_hash', 'unknown')
            self.last_sync_time = datetime.now()
            
            self.logger.info(f"✅ Downloaded {len(trades)} trades from cloud database")
            self.logger.info(f"📊 Last updated by: {cloud_data.get('updated_by', 'unknown')}")
            self.logger.info(f"⏰ Last updated: {cloud_data.get('last_updated', 'unknown')}")
            
            return trades
            
        except Exception as e:
            self.logger.error(f"❌ Error downloading from cloud: {e}")
            return None
    
    def sync_database(self, local_trades: Dict[str, Any]) -> Dict[str, Any]:
        """Intelligent bidirectional sync between local and cloud database"""
        try:
            self.logger.info(f"🔄 Starting database sync from {self.environment}")
            
            # Calculate local hash
            local_hash = self._calculate_data_hash(local_trades)
            
            # Download cloud data
            cloud_trades = self.download_database_from_cloud()
            
            if cloud_trades is None:
                self.logger.error("❌ Could not access cloud database")
                return local_trades
            
            # If cloud is empty, upload local data
            if not cloud_trades:
                self.logger.info("📤 Cloud database empty - uploading local data")
                if self.upload_database_to_cloud(local_trades):
                    return local_trades
                else:
                    self.logger.error("❌ Failed to initialize cloud database")
                    return local_trades
            
            # Compare hashes to detect changes
            cloud_hash = self._calculate_data_hash(cloud_trades)
            
            if local_hash == cloud_hash:
                self.logger.info("✅ Local and cloud databases are in sync")
                return local_trades
            
            # Determine which is more recent based on trade count and timestamps
            local_count = len(local_trades)
            cloud_count = len(cloud_trades)
            
            self.logger.info(f"📊 Sync comparison:")
            self.logger.info(f"   Local: {local_count} trades")
            self.logger.info(f"   Cloud: {cloud_count} trades")
            
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
            self.logger.info(f"🔄 Merged database: {final_count} trades")
            
            if self.upload_database_to_cloud(merged_trades):
                self.logger.info(f"✅ Database sync completed successfully")
                return merged_trades
            else:
                self.logger.error("❌ Failed to upload merged database")
                return local_trades
                
        except Exception as e:
            self.logger.error(f"❌ Error during database sync: {e}")
            import traceback
            self.logger.error(f"🔍 Sync error traceback: {traceback.format_exc()}")
            return local_trades
    
    def should_sync(self) -> bool:
        """Check if it's time to sync"""
        if self.last_sync_time is None:
            return True
        
        time_since_sync = (datetime.now() - self.last_sync_time).total_seconds()
        return time_since_sync >= self.sync_interval
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get current sync status"""
        return {
            'environment': self.environment,
            'last_sync_time': self.last_sync_time.isoformat() if self.last_sync_time else None,
            'local_hash': self.local_hash,
            'remote_hash': self.remote_hash,
            'sync_interval': self.sync_interval,
            'should_sync': self.should_sync()
        }

# Global cloud sync instance
cloud_sync = None

def initialize_cloud_sync(replit_db_url: str = None) -> CloudDatabaseSync:
    """Initialize global cloud sync instance"""
    global cloud_sync
    if cloud_sync is None:
        cloud_sync = CloudDatabaseSync(replit_db_url)
    return cloud_sync

def get_cloud_sync() -> Optional[CloudDatabaseSync]:
    """Get global cloud sync instance"""
    return cloud_sync
