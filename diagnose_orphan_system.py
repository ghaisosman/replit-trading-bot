
#!/usr/bin/env python3
"""
Orphan System Diagnostic Script
==============================

This script diagnoses the current state of the orphan detection and clearing system.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.execution_engine.trade_database import TradeDatabase
from src.execution_engine.order_manager import OrderManager
from src.execution_engine.trade_monitor import TradeMonitor
from src.binance_client.client import BinanceClientWrapper
from src.reporting.telegram_reporter import TelegramReporter

def diagnose_orphan_system():
    """Diagnose the orphan detection and clearing system"""
    
    print("🔍 ORPHAN SYSTEM DIAGNOSTIC")
    print("=" * 50)
    
    try:
        # Initialize components
        trade_db = TradeDatabase()
        binance_client = BinanceClientWrapper()
        order_manager = OrderManager(binance_client, None)
        telegram_reporter = TelegramReporter()
        trade_monitor = TradeMonitor(binance_client, order_manager, telegram_reporter)
        
        print("\n📊 CURRENT SYSTEM STATE")
        print("-" * 30)
        
        # Check trade monitor state
        orphan_count = len(trade_monitor.orphan_trades)
        print(f"🔍 Orphan trades in monitor: {orphan_count}")
        
        if orphan_count > 0:
            print("   Detected orphan trades:")
            for orphan_id, orphan_trade in trade_monitor.orphan_trades.items():
                print(f"   • {orphan_id}: {orphan_trade.cycles_remaining} cycles remaining")
                print(f"     Symbol: {orphan_trade.position.symbol}")
                print(f"     Side: {orphan_trade.position.side}")
                print(f"     Quantity: {orphan_trade.position.quantity}")
                print(f"     Detected: {orphan_trade.detected_at}")
        
        # Check order manager state
        active_positions = len(order_manager.active_positions)
        print(f"📈 Active positions in order manager: {active_positions}")
        
        if active_positions > 0:
            print("   Active positions:")
            for strategy, position in order_manager.active_positions.items():
                print(f"   • {strategy}: {position.symbol} {position.side} {position.quantity}")
        
        # Check database state
        open_trades = 0
        for trade_id, trade_data in trade_db.trades.items():
            if trade_data.get('trade_status') == 'OPEN':
                open_trades += 1
        
        print(f"💾 Open trades in database: {open_trades}")
        
        # Check for potential orphans
        print(f"\n🔍 ORPHAN DETECTION ANALYSIS")
        print("-" * 30)
        
        # Get Binance positions
        potential_orphans = []
        
        for strategy, position in order_manager.active_positions.items():
            symbol = position.symbol
            
            # Get Binance positions for this symbol
            try:
                if binance_client.is_futures:
                    account_info = binance_client.client.futures_account()
                    binance_positions = [pos for pos in account_info.get('positions', []) 
                                       if pos.get('symbol') == symbol]
                    
                    # Check if position exists on Binance
                    has_binance_position = any(abs(float(pos.get('positionAmt', 0))) > 0.001 
                                             for pos in binance_positions)
                    
                    if not has_binance_position:
                        potential_orphans.append({
                            'strategy': strategy,
                            'symbol': symbol,
                            'bot_position': position,
                            'binance_position': None
                        })
                        
            except Exception as e:
                print(f"   ⚠️ Error checking Binance positions for {symbol}: {e}")
        
        if potential_orphans:
            print(f"⚠️ Found {len(potential_orphans)} potential orphan trades:")
            for orphan in potential_orphans:
                print(f"   • {orphan['strategy']}: Bot has position but Binance doesn't")
                print(f"     Symbol: {orphan['symbol']}")
                print(f"     Bot quantity: {orphan['bot_position'].quantity}")
        else:
            print("✅ No potential orphan trades detected")
        
        # Test orphan detection manually
        print(f"\n🧪 MANUAL ORPHAN DETECTION TEST")
        print("-" * 30)
        
        initial_orphan_count = len(trade_monitor.orphan_trades)
        print(f"Initial orphan count: {initial_orphan_count}")
        
        # Run detection
        trade_monitor.check_for_anomalies(suppress_notifications=True)
        
        final_orphan_count = len(trade_monitor.orphan_trades)
        print(f"Final orphan count: {final_orphan_count}")
        
        if final_orphan_count > initial_orphan_count:
            print(f"✅ Detection working: {final_orphan_count - initial_orphan_count} new orphans detected")
        elif final_orphan_count == initial_orphan_count and len(potential_orphans) > 0:
            print("⚠️ Detection may have issues: Potential orphans exist but not detected")
        else:
            print("ℹ️ Detection status unclear: No new orphans detected")
        
        # Test clearing mechanism
        if len(trade_monitor.orphan_trades) > 0:
            print(f"\n🧹 CLEARING MECHANISM TEST")
            print("-" * 30)
            
            print("Testing clearing mechanism on existing orphans...")
            
            for orphan_id, orphan_trade in list(trade_monitor.orphan_trades.items()):
                print(f"Testing clearing for {orphan_id}:")
                print(f"   Current cycles: {orphan_trade.cycles_remaining}")
                
                # Force clearing
                original_cycles = orphan_trade.cycles_remaining
                orphan_trade.cycles_remaining = 0
                
                # Process clearing
                trade_monitor._process_cycle_countdown(suppress_notifications=True)
                
                # Check if cleared
                if orphan_id not in trade_monitor.orphan_trades:
                    print(f"   ✅ Successfully cleared {orphan_id}")
                else:
                    print(f"   ❌ Failed to clear {orphan_id}")
                    # Restore original cycles
                    orphan_trade.cycles_remaining = original_cycles
        
        print(f"\n📊 DIAGNOSTIC SUMMARY")
        print("-" * 30)
        print(f"🔍 Orphan trades detected: {len(trade_monitor.orphan_trades)}")
        print(f"📈 Active bot positions: {len(order_manager.active_positions)}")
        print(f"💾 Open database trades: {open_trades}")
        print(f"⚠️ Potential orphans found: {len(potential_orphans)}")
        
        if len(potential_orphans) > 0 and len(trade_monitor.orphan_trades) == 0:
            print("\n🚨 ISSUE DETECTED: Potential orphans exist but not detected by monitor")
            print("   Recommendation: Check orphan detection logic")
        elif len(trade_monitor.orphan_trades) > 0:
            print("\n✅ Orphan detection appears to be working")
            print("   Recommendation: Monitor clearing process")
        else:
            print("\n✅ System appears clean - no orphans detected")
        
    except Exception as e:
        print(f"❌ Diagnostic failed: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    diagnose_orphan_system()
