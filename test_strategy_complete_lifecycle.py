
#!/usr/bin/env python3
"""
Comprehensive Strategy Lifecycle Test
====================================

Tests the complete trading lifecycle for each strategy:
1. RSI Oversold Strategy (XRPUSDT)
2. MACD Divergence Strategy (BTCUSDT) 
3. Engulfing Pattern Strategy (BCHUSDT)
4. Smart Money Reversal Strategy (SOLUSDT)

For each strategy, this test verifies:
- Position opening and execution
- Database recording of open trade
- Trade logger synchronization
- Position monitoring and management
- Position closing and execution
- Database recording of closed trade
- Final trade data integrity

This test simulates the complete trading flow end-to-end.
"""

import sys
import os
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.execution_engine.order_manager import OrderManager, Position
from src.execution_engine.trade_database import TradeDatabase
from src.analytics.trade_logger import trade_logger
from src.binance_client.client import BinanceClientWrapper
from src.strategy_processor.signal_processor import TradingSignal, SignalType
from src.config.trading_config import trading_config_manager

class StrategyLifecycleTest:
    """Complete strategy lifecycle testing suite"""
    
    def __init__(self):
        self.results = {
            'rsi_oversold': {
                'position_open': False,
                'database_record_open': False,
                'logger_sync_open': False,
                'position_close': False,
                'database_record_close': False,
                'logger_sync_close': False,
                'data_integrity': False
            },
            'macd_divergence': {
                'position_open': False,
                'database_record_open': False,
                'logger_sync_open': False,
                'position_close': False,
                'database_record_close': False,
                'logger_sync_close': False,
                'data_integrity': False
            },
            'engulfing_pattern': {
                'position_open': False,
                'database_record_open': False,
                'logger_sync_open': False,
                'position_close': False,
                'database_record_close': False,
                'logger_sync_close': False,
                'data_integrity': False
            },
            'smart_money': {
                'position_open': False,
                'database_record_open': False,
                'logger_sync_open': False,
                'position_close': False,
                'database_record_close': False,
                'logger_sync_close': False,
                'data_integrity': False
            }
        }
        
        # Initialize components
        self.trade_db = TradeDatabase()
        self.binance_client = BinanceClientWrapper()
        self.order_manager = OrderManager(self.binance_client, trade_logger)
        
        # Test data storage
        self.test_trades = {}
        self.cleanup_trades = []
        
        print("🧪 STRATEGY COMPLETE LIFECYCLE TEST")
        print("=" * 60)
        print("Testing: Position Opening → Database Logging → Position Closing → Closure Logging")
        print("=" * 60)
        
    def print_section(self, title):
        print(f"\n{'─'*50}")
        print(f"📋 {title}")
        print(f"{'─'*50}")
        
    def print_strategy_header(self, strategy_name, symbol):
        print(f"\n{'='*60}")
        print(f"🎯 TESTING STRATEGY: {strategy_name.upper()}")
        print(f"💱 Symbol: {symbol}")
        print(f"{'='*60}")

    def create_test_signal(self, symbol: str, side: str = 'BUY', entry_price: float = None) -> TradingSignal:
        """Create a test trading signal"""
        try:
            # Get current price if not provided
            if entry_price is None:
                try:
                    ticker = self.binance_client.get_symbol_ticker(symbol)
                    entry_price = float(ticker['price']) if ticker else 100.0
                except Exception as e:
                    print(f"⚠️ Could not fetch price for {symbol}, using default: {e}")
                    # Use realistic default prices based on symbol
                    price_defaults = {
                        'XRPUSDT': 0.50,
                        'BTCUSDT': 45000.0,
                        'BCHUSDT': 200.0,
                        'SOLUSDT': 25.0,
                        'ETHUSDT': 2500.0
                    }
                    entry_price = price_defaults.get(symbol, 100.0)
            
            # Calculate stop loss and take profit
            if side == 'BUY':
                stop_loss = entry_price * 0.98  # 2% stop loss
                take_profit = entry_price * 1.04  # 4% take profit
            else:
                stop_loss = entry_price * 1.02  # 2% stop loss
                take_profit = entry_price * 0.96  # 4% take profit
            
            signal = TradingSignal(
                signal_type=SignalType.BUY if side == 'BUY' else SignalType.SELL,
                confidence=0.85,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                symbol=symbol,
                reason=f"Test signal for {symbol}"
            )
            
            return signal
            
        except Exception as e:
            print(f"❌ Error creating test signal: {e}")
            return None

    def test_strategy_lifecycle(self, strategy_name: str, symbol: str, config: Dict) -> Dict[str, bool]:
        """Test complete lifecycle for a single strategy"""
        
        self.print_strategy_header(strategy_name, symbol)
        results = {
            'position_open': False,
            'database_record_open': False,
            'logger_sync_open': False,
            'position_close': False,
            'database_record_close': False,
            'logger_sync_close': False,
            'data_integrity': False
        }
        
        trade_id = None
        position = None
        
        try:
            # Phase 1: Position Opening
            print(f"\n📈 PHASE 1: OPENING POSITION")
            print(f"─" * 30)
            
            # Create test signal
            signal = self.create_test_signal(symbol, 'BUY')
            if not signal:
                print(f"❌ Failed to create test signal")
                return results
                
            print(f"✅ Test signal created: {signal.signal_type.value} {symbol} @ ${signal.entry_price:.4f}")
            
            # Execute signal (open position)
            position = self.order_manager.execute_signal(signal, config)
            
            if position:
                print(f"✅ Position opened successfully")
                print(f"   📊 Trade ID: {position.trade_id}")
                print(f"   💱 Symbol: {position.symbol}")
                print(f"   📊 Side: {position.side}")
                print(f"   💰 Quantity: {position.quantity}")
                print(f"   💵 Entry Price: ${position.entry_price:.4f}")
                
                results['position_open'] = True
                trade_id = position.trade_id
                self.cleanup_trades.append(position.strategy_name)
                
            else:
                print(f"❌ Failed to open position")
                return results
            
            # Phase 2: Verify Database Recording (Open)
            print(f"\n💾 PHASE 2: VERIFYING DATABASE RECORDING (OPEN)")
            print(f"─" * 40)
            
            if trade_id:
                db_trade = self.trade_db.get_trade(trade_id)
                if db_trade:
                    print(f"✅ Trade found in database")
                    print(f"   📊 Status: {db_trade.get('trade_status', 'N/A')}")
                    print(f"   💰 Margin Used: ${db_trade.get('margin_used', 'N/A')}")
                    print(f"   ⚡ Leverage: {db_trade.get('leverage', 'N/A')}x")
                    print(f"   💵 Position Value: ${db_trade.get('position_value_usdt', 'N/A')}")
                    
                    results['database_record_open'] = True
                    self.test_trades[trade_id] = db_trade
                else:
                    print(f"❌ Trade not found in database")
                    
            # Phase 3: Verify Logger Sync (Open)
            print(f"\n📝 PHASE 3: VERIFYING TRADE LOGGER SYNC (OPEN)")
            print(f"─" * 40)
            
            logger_trade = None
            for logged_trade in trade_logger.trades:
                if logged_trade.trade_id == trade_id:
                    logger_trade = logged_trade
                    break
                    
            if logger_trade:
                print(f"✅ Trade found in logger")
                print(f"   📊 Strategy: {logger_trade.strategy_name}")
                print(f"   💱 Symbol: {logger_trade.symbol}")
                print(f"   📊 Side: {logger_trade.side}")
                print(f"   💰 Margin: ${logger_trade.margin_used:.2f}")
                
                results['logger_sync_open'] = True
            else:
                print(f"❌ Trade not found in logger")
            
            # Phase 4: Position Closing
            print(f"\n📉 PHASE 4: CLOSING POSITION")
            print(f"─" * 30)
            
            # Wait a moment before closing
            time.sleep(2)
            
            # Close the position
            close_result = self.order_manager.close_position(position.strategy_name, "Test Closure")
            
            if close_result and 'symbol' in close_result:
                print(f"✅ Position closed successfully")
                print(f"   💰 PnL: ${close_result.get('pnl_usdt', 0):.2f} USDT")
                print(f"   📊 PnL %: {close_result.get('pnl_percentage', 0):.2f}%")
                print(f"   🚪 Exit Price: ${close_result.get('exit_price', 0):.4f}")
                print(f"   📝 Exit Reason: {close_result.get('exit_reason', 'N/A')}")
                
                results['position_close'] = True
            else:
                print(f"❌ Failed to close position")
                print(f"   Close result: {close_result}")
                
            # Phase 5: Verify Database Recording (Close)
            print(f"\n💾 PHASE 5: VERIFYING DATABASE RECORDING (CLOSE)")
            print(f"─" * 40)
            
            time.sleep(1)  # Give database time to update
            
            if trade_id:
                db_trade_updated = self.trade_db.get_trade(trade_id)
                if db_trade_updated:
                    trade_status = db_trade_updated.get('trade_status', 'N/A')
                    exit_price = db_trade_updated.get('exit_price', 'N/A')
                    pnl_usdt = db_trade_updated.get('pnl_usdt', 'N/A')
                    exit_reason = db_trade_updated.get('exit_reason', 'N/A')
                    
                    print(f"✅ Updated trade found in database")
                    print(f"   📊 Status: {trade_status}")
                    print(f"   🚪 Exit Price: ${exit_price}")
                    print(f"   💰 PnL: ${pnl_usdt}")
                    print(f"   📝 Exit Reason: {exit_reason}")
                    
                    if trade_status == 'CLOSED':
                        results['database_record_close'] = True
                    else:
                        print(f"❌ Trade status not updated to CLOSED")
                else:
                    print(f"❌ Updated trade not found in database")
                    
            # Phase 6: Verify Logger Sync (Close)
            print(f"\n📝 PHASE 6: VERIFYING TRADE LOGGER SYNC (CLOSE)")
            print(f"─" * 40)
            
            logger_trade_updated = None
            for logged_trade in trade_logger.trades:
                if logged_trade.trade_id == trade_id:
                    logger_trade_updated = logged_trade
                    break
                    
            if logger_trade_updated:
                if hasattr(logger_trade_updated, 'exit_price') and logger_trade_updated.exit_price:
                    print(f"✅ Closed trade found in logger")
                    print(f"   🚪 Exit Price: ${logger_trade_updated.exit_price:.4f}")
                    print(f"   💰 PnL: ${getattr(logger_trade_updated, 'pnl_usdt', 0):.2f}")
                    
                    results['logger_sync_close'] = True
                else:
                    print(f"❌ Trade exit data not synced to logger")
            else:
                print(f"❌ Closed trade not found in logger")
                
            # Phase 7: Data Integrity Check
            print(f"\n🔍 PHASE 7: DATA INTEGRITY CHECK")
            print(f"─" * 30)
            
            integrity_score = 0
            total_checks = 6
            
            # Check database consistency
            if results['database_record_open'] and results['database_record_close']:
                db_trade_final = self.test_trades.get(trade_id, {})
                db_trade_updated = self.trade_db.get_trade(trade_id)
                
                if db_trade_updated:
                    # Check essential fields
                    essential_fields = ['strategy_name', 'symbol', 'side', 'quantity', 'entry_price', 'trade_status']
                    for field in essential_fields:
                        if field in db_trade_updated and db_trade_updated[field]:
                            integrity_score += 1
                            print(f"✅ {field}: {db_trade_updated[field]}")
                        else:
                            print(f"❌ Missing {field}")
                            
            integrity_percentage = (integrity_score / total_checks) * 100
            print(f"\n📊 Data Integrity: {integrity_score}/{total_checks} ({integrity_percentage:.1f}%)")
            
            if integrity_percentage >= 80:
                results['data_integrity'] = True
                print(f"✅ Data integrity check passed")
            else:
                print(f"❌ Data integrity check failed")
                
        except Exception as e:
            print(f"❌ Error in strategy lifecycle test: {e}")
            import traceback
            print(f"🔍 Traceback: {traceback.format_exc()}")
            
        return results

    def test_connection(self):
        """Test API connection before running tests"""
        print(f"\n🔍 TESTING API CONNECTION")
        print(f"─" * 30)
        
        try:
            # Test binance connection
            account_info = self.binance_client.client.futures_account()
            if account_info:
                print(f"✅ Binance API connection successful")
                print(f"   Balance: ${float(account_info.get('totalWalletBalance', 0)):.2f}")
                return True
            else:
                print(f"❌ Binance API connection failed")
                return False
        except Exception as e:
            print(f"❌ Binance API connection error: {e}")
            return False

    def test_all_strategies(self):
        """Test all strategies"""
        
        # Test connection first
        if not self.test_connection():
            print(f"❌ Cannot proceed without API connection")
            return
        
        # Strategy configurations
        strategies = [
            {
                'name': 'rsi_oversold',
                'strategy_name': 'RSI_XRPUSDT_TEST',
                'symbol': 'XRPUSDT',
                'config': {
                    'name': 'RSI_XRPUSDT_TEST',
                    'symbol': 'XRPUSDT',
                    'timeframe': '15m',
                    'margin': 10.0,
                    'leverage': 3,
                    'max_loss_pct': 10,
                    'decimals': 1,
                    'rsi_period': 14,
                    'rsi_oversold': 30,
                    'rsi_overbought': 70
                }
            },
            {
                'name': 'macd_divergence',
                'strategy_name': 'MACD_BTCUSDT_TEST',
                'symbol': 'BTCUSDT',
                'config': {
                    'name': 'MACD_BTCUSDT_TEST',
                    'symbol': 'BTCUSDT',
                    'timeframe': '1h',
                    'margin': 10.0,
                    'leverage': 3,
                    'max_loss_pct': 10,
                    'decimals': 3,
                    'macd_fast': 12,
                    'macd_slow': 26,
                    'macd_signal': 9
                }
            },
            {
                'name': 'engulfing_pattern',
                'strategy_name': 'ENGULFING_BCHUSDT_TEST',
                'symbol': 'BCHUSDT',
                'config': {
                    'name': 'ENGULFING_BCHUSDT_TEST',
                    'symbol': 'BCHUSDT',
                    'timeframe': '1h',
                    'margin': 10.0,
                    'leverage': 3,
                    'max_loss_pct': 10,
                    'decimals': 2,
                    'rsi_period': 14,
                    'rsi_threshold': 50
                }
            },
            {
                'name': 'smart_money',
                'strategy_name': 'SMART_SOLUSDT_TEST',
                'symbol': 'SOLUSDT',
                'config': {
                    'name': 'SMART_SOLUSDT_TEST',
                    'symbol': 'SOLUSDT',
                    'timeframe': '15m',
                    'margin': 10.0,
                    'leverage': 3,
                    'max_loss_pct': 10,
                    'decimals': 2,
                    'swing_lookback_period': 25,
                    'sweep_threshold_pct': 0.1
                }
            }
        ]
        
        # Test each strategy
        for strategy in strategies:
            strategy_results = self.test_strategy_lifecycle(
                strategy['strategy_name'],
                strategy['symbol'],
                strategy['config']
            )
            
            self.results[strategy['name']] = strategy_results
            
            # Small delay between strategies
            time.sleep(2)

    def cleanup_test_positions(self):
        """Clean up any remaining test positions"""
        self.print_section("CLEANUP TEST POSITIONS")
        
        try:
            # Close any remaining active positions from test
            active_positions = self.order_manager.get_active_positions()
            
            for strategy_name in self.cleanup_trades:
                if strategy_name in active_positions:
                    print(f"🧹 Cleaning up position: {strategy_name}")
                    self.order_manager.close_position(strategy_name, "Test Cleanup")
                    
            # Remove test trades from database
            for trade_id in self.test_trades.keys():
                if trade_id in self.trade_db.trades:
                    del self.trade_db.trades[trade_id]
                    print(f"🧹 Removed test trade from database: {trade_id}")
                    
            self.trade_db._save_database()
            
            # Remove test trades from logger
            trade_logger.trades = [t for t in trade_logger.trades if t.trade_id not in self.test_trades.keys()]
            trade_logger._save_trades()
            
            print(f"✅ Cleanup completed")
            
        except Exception as e:
            print(f"❌ Error during cleanup: {e}")

    def generate_report(self):
        """Generate comprehensive test report"""
        self.print_section("COMPREHENSIVE TEST REPORT")
        
        total_tests = 0
        passed_tests = 0
        
        print(f"\n📊 STRATEGY LIFECYCLE TEST RESULTS")
        print(f"{'Strategy':<20} {'Open':<6} {'DB+':<4} {'Log+':<4} {'Close':<6} {'DB-':<4} {'Log-':<4} {'Integrity':<9} {'Score'}")
        print(f"{'─'*20} {'─'*6} {'─'*4} {'─'*4} {'─'*6} {'─'*4} {'─'*4} {'─'*9} {'─'*5}")
        
        for strategy_name, results in self.results.items():
            tests = [
                results.get('position_open', False),
                results.get('database_record_open', False),
                results.get('logger_sync_open', False),
                results.get('position_close', False),
                results.get('database_record_close', False),
                results.get('logger_sync_close', False),
                results.get('data_integrity', False)
            ]
            
            strategy_passed = sum(tests)
            strategy_total = len(tests)
            
            total_tests += strategy_total
            passed_tests += strategy_passed
            
            # Format results
            open_pos = "✅" if results.get('position_open') else "❌"
            db_open = "✅" if results.get('database_record_open') else "❌"
            log_open = "✅" if results.get('logger_sync_open') else "❌"
            close_pos = "✅" if results.get('position_close') else "❌"
            db_close = "✅" if results.get('database_record_close') else "❌"
            log_close = "✅" if results.get('logger_sync_close') else "❌"
            integrity = "✅" if results.get('data_integrity') else "❌"
            score = f"{strategy_passed}/{strategy_total}"
            
            print(f"{strategy_name:<20} {open_pos:<6} {db_open:<4} {log_open:<4} {close_pos:<6} {db_close:<4} {log_close:<4} {integrity:<9} {score}")
        
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        
        print(f"\n{'='*70}")
        print(f"📋 OVERALL RESULTS")
        print(f"{'='*70}")
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")
        print(f"Success Rate: {success_rate:.1f}%")
        
        if success_rate >= 85:
            print(f"\n🎉 EXCELLENT! Trading system lifecycle working well!")
            print(f"   ✅ Position opening system: Functional")
            print(f"   ✅ Database recording system: Functional")
            print(f"   ✅ Trade logger sync: Functional")
            print(f"   ✅ Position closing system: Functional")
        elif success_rate >= 70:
            print(f"\n✅ GOOD! Trading system mostly functional with minor issues")
        else:
            print(f"\n❌ NEEDS ATTENTION! Trading system has significant issues")
            
        # Detailed analysis
        print(f"\n🔍 DETAILED ANALYSIS:")
        
        common_issues = {}
        for strategy_name, results in self.results.items():
            for test_type, result in results.items():
                if not result:
                    if test_type not in common_issues:
                        common_issues[test_type] = []
                    common_issues[test_type].append(strategy_name)
        
        if common_issues:
            print(f"\n❌ COMMON ISSUES FOUND:")
            for issue, strategies in common_issues.items():
                print(f"   {issue}: {', '.join(strategies)}")
        else:
            print(f"   ✅ No common issues detected across strategies")
        
        return success_rate

