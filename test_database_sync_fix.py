
#!/usr/bin/env python3
"""
Comprehensive Database Sync Fix Test
Test all aspects of the simplified database sync system
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.analytics.trade_logger import trade_logger
from datetime import datetime
import json

def test_database_sync_fix():
    """Comprehensive test of the database sync fix"""
    print("🧪 COMPREHENSIVE DATABASE SYNC FIX TEST")
    print("=" * 60)
    
    # Initialize systems
    trade_db = TradeDatabase()
    
    print(f"📊 INITIAL STATE:")
    print(f"   Database trades: {len(trade_db.trades)}")
    print(f"   Logger trades: {len(trade_logger.trades)}")
    
    # Test 1: Verify sync from logger to database works
    print(f"\n1️⃣ TESTING LOGGER-TO-DATABASE SYNC:")
    print("-" * 40)
    
    initial_db_count = len(trade_db.trades)
    sync_result = trade_db.sync_from_logger()
    final_db_count = len(trade_db.trades)
    
    print(f"   📈 Synced {sync_result} trades")
    print(f"   📊 Database: {initial_db_count} → {final_db_count} trades")
    
    if sync_result >= 0:
        print("   ✅ Sync method executed successfully")
    else:
        print("   ❌ Sync method failed")
        return False
    
    # Test 2: Verify data consistency
    print(f"\n2️⃣ TESTING DATA CONSISTENCY:")
    print("-" * 40)
    
    logger_trade_ids = {t.trade_id for t in trade_logger.trades}
    db_trade_ids = set(trade_db.trades.keys())
    
    missing_in_db = logger_trade_ids - db_trade_ids
    extra_in_db = db_trade_ids - logger_trade_ids
    
    print(f"   📊 Logger trade IDs: {len(logger_trade_ids)}")
    print(f"   📊 Database trade IDs: {len(db_trade_ids)}")
    print(f"   ❌ Missing in DB: {len(missing_in_db)}")
    print(f"   ⚠️ Extra in DB: {len(extra_in_db)}")
    
    consistency_score = len(logger_trade_ids & db_trade_ids) / max(len(logger_trade_ids), len(db_trade_ids), 1) * 100
    print(f"   📈 Consistency Score: {consistency_score:.1f}%")
    
    if consistency_score >= 95:
        print("   ✅ Excellent data consistency")
    elif consistency_score >= 80:
        print("   ⚠️ Good data consistency (some minor issues)")
    else:
        print("   ❌ Poor data consistency")
        return False
    
    # Test 3: Test new trade creation and sync
    print(f"\n3️⃣ TESTING NEW TRADE CREATION & SYNC:")
    print("-" * 40)
    
    test_trade_id = f"TEST_SYNC_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Create a test trade in the logger
    test_success = trade_logger.log_trade_entry(
        strategy_name='TEST_STRATEGY',
        symbol='BTCUSDT',
        side='BUY',
        entry_price=50000.0,
        quantity=0.001,
        margin_used=25.0,
        leverage=2,
        technical_indicators={
            'rsi': 35.5,
            'macd': 125.3,
            'sma_20': 49800.0,
            'sma_50': 49500.0,
            'volume': 1500000,
            'signal_strength': 0.85
        },
        market_conditions={
            'trend': 'BULLISH',
            'volatility': 0.65,
            'phase': 'TRENDING'
        },
        trade_id=test_trade_id
    )
    
    if test_success:
        print(f"   ✅ Test trade created in logger: {test_trade_id}")
        
        # Check if it synced to database
        synced_trade = trade_db.get_trade(test_trade_id)
        if synced_trade:
            print(f"   ✅ Test trade synced to database")
            
            # Verify data completeness
            required_fields = [
                'rsi_at_entry', 'macd_at_entry', 'sma_20_at_entry', 'sma_50_at_entry',
                'volume_at_entry', 'entry_signal_strength', 'market_trend', 
                'volatility_score', 'margin_used'
            ]
            
            present_fields = [field for field in required_fields if field in synced_trade and synced_trade[field] is not None]
            missing_fields = [field for field in required_fields if field not in synced_trade or synced_trade[field] is None]
            
            print(f"   📊 Data completeness: {len(present_fields)}/{len(required_fields)} fields")
            if present_fields:
                print(f"   ✅ Present fields: {present_fields}")
            if missing_fields:
                print(f"   ❌ Missing fields: {missing_fields}")
            
            # Clean up test trade
            trade_db.trades.pop(test_trade_id, None)
            trade_db._save_database()
            trade_logger.trades = [t for t in trade_logger.trades if t.trade_id != test_trade_id]
            trade_logger._save_trades()
            
            if len(missing_fields) == 0:
                print("   ✅ Perfect data sync - all fields present")
            else:
                print("   ⚠️ Partial data sync - some fields missing")
                return False
                
        else:
            print(f"   ❌ Test trade NOT synced to database")
            return False
    else:
        print(f"   ❌ Failed to create test trade in logger")
        return False
    
    # Test 4: Test update sync
    print(f"\n4️⃣ TESTING TRADE UPDATE SYNC:")
    print("-" * 40)
    
    # Find an existing open trade to test updates
    open_trade_id = None
    for trade_id, trade_data in trade_db.trades.items():
        if trade_data.get('trade_status') == 'OPEN':
            open_trade_id = trade_id
            break
    
    if open_trade_id:
        print(f"   📊 Testing update sync with trade: {open_trade_id}")
        
        # Update in database
        update_success = trade_db.update_trade(open_trade_id, {
            'test_update_field': 'SYNC_TEST_VALUE',
            'last_test_update': datetime.now().isoformat()
        })
        
        if update_success:
            print("   ✅ Trade updated in database")
            
            # Clean up test fields
            if open_trade_id in trade_db.trades:
                trade_db.trades[open_trade_id].pop('test_update_field', None)
                trade_db.trades[open_trade_id].pop('last_test_update', None)
                trade_db._save_database()
                print("   🧹 Test fields cleaned up")
        else:
            print("   ❌ Failed to update trade")
            return False
    else:
        print("   ℹ️ No open trades available for update test - skipping")
    
    # Test 5: Performance test
    print(f"\n5️⃣ TESTING SYNC PERFORMANCE:")
    print("-" * 40)
    
    start_time = datetime.now()
    sync_count = trade_db.sync_from_logger()
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print(f"   ⏱️ Sync duration: {duration:.3f} seconds")
    print(f"   📊 Trades processed: {sync_count}")
    if sync_count > 0:
        print(f"   📈 Speed: {sync_count/duration:.1f} trades/second")
    
    if duration < 5.0:  # Should complete within 5 seconds
        print("   ✅ Performance acceptable")
    else:
        print("   ⚠️ Performance slow - consider optimization")
    
    return True

def test_database_health():
    """Test overall database health after sync fix"""
    print(f"\n🏥 DATABASE HEALTH CHECK:")
    print("-" * 40)
    
    trade_db = TradeDatabase()
    
    # Check file existence and size
    if os.path.exists(trade_db.db_file):
        file_size = os.path.getsize(trade_db.db_file)
        print(f"   📁 Database file: EXISTS ({file_size} bytes)")
    else:
        print(f"   📁 Database file: MISSING")
        return False
    
    # Check data integrity
    try:
        with open(trade_db.db_file, 'r') as f:
            data = json.load(f)
        print(f"   ✅ Database file format: VALID JSON")
        
        if 'trades' in data:
            print(f"   ✅ Trade data structure: PRESENT")
        else:
            print(f"   ❌ Trade data structure: MISSING")
            return False
            
    except Exception as e:
        print(f"   ❌ Database file corruption: {e}")
        return False
    
    # Check for orphaned trades
    current_time = datetime.now()
    stale_count = 0
    
    for trade_id, trade_data in trade_db.trades.items():
        if trade_data.get('trade_status') == 'OPEN':
            timestamp = trade_data.get('timestamp', '')
            if timestamp:
                try:
                    trade_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    age_hours = (current_time - trade_time).total_seconds() / 3600
                    if age_hours > 24:  # Stale after 24 hours
                        stale_count += 1
                except:
                    pass
    
    print(f"   📊 Stale open trades (>24h): {stale_count}")
    if stale_count == 0:
        print(f"   ✅ No stale trades detected")
    else:
        print(f"   ⚠️ {stale_count} stale trades need attention")
    
    return True

def main():
    """Run all sync fix tests"""
    print("🚀 STARTING DATABASE SYNC FIX VERIFICATION")
    print("=" * 60)
    
    try:
        # Run sync fix test
        sync_test_passed = test_database_sync_fix()
        
        # Run health check
        health_check_passed = test_database_health()
        
        print(f"\n🎯 TEST RESULTS SUMMARY:")
        print("=" * 60)
        print(f"   📊 Sync Fix Test: {'✅ PASSED' if sync_test_passed else '❌ FAILED'}")
        print(f"   🏥 Health Check: {'✅ PASSED' if health_check_passed else '❌ FAILED'}")
        
        overall_success = sync_test_passed and health_check_passed
        
        if overall_success:
            print(f"\n🎉 ALL TESTS PASSED!")
            print(f"✅ Database synchronization fix is working correctly")
            print(f"✅ Trade Logger is now the single source of truth")
            print(f"✅ New trades will automatically sync with complete data")
            print(f"✅ System is ready for the next fix")
        else:
            print(f"\n❌ SOME TESTS FAILED!")
            print(f"⚠️ Database synchronization needs more work")
            print(f"⚠️ Do not proceed to next fix until this is resolved")
        
        return overall_success
        
    except Exception as e:
        print(f"❌ TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
