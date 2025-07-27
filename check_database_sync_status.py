
#!/usr/bin/env python3
"""
Database Synchronization Status Checker
Monitor the sync status between local and cloud databases
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.execution_engine.cloud_database_sync import get_cloud_sync
from datetime import datetime
import json

def check_sync_status():
    """Check current database synchronization status"""
    print("🔍 DATABASE SYNCHRONIZATION STATUS")
    print("=" * 40)
    
    try:
        # Initialize database
        trade_db = TradeDatabase()
        cloud_sync = get_cloud_sync()
        
        # Environment info
        is_deployment = os.environ.get('RENDER') == 'true'
        environment = "RENDER_DEPLOYMENT" if is_deployment else "REPLIT_DEVELOPMENT"
        
        print(f"\n🌐 Environment: {environment}")
        print(f"📊 Local database: {len(trade_db.trades)} trades")
        
        if cloud_sync:
            print(f"✅ Cloud sync: ENABLED")
            
            # Get sync status
            sync_status = cloud_sync.get_sync_status()
            print(f"\n📋 Sync Status:")
            print(f"   Last sync: {sync_status.get('last_sync_time', 'Never')}")
            print(f"   Should sync: {sync_status.get('should_sync', False)}")
            print(f"   Local hash: {sync_status.get('local_hash', 'Unknown')[:8]}...")
            print(f"   Remote hash: {sync_status.get('remote_hash', 'Unknown')[:8]}...")
            
            # Test cloud connectivity
            print(f"\n🔄 Testing cloud connectivity...")
            cloud_trades = cloud_sync.download_database_from_cloud()
            
            if cloud_trades is not None:
                print(f"✅ Cloud database accessible: {len(cloud_trades)} trades")
                
                # Compare counts
                local_count = len(trade_db.trades)
                cloud_count = len(cloud_trades)
                
                if local_count == cloud_count:
                    print(f"✅ Trade counts match: {local_count}")
                else:
                    print(f"⚠️ Trade count mismatch:")
                    print(f"   Local: {local_count}")
                    print(f"   Cloud: {cloud_count}")
                    print(f"   Difference: {abs(local_count - cloud_count)}")
                
                # Check for sync conflicts
                conflicts = []
                for trade_id in trade_db.trades:
                    if trade_id in cloud_trades:
                        local_updated = trade_db.trades[trade_id].get('last_updated', '')
                        cloud_updated = cloud_trades[trade_id].get('last_updated', '')
                        if local_updated != cloud_updated:
                            conflicts.append(trade_id)
                
                if conflicts:
                    print(f"⚠️ {len(conflicts)} trades have timestamp conflicts")
                    print(f"   These will be resolved on next sync")
                else:
                    print(f"✅ No timestamp conflicts detected")
                    
            else:
                print(f"❌ Could not access cloud database")
                
        else:
            print(f"❌ Cloud sync: DISABLED")
            print(f"   Reason: REPLIT_DB_URL not configured")
        
        # Recent trades analysis
        print(f"\n📊 Recent Trades Analysis:")
        recent_trades = []
        for trade_id, trade_data in trade_db.trades.items():
            created_at = trade_data.get('created_at', trade_data.get('timestamp', ''))
            if created_at:
                try:
                    trade_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    age_hours = (datetime.now() - trade_time).total_seconds() / 3600
                    if age_hours < 24:  # Last 24 hours
                        recent_trades.append({
                            'trade_id': trade_id,
                            'symbol': trade_data.get('symbol'),
                            'status': trade_data.get('trade_status'),
                            'age_hours': age_hours
                        })
                except:
                    pass
        
        if recent_trades:
            print(f"   📈 {len(recent_trades)} trades in last 24 hours")
            for trade in recent_trades[:5]:  # Show first 5
                print(f"      • {trade['trade_id']}: {trade['symbol']} ({trade['status']}) - {trade['age_hours']:.1f}h ago")
        else:
            print(f"   📊 No trades in last 24 hours")
        
        print(f"\n🎯 Recommendations:")
        if not cloud_sync:
            print(f"   1. Configure REPLIT_DB_URL environment variable")
            print(f"   2. Run setup_cloud_database.py for instructions")
        elif cloud_trades is None:
            print(f"   1. Check internet connectivity")
            print(f"   2. Verify REPLIT_DB_URL is correct")
        elif local_count != len(cloud_trades):
            print(f"   1. Sync will resolve differences automatically")
            print(f"   2. Monitor next few syncs for consistency")
        else:
            print(f"   ✅ Database sync is working perfectly!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking sync status: {e}")
        import traceback
        print(f"🔍 Error traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    check_sync_status()
