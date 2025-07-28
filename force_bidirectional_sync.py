
#!/usr/bin/env python3
"""
Force Bidirectional Database Sync
Ensure both development and deployment show the same database content
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.execution_engine.cloud_database_sync import get_cloud_sync
from datetime import datetime
import json

def force_bidirectional_sync():
    """Force complete sync between local and cloud databases"""
    print("🔄 FORCING BIDIRECTIONAL DATABASE SYNC")
    print("=" * 50)
    
    # Initialize database
    trade_db = TradeDatabase()
    cloud_sync = trade_db.cloud_sync
    
    if not cloud_sync or not cloud_sync.enabled:
        print("❌ Cloud sync not available - cannot perform sync")
        return False
    
    print(f"🌐 Environment: {cloud_sync.environment}")
    print(f"📊 Local database: {len(trade_db.trades)} trades")
    
    # Step 1: Download current cloud state
    print(f"\n📥 STEP 1: Downloading cloud database...")
    cloud_trades = cloud_sync.download_database_from_cloud()
    
    if cloud_trades is None:
        print("❌ Cannot access cloud database")
        return False
    
    print(f"📊 Cloud database: {len(cloud_trades)} trades")
    
    # Step 2: Merge databases intelligently
    print(f"\n🔄 STEP 2: Merging databases...")
    
    merged_trades = {}
    
    # Start with local trades (development is source of truth)
    merged_trades.update(trade_db.trades)
    print(f"   📤 Added {len(trade_db.trades)} local trades")
    
    # Add any cloud trades that don't exist locally
    added_from_cloud = 0
    updated_from_cloud = 0
    
    for trade_id, cloud_trade in cloud_trades.items():
        if trade_id not in merged_trades:
            merged_trades[trade_id] = cloud_trade
            added_from_cloud += 1
        else:
            # Compare timestamps to keep most recent
            local_updated = merged_trades[trade_id].get('last_updated', '')
            cloud_updated = cloud_trade.get('last_updated', '')
            
            try:
                if cloud_updated and (not local_updated or cloud_updated > local_updated):
                    merged_trades[trade_id] = cloud_trade
                    updated_from_cloud += 1
            except:
                pass  # Keep local version if comparison fails
    
    print(f"   📥 Added {added_from_cloud} trades from cloud")
    print(f"   🔄 Updated {updated_from_cloud} trades from cloud")
    print(f"   📊 Final merged database: {len(merged_trades)} trades")
    
    # Step 3: Upload merged database to cloud
    print(f"\n📤 STEP 3: Uploading merged database to cloud...")
    upload_success = cloud_sync.upload_database_to_cloud(merged_trades)
    
    if not upload_success:
        print("❌ Failed to upload merged database to cloud")
        return False
    
    print("✅ Successfully uploaded merged database to cloud")
    
    # Step 4: Update local database
    print(f"\n💾 STEP 4: Updating local database...")
    
    if len(merged_trades) != len(trade_db.trades):
        trade_db.trades = merged_trades
        save_success = trade_db._save_database()
        
        if save_success:
            print(f"✅ Local database updated with {len(merged_trades)} trades")
        else:
            print("❌ Failed to save updated local database")
            return False
    else:
        print("✅ Local database already up to date")
    
    # Step 5: Verification
    print(f"\n🔍 STEP 5: Verification...")
    
    # Download again to verify
    verification_trades = cloud_sync.download_database_from_cloud()
    
    if verification_trades and len(verification_trades) == len(merged_trades):
        print(f"✅ SYNC VERIFICATION SUCCESSFUL")
        print(f"   📊 Both databases now have {len(merged_trades)} trades")
        
        # Show open trades summary
        open_trades = [t for t in merged_trades.values() if t.get('trade_status') == 'OPEN']
        print(f"   🔓 Open trades: {len(open_trades)}")
        
        for trade in open_trades[:3]:  # Show first 3
            symbol = trade.get('symbol', 'Unknown')
            side = trade.get('side', 'Unknown')
            print(f"      • {symbol} {side}")
        
        return True
    else:
        print(f"❌ SYNC VERIFICATION FAILED")
        return False

if __name__ == "__main__":
    success = force_bidirectional_sync()
    if success:
        print(f"\n🎯 SYNC COMPLETE - Both environments should now show identical data")
    else:
        print(f"\n❌ SYNC FAILED - Manual intervention required")
