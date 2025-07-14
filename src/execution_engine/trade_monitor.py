
import logging
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass
from src.binance_client.client import BinanceClientWrapper
from src.execution_engine.order_manager import OrderManager, Position
from src.reporting.telegram_reporter import TelegramReporter

@dataclass
class OrphanTrade:
    """Represents a trade opened by bot but closed manually"""
    position: Position
    detected_at: datetime
    cycles_remaining: int = 2
    detection_notified: bool = False
    clearing_notified: bool = False

@dataclass
class GhostTrade:
    """Represents a trade opened manually but not by bot"""
    symbol: str
    side: str
    quantity: float
    detected_at: datetime
    cycles_remaining: int = 2
    binance_order_id: Optional[int] = None
    detection_notified: bool = False
    clearing_notified: bool = False

class TradeMonitor:
    """Monitors for orphan and ghost trades"""
    
    def __init__(self, binance_client: BinanceClientWrapper, order_manager: OrderManager, telegram_reporter: TelegramReporter):
        self.binance_client = binance_client
        self.order_manager = order_manager
        self.telegram_reporter = telegram_reporter
        self.logger = logging.getLogger(__name__)
        
        # Track detected anomalies
        self.orphan_trades: Dict[str, OrphanTrade] = {}  # strategy_name -> OrphanTrade
        self.ghost_trades: Dict[str, GhostTrade] = {}    # unique_id -> GhostTrade
        
        # Track strategy symbols for monitoring
        self.strategy_symbols: Dict[str, str] = {}  # strategy_name -> symbol
        
    def register_strategy(self, strategy_name: str, symbol: str):
        """Register a strategy and its symbol for monitoring"""
        self.strategy_symbols[strategy_name] = symbol
        
    def check_for_anomalies(self) -> None:
        """Check for orphan and ghost trades"""
        try:
            self.logger.info(f"🔍 ANOMALY CHECK: Starting trade anomaly detection")
            self.logger.info(f"🔍 ANOMALY CHECK: Registered strategies: {list(self.strategy_symbols.keys())}")
            self.logger.info(f"🔍 ANOMALY CHECK: Active bot positions: {list(self.order_manager.active_positions.keys())}")
            self.logger.info(f"🔍 ANOMALY CHECK: Current orphan trades: {len(self.orphan_trades)}")
            self.logger.info(f"🔍 ANOMALY CHECK: Current ghost trades: {len(self.ghost_trades)}")
            
            self._check_orphan_trades()
            self._check_ghost_trades()
            self._process_cycle_countdown()
            
            self.logger.info(f"🔍 ANOMALY CHECK: Completed anomaly detection")
        except Exception as e:
            self.logger.error(f"Error checking trade anomalies: {e}")
            import traceback
            self.logger.error(f"Anomaly check error traceback: {traceback.format_exc()}")
            
    def _check_orphan_trades(self) -> None:
        """Check for orphan trades (bot opened, manually closed)"""
        try:
            # Get bot's active positions
            bot_positions = self.order_manager.get_active_positions()
            
            # Check each bot position against Binance
            for strategy_name, position in bot_positions.items():
                symbol = position.symbol
                
                # Get open positions from Binance
                binance_positions = self._get_binance_positions(symbol)
                
                # Check if bot position exists on Binance
                position_exists = False
                for binance_pos in binance_positions:
                    if (binance_pos.get('symbol') == symbol and 
                        float(binance_pos.get('positionAmt', 0)) != 0):
                        position_exists = True
                        break
                
                # If bot thinks position is open but Binance shows it's closed
                if not position_exists and strategy_name not in self.orphan_trades:
                    orphan_trade = OrphanTrade(
                        position=position,
                        detected_at=datetime.now(),
                        cycles_remaining=2,
                        detection_notified=True,
                        clearing_notified=False
                    )
                    self.orphan_trades[strategy_name] = orphan_trade
                    
                    # Log and notify
                    self.logger.warning(f"🔍 ORPHAN TRADE DETECTED | {strategy_name} | {symbol} | Position closed manually")
                    self.telegram_reporter.report_orphan_trade_detected(
                        strategy_name=strategy_name,
                        symbol=symbol,
                        side=position.side,
                        entry_price=position.entry_price
                    )
                    
        except Exception as e:
            self.logger.error(f"Error checking orphan trades: {e}")
            
    def _check_ghost_trades(self) -> None:
        """Check for ghost trades (manually opened, not by bot)"""
        try:
            # Get ALL open positions from Binance first
            all_positions = []
            try:
                if self.binance_client.is_futures:
                    account_info = self.binance_client.client.futures_account()
                    all_positions = account_info.get('positions', [])
                    self.logger.info(f"🔍 GHOST CHECK: Found {len(all_positions)} total positions on Binance")
            except Exception as e:
                self.logger.error(f"Error getting all Binance positions: {e}")
                return
            
            # Filter for positions with non-zero amounts
            active_positions = [pos for pos in all_positions if abs(float(pos.get('positionAmt', 0))) > 0.001]
            self.logger.info(f"🔍 GHOST CHECK: {len(active_positions)} active positions found")
            
            # Check each active position
            for binance_pos in active_positions:
                symbol = binance_pos.get('symbol')
                position_amt = float(binance_pos.get('positionAmt', 0))
                
                self.logger.info(f"🔍 GHOST CHECK: Checking position {symbol}: {position_amt}")
                
                # Check if this position matches ANY known bot position
                is_bot_position = False
                matching_strategy = None
                
                for strategy_name, bot_position in self.order_manager.active_positions.items():
                    if bot_position.symbol == symbol:
                        # Compare position details
                        bot_side_multiplier = 1 if bot_position.side == 'BUY' else -1
                        expected_position_amt = bot_position.quantity * bot_side_multiplier
                        
                        # Allow small tolerance for quantity differences due to rounding
                        if abs(position_amt - expected_position_amt) < 0.01:  # Increased tolerance
                            is_bot_position = True
                            matching_strategy = strategy_name
                            self.logger.info(f"🔍 GHOST CHECK: Position {symbol} matches bot strategy {strategy_name}")
                            break
                
                # If this is not a bot position, it's a ghost trade
                if not is_bot_position:
                    self.logger.warning(f"🔍 GHOST CHECK: Found manual position {symbol}: {position_amt}")
                    
                    # Find which strategy should monitor this symbol
                    monitoring_strategy = None
                    for strategy_name, strategy_symbol in self.strategy_symbols.items():
                        if strategy_symbol == symbol:
                            monitoring_strategy = strategy_name
                            break
                    
                    # If no strategy monitors this symbol, use a generic name
                    if not monitoring_strategy:
                        monitoring_strategy = f"manual_{symbol.lower()}"
                    
                    # Check if we already have a ghost trade for this position
                    existing_ghost_found = False
                    for gid, ghost in self.ghost_trades.items():
                        if ghost.symbol == symbol and abs(ghost.quantity - abs(position_amt)) < 0.01:
                            existing_ghost_found = True
                            self.logger.info(f"🔍 GHOST CHECK: Already tracking ghost trade for {symbol}")
                            break
                    
                    # Only create new ghost trade if we don't already have one for this position
                    if not existing_ghost_found:
                        side = 'BUY' if position_amt > 0 else 'SELL'
                        timestamp = int(datetime.now().timestamp())
                        ghost_id = f"{monitoring_strategy}_{symbol}_{abs(position_amt):.6f}_{timestamp}"
                        
                        ghost_trade = GhostTrade(
                            symbol=symbol,
                            side=side,
                            quantity=abs(position_amt),
                            detected_at=datetime.now(),
                            cycles_remaining=20,  # 20 cycles (40 seconds)
                            detection_notified=True,
                            clearing_notified=False
                        )
                        self.ghost_trades[ghost_id] = ghost_trade
                        
                        # Get current price for USDT value calculation
                        try:
                            from src.data_fetcher.price_fetcher import PriceFetcher
                            price_fetcher = PriceFetcher(self.binance_client)
                            current_price = price_fetcher.get_current_price(symbol)
                        except:
                            current_price = None
                        
                        # Log and notify
                        usdt_value = current_price * abs(position_amt) if current_price else 0
                        self.logger.warning(f"👻 GHOST TRADE DETECTED | {monitoring_strategy} | {symbol} | Manual position found | Qty: {abs(position_amt):.6f} | Value: ${usdt_value:.2f} USDT")
                        self.telegram_reporter.report_ghost_trade_detected(
                            strategy_name=monitoring_strategy,
                            symbol=symbol,
                            side=side,
                            quantity=abs(position_amt),
                            current_price=current_price
                        )
                        
        except Exception as e:
            self.logger.error(f"Error checking ghost trades: {e}")
            import traceback
            self.logger.error(f"Ghost trade check error traceback: {traceback.format_exc()}")
            
    def _process_cycle_countdown(self) -> None:
        """Process countdown for orphan and ghost trades"""
        # Process orphan trades
        orphans_to_remove = []
        for strategy_name, orphan_trade in self.orphan_trades.items():
            orphan_trade.cycles_remaining -= 1
            
            if orphan_trade.cycles_remaining <= 0:
                # Clear orphan trade
                self.order_manager.clear_orphan_position(strategy_name)
                orphans_to_remove.append(strategy_name)
                
                # Log and notify only if not already notified
                if not orphan_trade.clearing_notified:
                    self.logger.info(f"🧹 ORPHAN TRADE CLEARED | {strategy_name} | Strategy can trade again")
                    self.telegram_reporter.report_orphan_trade_cleared(
                        strategy_name=strategy_name,
                        symbol=orphan_trade.position.symbol
                    )
                    orphan_trade.clearing_notified = True
        
        # Remove cleared orphan trades
        for strategy_name in orphans_to_remove:
            del self.orphan_trades[strategy_name]
            
        # Process ghost trades - NEVER close them on Binance, only clear from internal tracking
        ghosts_to_remove = []
        for ghost_id, ghost_trade in self.ghost_trades.items():
            ghost_trade.cycles_remaining -= 1
            
            # Check if position still exists on Binance before clearing
            binance_positions = self._get_binance_positions(ghost_trade.symbol)
            position_still_exists = False
            
            for binance_pos in binance_positions:
                position_amt = float(binance_pos.get('positionAmt', 0))
                if abs(position_amt) > 0.001:  # Position still exists
                    position_still_exists = True
                    break
            
            # Only clear from tracking if position no longer exists OR cycles expired
            if ghost_trade.cycles_remaining <= 0 or not position_still_exists:
                # Extract strategy name from ghost_id (everything before the last three underscores)
                parts = ghost_id.split('_')
                if len(parts) >= 4:
                    strategy_name = '_'.join(parts[:-3])  # Join all parts except symbol, quantity, and timestamp
                else:
                    strategy_name = parts[0]
                
                # Log and notify only if not already notified
                if not ghost_trade.clearing_notified:
                    if position_still_exists:
                        self.logger.info(f"🧹 GHOST TRADE CLEARED | {strategy_name} | Timeout - Position remains on Binance")
                    else:
                        self.logger.info(f"🧹 GHOST TRADE CLEARED | {strategy_name} | Position closed manually")
                    
                    self.telegram_reporter.report_ghost_trade_cleared(
                        strategy_name=strategy_name,
                        symbol=ghost_trade.symbol
                    )
                    ghost_trade.clearing_notified = True
                
                ghosts_to_remove.append(ghost_id)
        
        # Remove cleared ghost trades from internal tracking only
        for ghost_id in ghosts_to_remove:
            del self.ghost_trades[ghost_id]
            
    def _get_binance_positions(self, symbol: str) -> List[Dict]:
        """Get positions from Binance for a specific symbol"""
        try:
            if self.binance_client.is_futures:
                account_info = self.binance_client.client.futures_account()
                positions = account_info.get('positions', [])
                return [pos for pos in positions if pos.get('symbol') == symbol]
            else:
                # For spot trading, we'd need to check balances
                return []
        except Exception as e:
            self.logger.error(f"Error getting Binance positions for {symbol}: {e}")
            return []
            
    def has_blocking_anomaly(self, strategy_name: str) -> bool:
        """Check if strategy has blocking anomaly that prevents new trades"""
        return (strategy_name in self.orphan_trades or 
                any(ghost_id.startswith(f"{strategy_name}_") for ghost_id in self.ghost_trades))
                
    def get_anomaly_status(self, strategy_name: str) -> Optional[str]:
        """Get anomaly status for a strategy"""
        if strategy_name in self.orphan_trades:
            cycles = self.orphan_trades[strategy_name].cycles_remaining
            return f"ORPHAN ({cycles} cycles remaining)"
        
        for ghost_id, ghost_trade in self.ghost_trades.items():
            if ghost_id.startswith(f"{strategy_name}_"):
                return f"GHOST ({ghost_trade.cycles_remaining} cycles remaining)"
                
        return None
