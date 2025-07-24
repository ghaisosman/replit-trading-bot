
#!/usr/bin/env python3
"""
Database Persistence Debugging Tool
Deep dive into why database saves appear successful but data doesn't persist
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from datetime import datetime
import json
import tempfile
import time

def debug_database_persistence():
    """Debug database persistence with step-by-step verification"""
    print("🔍 DATABASE PERSISTENCE DEBUGGING")
    print("=" * 60)
    
    # Step 1: Initialize fresh database
    print("\n1️⃣ INITIALIZING FRESH DATABASE")
    print("-" * 40)
    
    trade_db = TradeDatabase()
    initial_count = len(trade_db.trades)
    print(f"✅ Database initialized with {initial_count} existing trades")
    print(f"📁 Database file: {trade_db.db_file}")
    
    # Check if database file exists
    if os.path.exists(trade_db.db_file):
        file_size = os.path.getsize(trade_db.db_file)
        print(f"📊 Database file exists, size: {file_size} bytes")
    else:
        print("❌ Database file does not exist")
    
    # Step 2: Create test trade data
    print("\n2️⃣ CREATING TEST TRADE DATA")
    print("-" * 40)
    
    test_trade_id = f"DEBUG_TEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    test_trade_data = {
        'strategy_name': 'debug_test',
        'symbol': 'BTCUSDT',
        'side': 'BUY',
        'quantity': 0.001,
        'entry_price': 50000.0,
        'trade_status': 'OPEN',
        'position_value_usdt': 50.0,
        'leverage': 1,
        'margin_used': 50.0
    }
    
    print(f"🔧 Test trade ID: {test_trade_id}")
    print(f"📊 Test trade data: {test_trade_data}")
    
    # Step 3: Manual database save with detailed logging
    print("\n3️⃣ MANUAL DATABASE SAVE WITH DETAILED LOGGING")
    print("-" * 40)
    
    # Add to memory first
    trade_db.trades[test_trade_id] = test_trade_data.copy()
    trade_db.trades[test_trade_id]['created_at'] = datetime.now().isoformat()
    trade_db.trades[test_trade_id]['last_updated'] = datetime.now().isoformat()
    
    print(f"✅ Added to memory, trades count: {len(trade_db.trades)}")
    
    # Manual save with verbose logging
    try:
        print(f"🔧 Starting manual save process...")
        
        # Prepare data
        data = {
            'trades': trade_db.trades,
            'last_updated': datetime.now().isoformat(),
            'debug_info': {
                'save_timestamp': datetime.now().isoformat(),
                'total_trades': len(trade_db.trades),
                'test_trade_included': test_trade_id in trade_db.trades
            }
        }
        
        print(f"📊 Data prepared with {len(data['trades'])} trades")
        
        # Try writing to a temporary file first
        temp_file = f"{trade_db.db_file}.debug_temp"
        print(f"🔧 Writing to temp file: {temp_file}")
        
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        
        print(f"✅ Temp file written successfully")
        
        # Check temp file
        if os.path.exists(temp_file):
            temp_size = os.path.getsize(temp_file)
            print(f"📊 Temp file size: {temp_size} bytes")
            
            # Verify temp file content
            with open(temp_file, 'r', encoding='utf-8') as f:
                temp_data = json.load(f)
                temp_trades = temp_data.get('trades', {})
                print(f"📊 Temp file contains {len(temp_trades)} trades")
                print(f"✅ Test trade in temp file: {'YES' if test_trade_id in temp_trades else 'NO'}")
        
        # Move temp file to actual location
        print(f"🔧 Moving temp file to actual location...")
        os.replace(temp_file, trade_db.db_file)
        print(f"✅ File moved successfully")
        
    except Exception as e:
        print(f"❌ Manual save failed: {e}")
        import traceback
        print(f"🔍 Traceback: {traceback.format_exc()}")
        return False
    
    # Step 4: Immediate file verification
    print("\n4️⃣ IMMEDIATE FILE VERIFICATION")
    print("-" * 40)
    
    time.sleep(0.1)  # Small delay to ensure filesystem sync
    
    if os.path.exists(trade_db.db_file):
        file_size = os.path.getsize(trade_db.db_file)
        print(f"📊 Database file exists, size: {file_size} bytes")
        
        try:
            with open(trade_db.db_file, 'r', encoding='utf-8') as f:
                verification_data = json.load(f)
                verification_trades = verification_data.get('trades', {})
                
                print(f"📊 File contains {len(verification_trades)} trades")
                print(f"✅ Test trade in file: {'YES' if test_trade_id in verification_trades else 'NO'}")
                
                if test_trade_id in verification_trades:
                    saved_trade = verification_trades[test_trade_id]
                    print(f"📊 Saved trade data matches: {'YES' if saved_trade.get('symbol') == 'BTCUSDT' else 'NO'}")
                else:
                    print(f"❌ Test trade NOT found in file!")
                    print(f"🔍 Available trade IDs: {list(verification_trades.keys())[:5]}")
                    
        except Exception as e:
            print(f"❌ Error reading verification file: {e}")
            return False
    else:
        print(f"❌ Database file does not exist after save!")
        return False
    
    # Step 5: Fresh database instance verification
    print("\n5️⃣ FRESH DATABASE INSTANCE VERIFICATION")
    print("-" * 40)
    
    try:
        fresh_db = TradeDatabase()
        fresh_count = len(fresh_db.trades)
        print(f"📊 Fresh database loaded {fresh_count} trades")
        print(f"✅ Test trade in fresh database: {'YES' if test_trade_id in fresh_db.trades else 'NO'}")
        
        if test_trade_id in fresh_db.trades:
            print(f"✅ SUCCESS: Database persistence is working correctly!")
            return True
        else:
            print(f"❌ FAILURE: Test trade not found in fresh database instance")
            print(f"🔍 This indicates a persistence problem")
            return False
            
    except Exception as e:
        print(f"❌ Error creating fresh database: {e}")
        return False

def test_filesystem_permissions():
    """Test filesystem permissions and write capabilities"""
    print("\n🔧 TESTING FILESYSTEM PERMISSIONS")
    print("=" * 50)
    
    # Test 1: Write to trading_data directory
    try:
        test_dir = "trading_data"
        os.makedirs(test_dir, exist_ok=True)
        test_file = os.path.join(test_dir, "permission_test.txt")
        
        with open(test_file, 'w') as f:
            f.write("permission test")
        
        if os.path.exists(test_file):
            print(f"✅ Can write to {test_dir} directory")
            os.remove(test_file)
        else:
            print(f"❌ Cannot write to {test_dir} directory")
            
    except Exception as e:
        print(f"❌ Permission test failed: {e}")
    
    # Test 2: Write to root directory
    try:
        root_test_file = "root_permission_test.txt"
        with open(root_test_file, 'w') as f:
            f.write("root permission test")
        
        if os.path.exists(root_test_file):
            print(f"✅ Can write to root directory")
            os.remove(root_test_file)
        else:
            print(f"❌ Cannot write to root directory")
            
    except Exception as e:
        print(f"❌ Root permission test failed: {e}")

if __name__ == "__main__":
    print("🚀 DATABASE PERSISTENCE DEBUG TOOL")
    print("Investigating why database saves appear successful but data doesn't persist")
    print("=" * 80)
    
    # Run filesystem tests first
    test_filesystem_permissions()
    
    # Run main debugging
    success = debug_database_persistence()
    
    if success:
        print(f"\n🎉 DATABASE PERSISTENCE IS WORKING CORRECTLY")
        print("The issue may be elsewhere in the codebase")
    else:
        print(f"\n❌ DATABASE PERSISTENCE ISSUE CONFIRMED")
        print("This tool has identified the root cause of the problem")
        print("\nRecommended actions:")
        print("1. Check file system permissions")
        print("2. Check disk space availability") 
        print("3. Check for Replit-specific file system limitations")
        print("4. Consider using alternative persistence methods")
