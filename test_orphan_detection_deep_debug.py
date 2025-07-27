
#!/usr/bin/env python3
"""
Deep Debug Orphan Detection System
=================================

This script provides comprehensive debugging for the orphan detection system
to identify exactly why it's not working automatically.
"""

import sys
import os
import time
from datetime import datetime

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def test_orphan_detection_deep_debug():
    """Run comprehensive orphan detection debugging"""
    try:
        print("🔍 DEEP DEBUG: Orphan Detection System Analysis")
        print("=" * 60)
        
        # Import required modules
        from src.execution_engine.trade_database import TradeDatabase
        from src.execution_engine.reliable_orphan_detector import ReliableOrphanDetector
        from src.binance_client.client import BinanceClientWrapper
        from src.reporting.telegram_reporter import TelegramReporter
        
        print("✅ Successfully imported required modules")
        
        # Initialize components
        print("\n📊 STEP 1: Initializing components...")
        trade_db = TradeDatabase()
        binance_client = BinanceClientWrapper()
        telegram_reporter = TelegramReporter()
        orphan_detector = ReliableOrphanDetector(binance_client, trade_db, telegram_reporter)
        
        print("✅ Components initialized successfully")
        
        # Test database connectivity
        print("\n📊 STEP 2: Testing database connectivity...")
        all_trades = trade_db.get_all_trades()
        print(f"   Total trades in database: {len(all_trades)}")
        
        open_trades = []
        for trade_id, trade_data in all_trades.items():
            if trade_data.get('trade_status', '').upper() == 'OPEN':
                open_trades.append((trade_id, trade_data))
        
        print(f"   Open trades in database: {len(open_trades)}")
        
        if open_trades:
            print("   Open trade details:")
            for trade_id, trade_data in open_trades:
                symbol = trade_data.get('symbol', 'unknown')
                side = trade_data.get('side', 'unknown')
                quantity = trade_data.get('quantity', 0)
                print(f"      • {trade_id}: {symbol} {side} {quantity}")
        
        # Test Binance connectivity
        print("\n📊 STEP 3: Testing Binance API connectivity...")
        try:
            if binance_client.is_futures:
                account_info = binance_client.client.futures_account()
                total_balance = float(account_info.get('totalWalletBalance', 0))
                print(f"   ✅ Binance API connected | Balance: ${total_balance:.2f}")
                
                # Get positions
                positions = account_info.get('positions', [])
                active_positions = [pos for pos in positions if abs(float(pos.get('positionAmt', 0))) > 0.001]
                print(f"   📊 Total positions: {len(positions)}")
                print(f"   📊 Active positions: {len(active_positions)}")
                
                if active_positions:
                    print("   Active position details:")
                    for pos in active_positions:
                        symbol = pos.get('symbol')
                        amt = float(pos.get('positionAmt', 0))
                        entry = float(pos.get('entryPrice', 0))
                        pnl = float(pos.get('unRealizedProfit', 0))
                        print(f"      • {symbol}: {amt} @ ${entry:.4f} (PnL: ${pnl:.2f})")
            else:
                print("   ⚠️ Not using futures - limited position verification")
                
        except Exception as api_error:
            print(f"   ❌ Binance API error: {api_error}")
            if "IP" in str(api_error) or "geo" in str(api_error).lower():
                print("   🌍 Geographic restriction detected")
            
        # Test orphan detector timing
        print("\n📊 STEP 4: Testing orphan detector timing...")
        last_verification = orphan_detector.last_verification
        verification_interval = orphan_detector.verification_interval
        time_since_last = (datetime.now() - last_verification).total_seconds()
        should_run = orphan_detector.should_run_verification()
        
        print(f"   Last verification: {last_verification}")
        print(f"   Verification interval: {verification_interval}s")
        print(f"   Time since last: {time_since_last:.1f}s")
        print(f"   Should run verification: {should_run}")
        
        # Force verification cycle
        print("\n📊 STEP 5: Running forced verification cycle...")
        print("   This will use DEEP DEBUG logging to show exactly what happens...")
        
        # Force immediate verification
        result = orphan_detector.force_verification()
        
        print(f"\n📊 VERIFICATION RESULT:")
        print(f"   Status: {result.get('status')}")
        print(f"   Open trades: {result.get('open_trades', 0)}")
        print(f"   Trades verified: {result.get('trades_verified', 0)}")
        print(f"   Orphans detected: {result.get('orphans_detected', 0)}")
        
        if result.get('orphan_details'):
            print("   Orphan details:")
            for orphan in result['orphan_details']:
                if orphan.get('success'):
                    trade_id = orphan.get('trade_id')
                    symbol = orphan.get('symbol')
                    pnl = orphan.get('pnl_usdt', 0)
                    print(f"      • {trade_id}: {symbol} (PnL: ${pnl:.2f})")
        
        # Analysis and recommendations
        print("\n📊 ANALYSIS AND RECOMMENDATIONS:")
        print("=" * 60)
        
        if len(open_trades) == 0:
            print("✅ NO ISSUES: No open trades in database")
            print("   The orphan detection system is working correctly")
            print("   There are simply no orphans to detect")
        
        elif result.get('orphans_detected', 0) == len(open_trades):
            print("✅ WORKING CORRECTLY: All open trades detected as orphans")
            print("   The orphan detection system is functioning properly")
            print("   The trades have been automatically marked as manually closed")
        
        elif result.get('orphans_detected', 0) == 0 and len(open_trades) > 0:
            print("🚨 ISSUE IDENTIFIED: Open trades exist but no orphans detected")
            print("   This indicates a problem with the detection logic")
            print("   Check the detailed logs above for specific issues")
            
            # Additional diagnostics
            if result.get('status') == 'error':
                print(f"   ERROR in verification: {result.get('error')}")
            elif "IP" in str(result) or "geo" in str(result).lower():
                print("   ISSUE: Geographic restrictions preventing Binance API access")
                print("   SOLUTION: This is expected in deployment - orphan detection disabled")
            else:
                print("   The detailed logs above should show where the detection is failing")
        
        else:
            print(f"⚠️ PARTIAL DETECTION: {result.get('orphans_detected', 0)} of {len(open_trades)} trades detected")
            print("   Some trades were detected as orphans but not all")
            print("   Check the detailed logs for specific trade issues")
            
        print(f"\n✅ Deep debug analysis completed at {datetime.now()}")
        return result
        
    except Exception as e:
        print(f"❌ Deep debug failed: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return None

if __name__ == "__main__":
    test_orphan_detection_deep_debug()
