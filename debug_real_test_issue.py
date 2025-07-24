#!/usr/bin/env python3
"""
Real Test Issue Diagnostic Tool
Find why tests report database failures when persistence actually works
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.analytics.trade_logger import trade_logger
from datetime import datetime
import time

def debug_test_vs_reality():
    """Debug the difference between test results and actual database behavior"""
    print("🔍 REAL TEST ISSUE DIAGNOSTIC")
    print("=" * 60)

    # Step 1: Simulate what the test does
    print("\n1️⃣ SIMULATING TEST BEHAVIOR")
    print("-" * 40)

    # Create test trade like the strategy test does
    test_trade_id = f"LIFECYCLE_TEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Initialize database
    trade_db = TradeDatabase()
    initial_count = len(trade_db.trades)
    print(f"📊 Initial database trades: {initial_count}")

    # Create trade data exactly like strategy test
    test_trade_data = {
        'trade_id': test_trade_id,
        'strategy_name': 'test_strategy',
        'symbol': 'BTCUSDT',
        'side': 'BUY',
        'quantity': 0.001,
        'entry_price': 50000.0,
        'trade_status': 'OPEN',
        'position_value_usdt': 50.0,
        'leverage': 1,
        'margin_used': 50.0,
        'stop_loss': 49000.0,
        'take_profit': 51000.0,
        'timestamp': datetime.now().isoformat()
    }

    print(f"🔧 Test trade ID: {test_trade_id}")

    # Step 2: Add trade using the same method as strategy test
    print("\n2️⃣ ADDING TRADE VIA DATABASE.ADD_TRADE()")
    print("-" * 40)

    add_result = trade_db.add_trade(test_trade_id, test_trade_data)
    print(f"📝 add_trade() returned: {add_result}")

    # Check immediate memory state
    if test_trade_id in trade_db.trades:
        print(f"✅ Trade exists in current database memory")
    else:
        print(f"❌ Trade NOT in current database memory")
        return False

    # Step 3: Simulate test verification - this is where the issue likely is
    print("\n3️⃣ SIMULATING TEST VERIFICATION METHODS")
    print("-" * 40)

    # Method 1: Same instance check (what tests probably do wrong)
    same_instance_check = test_trade_id in trade_db.trades
    print(f"🔍 Same instance check: {same_instance_check}")

    # Method 2: Fresh instance check (what should work)
    fresh_db = TradeDatabase()
    fresh_instance_check = test_trade_id in fresh_db.trades
    print(f"🔍 Fresh instance check: {fresh_instance_check}")

    # Method 3: Direct file check
    import json
    try:
        with open("trading_data/trade_database.json", 'r') as f:
            file_data = json.load(f)
            file_trades = file_data.get('trades', {})
            file_check = test_trade_id in file_trades
            print(f"🔍 Direct file check: {file_check}")
            print(f"📊 File contains {len(file_trades)} trades")
    except Exception as e:
        print(f"❌ File check failed: {e}")
        file_check = False

    # Step 4: Check logger sync (another potential issue)
    print("\n4️⃣ CHECKING LOGGER SYNC STATUS")
    print("-" * 40)

    logger_trade_ids = [t.trade_id for t in trade_logger.trades]
    logger_has_trade = test_trade_id in logger_trade_ids
    print(f"🔍 Logger has trade: {logger_has_trade}")
    print(f"📊 Logger contains {len(logger_trade_ids)} trades")

    # Step 5: Test the actual verification logic that might be failing
    print("\n5️⃣ TESTING COMMON VERIFICATION PATTERNS")
    print("-" * 40)

    # Pattern 1: Database + Logger both have trade
    verification_1 = fresh_instance_check and logger_has_trade
    print(f"🔍 Database + Logger verification: {verification_1}")

    # Pattern 2: Database integrity check
    verification_2 = fresh_instance_check and file_check
    print(f"🔍 Database integrity verification: {verification_2}")

    # Pattern 3: Count-based verification (common test mistake)
    final_count = len(fresh_db.trades)
    count_increased = final_count > initial_count
    print(f"🔍 Count-based verification: {count_increased} ({initial_count} → {final_count})")

    # Step 6: Identify the likely test issue
    print("\n6️⃣ DIAGNOSTIC RESULTS")
    print("-" * 40)

    if fresh_instance_check and file_check:
        print("✅ DATABASE PERSISTENCE IS WORKING CORRECTLY")
        print("🔍 The test is likely using wrong verification logic")

        # Common test mistakes:
        if not same_instance_check:
            print("⚠️  POTENTIAL ISSUE: Test might be checking same instance instead of fresh instance")

        if not logger_has_trade:
            print("⚠️  POTENTIAL ISSUE: Test might require logger sync but it's not happening")

        print("\n💡 RECOMMENDED FIXES:")
        print("1. Use fresh TradeDatabase() instance for verification")
        print("2. Ensure proper database-to-logger sync in tests")
        print("3. Add proper wait time between operations")
        print("4. Check test is using the right trade_id format")

        # Show the working verification pattern
        print(f"\n🔧 WORKING VERIFICATION PATTERN:")
        print(f"   verification_db = TradeDatabase()")
        print(f"   success = '{test_trade_id}' in verification_db.trades")
        print(f"   # Result: {fresh_instance_check}")

        return True
    else:
        print("❌ UNEXPECTED: Database persistence actually has issues")
        return False

if __name__ == "__main__":
    success = debug_test_vs_reality()

    if success:
        print(f"\n🎯 CONCLUSION: Database works fine, fix the test logic!")
    else:
        print(f"\n❌ CONCLUSION: Unexpected database issue found")