
import logging
import json
import os
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path

from src.binance_client.client import BinanceClientWrapper
from src.execution_engine.order_manager import OrderManager, Position
from src.reporting.telegram_reporter import TelegramReporter


class AnomalyType(Enum):
    ORPHAN = "orphan"  # Bot opened, manually closed
    GHOST = "ghost"    # Manually opened, not by bot


class AnomalyStatus(Enum):
    ACTIVE = "active"
    MONITORING = "monitoring"
    CLEARED = "cleared"
    EXPIRED = "expired"


@dataclass
class TradeAnomaly:
    """Represents a trade anomaly (orphan or ghost)"""
    id: str
    type: AnomalyType
    symbol: str
    strategy_name: str
    quantity: float
    side: str  # BUY/SELL or LONG/SHORT
    entry_price: Optional[float] = None
    detected_at: Optional[datetime] = None
    status: AnomalyStatus = AnomalyStatus.ACTIVE
    cycles_remaining: int = 3
    notified: bool = False
    cleared_at: Optional[datetime] = None
    binance_position_amt: Optional[float] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        # Convert datetime objects to ISO strings
        if self.detected_at:
            data['detected_at'] = self.detected_at.isoformat()
        if self.cleared_at:
            data['cleared_at'] = self.cleared_at.isoformat()
        # Convert enums to strings
        data['type'] = self.type.value
        data['status'] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> 'TradeAnomaly':
        """Create from dictionary"""
        # Convert string dates back to datetime
        if data.get('detected_at'):
            data['detected_at'] = datetime.fromisoformat(data['detected_at'])
        if data.get('cleared_at'):
            data['cleared_at'] = datetime.fromisoformat(data['cleared_at'])
        # Convert string enums back to enums
        data['type'] = AnomalyType(data['type'])
        data['status'] = AnomalyStatus(data['status'])
        return cls(**data)


