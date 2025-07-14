import logging
from typing import Dict, List, Optional, Any
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

    def execute_signal(self, signal: TradingSignal, strategy_config: Dict) -> Optional[Position]:
        """Execute a trading signal"""
        try:
            # Check if strategy already has an active position
            strategy_name = strategy_config['name']
            if strategy_name in self.active_positions:
                self.logger.info(f"Strategy {strategy_name} already has an active position")
                return None

            # Calculate position size
            quantity = self._calculate_position_size(signal, strategy_config)
            if not quantity:
                return None

            # Set leverage before creating order
            leverage = strategy_config.get('leverage', 1)
            if not self._set_leverage(strategy_config['symbol'], leverage):
                self.logger.error(f"Failed to set leverage {leverage}x for {strategy_config['symbol']}")
                return None

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

            # Clean log message with essential trade info
            self.logger.info(f"✅ TRADE IN PROGRESS | {strategy_name.upper()} | {position.symbol} | Entry: ${position.entry_price:.4f} | PnL: $0.00 USDT (0.00%)")
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

            # Apply symbol-specific precision
            if symbol == 'BTCUSDT':
                quantity = round(quantity, 6)  # BTC requires 6 decimal places
            elif symbol == 'ETHUSDT':
                quantity = round(quantity, 3)  # ETH requires 3 decimal places
            elif symbol.endswith('USDT'):
                quantity = round(quantity, 3)  # Most USDT pairs use 3 decimal places
            else:
                quantity = round(quantity, 6)  # Default fallback

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