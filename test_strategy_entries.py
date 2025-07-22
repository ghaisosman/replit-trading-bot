#!/usr/bin/env python3
"""
Strategy Entry Testing System
Test MACD Divergence and Smart Money strategies with simulated market conditions
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, List
import random

# Add src to path for imports
sys.path.append('src')

from src.config.global_config import global_config
from src.binance_client.client import BinanceClientWrapper
from src.execution_engine.trade_database import TradeDatabase
from src.analytics.trade_logger import TradeLogger
from src.execution_engine.order_manager import OrderManager

class StrategyTester:
    def __init__(self):
        """Initialize strategy tester"""
        self.client = BinanceClientWrapper()
        self.trade_db = TradeDatabase()
        self.trade_logger = TradeLogger()
        self.order_manager = OrderManager(self.client, self.trade_db, self.trade_logger)

        # Test symbols
        self.test_symbols = {
            'macd_divergence': 'SOLUSDT',  # SOL for MACD Divergence
            'smart_money': 'ETHUSDT'       # ETH for Smart Money
        }

        # Strategy configurations
        self.strategy_configs = {
            'macd_divergence': {
                'name': 'MACD Divergence',
                'symbol': 'SOLUSDT',
                'position_size_usdt': 50,
                'take_profit_percent': 2.5,
                'stop_loss_percent': 1.5,
                'leverage': 5
            },
            'smart_money': {
                'name': 'Smart Money',
                'symbol': 'ETHUSDT', 
                'position_size_usdt': 75,
                'take_profit_percent': 3.0,
                'stop_loss_percent': 2.0,
                'leverage': 3
            }
        }

    def generate_test_signals(self, strategy: str, count: int = 3) -> List[Dict[str, Any]]:
        """Generate test signals for strategy testing"""
        signals = []
        symbol = self.test_symbols[strategy]

        # Get current price for realistic testing
        try:
            current_price = float(self.client.client.get_symbol_ticker(symbol=symbol)['price'])
        except Exception as e:
            print(f"⚠️ Could not fetch current price for {symbol}, using mock price")
            current_price = 100.0 if symbol == 'SOLUSDT' else 2500.0

        for i in range(count):
            # Generate different signal types
            signal_types = ['LONG', 'SHORT'] if strategy == 'smart_money' else ['LONG']
            signal_type = random.choice(signal_types)

            # Simulate price variations for realistic testing
            price_variation = random.uniform(-0.02, 0.02)  # ±2% variation
            entry_price = current_price * (1 + price_variation)

            signal = {
                'strategy': strategy,
                'symbol': symbol,
                'signal_type': signal_type,
                'entry_price': entry_price,
                'timestamp': datetime.now() - timedelta(minutes=i*30),
                'confidence': random.uniform(0.7, 0.95),
                'test_id': f"TEST_{strategy.upper()}_{i+1}",
                'simulated': True
            }

            signals.append(signal)

        return signals

    async def simulate_entry(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate strategy entry with full trade lifecycle"""
        strategy = signal['strategy']
        config = self.strategy_configs[strategy]

        print(f"\n🎯 TESTING {config['name']} ENTRY")
        print(f"Symbol: {signal['symbol']}")
        print(f"Signal: {signal['signal_type']}")
        print(f"Entry Price: ${signal['entry_price']:.4f}")
        print(f"Test ID: {signal['test_id']}")

        # Calculate position details
        position_size_usdt = config['position_size_usdt']
        leverage = config['leverage']
        entry_price = signal['entry_price']

        # Calculate quantity based on USDT amount
        quantity = (position_size_usdt * leverage) / entry_price

        # Calculate take profit and stop loss prices
        if signal['signal_type'] == 'LONG':
            take_profit_price = entry_price * (1 + config['take_profit_percent'] / 100)
            stop_loss_price = entry_price * (1 - config['stop_loss_percent'] / 100)
        else:
            take_profit_price = entry_price * (1 - config['take_profit_percent'] / 100)
            stop_loss_price = entry_price * (1 + config['stop_loss_percent'] / 100)

        # Create trade entry data
        trade_data = {
            'trade_id': signal['test_id'],
            'strategy_name': config['name'],
            'symbol': signal['symbol'],
            'side': signal['signal_type'],
            'quantity': quantity,
            'entry_price': entry_price,
            'take_profit_price': take_profit_price,
            'stop_loss_price': stop_loss_price,
            'leverage': leverage,
            'position_size_usdt': position_size_usdt,
            'trade_status': 'OPEN',
            'entry_time': signal['timestamp'].isoformat(),
            'test_mode': True,
            'simulated': True
        }

        print(f"💰 Position Size: ${position_size_usdt} USDT")
        print(f"📊 Leverage: {leverage}x")
        print(f"📈 Quantity: {quantity:.6f} {signal['symbol'][:-4]}")
        print(f"🎯 Take Profit: ${take_profit_price:.4f}")
        print(f"🛑 Stop Loss: ${stop_loss_price:.4f}")

        # Record entry in database
        try:
            self.trade_db.record_trade_entry(trade_data)
            print(f"✅ Trade recorded in database")
        except Exception as e:
            print(f"❌ Database recording failed: {e}")

        # Record in trade logger
        try:
            self.trade_logger.log_trade_entry(trade_data)
            print(f"✅ Trade logged in trade logger")
        except Exception as e:
            print(f"❌ Trade logger failed: {e}")

        return trade_data

    async def simulate_exit(self, trade_data: Dict[str, Any], exit_type: str) -> Dict[str, Any]:
        """Simulate trade exit (TP/SL/Manual)"""
        print(f"\n🚪 SIMULATING EXIT - {exit_type}")

        entry_price = trade_data['entry_price']

        # Determine exit price based on exit type
        if exit_type == 'TAKE_PROFIT':
            exit_price = trade_data['take_profit_price']
            exit_reason = 'Take Profit Hit'
        elif exit_type == 'STOP_LOSS':
            exit_price = trade_data['stop_loss_price'] 
            exit_reason = 'Stop Loss Hit'
        else:  # MANUAL
            # Simulate manual exit at random price between entry and TP
            if trade_data['side'] == 'LONG':
                exit_price = random.uniform(entry_price, trade_data['take_profit_price'])
            else:
                exit_price = random.uniform(trade_data['take_profit_price'], entry_price)
            exit_reason = 'Manual Exit'

        # Calculate PnL
        quantity = trade_data['quantity']
        if trade_data['side'] == 'LONG':
            pnl_usdt = quantity * (exit_price - entry_price)
        else:
            pnl_usdt = quantity * (entry_price - exit_price)

        pnl_percentage = (pnl_usdt / trade_data['position_size_usdt']) * 100

        # Update trade data
        trade_data.update({
            'exit_price': exit_price,
            'exit_time': datetime.now().isoformat(),
            'exit_reason': exit_reason,
            'pnl_usdt': pnl_usdt,
            'pnl_percentage': pnl_percentage,
            'trade_status': 'CLOSED'
        })

        print(f"💸 Exit Price: ${exit_price:.4f}")
        print(f"💰 PnL: ${pnl_usdt:.2f} USDT ({pnl_percentage:.2f}%)")
        print(f"📝 Exit Reason: {exit_reason}")

        # Record exit in database
        try:
            self.trade_db.record_trade_exit(trade_data['trade_id'], trade_data)
            print(f"✅ Exit recorded in database")
        except Exception as e:
            print(f"❌ Database exit recording failed: {e}")

        # Record in trade logger
        try:
            self.trade_logger.log_trade_exit(trade_data)
            print(f"✅ Exit logged in trade logger")
        except Exception as e:
            print(f"❌ Trade logger exit failed: {e}")

        return trade_data

    async def test_strategy(self, strategy: str, num_tests: int = 3):
        """Test complete strategy lifecycle"""
        print(f"\n{'='*60}")
        print(f"🧪 TESTING STRATEGY: {strategy.upper()}")
        print(f"{'='*60}")

        # Generate test signals
        signals = self.generate_test_signals(strategy, num_tests)

        completed_trades = []

        for i, signal in enumerate(signals):
            print(f"\n--- TEST {i+1}/{num_tests} ---")

            # Simulate entry
            trade_data = await self.simulate_entry(signal)

            # Wait a bit to simulate time passage
            await asyncio.sleep(1)

            # Randomly choose exit type for testing
            exit_types = ['TAKE_PROFIT', 'STOP_LOSS', 'MANUAL']
            weights = [0.4, 0.3, 0.3]  # 40% TP, 30% SL, 30% Manual
            exit_type = random.choices(exit_types, weights=weights)[0]

            # Simulate exit
            completed_trade = await self.simulate_exit(trade_data, exit_type)
            completed_trades.append(completed_trade)

            print(f"✅ Test {i+1} completed")
            await asyncio.sleep(1)

        return completed_trades

    def generate_test_report(self, strategy: str, trades: List[Dict[str, Any]]):
        """Generate comprehensive test report"""
        print(f"\n{'='*60}")
        print(f"📊 TEST REPORT: {strategy.upper()}")
        print(f"{'='*60}")

        total_trades = len(trades)
        winning_trades = [t for t in trades if t['pnl_usdt'] > 0]
        losing_trades = [t for t in trades if t['pnl_usdt'] <= 0]

        total_pnl = sum(t['pnl_usdt'] for t in trades)
        win_rate = len(winning_trades) / total_trades * 100

        print(f"📈 Total Trades: {total_trades}")
        print(f"✅ Winning Trades: {len(winning_trades)}")
        print(f"❌ Losing Trades: {len(losing_trades)}")
        print(f"🎯 Win Rate: {win_rate:.1f}%")
        print(f"💰 Total PnL: ${total_pnl:.2f} USDT")
        print(f"📊 Average PnL per Trade: ${total_pnl/total_trades:.2f} USDT")

        if winning_trades:
            avg_win = sum(t['pnl_usdt'] for t in winning_trades) / len(winning_trades)
            print(f"📈 Average Win: ${avg_win:.2f} USDT")

        if losing_trades:
            avg_loss = sum(t['pnl_usdt'] for t in losing_trades) / len(losing_trades)
            print(f"📉 Average Loss: ${avg_loss:.2f} USDT")

        print(f"\n🔍 DETAILED TRADE BREAKDOWN:")
        for i, trade in enumerate(trades, 1):
            status = "✅ WIN" if trade['pnl_usdt'] > 0 else "❌ LOSS"
            print(f"  {i}. {trade['trade_id']} - {status} - ${trade['pnl_usdt']:.2f} - {trade['exit_reason']}")

    async def verify_database_records(self, strategy: str):
        """Verify that all test trades are properly recorded in database"""
        print(f"\n🔍 VERIFYING DATABASE RECORDS FOR {strategy.upper()}")

        # Check trade database
        try:
            trades = self.trade_db.get_all_trades()
            test_trades = {tid: data for tid, data in trades.items() 
                          if data.get('test_mode') and data.get('strategy_name', '').lower().replace(' ', '_') == strategy}

            print(f"📊 Found {len(test_trades)} test trades in database")

            for trade_id, data in test_trades.items():
                status = data.get('trade_status', 'UNKNOWN')
                pnl = data.get('pnl_usdt', 0)
                print(f"  - {trade_id}: {status} (PnL: ${pnl:.2f})")

        except Exception as e:
            print(f"❌ Database verification failed: {e}")

        # Check trade logger
        try:
            logger_file = "trading_data/trades/all_trades.json"
            if os.path.exists(logger_file):
                with open(logger_file, 'r') as f:
                    logger_data = json.load(f)

                test_logged_trades = [trade for trade in logger_data 
                                    if trade.get('test_mode') and 
                                    trade.get('strategy_name', '').lower().replace(' ', '_') == strategy]

                print(f"📝 Found {len(test_logged_trades)} test trades in logger")

                for trade in test_logged_trades:
                    trade_id = trade.get('trade_id', 'UNKNOWN')
                    status = trade.get('trade_status', 'UNKNOWN') 
                    pnl = trade.get('pnl_usdt', 0)
                    print(f"  - {trade_id}: {status} (PnL: ${pnl:.2f})")
            else:
                print(f"⚠️ Trade logger file not found")

        except Exception as e:
            print(f"❌ Trade logger verification failed: {e}")

    async def cleanup_test_data(self):
        """Clean up test data after testing"""
        print(f"\n🧹 CLEANING UP TEST DATA")

        try:
            # Remove test trades from database
            trades = self.trade_db.get_all_trades()
            test_trade_ids = [tid for tid, data in trades.items() if data.get('test_mode')]

            for trade_id in test_trade_ids:
                self.trade_db.remove_trade(trade_id)

            print(f"🗑️ Removed {len(test_trade_ids)} test trades from database")

            # Note: We won't clean trade logger as it's meant to be permanent record
            print(f"📝 Trade logger entries preserved for historical analysis")

        except Exception as e:
            print(f"❌ Cleanup failed: {e}")

