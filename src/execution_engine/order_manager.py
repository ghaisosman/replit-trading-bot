import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import json
from src.binance_client.client import BinanceClientWrapper
from src.strategy_processor.signal_processor import TradingSignal, SignalType
from src.analytics.trade_logger import trade_logger

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

class OrderManager:
    """Manages order execution and position tracking"""

    def __init__(self, binance_client: BinanceClientWrapper):
        self.binance_client = binance_client
        self.logger = logging.getLogger(__name__)
        self.active_positions: Dict[str, Position] = {}  # strategy_name -> Position
        self.position_history: List[Position] = []
        self.last_order_time = None  # Track when last order was placed

    def execute_signal(self, signal: TradingSignal, strategy_config: Dict) -> Optional[Position]:
        """Execute a trading signal"""
        try:
            # Check if strategy already has an active position
            strategy_name = strategy_config['name']
            symbol = strategy_config['symbol']
            signal_side = 'BUY' if signal.signal_type == SignalType.BUY else 'SELL'
            
            if strategy_name in self.active_positions:
                self.logger.info(f"Strategy {strategy_name} already has an active position")
                return None
            
            # Additional check: Prevent duplicate trades on same symbol/side across all strategies
            for existing_strategy, existing_position in self.active_positions.items():
                if (existing_position.symbol == symbol and 
                    existing_position.side == signal_side):
                    self.logger.warning(f"❌ DUPLICATE TRADE PREVENTED | {strategy_name} | {symbol} | {signal_side} | Already have position in {existing_strategy}")
                    return None

            # Calculate position size
            quantity = self._calculate_position_size(signal, strategy_config)
            if not quantity:
                return None

            # Set leverage before creating order
            leverage = strategy_config.get('leverage', 1)
            symbol = strategy_config['symbol']

            # Set leverage for the symbol
            leverage_result = self.binance_client.set_leverage(symbol, leverage)
            if leverage_result:
                self.logger.info(f"Leverage set to {leverage}x for {symbol}")
            else:
                self.logger.warning(f"Could not set leverage for {symbol}")

            # Set margin type to CROSSED
            margin_result = self.binance_client.set_margin_type(symbol, "CROSSED")
            if margin_result:
                self.logger.info(f"Margin type set to CROSS for {symbol}")
            else:
                self.logger.warning(f"Could not set margin type for {symbol}")

            # Calculate position size

            # Determine order side and position side for hedge mode
            side = 'BUY' if signal.signal_type == SignalType.BUY else 'SELL'
            position_side = 'LONG' if signal.signal_type == SignalType.BUY else 'SHORT'

            order_params = {
                'symbol': strategy_config['symbol'],
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
                symbol=strategy_config['symbol'],
                side=order_params['side'],
                entry_price=signal.entry_price,
                quantity=quantity,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit,
                position_side=order_params['positionSide'],
                order_id=order_result.get('orderId'),
                entry_time=datetime.now(),
                status="OPEN"
            )

            # Store active position
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

            # Clean log message with essential trade info including trade ID
            self.logger.info(f"✅ TRADE IN PROGRESS | {strategy_name.upper()} | {position.symbol} | ID: {position.trade_id} | Entry: ${position.entry_price:.4f} | PnL: $0.00 USDT (0.00%)")
            return position

        except Exception as e:
            self.logger.error(f"Error executing signal: {e}")
            return None

    def _calculate_profit_loss(self, position: Position, current_price: float) -> Tuple[float, float]:
        """Calculate profit and loss for a position"""
        entry_price = position.entry_price
        side = position.side
        quantity = position.quantity

        # Calculate PnL based on position side
        if side == 'BUY':  # Long position
            pnl = (current_price - entry_price) * quantity
        else:  # Short position
            pnl = (entry_price - current_price) * quantity

        # Calculate PnL percentage
        pnl_percentage = (pnl / (entry_price * quantity)) * 100 if entry_price * quantity != 0 else 0

        return pnl, pnl_percentage

    def close_position(self, strategy_name: str, reason: str = "Manual close") -> dict:
        """Close an active position"""
        try:
            if strategy_name not in self.active_positions:
                self.logger.warning(f"No active position for strategy {strategy_name}")
                return {}

            position = self.active_positions[strategy_name]
            symbol = position.symbol

            # Fetch current price for accurate PnL calculation
            current_price = self.binance_client.get_latest_price(symbol)
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

            # Update position status
            position.status = "CLOSED"

            # Move to history and remove from active
            self.position_history.append(position)
            del self.active_positions[strategy_name]

            self.logger.info(f"🔴 POSITION CLOSED | {strategy_name} | {symbol} | PnL: ${pnl:.2f} USDT ({pnl_percentage:+.2f}%) | Duration: {position.entry_time - datetime.now():.1f}min")

            return {
                'symbol': symbol,
                'pnl_usdt': pnl,
                'pnl_percentage': pnl_percentage,
                'exit_price': current_price,
                'exit_reason': reason,
                'duration_minutes': (datetime.now() - position.entry_time).total_seconds() / 60
            }

        except Exception as e:
            self.logger.error(f"Error closing position: {e}")
            return {}

    def _calculate_position_size(self, signal: TradingSignal, strategy_config: Dict) -> Optional[float]:
        """Calculate position size based on margin and leverage"""
        try:
            margin = strategy_config['margin']
            leverage = strategy_config['leverage']
            symbol = strategy_config['symbol']

            # Calculate notional value
            notional_value = margin * leverage

            # Calculate quantity based on entry price
            quantity = notional_value / signal.entry_price

            # Apply symbol-specific precision based on Binance Futures requirements
            if symbol == 'BTCUSDT':
                quantity = round(quantity, 3)  # BTC Futures requires 3 decimal places
            elif symbol == 'ETHUSDT':
                quantity = round(quantity, 2)  # ETH Futures requires 2 decimal places  
            elif symbol == 'SOLUSDT':
                quantity = round(quantity, 0)  # SOL Futures requires whole numbers only
            elif symbol == 'ADAUSDT':
                quantity = round(quantity, 0)  # ADA requires whole numbers
            elif symbol.endswith('USDT'):
                quantity = round(quantity, 2)  # Most USDT pairs use 2 decimal places
            else:
                quantity = round(quantity, 3)  # Default fallback

            self.logger.info(f"Calculated position size for {symbol}: {quantity}")

            return quantity

        except Exception as e:
            self.logger.error(f"Error calculating position size: {e}")
            return None

    def get_active_positions(self) -> Dict[str, Position]:
        """Get all active positions"""
        return self.active_positions.copy()

    def get_position_history(self) -> List[Position]:
        """Get position history"""
        return self.position_history.copy()
    
    def has_position_on_symbol(self, symbol: str, side: str = None) -> bool:
        """Check if there's already a position on this symbol (optionally with specific side)"""
        for position in self.active_positions.values():
            if position.symbol == symbol:
                if side is None or position.side == side:
                    return True
        return False
    
    def get_position_on_symbol(self, symbol: str) -> Optional[Position]:
        """Get existing position on symbol if any"""
        for position in self.active_positions.values():
            if position.symbol == symbol:
                return position
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
            self.position_history.append(position)

            # Remove from active positions
            del self.active_positions[strategy_name]

            self.logger.info(f"Orphan position cleared for {strategy_name}")
            return True

        except Exception as e:
            self.logger.error(f"Error clearing orphan position: {e}")
            return False

    def _set_leverage(self, symbol: str, leverage: int) -> bool:
        """Set leverage for a symbol on Binance Futures"""
        try:
            result = self.binance_client.set_leverage(symbol=symbol, leverage=leverage)

            if result:
                self.logger.info(f"✅ Set leverage {leverage}x for {symbol}")
                return True
            else:
                # For spot trading, leverage setting returns None but shouldn't block orders
                self.logger.info(f"Leverage setting not applicable for {symbol}")
                return True

        except Exception as e:
            self.logger.error(f"Error setting leverage {leverage}x for {symbol}: {e}")
            return False

    def clear_orphan_position(self, strategy_name: str) -> None:
        """Clear orphan position for a strategy"""
        if strategy_name in self.active_positions:
            del self.active_positions[strategy_name]
            self.logger.info(f"🧹 ORPHAN POSITION CLEARED | {strategy_name} | Strategy can trade again")

    def is_legitimate_bot_position(self, strategy_name: str, symbol: str, side: str, quantity: float, entry_price: float) -> Tuple[bool, Optional[str]]:
        """
        Validate if a position is a legitimate bot position by checking trade database
        Returns (is_legitimate, trade_id)
        """
        try:
            self.logger.debug(f"🔍 VALIDATING POSITION | {strategy_name} | {symbol} | {side} | Qty: {quantity} | Entry: ${entry_price}")

            # Simple and reliable: Check if trade ID exists in database
            try:
                from src.execution_engine.trade_database import trade_db
                trade_id = trade_db.find_trade_by_position(strategy_name, symbol, side, quantity, entry_price, tolerance=0.01)
            except ImportError as e:
                self.logger.error(f"Could not import trade_database: {e}")
                return False, None
            except Exception as e:
                self.logger.error(f"Error accessing trade database: {e}")
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

    def _register_bot_position_with_monitor(self, position: Position) -> None:
        """Register bot position with trade monitor to prevent ghost trade detection"""
        try:
            # This method will be called by the bot manager to set the trade monitor reference
            if hasattr(self, 'trade_monitor') and self.trade_monitor:
                self.trade_monitor.register_bot_position(position)
                self.logger.debug(f"🔍 POSITION REGISTERED: {position.strategy_name} | {position.symbol} | Registered with trade monitor")
            else:
                self.logger.debug(f"🔍 POSITION REGISTRATION: Trade monitor not available yet for {position.strategy_name}")
        except Exception as e:
            self.logger.error(f"Error registering bot position with monitor: {e}")

    def set_trade_monitor(self, trade_monitor) -> None:
        """Set trade monitor reference for position registration"""
        self.trade_monitor = trade_monitor
        self.logger.debug("🔍 TRADE MONITOR: Reference set in order manager")

    def set_anomaly_detector(self, anomaly_detector):
        """Set anomaly detector reference for ghost trade prevention"""
        self.anomaly_detector = anomaly_detector
        self.logger.debug("🔍 ANOMALY DETECTOR: Reference set in order manager")

    def get_latest_price(self, symbol: str) -> Optional[float]:
        """Get latest price for a symbol from Binance"""
        try:
            ticker = self.binance_client.get_symbol_ticker(symbol)
            if ticker and 'price' in ticker:
                return float(ticker['price'])
            return None
        except Exception as e:
            self.logger.error(f"Error getting latest price for {symbol}: {e}")
            return None

    def _log_trade_entry(self, position: Position) -> None:
        """Log trade entry for analytics"""
        try:
            # Calculate margin used (position value / leverage)
            margin_used = (position.entry_price * position.quantity) / 1  # Default leverage if not stored
            
            # Log trade entry for analytics - trade_logger generates its own ID
            generated_trade_id = trade_logger.log_trade_entry(
                strategy_name=position.strategy_name,
                symbol=position.symbol,
                side=position.side,
                entry_price=position.entry_price,
                quantity=position.quantity,
                margin_used=margin_used,
                leverage=1  # Default leverage, could be enhanced to store actual leverage
            )
            
            # Store the generated trade ID in the position
            position.trade_id = generated_trade_id
            
            self.logger.info(f"📊 TRADE ENTRY LOGGED | ID: {generated_trade_id} | {position.strategy_name} | {position.symbol}")

        except Exception as e:
            self.logger.error(f"❌ Error logging trade entry: {e}")

    def _log_trade_for_validation(self, position: Position) -> None:
        """Log trade details for validation purposes (e.g., to match with Binance trades)"""
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
            self.logger.error(f"❌ Error logging trade data: {e}")