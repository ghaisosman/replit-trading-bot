import json
import csv
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import pandas as pd

@dataclass
class TradeRecord:
    """Complete trade record for analytics"""
    trade_id: str
    timestamp: datetime
    strategy_name: str
    symbol: str
    side: str  # BUY/SELL
    entry_price: float
    exit_price: Optional[float]
    quantity: float
    margin_used: float
    leverage: int
    position_value_usdt: float

    # Technical indicators at entry
    rsi_at_entry: Optional[float] = None
    macd_at_entry: Optional[float] = None
    sma_20_at_entry: Optional[float] = None
    sma_50_at_entry: Optional[float] = None
    volume_at_entry: Optional[float] = None

    # Trade outcome
    pnl_usdt: Optional[float] = None
    pnl_percentage: Optional[float] = None
    exit_reason: Optional[str] = None
    duration_minutes: Optional[int] = None

    # Market conditions
    market_trend: Optional[str] = None  # BULLISH/BEARISH/SIDEWAYS
    volatility_score: Optional[float] = None

    # Performance metrics
    risk_reward_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None

    # Additional metadata
    entry_signal_strength: Optional[float] = None
    market_phase: Optional[str] = None  # TRENDING/RANGING
    trade_status: str = "OPEN"  # OPEN/CLOSED/STOPPED

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON/CSV export"""
        data = asdict(self)
        # Convert datetime to ISO string
        data['timestamp'] = self.timestamp.isoformat()
        return data

class TradeLogger:
    """Comprehensive trade logging for ML analysis"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Create data directories
        self.data_dir = Path("trading_data")
        self.trades_dir = self.data_dir / "trades"
        self.reports_dir = self.data_dir / "reports"

        # Create directories if they don't exist
        self.data_dir.mkdir(exist_ok=True)
        self.trades_dir.mkdir(exist_ok=True)
        self.reports_dir.mkdir(exist_ok=True)

        # File paths
        self.trades_json_file = self.trades_dir / "all_trades.json"
        self.trades_csv_file = self.trades_dir / "all_trades.csv"

        # Load existing trades
        self.trades: List[TradeRecord] = []
        self.load_existing_trades()

    def load_existing_trades(self):
        """Load existing trades from JSON file"""
        try:
            if self.trades_json_file.exists():
                with open(self.trades_json_file, 'r') as f:
                    trades_data = json.load(f)

                for trade_data in trades_data:
                    # Convert timestamp back to datetime
                    trade_data['timestamp'] = datetime.fromisoformat(trade_data['timestamp'])
                    self.trades.append(TradeRecord(**trade_data))

                self.logger.info(f"📊 Loaded {len(self.trades)} existing trade records")
        except Exception as e:
            self.logger.error(f"❌ Error loading existing trades: {e}")

    def log_trade_entry(self, strategy_name: str, symbol: str, side: str, 
                       entry_price: float, quantity: float, margin_used: float, 
                       leverage: int, technical_indicators: Dict[str, float] = None,
                       market_conditions: Dict[str, Any] = None, trade_id: str = None) -> str:
        """Log trade entry with comprehensive data"""

        # Use provided trade_id or generate unique one
        if trade_id is None:
            trade_id = f"{strategy_name}_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Calculate position value
        position_value_usdt = entry_price * quantity

        # Create trade record
        trade_record = TradeRecord(
            trade_id=trade_id,
            timestamp=datetime.now(),
            strategy_name=strategy_name,
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            exit_price=None,
            quantity=quantity,
            margin_used=margin_used,
            leverage=leverage,
            position_value_usdt=position_value_usdt,
            trade_status="OPEN"
        )

        # Add technical indicators if provided
        if technical_indicators:
            trade_record.rsi_at_entry = technical_indicators.get('rsi')
            trade_record.macd_at_entry = technical_indicators.get('macd')
            trade_record.sma_20_at_entry = technical_indicators.get('sma_20')
            trade_record.sma_50_at_entry = technical_indicators.get('sma_50')
            trade_record.volume_at_entry = technical_indicators.get('volume')
            trade_record.entry_signal_strength = technical_indicators.get('signal_strength')

        # Add market conditions if provided
        if market_conditions:
            trade_record.market_trend = market_conditions.get('trend')
            trade_record.volatility_score = market_conditions.get('volatility')
            trade_record.market_phase = market_conditions.get('phase')

        # Validate trade record has all required data
        if not all([trade_record.trade_id, trade_record.strategy_name, trade_record.symbol, 
                   trade_record.side, trade_record.entry_price, trade_record.quantity]):
            self.logger.error(f"❌ Invalid trade record - missing required fields: {trade_record}")
            return None

        # Add to trades list
        self.trades.append(trade_record)

        # Save to files
        self._save_trades()

        self.logger.info(f"📝 TRADE ENTRY LOGGED | {trade_id} | {symbol} | {side} | ${entry_price:.4f}")
        self.logger.debug(f"📝 TRADE DETAILS: {trade_record.to_dict()}")

        # NOTE: No longer syncing to database here - database is now source of truth
        self.logger.debug(f"📝 LOGGER: Trade added to logger only (database sync handled elsewhere)")

        return trade_id

    def log_trade_exit(self, trade_id: str, exit_price: float, exit_reason: str,
                      pnl_usdt: float = None, pnl_percentage: float = None, max_drawdown: float = None,
                      exit_time: datetime = None):
        """Log trade exit and calculate final metrics"""

        # Find the trade record
        trade_record = None
        for trade in self.trades:
            if trade.trade_id == trade_id:
                trade_record = trade
                break

        if not trade_record:
            self.logger.error(f"❌ Trade record not found for ID: {trade_id}")
            return

        # Use provided exit_time or current time
        actual_exit_time = exit_time if exit_time else datetime.now()

        # Calculate accurate P&L if not provided
        if pnl_usdt is None:
            if trade_record.side == "BUY":
                # For BUY: profit when exit price > entry price
                pnl_usdt = (exit_price - trade_record.entry_price) * trade_record.quantity
            else:
                # For SELL: profit when exit price < entry price
                pnl_usdt = (trade_record.entry_price - exit_price) * trade_record.quantity

        # Calculate accurate percentage if not provided
        if pnl_percentage is None:
            pnl_percentage = (pnl_usdt / trade_record.position_value_usdt) * 100

        # Update trade record
        trade_record.exit_price = exit_price
        trade_record.exit_reason = exit_reason
        trade_record.pnl_usdt = pnl_usdt
        trade_record.pnl_percentage = pnl_percentage
        trade_record.trade_status = "CLOSED"
        trade_record.max_drawdown = max_drawdown

        # Calculate accurate duration
        duration = actual_exit_time - trade_record.timestamp
        trade_record.duration_minutes = int(duration.total_seconds() / 60)

        # Calculate risk-reward ratio
        if trade_record.side == "BUY":
            risk = trade_record.entry_price - (trade_record.entry_price * 0.95)  # Assuming 5% stop loss
            reward = exit_price - trade_record.entry_price
        else:
            risk = (trade_record.entry_price * 1.05) - trade_record.entry_price  # Assuming 5% stop loss
            reward = trade_record.entry_price - exit_price

        if risk > 0:
            trade_record.risk_reward_ratio = reward / risk

        # Save updated trades
        self._save_trades()

        # Sync updated trade to database
        self._sync_to_database(trade_id, trade_record)

        self.logger.info(f"📝 TRADE EXIT LOGGED | {trade_id} | PnL: ${pnl_usdt:.2f} ({pnl_percentage:+.2f}%) | Duration: {trade_record.duration_minutes}min")

    def _save_trades(self):
        """Save trades to both JSON and CSV files"""
        try:
            # Save to JSON
            trades_data = [trade.to_dict() for trade in self.trades]
            with open(self.trades_json_file, 'w') as f:
                json.dump(trades_data, f, indent=2, default=str)

            # Save to CSV
            if trades_data:
                df = pd.DataFrame(trades_data)
                df.to_csv(self.trades_csv_file, index=False)

        except Exception as e:
            self.logger.error(f"❌ Error saving trades: {e}")

    def get_daily_summary(self, date: datetime) -> Dict[str, Any]:
        """Generate daily trading summary"""
        start_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=1)

        # Filter trades for the day
        daily_trades = [
            trade for trade in self.trades
            if start_date <= trade.timestamp < end_date
        ]

        if not daily_trades:
            return {
                'date': date.strftime('%Y-%m-%d'),
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'total_pnl': 0,
                'win_rate': 0,
                'trades': []
            }

        # Calculate metrics
        closed_trades = [trade for trade in daily_trades if trade.trade_status == "CLOSED"]
        winning_trades = [trade for trade in closed_trades if trade.pnl_usdt and trade.pnl_usdt > 0]
        losing_trades = [trade for trade in closed_trades if trade.pnl_usdt and trade.pnl_usdt < 0]

        total_pnl = sum(trade.pnl_usdt for trade in closed_trades if trade.pnl_usdt)
        win_rate = (len(winning_trades) / len(closed_trades)) * 100 if closed_trades else 0

        # Strategy breakdown
        strategy_stats = {}
        for trade in daily_trades:
            strategy = trade.strategy_name
            if strategy not in strategy_stats:
                strategy_stats[strategy] = {
                    'trades': 0,
                    'pnl': 0,
                    'symbols': set()
                }
            strategy_stats[strategy]['trades'] += 1
            if trade.pnl_usdt:
                strategy_stats[strategy]['pnl'] += trade.pnl_usdt
            strategy_stats[strategy]['symbols'].add(trade.symbol)

        # Convert sets to lists for JSON serialization
        for strategy in strategy_stats:
            strategy_stats[strategy]['symbols'] = list(strategy_stats[strategy]['symbols'])

        return {
            'date': date.strftime('%Y-%m-%d'),
            'total_trades': len(daily_trades),
            'closed_trades': len(closed_trades),
            'open_trades': len(daily_trades) - len(closed_trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'total_pnl': total_pnl,
            'win_rate': win_rate,
            'average_trade_duration': sum(trade.duration_minutes for trade in closed_trades if trade.duration_minutes) / len(closed_trades) if closed_trades else 0,
            'strategy_breakdown': strategy_stats,
            'trades': [trade.to_dict() for trade in daily_trades]
        }

    def export_for_ml(self, output_file: str = None) -> str:
        """Export trades data for machine learning analysis"""
        if not output_file:
            output_file = self.trades_dir / f"ml_dataset_{datetime.now().strftime('%Y%m%d')}.csv"

        try:
            # Create ML-friendly dataset
            ml_data = []

            for trade in self.trades:
                if trade.trade_status == "CLOSED" and trade.pnl_usdt is not None:
                    ml_record = {
                        # Basic trade info
                        'strategy': trade.strategy_name,
                        'symbol': trade.symbol,
                        'side': trade.side,
                        'leverage': trade.leverage,
                        'position_size_usdt': trade.position_value_usdt,

                        # Technical indicators
                        'rsi_entry': trade.rsi_at_entry or 0,
                        'macd_entry': trade.macd_at_entry or 0,
                        'sma_20_entry': trade.sma_20_at_entry or 0,
                        'sma_50_entry': trade.sma_50_at_entry or 0,
                        'volume_entry': trade.volume_at_entry or 0,
                        'signal_strength': trade.entry_signal_strength or 0,

                        # Market conditions
                        'market_trend': trade.market_trend or 'UNKNOWN',
                        'volatility_score': trade.volatility_score or 0,
                        'market_phase': trade.market_phase or 'UNKNOWN',

                        # Time features
                        'hour_of_day': trade.timestamp.hour,
                        'day_of_week': trade.timestamp.weekday(),
                        'month': trade.timestamp.month,

                        # Trade outcome (target variables)
                        'pnl_usdt': trade.pnl_usdt,
                        'pnl_percentage': trade.pnl_percentage,
                        'duration_minutes': trade.duration_minutes or 0,
                        'was_profitable': 1 if trade.pnl_usdt > 0 else 0,
                        'risk_reward_ratio': trade.risk_reward_ratio or 0,
                        'max_drawdown': trade.max_drawdown or 0,
                        'exit_reason': trade.exit_reason or 'UNKNOWN'
                    }
                    ml_data.append(ml_record)

            # Save to CSV
            if ml_data:
                df = pd.DataFrame(ml_data)
                df.to_csv(output_file, index=False)
                self.logger.info(f"📊 ML dataset exported: {output_file} ({len(ml_data)} records)")
                return str(output_file)
            else:
                self.logger.warning("⚠️ No closed trades available for ML export")
                return None

        except Exception as e:
            self.logger.error(f"❌ Error exporting ML dataset: {e}")
            return None

    def _enhance_trade_with_indicators(self, trade_data: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance trade data with current technical indicators for ML"""
        try:
            enhanced_data = trade_data.copy()
            symbol = trade_data.get('symbol', '')

            if not symbol:
                return enhanced_data

            # Fetch current market data for indicators
            try:
                from src.binance_client.client import BinanceClientWrapper
                binance_client = BinanceClientWrapper()

                # Get recent klines for indicator calculation
                klines = binance_client.client.futures_klines(
                    symbol=symbol,
                    interval='1h',  # 1-hour timeframe
                    limit=100  # Get enough data for indicators
                )

                if klines and len(klines) >= 50:
                    # Extract prices
                    closes = [float(kline[4]) for kline in klines]  # Close prices
                    volumes = [float(kline[5]) for kline in klines]  # Volumes

                    # Calculate RSI (simplified)
                    rsi = self._calculate_rsi(closes)
                    enhanced_data['rsi_at_entry'] = rsi

                    # Calculate simple moving averages
                    if len(closes) >= 20:
                        sma_20 = sum(closes[-20:]) / 20
                        enhanced_data['sma_20_at_entry'] = sma_20

                    if len(closes) >= 50:
                        sma_50 = sum(closes[-50:]) / 50
                        enhanced_data['sma_50_at_entry'] = sma_50

                    # Calculate MACD (simplified)
                    macd = self._calculate_simple_macd(closes)
                    enhanced_data['macd_at_entry'] = macd

                    # Volume analysis
                    if volumes:
                        avg_volume = sum(volumes[-20:]) / min(20, len(volumes))
                        enhanced_data['volume_at_entry'] = avg_volume

                    # Market trend analysis
                    if len(closes) >= 20:
                        recent_trend = (closes[-1] - closes[-20]) / closes[-20]
                        if recent_trend > 0.02:
                            enhanced_data['market_trend'] = 'BULLISH'
                        elif recent_trend < -0.02:
                            enhanced_data['market_trend'] = 'BEARISH'
                        else:
                            enhanced_data['market_trend'] = 'SIDEWAYS'

                    # Volatility score (simplified)
                    if len(closes) >= 10:
                        price_changes = [abs(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, min(10, len(closes)))]
                        volatility = sum(price_changes) / len(price_changes)
                        enhanced_data['volatility_score'] = volatility

                    # Market phase
                    current_hour = datetime.now().hour
                    if 8 <= current_hour <= 16:
                        enhanced_data['market_phase'] = 'LONDON'
                    elif 13 <= current_hour <= 21:
                        enhanced_data['market_phase'] = 'NEW_YORK'
                    else:
                        enhanced_data['market_phase'] = 'ASIAN'

                    self.logger.info(f"📊 Enhanced trade data with indicators for {symbol}")

            except Exception as e:
                self.logger.warning(f"⚠️ Could not fetch indicators for {symbol}: {e}")

            return enhanced_data

        except Exception as e:
            self.logger.error(f"❌ Error enhancing trade data: {e}")
            return trade_data

    def _calculate_rsi(self, prices: List[float], period: int = 14) -> Optional[float]:
        """Calculate RSI indicator"""
        try:
            if len(prices) < period + 1:
                return None

            gains = []
            losses = []

            for i in range(1, len(prices)):
                change = prices[i] - prices[i-1]
                if change > 0:
                    gains.append(change)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(abs(change))

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

    def _calculate_simple_macd(self, prices: List[float]) -> Optional[float]:
        """Calculate simplified MACD"""
        try:
            if len(prices) < 26:
                return None

            # Simple EMA approximation
            ema_12 = sum(prices[-12:]) / 12
            ema_26 = sum(prices[-26:]) / 26

            macd = ema_12 - ema_26
            return round(macd, 4)

        except Exception:
            return None

    def log_trade(self, trade_data: Dict[str, Any]):
        """Log a complete trade record with duplicate prevention"""
        try:
            # Handle both dictionary and TradeRecord objects
            if hasattr(trade_data, 'to_dict'):
                trade_dict = trade_data.to_dict()
            else:
                trade_dict = trade_data.copy()

            trade_id = trade_dict.get('trade_id')
            if not trade_id:
                self.logger.error(f"❌ No trade_id provided for logging")
                return False

            # Check for duplicates first
            for existing_trade in self.trades:
                if existing_trade.trade_id == trade_id:
                    self.logger.warning(f"⚠️ Trade {trade_id} already exists in logger - skipping duplicate")
                    return True  # Return success since trade is already logged

            # Clean up any old field names that might cause issues
            if 'position_size_usdt' in trade_dict:
                if 'position_value_usdt' not in trade_dict:
                    trade_dict['position_value_usdt'] = trade_dict['position_size_usdt']
                del trade_dict['position_size_usdt']

            # Create TradeRecord from dictionary
            # Map common field variations
            field_mapping = {
                'entry_time': 'timestamp',
                'created_at': 'timestamp'
            }

            for old_field, new_field in field_mapping.items():
                if old_field in trade_dict and new_field not in trade_dict:
                    trade_dict[new_field] = trade_dict[old_field]

            # Parse timestamp if it's a string
            if isinstance(trade_dict.get('timestamp'), str):
                trade_dict['timestamp'] = datetime.fromisoformat(trade_dict['timestamp'].replace('Z', '+00:00'))
            elif trade_dict.get('timestamp') is None:
                trade_dict['timestamp'] = datetime.now()

            # Create TradeRecord with proper field validation
            required_fields = [
                'trade_id', 'timestamp', 'strategy_name', 'symbol', 'side',
                'entry_price', 'quantity', 'margin_used', 'leverage', 'position_value_usdt'
            ]

            missing_fields = [field for field in required_fields if field not in trade_dict]
            if missing_fields:
                self.logger.error(f"❌ Error logging trade: Missing required fields: {missing_fields}")
                return False

            trade_record = TradeRecord(**{k: v for k, v in trade_dict.items() 
                                        if k in TradeRecord.__dataclass_fields__})

            # Add to trades list and save
            self.trades.append(trade_record)
            self._save_trades()

            self.logger.info(f"📝 TRADE LOGGED FROM DATABASE | {trade_record.trade_id} | {trade_record.symbol} | {trade_record.side} | ${trade_record.entry_price:.4f}")
            self.logger.debug(f"📝 TRADE DETAILS: {trade_record.to_dict()}")

            return True

        except Exception as e:
            self.logger.error(f"❌ Error logging trade: {e}")
            return False

    def _save_trades(self):
        """Save trades to both JSON and CSV files"""
        try:
            # Save to JSON
            trades_data = [trade.to_dict() for trade in self.trades]
            with open(self.trades_json_file, 'w') as f:
                json.dump(trades_data, f, indent=2, default=str)

            # Save to CSV
            if trades_data:
                df = pd.DataFrame(trades_data)
                df.to_csv(self.trades_csv_file, index=False)

        except Exception as e:
            self.logger.error(f"❌ Error saving trades: {e}")

    def _save_to_file(self):
        """Save trades to file for persistence"""
        try:
            data = {
                'trades': [self._trade_to_dict(trade) for trade in self.trades],
                'last_updated': datetime.now().isoformat()
            }

            with open(self.log_file, 'w') as f:
                json.dump(data, f, indent=2)

            self.logger.debug(f"💾 Saved {len(self.trades)} trades to {self.log_file}")
        except Exception as e:
            self.logger.error(f"❌ Error saving trades to file: {e}")

    def _log_sync_failure(self, sync_type: str, trade_id: str, error_message: str):
        """Log synchronization failures for investigation."""
        log_message = f"❌ SYNC FAILURE: Type={sync_type}, TradeID={trade_id}, Error={error_message}"
        self.logger.error(log_message)

    def _sync_to_database(self, trade_id: str, trade_record: TradeRecord):
        """Sync trade record to database - simplified approach"""
        try:
            self.logger.info(f"🔍 DEBUG: Starting sync for trade {trade_id}")
            
            from src.execution_engine.trade_database import TradeDatabase
            trade_db = TradeDatabase()
            
            self.logger.info(f"🔍 DEBUG: Database loaded with {len(trade_db.trades)} existing trades")
            
            # Convert trade record to dict
            trade_dict = trade_record.to_dict()
            self.logger.info(f"🔍 DEBUG: Trade dict keys: {list(trade_dict.keys())}")
            
            # Ensure proper formatting for database
            if 'timestamp' in trade_dict and hasattr(trade_dict['timestamp'], 'isoformat'):
                original_timestamp = trade_dict['timestamp']
                trade_dict['timestamp'] = trade_dict['timestamp'].isoformat()
                self.logger.info(f"🔍 DEBUG: Converted timestamp from {original_timestamp} to {trade_dict['timestamp']}")
            
            # Check if trade already exists
            exists_before = trade_id in trade_db.trades
            self.logger.info(f"🔍 DEBUG: Trade exists before sync: {exists_before}")
            
            # Add or update in database
            if trade_id in trade_db.trades:
                self.logger.info(f"🔍 DEBUG: Updating existing trade {trade_id}")
                success = trade_db.update_trade(trade_id, trade_dict)
                self.logger.info(f"🔄 Updated trade {trade_id} in database - Result: {success}")
            else:
                self.logger.info(f"🔍 DEBUG: Adding new trade {trade_id}")
                success = trade_db.add_trade(trade_id, trade_dict)
                self.logger.info(f"➕ Added new trade {trade_id} to database - Result: {success}")
            
            # Verify the trade was actually stored
            exists_after = trade_id in trade_db.trades
            self.logger.info(f"🔍 DEBUG: Trade exists after sync: {exists_after}")
            
            if exists_after:
                stored_trade = trade_db.get_trade(trade_id)
                self.logger.info(f"🔍 DEBUG: Stored trade data keys: {list(stored_trade.keys()) if stored_trade else 'None'}")
            
            # Check database file size and modification
            import os
            if os.path.exists(trade_db.db_file):
                file_size = os.path.getsize(trade_db.db_file)
                self.logger.info(f"🔍 DEBUG: Database file size: {file_size} bytes")
            else:
                self.logger.error(f"🔍 DEBUG: Database file does not exist: {trade_db.db_file}")
            
            if success and exists_after:
                self.logger.debug(f"✅ Trade {trade_id} synced to database successfully")
                return True
            else:
                self.logger.error(f"❌ Failed to sync trade {trade_id} to database - Success: {success}, Exists: {exists_after}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error syncing trade {trade_id} to database: {e}")
            import traceback
            self.logger.error(f"🔍 DEBUG: Full traceback: {traceback.format_exc()}")
            return False

# Global trade logger instance
trade_logger = TradeLogger()

