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
    last_notification_time: Optional[datetime] = None
    notification_cooldown_minutes: int = 60  # Don't re-notify for 60 minutes

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
        
        # Flag to prevent notifications during initial startup scan
        self.startup_scan_complete = False

    def register_strategy(self, strategy_name: str, symbol: str):
        """Register a strategy and its symbol for monitoring"""
        self.strategy_symbols[strategy_name] = symbol

    def check_for_anomalies(self, suppress_notifications: bool = False) -> None:
        """Check for orphan and ghost trades"""
        try:
            scan_type = "STARTUP SCAN" if not self.startup_scan_complete else "ANOMALY CHECK"
            self.logger.debug(f"🔍 {scan_type}: Starting trade anomaly detection")
            self.logger.debug(f"🔍 {scan_type}: Registered strategies: {list(self.strategy_symbols.keys())}")
            self.logger.debug(f"🔍 {scan_type}: Active bot positions: {list(self.order_manager.active_positions.keys())}")
            self.logger.debug(f"🔍 {scan_type}: Current orphan trades: {len(self.orphan_trades)}")
            self.logger.debug(f"🔍 {scan_type}: Current ghost trades: {len(self.ghost_trades)}")

            self._check_orphan_trades(suppress_notifications)
            self._check_ghost_trades(suppress_notifications)
            self._process_cycle_countdown(suppress_notifications)
            
            # Mark startup scan as complete only if not suppressed
            if not self.startup_scan_complete and not suppress_notifications:
                self.startup_scan_complete = True
                self.logger.info("🔍 STARTUP SCAN: Initial anomaly scan completed")
            elif not self.startup_scan_complete and suppress_notifications:
                self.logger.info("🔍 STARTUP SCAN: Initial anomaly scan completed (notifications suppressed)")

            self.logger.debug(f"🔍 {scan_type}: Completed anomaly detection")
        except Exception as e:
            self.logger.error(f"Error checking trade anomalies: {e}")
            import traceback
            self.logger.error(f"Anomaly check error traceback: {traceback.format_exc()}")

    def _check_orphan_trades(self, suppress_notifications: bool = False) -> None:
        """Check for orphan trades (bot opened, manually closed)"""
        try:
            # Skip orphan trade detection during startup scan to prevent false positives
            if not self.startup_scan_complete:
                self.logger.debug("🔍 ORPHAN CHECK: Skipping during startup scan")
                return

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
                        detection_notified=not suppress_notifications,
                        clearing_notified=False
                    )
                    self.orphan_trades[strategy_name] = orphan_trade

                    # Log and notify only if not suppressed
                    if not suppress_notifications:
                        self.logger.warning(f"🔍 ORPHAN TRADE DETECTED | {strategy_name} | {symbol} | Position closed manually")
                        self.telegram_reporter.report_orphan_trade_detected(
                            strategy_name=strategy_name,
                            symbol=symbol,
                            side=position.side,
                            entry_price=position.entry_price
                        )
                    else:
                        self.logger.info(f"🔍 ORPHAN POSITION NOTED (STARTUP) | {strategy_name} | {symbol} | Position tracking")

        except Exception as e:
            self.logger.error(f"Error checking orphan trades: {e}")

    def _check_ghost_trades(self, suppress_notifications: bool = False) -> None:
        """Check for ghost trades (manually opened, not by bot)"""
        try:
            # Get ALL open positions from Binance first
            all_positions = []
            try:
                if self.binance_client.is_futures:
                    account_info = self.binance_client.client.futures_account()
                    all_positions = account_info.get('positions', [])
                    self.logger.debug(f"🔍 GHOST CHECK: Found {len(all_positions)} total positions on Binance")

                    # Debug: Log all positions with their amounts
                    for pos in all_positions:
                        pos_amt = float(pos.get('positionAmt', 0))
                        if abs(pos_amt) > 0:
                            self.logger.debug(f"🔍 GHOST CHECK: Position found - {pos.get('symbol')}: {pos_amt}")

            except Exception as e:
                self.logger.error(f"Error getting all Binance positions: {e}")
                return

            # Filter for positions with non-zero amounts (lower threshold)
            active_positions = [pos for pos in all_positions if abs(float(pos.get('positionAmt', 0))) > 0.00001]
            self.logger.debug(f"🔍 GHOST CHECK: {len(active_positions)} active positions found")

            # Log bot's current positions for comparison
            self.logger.debug(f"🔍 GHOST CHECK: Bot has {len(self.order_manager.active_positions)} active positions:")
            for strategy_name, bot_position in self.order_manager.active_positions.items():
                side_multiplier = 1 if bot_position.side == 'BUY' else -1
                expected_amt = bot_position.quantity * side_multiplier
                self.logger.debug(f"  • {strategy_name}: {bot_position.symbol} = {expected_amt} ({bot_position.side})")

            # Check each active position
            for binance_pos in active_positions:
                symbol = binance_pos.get('symbol')
                position_amt = float(binance_pos.get('positionAmt', 0))

                self.logger.debug(f"🔍 GHOST CHECK: Analyzing position {symbol}: {position_amt}")

                # Check if this position matches ANY known bot position
                is_bot_position = False
                matching_strategy = None

                for strategy_name, bot_position in self.order_manager.active_positions.items():
                    if bot_position.symbol == symbol:
                        # Compare position details
                        bot_side_multiplier = 1 if bot_position.side == 'BUY' else -1
                        expected_position_amt = bot_position.quantity * bot_side_multiplier

                        self.logger.debug(f"🔍 GHOST CHECK: Comparing {symbol} - Binance: {position_amt}, Bot expects: {expected_position_amt}")

                        # Allow small tolerance for quantity differences due to rounding
                        if abs(position_amt - expected_position_amt) < 0.1:  # Increased tolerance
                            is_bot_position = True
                            matching_strategy = strategy_name
                            self.logger.debug(f"🔍 GHOST CHECK: Position {symbol} matches bot strategy {strategy_name}")
                            break
                        else:
                            self.logger.debug(f"🔍 GHOST CHECK: Position {symbol} differs from bot - difference: {abs(position_amt - expected_position_amt)}")

                # If this is not a bot position, it's a ghost trade
                if not is_bot_position:
                    self.logger.debug(f"🔍 GHOST CHECK: Found manual position {symbol}: {position_amt}")

                    # Find which strategy should monitor this symbol
                    monitoring_strategy = None
                    for strategy_name, strategy_symbol in self.strategy_symbols.items():
                        if strategy_symbol == symbol:
                            monitoring_strategy = strategy_name
                            break

                    # If no strategy monitors this symbol, create a generic monitoring name
                    if not monitoring_strategy:
                        monitoring_strategy = f"manual_{symbol.lower()}"
                        self.logger.debug(f"🔍 GHOST CHECK: No strategy monitors {symbol}, using generic name: {monitoring_strategy}")

                    # Check if we already have a ghost trade for this symbol
                    existing_ghost_found = False
                    existing_ghost_id = None
                    for ghost_id, ghost_trade in self.ghost_trades.items():
                        if ghost_trade.symbol == symbol:
                            existing_ghost_found = True
                            existing_ghost_id = ghost_id
                            self.logger.debug(f"🔍 GHOST CHECK: Already tracking ghost trade for {symbol} with ID {ghost_id}")
                            break

                    # Only create new ghost trade if we don't already have one for this symbol
                    if not existing_ghost_found:
                        side = 'LONG' if position_amt > 0 else 'SHORT'
                        # Simple ghost ID using just strategy and symbol to prevent duplicates
                        ghost_id = f"{monitoring_strategy}_{symbol}"

                        ghost_trade = GhostTrade(
                            symbol=symbol,
                            side=side,
                            quantity=abs(position_amt),
                            detected_at=datetime.now(),
                            cycles_remaining=5,  # 5 cycles before clearing
                            detection_notified=False,  # Start as False, will be set to True if notification sent
                            clearing_notified=False,
                            last_notification_time=None,  # Will be set when notification is sent
                            notification_cooldown_minutes=60
                        )
                        self.ghost_trades[ghost_id] = ghost_trade

                        # Get current price for USDT value calculation
                        try:
                            ticker = self.binance_client.get_symbol_ticker(symbol)
                            current_price = float(ticker['price']) if ticker else None
                        except:
                            current_price = None

                        # Log detection
                        usdt_value = current_price * abs(position_amt) if current_price else 0
                        
                        # Only send notifications if:
                        # 1. Not suppressed AND
                        # 2. Startup scan is complete AND  
                        # 3. This is a truly new detection (not a duplicate)
                        should_notify = (not suppress_notifications and 
                                       self.startup_scan_complete and 
                                       not ghost_trade.detection_notified)
                        
                        if should_notify:
                            self.logger.warning(f"👻 NEW GHOST TRADE DETECTED | {monitoring_strategy} | {symbol} | Manual position found | Qty: {abs(position_amt):.6f} | Value: ${usdt_value:.2f} USDT")
                            
                            # Send Telegram notification
                            self.telegram_reporter.report_ghost_trade_detected(
                                strategy_name=monitoring_strategy,
                                symbol=symbol,
                                side=side,
                                quantity=abs(position_amt),
                                current_price=current_price
                            )
                            
                            # Mark as notified to prevent re-notification
                            ghost_trade.detection_notified = True
                            ghost_trade.last_notification_time = datetime.now()
                        else:
                            scan_type = "STARTUP SCAN" if not self.startup_scan_complete else "SUPPRESSED CHECK"
                            self.logger.info(f"👻 POSITION NOTED ({scan_type}) | {monitoring_strategy} | {symbol} | Manual position tracked | Qty: {abs(position_amt):.6f} | Value: ${usdt_value:.2f} USDT")
                    else:
                        # Update the existing ghost trade but don't re-notify
                        if existing_ghost_id:
                            existing_ghost = self.ghost_trades[existing_ghost_id]
                            # Update quantity if it has changed significantly
                            if abs(existing_ghost.quantity - abs(position_amt)) > 0.1:
                                self.logger.debug(f"🔍 GHOST CHECK: Updating ghost trade quantity for {symbol} from {existing_ghost.quantity:.6f} to {abs(position_amt):.6f}")
                                existing_ghost.quantity = abs(position_amt)
                                existing_ghost.side = 'LONG' if position_amt > 0 else 'SHORT'
                            
                        self.logger.debug(f"🔍 GHOST CHECK: Ghost trade already exists for {symbol}, skipping duplicate detection")
                else:
                    self.logger.debug(f"🔍 GHOST CHECK: Position {symbol} is a known bot position")

        except Exception as e:
            self.logger.error(f"Error checking ghost trades: {e}")
            import traceback
            self.logger.error(f"Ghost trade check error traceback: {traceback.format_exc()}")

    def _process_cycle_countdown(self, suppress_notifications: bool = False) -> None:
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
            # Only decrement cycles if not suppressed (to prevent clearing during startup)
            if not suppress_notifications:
                ghost_trade.cycles_remaining -= 1

            # Check if position still exists on Binance before clearing
            binance_positions = self._get_binance_positions(ghost_trade.symbol)
            position_still_exists = False

            for binance_pos in binance_positions:
                position_amt = float(binance_pos.get('positionAmt', 0))
                if abs(position_amt) > 0.001:  # Position still exists
                    position_still_exists = True
                    break

            # Only clear from tracking if position no longer exists OR cycles expired (and not suppressed)
            should_clear = ((ghost_trade.cycles_remaining <= 0 and not suppress_notifications) or 
                          not position_still_exists)
            
            if should_clear:
                # Extract strategy name from simplified ghost_id (strategy_symbol format)
                parts = ghost_id.split('_')
                if len(parts) >= 2:
                    strategy_name = '_'.join(parts[:-1])  # All parts except the last (symbol)
                else:
                    strategy_name = parts[0]

                # Log and notify only if not already notified and not suppressed
                if not ghost_trade.clearing_notified and not suppress_notifications:
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