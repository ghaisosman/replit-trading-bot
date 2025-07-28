
#!/usr/bin/env python3
"""
Force sync development database to cloud PostgreSQL
This will upload all 14 development trades to the cloud database
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.execution_engine.cloud_database_sync import get_cloud_sync, initialize_cloud_sync
from datetime import datetime

def force_sync_to_cloud():
    """Force upload development database to cloud"""
    print("🔄 FORCING DEVELOPMENT DATABASE SYNC TO CLOUD")
    print("=" * 60)
    
    # Initialize trade database
    trade_db = TradeDatabase()
    
    print(f"📊 Development database: {len(trade_db.trades)} trades")
    
    if not trade_db.trades:
        print("❌ No trades in development database to sync")
        return False
    
    # Get cloud sync
    cloud_sync = trade_db.cloud_sync
    
    if not cloud_sync or not cloud_sync.enabled:
        print("❌ Cloud sync not available")
        return False
    
    print(f"🌐 Cloud sync enabled: {cloud_sync.environment}")
    
    # Force upload to cloud
    print("📤 Uploading development trades to cloud...")
    success = cloud_sync.upload_database_to_cloud(trade_db.trades)
    
    if success:
        print(f"✅ Successfully uploaded {len(trade_db.trades)} trades to cloud")
        print("🚀 Render deployment will now show all trades")
        return True
    else:
        print("❌ Failed to upload to cloud")
        return False

if __name__ == "__main__":
    force_sync_to_cloud()
