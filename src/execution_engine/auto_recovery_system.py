
#!/usr/bin/env python3
"""
Automatic Recovery System for Render Deployment
==============================================

This system automatically:
1. Detects orphaned Binance positions on startup
2. Creates matching database records
3. Syncs with trade monitoring systems
4. Runs continuously to catch manual closures

Safe to run multiple times - only updates what needs updating.
"""

import logging
import asyncio
import time
from datetime import datetime
from typing import Dict, List, Optional
import os

class AutoRecoverySystem:
    """Automatic position recovery and synchronization system"""
    
    def __init__(self, binance_client, trade_db, order_manager, trade_monitor):
        self.logger = logging.getLogger(__name__)
        self.binance_client = binance_client
        self.trade_db = trade_db
        self.order_manager = order_manager
        self.trade_monitor = trade_monitor
        self.is_running = False
        self.recovery_interval = 300  # 5 minutes
        
    async def start_auto_recovery(self):
        """Start the automatic recovery system"""
        if self.is_running:
            self.logger.info("🔄 Auto-recovery already running")
            return
            
        self.is_running = True
        self.logger.info("🚀 STARTING AUTO-RECOVERY SYSTEM")
        
        # Run initial recovery
        await self.run_recovery_cycle()
        
        # Start continuous monitoring
        asyncio.create_task(self._recovery_loop())
        
    async def _recovery_loop(self):
        """Continuous recovery monitoring loop"""
        while self.is_running:
            try:
                await asyncio.sleep(self.recovery_interval)
                if self.is_running:
                    await self.run_recovery_cycle()
            except Exception as e:
                self.logger.error(f"❌ Recovery loop error: {e}")
                await asyncio.sleep(60)  # Wait before retrying
                
    async def run_recovery_cycle(self):
        """Run a complete recovery cycle"""
        try:
            self.logger.info("🔍 RUNNING RECOVERY CYCLE")
            
            # Step 1: Get actual Binance positions
            binance_positions = await self.get_binance_positions()
            if not binance_positions:
                self.logger.info("📊 No active Binance positions found")
                return
                
            # Step 2: Match with database records
            orphaned_positions = await self.find_orphaned_positions(binance_positions)
            
            # Step 3: Create database records for orphans
            if orphaned_positions:
                recovered = await self.recover_orphaned_positions(orphaned_positions)
                self.logger.info(f"✅ Recovered {recovered} orphaned positions")
                
            # Step 4: Update closed positions
            closed_trades = await self.detect_closed_positions(binance_positions)
            if closed_trades:
                updated = await self.update_closed_trades(closed_trades)
                self.logger.info(f"✅ Updated {updated} closed trades")
                
            # Step 5: Sync with monitoring systems
            await self.sync_monitoring_systems()
            
        except Exception as e:
            self.logger.error(f"❌ Recovery cycle error: {e}")
            
    async def get_binance_positions(self) -> Dict[str, dict]:
        """Get all active positions from Binance"""
        try:
            if not self.binance_client.is_futures:
                return {}
                
            account_info = self.binance_client.client.futures_account()
            positions = account_info.get('positions', [])
            
            active_positions = {}
            for pos in positions:
                symbol = pos.get('symbol')
                position_amt = float(pos.get('positionAmt', 0))
                
                if abs(position_amt) > 0.001:  # Has actual position
                    active_positions[symbol] = {
                        'symbol': symbol,
                        'position_amt': position_amt,
                        'side': 'BUY' if position_amt > 0 else 'SELL',
                        'quantity': abs(position_amt),
                        'entry_price': float(pos.get('entryPrice', 0)),
                        'unrealized_pnl': float(pos.get('unRealizedProfit', 0)),
                        'raw_data': pos
                    }
                    
            self.logger.info(f"📊 Found {len(active_positions)} active Binance positions")
            return active_positions
            
        except Exception as e:
            self.logger.error(f"❌ Error getting Binance positions: {e}")
            return {}
            
    async def find_orphaned_positions(self, binance_positions: Dict[str, dict]) -> List[dict]:
        """Find Binance positions without matching database records"""
        orphaned = []
        
        for symbol, pos in binance_positions.items():
            # Check if we have a matching database record
            position_matched = False
            
            for trade_id, trade_data in self.trade_db.trades.items():
                if (trade_data.get('symbol') == symbol and 
                    trade_data.get('trade_status') == 'OPEN'):
                    
                    db_quantity = float(trade_data.get('quantity', 0))
                    db_side = trade_data.get('side')
                    
                    # Check if quantities and sides match
                    expected_amt = db_quantity if db_side == 'BUY' else -db_quantity
                    
                    if abs(pos['position_amt'] - expected_amt) < 0.1:
                        position_matched = True
                        break
                        
            if not position_matched:
                orphaned.append(pos)
                self.logger.info(f"🔍 Found orphaned position: {symbol} {pos['side']} {pos['quantity']}")
                
        return orphaned
        
    async def recover_orphaned_positions(self, orphaned_positions: List[dict]) -> int:
        """Create database records for orphaned positions"""
        recovered_count = 0
        
        for pos in orphaned_positions:
            try:
                # Generate recovery trade ID
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                strategy_name = self._estimate_strategy(pos['symbol'])
                trade_id = f"RECOVERY_{strategy_name}_{pos['symbol']}_{timestamp}"
                
                # Create trade record
                trade_data = {
                    'trade_id': trade_id,
                    'strategy_name': strategy_name,
                    'symbol': pos['symbol'],
                    'side': pos['side'],
                    'quantity': pos['quantity'],
                    'entry_price': pos['entry_price'],
                    'trade_status': 'OPEN',
                    'position_value_usdt': pos['entry_price'] * pos['quantity'],
                    'leverage': 3,  # Default leverage
                    'margin_used': (pos['entry_price'] * pos['quantity']) / 3,
                    'unrealized_pnl': pos['unrealized_pnl'],
                    'recovery_trade': True,
                    'auto_recovered': True,
                    'timestamp': datetime.now().isoformat(),
                    'created_at': datetime.now().isoformat(),
                    'last_updated': datetime.now().isoformat()
                }
                
                # Add to database
                success = self.trade_db.add_trade(trade_id, trade_data)
                if success:
                    recovered_count += 1
                    self.logger.info(f"✅ Auto-recovered: {trade_id}")
                    
                    # Add to order manager active positions
                    if hasattr(self.order_manager, 'active_positions'):
                        self.order_manager.active_positions[strategy_name] = {
                            'trade_id': trade_id,
                            'symbol': pos['symbol'],
                            'side': pos['side'],
                            'quantity': pos['quantity'],
                            'entry_price': pos['entry_price']
                        }
                        
            except Exception as e:
                self.logger.error(f"❌ Error recovering position {pos['symbol']}: {e}")
                
        return recovered_count
        
    async def detect_closed_positions(self, binance_positions: Dict[str, dict]) -> List[str]:
        """Detect database trades that are closed on Binance"""
        closed_trades = []
        
        # Get all open trades from database
        for trade_id, trade_data in self.trade_db.trades.items():
            if trade_data.get('trade_status') == 'OPEN':
                symbol = trade_data.get('symbol')
                
                # Check if position still exists on Binance
                if symbol not in binance_positions:
                    closed_trades.append(trade_id)
                    self.logger.info(f"🔍 Detected closed position: {trade_id}")
                    
        return closed_trades
        
    async def update_closed_trades(self, closed_trade_ids: List[str]) -> int:
        """Update database records for closed trades"""
        updated_count = 0
        
        for trade_id in closed_trade_ids:
            try:
                updates = {
                    'trade_status': 'CLOSED',
                    'exit_reason': 'Manual closure detected',
                    'exit_price': self.trade_db.trades[trade_id]['entry_price'],  # Simplified
                    'pnl_usdt': 0.0,  # Will be calculated properly later
                    'pnl_percentage': 0.0,
                    'manually_closed': True,
                    'auto_detected_closure': True,
                    'last_updated': datetime.now().isoformat()
                }
                
                success = self.trade_db.update_trade(trade_id, updates)
                if success:
                    updated_count += 1
                    self.logger.info(f"✅ Auto-updated closed trade: {trade_id}")
                    
            except Exception as e:
                self.logger.error(f"❌ Error updating closed trade {trade_id}: {e}")
                
        return updated_count
        
    async def sync_monitoring_systems(self):
        """Sync with order manager and trade monitor"""
        try:
            # Clear orphan positions from order manager
            if hasattr(self.order_manager, 'active_positions'):
                positions_to_clear = []
                for strategy_name, position_data in self.order_manager.active_positions.items():
                    trade_id = position_data.get('trade_id')
                    if trade_id and trade_id in self.trade_db.trades:
                        if self.trade_db.trades[trade_id].get('trade_status') == 'CLOSED':
                            positions_to_clear.append(strategy_name)
                            
                for strategy_name in positions_to_clear:
                    if hasattr(self.order_manager, 'clear_orphan_position'):
                        self.order_manager.clear_orphan_position(strategy_name)
                        self.logger.info(f"🧹 Cleared orphan position: {strategy_name}")
                        
            # Clear orphan trades from trade monitor
            if hasattr(self.trade_monitor, 'orphan_trades'):
                orphans_to_clear = []
                for orphan_id in list(self.trade_monitor.orphan_trades.keys()):
                    if orphan_id in self.trade_db.trades:
                        if self.trade_db.trades[orphan_id].get('trade_status') == 'CLOSED':
                            orphans_to_clear.append(orphan_id)
                            
                for orphan_id in orphans_to_clear:
                    if orphan_id in self.trade_monitor.orphan_trades:
                        del self.trade_monitor.orphan_trades[orphan_id]
                        self.logger.info(f"🧹 Cleared orphan trade: {orphan_id}")
                        
        except Exception as e:
            self.logger.error(f"❌ Error syncing monitoring systems: {e}")
            
    def _estimate_strategy(self, symbol: str) -> str:
        """Estimate strategy name based on symbol"""
        if "BTC" in symbol:
            return "macd_divergence"
        elif "ETH" in symbol:
            return "engulfing_pattern"
        elif "SOL" in symbol:
            return "rsi_oversold"
        elif "XRP" in symbol:
            return "smart_money"
        else:
            return "manual_recovery"
            
    def stop(self):
        """Stop the auto-recovery system"""
        self.is_running = False
        self.logger.info("🛑 Auto-recovery system stopped")


# Singleton instance
auto_recovery_system = None

def get_auto_recovery_system(binance_client=None, trade_db=None, order_manager=None, trade_monitor=None):
    """Get or create auto-recovery system instance"""
    global auto_recovery_system
    
    if auto_recovery_system is None and all([binance_client, trade_db, order_manager, trade_monitor]):
        auto_recovery_system = AutoRecoverySystem(binance_client, trade_db, order_manager, trade_monitor)
        
    return auto_recovery_system
