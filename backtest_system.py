
#!/usr/bin/env python3
"""
Comprehensive Backtesting System
Tests strategies with real historical data and strategy-specific configurations
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
import json
from pathlib import Path
import asyncio
import logging

# Add src to path for imports
sys.path.append('src')

from src.binance_client.client import BinanceClientWrapper
from src.data_fetcher.price_fetcher import PriceFetcher
from src.strategy_processor.signal_processor import SignalProcessor, TradingSignal, SignalType
from src.execution_engine.strategies.macd_divergence_strategy import MACDDivergenceStrategy
from src.execution_engine.strategies.engulfing_pattern_strategy import EngulfingPatternStrategy

class BacktestEngine:
    """Comprehensive backtesting engine for all strategies"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.binance_client = BinanceClientWrapper()
        self.price_fetcher = PriceFetcher(self.binance_client)
        self.signal_processor = SignalProcessor()
        
        # Backtest results storage
        self.results = {
            'trades': [],
            'summary': {},
            'strategy_performance': {}
        }
        
        # Strategy configurations templates
        self.strategy_configs = {
            'rsi_oversold': {
                'name': 'rsi_oversold',
                'symbol': 'BTCUSDT',
                'margin': 50.0,
                'leverage': 5,
                'timeframe': '15m',
                'max_loss_pct': 10.0,
                'assessment_interval': 60,
                'cooldown_period': 300,
                'decimals': 3,
                'rsi_period': 14,
                'rsi_long_entry': 30,
                'rsi_long_exit': 70,
                'rsi_short_entry': 70,
                'rsi_short_exit': 30,
                'partial_tp_pnl_threshold': 0.0,
                'partial_tp_position_percentage': 0.0
            },
            'macd_divergence': {
                'name': 'macd_divergence',
                'symbol': 'BTCUSDT',
                'margin': 50.0,
                'leverage': 5,
                'timeframe': '15m',
                'max_loss_pct': 10.0,
                'assessment_interval': 30,
                'cooldown_period': 300,
                'decimals': 3,
                'macd_fast': 12,
                'macd_slow': 26,
                'macd_signal': 9,
                'min_histogram_threshold': 0.0001,
                'macd_entry_threshold': 0.0015,
                'macd_exit_threshold': 0.002,
                'confirmation_candles': 1,
                'divergence_strength_min': 0.6,
                'histogram_divergence_lookback': 10,
                'price_divergence_lookback': 10
            },
            'engulfing_pattern': {
                'name': 'engulfing_pattern',
                'symbol': 'BTCUSDT',
                'margin': 50.0,
                'leverage': 5,
                'timeframe': '1h',
                'max_loss_pct': 10.0,
                'assessment_interval': 120,
                'cooldown_period': 600,
                'decimals': 3,
                'rsi_period': 14,
                'rsi_threshold': 50,
                'rsi_long_exit': 70,
                'rsi_short_exit': 30,
                'stable_candle_ratio': 0.5,
                'price_lookback_bars': 5,
                'partial_tp_pnl_threshold': 0.0,
                'partial_tp_position_percentage': 0.0
            },
            'smart_money': {
                'name': 'smart_money',
                'symbol': 'ETHUSDT',
                'margin': 75.0,
                'leverage': 3,
                'timeframe': '15m',
                'max_loss_pct': 15.0,
                'assessment_interval': 45,
                'cooldown_period': 900,
                'decimals': 2,
                'swing_lookback_period': 25,
                'sweep_threshold_pct': 0.1,
                'reversion_candles': 3,
                'volume_spike_multiplier': 2.0,
                'min_swing_distance_pct': 1.0
            }
        }

    def get_historical_data(self, symbol: str, interval: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Get historical data for backtesting period"""
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            
            # Convert to milliseconds
            start_ms = int(start_dt.timestamp() * 1000)
            end_ms = int(end_dt.timestamp() * 1000)
            
            # Get historical data in chunks (Binance limit is 1000 candles)
            all_klines = []
            current_start = start_ms
            
            # Calculate interval in milliseconds
            interval_ms = self._interval_to_ms(interval)
            
            while current_start < end_ms:
                current_end = min(current_start + (1000 * interval_ms), end_ms)
                
                klines = self.binance_client.get_historical_klines(
                    symbol=symbol,
                    interval=interval,
                    start_str=current_start,
                    end_str=current_end,
                    limit=1000
                )
                
                if not klines:
                    break
                    
                all_klines.extend(klines)
                current_start = current_end
                
                # Add small delay to avoid rate limits
                import time
                time.sleep(0.1)
            
            if not all_klines:
                self.logger.error(f"No historical data found for {symbol} {interval}")
                return None
            
            # Convert to DataFrame
            df = pd.DataFrame(all_klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            
            # Convert data types
            numeric_columns = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # Keep only OHLCV columns
            df = df[['open', 'high', 'low', 'close', 'volume']]
            
            # Calculate indicators using the same method as live trading
            df = self.price_fetcher.calculate_indicators(df)
            
            self.logger.info(f"✅ Historical data loaded: {len(df)} candles from {start_date} to {end_date}")
            return df
            
        except Exception as e:
            self.logger.error(f"Error getting historical data: {e}")
            return None

    def _interval_to_ms(self, interval: str) -> int:
        """Convert interval string to milliseconds"""
        interval_map = {
            '1m': 60 * 1000,
            '3m': 3 * 60 * 1000,
            '5m': 5 * 60 * 1000,
            '15m': 15 * 60 * 1000,
            '30m': 30 * 60 * 1000,
            '1h': 60 * 60 * 1000,
            '2h': 2 * 60 * 60 * 1000,
            '4h': 4 * 60 * 60 * 1000,
            '6h': 6 * 60 * 60 * 1000,
            '8h': 8 * 60 * 60 * 1000,
            '12h': 12 * 60 * 60 * 1000,
            '1d': 24 * 60 * 60 * 1000
        }
        return interval_map.get(interval, 15 * 60 * 1000)

    def backtest_strategy(self, strategy_name: str, config: Dict[str, Any], start_date: str, end_date: str) -> Dict[str, Any]:
        """Backtest a specific strategy with given configuration"""
        try:
            self.logger.info(f"🚀 Starting backtest for {strategy_name}")
            self.logger.info(f"📅 Period: {start_date} to {end_date}")
            self.logger.info(f"📊 Config: {config}")
            
            # Get historical data
            symbol = config['symbol']
            timeframe = config['timeframe']
            
            df = self.get_historical_data(symbol, timeframe, start_date, end_date)
            if df is None or df.empty:
                return {'error': f'No historical data available for {symbol}'}
            
            # Initialize strategy-specific handler
            strategy_handler = self._get_strategy_handler(strategy_name, config)
            
            # Backtest variables
            trades = []
            current_position = None
            last_trade_exit_time = None
            cooldown_period = timedelta(seconds=config.get('cooldown_period', 300))
            
            # Process each candle
            for i in range(50, len(df)):  # Start from 50 to ensure indicators are calculated
                current_time = df.index[i]
                current_data = df.iloc[:i+1]  # Data up to current candle
                current_price = df.iloc[i]['close']
                
                # Skip if in cooldown period
                if last_trade_exit_time and current_time < last_trade_exit_time + cooldown_period:
                    continue
                
                # Check for exit conditions if we have a position
                if current_position:
                    exit_result = self._check_exit_conditions(
                        current_position, current_data, current_price, strategy_handler, config
                    )
                    
                    if exit_result:
                        # Close position
                        trade_result = self._close_position(
                            current_position, current_price, current_time, exit_result['reason']
                        )
                        trades.append(trade_result)
                        current_position = None
                        last_trade_exit_time = current_time
                        
                        self.logger.info(f"📊 Trade closed: {trade_result['exit_reason']} | PnL: ${trade_result['pnl_usdt']:.2f}")
                        continue
                
                # Check for entry conditions if no position
                if not current_position:
                    entry_signal = self._check_entry_conditions(current_data, strategy_handler, config)
                    
                    if entry_signal:
                        # Open position
                        current_position = self._open_position(
                            entry_signal, current_price, current_time, config
                        )
                        
                        self.logger.info(f"🟢 Position opened: {entry_signal.signal_type.value} | Entry: ${current_price:.4f} | Reason: {entry_signal.reason}")
            
            # Close any remaining position at the end
            if current_position:
                final_price = df.iloc[-1]['close']
                final_time = df.index[-1]
                trade_result = self._close_position(
                    current_position, final_price, final_time, "End of backtest period"
                )
                trades.append(trade_result)
            
            # Calculate strategy performance
            performance = self._calculate_performance(trades, config)
            
            return {
                'strategy_name': strategy_name,
                'symbol': symbol,
                'timeframe': timeframe,
                'period': f"{start_date} to {end_date}",
                'config': config,
                'trades': trades,
                'performance': performance,
                'total_candles': len(df),
                'data_range': f"{df.index[0]} to {df.index[-1]}"
            }
            
        except Exception as e:
            self.logger.error(f"Error in backtest: {e}")
            import traceback
            traceback.print_exc()
            return {'error': str(e)}

    def _get_strategy_handler(self, strategy_name: str, config: Dict[str, Any]):
        """Get strategy-specific handler"""
        if 'macd' in strategy_name.lower():
            return MACDDivergenceStrategy(strategy_name, config)
        elif 'engulfing' in strategy_name.lower():
            return EngulfingPatternStrategy(strategy_name, config)
        elif 'smart_money' in strategy_name.lower():
            # Import Smart Money strategy if available
            try:
                from src.execution_engine.strategies.smart_money_strategy import SmartMoneyStrategy
                return SmartMoneyStrategy(strategy_name, config)
            except ImportError:
                return None
        else:
            # RSI and other strategies use signal processor
            return None

    def _check_entry_conditions(self, df: pd.DataFrame, strategy_handler, config: Dict[str, Any]) -> Optional[TradingSignal]:
        """Check entry conditions for strategy"""
        try:
            if strategy_handler and hasattr(strategy_handler, 'evaluate_entry_signal'):
                # Use strategy-specific entry evaluation
                return strategy_handler.evaluate_entry_signal(df)
            else:
                # Use signal processor for RSI and other strategies
                return self.signal_processor.evaluate_entry_conditions(df, config)
        except Exception as e:
            self.logger.error(f"Error checking entry conditions: {e}")
            return None

    def _check_exit_conditions(self, position: Dict, df: pd.DataFrame, current_price: float, 
                              strategy_handler, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check exit conditions for current position"""
        try:
            # Check stop loss first (based on max loss percentage)
            margin = config.get('margin', 50.0)
            max_loss_pct = config.get('max_loss_pct', 10.0)
            max_loss_amount = margin * (max_loss_pct / 100)
            
            # Calculate current PnL
            entry_price = position['entry_price']
            quantity = position['quantity']
            side = position['side']
            
            if side == 'BUY':
                pnl = (current_price - entry_price) * quantity
            else:  # SELL
                pnl = (entry_price - current_price) * quantity
            
            # Check stop loss
            if pnl <= -max_loss_amount:
                return {
                    'reason': f'Stop Loss (Max Loss {max_loss_pct}%)',
                    'type': 'stop_loss'
                }
            
            # Check partial take profit if enabled
            partial_tp_threshold = config.get('partial_tp_pnl_threshold', 0.0)
            partial_tp_percentage = config.get('partial_tp_position_percentage', 0.0)
            
            if (partial_tp_threshold > 0 and partial_tp_percentage > 0 and 
                not position.get('partial_tp_triggered', False)):
                pnl_percentage = (pnl / margin) * 100
                if pnl_percentage >= partial_tp_threshold:
                    position['partial_tp_triggered'] = True
                    position['quantity'] *= (1 - partial_tp_percentage / 100)
                    return {
                        'reason': f'Partial Take Profit ({partial_tp_percentage}% at {partial_tp_threshold}% profit)',
                        'type': 'partial_tp',
                        'partial': True
                    }
            
            # Check strategy-specific exit conditions
            if strategy_handler and hasattr(strategy_handler, 'evaluate_exit_signal'):
                exit_reason = strategy_handler.evaluate_exit_signal(df, position)
                if exit_reason:
                    return {
                        'reason': exit_reason,
                        'type': 'strategy_exit'
                    }
            else:
                # Use signal processor for RSI and other strategies
                exit_reason = self.signal_processor.evaluate_exit_conditions(df, position, config)
                if exit_reason:
                    return {
                        'reason': exit_reason,
                        'type': 'strategy_exit'
                    }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error checking exit conditions: {e}")
            return None

    def _open_position(self, signal: TradingSignal, price: float, timestamp: datetime, config: Dict[str, Any]) -> Dict[str, Any]:
        """Open a new position"""
        margin = config.get('margin', 50.0)
        leverage = config.get('leverage', 5)
        
        # Calculate position size
        notional_value = margin * leverage
        quantity = notional_value / price
        
        return {
            'entry_time': timestamp,
            'entry_price': price,
            'side': signal.signal_type.value,
            'quantity': quantity,
            'margin_used': margin,
            'leverage': leverage,
            'notional_value': notional_value,
            'entry_reason': signal.reason,
            'partial_tp_triggered': False
        }

    def _close_position(self, position: Dict, price: float, timestamp: datetime, reason: str) -> Dict[str, Any]:
        """Close position and calculate results"""
        entry_price = position['entry_price']
        quantity = position['quantity']
        side = position['side']
        margin_used = position['margin_used']
        
        # Calculate PnL
        if side == 'BUY':
            pnl = (price - entry_price) * quantity
        else:  # SELL
            pnl = (entry_price - price) * quantity
        
        # Calculate percentage returns
        pnl_percentage = (pnl / margin_used) * 100
        
        # Calculate duration
        duration = timestamp - position['entry_time']
        duration_minutes = duration.total_seconds() / 60
        
        return {
            'entry_time': position['entry_time'],
            'exit_time': timestamp,
            'duration_minutes': duration_minutes,
            'entry_price': entry_price,
            'exit_price': price,
            'side': side,
            'quantity': quantity,
            'margin_used': margin_used,
            'leverage': position['leverage'],
            'entry_reason': position['entry_reason'],
            'exit_reason': reason,
            'pnl_usdt': pnl,
            'pnl_percentage': pnl_percentage,
            'trade_status': 'CLOSED'
        }

    def _calculate_performance(self, trades: List[Dict], config: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate comprehensive performance metrics"""
        if not trades:
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'total_pnl_percentage': 0.0,
                'avg_pnl_per_trade': 0.0,
                'max_win': 0.0,
                'max_loss': 0.0,
                'avg_duration_minutes': 0.0,
                'profitable_trades': 0,
                'losing_trades': 0
            }
        
        # Basic statistics
        total_trades = len(trades)
        profitable_trades = len([t for t in trades if t['pnl_usdt'] > 0])
        losing_trades = len([t for t in trades if t['pnl_usdt'] < 0])
        break_even_trades = total_trades - profitable_trades - losing_trades
        
        # PnL statistics
        total_pnl = sum(t['pnl_usdt'] for t in trades)
        total_pnl_percentage = sum(t['pnl_percentage'] for t in trades)
        avg_pnl_per_trade = total_pnl / total_trades
        avg_pnl_percentage = total_pnl_percentage / total_trades
        
        # Win/Loss statistics
        win_rate = (profitable_trades / total_trades) * 100
        max_win = max(t['pnl_usdt'] for t in trades)
        max_loss = min(t['pnl_usdt'] for t in trades)
        
        # Duration statistics
        avg_duration = sum(t['duration_minutes'] for t in trades) / total_trades
        
        # Risk metrics
        margin_per_trade = config.get('margin', 50.0)
        max_loss_pct = config.get('max_loss_pct', 10.0)
        max_risk_per_trade = margin_per_trade * (max_loss_pct / 100)
        
        # Calculate drawdown
        running_pnl = 0
        peak_pnl = 0
        max_drawdown = 0
        
        for trade in trades:
            running_pnl += trade['pnl_usdt']
            if running_pnl > peak_pnl:
                peak_pnl = running_pnl
            drawdown = peak_pnl - running_pnl
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        # Sharpe ratio approximation (using trade PnL standard deviation)
        if len(trades) > 1:
            pnl_values = [t['pnl_usdt'] for t in trades]
            pnl_std = np.std(pnl_values)
            sharpe_ratio = avg_pnl_per_trade / pnl_std if pnl_std > 0 else 0
        else:
            sharpe_ratio = 0
        
        return {
            'total_trades': total_trades,
            'profitable_trades': profitable_trades,
            'losing_trades': losing_trades,
            'break_even_trades': break_even_trades,
            'win_rate': win_rate,
            'total_pnl_usdt': total_pnl,
            'total_pnl_percentage': total_pnl_percentage,
            'avg_pnl_per_trade_usdt': avg_pnl_per_trade,
            'avg_pnl_percentage': avg_pnl_percentage,
            'max_win_usdt': max_win,
            'max_loss_usdt': max_loss,
            'avg_duration_minutes': avg_duration,
            'max_drawdown_usdt': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'max_risk_per_trade': max_risk_per_trade,
            'risk_reward_ratio': abs(max_win / max_loss) if max_loss < 0 else 0,
            'profit_factor': sum(t['pnl_usdt'] for t in trades if t['pnl_usdt'] > 0) / abs(sum(t['pnl_usdt'] for t in trades if t['pnl_usdt'] < 0)) if any(t['pnl_usdt'] < 0 for t in trades) else float('inf')
        }

    def run_comprehensive_backtest(self, test_configs: List[Dict[str, Any]], start_date: str, end_date: str) -> Dict[str, Any]:
        """Run comprehensive backtest for multiple strategies and configurations"""
        self.logger.info(f"🚀 Starting comprehensive backtest")
        self.logger.info(f"📅 Period: {start_date} to {end_date}")
        self.logger.info(f"📊 Testing {len(test_configs)} strategy configurations")
        
        all_results = []
        
        for config in test_configs:
            strategy_name = config.get('strategy_name')
            self.logger.info(f"\n🔄 Testing {strategy_name} on {config.get('symbol')} {config.get('timeframe')}")
            
            result = self.backtest_strategy(strategy_name, config, start_date, end_date)
            all_results.append(result)
        
        # Generate comprehensive summary
        summary = self._generate_summary_report(all_results)
        
        return {
            'backtest_period': f"{start_date} to {end_date}",
            'test_configs': test_configs,
            'individual_results': all_results,
            'summary': summary,
            'generated_at': datetime.now().isoformat()
        }

    def _generate_summary_report(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate comprehensive summary report"""
        if not results:
            return {}
        
        valid_results = [r for r in results if 'error' not in r]
        
        if not valid_results:
            return {'error': 'No valid backtest results'}
        
        # Overall statistics
        total_strategies_tested = len(valid_results)
        total_trades_all = sum(len(r.get('trades', [])) for r in valid_results)
        
        # Aggregate performance
        all_trades = []
        for result in valid_results:
            all_trades.extend(result.get('trades', []))
        
        if all_trades:
            total_pnl = sum(t['pnl_usdt'] for t in all_trades)
            profitable_trades = len([t for t in all_trades if t['pnl_usdt'] > 0])
            overall_win_rate = (profitable_trades / len(all_trades)) * 100
        else:
            total_pnl = 0
            overall_win_rate = 0
        
        # Best and worst performing strategies
        strategy_performance = []
        for result in valid_results:
            if result.get('performance'):
                perf = result['performance']
                strategy_performance.append({
                    'strategy_name': result['strategy_name'],
                    'symbol': result['symbol'],
                    'timeframe': result['timeframe'],
                    'total_trades': perf['total_trades'],
                    'win_rate': perf['win_rate'],
                    'total_pnl': perf['total_pnl_usdt'],
                    'avg_pnl_per_trade': perf['avg_pnl_per_trade_usdt'],
                    'max_drawdown': perf['max_drawdown_usdt'],
                    'sharpe_ratio': perf['sharpe_ratio']
                })
        
        # Sort by total PnL
        strategy_performance.sort(key=lambda x: x['total_pnl'], reverse=True)
        
        best_strategy = strategy_performance[0] if strategy_performance else None
        worst_strategy = strategy_performance[-1] if strategy_performance else None
        
        return {
            'total_strategies_tested': total_strategies_tested,
            'total_trades_all_strategies': total_trades_all,
            'overall_pnl_usdt': total_pnl,
            'overall_win_rate': overall_win_rate,
            'best_performing_strategy': best_strategy,
            'worst_performing_strategy': worst_strategy,
            'strategy_rankings': strategy_performance,
            'recommendations': self._generate_recommendations(strategy_performance)
        }

    def _generate_recommendations(self, strategy_performance: List[Dict]) -> List[str]:
        """Generate trading recommendations based on backtest results"""
        recommendations = []
        
        if not strategy_performance:
            return ["No strategy performance data available for recommendations"]
        
        # Top performing strategy
        best = strategy_performance[0]
        if best['total_pnl'] > 0:
            recommendations.append(
                f"✅ {best['strategy_name']} on {best['symbol']} ({best['timeframe']}) shows best performance "
                f"with ${best['total_pnl']:.2f} total PnL and {best['win_rate']:.1f}% win rate"
            )
        
        # Strategies with high win rates
        high_win_rate_strategies = [s for s in strategy_performance if s['win_rate'] >= 60]
        if high_win_rate_strategies:
            recommendations.append(
                f"🎯 Strategies with 60%+ win rate: " + 
                ", ".join([f"{s['strategy_name']} ({s['win_rate']:.1f}%)" for s in high_win_rate_strategies[:3]])
            )
        
        # Risk warnings
        high_drawdown_strategies = [s for s in strategy_performance if s['max_drawdown'] > 100]
        if high_drawdown_strategies:
            recommendations.append(
                f"⚠️ High risk strategies (>$100 max drawdown): " + 
                ", ".join([f"{s['strategy_name']} (${s['max_drawdown']:.2f})" for s in high_drawdown_strategies[:3]])
            )
        
        # General recommendations
        profitable_count = len([s for s in strategy_performance if s['total_pnl'] > 0])
        if profitable_count > 0:
            recommendations.append(f"📊 {profitable_count}/{len(strategy_performance)} strategies showed profitability")
        
        if any(s['sharpe_ratio'] > 1.0 for s in strategy_performance):
            recommendations.append("🏆 Some strategies show excellent risk-adjusted returns (Sharpe > 1.0)")
        
        return recommendations

    def export_results(self, results: Dict[str, Any], filename: str = None) -> str:
        """Export backtest results to JSON file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"backtest_results_{timestamp}.json"
        
        # Ensure trading_data directory exists
        os.makedirs("trading_data", exist_ok=True)
        
        filepath = f"trading_data/{filename}"
        
        # Convert datetime objects to strings for JSON serialization
        def convert_datetime(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, dict):
                return {k: convert_datetime(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_datetime(item) for item in obj]
            return obj
        
        serializable_results = convert_datetime(results)
        
        with open(filepath, 'w') as f:
            json.dump(serializable_results, f, indent=2)
        
        self.logger.info(f"📁 Results exported to: {filepath}")
        return filepath

class BacktestWebInterface:
    """Web interface for the backtesting system"""
    
    def __init__(self):
        self.engine = BacktestEngine()
    
    def get_strategy_templates(self) -> Dict[str, Any]:
        """Get strategy configuration templates for the web interface"""
        return self.engine.strategy_configs
    
    def run_backtest_from_web(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run backtest from web form data"""
        try:
            # Extract form data
            strategy_name = form_data.get('strategy_name')
            start_date = form_data.get('start_date')
            end_date = form_data.get('end_date')
            
            # Build configuration from form data
            base_config = self.engine.strategy_configs.get(strategy_name, {}).copy()
            
            # Update with form values
            for key, value in form_data.items():
                if key not in ['strategy_name', 'start_date', 'end_date']:
                    # Convert to appropriate type
                    if isinstance(base_config.get(key), float):
                        base_config[key] = float(value)
                    elif isinstance(base_config.get(key), int):
                        base_config[key] = int(value)
                    else:
                        base_config[key] = value
            
            # Run single strategy backtest
            result = self.engine.backtest_strategy(strategy_name, base_config, start_date, end_date)
            
            # Export results
            filename = self.engine.export_results({
                'backtest_type': 'single_strategy',
                'result': result
            })
            
            return {
                'success': True,
                'result': result,
                'exported_file': filename
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

# Web interface integration
web_interface = BacktestWebInterface()

if __name__ == "__main__":
    # Example usage
    engine = BacktestEngine()
    
    # Example configuration
    test_configs = [
        {
            'strategy_name': 'rsi_oversold',
            'symbol': 'BTCUSDT',
            'timeframe': '15m',
            'margin': 50.0,
            'leverage': 5,
            'max_loss_pct': 10.0,
            'rsi_long_entry': 30,
            'rsi_long_exit': 70,
            'rsi_short_entry': 70,
            'rsi_short_exit': 30
        },
        {
            'strategy_name': 'macd_divergence',
            'symbol': 'ETHUSDT',
            'timeframe': '15m',
            'margin': 75.0,
            'leverage': 3,
            'max_loss_pct': 15.0,
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9
        }
    ]
    
    # Run backtest
    print("🚀 Starting backtest example...")
    results = engine.run_comprehensive_backtest(
        test_configs, 
        start_date="2024-01-01", 
        end_date="2024-01-31"
    )
    
    # Export results
    filename = engine.export_results(results)
    print(f"✅ Backtest completed! Results saved to: {filename}")
