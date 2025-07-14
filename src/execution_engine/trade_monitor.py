
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
                            # Create unique ID for this ghost trade
                            ghost_id = f"{strategy_name}_{symbol}_{abs(position_amt)}_{datetime.now().strftime('%H%M%S')}"
                            
                            # Check if we already detected this ghost trade (use simpler check)
                            existing_ghost = None
                            for gid, ghost in self.ghost_trades.items():
                                if (gid.startswith(f"{strategy_name}_{symbol}_") and 
                                    abs(ghost.quantity - abs(position_amt)) < 0.001):
                                    existing_ghost = gid
                                    break
                            
                            if not existing_ghost:
                                side = 'BUY' if position_amt > 0 else 'SELL'
                                
                                ghost_trade = GhostTrade(
                                    symbol=symbol,
                                    side=side,
                                    quantity=abs(position_amt),
                                    detected_at=datetime.now(),
                                    cycles_remaining=2,
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
            
            if ghost_trade.cycles_remaining <= 0:
                # Clear ghost trade from internal tracking ONLY - DO NOT close on Binance
                # Ghost trades are manual positions that bot should never interfere with
                ghosts_to_remove.append(ghost_id)
                
                # Extract strategy name from ghost_id
                strategy_name = ghost_id.split('_')[0]
                
                # Log and notify only if not already notified
                if not ghost_trade.clearing_notified:
                    self.logger.info(f"🧹 GHOST TRADE CLEARED | {strategy_name} | Removed from tracking only - Position remains on Binance")
                    self.telegram_reporter.report_ghost_trade_cleared(
                        strategy_name=strategy_name,
                        symbol=ghost_trade.symbol
                    )
                    ghost_trade.clearing_notified = True
        
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
