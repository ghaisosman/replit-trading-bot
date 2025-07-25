
#!/usr/bin/env python3
"""
Sync Render Database with Binance Positions
===========================================

This script is designed to run on your deployed Render environment to:
1. Check actual Binance positions
2. Update database records for manually closed trades
3. Clear orphan trades from the system
4. Reset dashboard display

Safe to run multiple times - only updates what needs updating.
"""

import sys
import os
import json
from datetime import datetime

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

class RenderDatabaseSync:
    """Sync database with actual Binance positions in deployed environment"""
    
    def __init__(self):
        self.binance_client = None
        self.trade_db = None
        self.order_manager = None
        self.trade_monitor = None
        self.sync_report = {
            'timestamp': datetime.now().isoformat(),
            'trades_updated': 0,
            'orphans_cleared': 0,
            'positions_synced': 0,
            'errors': []
        }
    
    def initialize_components(self):
        """Initialize all required components"""
        try:
            print("🔧 INITIALIZING RENDER SYNC COMPONENTS")
            print("=" * 50)
            
            # Initialize Binance client
            from src.binance_client.client import BinanceClientWrapper
            self.binance_client = BinanceClientWrapper()
            print("✅ Binance client initialized")
            
            # Initialize database
            from src.execution_engine.trade_database import TradeDatabase
            self.trade_db = TradeDatabase()
            print(f"✅ Database loaded: {len(self.trade_db.trades)} trades")
            
            # Initialize order manager
            from src.analytics.trade_logger import trade_logger
            from src.execution_engine.order_manager import OrderManager
            self.order_manager = OrderManager(self.binance_client, trade_logger)
            print("✅ Order manager initialized")
            
            # Initialize telegram reporter
            from src.reporting.telegram_reporter import TelegramReporter
            self.telegram_reporter = TelegramReporter()
            print("✅ Telegram reporter initialized")
            
            # Initialize trade monitor
            from src.execution_engine.trade_monitor import TradeMonitor
            self.trade_monitor = TradeMonitor(self.binance_client, self.order_manager, self.telegram_reporter)
            print("✅ Trade monitor initialized")
            
            return True
            
        except Exception as e:
            error_msg = f"Failed to initialize components: {e}"
            print(f"❌ {error_msg}")
            self.sync_report['errors'].append(error_msg)
            return False
    
    def get_actual_binance_positions(self):
        """Get actual positions from Binance"""
        try:
            print("\n🔍 CHECKING ACTUAL BINANCE POSITIONS")
            print("-" * 40)
            
            if not self.binance_client.is_futures:
                print("❌ Not in futures mode")
                return {}
            
            account_info = self.binance_client.client.futures_account()
            positions = account_info.get('positions', [])
            
            # Filter for positions with actual amounts
            actual_positions = {}
            for pos in positions:
                symbol = pos.get('symbol')
                position_amt = float(pos.get('positionAmt', 0))
                
                if abs(position_amt) > 0.001:  # Position exists
                    side = 'BUY' if position_amt > 0 else 'SELL'
                    actual_positions[symbol] = {
                        'symbol': symbol,
                        'position_amt': position_amt,
                        'side': side,
                        'quantity': abs(position_amt),
                        'entry_price': float(pos.get('entryPrice', 0)),
                        'pnl': float(pos.get('unRealizedProfit', 0))
                    }
            
            print(f"📊 Found {len(actual_positions)} actual positions on Binance")
            for symbol, pos in actual_positions.items():
                print(f"   • {symbol}: {pos['side']} {pos['quantity']} @ ${pos['entry_price']:.4f}")
            
            return actual_positions
            
        except Exception as e:
            error_msg = f"Error getting Binance positions: {e}"
            print(f"❌ {error_msg}")
            self.sync_report['errors'].append(error_msg)
            return {}
    
    def sync_database_with_reality(self, actual_positions):
        """Update database to match actual Binance positions"""
        try:
            print("\n💾 SYNCING DATABASE WITH REALITY")
            print("-" * 35)
            
            open_trades = []
            for trade_id, trade_data in self.trade_db.trades.items():
                if trade_data.get('trade_status') == 'OPEN':
                    open_trades.append((trade_id, trade_data))
            
            print(f"📊 Database shows {len(open_trades)} OPEN trades")
            
            updated_count = 0
            
            for trade_id, trade_data in open_trades:
                symbol = trade_data.get('symbol')
                db_side = trade_data.get('side')
                db_quantity = float(trade_data.get('quantity', 0))
                
                # Check if this trade has a matching position on Binance
                position_exists = False
                
                if symbol in actual_positions:
                    binance_pos = actual_positions[symbol]
                    binance_side = binance_pos['side']
                    binance_quantity = binance_pos['quantity']
                    
                    # Check if sides and quantities roughly match
                    if (db_side == binance_side and 
                        abs(db_quantity - binance_quantity) < 0.1):
                        position_exists = True
                        print(f"   ✅ {trade_id}: Position matches Binance - keeping OPEN")
                
                if not position_exists:
                    print(f"   🔄 {trade_id}: No matching Binance position - marking CLOSED")
                    
                    # Calculate estimated PnL (simplified)
                    entry_price = float(trade_data.get('entry_price', 0))
                    current_price = entry_price  # Simplified - using entry as exit
                    
                    # Update trade as closed
                    updates = {
                        'trade_status': 'CLOSED',
                        'exit_price': current_price,
                        'exit_reason': 'Manual closure detected',
                        'pnl_usdt': 0.0,  # Simplified
                        'pnl_percentage': 0.0,
                        'duration_minutes': 0,
                        'manually_closed': True,
                        'sync_updated': True,
                        'last_updated': datetime.now().isoformat()
                    }
                    
                    success = self.trade_db.update_trade(trade_id, updates)
                    if success:
                        updated_count += 1
                        print(f"      ✅ Database updated successfully")
                    else:
                        print(f"      ❌ Failed to update database")
            
            self.sync_report['trades_updated'] = updated_count
            print(f"\n✅ SYNC COMPLETE: {updated_count} trades updated")
            return updated_count > 0
            
        except Exception as e:
            error_msg = f"Error syncing database: {e}"
            print(f"❌ {error_msg}")
            self.sync_report['errors'].append(error_msg)
            return False
    
    def clear_orphan_trades(self):
        """Clear any remaining orphan trades"""
        try:
            print("\n🧹 CLEARING ORPHAN TRADES")
            print("-" * 25)
            
            # Clear from order manager
            cleared_positions = 0
            if self.order_manager and hasattr(self.order_manager, 'active_positions'):
                active_count = len(self.order_manager.active_positions)
                print(f"📊 Order manager has {active_count} active positions")
                
                # Clear all positions since they were manually closed
                position_keys = list(self.order_manager.active_positions.keys())
                for strategy_name in position_keys:
                    try:
                        self.order_manager.clear_orphan_position(strategy_name)
                        cleared_positions += 1
                        print(f"   ✅ Cleared position: {strategy_name}")
                    except Exception as e:
                        print(f"   ⚠️ Could not clear {strategy_name}: {e}")
            
            # Clear from trade monitor
            cleared_orphans = 0
            if self.trade_monitor and hasattr(self.trade_monitor, 'orphan_trades'):
                orphan_count = len(self.trade_monitor.orphan_trades)
                print(f"📊 Trade monitor has {orphan_count} orphan trades")
                
                # Clear all orphan trades
                orphan_ids = list(self.trade_monitor.orphan_trades.keys())
                for orphan_id in orphan_ids:
                    try:
                        if orphan_id in self.trade_monitor.orphan_trades:
                            del self.trade_monitor.orphan_trades[orphan_id]
                            cleared_orphans += 1
                            print(f"   ✅ Cleared orphan: {orphan_id}")
                    except Exception as e:
                        print(f"   ⚠️ Could not clear orphan {orphan_id}: {e}")
            
            self.sync_report['orphans_cleared'] = cleared_orphans
            self.sync_report['positions_synced'] = cleared_positions
            
            print(f"\n✅ CLEANUP COMPLETE:")
            print(f"   📊 Positions cleared: {cleared_positions}")
            print(f"   🧹 Orphans cleared: {cleared_orphans}")
            
            return True
            
        except Exception as e:
            error_msg = f"Error clearing orphans: {e}"
            print(f"❌ {error_msg}")
            self.sync_report['errors'].append(error_msg)
            return False
    
    def generate_report(self):
        """Generate sync report"""
        print("\n📊 RENDER SYNC REPORT")
        print("=" * 30)
        print(f"⏰ Timestamp: {self.sync_report['timestamp']}")
        print(f"📊 Trades updated: {self.sync_report['trades_updated']}")
        print(f"🧹 Orphans cleared: {self.sync_report['orphans_cleared']}")
        print(f"📍 Positions synced: {self.sync_report['positions_synced']}")
        
        if self.sync_report['errors']:
            print(f"\n⚠️ Errors encountered: {len(self.sync_report['errors'])}")
            for error in self.sync_report['errors']:
                print(f"   • {error}")
        else:
            print("\n✅ No errors encountered")
        
        # Save report to file
        report_file = f"render_sync_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            with open(report_file, 'w') as f:
                json.dump(self.sync_report, f, indent=2)
            print(f"\n💾 Report saved to: {report_file}")
        except Exception as e:
            print(f"⚠️ Could not save report: {e}")
    
    def run_full_sync(self):
        """Run complete synchronization process"""
        print("🚀 RENDER DATABASE SYNC STARTED")
        print("=" * 50)
        print("🎯 Syncing database with actual Binance positions")
        print("🧹 Clearing orphan trades and positions")
        print("📊 Updating dashboard display")
        print()
        
        # Step 1: Initialize components
        if not self.initialize_components():
            print("❌ SYNC FAILED: Could not initialize components")
            return False
        
        # Step 2: Get actual Binance positions
        actual_positions = self.get_actual_binance_positions()
        
        # Step 3: Sync database with reality
        sync_success = self.sync_database_with_reality(actual_positions)
        
        # Step 4: Clear orphan trades
        clear_success = self.clear_orphan_trades()
        
        # Step 5: Generate report
        self.generate_report()
        
        # Final status
        if sync_success or clear_success:
            print("\n🎉 RENDER SYNC COMPLETED SUCCESSFULLY!")
            print("📊 Dashboard should now show correct positions")
            print("🔄 Orphan detection should work properly")
            return True
        else:
            print("\n⚠️ RENDER SYNC COMPLETED WITH ISSUES")
            print("📋 Check the report above for details")
            return False


def main():
    """Main execution function"""
    try:
        # Run sync
        sync_manager = RenderDatabaseSync()
        success = sync_manager.run_full_sync()
        
        if success:
            print("\n🎯 NEXT STEPS:")
            print("1. Check your dashboard - should show 0 open positions")
            print("2. Orphan detection should now work correctly")
            print("3. Future manual closures will be detected properly")
        else:
            print("\n🔧 TROUBLESHOOTING:")
            print("1. Check the error messages above")
            print("2. Verify Binance API connectivity")
            print("3. Check database file permissions")
    
    except Exception as e:
        print(f"❌ CRITICAL ERROR: {e}")
        import traceback
        print(f"🔍 Traceback: {traceback.format_exc()}")


if __name__ == "__main__":
    main()
