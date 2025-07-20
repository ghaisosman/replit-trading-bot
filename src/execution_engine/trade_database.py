
import json
import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

class TradeDatabase:
    """Simple trade database for tracking bot trades and validating positions"""

    def __init__(self, db_file: str = "trading_data/trade_database.json"):
        self.logger = logging.getLogger(__name__)
        self.db_file = db_file
        self.trades = {}
        self._ensure_directory()
        self._load_database()

    def _ensure_directory(self):
        """Ensure the trading_data directory exists"""
        os.makedirs(os.path.dirname(self.db_file), exist_ok=True)

    def _load_database(self):
        """Load trades from database file with bulletproof startup cleanup"""
        try:
            if os.path.exists(self.db_file):
                with open(self.db_file, 'r') as f:
                    data = json.load(f)
                    self.trades = data.get('trades', {})
                    self.logger.debug(f"Loaded {len(self.trades)} trades from database")

                    # Bulletproof cleanup on startup with Binance synchronization
                    self.logger.info(f"🔄 Running bulletproof database cleanup on startup...")
                    self.cleanup_stale_open_trades(hours=6, sync_with_binance=True)
            else:
                self.logger.info("Trade database file not found, starting with empty database")
                self.trades = {}
        except Exception as e:
            self.logger.error(f"Error loading trade database: {e}")
            self.trades = {}

    def _save_database(self):
        """Save trades to database file"""
        try:
            data = {
                'trades': self.trades,
                'last_updated': datetime.now().isoformat()
            }
            with open(self.db_file, 'w') as f:
                json.dump(data, f, indent=2)
            self.logger.debug(f"Saved {len(self.trades)} trades to database")
        except Exception as e:
            self.logger.error(f"Error saving trade database: {e}")

    def add_trade(self, trade_id: str, trade_data: Dict[str, Any]):
        """Add a trade to the database"""
        try:
            self.trades[trade_id] = trade_data
            self._save_database()
            self.logger.debug(f"Added trade {trade_id} to database")
        except Exception as e:
            self.logger.error(f"Error adding trade to database: {e}")

    def find_trade_by_position(self, strategy_name: str, symbol: str, side: str, 
                             quantity: float, entry_price: float, tolerance: float = 0.01) -> Optional[str]:
        """Find a trade ID by position details with tolerance for price/quantity matching"""
        try:
            self.logger.debug(f"Searching for trade: {strategy_name} | {symbol} | {side} | Qty: {quantity} | Entry: ${entry_price}")

            for trade_id, trade_data in self.trades.items():
                # Match strategy and symbol
                if (trade_data.get('strategy_name') == strategy_name and 
                    trade_data.get('symbol') == symbol and
                    trade_data.get('side') == side):

                    # Check quantity match with tolerance
                    db_quantity = trade_data.get('quantity', 0)
                    quantity_diff = abs(db_quantity - quantity)
                    quantity_tolerance = max(quantity * tolerance, 0.001)

                    # Check price match with tolerance
                    db_entry_price = trade_data.get('entry_price', 0)
                    price_diff = abs(db_entry_price - entry_price)
                    price_tolerance = max(entry_price * tolerance, 0.01)

                    if quantity_diff <= quantity_tolerance and price_diff <= price_tolerance:
                        self.logger.debug(f"Found matching trade: {trade_id}")
                        return trade_id
                    else:
                        self.logger.debug(f"Trade {trade_id} close but not exact match - "
                                        f"Qty diff: {quantity_diff:.6f} (tol: {quantity_tolerance:.6f}), "
                                        f"Price diff: {price_diff:.4f} (tol: {price_tolerance:.4f})")

            self.logger.debug(f"No matching trade found for {strategy_name} | {symbol}")
            return None

        except Exception as e:
            self.logger.error(f"Error searching for trade: {e}")
            return None

    def get_trade(self, trade_id: str) -> Optional[Dict[str, Any]]:
        """Get trade data by ID"""
        return self.trades.get(trade_id)

    def update_trade(self, trade_id: str, updates: Dict[str, Any]):
        """Update trade data"""
        try:
            if trade_id in self.trades:
                self.trades[trade_id].update(updates)
                self._save_database()
                self.logger.debug(f"Updated trade {trade_id}")
            else:
                self.logger.warning(f"Trade {trade_id} not found for update")
        except Exception as e:
            self.logger.error(f"Error updating trade: {e}")

    def get_all_trades(self) -> Dict[str, Dict[str, Any]]:
        """Get all trades"""
        return self.trades.copy()

    def cleanup_old_trades(self, days: int = 30):
        """Clean up trades older than specified days"""
        try:
            current_time = datetime.now()
            trades_to_remove = []

            for trade_id, trade_data in self.trades.items():
                entry_time_str = trade_data.get('entry_time') or trade_data.get('timestamp')
                if entry_time_str:
                    try:
                        entry_time = datetime.fromisoformat(entry_time_str.replace('Z', '+00:00'))
                        if (current_time - entry_time).days > days:
                            trades_to_remove.append(trade_id)
                    except ValueError:
                        continue

            for trade_id in trades_to_remove:
                del self.trades[trade_id]

            if trades_to_remove:
                self._save_database()
                self.logger.info(f"Cleaned up {len(trades_to_remove)} old trades")

        except Exception as e:
            self.logger.error(f"Error cleaning up old trades: {e}")

    def cleanup_stale_open_trades(self, hours: int = 6, sync_with_binance: bool = True):
        """Bulletproof cleanup of stale open trades with optional Binance synchronization"""
        try:
            current_time = datetime.now()
            trades_to_close = []

            # Get actual Binance positions if sync is enabled
            actual_binance_positions = {}
            if sync_with_binance:
                try:
                    from src.binance_client.client import BinanceClientWrapper
                    from src.config.global_config import global_config
                    
                    binance_client = BinanceClientWrapper()
                    if binance_client.is_futures:
                        account_info = binance_client.client.futures_account()
                        positions = account_info.get('positions', [])
                        
                        for position in positions:
                            symbol = position.get('symbol')
                            position_amt = float(position.get('positionAmt', 0))
                            if abs(position_amt) > 0.0001:  # Position exists
                                actual_binance_positions[symbol] = {
                                    'position_amt': position_amt,
                                    'entry_price': float(position.get('entryPrice', 0)),
                                    'side': 'BUY' if position_amt > 0 else 'SELL',
                                    'quantity': abs(position_amt)
                                }
                        
                        self.logger.debug(f"🔄 CLEANUP: Found {len(actual_binance_positions)} active Binance positions")
                except Exception as e:
                    self.logger.warning(f"Could not sync with Binance during cleanup: {e}")
                    sync_with_binance = False

            for trade_id, trade_data in self.trades.items():
                # Only process OPEN trades
                if trade_data.get('trade_status') == 'OPEN':
                    symbol = trade_data.get('symbol')
                    db_side = trade_data.get('side')
                    db_quantity = trade_data.get('quantity', 0)
                    
                    should_close = False
                    close_reason = 'Stale Trade - Auto Closed'
                    
                    # Method 1: Check if position exists on Binance (if sync enabled)
                    if sync_with_binance and symbol:
                        position_exists_on_binance = False
                        
                        if symbol in actual_binance_positions:
                            binance_pos = actual_binance_positions[symbol]
                            # Check if position details match with tolerance
                            quantity_match = abs(binance_pos['quantity'] - db_quantity) < 0.1
                            side_match = binance_pos['side'] == db_side
                            
                            if quantity_match and side_match:
                                position_exists_on_binance = True
                                self.logger.debug(f"🔄 CLEANUP: {trade_id} - Position confirmed on Binance")
                        
                        if not position_exists_on_binance:
                            should_close = True
                            close_reason = 'Position closed externally - Binance sync'
                            self.logger.info(f"🔄 CLEANUP: {trade_id} - No matching position on Binance")
                    
                    # Method 2: Check if trade is old (fallback or additional check)
                    if not should_close:
                        entry_time_str = trade_data.get('timestamp')
                        if entry_time_str:
                            try:
                                entry_time = datetime.fromisoformat(entry_time_str.replace('Z', '+00:00'))
                                hours_old = (current_time - entry_time).total_seconds() / 3600

                                if hours_old > hours:
                                    should_close = True
                                    close_reason = f'Stale Trade - Open for {hours_old:.1f} hours'
                                    self.logger.info(f"🔄 CLEANUP: {trade_id} - Trade is {hours_old:.1f} hours old")
                            except ValueError:
                                # If timestamp parsing fails, consider it stale
                                should_close = True
                                close_reason = 'Stale Trade - Invalid timestamp'
                    
                    # Close the trade if criteria met
                    if should_close:
                        trades_to_close.append((trade_id, close_reason))

            # Mark stale trades as closed
            for trade_id, close_reason in trades_to_close:
                self.trades[trade_id]['trade_status'] = 'CLOSED'
                self.trades[trade_id]['exit_reason'] = close_reason
                self.trades[trade_id]['exit_price'] = self.trades[trade_id].get('entry_price', 0)  # Use entry price as exit
                self.trades[trade_id]['pnl_usdt'] = 0.0
                self.trades[trade_id]['pnl_percentage'] = 0.0
                self.trades[trade_id]['duration_minutes'] = 0
                self.trades[trade_id]['closed_at'] = current_time.isoformat()

            if trades_to_close:
                self._save_database()
                self.logger.info(f"🔄 BULLETPROOF CLEANUP: Marked {len(trades_to_close)} stale trades as CLOSED")
                for trade_id, close_reason in trades_to_close:
                    self.logger.info(f"   ✅ {trade_id}: {close_reason}")
            else:
                self.logger.debug(f"🔄 CLEANUP: No stale trades found - database is clean")

        except Exception as e:
            self.logger.error(f"Error in bulletproof cleanup: {e}")
            import traceback
            self.logger.error(f"Cleanup error traceback: {traceback.format_exc()}")
