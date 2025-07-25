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

    def __init__(self, binance_client: BinanceClientWrapper, order_manager: OrderManager, 
                 telegram_reporter: TelegramReporter):
        self.binance_client = binance_client
        self.order_manager = order_manager
        self.telegram_reporter = telegram_reporter
        self.logger = logging.getLogger(__name__)

        # Tracking dictionaries for anomalies with size limits
        self.orphan_trades: Dict[str, OrphanTrade] = {}
        self.ghost_trades: Dict[str, GhostTrade] = {}
        self.recently_cleared_ghosts: Dict[str, datetime] = {}
        self.recent_bot_trades: Dict[str, datetime] = {}
        self.ghost_notification_times: Dict[str, datetime] = {}
        self.notified_ghost_positions: Dict[str, datetime] = {}
        self.strategy_symbols: Dict[str, str] = {}

        # Memory management limits
        self.max_tracking_items = 1000  # Maximum items per dictionary
        self.memory_cleanup_interval = 300  # Cleanup every 5 minutes
        self.last_memory_cleanup = datetime.now()

        # Configuration
        self.ghost_detection_delay_seconds = 60  # 60 second delay after bot trades for better confirmation
        self.startup_scan_complete = False

        # Track notified ghosts to prevent repeated notifications
        self.notified_ghost_positions: Dict[str, datetime] = {}  # symbol -> last_notification_time

        # Track ghost trade fingerprints to prevent re-detection of same trades
        self.ghost_trade_fingerprints: Dict[str, datetime] = {}  # fingerprint -> clear_time

        # Track recent bot trades to prevent immediate ghost detection
        self.recent_bot_trades: Dict[str, datetime] = {}  # symbol -> trade_timestamp

        # Memory management limits to prevent leaks
        self.max_ghost_trades = 100
        self.max_recently_cleared = 50
        self.max_notified_positions = 50
        self.max_fingerprints = 200
        self.max_recent_bot_trades = 20

        # Load persistent ghost fingerprints to survive bot restarts
        self._load_persistent_ghost_fingerprints()

    def register_strategy(self, strategy_name: str, symbol: str):
        """Register a strategy and its symbol for monitoring"""
        self.strategy_symbols[strategy_name] = symbol

    def register_bot_trade(self, symbol: str):
        """Register that the bot just placed a trade on this symbol"""
        self.recent_bot_trades[symbol] = datetime.now()
        self.logger.info(f"🔍 BOT TRADE REGISTERED | {symbol} | Ghost detection paused for {self.ghost_detection_delay_seconds} seconds")

        # Also clear any existing ghost trade for this symbol since bot just placed a trade
        ghosts_to_clear = []
        for ghost_id, ghost_trade in self.ghost_trades.items():
            if ghost_trade.symbol == symbol:
                ghosts_to_clear.append(ghost_id)

        for ghost_id in ghosts_to_clear:
            del self.ghost_trades[ghost_id]
            self.logger.info(f"🔍 GHOST TRADE CLEARED | {symbol} | Removed due to bot trade placement")

    def _is_ghost_detection_paused(self, symbol: str) -> bool:
        """Check if ghost detection should be paused for this symbol due to recent bot trade"""
        if symbol not in self.recent_bot_trades:
            return False

        time_since_trade = datetime.now() - self.recent_bot_trades[symbol]
        is_paused = time_since_trade.total_seconds() < self.ghost_detection_delay_seconds

        if is_paused:
            remaining_seconds = self.ghost_detection_delay_seconds - time_since_trade.total_seconds()
            self.logger.debug(f"🔍 GHOST DETECTION PAUSED | {symbol} | {remaining_seconds:.1f}s remaining")

        return is_paused

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
            self._cleanup_recently_cleared_ghosts()

            # Mark startup scan as complete after first run, regardless of suppression
            if not self.startup_scan_complete:
                self.startup_scan_complete = True
                if suppress_notifications:
                    self.logger.info("🔍 STARTUP SCAN: Initial anomaly scan completed (notifications suppressed)")
                else:
                    self.logger.info("🔍 STARTUP SCAN: Initial anomaly scan completed")

            self.logger.debug(f"🔍 {scan_type}: Completed anomaly detection")
        except Exception as e:
            self.logger.error(f"Error checking trade anomalies: {e}")
            import traceback
            self.logger.error(f"Anomaly check error traceback: {traceback.format_exc()}")

    def _check_orphan_trades(self, suppress_notifications: bool = False) -> None:
        """Check for orphan trades (bot opened, manually closed)"""
        try:
            # Skip orphan detection only during production startup (when notifications aren't suppressed)
            # This allows testing during startup when suppress_notifications=True
            if not self.startup_scan_complete and not suppress_notifications:
                self.logger.debug("🔍 ORPHAN CHECK: Skipping during startup scan (production mode)")
                return

            # Get bot's active positions
            bot_positions = self.order_manager.get_active_positions()

            # Check each bot position against Binance
            for strategy_name, position in bot_positions.items():
                symbol = position.symbol

                # Enhanced logging for RSI strategy
                if 'rsi' in strategy_name.lower():
                    self.logger.info(f"🔍 RSI ORPHAN CHECK START: {strategy_name} | {symbol} | "
                                   f"Bot position: {position.quantity}")

                # Get open positions from Binance
                binance_positions = self._get_binance_positions(symbol)

                # Enhanced logging for RSI strategy  
                if 'rsi' in strategy_name.lower():
                    self.logger.info(f"🔍 RSI ORPHAN CHECK: Found {len(binance_positions)} Binance positions for {symbol}")

                # Find matching Binance position
                binance_position = None
                for pos in binance_positions:
                    pos_amt = float(pos['positionAmt'])
                    if pos['symbol'] == symbol and abs(pos_amt) > 0.001:  # Use absolute value and tolerance
                        binance_position = pos
                        if 'rsi' in strategy_name.lower():
                            self.logger.info(f"🔍 RSI ORPHAN CHECK: Found matching Binance position: {pos_amt}")
                        break

                # Enhanced logging for RSI strategy
                if 'rsi' in strategy_name.lower():
                    self.logger.info(f"🔍 RSI ORPHAN CHECK: Binance position found: {binance_position is not None}")

                # Check if orphan (bot has position but Binance doesn't)
                if binance_position is None:
                    # This is an orphan trade
                    orphan_id = f"{strategy_name}_{symbol}"

                    if 'rsi' in strategy_name.lower():
                        self.logger.info(f"🔍 RSI ORPHAN DETECTED: Creating orphan trade {orphan_id}")

                    if orphan_id not in self.orphan_trades:
                        orphan_trade = OrphanTrade(
                            position=position,
                            detected_at=datetime.now(),
                            cycles_remaining=2
                        )

                        self.orphan_trades[orphan_id] = orphan_trade

                        if 'rsi' in strategy_name.lower():
                            self.logger.info(f"🔍 RSI ORPHAN SUCCESS: Added {orphan_id} to orphan_trades")

                        # Send notification if not suppressed
                        if not suppress_notifications and self.startup_scan_complete:
                            self.logger.warning(f"👻 ORPHAN TRADE DETECTED | {strategy_name} | {symbol} | "
                                              f"Bot position exists but not on Binance")
                            self.telegram_reporter.report_orphan_trade_detected(
                                strategy_name=strategy_name,
                                symbol=symbol,
                                quantity=position.quantity,
                                side=position.side
                            )
                else:
                    if 'rsi' in strategy_name.lower():
                        self.logger.info(f"🔍 RSI ORPHAN CHECK: Position exists on Binance, no orphan")

                    # Remove any existing orphan trade since position exists
                    orphan_id = f"{strategy_name}_{symbol}"
                    if orphan_id in self.orphan_trades:
                        del self.orphan_trades[orphan_id]
                        self.logger.debug(f"🔍 Removed orphan trade {orphan_id} - position exists on Binance")

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

                # Skip ghost detection if bot recently placed a trade on this symbol
                if self._is_ghost_detection_paused(symbol):
                    self.logger.debug(f"🔍 GHOST CHECK: Skipping {symbol} - bot trade detected recently, waiting for confirmation")
                    continue

                # Check if this position matches ANY known bot position
                is_bot_position = False
                matching_strategy = None

                for strategy_name, bot_position in self.order_manager.active_positions.items():
                    if bot_position.symbol == symbol:
                        # Compare position details more accurately
                        bot_side_multiplier = 1 if bot_position.side == 'BUY' else -1
                        expected_position_amt = bot_position.quantity * bot_side_multiplier

                        self.logger.debug(f"🔍 GHOST CHECK: Comparing {symbol} - Binance: {position_amt}, Bot expects: {expected_position_amt}")

                        # More lenient tolerance for quantity differences due to rounding
                        if abs(position_amt - expected_position_amt) < 0.1:  # Increased tolerance for futures rounding
                            is_bot_position = True
                            matching_strategy = strategy_name
                            self.logger.debug(f"🔍 GHOST CHECK: Position {symbol} matches bot strategy {strategy_name}")
                            break
                        # Also check for exact quantity match (common case)
                        elif abs(abs(position_amt) - bot_position.quantity) < 0.1:  # Increased tolerance
                            is_bot_position = True
                            matching_strategy = strategy_name
                            self.logger.debug(f"🔍 GHOST CHECK: Position {symbol} matches bot strategy {strategy_name} (quantity match)")
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
                    # AND it wasn't recently cleared
                    if not existing_ghost_found:
                        side = 'LONG' if position_amt > 0 else 'SHORT'
                        # Simple ghost ID using just strategy and symbol to prevent duplicates
                        ghost_id = f"{monitoring_strategy}_{symbol}"

                        # Check if this ghost trade was recently cleared by ID
                        if ghost_id in self.recently_cleared_ghosts:
                            self.logger.debug(f"🔍 GHOST CHECK: Ghost trade {ghost_id} was recently cleared, skipping re-detection")
                            continue

                        # Check if a ghost trade with same characteristics was recently cleared (NEW)
                        if self._is_ghost_trade_recently_cleared(symbol, position_amt):
                            self.logger.debug(f"🔍 GHOST CHECK: Ghost trade with same fingerprint was recently cleared, skipping re-detection")
                            continue

                        # Check if ghost trade already exists (additional safety check)
                        if ghost_id in self.ghost_trades:
                            self.logger.debug(f"🔍 GHOST CHECK: Ghost trade {ghost_id} already exists, skipping duplicate creation")
                            continue

                        # Check if this symbol has been persistently tracked to prevent re-notifications
                        if symbol in self.persistent_ghost_symbols:
                            time_since_first_detection = datetime.now() - self.persistent_ghost_symbols[symbol]
                            if time_since_first_detection.total_seconds() < 3600:  # 1 hour grace period
                                self.logger.debug(f"🔍 GHOST CHECK: Symbol {symbol} was recently notified ({time_since_first_detection.total_seconds():.0f}s ago), skipping duplicate notification")
                                continue

                        # Additional check: Look for any existing ghost trade for this symbol regardless of strategy name
                        # This prevents duplicate detection when strategies change or symbol monitoring changes
                        symbol_already_tracked = False
                        for existing_ghost_id, existing_ghost in self.ghost_trades.items():
                            if existing_ghost.symbol == symbol and not existing_ghost.clearing_notified:
                                self.logger.debug(f"🔍 GHOST CHECK: Symbol {symbol} already tracked under ghost ID {existing_ghost_id}, skipping duplicate")
                                symbol_already_tracked = True
                                break

                        if symbol_already_tracked:
                            continue

                        ghost_trade = GhostTrade(
                            symbol=symbol,
                            side=side,
                            quantity=abs(position_amt),
                            detected_at=datetime.now(),
                            cycles_remaining=20,  # 20 cycles before clearing (about 3-4 minutes)
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

                        # Check if this symbol has been recently notified (prevent spam)
                        last_notification = self.notified_ghost_positions.get(symbol)
                        notification_cooldown_hours = 2  # Don't re-notify for 2 hours

                        recently_notified = False
                        if last_notification:
                            time_since_notification = datetime.now() - last_notification
                            recently_notified = time_since_notification.total_seconds() < (notification_cooldown_hours * 3600)

                        # Mark all ghost trades as notified immediately upon creation to prevent ANY duplicate notifications
                        ghost_trade.detection_notified = True
                        ghost_trade.last_notification_time = datetime.now()
                        self.notified_ghost_positions[symbol] = datetime.now()

                        # Check if we should send notification (but mark as notified regardless)
                        should_notify = (not suppress_notifications and 
                                       self.startup_scan_complete and 
                                       not recently_notified)

                        # During startup scan, just log but don't notify
                        if not self.startup_scan_complete:
                            self.logger.warning(f"🔍 STARTUP POSITION DETECTED | {monitoring_strategy} | {symbol} | Manual position found during startup | Qty: {abs(position_amt):.6f} | Value: ${usdt_value:.2f} USDT")
                            self.logger.warning(f"🚨 CRITICAL: This position was NOT opened by the bot in this session")
                            self.logger.warning(f"🔍 Position will be monitored as ghost trade until manually closed")

                        elif should_notify:
                            # This is a normal anomaly check - send notification ONLY ONCE
                            self.logger.warning(f"👻 NEW GHOST TRADE DETECTED | {monitoring_strategy} | {symbol} | Manual position found | Qty: {abs(position_amt):.6f} | Value: ${usdt_value:.2f} USDT")

                            # Send Telegram notification
                            try:
                                self.telegram_reporter.report_ghost_trade_detected(
                                    strategy_name=monitoring_strategy,
                                    symbol=symbol,
                                    side=side,
                                    quantity=abs(position_amt),
                                    current_price=current_price
                                )

                                self.logger.debug(f"🔍 GHOST NOTIFICATION: Successfully sent notification for {ghost_id}")

                            except Exception as e:
                                self.logger.error(f"Failed to send ghost trade notification: {e}")
                        else:
                            # This is a suppressed check or already notified - just log
                            if not self.startup_scan_complete:
                                scan_type = "STARTUP SCAN"
                            elif recently_notified:
                                scan_type = "COOLDOWN ACTIVE"
                            else:
                                scan_type = "SUPPRESSED CHECK"
                            self.logger.debug(f"👻 POSITION NOTED ({scan_type}) | {monitoring_strategy} | {symbol} | Manual position tracked | Qty: {abs(position_amt):.6f} | Value: ${usdt_value:.2f} USDT")
                    else:
                        # Update the existing ghost trade but don't re-notify
                        if existing_ghost_id:
                            existing_ghost = self.ghost_trades[existing_ghost_id]

                            # Always ensure existing ghost trades are marked as notified during startup
                            if not self.startup_scan_complete and not existing_ghost.detection_notified:
                                self.logger.info(f"🔍 STARTUP SCAN: Marking existing ghost trade {existing_ghost_id} as notified to prevent duplicate notifications")
                                existing_ghost.detection_notified = True
                                existing_ghost.last_notification_time = datetime.now()
                                self.notified_ghost_positions[symbol] = datetime.now()

                            # Update quantity if significantly different
                            if abs(existing_ghost.quantity - abs(position_amt)) > 0.001:
                                self.logger.debug(f"🔍 GHOST CHECK: Updating ghost trade quantity for {symbol} from {existing_ghost.quantity:.6f} to {abs(position_amt):.6f}")
                                existing_ghost.quantity = abs(position_amt)
                                existing_ghost.side = 'LONG' if position_amt > 0 else 'SHORT'

                            # Never re-notify for existing ghost trades
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

        # Remove cleared orphan trades and update database
        for strategy_name in orphans_to_remove:
            orphan_trade = self.orphan_trades[strategy_name]

            # Update database to mark trade as manually closed
            try:
                from src.execution_engine.trade_database import TradeDatabase
                trade_db = TradeDatabase()

                # Find the trade in database by position details
                symbol = orphan_trade.position.symbol
                side = orphan_trade.position.side
                quantity = orphan_trade.position.quantity
                entry_price = orphan_trade.position.entry_price

                trade_id = trade_db.find_trade_by_position(strategy_name, symbol, side, quantity, entry_price)

                if trade_id:
                    # Get current price for exit price
                    try:
                        ticker = self.binance_client.get_symbol_ticker(symbol)
                        current_price = float(ticker['price']) if ticker else entry_price
                    except:
                        current_price = entry_price

                    # Calculate duration
                    duration_minutes = (datetime.now() - orphan_trade.detected_at).total_seconds() / 60

                    # Update database with manual closure
                    update_data = {
                        'trade_status': 'CLOSED',
                        'exit_price': current_price,
                        'exit_reason': 'Manual Closure (Orphan Cleared)',
                        'pnl_usdt': 0.0,  # Unknown PnL since manually closed
                        'pnl_percentage': 0.0,
                        'duration_minutes': duration_minutes,
                        'manually_closed': True,
                        'orphan_cleared': True
                    }

                    success = trade_db.update_trade(trade_id, update_data)
                    if success:
                        self.logger.info(f"✅ Database updated for orphan clear: {trade_id}")
                    else:
                        self.logger.error(f"❌ Failed to update database for orphan clear: {trade_id}")

            except Exception as db_error:
                self.logger.error(f"❌ Database update error during orphan clear: {db_error}")

            del self.orphan_trades[strategy_name]

        # Process ghost trades - NEVER close them on Binance, only clear from internal tracking
        ghosts_to_remove = []
        for ghost_id, ghost_trade in self.ghost_trades.items():
            # Check if position still exists on Binance before any processing
            binance_positions = self._get_binance_positions(ghost_trade.symbol)
            position_still_exists = False

            for binance_pos in binance_positions:
                position_amt = float(binance_pos.get('positionAmt', 0))
                if abs(position_amt) > 0.001:  # Position still exists
                    position_still_exists = True
                    break

            # If position no longer exists on Binance, clear it immediately regardless of cycles
            if not position_still_exists:
                # Extract strategy name from simplified ghost_id (strategy_symbol format)
                parts = ghost_id.split('_')
                if len(parts) >= 2:
                    strategy_name = '_'.join(parts[:-1])  # All parts except the last (symbol)
                else:
                    strategy_name = parts[0]

                # Log and notify only if not already notified and not suppressed
                if not ghost_trade.clearing_notified and not suppress_notifications:
                    self.logger.info(f"🧹 GHOST TRADE CLEARED | {strategy_name} | Position closed manually on Binance")

                    self.telegram_reporter.report_ghost_trade_cleared(
                        strategy_name=strategy_name,
                        symbol=ghost_trade.symbol
                    )
                    ghost_trade.clearing_notified = True

                    # Remove from notification tracking since position is actually closed
                    if ghost_trade.symbol in self.notified_ghost_positions:
                        del self.notified_ghost_positions[ghost_trade.symbol]

                ghosts_to_remove.append(ghost_id)
                self.logger.debug(f"🔍 GHOST CLEANUP: Marking {ghost_id} for removal - position no longer exists on Binance")

            else:
                # Position still exists - this is a persistent manual trade
                # Don't decrement cycles or clear - just monitor indefinitely
                self.logger.debug(f"🔍 GHOST CHECK: Persistent manual position {ghost_id} still exists, continuing to monitor")

                # Reset cycles to prevent negative overflow but don't clear
                if ghost_trade.cycles_remaining <= -100:
                    ghost_trade.cycles_remaining = 100
                    self.logger.debug(f"🔍 GHOST CHECK: Reset cycle counter for persistent ghost trade {ghost_id}")

        # Remove ghost trades that no longer exist on Binance
        for ghost_id in ghosts_to_remove:
            ghost_trade = self.ghost_trades[ghost_id]
            current_time = datetime.now()

            # Add to recently cleared to prevent immediate re-detection (with longer cooldown)
            self.recently_cleared_ghosts[ghost_id] = current_time

            # Generate and store fingerprint to prevent re-detection of same trade (NEW)
            fingerprint = self._generate_ghost_trade_fingerprint(ghost_trade.symbol, ghost_trade.quantity if ghost_trade.side == 'LONG' else -ghost_trade.quantity)
            self.ghost_trade_fingerprints[fingerprint] = current_time
            self.logger.debug(f"🔍 GHOST CLEANUP: Added fingerprint {fingerprint} to prevent re-detection")

            # Save fingerprints persistently
            self._save_persistent_ghost_fingerprints()

            # Clean up persistent symbol tracking when position is actually closed
            if ghost_trade.symbol in self.persistent_ghost_symbols:
                del self.persistent_ghost_symbols[ghost_trade.symbol]
                self.logger.debug(f"🔍 GHOST CLEANUP: Removed {ghost_trade.symbol} from persistent tracking")

            # Remove from notification tracking
            if ghost_trade.symbol in self.notified_ghost_positions:
                del self.notified_ghost_positions[ghost_trade.symbol]
                self.logger.debug(f"🔍 GHOST CLEANUP: Removed {ghost_trade.symbol} from notification tracking")

            del self.ghost_trades[ghost_id]
            self.logger.debug(f"🔍 GHOST CLEANUP: Successfully removed ghost trade {ghost_id}")

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

    def get_anomaly_status(self, strategy_name: str) -> Optional[str):
        """Get anomaly status for a strategy"""
        if strategy_name in self.orphan_trades:
            cycles = self.orphan_trades[strategy_name].cycles_remaining
            return f"ORPHAN ({cycles} cycles remaining)"

        for ghost_id, ghost_trade in self.ghost_trades.items():
            if ghost_id.startswith(f"{strategy_name}_"):
                return f"GHOST ({ghost_trade.cycles_remaining} cycles remaining)"

        return None

    def _cleanup_recently_cleared_ghosts(self):
        """Clean up recently cleared ghosts after 24 hours"""
        try:
            current_time = datetime.now()

            # Remove cleared ghosts older than 24 hours
            ghosts_to_remove = []
            for symbol, cleared_time in self.recently_cleared_ghosts.items():
                if (current_time - cleared_time).total_seconds() > 86400:  # 24 hours
                    ghosts_to_remove.append(symbol)

            for symbol in ghosts_to_remove:
                del self.recently_cleared_ghosts[symbol]
                self.logger.debug(f"🔍 GHOST CLEANUP: Removed {symbol} from recently cleared after 24 hours")

            # Also cleanup notification tracking
            notifications_to_remove = []
            for symbol, notification_time in self.notified_ghost_positions.items():
                if (current_time - notification_time).total_seconds() > 86400:  # 24 hours
                    notifications_to_remove.append(symbol)

            for symbol in notifications_to_remove:
                del self.notified_ghost_positions[symbol]
                self.logger.debug(f"🔍 NOTIFICATION CLEANUP: Removed {symbol} from notification tracking after 24 hours")

            # Cleanup expired bot trade tracking (after delay period + buffer)
            bot_trades_to_remove = []
            cleanup_threshold = self.ghost_detection_delay_seconds + 60  # 30s delay + 60s buffer
            for symbol, trade_time in self.recent_bot_trades.items():
                if (current_time - trade_time).total_seconds() > cleanup_threshold:
                    bot_trades_to_remove.append(symbol)

            for symbol in bot_trades_to_remove:
                del self.recent_bot_trades[symbol]
                self.logger.debug(f"🔍 BOT TRADE CLEANUP: Removed {symbol} from recent trades tracking after {cleanup_threshold}s")

            # Memory management cleanup
            self._perform_memory_cleanup()

        except Exception as e:
            self.logger.error(f"Error cleaning up recently cleared ghosts: {e}")

    def _perform_memory_cleanup(self):
        """Perform memory cleanup to prevent unlimited growth"""
        try:
            current_time = datetime.now()

            # Check if cleanup is needed
            if (current_time - self.last_memory_cleanup).total_seconds() < self.memory_cleanup_interval:
                return

            # Clean up each tracking dictionary if it exceeds limits
            tracking_dicts = [
                ('orphan_trades', self.orphan_trades),
                ('ghost_trades', self.ghost_trades),
                ('recently_cleared_ghosts', self.recently_cleared_ghosts),
                ('recent_bot_trades', self.recent_bot_trades),
                ('ghost_notification_times', self.ghost_notification_times),
                ('notified_ghost_positions', self.notified_ghost_positions)
            ]

            for dict_name, tracking_dict in tracking_dicts:
                if len(tracking_dict) > self.max_tracking_items:
                    # Remove oldest entries
                    if dict_name in ['orphan_trades', 'ghost_trades']:
                        # For trade objects, sort by detected_at
                        sorted_items = sorted(tracking_dict.items(), 
                                            key=lambda x: x[1].detected_at if hasattr(x[1], 'detected_at') else datetime.min)
                    else:
                        # For datetime dictionaries
                        sorted_items = sorted(tracking_dict.items(), key=lambda x: x[1])

                    # Keep only the most recent max_tracking_items
                    items_to_remove = len(tracking_dict) - self.max_tracking_items
                    for i in range(items_to_remove):
                        key_to_remove = sorted_items[i][0]
                        del tracking_dict[key_to_remove]

                    self.logger.warning(f"🧹 MEMORY CLEANUP: Removed {items_to_remove} old entries from {dict_name}")

            self.last_memory_cleanup = current_time

        except Exception as e:
            self.logger.error(f"Error in memory cleanup: {e}")

    def _clear_expired_anomalies(self):
        """Clear expired anomalies (after countdown reaches 0)"""
        try:
            self.logger.debug(f"🔍 CLEAR EXPIRED: Checking for expired anomalies")
            self.logger.debug(f"🔍 CLEAR EXPIRED: Current orphan trades: {len(self.orphan_trades)}")
            self.logger.debug(f"🔍 CLEAR EXPIRED: Current ghost trades: {len(self.ghost_trades)}")

            # Clear expired orphan trades
            expired_orphan_ids = []
            for orphan_id, orphan_trade in self.orphan_trades.items():
                orphan_trade.cycles_remaining -= 1
                self.logger.debug(f"🔍 CLEAR EXPIRED: Orphan {orphan_id} cycles remaining: {orphan_trade.cycles_remaining}")
                if orphan_trade.cycles_remaining <= 0:
                    expired_orphan_ids.append(orphan_id)

            for orphan_id in expired_orphan_ids:
                orphan_trade = self.orphan_trades[orphan_id]
                if not orphan_trade.clearing_notified:
                    self.logger.info(f"🧹 ORPHAN TRADE CLEARED | {orphan_trade.position.strategy_name} | {orphan_trade.position.symbol} | Cleared after timeout")
                    self.telegram_reporter.report_orphan_trade_cleared(orphan_trade.position.strategy_name, orphan_trade.position.symbol)
                    orphan_trade.clearing_notified = True

                del self.orphan_trades[orphan_id]
                self.logger.debug(f"🔍 CLEAR EXPIRED: Removed expired orphan trade {orphan_id}")

            # Clear expired ghost trades
            expired_ghost_ids = []
            for ghost_id, ghost_trade in self.ghost_trades.items():
                ghost_trade.cycles_remaining -= 1
                self.logger.debug(f"🔍 CLEAR EXPIRED: Ghost {ghost_id} cycles remaining: {ghost_trade.cycles_remaining}")
                if ghost_trade.cycles_remaining <= 0:
                    expired_ghost_ids.append(ghost_id)

            for ghost_id in expired_ghost_ids:
                ghost_trade = self.ghost_trades[ghost_id]
                if not ghost_trade.clearing_notified:
                    strategy_name = ghost_id.split('_')[0]  # Extract strategy name from ghost_id
                    self.logger.info(f"🧹 GHOST TRADE CLEARED | {strategy_name} | {ghost_trade.symbol} | Cleared after timeout")
                    self.telegram_reporter.report_ghost_trade_cleared(strategy_name, ghost_trade.symbol)
                    ghost_trade.clearing_notified = True

                del self.ghost_trades[ghost_id]
                self.logger.debug(f"🔍 CLEAR EXPIRED: Removed expired ghost trade {ghost_id}")

        except Exception as e:
            self.logger.error(f"Error clearing expired anomalies: {e}")

    def _handle_ghost_trade(self, monitoring_strategy: str, symbol: str, position_amt: float, suppress_notifications: bool = False):
        """Handle detected ghost trade"""
        try:
            self.logger.debug(f"🔍 GHOST TRADE: _handle_ghost_trade called for {monitoring_strategy} {symbol} amt={position_amt} suppress={suppress_notifications}")

            current_price = self._get_current_price(symbol)
            side = 'BUY' if position_amt > 0 else 'SELL'
            ghost_id = f"{monitoring_strategy}_{symbol}"

            self.logger.debug(f"🔍 GHOST TRADE: Generated ghost_id={ghost_id}")
            self.logger.debug(f"🔍 GHOST TRADE: Current ghost trades: {list(self.ghost_trades.keys())}")

            # Check if ghost trade already exists
            existing_ghost_found = False
            existing_ghost_id = None
            for gid, ghost in self.ghost_trades.items():
                if ghost.symbol == symbol and gid.startswith(monitoring_strategy):
                    existing_ghost_found = True
                    existing_ghost_id = gid
                    self.logger.debug(f"🔍 GHOST TRADE: Found existing ghost trade: {gid}")
                    break

            if not existing_ghost_found:
                self.logger.debug(f"🔍 GHOST TRADE: No existing ghost trade found, creating new one")

                # New ghost trade
                ghost_trade = GhostTrade(
                    symbol=symbol,
                    side=side,
                    quantity=abs(position_amt),
                    detected_at=datetime.now(),
                    cycles_remaining=20,  # Extended cycles for new trades
                    detection_notified=False,
                    clearing_notified=False,
                    last_notification_time=None,
                    notification_cooldown_minutes=60
                )

                self.ghost_trades[ghost_id] = ghost_trade
                self.logger.debug(f"🔍 GHOST TRADE: Created new ghost trade {ghost_id}")

                # Log detection
                usdt_value = current_price * abs(position_amt) if current_price else 0

                # Check notification conditions in detail
                self.logger.debug(f"🔍 GHOST TRADE: Notification check:")
                self.logger.debug(f"  - suppress_notifications: {suppress_notifications}")
                self.logger.debug(f"  - startup_scan_complete: {self.startup_scan_complete}")
                self.logger.debug(f"  - detection_notified: {ghost_trade.detection_notified}")

                should_notify = (not suppress_notifications and 
                               self.startup_scan_complete and 
                               not ghost_trade.detection_notified)

                self.logger.debug(f"🔍 GHOST TRADE: should_notify = {should_notify}")

                if should_notify:
                    # This is a normal anomaly check - send notification ONLY ONCE
                    self.logger.warning(f"👻 NEW GHOST TRADE DETECTED | {monitoring_strategy} | {symbol} | Manual position found | Qty: {abs(position_amt):.6f} | Value: ${usdt_value:.2f} USDT")

                    # Send Telegram notification
                    self.telegram_reporter.report_ghost_trade_detected(
                        strategy_name=monitoring_strategy,
                        symbol=symbol,
                        side=side,
                        quantity=abs(position_amt),
                        current_price=current_price
                    )

                    ghost_trade.detection_notified = True
                    ghost_trade.last_notification_time = datetime.now()
                    self.logger.debug(f"🔍 GHOST TRADE: Notification sent and marked as notified")
                else:
                    # This is a suppressed startup scan or already notified - just log
                    if not self.startup_scan_complete:
                        scan_type = "STARTUP SCAN"
                    elif ghost_trade.detection_notified:
                        scan_type = "ALREADY NOTIFIED"
                    else:
                        scan_type = "SUPPRESSED CHECK"
                    self.logger.debug(f"👻 POSITION NOTED ({scan_type}) | {monitoring_strategy} | {symbol} | Manual position tracked | Qty: {abs(position_amt):.6f} | Value: ${usdt_value:.2f} USDT")
            else:
                self.logger.debug(f"🔍 GHOST TRADE: Existing ghost trade found: {existing_ghost_id}")
                existing_ghost = self.ghost_trades[existing_ghost_id]

                # Update the existing ghost trade but don't re-notify
                if existing_ghost_id:
                    if existing_ghost and abs(existing_ghost.quantity - abs(position_amt)) > 0.000001:
                        self.logger.debug(f"🔍 GHOST TRADE: Updating ghost trade quantity for {symbol} from {existing_ghost.quantity:.6f} to {abs(position_amt):.6f}")
                        existing_ghost.quantity = abs(position_amt)
                        existing_ghost.side = 'LONG' if position_amt > 0 else 'SHORT'

                    # Check if this ghost trade was already notified
                    self.logger.debug(f"🔍 GHOST TRADE: Existing ghost notification status: detection_notified={existing_ghost.detection_notified}")

                    # Ensure we don't re-notify for existing ghost trades
                    if not existing_ghost.detection_notified and not suppress_notifications and self.startup_scan_complete:
                        # This should not happen, but just in case, mark as notified without sending
                        self.logger.debug(f"🔍 GHOST TRADE: Marking existing ghost trade {ghost_id} as notified to prevent notifications")
                        existing_ghost.detection_notified = True
                        existing_ghost.last_notification_time = datetime.now()
                    else:
                        self.logger.debug(f"🔍 GHOST TRADE: Skipping notification - already notified or suppressed")

                self.logger.debug(f"🔍 GHOST TRADE: Ghost trade already exists for {symbol}, skipping duplicate detection")

        except Exception as e:
            self.logger.error(f"Error handling ghost trade: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")

    def _get_current_price(self, symbol: str) -> Optional[float]:
        """Helper method to fetch current price for a symbol"""
        try:
            ticker = self.binance_client.get_symbol_ticker(symbol)
            current_price = float(ticker['price']) if ticker else None
            return current_price
        except Exception as e:
            self.logger.error(f"Error getting ticker price for {symbol}: {e}")
            return None

    def _generate_ghost_trade_fingerprint(self, symbol: str, position_amt: float) -> str:
        """Generate a unique fingerprint for a ghost trade to prevent re-detection"""
        # Create fingerprint based on symbol, direction, and rounded quantity
        side = 'LONG' if position_amt > 0 else 'SHORT'
        # Round quantity to 6 decimal places to handle minor differences
        rounded_qty = round(abs(position_amt), 6)
        fingerprint = f"{symbol}_{side}_{rounded_qty}"
        return fingerprint

    def _is_ghost_trade_recently_cleared(self, symbol: str, position_amt: float) -> bool:
        """Check if a ghost trade with same characteristics was recently cleared"""
        fingerprint = self._generate_ghost_trade_fingerprint(symbol, position_amt)

        if fingerprint in self.ghost_trade_fingerprints:
            clear_time = self.ghost_trade_fingerprints[fingerprint]
            time_since_clear = datetime.now() - clear_time
            cooldown_hours = 2  # 2 hours cooldown as requested

            if time_since_clear.total_seconds() < (cooldown_hours * 3600):
                self.logger.debug(f"🔍 GHOST FINGERPRINT: Trade {fingerprint} was cleared {time_since_clear.total_seconds():.0f}s ago, within {cooldown_hours}h cooldown")
                return True

        return False

    def _load_persistent_ghost_fingerprints(self):
        """Load persistent ghost fingerprints from file to survive bot restarts"""
        try:
            import os
            import json

            fingerprint_file = "trading_data/ghost_fingerprints.json"

            if os.path.exists(fingerprint_file):
                with open(fingerprint_file, 'r') as f:
                    data = json.load(f)

                # Convert string timestamps back to datetime objects
                current_time = datetime.now()
                for fingerprint, timestamp_str in data.items():
                    try:
                        clear_time = datetime.fromisoformat(timestamp_str)
                        # Only load fingerprints that are still within the 2-hour cooldown
                        if (current_time - clear_time).total_seconds() < (2 * 3600):
                            self.ghost_trade_fingerprints[fingerprint] = clear_time
                            self.logger.debug(f"🔍 FINGERPRINT LOADED: {fingerprint} from {timestamp_str}")
                    except ValueError:
                        continue

                self.logger.info(f"🔍 FINGERPRINT TRACKING: Loaded {len(self.ghost_trade_fingerprints)} persistent ghost fingerprints")
            else:
                self.logger.debug(f"🔍 FINGERPRINT TRACKING: No persistent fingerprint file found")

        except Exception as e:
            self.logger.error(f"Error loading persistent ghost fingerprints: {e}")

    def _save_persistent_ghost_fingerprints(self):
        """Save ghost fingerprints to file to persist across bot restarts"""
        try:
            import os
            import json

            # Ensure directory exists
            os.makedirs("trading_data", exist_ok=True)

            fingerprint_file = "trading_data/ghost_fingerprints.json"

            # Convert datetime objects to strings for JSON serialization
            data = {}
            for fingerprint, clear_time in self.ghost_trade_fingerprints.items():
                data[fingerprint] = clear_time.isoformat()

            with open(fingerprint_file, 'w') as f:
                json.dump(data, f, indent=2)

            self.logger.debug(f"🔍 FINGERPRINT TRACKING: Saved {len(data)} ghost fingerprints to {fingerprint_file}")

        except Exception as e:
            self.logger.error(f"Error saving persistent ghost fingerprints: {e}")
    def has_blocking_anomaly(self, strategy_name: str) -> bool:
        """Check if strategy has a blocking anomaly"""
        return strategy_name in self.ghost_trades

    def _should_delay_ghost_detection(self) -> bool:
        """Check if ghost detection should be delayed due to recent order"""
        if not self.order_manager or not hasattr(self.order_manager, 'last_order_time'):
            return False

        if not self.order_manager.last_order_time:
            return False

        from datetime import datetime, timedelta
        time_since_order = datetime.now() - self.order_manager.last_order_time

        # Delay ghost detection for 30 seconds after placing an order
        if time_since_order < timedelta(seconds=30):
            return True

        return False

    def clear_orphan_by_cycles(self, orphan_id: str, reason: str = "Cycle limit reached") -> bool:
        """Clear orphan trade after countdown cycles with enhanced database sync"""
        if orphan_id not in self.orphan_trades:
            self.logger.warning(f"🧹 Orphan {orphan_id} not found for clearing")
            return False

        orphan = self.orphan_trades[orphan_id]

        try:
            self.logger.info(f"🧹 CLEARING ORPHAN | {orphan_id} | Reason: {reason}")

            # Clear from order manager with improved strategy matching
            if self.order_manager:
                # Try multiple strategy name variations for clearing
                strategy_variations = [
                    orphan.position.strategy_name,
                    orphan_id,
                    f"{orphan.position.strategy_name}_{orphan.position.symbol}",
                    orphan.position.strategy_name.split('_')[0] + '_' + orphan.position.strategy_name.split('_')[1] if '_' in orphan.position.strategy_name else orphan.position.strategy_name
                ]

                cleared = False
                for strategy_name in strategy_variations:
                    try:
                        result = self.order_manager.clear_orphan_position(strategy_name)
                        if result:
                            cleared = True
                            self.logger.info(f"✅ Cleared from order manager: {strategy_name}")
                            break
                    except Exception as e:
                        self.logger.debug(f"Could not clear {strategy_name}: {e}")

                if not cleared:
                    self.logger.warning(f"⚠️ Could not clear from order manager, continuing with database update")

            # Update database record to CLOSED with enhanced error handling
            database_updated = self._update_database_for_cleared_orphan(orphan, reason)

            if not database_updated:
                self.logger.error(f"❌ Failed to update database for orphan {orphan_id}")
                # Continue with clearing from memory even if database update fails

            # Remove from orphan trades
            del self.orphan_trades[orphan_id]

            # Send clearing notification
            try:
                self._send_orphan_clearing_notification(orphan, reason)
            except Exception as e:
                self.logger.warning(f"⚠️ Could not send clearing notification: {e}")

            self.logger.info(f"✅ ORPHAN CLEARED SUCCESSFULLY | {orphan_id}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error clearing orphan {orphan_id}: {e}")
            import traceback
            self.logger.error(f"🔍 Clearing traceback: {traceback.format_exc()}")
            return False

    def _update_database_for_cleared_orphan(self, orphan: OrphanTrade, reason: str) -> bool:
        """Update database record for cleared orphan trade with improved matching"""
        try:
            from src.execution_engine.trade_database import TradeDatabase
            trade_db = TradeDatabase()

            # Find the trade record with multiple matching strategies
            trade_record = None

            # Strategy 1: Exact match
            for trade_id, trade_data in trade_db.trades.items():
                if (trade_data.get('symbol') == orphan.position.symbol and
                    trade_data.get('strategy_name') == orphan.position.strategy_name and
                    trade_data.get('trade_status') == 'OPEN'):
                    trade_record = (trade_id, trade_data)
                    self.logger.info(f"Found exact match for orphan: {trade_id}")
                    break

            # Strategy 2: Symbol and position details match (for test orphans)
            if not trade_record:
                for trade_id, trade_data in trade_db.trades.items():
                    if (trade_data.get('symbol') == orphan.position.symbol and
                        trade_data.get('side') == orphan.position.side and
                        abs(float(trade_data.get('quantity', 0)) - orphan.position.quantity) < 0.01 and
                        trade_data.get('trade_status') == 'OPEN'):
                        trade_record = (trade_id, trade_data)
                        self.logger.info(f"Found position match for orphan: {trade_id}")
                        break

            # Strategy 3: Any open trade with matching symbol (last resort)
            if not trade_record:
                for trade_id, trade_data in trade_db.trades.items():
                    if (trade_data.get('symbol') == orphan.position.symbol and
                        trade_data.get('trade_status') == 'OPEN'):
                        trade_record = (trade_id, trade_data)
                        self.logger.info(f"Found symbol match for orphan: {trade_id}")
                        break

            if trade_record:
                trade_id, trade_data = trade_record

                # Get current price for PnL calculation
                current_price = orphan.position.entry_price  # Fallback to entry price
                try:
                    if self.binance_client:
                        ticker = self.binance_client.get_symbol_ticker(orphan.position.symbol)
                        if ticker and 'price' in ticker:
                            current_price = float(ticker['price'])
                except Exception as e:
                    self.logger.warning(f"Could not get current price for {orphan.position.symbol}: {e}")

                # Calculate simplified PnL based on position
                entry_price = float(trade_data.get('entry_price', orphan.position.entry_price))
                quantity = float(trade_data.get('quantity', orphan.position.quantity))
                side = trade_data.get('side', orphan.position.side)

                if side == 'BUY':
                    pnl_usdt = (current_price - entry_price) * quantity
                else:
                    pnl_usdt = (entry_price - current_price) * quantity

                # Calculate PnL percentage against margin used
                margin_used = float(trade_data.get('margin_used', 50.0))
                pnl_percentage = (pnl_usdt / margin_used) * 100 if margin_used > 0 else 0.0

                updates = {
                    'trade_status': 'CLOSED',
                    'exit_price': current_price,
                    'exit_reason': f'Orphan cleared: {reason}',
                    'pnl_usdt': round(pnl_usdt, 2),
                    'pnl_percentage': round(pnl_percentage, 2),
                    'duration_minutes': 0,
                    'orphan_cleared': True,
                    'last_updated': datetime.now().isoformat()
                }

                success = trade_db.update_trade(trade_id, updates)
                if success:
                    self.logger.info(f"✅ Database updated for orphan: {trade_id} | PnL: ${pnl_usdt:.2f}")
                    return True
                else:
                    self.logger.error(f"❌ Failed to update database for orphan: {trade_id}")
                    return False

            else:
                self.logger.warning(f"⚠️ No database record found for orphan {orphan.position.strategy_name} ({orphan.position.symbol})")
                return False

        except Exception as e:
            self.logger.error(f"❌ Error updating database for orphan: {e}")
            import traceback
            self.logger.error(f"🔍 Database update traceback: {traceback.format_exc()}")
            return False

    def _send_orphan_clearing_notification(self, orphan: OrphanTrade, reason: str):
        """Send Telegram notification when orphan trade is cleared."""
        self.telegram_reporter.report_orphan_trade_cleared(
            strategy_name=orphan.position.strategy_name,
            symbol=orphan.position.symbol,
        )