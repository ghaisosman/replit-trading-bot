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

    # Partial Take Profit Support
    original_quantity: Optional[float] = None  # Track original quantity
    remaining_quantity: Optional[float] = None  # Track remaining quantity
    partial_tp_taken: bool = False  # Track if partial TP was taken
    partial_tp_amount: float = 0.0  # Track partial TP profit in USDT
    partial_tp_percentage: float = 0.0  # Track partial TP profit as %
    actual_margin_used: Optional[float] = None  # Track actual margin used for this position

class OrderManager:
    """Manages order execution and position tracking"""

    def __init__(self, binance_client: BinanceClientWrapper, trade_logger, telegram_reporter=None):
        self.binance_client = binance_client
        self.trade_logger = trade_logger
        self.telegram_reporter = telegram_reporter
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
                # Check if this might be a minimum position value issue
                actual_position_value = quantity * signal.entry_price
                self.logger.error(f"❌ FAILED TO PLACE ORDER. BELOW MINIMUM POSITION VALUE | {symbol} | Position Value: ${actual_position_value:.2f} USDT | Quantity: {quantity} | Please increase margin in configuration")
                return None

            # Calculate actual margin used for this specific position
            position_value_usdt = signal.entry_price * quantity
            actual_margin_used = position_value_usdt / leverage

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
                status="OPEN",
                # Initialize partial TP fields
                original_quantity=quantity,
                remaining_quantity=quantity,
                partial_tp_taken=False,
                partial_tp_amount=0.0,
                partial_tp_percentage=0.0,
                actual_margin_used=actual_margin_used
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
            # self._log_trade_entry(position)

            # Generate Trade ID
            position.trade_id = self._generate_trade_id(strategy_name, symbol)

            # Single database recording with actual order confirmation data
            self._record_confirmed_trade(position, order_result, strategy_config)

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

            if not all([entry_price, side, quantity]) or current_price <= 0 or entry_price <= 0:
                return 0.0, 0.0

            # Calculate PnL based on position side
            if side == 'BUY':  # Long position
                pnl = (current_price - entry_price) * quantity
            else:  # Short position
                pnl = (entry_price - current_price) * quantity

            # FIXED: Calculate PnL percentage against actual margin invested for this position
            margin_invested = getattr(position, 'actual_margin_used', None)

            if margin_invested is None:
                # Fallback: try strategy config margin
                if hasattr(position, 'strategy_config') and position.strategy_config:
                    margin_invested = position.strategy_config.get('margin', 50.0)
                else:
                    # Last resort: calculate from position value and leverage
                    leverage = max(1, 5)  # Default leverage, ensure minimum 1
                    position_value = entry_price * quantity
                    margin_invested = position_value / leverage

            # Ensure margin_invested is not zero to prevent division by zero
            if margin_invested <= 0:
                margin_invested = 50.0  # Safe fallback

            pnl_percentage = (pnl / margin_invested) * 100

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

            # Calculate profit/loss for remaining position
            remaining_pnl, remaining_pnl_percentage = self._calculate_profit_loss(position, current_price)
            
            # Initialize pnl variables for consistent use throughout method
            pnl = remaining_pnl
            pnl_percentage = remaining_pnl_percentage

            # Calculate total combined PnL (partial + remaining)
            total_pnl = remaining_pnl + position.partial_tp_amount

            # Get actual margin invested for PnL percentage calculation
            margin_invested = getattr(position, 'actual_margin_used', None)
            if margin_invested is None:
                # Fallback to strategy config margin if actual margin not available
                margin_invested = position.strategy_config.get('margin', 50.0) if hasattr(position, 'strategy_config') and position.strategy_config else 50.0

            total_pnl_percentage = (total_pnl / margin_invested) * 100 if margin_invested > 0 else 0

            # First, check if position still exists on Binance before attempting to close
            try:
                if self.binance_client.is_futures:
                    binance_positions = self.binance_client.client.futures_position_information(symbol=symbol)
                    position_exists = False
                    for binance_pos in binance_positions:
                        pos_amt = float(binance_pos.get('positionAmt', 0))
                        if abs(pos_amt) > 0.000001:  # Position exists
                            position_exists = True
                            break

                    if not position_exists:
                        self.logger.warning(f"Position {symbol} already closed on Binance, updating bot records")
                        # Position already closed manually, just update records
                        pnl, pnl_percentage = self._calculate_profit_loss(position, current_price)

                        # Calculate duration
                        duration_minutes = (datetime.now() - position.entry_time).total_seconds() / 60 if position.entry_time else 0

                        # CRITICAL: Update database with manual closure info
                        try:
                            from src.execution_engine.trade_database import TradeDatabase
                            trade_db = TradeDatabase()

                            if position.trade_id:
                                trade_db.update_trade(position.trade_id, {
                                    'trade_status': 'CLOSED',
                                    'exit_price': current_price,
                                    'exit_reason': 'Manual Closure (Detected)',
                                    'pnl_usdt': pnl,
                                    'pnl_percentage': pnl_percentage,
                                    'duration_minutes': duration_minutes,
                                    'manually_closed': True
                                })
                                self.logger.info(f"✅ Database updated for manual closure: {position.trade_id}")
                        except Exception as db_error:
                            self.logger.error(f"❌ Failed to update database for manual closure: {db_error}")

                        # Update position status and move to history
                        position.status = "MANUALLY_CLOSED"
                        self._add_to_history(position)
                        with self._position_lock:
                            del self.active_positions[strategy_name]

                        self.logger.info(f"✅ Position {symbol} marked as manually closed with P&L: ${pnl:.2f} USDT")
                        return {
                            'symbol': symbol,
                            'pnl_usdt': total_pnl,
                            'pnl_percentage': total_pnl_percentage,
                            'exit_price': current_price,
                            'exit_reason': "Already closed manually",
                            'duration_minutes': duration_minutes,
                            'partial_tp_taken': position.partial_tp_taken,
                            'partial_tp_amount': position.partial_tp_amount
                        }

            except Exception as pos_check_error:
                self.logger.warning(f"Could not verify position existence: {pos_check_error}")

            # Create closing order (opposite side) with hedge mode support
            close_side = 'SELL' if position.side == 'BUY' else 'BUY'

            order_params = {
                'symbol': position.symbol,
                'side': close_side,
                'type': 'MARKET',
                'quantity': position.quantity,
                'positionSide': position.position_side  # Use stored position side
            }

            try:
                order_result = self.binance_client.create_order(**order_params)
                if not order_result:
                    self.logger.error("Failed to create closing order")
                    return {}
            except Exception as order_error:
                # Handle ReduceOnly error specifically
                if "-2022" in str(order_error):
                    self.logger.warning(f"ReduceOnly order rejected for {symbol} - position likely already closed")
                    # Position already closed, update records
                    position.status = "ALREADY_CLOSED"
                    self._add_to_history(position)
                    with self._position_lock:
                        del self.active_positions[strategy_name]

                    pnl, pnl_percentage = self._calculate_profit_loss(position, current_price)
                    return {
                        'symbol': symbol,
                        'pnl_usdt': total_pnl,
                        'pnl_percentage': total_pnl_percentage,
                        'exit_price': current_price,
                        'exit_reason': "Position already closed",
                        'duration_minutes': (datetime.now() - position.entry_time).total_seconds() / 60 if position.entry_time else 0,
                        'partial_tp_taken': position.partial_tp_taken,
                        'partial_tp_amount': position.partial_tp_amount
                    }
                else:
                    self.logger.error(f"Error creating closing order: {order_error}")
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
                self.logger.info(f"🔧 DATABASE CLOSE UPDATE | {position.trade_id} | Updating trade status to CLOSED")

                # Ensure we have a trade ID to update
                if position.trade_id:
                    update_success = trade_db.update_trade(position.trade_id, {
                        'trade_status': 'CLOSED',
                        'exit_price': current_price,
                        'exit_reason': reason,
                        'pnl_usdt': pnl,
                        'pnl_percentage': pnl_percentage,
                        'duration_minutes': duration_minutes
                    })
                    self.logger.info(f"🔧 DATABASE UPDATE RESULT | {position.trade_id} | Success: {update_success}")
                else:
                    # Fallback: Try to find and close any open trade for this position
                    matching_trade_id = trade_db.find_trade_by_position(
                        position.strategy_name, 
                        position.symbol, 
                        position.side, 
                        position.quantity, 
                        position.entry_price,
                        tolerance=0.05  # 5% tolerance
                    )

                    if matching_trade_id:
                        trade_db.update_trade(matching_trade_id, {
                            'trade_status': 'CLOSED',
                            'exit_price': current_price,
                            'exit_reason': reason,
                            'pnl_usdt': pnl,
                            'pnl_percentage': pnl_percentage,
                            'duration_minutes': duration_minutes
                        })
                        self.logger.info(f"✅ Found and closed matching trade in database: {matching_trade_id}")
                    else:
                        self.logger.warning(f"⚠️ No matching trade ID found in database for closed position {position.symbol}")

            except Exception as db_error:
                self.logger.error(f"❌ Error updating trade database: {db_error}")

            # Update position status
            position.status = "CLOSED"

            # Move to history and remove from active (with memory management)
            self._add_to_history(position)
            with self._position_lock:
                del self.active_positions[strategy_name]

            # Position closed format with partial TP info
            partial_tp_info = ""
            if position.partial_tp_taken:
                partial_tp_info = f"""║ 🎯 Partial TP: ${position.partial_tp_amount:.2f} USDT ({position.partial_tp_percentage:+.1f}%)        ║
║ 🔄 Remaining TP: ${remaining_pnl:.2f} USDT ({remaining_pnl_percentage:+.1f}%)       ║"""

            position_closed_message = f"""╔═══════════════════════════════════════════════════╗
║ 🔴 POSITION CLOSED                               ║
║ ⏰ {datetime.now().strftime('%H:%M:%S')}                                        ║
║                                                   ║
║ 🎯 Strategy: {strategy_name.upper()}                        ║
║ 💱 Symbol: {symbol}                              ║
║ 📊 Side: {position.side}                                   ║
║ 💵 Entry: ${position.entry_price:.4f}                                ║
║ 🚪 Exit: ${current_price:.4f}                                 ║{partial_tp_info}
║ 💰 Total PnL: ${total_pnl:.2f} USDT ({total_pnl_percentage:+.2f}%)               ║
║ 📝 Exit Reason: {reason}                 ║
║                                                   ║
╚═══════════════════════════════════════════════════╝"""
            self.logger.info(position_closed_message)

            # Log trade closure
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

            # Send Telegram notification for position closure
            try:
                if hasattr(self, 'telegram_reporter') and self.telegram_reporter:
                    position_data = {
                        'strategy_name': position.strategy_name,
                        'symbol': symbol,
                        'side': position.side,
                        'entry_price': position.entry_price,
                        'exit_price': current_price,
                        'quantity': position.quantity
                    }
                    self.telegram_reporter.report_position_closed(
                        position_data=position_data,
                        exit_reason=reason,
                        pnl=pnl
                    )
                    self.logger.info(f"📱 TELEGRAM: Position closure notification sent for {strategy_name}")
            except Exception as e:
                self.logger.error(f"❌ TELEGRAM: Failed to send position closure notification: {e}")

            return {
                'symbol': symbol,
                'pnl_usdt': total_pnl,
                'pnl_percentage': total_pnl_percentage,
                'exit_price': current_price,
                'exit_reason': reason,
                'duration_minutes': duration_minutes,
                'partial_tp_taken': position.partial_tp_taken,
                'partial_tp_amount': position.partial_tp_amount,
                'remaining_pnl': remaining_pnl  # For logging purposes
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

    def _get_symbol_info(self, symbol: str) -> Dict:
        """Get symbol trading rules from Binance with caching"""
        try:
            # Cache symbol info to avoid repeated API calls
            if not hasattr(self, '_symbol_info_cache'):
                self._symbol_info_cache = {}

            if symbol in self._symbol_info_cache:
                return self._symbol_info_cache[symbol]

            # Fetch exchange info from Binance
            if self.binance_client.is_futures:
                exchange_info = self.binance_client.client.futures_exchange_info()
            else:
                exchange_info = self.binance_client.client.get_exchange_info()

            # Find symbol info
            symbol_info = None
            for s in exchange_info['symbols']:
                if s['symbol'] == symbol:
                    symbol_info = s
                    break

            if symbol_info:
                # Extract relevant filters
                filters = {f['filterType']: f for f in symbol_info.get('filters', [])}

                # Get LOT_SIZE filter for quantity precision
                lot_size = filters.get('LOT_SIZE', {})
                min_qty = float(lot_size.get('minQty', 0.1))
                step_size = float(lot_size.get('stepSize', 0.1))

                # Calculate precision from step size
                precision = len(str(step_size).rstrip('0').split('.')[-1]) if '.' in str(step_size) else 0

                info = {
                    'min_qty': min_qty,
                    'step_size': step_size,
                    'precision': precision
                }

                self._symbol_info_cache[symbol] = info
                self.logger.debug(f"📋 SYMBOL INFO | {symbol} | Min: {min_qty} | Step: {step_size} | Precision: {precision}")
                return info

        except Exception as e:
            self.logger.warning(f"Could not fetch symbol info for {symbol}: {e}")

        # Fallback to hardcoded rules if API fails
        return self._get_fallback_symbol_info(symbol)

    def _get_fallback_symbol_info(self, symbol: str) -> Dict:
        """Fallback symbol info if API fails"""
        symbol_upper = symbol.upper()

        if 'ETH' in symbol_upper:
            # ETHUSDT minimum position size is 20 USDT, precision is 2 decimals
            return {'min_qty': 0.01, 'step_size': 0.01, 'precision': 2}
        elif 'SOL' in symbol_upper:
            return {'min_qty': 0.01, 'step_size': 0.01, 'precision': 2}
        elif 'BTC' in symbol_upper:
            return {'min_qty': 0.001, 'step_size': 0.001, 'precision': 3}
        else:
            return {'min_qty': 0.1, 'step_size': 0.1, 'precision': 1}

    def _calculate_position_size(self, signal: TradingSignal, strategy_config: Dict) -> float:
        """Calculate position size based on margin and leverage with improved accuracy"""
        try:
            margin = strategy_config.get('margin', 50.0)
            leverage = strategy_config.get('leverage', 5)

            self.logger.info(f"🔍 POSITION SIZE CALCULATION | Target Margin: ${margin} | Leverage: {leverage}x | Entry: ${signal.entry_price}")

            # Get symbol info first to understand constraints
            config_symbol = strategy_config.get('symbol', '')
            actual_symbol = signal.symbol or config_symbol
            symbol_info = self._get_symbol_info(actual_symbol)

            min_qty = symbol_info['min_qty']
            step_size = symbol_info['step_size']
            precision = strategy_config.get('decimals', symbol_info['precision'])

            # Method 1: Calculate ideal quantity based on exact margin
            target_position_value = margin * leverage
            ideal_quantity = target_position_value / signal.entry_price

            # Method 2: Smart rounding to minimize margin discrepancy
            # Try both rounding up and down, choose the one closest to target margin
            quantity_down = (ideal_quantity // step_size) * step_size
            quantity_up = quantity_down + step_size

            # Calculate actual margins for both options
            margin_down = (quantity_down * signal.entry_price) / leverage if quantity_down >= min_qty else float('inf')
            margin_up = (quantity_up * signal.entry_price) / leverage

            # Choose the quantity that gets closest to target margin
            margin_diff_down = abs(margin_down - margin) if margin_down != float('inf') else float('inf')
            margin_diff_up = abs(margin_up - margin)

            if margin_diff_down <= margin_diff_up and quantity_down >= min_qty:
                quantity = quantity_down
                chosen_direction = "DOWN"
            else:
                quantity = quantity_up
                chosen_direction = "UP"

            # Apply precision rounding
            quantity = round(quantity, precision)

            # Ensure minimum quantity (final safety check)
            if quantity < min_qty:
                quantity = min_qty
                chosen_direction = "MIN_QTY"
                self.logger.warning(f"⚠️ MARGIN ADJUSTMENT: Quantity increased to minimum {min_qty} - margin will be higher than configured")

            # Calculate actual values after rounding
            actual_position_value = quantity * signal.entry_price
            actual_margin_used = actual_position_value / leverage

            # Log the margin difference for transparency
            margin_difference = actual_margin_used - margin
            margin_difference_pct = (margin_difference / margin) * 100 if margin > 0 else 0

            self.logger.info(f"🔧 MARGIN CALCULATION RESULTS:")
            self.logger.info(f"   🎯 Target Margin: ${margin:.2f} USDT")
            self.logger.info(f"   💰 Actual Margin: ${actual_margin_used:.2f} USDT")
            self.logger.info(f"   📊 Difference: ${margin_difference:+.2f} USDT ({margin_difference_pct:+.1f}%)")
            self.logger.info(f"   📏 Quantity: {ideal_quantity:.6f} → {quantity} (rounded {chosen_direction})")
            self.logger.info(f"   💵 Position Value: ${actual_position_value:.2f} USDT")
            self.logger.info(f"   🔧 Step Size: {step_size}, Min Qty: {min_qty}, Precision: {precision}")

            # Store actual margin for later use in position object
            signal.actual_margin_used = actual_margin_used

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

    def set_anomaly_detector(self, anomaly_detector):
        """Set anomaly detector reference for ghost trade prevention"""
        try:
            self.anomaly_detector = anomaly_detector
            self.logger.debug("🔍 ANOMALY DETECTOR: Reference set in order manager")
        except Exception as e:
            self.logger.error(f"Error setting anomaly detector: {e}")

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
            self.logger.info(f"🔍 DEBUG: VALIDATING POSITION | {strategy_name} | {symbol} | {side} | Qty: {quantity} | Entry: ${entry_price}")

            # Check if trade ID exists in database with comprehensive tolerance
            try:
                from src.execution_engine.trade_database import TradeDatabase
                trade_db = TradeDatabase()

                # First try exact strategy match
                trade_id = trade_db.find_trade_by_position(strategy_name, symbol, side, quantity, entry_price, tolerance=0.05)

                if not trade_id:
                    # If no exact match, try searching all strategies (for recovered positions)
                    self.logger.info(f"🔍 DEBUG: No exact strategy match, searching all strategies for {symbol}")
                    trade_id = trade_db.find_trade_by_position('UNKNOWN', symbol, side, quantity, entry_price, tolerance=0.05)

                    if trade_id:
                        self.logger.info(f"🔍 DEBUG: Found matching trade in different strategy: {trade_id}")

            except ImportError as e:
                self.logger.warning(f"Trade database not available: {e}")
                return False, None
            except Exception as e:
                self.logger.warning(f"Error accessing trade database: {e}")
                return False, None

            if trade_id:
                self.logger.info(f"✅ DEBUG: POSITION VALIDATED | Trade ID: {trade_id} | {strategy_name} | {symbol}")
                return True, trade_id
            else:
                self.logger.warning(f"🚨 DEBUG: NO TRADE ID FOUND | {strategy_name} | {symbol} | Likely manual position")
                return False, None

        except Exception as e:
            self.logger.error(f"❌ Error validating position legitimacy: {e}")
            return False, None

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

    def _calculate_entry_indicators(self, symbol: str) -> dict:
        """Calculate technical indicators at trade entry"""
        try:
            # Get recent klines for indicator calculation
            klines = self.binance_client.client.futures_klines(
                symbol=symbol,
                interval='1h',
                limit=100
            )

            if not klines or len(klines) < 50:
                self.logger.warning(f"Insufficient data for indicators on {symbol}")
                return {}

            # Extract prices and volumes
            closes = [float(kline[4]) for kline in klines]
            volumes = [float(kline[5]) for kline in klines]

            indicators = {}

            # Calculate RSI
            if len(closes) >= 14:
                indicators['rsi'] = self._calculate_rsi(closes)

            # Calculate MACD
            if len(closes) >= 26:
                indicators['macd'] = self._calculate_simple_macd(closes)

            # Calculate SMAs
            if len(closes) >= 20:
                indicators['sma_20'] = sum(closes[-20:]) / 20
            if len(closes) >= 50:
                indicators['sma_50'] = sum(closes[-50:]) / 50

            # Volume analysis
            if volumes:
                indicators['volume'] = sum(volumes[-20:]) / min(20, len(volumes))

            # Signal strength (basic calculation)
            indicators['signal_strength'] = self._calculate_signal_strength(indicators)

            self.logger.info(f"📊 Calculated indicators for {symbol}: RSI={indicators.get('rsi', 'N/A')}, MACD={indicators.get('macd', 'N/A')}")
            return indicators

        except Exception as e:
            self.logger.error(f"Error calculating entry indicators for {symbol}: {e}")
            return {}

    def _analyze_market_conditions(self, symbol: str) -> dict:
        """Analyze current market conditions"""
        try:
            # Get recent price data
            klines = self.binance_client.client.futures_klines(
                symbol=symbol,
                interval='1h',
                limit=20
            )

            if not klines or len(klines) < 20:
                return {}

            closes = [float(kline[4]) for kline in klines]
            conditions = {}

            # Market trend analysis
            recent_trend = (closes[-1] - closes[-20]) / closes[-20]
            if recent_trend > 0.02:
                conditions['trend'] = 'BULLISH'
            elif recent_trend < -0.02:
                conditions['trend'] = 'BEARISH'
            else:
                conditions['trend'] = 'SIDEWAYS'

            # Volatility score
            price_changes = [abs(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes))]
            conditions['volatility'] = sum(price_changes) / len(price_changes)

            # Market phase (based on time)
            from datetime import datetime
            current_hour = datetime.now().hour
            if 8 <= current_hour <= 16:
                conditions['phase'] = 'LONDON'
            elif 13 <= current_hour <= 21:
                conditions['phase'] = 'NEW_YORK'
            else:
                conditions['phase'] = 'ASIAN'

            return conditions

        except Exception as e:
            self.logger.error(f"Error analyzing market conditions for {symbol}: {e}")
            return {}

    def _calculate_rsi(self, prices: list, period: int = 14) -> float:
        """Calculate RSI indicator"""
        try:
            if len(prices) < period + 1:
                return None

            gains, losses = [], []
            for i in range(1, len(prices)):
                change = prices[i] - prices[i-1]
                gains.append(max(change, 0))
                losses.append(max(-change, 0))

            if len(gains) < period:
                return None

            avg_gain = sum(gains[-period:]) / period
            avg_loss = sum(losses[-period:]) / period

            if avg_loss == 0:
                return 100

            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            return round(rsi, 2)

        except Exception:
            return None

    def _calculate_simple_macd(self, prices: list) -> float:
        """Calculate simplified MACD"""
        try:
            if len(prices) < 26:
                return None

            ema_12 = sum(prices[-12:]) / 12
            ema_26 = sum(prices[-26:]) / 26
            macd = ema_12 - ema_26
            return round(macd, 4)

        except Exception:
            return None

    def _calculate_signal_strength(self, indicators: dict) -> float:
        """Calculate signal strength based on indicators"""
        try:
            strength = 0.0
            total_weight = 0.0

            # RSI contribution
            rsi = indicators.get('rsi')
            if rsi is not None:
                if rsi < 30:  # Oversold
                    strength += 0.8
                elif rsi > 70:  # Overbought
                    strength += 0.8
                else:
                    strength += 0.3
                total_weight += 1.0

            # MACD contribution
            macd = indicators.get('macd')
            if macd is not None:
                strength += min(abs(macd) * 100, 1.0)  # Normalize MACD
                total_weight += 1.0

            # SMA trend contribution
            sma_20 = indicators.get('sma_20')
            sma_50 = indicators.get('sma_50')
            if sma_20 and sma_50:
                trend_strength = abs(sma_20 - sma_50) / sma_50
                strength += min(trend_strength * 10, 1.0)
                total_weight += 1.0

            return round(strength / max(total_weight, 1.0), 2)

        except Exception:
            return 0.0

    def _generate_trade_id(self, strategy_name: str, symbol: str) -> str:
        """Generate consistent trade ID"""
        return f"{strategy_name}_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def _record_confirmed_trade(self, position: Position, order_result: Dict, strategy_config: Dict):
        """Record confirmed trade in database ONLY, then sync to logger - Option 1 Implementation"""
        try:
            # Calculate comprehensive trade data with GUARANTEED margin calculation
            position_value_usdt = position.entry_price * position.quantity
            leverage = strategy_config.get('leverage', 1)

            # CRITICAL: Always calculate margin from position value and leverage
            actual_margin_used = position_value_usdt / leverage

            # Store the calculated margin in the position for consistency
            position.actual_margin_used = actual_margin_used

            self.logger.info(f"🔧 MARGIN CALCULATION | Position: ${position_value_usdt:.2f} | Leverage: {leverage}x | Margin: ${actual_margin_used:.2f}")

            # Validate margin is not zero
            if actual_margin_used <= 0:
                self.logger.error(f"❌ CRITICAL: Zero margin calculated for {position.trade_id}")
                actual_margin_used = strategy_config.get('margin', 50.0)  # Fallback
                self.logger.warning(f"🔄 Using fallback margin: ${actual_margin_used}")

            # Create complete trade data with actual order confirmation data
            complete_data = {
                'trade_id': position.trade_id,
                'strategy_name': position.strategy_name,
                'symbol': position.symbol,
                'side': position.side,
                'quantity': position.quantity,
                'entry_price': position.entry_price,
                'trade_status': 'OPEN',
                'position_value_usdt': position_value_usdt,
                'leverage': leverage,
                'margin_used': actual_margin_used,  # Guaranteed non-zero
                'stop_loss': position.stop_loss,
                'take_profit': position.take_profit,
                'order_id': order_result.get('orderId'),
                'position_side': position.position_side,
                'timestamp': position.entry_time.isoformat() if position.entry_time else None
            }

            # Calculate technical indicators at entry (non-blocking)
            try:
                technical_indicators = self._calculate_entry_indicators(position.symbol)
                complete_data.update(technical_indicators)
            except Exception as e:
                self.logger.warning(f"⚠️ Could not calculate indicators: {e}")

            # Analyze market conditions (non-blocking)
            try:
                market_conditions = self._analyze_market_conditions(position.symbol)
                complete_data.update(market_conditions)
            except Exception as e:
                self.logger.warning(f"⚠️ Could not analyze market conditions: {e}")

            # Record in database (single source of truth)
            self.logger.info(f"📝 RECORDING TRADE IN DATABASE | {position.trade_id} | Database is source of truth")
            try:
                from src.execution_engine.trade_database import TradeDatabase
                trade_db = TradeDatabase()
                self.logger.info(f"🔧 DATABASE INSTANCE CREATED | {position.trade_id}")
                db_success = trade_db.add_trade(position.trade_id, complete_data)
                self.logger.info(f"🔧 DATABASE ADD_TRADE CALLED | {position.trade_id} | Success: {db_success}")
            except Exception as db_import_error:
                self.logger.error(f"❌ DATABASE IMPORT/CREATION ERROR | {position.trade_id} | {db_import_error}")
                db_success = False

            if db_success:
                self.logger.info(f"✅ DATABASE RECORDING SUCCESS | {position.trade_id}")

                # Verify the trade was actually stored
                stored_trade = trade_db.get_trade(position.trade_id)
                if stored_trade:
                    self.logger.info(f"✅ DATABASE VERIFICATION SUCCESS | {position.trade_id} | Trade confirmed in database")

                    # Sync from database to trade logger (database → logger)
                    sync_success = trade_db.sync_trade_to_logger(position.trade_id)

                    if sync_success:
                        self.logger.info(f"✅ SYNC SUCCESS | {position.trade_id} | Database → Logger sync complete")
                    else:
                        self.logger.warning(f"⚠️ SYNC FAILED | {position.trade_id} | Database recorded but logger sync failed")
                else:
                    self.logger.error(f"❌ DATABASE VERIFICATION FAILED | {position.trade_id} | Trade not found after recording")
                    db_success = False  # Mark as failed since verification failed

            else:
                self.logger.error(f"❌ DATABASE RECORDING FAILED | {position.trade_id}")
                # Fallback: Try direct logger recording
                try:
                    from src.analytics.trade_logger import trade_logger
                    fallback_success = trade_logger.log_trade(complete_data)
                    if fallback_success:
                        self.logger.warning(f"⚠️ FALLBACK SUCCESS | {position.trade_id} | Recorded directly in logger")
                    else:
                        self.logger.error(f"❌ FALLBACK FAILED | {position.trade_id} | Both database and logger failed")
                except Exception as fallback_error:
                    self.logger.error(f"❌ FALLBACK ERROR | {position.trade_id} | {fallback_error}")

        except Exception as e:
            self.logger.error(f"❌ Error recording confirmed trade: {e}")
            import traceback
            self.logger.error(f"❌ Recording error traceback: {traceback.format_exc()}")



    def check_partial_take_profit(self, strategy_name: str, current_price: float) -> bool:
        """Check and execute partial take profit if conditions are met"""
        try:
            if strategy_name not in self.active_positions:
                return False

            position = self.active_positions[strategy_name]

            # Skip if partial TP already taken
            if position.partial_tp_taken:
                return False

            # Get strategy config for partial TP settings
            strategy_config = position.strategy_config
            if not strategy_config:
                return False

            # Get partial TP configuration
            partial_tp_pnl_threshold = strategy_config.get('partial_tp_pnl_threshold', 0.0)  # % of margin
            partial_tp_position_percentage = strategy_config.get('partial_tp_position_percentage', 0.0)  # % of position

            # Check if partial TP is actually enabled (both values must be > 0)
            if partial_tp_pnl_threshold <= 0 or partial_tp_position_percentage <= 0:
                return False  # Partial TP is disabled

            # Calculate current PnL and PnL percentage against margin invested
            pnl, pnl_percentage = self._calculate_profit_loss(position, current_price)

            # Check if partial TP threshold is reached
            if pnl_percentage >= partial_tp_pnl_threshold:
                self.logger.info(f"🎯 PARTIAL TAKE PROFIT TRIGGERED | {strategy_name} | PnL: {pnl_percentage:.1f}% >= {partial_tp_pnl_threshold}%")

                # Calculate quantity to close (percentage of original position)
                close_quantity = (position.original_quantity * partial_tp_position_percentage) / 100.0

                # Apply symbol precision
                symbol_info = self._get_symbol_info(position.symbol)
                precision = strategy_config.get('decimals', symbol_info['precision'])
                close_quantity = round(close_quantity, precision)

                # Ensure minimum quantity
                if close_quantity < symbol_info['min_qty']:
                    close_quantity = symbol_info['min_qty']

                # Ensure we don't close more than remaining quantity
                if close_quantity > position.remaining_quantity:
                    close_quantity = position.remaining_quantity

                # Execute partial close
                success = self._execute_partial_close(position, close_quantity, current_price)

                if success:
                    # Calculate partial profit
                    if position.side == 'BUY':
                        partial_profit = (current_price - position.entry_price) * close_quantity
                    else:
                        partial_profit = (position.entry_price - current_price) * close_quantity

                    # Get margin invested for percentage calculation
                    margin_invested = strategy_config.get('margin', 50.0)
                    partial_profit_percentage = (partial_profit / margin_invested) * 100

                    # Update position with partial TP data
                    position.partial_tp_taken = True
                    position.partial_tp_amount = partial_profit
                    position.partial_tp_percentage = partial_profit_percentage
                    position.remaining_quantity = position.quantity - close_quantity
                    position.quantity = position.remaining_quantity  # Update current quantity

                    # Send Telegram notification
                    self._send_partial_tp_notification(position, current_price, partial_profit, partial_profit_percentage)

                    self.logger.info(f"✅ PARTIAL TAKE PROFIT EXECUTED | {strategy_name} | Closed: {close_quantity} | Profit: ${partial_profit:.2f} ({partial_profit_percentage:+.1f}%) | Remaining: {position.remaining_quantity}")

                    return True

            return False

        except Exception as e:
            self.logger.error(f"Error checking partial take profit: {e}")
            return False

    def _execute_partial_close(self, position: Position, close_quantity: float, current_price: float) -> bool:
        """Execute partial position close"""
        try:
            # Create closing order (opposite side)
            close_side = 'SELL' if position.side == 'BUY' else 'BUY'

            order_params = {
                'symbol': position.symbol,
                'side': close_side,
                'type': 'MARKET',
                'quantity': close_quantity,
                'positionSide': position.position_side,
                'reduceOnly': True  # Ensure this is a reduce-only order
            }

            order_result = self.binance_client.create_order(**order_params)
            if order_result:
                self.logger.info(f"✅ PARTIAL CLOSE ORDER EXECUTED | {position.symbol} | Quantity: {close_quantity} | Price: ${current_price:.4f}")
                return True
            else:
                self.logger.error(f"❌ PARTIAL CLOSE ORDER FAILED | {position.symbol}")
                return False

        except Exception as e:
            self.logger.error(f"Error executing partial close: {e}")
            return False

    def _send_partial_tp_notification(self, position: Position, current_price: float, partial_profit: float, partial_profit_percentage: float):
        """Send Telegram notification for partial take profit"""
        try:
            if hasattr(self, 'telegram_reporter') and self.telegram_reporter:
                # Get current indicator value based on strategy
                current_indicator = "N/A"
                strategy_config = position.strategy_config

                if strategy_config and 'rsi' in position.strategy_name.lower():
                    # Try to get current RSI value - simplified for now
                    current_indicator = "RSI: N/A"  # Could be enhanced with actual RSI
                elif strategy_config and 'macd' in position.strategy_name.lower():
                    current_indicator = "MACD: N/A"  # Could be enhanced with actual MACD

                message = f"""🎯 **Partial Take Profit Taken**

Strategy: {position.strategy_name.upper()}
Symbol: {position.symbol}
Side: {position.side}
Entry: ${position.entry_price:.4f}
Current Price: ${current_price:.4f}
{current_indicator}

💰 Partial Take Profit: ${partial_profit:.2f} USDT ({partial_profit_percentage:+.1f}%)
📊 Rest of trade is ongoing

Remaining Position: {position.remaining_quantity} {position.symbol.replace('USDT', '')}"""

                # Send via Telegram
                self.telegram_reporter.send_message(message)
                self.logger.info(f"📱 TELEGRAM: Partial TP notification sent for {position.strategy_name}")

        except Exception as e:
            self.logger.error(f"❌ TELEGRAM: Failed to send partial TP notification: {e}")

    def _sync_database_to_logger(self, trade_id: str, trade_data: Dict) -> bool:
        """Sync trade from database to logger (database is source of truth)"""
        try:
            from src.execution_engine.trade_database import TradeDatabase

            # Get the trade from database as source of truth
            trade_db = TradeDatabase()
            db_trade = trade_db.get_trade(trade_id)

            if not db_trade:
                self.logger.error(f"❌ Trade {trade_id} not found in database for sync")
                return False

            # Use database sync method to sync to logger
            success = trade_db.sync_trade_to_logger(trade_id)

            if success:
                self.logger.info(f"✅ SYNCED TO LOGGER | {trade_id} | Database → Logger sync complete")
                return True
            else:
                self.logger.error(f"❌ FAILED TO SYNC TO LOGGER | {trade_id}")
                return False

        except Exception as e:
            self.logger.error(f"❌ Error syncing database to logger: {e}")
            return False

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

    def _validate_position_details(self, symbol: str, side: str, quantity: float, entry_price: float) -> bool:
        """Validate position details"""
        try:
            if not all([symbol, side, quantity, entry_price]):
                self.logger.error("Missing position details")
                return False
            return True
        except Exception as e:
            self.logger.error(f"Error validating position details: {e}")
            return False