class AnomalyDatabase:
    """Handles persistent storage of anomaly data"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.data_dir = Path("trading_data")
        self.data_dir.mkdir(exist_ok=True)
        self.db_file = self.data_dir / "anomalies.json"
        self.anomalies: Dict[str, TradeAnomaly] = {}
        self._load_anomalies()

    def _load_anomalies(self):
        """Load anomalies from persistent storage"""
        try:
            if self.db_file.exists():
                with open(self.db_file, 'r') as f:
                    data = json.load(f)

                # Handle both old and new JSON formats
                if isinstance(data, dict):
                    # Check if this is the new format with 'anomalies' key
                    if 'anomalies' in data:
                        anomaly_data = data['anomalies']
                        # Handle case where anomalies is a list (empty) vs dict
                        if isinstance(anomaly_data, list):
                            anomaly_data = {}
                    else:
                        # Old format - data is directly the anomalies dict
                        anomaly_data = data
                else:
                    # Invalid format
                    anomaly_data = {}

                for anomaly_id, anomaly_info in anomaly_data.items():
                    try:
                        self.anomalies[anomaly_id] = TradeAnomaly.from_dict(anomaly_info)
                    except Exception as e:
                        self.logger.error(f"Error loading anomaly {anomaly_id}: {e}")
                        continue

                self.logger.info(f"📊 Loaded {len(self.anomalies)} anomalies from database")
            else:
                self.logger.info("📊 No existing anomaly database found, starting fresh")
        except Exception as e:
            self.logger.error(f"Error loading anomaly database: {e}")

    def _save_anomalies(self):
        """Save anomalies to persistent storage"""
        try:
            # Use new format with metadata
            data = {
                'anomalies': {anomaly_id: anomaly.to_dict() for anomaly_id, anomaly in self.anomalies.items()},
                'last_updated': datetime.now().isoformat()
            }

            with open(self.db_file, 'w') as f:
                json.dump(data, f, indent=2)

            self.logger.debug(f"📊 Saved {len(self.anomalies)} anomalies to database")
        except Exception as e:
            self.logger.error(f"Error saving anomaly database: {e}")

    def add_anomaly(self, anomaly: TradeAnomaly):
        """Add new anomaly to database"""
        self.anomalies[anomaly.id] = anomaly
        self._save_anomalies()
        self.logger.info(f"📊 Added anomaly to database: {anomaly.id}")

    def update_anomaly(self, anomaly_id: str, **updates):
        """Update existing anomaly"""
        if anomaly_id in self.anomalies:
            anomaly = self.anomalies[anomaly_id]
            for key, value in updates.items():
                if hasattr(anomaly, key):
                    setattr(anomaly, key, value)
            self._save_anomalies()
            self.logger.debug(f"📊 Updated anomaly: {anomaly_id}")

    def remove_anomaly(self, anomaly_id: str):
        """Remove anomaly from database"""
        if anomaly_id in self.anomalies:
            del self.anomalies[anomaly_id]
            self._save_anomalies()
            self.logger.info(f"📊 Removed anomaly from database: {anomaly_id}")

    def get_anomaly(self, anomaly_id: str) -> Optional[TradeAnomaly]:
        """Get specific anomaly"""
        return self.anomalies.get(anomaly_id)

    def get_active_anomalies(self) -> List[TradeAnomaly]:
        """Get all active anomalies"""
        return [anomaly for anomaly in self.anomalies.values() 
                if anomaly.status == AnomalyStatus.ACTIVE]

    def get_anomalies_by_strategy(self, strategy_name: str) -> List[TradeAnomaly]:
        """Get anomalies for specific strategy"""
        return [anomaly for anomaly in self.anomalies.values() 
                if anomaly.strategy_name == strategy_name and anomaly.status == AnomalyStatus.ACTIVE]

    def get_anomalies_by_symbol(self, symbol: str) -> List[TradeAnomaly]:
        """Get anomalies for specific symbol"""
        return [anomaly for anomaly in self.anomalies.values() 
                if anomaly.symbol == symbol and anomaly.status == AnomalyStatus.ACTIVE]

    def cleanup_old_anomalies(self, days_old: int = 7):
        """Remove old cleared/expired anomalies"""
        cutoff_date = datetime.now() - timedelta(days=days_old)
        to_remove = []

        for anomaly_id, anomaly in self.anomalies.items():
            if (anomaly.status in [AnomalyStatus.CLEARED, AnomalyStatus.EXPIRED] and
                anomaly.cleared_at and anomaly.cleared_at < cutoff_date):
                to_remove.append(anomaly_id)

        for anomaly_id in to_remove:
            self.remove_anomaly(anomaly_id)

        if to_remove:
            self.logger.info(f"📊 Cleaned up {len(to_remove)} old anomalies")


class AnomalyDetector:
    """Advanced anomaly detection system"""

    def __init__(self, binance_client: BinanceClientWrapper, order_manager: OrderManager, 
                 telegram_reporter: TelegramReporter):
        self.binance_client = binance_client
        self.order_manager = order_manager
        self.telegram_reporter = telegram_reporter
        self.logger = logging.getLogger(__name__)

        # Initialize database
        self.db = AnomalyDatabase()

        # Strategy registration
        self.registered_strategies: Dict[str, str] = {}  # strategy_name -> symbol

        # Bot trade tracking with enhanced safety
        self.bot_trades_register: Dict[str, datetime] = {}  # symbol -> last_trade_time
        self.bot_trade_cooldown = 120  # 2 minutes cooldown after bot trades

        # Startup protection
        self.startup_complete = False
        self.startup_protection_duration = 180  # 3 minutes startup protection
        self.startup_time = datetime.now()

        # Detection settings
        self.detection_interval = 30  # Run detection every 30 seconds for faster response
        self.last_detection_run = datetime.now()

        # Position tolerance for rounding differences
        self.position_tolerance = 0.01  # 1% tolerance

    def register_strategy(self, strategy_name: str, symbol: str):
        """Register a strategy for monitoring"""
        self.registered_strategies[strategy_name] = symbol
        self.logger.info(f"🔍 Registered strategy for monitoring: {strategy_name} -> {symbol}")

    def register_bot_trade(self, symbol: str, strategy_name: str):
        """Register that bot just placed a trade or recovered a position"""
        self.bot_trades_register[symbol] = datetime.now()

        # For recovered positions during startup, extend protection period
        if not self.startup_complete:
            # Extend protection to 5 minutes for recovered positions
            extended_time = datetime.now() - timedelta(seconds=self.bot_trade_cooldown - 300)
            self.bot_trades_register[symbol] = extended_time
            self.logger.info(f"🔍 RECOVERED POSITION REGISTERED: {symbol} ({strategy_name}) - "
                           f"Extended anomaly protection for 5 minutes")
        else:
            self.logger.info(f"🔍 BOT TRADE REGISTERED: {symbol} ({strategy_name}) - "
                           f"Anomaly detection paused for {self.bot_trade_cooldown}s")

    def is_bot_trade_protected(self, symbol: str) -> bool:
        """Check if symbol is protected due to recent bot trade"""
        if symbol not in self.bot_trades_register:
            return False

        time_since_trade = datetime.now() - self.bot_trades_register[symbol]
        is_protected = time_since_trade.total_seconds() < self.bot_trade_cooldown

        if is_protected:
            remaining = self.bot_trade_cooldown - time_since_trade.total_seconds()
            self.logger.debug(f"🔍 Symbol {symbol} protected for {remaining:.1f}s more")

        return is_protected

    def is_startup_protected(self) -> bool:
        """Check if we're still in startup protection period"""
        if self.startup_complete:
            return False

        time_since_startup = datetime.now() - self.startup_time
        if time_since_startup.total_seconds() > self.startup_protection_duration:
            self.startup_complete = True
            self.logger.info("🔍 Startup protection period ended - anomaly detection fully active")
            return False

        return True

    def run_detection(self, suppress_notifications: bool = False):
        """Main detection method - should be called periodically"""
        try:
            # Check if it's time to run detection
            time_since_last = datetime.now() - self.last_detection_run
            if time_since_last.total_seconds() < self.detection_interval:
                return

            self.last_detection_run = datetime.now()

            scan_type = "STARTUP" if self.is_startup_protected() else "NORMAL"
            self.logger.debug(f"🔍 Starting {scan_type} anomaly detection scan")

            # Get current positions from Binance
            binance_positions = self._get_all_binance_positions()
            if binance_positions is None:
                self.logger.error("🔍 Failed to get Binance positions, skipping detection")
                return

            # Get bot's active positions
            bot_positions = self.order_manager.get_active_positions()

            # Detect orphan trades (bot opened, manually closed)
            self._detect_orphan_trades(bot_positions, binance_positions, suppress_notifications)

            # Detect ghost trades (manually opened, not by bot)
            self._detect_ghost_trades(bot_positions, binance_positions, suppress_notifications)

            # Process anomaly lifecycle
            self._process_anomaly_lifecycle(binance_positions, suppress_notifications)

            # Cleanup old anomalies
            self.db.cleanup_old_anomalies()

            # Cleanup old bot trade registrations
            self._cleanup_bot_trade_register()

            self.logger.debug(f"🔍 {scan_type} anomaly detection completed")

        except Exception as e:
            self.logger.error(f"Error in anomaly detection: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")

    def _get_all_binance_positions(self) -> Optional[List[Dict]]:
        """Get all positions from Binance"""
        try:
            if self.binance_client.is_futures:
                account_info = self.binance_client.client.futures_account()
                positions = account_info.get('positions', [])
                # Filter for non-zero positions
                active_positions = [pos for pos in positions 
                                  if abs(float(pos.get('positionAmt', 0))) > 0.000001]
                return active_positions
            else:
                # For spot trading, would need different logic
                return []
        except Exception as e:
            self.logger.error(f"Error getting Binance positions: {e}")
            return None

    def _detect_orphan_trades(self, bot_positions: Dict[str, Position], 
                            binance_positions: List[Dict], suppress_notifications: bool):
        """Detect orphan trades (bot opened, manually closed)"""
        if self.is_startup_protected():
            self.logger.debug("🔍 Skipping orphan detection during startup protection")
            return

        for strategy_name, bot_position in bot_positions.items():
            symbol = bot_position.symbol

            # Check if this position exists on Binance
            binance_position = None
            for pos in binance_positions:
                if pos.get('symbol') == symbol:
                    binance_position = pos
                    break

            position_exists_on_binance = False
            if binance_position:
                position_amt = float(binance_position.get('positionAmt', 0))
                if abs(position_amt) > 0.000001:
                    position_exists_on_binance = True

            # If bot thinks position is open but Binance shows it's closed
            if not position_exists_on_binance:
                anomaly_id = f"orphan_{strategy_name}_{symbol}"

                # Check if we already detected this orphan
                existing_anomaly = self.db.get_anomaly(anomaly_id)
                if existing_anomaly:
                    continue  # Already tracking this orphan

                # Create new orphan anomaly
                anomaly = TradeAnomaly(
                    id=anomaly_id,
                    type=AnomalyType.ORPHAN,
                    symbol=symbol,
                    strategy_name=strategy_name,
                    quantity=bot_position.quantity,
                    side=bot_position.side,
                    entry_price=bot_position.entry_price,
                    detected_at=datetime.now(),
                    status=AnomalyStatus.ACTIVE,
                    cycles_remaining=2,
                    notified=False,
                    binance_position_amt=0.0
                )

                self.db.add_anomaly(anomaly)

                # Send notification if not suppressed
                if not suppress_notifications:
                    self._send_orphan_notification(anomaly)
                    self.db.update_anomaly(anomaly_id, notified=True)

                self.logger.warning(f"🔍 ORPHAN DETECTED: {strategy_name} | {symbol} | "
                                  f"Bot position exists but not on Binance")

    def _detect_ghost_trades(self, bot_positions: Dict[str, Position], 
                           binance_positions: List[Dict], suppress_notifications: bool):
        """Detect ghost trades (manually opened, not by bot)"""
        for binance_position in binance_positions:
            symbol = binance_position.get('symbol')
            position_amt = float(binance_position.get('positionAmt', 0))

            if abs(position_amt) < 0.000001:
                continue  # Skip zero positions

            # Skip if symbol is protected due to recent bot trade
            if self.is_bot_trade_protected(symbol):
                self.logger.debug(f"🔍 Skipping ghost detection for {symbol} - bot trade protection active")
                continue

            # Check if this position matches any bot position
            is_bot_position = False
            for strategy_name, bot_position in bot_positions.items():
                if bot_position.symbol == symbol:
                    # Calculate expected position amount
                    expected_amt = bot_position.quantity
                    if bot_position.side == 'SELL':
                        expected_amt = -expected_amt

                    # Check if amounts match within tolerance
                    tolerance = max(abs(expected_amt) * self.position_tolerance, 0.001)
                    if abs(position_amt - expected_amt) <= tolerance:
                        is_bot_position = True
                        self.logger.debug(f"🔍 Position {symbol} matches bot position {strategy_name}")
                        break

            # If this is not a bot position, it's a ghost trade
            if not is_bot_position:
                # Find which strategy should monitor this symbol
                monitoring_strategy = None
                for strategy_name, strategy_symbol in self.registered_strategies.items():
                    if strategy_symbol == symbol:
                        monitoring_strategy = strategy_name
                        break

                if not monitoring_strategy:
                    monitoring_strategy = f"manual_{symbol.lower()}"

                anomaly_id = f"ghost_{monitoring_strategy}_{symbol}"

                # Check if we already detected this ghost
                existing_anomaly = self.db.get_anomaly(anomaly_id)
                if existing_anomaly:
                    # Update quantity if changed significantly
                    if abs(existing_anomaly.binance_position_amt - position_amt) > 0.001:
                        self.db.update_anomaly(anomaly_id, 
                                             binance_position_amt=position_amt,
                                             quantity=abs(position_amt))
                    continue

                # Create new ghost anomaly
                side = 'LONG' if position_amt > 0 else 'SHORT'
                anomaly = TradeAnomaly(
                    id=anomaly_id,
                    type=AnomalyType.GHOST,
                    symbol=symbol,
                    strategy_name=monitoring_strategy,
                    quantity=abs(position_amt),
                    side=side,
                    detected_at=datetime.now(),
                    status=AnomalyStatus.ACTIVE,
                    cycles_remaining=2,
                    notified=False,
                    binance_position_amt=position_amt
                )

                self.db.add_anomaly(anomaly)

                # Send notification if not suppressed and not in startup
                if not suppress_notifications and not self.is_startup_protected():
                    self._send_ghost_notification(anomaly)
                    self.db.update_anomaly(anomaly_id, notified=True)
                elif self.is_startup_protected():
                    self.logger.info(f"🔍 GHOST DETECTED (STARTUP): {monitoring_strategy} | {symbol} | "
                                   f"Manual position noted during startup")

                self.logger.warning(f"🔍 GHOST DETECTED: {monitoring_strategy} | {symbol} | "
                                  f"Manual position found | Qty: {abs(position_amt):.6f}")

    def _process_anomaly_lifecycle(self, binance_positions: List[Dict], suppress_notifications: bool):
        """Process lifecycle of existing anomalies"""
        binance_positions_map = {pos.get('symbol'): pos for pos in binance_positions}

        for anomaly in list(self.db.get_active_anomalies()):
            if anomaly.type == AnomalyType.ORPHAN:
                self._process_orphan_lifecycle(anomaly, binance_positions_map, suppress_notifications)
            elif anomaly.type == AnomalyType.GHOST:
                self._process_ghost_lifecycle(anomaly, binance_positions_map, suppress_notifications)

    def _process_orphan_lifecycle(self, anomaly: TradeAnomaly, 
                                binance_positions_map: Dict, suppress_notifications: bool):
        """Process orphan trade lifecycle"""
        # Decrement cycles
        anomaly.cycles_remaining -= 1
        self.logger.info(f"🔍 ORPHAN LIFECYCLE: {anomaly.strategy_name} | {anomaly.symbol} | "
                        f"Cycles remaining: {anomaly.cycles_remaining}")

        if anomaly.cycles_remaining <= 0:
            # Clear orphan from bot's memory
            cleared = self.order_manager.clear_orphan_position(anomaly.strategy_name)
            
            if cleared:
                # Update database
                self.db.update_anomaly(anomaly.id, 
                                     status=AnomalyStatus.CLEARED,
                                     cleared_at=datetime.now())

                # Send clear notification
                if not suppress_notifications:
                    self._send_orphan_clear_notification(anomaly)

                self.logger.info(f"🧹 ORPHAN AUTO-CLEARED: {anomaly.strategy_name} | {anomaly.symbol} | "
                               f"Strategy can trade again")
            else:
                # If clearing failed, try one more cycle
                self.db.update_anomaly(anomaly.id, cycles_remaining=1)
                self.logger.warning(f"⚠️ ORPHAN CLEAR RETRY: {anomaly.strategy_name} | {anomaly.symbol}")
        else:
            self.db.update_anomaly(anomaly.id, cycles_remaining=anomaly.cycles_remaining)
            self.logger.debug(f"🔍 ORPHAN MONITORING: {anomaly.strategy_name} | {anomaly.symbol} | "
                            f"{anomaly.cycles_remaining} cycles remaining")

    def _process_ghost_lifecycle(self, anomaly: TradeAnomaly, 
                               binance_positions_map: Dict, suppress_notifications: bool):
        """Process ghost trade lifecycle"""
        binance_position = binance_positions_map.get(anomaly.symbol)

        # Check if position still exists on Binance
        position_still_exists = False
        if binance_position:
            position_amt = float(binance_position.get('positionAmt', 0))
            if abs(position_amt) > 0.000001:
                position_still_exists = True
                # Update position amount if changed
                if abs(anomaly.binance_position_amt - position_amt) > 0.001:
                    self.db.update_anomaly(anomaly.id, 
                                         binance_position_amt=position_amt,
                                         quantity=abs(position_amt))

        if not position_still_exists:
            # Ghost position was closed manually
            self.db.update_anomaly(anomaly.id, 
                                 status=AnomalyStatus.CLEARED,
                                 cleared_at=datetime.now())

            # Send clear notification
            if not suppress_notifications:
                self._send_ghost_clear_notification(anomaly)

            self.logger.info(f"🧹 GHOST CLEARED: {anomaly.strategy_name} | {anomaly.symbol} | "
                           f"Manual position closed")
        else:
            # Ghost still exists, continue monitoring
            self.logger.debug(f"🔍 GHOST MONITORING: {anomaly.strategy_name} | {anomaly.symbol} | "
                            f"Manual position still active")

    def _send_orphan_notification(self, anomaly: TradeAnomaly):
        """Send orphan trade notification"""
        try:
            message = f"""👻 **ORPHAN TRADE DETECTED**

Strategy: {anomaly.strategy_name.upper()}
Symbol: {anomaly.symbol}
Side: {anomaly.side}
Entry Price: ${anomaly.entry_price or 0:.4f}

📝 Description: Bot opened position but it was closed manually
🔍 Action: System will auto-clear in 2-3 detection cycles
💡 Note: Strategy is temporarily blocked from new trades"""

            self.telegram_reporter.send_message(message)
            self.logger.info(f"📱 TELEGRAM: Orphan trade notification sent for {anomaly.strategy_name}")
        except Exception as e:
            self.logger.error(f"Error sending orphan notification: {e}")

    def _send_orphan_clear_notification(self, anomaly: TradeAnomaly):
        """Send orphan trade clear notification"""
        try:
            message = f"""🧹 **ORPHAN TRADE CLEARED**

Strategy: {anomaly.strategy_name.upper()}
Symbol: {anomaly.symbol}

✅ Status: Orphan trade automatically cleared
🎯 Result: Strategy is now available for new trades
🔄 Action: Automatic - no manual intervention needed"""

            self.telegram_reporter.send_message(message)
            self.logger.info(f"📱 TELEGRAM: Orphan clear notification sent for {anomaly.strategy_name}")
        except Exception as e:
            self.logger.error(f"Error sending orphan clear notification: {e}")

    def _send_ghost_notification(self, anomaly: TradeAnomaly):
        """Send ghost trade notification"""
        try:
            # Get current price for value calculation
            current_price = None
            try:
                ticker = self.binance_client.get_symbol_ticker(anomaly.symbol)
                current_price = float(ticker['price']) if ticker else None
            except:
                pass

            self.telegram_reporter.report_ghost_trade_detected(
                strategy_name=anomaly.strategy_name,
                symbol=anomaly.symbol,
                side=anomaly.side,
                quantity=anomaly.quantity,
                current_price=current_price
            )
        except Exception as e:
            self.logger.error(f"Error sending ghost notification: {e}")

    def _send_ghost_clear_notification(self, anomaly: TradeAnomaly):
        """Send ghost trade clear notification"""
        try:
            self.telegram_reporter.report_ghost_trade_cleared(
                strategy_name=anomaly.strategy_name,
                symbol=anomaly.symbol
            )
        except Exception as e:
            self.logger.error(f"Error sending ghost clear notification: {e}")

    def _cleanup_bot_trade_register(self):
        """Clean up old bot trade registrations"""
        cutoff_time = datetime.now() - timedelta(seconds=self.bot_trade_cooldown * 2)
        to_remove = []

        for symbol, trade_time in self.bot_trades_register.items():
            if trade_time < cutoff_time:
                to_remove.append(symbol)

        for symbol in to_remove:
            del self.bot_trades_register[symbol]

    def has_blocking_anomaly(self, strategy_name: str) -> bool:
        """Check if strategy has blocking anomaly"""
        anomalies = self.db.get_anomalies_by_strategy(strategy_name)
        return len(anomalies) > 0

    def get_anomaly_status(self, strategy_name: str) -> Optional[str]:
        """Get anomaly status for strategy"""
        anomalies = self.db.get_anomalies_by_strategy(strategy_name)
        if not anomalies:
            return None

        anomaly = anomalies[0]  # Get first active anomaly
        return f"{anomaly.type.value.upper()} ({anomaly.cycles_remaining} cycles remaining)"

    def clear_anomaly_by_id(self, anomaly_id: str, reason: str = "Manual clear") -> bool:
        """Manually clear a specific anomaly by ID"""
        try:
            existing_anomaly = self.db.get_anomaly(anomaly_id)
            if existing_anomaly:
                self.db.update_anomaly(anomaly_id, 
                                     status=AnomalyStatus.CLEARED,
                                     cleared_at=datetime.now())
                self.logger.info(f"🧹 MANUALLY CLEARED ANOMALY | {anomaly_id} | Reason: {reason}")
                return True
            else:
                self.logger.warning(f"❌ ANOMALY NOT FOUND | {anomaly_id}")
                return False
        except Exception as e:
            self.logger.error(f"Error clearing anomaly {anomaly_id}: {e}")
            return False

    def get_anomaly_summary(self) -> Dict:
        """Get summary of all anomalies"""
        active_anomalies = self.db.get_active_anomalies()

        summary = {
            'total_active': len(active_anomalies),
            'orphan_trades': len([a for a in active_anomalies if a.type == AnomalyType.ORPHAN]),
            'ghost_trades': len([a for a in active_anomalies if a.type == AnomalyType.GHOST]),
            'anomalies': []
        }

        for anomaly in active_anomalies:
            summary['anomalies'].append({
                'id': anomaly.id,
                'type': anomaly.type.value,
                'strategy': anomaly.strategy_name,
                'symbol': anomaly.symbol,
                'quantity': anomaly.quantity,
                'side': anomaly.side,
                'detected_at': anomaly.detected_at.isoformat() if anomaly.detected_at else None,
                'cycles_remaining': anomaly.cycles_remaining,
                'notified': anomaly.notified
            })

        return summary
