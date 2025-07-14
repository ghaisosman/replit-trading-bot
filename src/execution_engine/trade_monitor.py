
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
            self._check_orphan_trades()
            self._check_ghost_trades()
            self._process_cycle_countdown()
        except Exception as e:
            self.logger.error(f"Error checking trade anomalies: {e}")
            
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
            # Check each registered strategy symbol
            for strategy_name, symbol in self.strategy_symbols.items():
                # Get open positions from Binance
                binance_positions = self._get_binance_positions(symbol)
                
                # Check for positions that bot doesn't know about
                for binance_pos in binance_positions:
                    position_amt = float(binance_pos.get('positionAmt', 0))
                    if position_amt != 0:  # Position exists on Binance
                        
                        # Check if this position matches a known bot position
                        bot_position = self.order_manager.active_positions.get(strategy_name)
                        is_bot_position = False
                        
                        if bot_position:
                            # Compare position details to see if this is the bot's position
                            bot_side_multiplier = 1 if bot_position.side == 'BUY' else -1
                            expected_position_amt = bot_position.quantity * bot_side_multiplier
                            
                            # Allow small tolerance for quantity differences due to rounding
                            if abs(position_amt - expected_position_amt) < 0.001:
                                is_bot_position = True
                        
                        # If this is not the bot's position, it's a ghost trade
                        if not is_bot_position:
                            # Check if we already have a ghost trade for this symbol and strategy
                            existing_ghost_id = None
                            for gid, ghost in self.ghost_trades.items():
                                # Extract strategy and symbol from ghost_id
                                parts = gid.split('_')
                                if len(parts) >= 2:
                                    ghost_strategy = '_'.join(parts[:-3]) if len(parts) > 3 else parts[0]
                                    ghost_symbol = parts[-3] if len(parts) > 3 else parts[1]
                                    
                                    if (ghost_strategy == strategy_name and 
                                        ghost_symbol == symbol and
                                        abs(ghost.quantity - abs(position_amt)) < 0.001):
                                        existing_ghost_id = gid
                                        break
                            
                            # Only create new ghost trade if we don't already have one
                            if not existing_ghost_id:
                                side = 'BUY' if position_amt > 0 else 'SELL'
                                # Use timestamp to ensure uniqueness while keeping strategy name intact
                                timestamp = int(datetime.now().timestamp())
                                ghost_id = f"{strategy_name}_{symbol}_{abs(position_amt):.6f}_{timestamp}"
                                
                                ghost_trade = GhostTrade(
                                    symbol=symbol,
                                    side=side,
                                    quantity=abs(position_amt),
                                    detected_at=datetime.now(),
                                    cycles_remaining=20,  # Increased from 2 to 20 cycles (40 seconds)
                                    detection_notified=True,
                                    clearing_notified=False
                                )
                                self.ghost_trades[ghost_id] = ghost_trade
                                
                                # Log and notify
                                self.logger.warning(f"👻 GHOST TRADE DETECTED | {strategy_name} | {symbol} | Manual position found")
                                self.telegram_reporter.report_ghost_trade_detected(
                                    strategy_name=strategy_name,
                                    symbol=symbol,
                                    side=side,
                                    quantity=abs(position_amt)
                                )
                            
        except Exception as e:
            self.logger.error(f"Error checking ghost trades: {e}")
            
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
                # Extract strategy name from ghost_id (everything before the last two underscores)
                parts = ghost_id.split('_')
                if len(parts) >= 3:
                    strategy_name = '_'.join(parts[:-2])  # Join all parts except symbol and quantity
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
