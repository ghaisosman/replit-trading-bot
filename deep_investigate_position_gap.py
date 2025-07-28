
#!/usr/bin/env python3
"""
Deep Investigation: Position Gap Analysis
Investigate why legitimate Binance position isn't in database and why recovery isn't working
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.binance_client.client import BinanceClientWrapper
from src.execution_engine.reliable_orphan_detector import ReliableOrphanDetector
from src.reporting.telegram_reporter import TelegramReporter
from datetime import datetime
import json

def deep_investigate_position_gap():
    """Deep investigation of the position gap issue"""
    print("🔍 DEEP INVESTIGATION: POSITION GAP ANALYSIS")
    print("=" * 60)
    
    # Initialize components
    trade_db = TradeDatabase()
    binance_client = BinanceClientWrapper()
    telegram_reporter = TelegramReporter()
    
    print(f"\n📊 STEP 1: DATABASE STATE ANALYSIS")
    print("-" * 40)
    
    # Analyze database thoroughly
    all_trades = trade_db.get_all_trades()
    print(f"📊 Total trades in database: {len(all_trades)}")
    
    # Count by status
    status_counts = {}
    recent_trades = []
    ethusdt_trades = []
    
    for trade_id, trade_data in all_trades.items():
        status = trade_data.get('trade_status', 'UNKNOWN')
        status_counts[status] = status_counts.get(status, 0) + 1
        
        # Look for recent trades
        timestamp_str = trade_data.get('timestamp') or trade_data.get('created_at', '')
        if timestamp_str:
            try:
                trade_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                hours_ago = (datetime.now() - trade_time).total_seconds() / 3600
                if hours_ago <= 24:  # Last 24 hours
                    recent_trades.append((trade_id, trade_data, hours_ago))
            except:
                pass
        
        # Look for ETHUSDT trades specifically
        if trade_data.get('symbol') == 'ETHUSDT':
            ethusdt_trades.append((trade_id, trade_data))
    
    print(f"📊 Trade Status Breakdown:")
    for status, count in status_counts.items():
        print(f"   {status}: {count}")
    
    print(f"\n📊 Recent Trades (24h): {len(recent_trades)}")
    for trade_id, trade_data, hours_ago in recent_trades[-5:]:  # Last 5
        symbol = trade_data.get('symbol', 'N/A')
        status = trade_data.get('trade_status', 'N/A')
        print(f"   {trade_id}: {symbol} | {status} | {hours_ago:.1f}h ago")
    
    print(f"\n📊 ETHUSDT Trades in Database: {len(ethusdt_trades)}")
    for trade_id, trade_data in ethusdt_trades:
        status = trade_data.get('trade_status', 'N/A')
        entry_price = trade_data.get('entry_price', 0)
        quantity = trade_data.get('quantity', 0)
        timestamp = trade_data.get('timestamp', 'N/A')
        print(f"   {trade_id}: {status} | Entry: ${entry_price} | Qty: {quantity} | Time: {timestamp}")
    
    print(f"\n📊 STEP 2: BINANCE POSITION ANALYSIS")
    print("-" * 40)
    
    try:
        if binance_client.is_futures:
            account_info = binance_client.client.futures_account()
            all_positions = account_info.get('positions', [])
            
            # Find ETHUSDT position specifically
            ethusdt_position = None
            active_positions = []
            
            for pos in all_positions:
                position_amt = float(pos.get('positionAmt', 0))
                if abs(position_amt) > 0.001:
                    symbol = pos.get('symbol')
                    entry_price = float(pos.get('entryPrice', 0))
                    unrealized_pnl = float(pos.get('unRealizedProfit', 0))
                    
                    active_positions.append({
                        'symbol': symbol,
                        'position_amt': position_amt,
                        'entry_price': entry_price,
                        'unrealized_pnl': unrealized_pnl
                    })
                    
                    if symbol == 'ETHUSDT':
                        ethusdt_position = pos
            
            print(f"📊 Active Binance Positions: {len(active_positions)}")
            for pos in active_positions:
                side = 'LONG' if pos['position_amt'] > 0 else 'SHORT'
                print(f"   {pos['symbol']}: {side} | Qty: {abs(pos['position_amt'])} | Entry: ${pos['entry_price']} | PnL: ${pos['unrealized_pnl']:.2f}")
            
            if ethusdt_position:
                print(f"\n🎯 ETHUSDT POSITION FOUND:")
                print(f"   Position Amount: {ethusdt_position.get('positionAmt')}")
                print(f"   Entry Price: ${float(ethusdt_position.get('entryPrice', 0))}")
                print(f"   Mark Price: ${float(ethusdt_position.get('markPrice', 0))}")
                print(f"   Unrealized PnL: ${float(ethusdt_position.get('unRealizedProfit', 0)):.2f}")
                print(f"   Position Side: {ethusdt_position.get('positionSide', 'N/A')}")
            else:
                print(f"❌ NO ETHUSDT POSITION FOUND ON BINANCE")
                print("   This contradicts the console warning!")
        else:
            print("❌ Not using futures - cannot check positions")
            active_positions = []
            ethusdt_position = None
            
    except Exception as e:
        print(f"❌ Error checking Binance positions: {e}")
        active_positions = []
        ethusdt_position = None
    
    print(f"\n📊 STEP 3: ORPHAN DETECTION SYSTEM ANALYSIS")
    print("-" * 40)
    
    try:
        # Initialize orphan detector
        orphan_detector = ReliableOrphanDetector(binance_client, trade_db, telegram_reporter)
        
        print(f"📊 Orphan Detector Status:")
        status = orphan_detector.get_status()
        print(f"   Last Verification: {status['last_verification']}")
        print(f"   Verification Interval: {status['verification_interval']}s")
        print(f"   Next Verification In: {status['next_verification_in']:.1f}s")
        
        # Check if verification should run
        should_run = orphan_detector.should_run_verification()
        print(f"   Should Run Now: {should_run}")
        
        # Force a verification cycle to see what happens
        print(f"\n🔄 FORCING ORPHAN VERIFICATION CYCLE...")
        verification_result = orphan_detector.force_verification()
        
        print(f"📊 Verification Result:")
        print(f"   Status: {verification_result.get('status')}")
        print(f"   Open Trades: {verification_result.get('open_trades', 0)}")
        print(f"   Trades Verified: {verification_result.get('trades_verified', 0)}")
        print(f"   Orphans Detected: {verification_result.get('orphans_detected', 0)}")
        
        if verification_result.get('orphan_details'):
            print(f"   Orphan Details: {verification_result['orphan_details']}")
        
    except Exception as e:
        print(f"❌ Error with orphan detection system: {e}")
        import traceback
        print(f"🔍 Traceback: {traceback.format_exc()}")
    
    print(f"\n📊 STEP 4: GAP ANALYSIS")
    print("-" * 40)
    
    print(f"🔍 IDENTIFIED GAPS:")
    
    # Gap 1: Database vs Console Warning
    if len(ethusdt_trades) == 0 and ethusdt_position:
        print(f"   🚨 GAP 1: Console shows ETHUSDT untracked position, but NO database record")
        print(f"      This means the position was opened but never recorded in database")
        print(f"      Possible causes: Database write failure, crash during trade creation")
    
    # Gap 2: Orphan Detection
    if ethusdt_position and len(ethusdt_trades) == 0:
        print(f"   🚨 GAP 2: Orphan detection should have created recovery record")
        print(f"      Binance has ETHUSDT position but database has none")
        print(f"      This should trigger orphan detection and recovery")
    
    # Gap 3: Position Recovery
    recovery_candidates = trade_db.get_recovery_candidates()
    print(f"   📊 Recovery Candidates: {len(recovery_candidates)}")
    
    if ethusdt_position and len(recovery_candidates) == 0:
        print(f"   🚨 GAP 3: Position recovery system not working")
        print(f"      There should be recovery candidates for untracked positions")
    
    print(f"\n📊 STEP 5: ROOT CAUSE DETERMINATION")
    print("-" * 40)
    
    if ethusdt_position and len(ethusdt_trades) == 0:
        print(f"🎯 PRIMARY ROOT CAUSE:")
        print(f"   The ETHUSDT position exists on Binance but has NO database record")
        print(f"   This creates a 'phantom' position that the bot can see but cannot track")
        print(f"")
        print(f"🔍 LIKELY SCENARIO:")
        print(f"   1. Bot opened ETHUSDT position successfully on Binance")
        print(f"   2. Database write failed OR bot crashed before writing to database")
        print(f"   3. Position remained open on Binance but never recorded locally")
        print(f"   4. Bot restart detected position but had no record to match")
        print(f"   5. Orphan detection failed to create recovery record")
        print(f"")
        print(f"🚨 SECONDARY ISSUES:")
        print(f"   1. Orphan detection system not running or failing")
        print(f"   2. Position recovery mechanism not triggering")
        print(f"   3. Database integrity checks not working")
    
    else:
        print(f"✅ No clear gap identified - need more investigation")
    
    print(f"\n📊 STEP 6: IMMEDIATE ACTIONS NEEDED")
    print("-" * 40)
    
    if ethusdt_position and len(ethusdt_trades) == 0:
        print(f"🔧 IMMEDIATE FIXES REQUIRED:")
        print(f"   1. Create manual database record for ETHUSDT position")
        print(f"   2. Fix orphan detection system to prevent future occurrences")
        print(f"   3. Add database write verification to prevent silent failures")
        print(f"   4. Implement position recovery on bot startup")
        
        # Show the exact position details that need to be recorded
        position_amt = float(ethusdt_position.get('positionAmt', 0))
        entry_price = float(ethusdt_position.get('entryPrice', 0))
        side = 'BUY' if position_amt > 0 else 'SELL'
        quantity = abs(position_amt)
        
        print(f"\n📋 POSITION TO RECORD:")
        print(f"   Symbol: ETHUSDT")
        print(f"   Side: {side}")
        print(f"   Quantity: {quantity}")
        print(f"   Entry Price: ${entry_price}")
        print(f"   Current PnL: ${float(ethusdt_position.get('unRealizedProfit', 0)):.2f}")
    
    return {
        'database_trades': len(all_trades),
        'ethusdt_trades': len(ethusdt_trades),
        'binance_positions': len(active_positions) if 'active_positions' in locals() else 0,
        'ethusdt_position_exists': ethusdt_position is not None,
        'gap_identified': ethusdt_position is not None and len(ethusdt_trades) == 0
    }

if __name__ == "__main__":
    try:
        results = deep_investigate_position_gap()
        print(f"\n" + "=" * 60)
        print(f"🎯 INVESTIGATION COMPLETE")
        print(f"Gap Identified: {results.get('gap_identified', False)}")
        
        if results.get('gap_identified'):
            print(f"❌ CRITICAL ISSUE CONFIRMED: Position exists on Binance but not in database")
            print(f"🔧 Manual intervention required to restore database integrity")
        else:
            print(f"✅ No critical gaps identified")
            
    except Exception as e:
        print(f"❌ Investigation failed: {e}")
        import traceback
        print(f"🔍 Error traceback: {traceback.format_exc()}")
