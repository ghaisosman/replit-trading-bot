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
    """Simplified order manager for trading operations"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.active_orders = {}
        self.logger.info("📋 Order Manager initialized")
    
    def create_order(self, symbol: str, side: str, quantity: float, order_type: str = "MARKET") -> Optional[Dict[str, Any]]:
        """Create a new order"""
        try:
            order_id = f"order_{len(self.active_orders) + 1}"
            order = {
                "orderId": order_id,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "type": order_type,
                "status": "NEW",
                "timestamp": "2025-07-28T15:00:00.000Z"
            }
            
            self.active_orders[order_id] = order
            self.logger.info(f"✅ Created {side} order for {quantity} {symbol}")
            return order
            
        except Exception as e:
            self.logger.error(f"❌ Error creating order: {e}")
            return None
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an active order"""
        try:
            if order_id in self.active_orders:
                self.active_orders[order_id]["status"] = "CANCELED"
                self.logger.info(f"✅ Canceled order {order_id}")
                return True
            else:
                self.logger.warning(f"⚠️ Order {order_id} not found")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error canceling order: {e}")
            return False
    
    def get_active_orders(self) -> Dict[str, Any]:
        """Get all active orders"""
        return {k: v for k, v in self.active_orders.items() if v["status"] == "NEW"}
    
    def get_order_status(self, order_id: str) -> Optional[str]:
        """Get status of a specific order"""
        if order_id in self.active_orders:
            return self.active_orders[order_id]["status"]
        return None