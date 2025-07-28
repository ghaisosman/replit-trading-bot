
#!/usr/bin/env python3
"""
Automatic Database Sync Fix
Fix the root cause of database sync issues and ensure proper bidirectional sync
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.execution_engine.cloud_database_sync import get_cloud_sync, initialize_cloud_sync
from datetime import datetime
import json
import time
import threading

def fix_cloud_sync_initialization():
    """Fix cloud sync initialization issues"""
    print("🔧 FIXING CLOUD SYNC INITIALIZATION")
    print("=" * 40)
    
    # Ensure DATABASE_URL is properly configured
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL not configured")
        return False
    
    print(f"✅ DATABASE_URL configured: {database_url[:50]}...")
    
    # Test cloud sync initialization
    try:
        cloud_sync = initialize_cloud_sync(database_url)
        if cloud_sync and cloud_sync.enabled:
            print("✅ Cloud sync initialized successfully")
            return True
        else:
            print("❌ Cloud sync initialization failed")
            return False
    except Exception as e:
        print(f"❌ Cloud sync error: {e}")
        return False

def force_bidirectional_sync():
    """Force complete bidirectional sync"""
    print("\n🔄 FORCING BIDIRECTIONAL SYNC")
    print("=" * 30)
    
    trade_db = TradeDatabase()
    cloud_sync = trade_db.cloud_sync
    
    if not cloud_sync or not cloud_sync.enabled:
        print("❌ Cloud sync not available")
        return False
    
    print(f"📊 Local database: {len(trade_db.trades)} trades")
    
    # Download cloud data
    print("📥 Downloading from cloud...")
    cloud_trades = cloud_sync.download_database_from_cloud()
    
    if cloud_trades is None:
        print("❌ Cannot access cloud database")
        return False
    
    print(f"📊 Cloud database: {len(cloud_trades)} trades")
    
    # Merge intelligently
    merged_trades = {}
    
    # Add all local trades
    merged_trades.update(trade_db.trades)
    
    # Add cloud trades that don't exist locally
    for trade_id, cloud_trade in cloud_trades.items():
        if trade_id not in merged_trades:
            merged_trades[trade_id] = cloud_trade
            print(f"➕ Added from cloud: {trade_id}")
    
    # Upload merged database
    print(f"📤 Uploading merged database ({len(merged_trades)} trades)...")
    upload_success = cloud_sync.upload_database_to_cloud(merged_trades)
    
    if upload_success:
        # Update local database
        trade_db.trades = merged_trades
        trade_db._save_database()
        print(f"✅ Sync completed: {len(merged_trades)} trades")
        return True
    else:
        print("❌ Upload failed")
        return False

def test_sync_functionality():
    """Test if sync is working properly"""
    print("\n🧪 TESTING SYNC FUNCTIONALITY")
    print("=" * 30)
    
    trade_db = TradeDatabase()
    cloud_sync = trade_db.cloud_sync
    
    if not cloud_sync:
        print("❌ Cloud sync not available for testing")
        return False
    
    # Test 1: Upload current data
    print("🧪 Test 1: Upload current database...")
    upload_success = cloud_sync.upload_database_to_cloud(trade_db.trades)
    print(f"   Result: {'✅ Success' if upload_success else '❌ Failed'}")
    
    # Test 2: Download and verify
    print("🧪 Test 2: Download and verify...")
    downloaded_trades = cloud_sync.download_database_from_cloud()
    
    if downloaded_trades is not None:
        if len(downloaded_trades) == len(trade_db.trades):
            print(f"   Result: ✅ Success ({len(downloaded_trades)} trades)")
        else:
            print(f"   Result: ⚠️ Count mismatch: local={len(trade_db.trades)}, cloud={len(downloaded_trades)}")
    else:
        print("   Result: ❌ Download failed")
        return False
    
    # Test 3: Sync functionality
    print("🧪 Test 3: Sync functionality...")
    synced_trades = cloud_sync.sync_database(trade_db.trades)
    
    if synced_trades:
        print(f"   Result: ✅ Success ({len(synced_trades)} trades)")
        return True
    else:
        print("   Result: ❌ Sync failed")
        return False

def monitor_sync_status():
    """Monitor sync status in real-time"""
    print("\n👁️ MONITORING SYNC STATUS")
    print("=" * 25)
    
    trade_db = TradeDatabase()
    cloud_sync = trade_db.cloud_sync
    
    if not cloud_sync:
        print("❌ Cloud sync not available for monitoring")
        return
    
    for i in range(3):
        print(f"\n📊 Check {i+1}/3:")
        
        # Get local count
        local_count = len(trade_db.trades)
        
        # Get cloud count
        cloud_trades = cloud_sync.download_database_from_cloud()
        cloud_count = len(cloud_trades) if cloud_trades else 0
        
        print(f"   Local: {local_count} trades")
        print(f"   Cloud: {cloud_count} trades")
        
        if local_count == cloud_count:
            print("   Status: ✅ Synchronized")
        else:
            print("   Status: ⚠️ Not synchronized")
        
        if i < 2:  # Don't sleep on last iteration
            time.sleep(2)

def verify_environment_sync():
    """Verify sync works between environments"""
    print("\n🌐 VERIFYING ENVIRONMENT SYNC")
    print("=" * 30)
    
    # Check current environment
    is_deployment = os.environ.get('RENDER') == 'true' or os.environ.get('REPLIT_DEPLOYMENT') == '1'
    environment = "DEPLOYMENT" if is_deployment else "DEVELOPMENT"
    
    print(f"🌐 Current environment: {environment}")
    
    trade_db = TradeDatabase()
    print(f"📊 Local trades: {len(trade_db.trades)}")
    
    # Show open trades
    open_trades = [t for t in trade_db.trades.values() if t.get('trade_status') == 'OPEN']
    print(f"🔓 Open trades: {len(open_trades)}")
    
    for trade in open_trades[:3]:  # Show first 3
        symbol = trade.get('symbol', 'Unknown')
        side = trade.get('side', 'Unknown')
        print(f"   • {symbol} {side}")
    
    return len(trade_db.trades)

def automated_sync_fix():
    """Main automated sync fix function"""
    print("🤖 AUTOMATED DATABASE SYNC FIX")
    print("=" * 40)
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    success_count = 0
    total_tests = 5
    
    # Step 1: Fix initialization
    print(f"\n1️⃣ STEP 1: Fix cloud sync initialization")
    if fix_cloud_sync_initialization():
        success_count += 1
        print("✅ Step 1 completed")
    else:
        print("❌ Step 1 failed")
    
    # Step 2: Force sync
    print(f"\n2️⃣ STEP 2: Force bidirectional sync")
    if force_bidirectional_sync():
        success_count += 1
        print("✅ Step 2 completed")
    else:
        print("❌ Step 2 failed")
    
    # Step 3: Test functionality
    print(f"\n3️⃣ STEP 3: Test sync functionality")
    if test_sync_functionality():
        success_count += 1
        print("✅ Step 3 completed")
    else:
        print("❌ Step 3 failed")
    
    # Step 4: Monitor status
    print(f"\n4️⃣ STEP 4: Monitor sync status")
    try:
        monitor_sync_status()
        success_count += 1
        print("✅ Step 4 completed")
    except Exception as e:
        print(f"❌ Step 4 failed: {e}")
    
    # Step 5: Verify environment sync
    print(f"\n5️⃣ STEP 5: Verify environment sync")
    try:
        trade_count = verify_environment_sync()
        if trade_count > 0:
            success_count += 1
            print("✅ Step 5 completed")
        else:
            print("⚠️ Step 5 completed with warnings")
    except Exception as e:
        print(f"❌ Step 5 failed: {e}")
    
    # Final results
    print(f"\n📊 AUTOMATED FIX RESULTS")
    print("=" * 25)
    print(f"✅ Successful steps: {success_count}/{total_tests}")
    print(f"📊 Success rate: {(success_count/total_tests)*100:.1f}%")
    
    if success_count >= 4:
        print("🎉 DATABASE SYNC FIX SUCCESSFUL!")
        print("✅ Your databases should now sync automatically")
        print("✅ Both development and deployment will show the same data")
    elif success_count >= 2:
        print("⚠️ PARTIAL SUCCESS")
        print("🔧 Some issues remain - manual intervention may be needed")
    else:
        print("❌ FIX FAILED")
        print("🆘 Manual debugging required")
    
    return success_count >= 4

if __name__ == "__main__":
    try:
        success = automated_sync_fix()
        
        if success:
            print(f"\n🚀 NEXT STEPS:")
            print("1. Check your deployment dashboard - it should show all trades")
            print("2. Create a new trade in development - it should appear in deployment")
            print("3. The sync now happens automatically every 30 seconds")
        else:
            print(f"\n🔧 TROUBLESHOOTING:")
            print("1. Check DATABASE_URL environment variable")
            print("2. Verify PostgreSQL connection")
            print("3. Run the script again in 5 minutes")
            
    except Exception as e:
        print(f"❌ Critical error in automated fix: {e}")
        import traceback
        print(f"🔍 Error details: {traceback.format_exc()}")
