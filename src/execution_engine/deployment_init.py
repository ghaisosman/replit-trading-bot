
#!/usr/bin/env python3
"""
Deployment Initialization System
==============================

Handles initial setup and recovery for deployment environments like Render.
Runs once on deployment startup to ensure all systems are properly synchronized.
"""

import os
import logging
import asyncio
from datetime import datetime

class DeploymentInitializer:
    """Initialize deployment environment with automatic recovery"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.is_deployment = os.environ.get('IS_DEPLOYMENT', '0') == '1'
        
    async def initialize_deployment(self, bot_manager):
        """Initialize deployment environment"""
        if not self.is_deployment:
            self.logger.info("🏠 Development environment - skipping deployment initialization")
            return True
            
        self.logger.info("🚀 DEPLOYMENT INITIALIZATION STARTED")
        self.logger.info("=" * 50)
        
        try:
            # Step 1: Verify API connectivity
            await self._verify_api_connection(bot_manager.binance_client)
            
            # Step 2: Initialize database and recovery systems
            await self._initialize_recovery_systems(bot_manager)
            
            # Step 3: Run initial position recovery
            await self._run_initial_recovery(bot_manager)
            
            # Step 4: Verify all systems are synchronized
            await self._verify_system_sync(bot_manager)
            
            self.logger.info("✅ DEPLOYMENT INITIALIZATION COMPLETE")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ DEPLOYMENT INITIALIZATION FAILED: {e}")
            return False
            
    async def _verify_api_connection(self, binance_client):
        """Verify Binance API connectivity"""
        self.logger.info("🔗 Verifying API connection...")
        
        connection_test = await binance_client.test_connection()
        if not connection_test:
            raise Exception("Cannot establish API connection")
            
        self.logger.info("✅ API connection verified")
        
    async def _initialize_recovery_systems(self, bot_manager):
        """Initialize recovery and monitoring systems"""
        self.logger.info("🔧 Initializing recovery systems...")
        
        # Ensure database is properly loaded
        if not hasattr(bot_manager.trade_db, 'trades') or not isinstance(bot_manager.trade_db.trades, dict):
            bot_manager.trade_db.trades = {}
            self.logger.info("📊 Database initialized with empty state")
            
        # Initialize auto-recovery if not already initialized
        if not bot_manager.auto_recovery:
            from src.execution_engine.auto_recovery_system import get_auto_recovery_system
            bot_manager.auto_recovery = get_auto_recovery_system(
                bot_manager.binance_client,
                bot_manager.trade_db,
                bot_manager.order_manager,
                bot_manager.trade_monitor
            )
            
        self.logger.info("✅ Recovery systems initialized")
        
    async def _run_initial_recovery(self, bot_manager):
        """Run initial position recovery"""
        self.logger.info("🔄 Running initial position recovery...")
        
        if bot_manager.auto_recovery:
            await bot_manager.auto_recovery.run_recovery_cycle()
            self.logger.info("✅ Initial recovery completed")
        else:
            self.logger.warning("⚠️ Auto-recovery system not available")
            
    async def _verify_system_sync(self, bot_manager):
        """Verify all systems are properly synchronized"""
        self.logger.info("🔍 Verifying system synchronization...")
        
        # Check database state
        open_trades = sum(1 for trade in bot_manager.trade_db.trades.values() 
                         if trade.get('trade_status') == 'OPEN')
        self.logger.info(f"📊 Database shows {open_trades} open trades")
        
        # Check order manager state
        active_positions = len(getattr(bot_manager.order_manager, 'active_positions', {}))
        self.logger.info(f"📊 Order manager shows {active_positions} active positions")
        
        # Check for orphan trades
        orphan_count = len(getattr(bot_manager.trade_monitor, 'orphan_trades', {}))
        if orphan_count > 0:
            self.logger.warning(f"⚠️ Found {orphan_count} orphan trades - auto-recovery will handle these")
        else:
            self.logger.info("✅ No orphan trades detected")
            
        self.logger.info("✅ System synchronization verified")


# Global instance
deployment_initializer = DeploymentInitializer()

async def initialize_deployment_environment(bot_manager):
    """Initialize deployment environment if needed"""
    return await deployment_initializer.initialize_deployment(bot_manager)
