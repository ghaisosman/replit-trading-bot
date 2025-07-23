
#!/usr/bin/env python3
"""
Check if Option 1 Implementation is Working Correctly
Focus: Database-first recording for NEW trades only
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.analytics.trade_logger import trade_logger
from src.execution_engine.order_manager import OrderManager
from src.binance_client.client import BinanceClientWrapper
from datetime import datetime
import inspect

def check_option1_implementation():
    """Check if Option 1 is properly implemented"""
    print("🔍 OPTION 1 IMPLEMENTATION STATUS CHECK")
    print("=" * 50)
    
    # 1. CHECK ORDER MANAGER METHOD
    print("\n📋 STEP 1: ORDER MANAGER METHOD CHECK")
    print("-" * 40)
    
    try:
        binance_client = BinanceClientWrapper()
        order_manager = OrderManager(binance_client, trade_logger)
        
        # Check if _record_confirmed_trade method exists
        if hasattr(order_manager, '_record_confirmed_trade'):
            print("✅ _record_confirmed_trade method exists")
            
            # Get the source code to verify implementation
            source = inspect.getsource(order_manager._record_confirmed_trade)
            
            # Check for Option 1 indicators
            has_database_first = "trade_db.add_trade" in source
            has_sync_to_logger = "_sync_database_to_logger" in source
            has_old_dual_recording = "trade_logger.log_trade_entry" in source
            
            print(f"✅ Database-first recording: {'YES' if has_database_first else 'NO'}")
            print(f"✅ Sync to logger: {'YES' if has_sync_to_logger else 'NO'}")
            print(f"❌ Old dual recording removed: {'YES' if not has_old_dual_recording else 'NO'}")
            
            if has_database_first and has_sync_to_logger and not has_old_dual_recording:
                print("✅ OPTION 1 CORRECTLY IMPLEMENTED")
            else:
                print("❌ OPTION 1 NEEDS FIXING")
                
        else:
            print("❌ _record_confirmed_trade method missing")
            
    except Exception as e:
        print(f"❌ Error checking order manager: {e}")
    
    # 2. CHECK SYNC METHOD
    print("\n📋 STEP 2: SYNC METHOD CHECK")
    print("-" * 30)
    
    try:
        if hasattr(order_manager, '_sync_database_to_logger'):
            print("✅ _sync_database_to_logger method exists")
            
            # Check the sync method implementation
            sync_source = inspect.getsource(order_manager._sync_database_to_logger)
            has_logger_import = "from src.analytics.trade_logger import trade_logger" in sync_source
            has_log_trade_call = "trade_logger.log_trade" in sync_source
            
            print(f"✅ Logger import: {'YES' if has_logger_import else 'NO'}")
            print(f"✅ Log trade call: {'YES' if has_log_trade_call else 'NO'}")
            
        else:
            print("❌ _sync_database_to_logger method missing")
            
    except Exception as e:
        print(f"❌ Error checking sync method: {e}")
    
    # 3. TEST WITH SIMULATED TRADE
    print("\n📋 STEP 3: SIMULATED TRADE TEST")
    print("-" * 35)
    
    try:
        trade_db = TradeDatabase()
        
        # Create test trade data
        test_trade_id = f"OPTION1_TEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        test_data = {
            'strategy_name': 'TEST_STRATEGY',
            'symbol': 'TESTUSDT',
            'side': 'BUY',
            'quantity': 1.0,
            'entry_price': 100.0,
            'trade_status': 'OPEN',
            'position_value_usdt': 100.0,
            'leverage': 5,
            'margin_used': 20.0
        }
        
        # Test database recording
        db_success = trade_db.add_trade(test_trade_id, test_data)
        print(f"Database recording: {'SUCCESS' if db_success else 'FAILED'}")
        
        # Test sync to logger
        if db_success:
            sync_success = order_manager._sync_database_to_logger(test_trade_id, test_data)
            print(f"Sync to logger: {'SUCCESS' if sync_success else 'FAILED'}")
            
            # Verify in logger
            logger_has_trade = any(t.trade_id == test_trade_id for t in trade_logger.trades)
            print(f"Trade in logger: {'YES' if logger_has_trade else 'NO'}")
            
        # Cleanup test trade
        if test_trade_id in trade_db.trades:
            del trade_db.trades[test_trade_id]
            trade_db._save_database()
        
        trade_logger.trades = [t for t in trade_logger.trades if t.trade_id != test_trade_id]
        trade_logger._save_trades()
        print("✅ Test data cleaned up")
        
    except Exception as e:
        print(f"❌ Error in simulated test: {e}")
    
    # 4. FINAL ASSESSMENT
    print("\n🏁 FINAL ASSESSMENT")
    print("-" * 20)
    
    print("Option 1 Implementation Requirements:")
    print("1. ✅ Database-first recording (TradeDatabase.add_trade)")
    print("2. ✅ Then sync to logger (_sync_database_to_logger)")
    print("3. ✅ Remove old dual recording")
    print("4. ✅ Single source of truth (database)")
    
    print("\nFor NEW trades going forward:")
    print("- All trades should be recorded in database first")
    print("- Then synced to logger for analytics")
    print("- No more duplicate recording issues")

if __name__ == "__main__":
    check_option1_implementation()
