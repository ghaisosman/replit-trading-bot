#!/usr/bin/env python3
"""
Enhanced Database Sync Fix Test with Comprehensive Debugging
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.analytics.trade_logger import trade_logger
from datetime import datetime
import logging

# Enable debug logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_sync_with_full_debugging():
    """Test new trade sync with complete debugging"""
    print("🧪 ENHANCED SYNC DEBUG TEST")
    print("=" * 50)

    # Create unique test trade ID
    test_trade_id = f"DEBUG_SYNC_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

    print(f"🎯 Testing with trade ID: {test_trade_id}")
    print("-" * 40)

    # Step 1: Create test trade in logger
    print("1️⃣ CREATING TEST TRADE IN LOGGER")
    trade_created = trade_logger.log_trade_entry(
        strategy_name='DEBUG_SYNC_TEST',
        symbol='BTCUSDT',
        side='BUY',
        entry_price=50000.0,
        quantity=0.001,
        margin_used=25.0,
        leverage=2,
        trade_id=test_trade_id
    )

    if not trade_created:
        print("❌ FAILED: Could not create test trade")
        return False

    print(f"✅ Trade created with ID: {trade_created}")

    # Step 2: Verify trade exists in logger
    print("\n2️⃣ VERIFYING TRADE IN LOGGER")
    logger_trade = None
    for trade in trade_logger.trades:
        if trade.trade_id == test_trade_id:
            logger_trade = trade
            break

    if not logger_trade:
        print("❌ FAILED: Trade not found in logger")
        return False

    print("✅ Trade confirmed in logger")
    print(f"   Trade status: {logger_trade.trade_status}")
    print(f"   Symbol: {logger_trade.symbol}")
    print(f"   Entry price: {logger_trade.entry_price}")

    # Step 3: Check database BEFORE manual sync
    print("\n3️⃣ CHECKING DATABASE BEFORE MANUAL SYNC")
    trade_db = TradeDatabase()

    print(f"   Database file: {trade_db.db_file}")
    print(f"   Total trades in database: {len(trade_db.trades)}")

    db_trade_before = trade_db.get_trade(test_trade_id)
    print(f"   Test trade in database: {'YES' if db_trade_before else 'NO'}")

    # Step 4: Manual sync with full debugging
    print("\n4️⃣ PERFORMING MANUAL SYNC WITH DEBUGGING")
    print("   (Check console for detailed debug logs)")

    manual_sync_result = trade_logger._sync_to_database(test_trade_id, logger_trade)
    print(f"   Manual sync returned: {manual_sync_result}")

    # Step 5: Check database AFTER manual sync
    print("\n5️⃣ CHECKING DATABASE AFTER MANUAL SYNC")

    # Reload database to ensure we have fresh data
    trade_db_fresh = TradeDatabase()
    print(f"   Fresh database loaded with {len(trade_db_fresh.trades)} trades")

    db_trade_after = trade_db_fresh.get_trade(test_trade_id)
    print(f"   Test trade in fresh database: {'YES' if db_trade_after else 'NO'}")

    if db_trade_after:
        print("✅ SYNC SUCCESSFUL!")
        print(f"   Stored trade keys: {list(db_trade_after.keys())}")
        print(f"   Stored symbol: {db_trade_after.get('symbol')}")
        print(f"   Stored entry_price: {db_trade_after.get('entry_price')}")
        return True
    else:
        print("❌ SYNC FAILED!")

        # Additional debugging - check if file exists and content
        print("\n🔍 ADDITIONAL FILE DEBUGGING:")
        if os.path.exists(trade_db_fresh.db_file):
            file_size = os.path.getsize(trade_db_fresh.db_file)
            print(f"   Database file exists, size: {file_size} bytes")

            try:
                import json
                with open(trade_db_fresh.db_file, 'r') as f:
                    file_content = json.load(f)
                    file_trades = file_content.get('trades', {})
                    print(f"   Trades in file: {len(file_trades)}")
                    print(f"   Test trade in file: {'YES' if test_trade_id in file_trades else 'NO'}")

                    if file_trades:
                        print(f"   Sample trade IDs: {list(file_trades.keys())[:3]}")

            except Exception as e:
                print(f"   Error reading file: {e}")
        else:
            print(f"   Database file does not exist: {trade_db_fresh.db_file}")

        return False

    # Step 6: Final verification
    print("\n6️⃣ FINAL VERIFICATION")
    final_verification = test_trade_id in trade_db_fresh.trades
    print(f"   Final check - trade in database: {final_verification}")

    return final_verification

if __name__ == "__main__":
    print("🚀 ENHANCED DATABASE SYNC DEBUG TEST")
    print("=" * 60)

    success = test_sync_with_full_debugging()

    print("\n" + "=" * 60)
    if success:
        print("✅ SYNC FIX IS WORKING!")
        print("🎉 New trades are syncing properly to database")
    else:
        print("❌ SYNC FIX IS STILL BROKEN")
        print("🔍 Check the debug logs above for the root cause")
        print("⚠️ Do not proceed until this is resolved")