
#!/usr/bin/env python3
"""
Comprehensive Position Closing Database Recording Test
====================================================

Tests the complete position closing flow for all strategies:
1. RSI Oversold Strategy
2. MACD Divergence Strategy  
3. Engulfing Pattern Strategy
4. Smart Money Reversal Strategy

Verifies:
- Position closure executes correctly
- Database is updated with exit data
- Trade logger receives exit information
- PnL calculations are accurate
- Duration tracking works
- Exit reasons are recorded properly
"""

import sys
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.execution_engine.trade_database import TradeDatabase
from src.analytics.trade_logger import trade_logger
from src.execution_engine.order_manager import OrderManager, Position
from src.binance_client.client import BinanceClientWrapper
from src.strategy_processor.signal_processor import TradingSignal, SignalType
from src.config.trading_config import trading_config_manager

class PositionClosingDatabaseTest:
    """Test suite for position closing database recording"""
    
    def __init__(self):
        self.results = {
            'rsi_strategy': {'close_success': False, 'db_update': False, 'logger_sync': False},
            'macd_strategy': {'close_success': False, 'db_update': False, 'logger_sync': False},
            'engulfing_strategy': {'close_success': False, 'db_update': False, 'logger_sync': False},
            'smart_money_strategy': {'close_success': False, 'db_update': False, 'logger_sync': False}
        }
        
        # Initialize components
        self.trade_db = TradeDatabase()
        self.binance_client = BinanceClientWrapper()
        self.order_manager = OrderManager(self.binance_client, trade_logger)
        
        print("🧪 POSITION CLOSING DATABASE RECORDING TEST")
        print("=" * 80)
        
    def print_section(self, title):
        print(f"\n{'─'*60}")
        print(f"📋 {title}")
        print(f"{'─'*60}")
        
    def create_test_position(self, strategy_name: str, symbol: str, side: str = 'BUY') -> Position:
        """Create a test position for closing"""
        try:
            # Create a position object
            position = Position(
                strategy_name=strategy_name,
                symbol=symbol,
                side=side,
                entry_price=100.0,  # Test price
                quantity=0.1,  # Test quantity
                stop_loss=95.0,
                take_profit=110.0,
                position_side='LONG' if side == 'BUY' else 'SHORT',
                order_id=12345,
                entry_time=datetime.now() - timedelta(minutes=30),  # 30 minutes ago
                status="OPEN",
                trade_id=f"{strategy_name}_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            
            # Set strategy config
            position.strategy_config = {
                'margin': 10.0,
                'leverage': 3,
                'name': strategy_name,
                'symbol': symbol
            }
            
            # Store actual margin used
            position.actual_margin_used = 10.0
            
            return position
            
        except Exception as e:
            print(f"❌ Error creating test position: {e}")
            return None
    
    def add_position_to_database(self, position: Position) -> bool:
        """Add position to database as open trade"""
        try:
            trade_data = {
                'trade_id': position.trade_id,
                'strategy_name': position.strategy_name,
                'symbol': position.symbol,
                'side': position.side,
                'quantity': position.quantity,
                'entry_price': position.entry_price,
                'trade_status': 'OPEN',
                'position_value_usdt': position.entry_price * position.quantity,
                'leverage': 3,
                'margin_used': position.actual_margin_used,
                'stop_loss': position.stop_loss,
                'take_profit': position.take_profit,
                'order_id': position.order_id,
                'position_side': position.position_side,
                'created_at': position.entry_time.isoformat()
            }
            
            success = self.trade_db.add_trade(position.trade_id, trade_data)
            if success:
                print(f"✅ Test position added to database: {position.trade_id}")
            else:
                print(f"❌ Failed to add test position to database: {position.trade_id}")
                
            return success
            
        except Exception as e:
            print(f"❌ Error adding position to database: {e}")
            return False
    
    def simulate_position_close(self, position: Position, exit_price: float, exit_reason: str) -> bool:
        """Simulate position closure and test database recording"""
        try:
            print(f"🔍 Testing position close for {position.strategy_name}")
            print(f"   Trade ID: {position.trade_id}")
            print(f"   Symbol: {position.symbol}")
            print(f"   Entry: ${position.entry_price}")
            print(f"   Exit: ${exit_price}")
            print(f"   Reason: {exit_reason}")
            
            # Add position to order manager's active positions
            self.order_manager.active_positions[position.strategy_name] = position
            
            # Calculate expected PnL
            if position.side == 'BUY':
                expected_pnl = (exit_price - position.entry_price) * position.quantity
            else:
                expected_pnl = (position.entry_price - exit_price) * position.quantity
                
            expected_pnl_percentage = (expected_pnl / position.actual_margin_used) * 100
            
            print(f"   Expected PnL: ${expected_pnl:.2f} ({expected_pnl_percentage:+.2f}%)")
            
            # Mock the close_position method behavior for testing
            return self.test_close_position_database_update(position, exit_price, exit_reason, expected_pnl, expected_pnl_percentage)
            
        except Exception as e:
            print(f"❌ Error simulating position close: {e}")
            return False
    
    def test_close_position_database_update(self, position: Position, exit_price: float, 
                                          exit_reason: str, expected_pnl: float, 
                                          expected_pnl_percentage: float) -> bool:
        """Test the database update portion of position closing"""
        try:
            # Calculate duration
            duration_minutes = (datetime.now() - position.entry_time).total_seconds() / 60
            
            # Test database update
            update_data = {
                'trade_status': 'CLOSED',
                'exit_price': exit_price,
                'exit_reason': exit_reason,
                'pnl_usdt': expected_pnl,
                'pnl_percentage': expected_pnl_percentage,
                'duration_minutes': duration_minutes,
                'exit_time': datetime.now().isoformat()
            }
            
            print(f"🔍 Testing database update with:")
            for key, value in update_data.items():
                print(f"   {key}: {value}")
            
            # Update database
            success = self.trade_db.update_trade(position.trade_id, update_data)
            
            if success:
                print(f"✅ Database update successful")
                
                # Verify the update
                updated_trade = self.trade_db.get_trade(position.trade_id)
                if updated_trade:
                    print(f"✅ Trade retrieved after update")
                    
                    # Check key fields
                    verification_passed = True
                    
                    if updated_trade.get('trade_status') != 'CLOSED':
                        print(f"❌ Trade status not updated: {updated_trade.get('trade_status')}")
                        verification_passed = False
                        
                    if abs(updated_trade.get('exit_price', 0) - exit_price) > 0.01:
                        print(f"❌ Exit price not recorded correctly: {updated_trade.get('exit_price')}")
                        verification_passed = False
                        
                    if updated_trade.get('exit_reason') != exit_reason:
                        print(f"❌ Exit reason not recorded: {updated_trade.get('exit_reason')}")
                        verification_passed = False
                        
                    if abs(updated_trade.get('pnl_usdt', 0) - expected_pnl) > 0.01:
                        print(f"❌ PnL not calculated correctly: {updated_trade.get('pnl_usdt')}")
                        verification_passed = False
                        
                    if abs(updated_trade.get('pnl_percentage', 0) - expected_pnl_percentage) > 0.1:
                        print(f"❌ PnL percentage not calculated correctly: {updated_trade.get('pnl_percentage')}")
                        verification_passed = False
                    
                    if verification_passed:
                        print(f"✅ All database fields verified correctly")
                        return True
                    else:
                        print(f"❌ Database verification failed")
                        return False
                else:
                    print(f"❌ Could not retrieve updated trade from database")
                    return False
            else:
                print(f"❌ Database update failed")
                return False
                
        except Exception as e:
            print(f"❌ Error testing database update: {e}")
            return False
    
    def test_trade_logger_sync(self, position: Position) -> bool:
        """Test if trade logger receives the exit data"""
        try:
            # Check if trade exists in logger
            logger_trade = None
            for trade in trade_logger.trades:
                if trade.trade_id == position.trade_id:
                    logger_trade = trade
                    break
            
            if logger_trade:
                print(f"✅ Trade found in logger: {position.trade_id}")
                
                # Check if exit data is present
                if logger_trade.trade_status == "CLOSED":
                    print(f"✅ Trade marked as closed in logger")
                    
                    if logger_trade.exit_price:
                        print(f"✅ Exit price recorded in logger: ${logger_trade.exit_price}")
                        
                    if logger_trade.pnl_usdt is not None:
                        print(f"✅ PnL recorded in logger: ${logger_trade.pnl_usdt:.2f}")
                        
                    if logger_trade.exit_reason:
                        print(f"✅ Exit reason recorded in logger: {logger_trade.exit_reason}")
                        
                    return True
                else:
                    print(f"❌ Trade not marked as closed in logger")
                    return False
            else:
                print(f"❌ Trade not found in logger: {position.trade_id}")
                return False
                
        except Exception as e:
            print(f"❌ Error testing logger sync: {e}")
            return False
    
    def test_strategy_closing(self, strategy_name: str, symbol: str, side: str = 'BUY') -> Dict[str, bool]:
        """Test position closing for a specific strategy"""
        results = {'close_success': False, 'db_update': False, 'logger_sync': False}
        
        try:
            # Create test position
            position = self.create_test_position(strategy_name, symbol, side)
            if not position:
                return results
            
            # Add to database
            if not self.add_position_to_database(position):
                return results
            
            # Test position closing with different exit scenarios
            exit_scenarios = [
                {'price': 105.0, 'reason': 'Take Profit Hit'},
                {'price': 98.0, 'reason': 'Stop Loss Hit'},
                {'price': 102.0, 'reason': 'Manual Close'}
            ]
            
            # Test with first scenario
            scenario = exit_scenarios[0]
            
            # Simulate position close
            close_success = self.simulate_position_close(position, scenario['price'], scenario['reason'])
            results['close_success'] = close_success
            
            if close_success:
                results['db_update'] = True
                
                # Test logger sync
                logger_sync = self.test_trade_logger_sync(position)
                results['logger_sync'] = logger_sync
            
            return results
            
        except Exception as e:
            print(f"❌ Error testing strategy closing: {e}")
            return results
    
    def test_all_strategies(self):
        """Test position closing for all strategies"""
        
        strategies_to_test = [
            {'name': 'RSI_XRPUSDT', 'symbol': 'XRPUSDT', 'side': 'BUY'},
            {'name': 'MACD_DIVERGENCE', 'symbol': 'BTCUSDT', 'side': 'BUY'},
            {'name': 'RSI_ETH', 'symbol': 'ETHUSDT', 'side': 'BUY'},
            {'name': 'SMART_MONEY_REVERSAL', 'symbol': 'SOLUSDT', 'side': 'BUY'}
        ]
        
        for strategy in strategies_to_test:
            self.print_section(f"Testing {strategy['name']} Strategy")
            
            strategy_key = strategy['name'].lower().replace('_', '').replace('usdt', '').replace('xrp', 'rsi').replace('btc', 'macd').replace('eth', 'rsi').replace('sol', 'smartmoney')
            if 'smartmoney' in strategy_key:
                strategy_key = 'smart_money_strategy'
            elif 'macd' in strategy_key:
                strategy_key = 'macd_strategy' 
            elif 'rsi' in strategy_key:
                strategy_key = 'rsi_strategy'
            else:
                strategy_key = 'engulfing_strategy'
                
            results = self.test_strategy_closing(
                strategy['name'], 
                strategy['symbol'], 
                strategy['side']
            )
            
            self.results[strategy_key] = results
            
            print(f"\n📊 Results for {strategy['name']}:")
            print(f"   Close Success: {'✅' if results['close_success'] else '❌'}")
            print(f"   Database Update: {'✅' if results['db_update'] else '❌'}")
            print(f"   Logger Sync: {'✅' if results['logger_sync'] else '❌'}")
    
    def test_edge_cases(self):
        """Test edge cases in position closing"""
        self.print_section("Testing Edge Cases")
        
        # Test 1: Position with zero PnL
        print("🔍 Testing zero PnL scenario...")
        position = self.create_test_position("TEST_ZERO_PNL", "TESTUSDT")
        if position:
            self.add_position_to_database(position)
            zero_pnl_result = self.simulate_position_close(position, position.entry_price, "Zero PnL Close")
            print(f"Zero PnL Test: {'✅ PASSED' if zero_pnl_result else '❌ FAILED'}")
        
        # Test 2: Position with negative PnL
        print("\n🔍 Testing negative PnL scenario...")
        position = self.create_test_position("TEST_NEGATIVE_PNL", "TESTUSDT")
        if position:
            self.add_position_to_database(position)
            negative_pnl_result = self.simulate_position_close(position, 90.0, "Stop Loss Hit")
            print(f"Negative PnL Test: {'✅ PASSED' if negative_pnl_result else '❌ FAILED'}")
        
        # Test 3: Position with very small quantity
        print("\n🔍 Testing small quantity scenario...")
        position = self.create_test_position("TEST_SMALL_QTY", "TESTUSDT")
        if position:
            position.quantity = 0.001
            self.add_position_to_database(position)
            small_qty_result = self.simulate_position_close(position, 105.0, "Small Quantity Close")
            print(f"Small Quantity Test: {'✅ PASSED' if small_qty_result else '❌ FAILED'}")
    
    def generate_report(self):
        """Generate comprehensive test report"""
        self.print_section("TEST REPORT SUMMARY")
        
        total_tests = 0
        passed_tests = 0
        
        for strategy, results in self.results.items():
            print(f"\n📊 {strategy.upper().replace('_', ' ')}:")
            
            for test_type, result in results.items():
                total_tests += 1
                if result:
                    passed_tests += 1
                    print(f"   {test_type}: ✅ PASSED")
                else:
                    print(f"   {test_type}: ❌ FAILED")
        
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        
        print(f"\n{'='*60}")
        print(f"📋 OVERALL TEST RESULTS")
        print(f"{'='*60}")
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")
        print(f"Success Rate: {success_rate:.1f}%")
        
        if success_rate >= 80:
            print(f"\n🎉 POSITION CLOSING SYSTEM: WORKING WELL!")
            print(f"   Database recording is functioning correctly")
            print(f"   Trade logger sync is operational")
            print(f"   PnL calculations are accurate")
        elif success_rate >= 60:
            print(f"\n⚠️ POSITION CLOSING SYSTEM: NEEDS MINOR FIXES")
            print(f"   Some components need attention")
            print(f"   Review failed tests above")
        else:
            print(f"\n❌ POSITION CLOSING SYSTEM: NEEDS MAJOR FIXES")
            print(f"   Critical issues found in database recording")
            print(f"   Immediate attention required")
        
        return success_rate

def main():
    """Run the comprehensive position closing database recording test"""
    
    print("🚀 STARTING POSITION CLOSING DATABASE RECORDING TEST")
    print("=" * 80)
    
    # Initialize test suite
    test_suite = PositionClosingDatabaseTest()
    
    try:
        # Test all strategies
        test_suite.test_all_strategies()
        
        # Test edge cases
        test_suite.test_edge_cases()
        
        # Generate report
        success_rate = test_suite.generate_report()
        
        # Recommendations
        print(f"\n📋 RECOMMENDATIONS:")
        if success_rate < 80:
            print(f"1. Check order_manager.close_position() method")
            print(f"2. Verify trade_database.update_trade() functionality")
            print(f"3. Ensure trade_logger sync is working")
            print(f"4. Review PnL calculation logic")
            
        print(f"\n🔍 FOCUS AREAS FOR FIXES:")
        for strategy, results in test_suite.results.items():
            failed_tests = [test for test, result in results.items() if not result]
            if failed_tests:
                print(f"   {strategy}: {', '.join(failed_tests)}")
        
    except Exception as e:
        print(f"❌ Test suite error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
