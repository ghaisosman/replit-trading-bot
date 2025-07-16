import logging
import threading
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import json
from src.binance_client.client import BinanceClientWrapper
from src.strategy_processor.signal_processor import TradingSignal, SignalType

@dataclass
class Position:
    strategy_name: str
    symbol: str
    side: str
    entry_price: float
    quantity: float
    stop_loss: float
    take_profit: float
    position_side: str = "LONG"  # LONG or SHORT for hedge mode
    order_id: Optional[int] = None
    entry_time: Optional[datetime] = None
    status: str = "OPEN"
    trade_id: Optional[str] = None
    strategy_config: Optional[Dict] = None

class OrderManager:
    """Manages order execution and position tracking"""

    def __init__(self, binance_client: BinanceClientWrapper):
        self.binance_client = binance_client
        self.logger = logging.getLogger(__name__)
        self.active_positions: Dict[str, Position] = {}  # strategy_name -> Position
        self.position_history: List[Position] = []
        self.last_order_time = None  # Track when last order was placed

        # Thread safety for position management
        self._position_lock = threading.RLock()

        # Memory management - limit history size
        self.max_history_size = 1000

    def execute_signal(self, signal: TradingSignal, strategy_config: Dict) -> Optional[Position]:
        """Execute a trading signal with improved error handling"""
        try:
            # Validate inputs
            if not signal or not strategy_config:
                self.logger.error("Invalid signal or strategy config provided")
                return None

            # Check if strategy already has an active position
            strategy_name = strategy_config.get('name')
            symbol = strategy_config.get('symbol')

            if not strategy_name or not symbol:
                self.logger.error("Missing strategy name or symbol in config")
                return None

            signal_side = 'BUY' if signal.signal_type == SignalType.BUY else 'SELL'

            if strategy_name in self.active_positions:
                self.logger.info(f"Strategy {strategy_name} already has an active position")
                return None

            # Enhanced duplicate trade prevention: Check both bot's internal positions AND Binance positions
            for existing_strategy, existing_position in self.active_positions.items():
                if (existing_position.symbol == symbol and 
                    existing_position.side == signal_side):
                    self.logger.warning(f"❌ DUPLICATE TRADE PREVENTED | {strategy_name} | {symbol} | {signal_side} | Already have position in {existing_strategy}")
                    return None

            # CRITICAL: Also check if there's already a position on Binance for this symbol
            try:
                if self.binance_client.is_futures:
                    positions = self.binance_client.client.futures_position_information(symbol=symbol)
                    for position in positions:
                        position_amt = float(position.get('positionAmt', 0))
                        # Use stricter threshold to ignore tiny positions from previous trades
                        if abs(position_amt) > 0.001:
                            existing_side = 'BUY' if position_amt > 0 else 'SELL'
                            if existing_side == signal_side:
                                self.logger.warning(f"❌ DUPLICATE TRADE PREVENTED | {strategy_name} | {symbol} | {signal_side} | Position already exists on Binance: {position_amt}")
                                return None
                            else:
                                self.logger.warning(f"❌ OPPOSING TRADE PREVENTED | {strategy_name} | {symbol} | {signal_side} | Opposite position exists on Binance: {position_amt}")
                                return None
            except Exception as e:
                self.logger.error(f"Error checking Binance positions for duplicate prevention: {e}")
                # Continue execution despite error to avoid blocking legitimate trades

            # Calculate position size
            quantity = self._calculate_position_size(signal, strategy_config)
            if not quantity or quantity <= 0:
                self.logger.error(f"Invalid quantity calculated: {quantity}")
                return None

            # Set leverage before creating order
            leverage = strategy_config.get('leverage', 1)
            
            self.logger.info(f"🔧 SETTING LEVERAGE | {symbol} | Requested: {leverage}x | From Config: {strategy_config}")

            # Set leverage for the symbol
            try:
                self.logger.info(f"🔧 BINANCE LEVERAGE CALL | {symbol} | Setting to {leverage}x")
                leverage_result = self.binance_client.set_leverage(symbol, leverage)
                if leverage_result:
                    self.logger.info(f"✅ LEVERAGE SET SUCCESSFULLY | {symbol} | {leverage}x | Result: {leverage_result}")
                else:
                    self.logger.error(f"❌ LEVERAGE SET FAILED | {symbol} | {leverage}x | No result returned")
            except Exception as e:
                self.logger.error(f"❌ LEVERAGE SET ERROR | {symbol} | {leverage}x | Error: {e}")

            # Set margin type to CROSSED
            try:
                margin_result = self.binance_client.set_margin_type(symbol, "CROSSED")
                if margin_result:
                    self.logger.info(f"Margin type set to CROSS for {symbol}")
            except Exception as e:
                self.logger.warning(f"Could not set margin type for {symbol}: {e}")

            # Determine order side and position side for hedge mode
            side = 'BUY' if signal.signal_type == SignalType.BUY else 'SELL'
            position_side = 'LONG' if signal.signal_type == SignalType.BUY else 'SHORT'

            order_params = {
                'symbol': symbol,
                'side': side,
                'type': 'MARKET',
                'quantity': quantity,
                'positionSide': position_side  # LONG/SHORT for hedge mode
            }

            order_result = self.binance_client.create_order(**order_params)
            if not order_result:
                self.logger.error("Failed to create order")
                return None

            # Create position object
            position = Position(
                strategy_name=strategy_name,
                symbol=symbol,
                side=side,
                entry_price=signal.entry_price,
                quantity=quantity,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit,
                position_side=position_side,
                order_id=order_result.get('orderId'),
                entry_time=datetime.now(),
                status="OPEN"
            )
            
            # Store strategy config reference for exit condition evaluation
            position.strategy_config = strategy_config

            # Store active position with thread safety
            with self._position_lock:
                self.active_positions[strategy_name] = position

            # Register bot trade with anomaly detector to pause ghost detection
            if hasattr(self, 'anomaly_detector') and self.anomaly_detector:
                self.anomaly_detector.register_bot_trade(position.symbol, strategy_name)
                self.logger.debug(f"🔍 BOT TRADE REGISTERED: {position.symbol} | Anomaly detection paused for 120 seconds")

            # Log trade entry for analytics with confirmed trade ID
            self._log_trade_entry(position)

            # Log trade for validation purposes
            self._log_trade_for_validation(position)

            # Record the time of this order for ghost detection timing
            self.last_order_time = datetime.now()

            # Get strategy config for additional details
            timeframe = strategy_config.get('timeframe', 'N/A')
            margin = strategy_config.get('margin', 0.0)
            leverage = strategy_config.get('leverage', 1)
            
            # Calculate actual position value and margin used
            position_value_usdt = position.entry_price * position.quantity
            actual_margin_used = position_value_usdt / leverage
            
            # Get current indicator value based on strategy - this would be enhanced to receive actual values
            current_indicator = "N/A"
            if 'macd' in strategy_name.lower():
                current_indicator = "MACD: N/A"  # Placeholder - could be enhanced to show actual MACD values
            elif 'rsi' in strategy_name.lower():
                current_indicator = "RSI: N/A"  # Placeholder - could be enhanced to show actual RSI value
            
            # Position opened format with corrected margin display
            position_opened_message = f"""╔═══════════════════════════════════════════════════╗
║ ✅ POSITION OPENED                               ║
║ ⏰ {datetime.now().strftime('%H:%M:%S')}                                        ║
║                                                   ║
║ 🎯 Strategy: {strategy_name.upper()}                        ║
║ 💱 Symbol: {position.symbol}                              ║
║ 📊 Side: {position.side}                                   ║
║ ⏱️ Timeframe: {timeframe}                                ║
║ 💸 Margin Used: ${actual_margin_used:.1f} USDT                          ║
║ ⚡ Leverage: {leverage}x                                ║
║ 💵 Entry Price: ${position.entry_price:.4f}                                ║
║ 🛡️ Stop Loss: ${position.stop_loss:.4f}                                ║
║ 📈 Current {current_indicator}                         ║
║                                                   ║
╚═══════════════════════════════════════════════════╝"""
            self.logger.info(position_opened_message)
            return position

        except Exception as e:
            self.logger.error(f"Error executing signal: {e}")
            return None

    def _calculate_profit_loss(self, position: Position, current_price: float) -> Tuple[float, float]:
        """Calculate profit and loss for a position with validation"""
        try:
            if not position or not hasattr(position, 'entry_price'):
                return 0.0, 0.0

            entry_price = position.entry_price
            side = position.side
            quantity = position.quantity

            if not all([entry_price, side, quantity]) or current_price <= 0:
                return 0.0, 0.0

            # Calculate PnL based on position side
            if side == 'BUY':  # Long position
                pnl = (current_price - entry_price) * quantity
            else:  # Short position
                pnl = (entry_price - current_price) * quantity

            # Calculate PnL percentage against actual margin invested from strategy config
            margin_invested = 50.0  # Default margin
            if hasattr(position, 'strategy_config') and position.strategy_config:
                margin_invested = position.strategy_config.get('margin', 50.0)
            else:
                # Fallback: calculate from position value and leverage
                leverage = 5  # Default leverage
                position_value = entry_price * quantity
                margin_invested = position_value / leverage
            
            pnl_percentage = (pnl / margin_invested) * 100 if margin_invested != 0 else 0

            return pnl, pnl_percentage

        except Exception as e:
            self.logger.error(f"Error calculating PnL: {e}")
            return 0.0, 0.0

    def close_position(self, strategy_name: str, reason: str = "Manual close") -> dict:
        """Close an active position with improved error handling"""
        try:
            if strategy_name not in self.active_positions:
                self.logger.warning(f"No active position for strategy {strategy_name}")
                return {}

            position = self.active_positions[strategy_name]
            symbol = position.symbol

            # Fetch current price for accurate PnL calculation
            current_price = self.get_latest_price(symbol)
            if not current_price:
                self.logger.error(f"❌ Could not fetch current price for {symbol}")
                return {}

            # Calculate profit/loss
            pnl, pnl_percentage = self._calculate_profit_loss(position, current_price)

            # Create closing order (opposite side) with hedge mode support
            close_side = 'SELL' if position.side == 'BUY' else 'BUY'

            order_params = {
                'symbol': position.symbol,
                'side': close_side,
                'type': 'MARKET',
                'quantity': position.quantity,
                'positionSide': position.position_side  # Use stored position side
            }

            order_result = self.binance_client.create_order(**order_params)
            if not order_result:
                self.logger.error("Failed to create closing order")
                return {}

            # Log trade exit for analytics
            try:
                if position.trade_id:
                    from src.analytics.trade_logger import trade_logger
                    trade_logger.log_trade_exit(
                        trade_id=position.trade_id,
                        exit_price=current_price,
                        exit_reason=reason,
                        pnl_usdt=pnl,
                        pnl_percentage=pnl_percentage,
                        max_drawdown=0  # Could be calculated if tracking is implemented
                    )
                    
            except Exception as e:
                self.logger.error(f"❌ Error logging trade exit: {e}")

            # Calculate duration before updating anything
            duration_minutes = (datetime.now() - position.entry_time).total_seconds() / 60 if position.entry_time else 0
            
            # CRITICAL FIX: Update trade database when position closes
            try:
                from src.execution_engine.trade_database import TradeDatabase
                trade_db = TradeDatabase()
                trade_db.update_trade(position.trade_id, {
                    'trade_status': 'CLOSED',
                    'exit_price': current_price,
                    'exit_reason': reason,
                    'pnl_usdt': pnl,
                    'pnl_percentage': pnl_percentage,
                    'duration_minutes': duration_minutes
                })
                self.logger.debug(f"✅ Trade database updated for {position.trade_id}")
            except Exception as db_error:
                self.logger.error(f"❌ Error updating trade database: {db_error}")
            
            # Update position status
            position.status = "CLOSED"

            # Move to history and remove from active (with memory management)
            self._add_to_history(position)
            with self._position_lock:
                del self.active_positions[strategy_name]
            
            # Position closed format
            position_closed_message = f"""╔═══════════════════════════════════════════════════╗
║ 🔴 POSITION CLOSED                               ║
║ ⏰ {datetime.now().strftime('%H:%M:%S')}                                        ║
║                                                   ║
║ 🎯 Strategy: {strategy_name.upper()}                        ║
║ 💱 Symbol: {symbol}                              ║
║ 📊 Side: {position.side}                                   ║
║ 💵 Entry: ${position.entry_price:.4f}                                ║
║ 🚪 Exit: ${current_price:.4f}                                 ║
║ 💰 PnL: ${pnl:.2f} USDT ({pnl_percentage:+.2f}%)                     ║
║ 📝 Exit Reason: {reason}                 ║
║                                                   ║
╚═══════════════════════════════════════════════════╝"""
            self.logger.info(position_closed_message)

            return {
                'symbol': symbol,
                'pnl_usdt': pnl,
                'pnl_percentage': pnl_percentage,
                'exit_price': current_price,
                'exit_reason': reason,
                'duration_minutes': duration_minutes
            }

        except Exception as e:
            self.logger.error(f"Error closing position: {e}")
            return {}

    def _add_to_history(self, position: Position):
        """Add position to history with memory management"""
        try:
            self.position_history.append(position)

            # Limit history size to prevent memory issues
            if len(self.position_history) > self.max_history_size:
                # Remove oldest entries, keep last max_history_size entries
                self.position_history = self.position_history[-self.max_history_size:]
                self.logger.debug(f"Position history trimmed to {self.max_history_size} entries")

        except Exception as e:
            self.logger.error(f"Error adding position to history: {e}")

    def _calculate_position_size(self, signal: TradingSignal, strategy_config: Dict) -> float:
        """Calculate position size based on margin and leverage with improved precision"""
        try:
            margin = strategy_config.get('margin', 50.0)
            leverage = strategy_config.get('leverage', 5)

            self.logger.info(f"🔍 POSITION SIZE CALCULATION | Margin: ${margin} | Leverage: {leverage}x | Entry: ${signal.entry_price}")

            # Calculate base position size in quote currency (USDT)
            position_value_usdt = margin * leverage

            # Calculate quantity in base currency
            quantity = position_value_usdt / signal.entry_price

            # Apply symbol-specific precision for futures trading
            # Use strategy config symbol if signal symbol is empty
            config_symbol = strategy_config.get('symbol', '')
            actual_symbol = signal.symbol or config_symbol
            symbol_upper = actual_symbol.upper()

            self.logger.info(f"🔍 RAW CALCULATION | Symbol: {actual_symbol} | Position Value: ${position_value_usdt} | Raw Quantity: {quantity:.6f}")

            if 'SOLUSDT' in symbol_upper or 'SOL' in symbol_upper:
                # SOL futures uses 3 decimal places, minimum 0.001
                original_quantity = quantity
                quantity = round(quantity, 3)
                if quantity < 0.001:
                    quantity = 0.001
                self.logger.info(f"🔧 SOL PRECISION FIX | Original: {original_quantity:.6f} → Fixed: {quantity}")
            elif 'BTCUSDT' in symbol_upper or 'BTC' in symbol_upper:
                # BTC futures uses 3 decimal places, minimum 0.001
                original_quantity = quantity
                quantity = round(quantity, 3)
                if quantity < 0.001:
                    quantity = 0.001
                self.logger.info(f"🔧 BTC PRECISION FIX | Original: {original_quantity:.6f} → Fixed: {quantity}")
            else:
                # Default to 1 decimal place for most futures
                original_quantity = quantity
                quantity = round(quantity, 1)
                if quantity < 0.1:
                    quantity = 0.1
                self.logger.info(f"🔧 DEFAULT PRECISION | Original: {original_quantity:.6f} → Fixed: {quantity}")

            # Calculate what the actual margin will be with this quantity
            actual_position_value = quantity * signal.entry_price
            actual_margin_will_be = actual_position_value / leverage

            self.logger.info(f"✅ FINAL POSITION SIZE | Symbol: {signal.symbol} | Quantity: {quantity} | Actual Position Value: ${actual_position_value:.2f} | Actual Margin: ${actual_margin_will_be:.2f}")
            
            return quantity

        except Exception as e:
            self.logger.error(f"Error calculating position size: {e}")
            return 0.0

    def get_active_positions(self) -> Dict[str, Position]:
        """Get all active positions with thread safety"""
        with self._position_lock:
            return self.active_positions.copy()

    def get_position_history(self) -> List[Position]:
        """Get position history"""
        return self.position_history.copy()

    def has_position_on_symbol(self, symbol: str, side: str = None) -> bool:
        """Check if there's already a position on this symbol (optionally with specific side)"""
        try:
            for position in self.active_positions.values():
                if position.symbol == symbol:
                    if side is None or position.side == side:
                        return True
            return False
        except Exception as e:
            self.logger.error(f"Error checking position on symbol: {e}")
            return False

    def get_position_on_symbol(self, symbol: str) -> Optional[Position]:
        """Get existing position on symbol if any"""
        try:
            for position in self.active_positions.values():
                if position.symbol == symbol:
                    return position
            return None
        except Exception as e:
            self.logger.error(f"Error getting position on symbol: {e}")
            return None

    def clear_orphan_position(self, strategy_name: str) -> bool:
        """Clear an orphan position (bot opened, manually closed)"""
        try:
            if strategy_name not in self.active_positions:
                self.logger.warning(f"No active position to clear for strategy {strategy_name}")
                return False

            position = self.active_positions[strategy_name]

            # Mark as orphan and move to history
            position.status = "ORPHAN_CLEARED"
            self._add_to_history(position)

            # Remove from active positions
            del self.active_positions[strategy_name]

            self.logger.info(f"Orphan position cleared for {strategy_name}")
            return True

        except Exception as e:
            self.logger.error(f"Error clearing orphan position: {e}")
            return False

    def is_legitimate_bot_position(self, strategy_name: str, symbol: str, side: str, quantity: float, entry_price: float) -> Tuple[bool, Optional[str]]:
        """
        Validate if a position is a legitimate bot position by checking trade database
        Returns (is_legitimate, trade_id)
        """
        try:
            self.logger.debug(f"🔍 VALIDATING POSITION | {strategy_name} | {symbol} | {side} | Qty: {quantity} | Entry: ${entry_price}")

            # Simple and reliable: Check if trade ID exists in database
            try:
                from src.execution_engine.trade_database import TradeDatabase
                trade_db = TradeDatabase()
                trade_id = trade_db.find_trade_by_position(strategy_name, symbol, side, quantity, entry_price, tolerance=0.01)
            except ImportError as e:
                self.logger.warning(f"Trade database not available: {e}")
                return False, None
            except Exception as e:
                self.logger.warning(f"Error accessing trade database: {e}")
                return False, None

            if trade_id:
                self.logger.info(f"✅ POSITION VALIDATED | Trade ID: {trade_id} | {strategy_name} | {symbol}")
                return True, trade_id
            else:
                self.logger.warning(f"🚨 NO TRADE ID FOUND | {strategy_name} | {symbol} | Treating as manual position")
                return False, None

        except Exception as e:
            self.logger.error(f"Error validating position legitimacy: {e}")
            return False, None

    def set_anomaly_detector(self, anomaly_detector):
        """Set anomaly detector reference for ghost trade prevention"""
        try:
            self.anomaly_detector = anomaly_detector
            self.logger.debug("🔍 ANOMALY DETECTOR: Reference set in order manager")
        except Exception as e:
            self.logger.error(f"Error setting anomaly detector: {e}")

    def get_latest_price(self, symbol: str) -> Optional[float]:
        """Get latest price for a symbol from Binance with error handling"""
        try:
            ticker = self.binance_client.get_symbol_ticker(symbol)
            if ticker and 'price' in ticker:
                return float(ticker['price'])
            return None
        except Exception as e:
            self.logger.error(f"Error getting latest price for {symbol}: {e}")
            return None

    def _log_trade_entry(self, position: Position) -> None:
        """Log trade entry for analytics with error handling"""
        try:
            # Calculate margin used (position value / leverage)
            leverage = position.strategy_config.get('leverage', 5) if hasattr(position, 'strategy_config') and position.strategy_config else 5
            margin_used = (position.entry_price * position.quantity) / leverage

            # Log trade entry for analytics - trade_logger generates its own ID
            from src.analytics.trade_logger import trade_logger
            # Get actual leverage from strategy config
            actual_leverage = position.strategy_config.get('leverage', 5) if hasattr(position, 'strategy_config') and position.strategy_config else 5
            
            generated_trade_id = trade_logger.log_trade_entry(
                strategy_name=position.strategy_name,
                symbol=position.symbol,
                side=position.side,
                entry_price=position.entry_price,
                quantity=position.quantity,
                margin_used=margin_used,
                leverage=actual_leverage
            )

            # Store the generated trade ID in the position
            position.trade_id = generated_trade_id

            self.logger.info(f"📊 TRADE ENTRY LOGGED | ID: {generated_trade_id} | {position.strategy_name} | {position.symbol}")

        except Exception as e:
            self.logger.error(f"❌ Error logging trade entry: {e}")

    def _log_trade_for_validation(self, position: Position) -> None:
        """Log trade details for validation purposes with error handling"""
        try:
            trade_data = {
                'strategy_name': position.strategy_name,
                'symbol': position.symbol,
                'side': position.side,
                'entry_price': position.entry_price,
                'quantity': position.quantity,
                'stop_loss': position.stop_loss,
                'take_profit': position.take_profit,
                'position_side': position.position_side,
                'order_id': position.order_id,
                'entry_time': position.entry_time.isoformat() if position.entry_time else None,
                'status': position.status,
                'trade_id': position.trade_id,
            }
            self.logger.debug(f"📜 TRADE DATA: {json.dumps(trade_data, indent=2)}")
        except Exception as e:
            self.logger.error(f"Error logging trade validation data: {e}")