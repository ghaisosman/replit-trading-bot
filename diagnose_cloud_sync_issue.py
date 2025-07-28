
#!/usr/bin/env python3
"""
Diagnose Cloud Database Sync Issues
Check why development and deployment databases are not syncing properly
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.execution_engine.cloud_database_sync import get_cloud_sync
from datetime import datetime
import json

def diagnose_cloud_sync():
    """Comprehensive cloud sync diagnosis"""
    print("🔍 CLOUD DATABASE SYNC DIAGNOSIS")
    print("=" * 50)
    
    # Initialize trade database
    trade_db = TradeDatabase()
    cloud_sync = trade_db.cloud_sync
    
    print(f"\n📊 CURRENT ENVIRONMENT STATUS:")
    print(f"   Environment: {os.environ.get('RENDER', 'false')} (Render) | {os.environ.get('REPLIT_DEPLOYMENT', '0')} (Replit Deploy)")
    print(f"   Local trades: {len(trade_db.trades)}")
    
    if cloud_sync:
        print(f"   Cloud sync enabled: {cloud_sync.enabled}")
        print(f"   Environment: {cloud_sync.environment}")
        print(f"   Database URL configured: {'Yes' if cloud_sync.database_url else 'No'}")
        
        # Test cloud connectivity
        print(f"\n🔄 TESTING CLOUD CONNECTIVITY:")
        try:
            cloud_trades = cloud_sync.download_database_from_cloud()
            if cloud_trades is not None:
                print(f"   ✅ Cloud accessible: {len(cloud_trades)} trades found")
                
                # Compare local vs cloud
                print(f"\n📊 COMPARISON:")
                print(f"   Local database: {len(trade_db.trades)} trades")
                print(f"   Cloud database: {len(cloud_trades)} trades")
                
                if len(trade_db.trades) != len(cloud_trades):
                    print(f"   🚨 SYNC MISMATCH DETECTED!")
                    
                    # Show differences
                    local_ids = set(trade_db.trades.keys())
                    cloud_ids = set(cloud_trades.keys())
                    
                    only_local = local_ids - cloud_ids
                    only_cloud = cloud_ids - local_ids
                    
                    if only_local:
                        print(f"   📤 Only in local ({len(only_local)}): {list(only_local)[:3]}...")
                    if only_cloud:
                        print(f"   📥 Only in cloud ({len(only_cloud)}): {list(only_cloud)[:3]}...")
                        
                else:
                    print(f"   ✅ Trade counts match")
                    
            else:
                print(f"   ❌ Cloud not accessible")
                
        except Exception as e:
            print(f"   ❌ Cloud connectivity error: {e}")
    else:
        print(f"   ❌ Cloud sync not initialized")
        
    # Check environment variables
    print(f"\n🔧 ENVIRONMENT VARIABLES:")
    database_url = os.getenv('DATABASE_URL')
    replit_db_url = os.getenv('REPLIT_DB_URL')
    
    print(f"   DATABASE_URL: {'✅ Set' if database_url else '❌ Missing'}")
    print(f"   REPLIT_DB_URL: {'✅ Set' if replit_db_url else '❌ Missing'}")
    
    if database_url:
        print(f"   DATABASE_URL prefix: {database_url[:30]}...")
    
    # Test manual sync
    print(f"\n🔄 TESTING MANUAL SYNC:")
    if cloud_sync and cloud_sync.enabled:
        try:
            print(f"   📤 Forcing upload to cloud...")
            upload_success = cloud_sync.upload_database_to_cloud(trade_db.trades)
            print(f"   Upload result: {'✅ Success' if upload_success else '❌ Failed'}")
            
            if upload_success:
                print(f"   📥 Testing download after upload...")
                download_trades = cloud_sync.download_database_from_cloud()
                if download_trades and len(download_trades) == len(trade_db.trades):
                    print(f"   ✅ Round-trip sync successful")
                else:
                    print(f"   ❌ Round-trip sync failed")
            
        except Exception as e:
            print(f"   ❌ Manual sync error: {e}")
    
    print(f"\n💡 DIAGNOSIS RECOMMENDATIONS:")
    
    if not cloud_sync or not cloud_sync.enabled:
        print(f"   1. 🔧 Cloud sync not properly initialized")
        print(f"   2. ⚙️ Check DATABASE_URL environment variable")
        print(f"   3. 🔄 Restart the application after fixing env vars")
    elif len(trade_db.trades) != len(cloud_trades if 'cloud_trades' in locals() else []):
        print(f"   1. 🔄 Run force sync script to align databases")
        print(f"   2. 📊 Monitor sync status in both environments")
        print(f"   3. 🔧 Check if auto-sync is working during normal operations")
    else:
        print(f"   ✅ Sync appears to be working correctly")

if __name__ == "__main__":
    diagnose_cloud_sync()