async def main():
    """Main testing function"""
    print("🧪 STRATEGY ENTRY TESTING SYSTEM")
    print("Testing MACD Divergence and Smart Money strategies")
    print("=" * 60)

    tester = StrategyTester()

    # Test both strategies
    strategies_to_test = ['macd_divergence', 'smart_money']
    all_results = {}

    for strategy in strategies_to_test:
        print(f"\n🚀 STARTING TESTS FOR {strategy.upper()}")

        # Run tests
        completed_trades = await tester.test_strategy(strategy, num_tests=3)
        all_results[strategy] = completed_trades

        # Generate report
        tester.generate_test_report(strategy, completed_trades)

        # Verify database records
        await tester.verify_database_records(strategy)

        print(f"✅ {strategy.upper()} testing completed")
        await asyncio.sleep(2)

    # Overall summary
    print(f"\n{'='*60}")
    print(f"🏁 TESTING COMPLETE - OVERALL SUMMARY")
    print(f"{'='*60}")

    total_trades = sum(len(trades) for trades in all_results.values())
    total_pnl = sum(sum(t['pnl_usdt'] for t in trades) for trades in all_results.values())

    print(f"📊 Total Strategies Tested: {len(strategies_to_test)}")
    print(f"📈 Total Trades Executed: {total_trades}")
    print(f"💰 Combined PnL: ${total_pnl:.2f} USDT")

    for strategy, trades in all_results.items():
        strategy_pnl = sum(t['pnl_usdt'] for t in trades)
        win_rate = len([t for t in trades if t['pnl_usdt'] > 0]) / len(trades) * 100
        print(f"  - {strategy.upper()}: {len(trades)} trades, ${strategy_pnl:.2f} PnL, {win_rate:.1f}% win rate")

    print(f"\n💡 RECOMMENDATIONS:")
    print(f"1. Check web dashboard for updated trade records")
    print(f"2. Review database synchronization between systems")
    print(f"3. Analyze exit reasons and PnL distribution")
    print(f"4. Use insights to optimize real trading parameters")

    # Ask about cleanup
    print(f"\n🧹 Cleanup test data? (y/n): ", end='')
    try:
        choice = input().lower().strip()
        if choice == 'y':
            await tester.cleanup_test_data()
            print(f"✅ Test data cleaned up")
        else:
            print(f"📊 Test data preserved for analysis")
    except:
        print(f"📊 Test data preserved for analysis")

    print(f"\n🎉 Strategy testing completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())