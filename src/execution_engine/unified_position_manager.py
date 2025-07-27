import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from src.execution_engine.trade_database import TradeDatabase
from src.execution_engine.cloud_database_sync import get_cloud_sync

@dataclass
class UnifiedPosition:
    """Single source of truth for position data"""
    trade_id: str
    strategy_name: str
    symbol: str
    side: str  # 'BUY' or 'SELL'
    entry_price: float
    quantity: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    margin_used: float = 0.0
    leverage: int = 1
    status: str = "OPEN"  # OPEN, CLOSED
    created_at: str = ""
    last_updated: str = ""
    binance_position_amt: float = 0.0  # Track actual Binance position

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        self.last_updated = datetime.now().isoformat()

class UnifiedPositionManager:
    """
    Unified Position Manager - Single Source of Truth

    This system ensures both local development and Render deployment
    maintain identical position states by using the cloud database
    as the authoritative source.
    """

    def __init__(self, binance_client, telegram_reporter):
        self.logger = logging.getLogger(__name__)
        self.binance_client = binance_client
        self.telegram_reporter = telegram_reporter
        self.trade_db = TradeDatabase()

        # Single source of truth - positions are ALWAYS loaded from database
        self._positions: Dict[str, UnifiedPosition] = {}

        self.logger.info("🔗 UNIFIED POSITION MANAGER INITIALIZED")
        self.logger.info("📊 Single source of truth: PostgreSQL Cloud Database")

    async def initialize(self):
        """Initialize positions from database and sync with Binance"""
        try:
            self.logger.info("🔄 INITIALIZING UNIFIED POSITION SYSTEM...")

            # Step 1: Load all positions from database
            await self._load_positions_from_database()

            # Step 2: Sync with actual Binance positions
            await self._sync_with_binance_positions()

            # Step 3: Clean up orphan/ghost positions
            await self._cleanup_orphan_positions()

            self.logger.info(f"✅ UNIFIED SYSTEM READY: {len(self._positions)} active positions")

        except Exception as e:
            self.logger.error(f"❌ Failed to initialize unified position system: {e}")
            raise

    async def _load_positions_from_database(self):
        """Load all open positions from database"""
        try:
            self.logger.info("📊 LOADING POSITIONS FROM DATABASE...")

            # Always start fresh from database
            self._positions.clear()

            # Get all open trades from database
            for trade_id, trade_data in self.trade_db.trades.items():
                if trade_data.get('trade_status') == 'OPEN':
                    position = UnifiedPosition(
                        trade_id=trade_id,
                        strategy_name=trade_data.get('strategy_name', 'UNKNOWN'),
                        symbol=trade_data.get('symbol'),
                        side=trade_data.get('side'),
                        entry_price=float(trade_data.get('entry_price', 0)),
                        quantity=float(trade_data.get('quantity', 0)),
                        stop_loss=trade_data.get('stop_loss'),
                        take_profit=trade_data.get('take_profit'),
                        margin_used=float(trade_data.get('margin_used', 0)),
                        leverage=int(trade_data.get('leverage', 1)),
                        status=trade_data.get('trade_status', 'OPEN'),
                        created_at=trade_data.get('created_at', ''),
                        last_updated=trade_data.get('last_updated', '')
                    )

                    self._positions[trade_id] = position
                    self.logger.info(f"📊 LOADED: {trade_id} | {position.symbol} | {position.side}")

            self.logger.info(f"📊 LOADED {len(self._positions)} POSITIONS FROM DATABASE")

        except Exception as e:
            self.logger.error(f"❌ Error loading positions from database: {e}")

    async def _sync_with_binance_positions(self):
        """Sync database positions with actual Binance positions"""
        try:
            if not self.binance_client.is_futures:
                self.logger.info("📊 Not using futures - skipping Binance sync")
                return

            self.logger.info("🔄 SYNCING WITH BINANCE POSITIONS...")

            # Get actual Binance positions
            positions = self.binance_client.client.futures_position_information()
            binance_positions = {}

            for position in positions:
                symbol = position.get('symbol')
                position_amt = float(position.get('positionAmt', 0))

                if abs(position_amt) > 0.001:  # Has actual position
                    binance_positions[symbol] = {
                        'symbol': symbol,
                        'position_amt': position_amt,
                        'entry_price': float(position.get('entryPrice', 0)),
                        'side': 'BUY' if position_amt > 0 else 'SELL',
                        'quantity': abs(position_amt),
                        'unrealized_pnl': float(position.get('unrealizedPnl', 0))
                    }

            self.logger.info(f"🔄 FOUND {len(binance_positions)} BINANCE POSITIONS")
            
            # Log all Binance positions for debugging
            for symbol, pos_data in binance_positions.items():
                self.logger.info(f"📊 BINANCE POSITION: {symbol} | {pos_data['side']} | Qty: {pos_data['quantity']} | Entry: ${pos_data['entry_price']:.4f}")

            # Check for untracked legitimate positions (like ADAUSDT)
            await self._recover_untracked_positions(binance_positions)

            # Update existing positions with Binance data
            positions_to_remove = []

            for trade_id, position in self._positions.items():
                binance_pos = binance_positions.get(position.symbol)

                if binance_pos:
                    # Position exists on Binance - update with actual data
                    position.binance_position_amt = binance_pos['position_amt']

                    # Verify position matches (with tolerance)
                    expected_amt = position.quantity if position.side == 'BUY' else -position.quantity
                    if abs(binance_pos['position_amt'] - expected_amt) > 0.1:
                        self.logger.warning(f"⚠️ POSITION MISMATCH: {trade_id} | DB: {expected_amt} | Binance: {binance_pos['position_amt']}")
                else:
                    # Position doesn't exist on Binance - mark for cleanup
                    self.logger.warning(f"👻 ORPHAN POSITION: {trade_id} | {position.symbol} | No Binance position")
                    positions_to_remove.append(trade_id)

            # Remove orphan positions
            for trade_id in positions_to_remove:
                await self._close_position(trade_id, "ORPHAN_CLEANUP")

        except Exception as e:
            self.logger.error(f"❌ Error syncing with Binance: {e}")

    async def _recover_untracked_positions(self, binance_positions: dict):
        """Recover legitimate positions that exist on Binance but not in database"""
        try:
            tracked_symbols = {pos.symbol for pos in self._positions.values()}
            
            for symbol, binance_pos in binance_positions.items():
                if symbol not in tracked_symbols:
                    self.logger.info(f"🔍 UNTRACKED POSITION DETECTED: {symbol} | {binance_pos['side']} | Qty: {binance_pos['quantity']}")
                    
                    # Check if this might be a legitimate bot position
                    trade_id = await self._attempt_position_recovery(symbol, binance_pos)
                    
                    if trade_id:
                        self.logger.info(f"✅ RECOVERED LEGITIMATE POSITION: {trade_id} | {symbol}")
                    else:
                        self.logger.warning(f"⚠️ UNTRACKED POSITION: {symbol} | Manual position or orphaned trade")

        except Exception as e:
            self.logger.error(f"❌ Error recovering untracked positions: {e}")

    async def _attempt_position_recovery(self, symbol: str, binance_pos: dict) -> str:
        """Attempt to recover a position by finding it in the database or create cross-deployment record"""
        try:
            # First, search database for matching trade
            for trade_id, trade_data in self.trade_db.trades.items():
                if (trade_data.get('trade_status') == 'OPEN' and 
                    trade_data.get('symbol') == symbol and
                    trade_data.get('side') == binance_pos['side']):
                    
                    # Check quantity match with tolerance
                    db_quantity = float(trade_data.get('quantity', 0))
                    if abs(db_quantity - binance_pos['quantity']) < 0.1:
                        
                        # Create unified position from database data
                        position = UnifiedPosition(
                            trade_id=trade_id,
                            strategy_name=trade_data.get('strategy_name', 'RECOVERED'),
                            symbol=symbol,
                            side=binance_pos['side'],
                            entry_price=float(trade_data.get('entry_price', binance_pos['entry_price'])),
                            quantity=binance_pos['quantity'],
                            stop_loss=trade_data.get('stop_loss'),
                            take_profit=trade_data.get('take_profit'),
                            margin_used=float(trade_data.get('margin_used', 0)),
                            leverage=int(trade_data.get('leverage', 1)),
                            status='OPEN',
                            created_at=trade_data.get('created_at', ''),
                            binance_position_amt=binance_pos['position_amt']
                        )
                        
                        self._positions[trade_id] = position
                        
                        self.logger.info(f"✅ POSITION RECOVERED: {trade_id} | {symbol} | Strategy: {position.strategy_name}")
                        return trade_id
            
            # If not found in database, create cross-deployment recovery record
            # This handles legitimate positions from other bot deployments (like Render)
            self.logger.info(f"🔄 CREATING CROSS-DEPLOYMENT RECOVERY RECORD FOR {symbol}")
            
            # Generate recovery trade ID
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            recovery_trade_id = f"RENDER_RECOVERY_{symbol}_{timestamp}"
            
            # Estimate strategy based on symbol
            estimated_strategy = "cross_deployment"
            if "ADA" in symbol:
                estimated_strategy = "render_ada_position"
            elif "BTC" in symbol:
                estimated_strategy = "render_btc_position"
            elif "ETH" in symbol:
                estimated_strategy = "render_eth_position"
            
            # Calculate estimated margin (conservative estimate)
            position_value = binance_pos['entry_price'] * binance_pos['quantity']
            estimated_leverage = 5  # Conservative estimate
            estimated_margin = position_value / estimated_leverage
            
            # Create recovery trade record
            recovery_data = {
                'trade_id': recovery_trade_id,
                'strategy_name': estimated_strategy,
                'symbol': symbol,
                'side': binance_pos['side'],
                'quantity': binance_pos['quantity'],
                'entry_price': binance_pos['entry_price'],
                'trade_status': 'OPEN',
                'position_value_usdt': position_value,
                'leverage': estimated_leverage,
                'margin_used': estimated_margin,
                'created_at': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat(),
                'cross_deployment_recovery': True,
                'recovery_source': 'render_deployment',
                'original_binance_data': binance_pos
            }
            
            # Add to database
            success = self.trade_db.add_trade(recovery_trade_id, recovery_data)
            
            if success:
                # Create unified position
                position = UnifiedPosition(
                    trade_id=recovery_trade_id,
                    strategy_name=estimated_strategy,
                    symbol=symbol,
                    side=binance_pos['side'],
                    entry_price=binance_pos['entry_price'],
                    quantity=binance_pos['quantity'],
                    margin_used=estimated_margin,
                    leverage=estimated_leverage,
                    status='OPEN',
                    created_at=datetime.now().isoformat(),
                    binance_position_amt=binance_pos['position_amt']
                )
                
                self._positions[recovery_trade_id] = position
                
                self.logger.info(f"✅ CROSS-DEPLOYMENT POSITION RECOVERED: {recovery_trade_id} | {symbol} | From Render deployment")
                return recovery_trade_id
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Error attempting position recovery for {symbol}: {e}")
            return None

    async def _cleanup_orphan_positions(self):
        """Clean up positions that don't have corresponding Binance positions"""
        try:
            cleanup_count = 0

            for trade_id, position in list(self._positions.items()):
                if abs(position.binance_position_amt) < 0.001:
                    # No actual Binance position - close this orphan
                    await self._close_position(trade_id, "ORPHAN_CLEANUP")
                    cleanup_count += 1

            if cleanup_count > 0:
                self.logger.info(f"🧹 CLEANED UP {cleanup_count} ORPHAN POSITIONS")

        except Exception as e:
            self.logger.error(f"❌ Error cleaning up orphans: {e}")

    async def _close_position(self, trade_id: str, reason: str):
        """Close a position and update database"""
        try:
            if trade_id not in self._positions:
                return False

            position = self._positions[trade_id]

            # Update database
            self.trade_db.update_trade(trade_id, {
                'trade_status': 'CLOSED',
                'close_reason': reason,
                'close_time': datetime.now().isoformat()
            })

            # Remove from memory
            del self._positions[trade_id]

            self.logger.info(f"✅ POSITION CLOSED: {trade_id} | {position.symbol} | Reason: {reason}")

            # Send notification
            try:
                self.telegram_reporter.report_position_closed({
                    'trade_id': trade_id,
                    'symbol': position.symbol,
                    'side': position.side,
                    'close_reason': reason
                })
            except Exception as e:
                self.logger.warning(f"Failed to send close notification: {e}")

            return True

        except Exception as e:
            self.logger.error(f"❌ Error closing position {trade_id}: {e}")
            return False

    def get_all_positions(self) -> Dict[str, UnifiedPosition]:
        """Get all active positions"""
        return self._positions.copy()

    def get_position_by_strategy(self, strategy_name: str) -> Optional[UnifiedPosition]:
        """Get position for a specific strategy"""
        for position in self._positions.values():
            if position.strategy_name == strategy_name:
                return position
        return None

    def get_position_by_symbol(self, symbol: str) -> Optional[UnifiedPosition]:
        """Get position for a specific symbol"""
        for position in self._positions.values():
            if position.symbol == symbol:
                return position
        return None

    async def add_position(self, trade_data: Dict[str, Any]) -> bool:
        """Add new position to unified system"""
        try:
            trade_id = trade_data['trade_id']

            # Add to database first
            success = self.trade_db.add_trade(trade_id, trade_data)
            if not success:
                return False

            # Add to memory
            position = UnifiedPosition(
                trade_id=trade_id,
                strategy_name=trade_data['strategy_name'],
                symbol=trade_data['symbol'],
                side=trade_data['side'],
                entry_price=float(trade_data['entry_price']),
                quantity=float(trade_data['quantity']),
                stop_loss=trade_data.get('stop_loss'),
                take_profit=trade_data.get('take_profit'),
                margin_used=float(trade_data.get('margin_used', 0)),
                leverage=int(trade_data.get('leverage', 1))
            )

            self._positions[trade_id] = position

            self.logger.info(f"✅ POSITION ADDED: {trade_id} | {position.symbol} | {position.side}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error adding position: {e}")
            return False

    async def refresh_from_database(self):
        """Refresh in-memory positions from database - ensures sync between environments"""
        try:
            self.logger.info("🔄 REFRESHING POSITIONS FROM DATABASE...")

            # Reload database
            self.trade_db._load_database()

            # Reload positions
            await self._load_positions_from_database()

            self.logger.info(f"✅ REFRESHED: {len(self._positions)} ACTIVE POSITIONS")

        except Exception as e:
            self.logger.error(f"❌ Error refreshing from database: {e}")

    def get_position_count(self) -> int:
        """Get count of active positions"""
        return len(self._positions)

    def get_positions_summary(self) -> List[Dict[str, Any]]:
        """Get summary of all positions for dashboard"""
        summary = []

        for position in self._positions.values():
            summary.append({
                'trade_id': position.trade_id,
                'strategy_name': position.strategy_name,
                'symbol': position.symbol,
                'side': position.side,
                'entry_price': position.entry_price,
                'quantity': position.quantity,
                'margin_used': position.margin_used,
                'leverage': position.leverage,
                'status': position.status,
                'created_at': position.created_at,
                'has_binance_position': abs(position.binance_position_amt) > 0.001
            })

        return summary
    def get_unified_positions(self):
        """Get unified view of all positions from all sources"""
        try:
            # Handle different event loop scenarios
            try:
                loop = asyncio.get_running_loop()
                # If we're in an async context, create a task
                return asyncio.run_coroutine_threadsafe(
                    self._get_unified_positions_async(), loop
                ).result(timeout=10)
            except RuntimeError:
                # No running loop, create new one
                return asyncio.run(self._get_unified_positions_async())
        except Exception as e:
            self.logger.error(f"Error getting unified positions: {e}")
            return []