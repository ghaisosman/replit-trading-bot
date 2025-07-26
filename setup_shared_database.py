
#!/usr/bin/env python3
"""
Setup Shared Database
Initialize and test the shared database system
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.shared_database import shared_db
from src.execution_engine.trade_database import TradeDatabase
from datetime import datetime

def test_shared_database():
    """Test shared database functionality"""
    print("🧪 TESTING SHARED DATABASE")
    print("=" * 40)
    
    # Test connection
    status = shared_db.get_sync_status()
    print(f"📊 Connection status: {status['status']}")
    
    if status['status'] != 'connected':
        print(f"❌ Cannot proceed: {status.get('message', 'Connection failed')}")
        return False
    
    # Test adding a sample trade
    test_trade_id = f"TEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    test_trade_data = {
        'strategy_name': 'test_strategy',
        'symbol': 'BTCUSDT',
        'side': 'BUY',
        'quantity': 0.001,
        'entry_price': 50000.0,
        'trade_status': 'OPEN',
        'position_value_usdt': 50.0,
        'leverage': 1,
        'margin_used': 50.0,
        'timestamp': datetime.now().isoformat()
    }
    
    print(f"\n🧪 Testing trade addition: {test_trade_id}")
    success = shared_db.add_trade(test_trade_id, test_trade_data)
    
    if success:
        print("✅ Trade addition successful")
        
        # Test retrieval
        retrieved = shared_db.get_trade(test_trade_id)
        if retrieved:
            print("✅ Trade retrieval successful")
            
            # Test update
            updates = {'trade_status': 'CLOSED', 'exit_price': 51000.0}
            update_success = shared_db.update_trade(test_trade_id, updates)
            
            if update_success:
                print("✅ Trade update successful")
                
                # Clean up test trade
                shared_db.delete_trade(test_trade_id)
                print("✅ Test trade cleaned up")
                
                return True
            else:
                print("❌ Trade update failed")
        else:
            print("❌ Trade retrieval failed")
    else:
        print("❌ Trade addition failed")
    
    return False

def setup_initial_sync():
    """Setup initial sync from local database"""
    print("\n🔄 SETTING UP INITIAL SYNC")
    print("=" * 40)
    
    trade_db = TradeDatabase()
    local_count = len(trade_db.trades)
    print(f"📊 Local database has {local_count} trades")
    
    if local_count > 0:
        print("🔄 Syncing local trades to shared database...")
        synced_count = shared_db.sync_from_local(trade_db.trades)
        print(f"✅ Synced {synced_count} trades to shared database")
    else:
        print("📊 No local trades to sync")
    
    # Check final status
    status = shared_db.get_sync_status()
    print(f"📊 Shared database now has {status.get('total_trades', 0)} trades")

def main():
    """Main setup function"""
    print("🚀 SHARED DATABASE SETUP")
    print("=" * 50)
    print("This will set up a shared database using Replit Key-Value Store")
    print("that syncs between development and deployment environments.\n")
    
    # Step 1: Test basic functionality
    if not test_shared_database():
        print("❌ SETUP FAILED: Basic database tests failed")
        return
    
    # Step 2: Setup initial sync
    setup_initial_sync()
    
    # Step 3: Final verification
    print("\n✅ SETUP COMPLETE!")
    print("📊 Shared database is ready for cross-environment sync")
    print("\n🎯 USAGE:")
    print("1. Trades will automatically sync when added/updated")
    print("2. Use 'python sync_shared_database.py' for manual sync")
    print("3. Dashboard has shared database sync controls")
    print("4. Both development and deployment will see the same trades")

if __name__ == "__main__":
    main()