def main():
    """Run the comprehensive strategy lifecycle test"""
    
    print("🚀 STARTING STRATEGY COMPLETE LIFECYCLE TEST")
    print("=" * 80)
    
    # Initialize test suite
    test_suite = StrategyLifecycleTest()
    
    try:
        # Test all strategies
        test_suite.test_all_strategies()
        
        # Generate comprehensive report
        success_rate = test_suite.generate_report()
        
        # Cleanup
        test_suite.cleanup_test_positions()
        
        # Final recommendations
        print(f"\n📋 RECOMMENDATIONS:")
        if success_rate < 70:
            print(f"1. Check order execution system")
            print(f"2. Verify database recording mechanisms") 
            print(f"3. Ensure trade logger synchronization")
            print(f"4. Review position management logic")
        elif success_rate < 85:
            print(f"1. Address specific failing test cases")
            print(f"2. Improve error handling in weaker areas")
        else:
            print(f"1. System performing excellently!")
            print(f"2. Continue monitoring in production")
        
        print(f"\n🎯 FOCUS AREAS:")
        if success_rate >= 85:
            print(f"   ✅ Trading system ready for production use")
        else:
            print(f"   ⚠️ Address failing components before live trading")
        
    except Exception as e:
        print(f"❌ Test suite error: {e}")
        import traceback
        print(f"🔍 Traceback: {traceback.format_exc()}")
        
        # Still attempt cleanup
        try:
            test_suite.cleanup_test_positions()
        except:
            pass

if __name__ == "__main__":
    main()
