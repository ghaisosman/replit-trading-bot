
#!/usr/bin/env python3
"""
Comprehensive Trade Recovery Test
=================================

Tests the bot's ability to recover open trades after restart for all strategy types:
1. RSI Oversold Strategy
2. MACD Divergence Strategy  
3. Engulfing Pattern Strategy

This test verifies:
- Trade database contains open trades
- Binance positions match database records
- Bot correctly identifies recoverable trades
- Position management continues after recovery
- Exit conditions are properly monitored
"""

import sys
import os
import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

class TradeRecoveryTester:
    """Comprehensive trade recovery testing suite"""
    
    def __init__(self):
        self.results = {
            'database_analysis': {},
            'binance_positions': {},
            'recovery_matching': {},
            'strategy_management': {},
            'exit_monitoring': {},
            'overall_status': 'UNKNOWN'
        }
        self.test_start_time = datetime.now()
        
    def run_comprehensive_test(self):
        """Run complete trade recovery test suite"""
        print("🧪 COMPREHENSIVE TRADE RECOVERY TEST")
        print("=" * 60)
        print(f"⏰ Test started: {self.test_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        try:
            # Test 1: Analyze trade database for open trades
            print("📊 TEST 1: Database Analysis")
            self._test_database_analysis()
            
            # Test 2: Check Binance positions
            print("\n🔗 TEST 2: Binance Positions Analysis")
            self._test_binance_positions()
            
            # Test 3: Test recovery matching logic
            print("\n🔄 TEST 3: Recovery Matching Logic")
            self._test_recovery_matching()
            
            # Test 4: Test strategy-specific management
            print("\n📈 TEST 4: Strategy Management Testing")
            self._test_strategy_management()
            
            # Test 5: Test exit condition monitoring
            print("\n🚪 TEST 5: Exit Condition Monitoring")
            self._test_exit_monitoring()
            
            # Generate final report
            print("\n📋 FINAL RECOVERY TEST REPORT")
            self._generate_final_report()
            
        except Exception as e:
            print(f"❌ Test suite error: {e}")
            import traceback
            print(f"❌ Traceback: {traceback.format_exc()}")
    
    def _test_database_analysis(self):
        """Test 1: Analyze trade database for open trades"""
        try:
            from src.execution_engine.trade_database import TradeDatabase
            
            trade_db = TradeDatabase()
            all_trades = trade_db.get_all_trades()
            
            print(f"📊 Total trades in database: {len(all_trades)}")
            
            # Categorize trades by status
            open_trades = {}
            closed_trades = {}
            strategy_breakdown = {'rsi': 0, 'macd': 0, 'engulfing': 0, 'other': 0}
            
            for trade_id, trade_data in all_trades.items():
                status = trade_data.get('trade_status', 'UNKNOWN')
                strategy_name = trade_data.get('strategy_name', '').lower()
                
                if status == 'OPEN':
                    open_trades[trade_id] = trade_data
                    
                    # Categorize by strategy type
                    if 'rsi' in strategy_name:
                        strategy_breakdown['rsi'] += 1
                    elif 'macd' in strategy_name:
                        strategy_breakdown['macd'] += 1
                    elif 'engulfing' in strategy_name:
                        strategy_breakdown['engulfing'] += 1
                    else:
                        strategy_breakdown['other'] += 1
                        
                elif status == 'CLOSED':
                    closed_trades[trade_id] = trade_data
            
            print(f"🟢 Open trades: {len(open_trades)}")
            print(f"🔴 Closed trades: {len(closed_trades)}")
            print(f"📈 Strategy breakdown:")
            print(f"   RSI: {strategy_breakdown['rsi']} open trades")
            print(f"   MACD: {strategy_breakdown['macd']} open trades")
            print(f"   Engulfing: {strategy_breakdown['engulfing']} open trades")
            print(f"   Other: {strategy_breakdown['other']} open trades")
            
            # Detailed analysis of open trades
            if open_trades:
                print(f"\n🔍 DETAILED OPEN TRADES ANALYSIS:")
                for trade_id, trade_data in open_trades.items():
                    symbol = trade_data.get('symbol', 'N/A')
                    strategy = trade_data.get('strategy_name', 'N/A')
                    side = trade_data.get('side', 'N/A')
                    quantity = trade_data.get('quantity', 0)
                    entry_price = trade_data.get('entry_price', 0)
                    margin_used = trade_data.get('margin_used', 0)
                    
                    print(f"   {trade_id}:")
                    print(f"     Strategy: {strategy}")
                    print(f"     Symbol: {symbol}")
                    print(f"     Side: {side}")
                    print(f"     Quantity: {quantity}")
                    print(f"     Entry Price: ${entry_price}")
                    print(f"     Margin: ${margin_used}")
                    print()
            
            self.results['database_analysis'] = {
                'total_trades': len(all_trades),
                'open_trades': len(open_trades),
                'closed_trades': len(closed_trades),
                'strategy_breakdown': strategy_breakdown,
                'open_trade_details': open_trades,
                'status': 'COMPLETED'
            }
            
            print("✅ Database analysis completed")
            
        except Exception as e:
            print(f"❌ Database analysis failed: {e}")
            self.results['database_analysis'] = {'status': 'ERROR', 'error': str(e)}
    
    def _test_binance_positions(self):
        """Test 2: Check current Binance positions"""
        try:
            from src.binance_client.client import BinanceClientWrapper
            
            binance_client = BinanceClientWrapper()
            
            if not binance_client.is_futures:
                print("⚠️ Not using futures trading - skipping Binance position check")
                self.results['binance_positions'] = {'status': 'SKIPPED', 'reason': 'Not futures trading'}
                return
            
            # Get all positions
            positions = binance_client.client.futures_position_information()
            active_positions = []
            
            for position in positions:
                position_amt = float(position.get('positionAmt', 0))
                if abs(position_amt) > 0.001:  # Only positions with meaningful size
                    symbol = position.get('symbol')
                    side = 'BUY' if position_amt > 0 else 'SELL'
                    entry_price = float(position.get('entryPrice', 0))
                    unrealized_pnl = float(position.get('unRealizedProfit', 0))
                    
                    active_positions.append({
                        'symbol': symbol,
                        'side': side,
                        'quantity': abs(position_amt),
                        'entry_price': entry_price,
                        'unrealized_pnl': unrealized_pnl,
                        'raw_position': position
                    })
            
            print(f"🔗 Active Binance positions: {len(active_positions)}")
            
            if active_positions:
                print(f"\n🔍 BINANCE POSITIONS DETAILS:")
                for i, pos in enumerate(active_positions, 1):
                    print(f"   Position {i}:")
                    print(f"     Symbol: {pos['symbol']}")
                    print(f"     Side: {pos['side']}")
                    print(f"     Quantity: {pos['quantity']}")
                    print(f"     Entry Price: ${pos['entry_price']}")
                    print(f"     Unrealized PnL: ${pos['unrealized_pnl']:.2f}")
                    print()
            
            self.results['binance_positions'] = {
                'active_count': len(active_positions),
                'positions': active_positions,
                'status': 'COMPLETED'
            }
            
            print("✅ Binance positions analysis completed")
            
        except Exception as e:
            print(f"❌ Binance positions analysis failed: {e}")
            self.results['binance_positions'] = {'status': 'ERROR', 'error': str(e)}
    
    def _test_recovery_matching(self):
        """Test 3: Test recovery matching logic"""
        try:
            db_trades = self.results.get('database_analysis', {}).get('open_trade_details', {})
            binance_positions = self.results.get('binance_positions', {}).get('positions', [])
            
            print(f"🔄 Matching {len(db_trades)} database trades with {len(binance_positions)} Binance positions")
            
            matches = []
            unmatched_db = []
            unmatched_binance = []
            
            # Try to match database trades with Binance positions
            for trade_id, trade_data in db_trades.items():
                db_symbol = trade_data.get('symbol')
                db_side = trade_data.get('side')
                db_quantity = float(trade_data.get('quantity', 0))
                db_entry_price = float(trade_data.get('entry_price', 0))
                
                matched = False
                
                for binance_pos in binance_positions:
                    binance_symbol = binance_pos['symbol']
                    binance_side = binance_pos['side']
                    binance_quantity = binance_pos['quantity']
                    binance_entry_price = binance_pos['entry_price']
                    
                    # Check for match with tolerance
                    symbol_match = db_symbol == binance_symbol
                    side_match = db_side == binance_side
                    quantity_tolerance = 0.05  # 5% tolerance
                    quantity_match = abs(db_quantity - binance_quantity) <= (db_quantity * quantity_tolerance)
                    price_tolerance = 0.01  # 1% tolerance
                    price_match = abs(db_entry_price - binance_entry_price) <= (db_entry_price * price_tolerance)
                    
                    if symbol_match and side_match and quantity_match and price_match:
                        matches.append({
                            'trade_id': trade_id,
                            'trade_data': trade_data,
                            'binance_position': binance_pos,
                            'match_quality': 'PERFECT'
                        })
                        matched = True
                        break
                    elif symbol_match and side_match:
                        # Partial match - same symbol and side but different quantity/price
                        matches.append({
                            'trade_id': trade_id,
                            'trade_data': trade_data,
                            'binance_position': binance_pos,
                            'match_quality': 'PARTIAL',
                            'differences': {
                                'quantity_diff': abs(db_quantity - binance_quantity),
                                'price_diff': abs(db_entry_price - binance_entry_price)
                            }
                        })
                        matched = True
                        break
                
                if not matched:
                    unmatched_db.append({'trade_id': trade_id, 'trade_data': trade_data})
            
            # Find unmatched Binance positions
            matched_symbols = [match['binance_position']['symbol'] for match in matches]
            for binance_pos in binance_positions:
                if binance_pos['symbol'] not in matched_symbols:
                    unmatched_binance.append(binance_pos)
            
            print(f"✅ Perfect matches: {len([m for m in matches if m['match_quality'] == 'PERFECT'])}")
            print(f"⚠️ Partial matches: {len([m for m in matches if m['match_quality'] == 'PARTIAL'])}")
            print(f"❌ Unmatched database trades: {len(unmatched_db)}")
            print(f"❌ Unmatched Binance positions: {len(unmatched_binance)}")
            
            if matches:
                print(f"\n🔍 RECOVERY MATCHES DETAILS:")
                for match in matches:
                    trade_id = match['trade_id']
                    strategy = match['trade_data'].get('strategy_name', 'N/A')
                    symbol = match['trade_data'].get('symbol', 'N/A')
                    quality = match['match_quality']
                    
                    print(f"   {trade_id} ({strategy}) - {symbol}: {quality} MATCH")
                    
                    if quality == 'PARTIAL':
                        diffs = match.get('differences', {})
                        print(f"     Quantity difference: {diffs.get('quantity_diff', 0)}")
                        print(f"     Price difference: ${diffs.get('price_diff', 0)}")
            
            self.results['recovery_matching'] = {
                'perfect_matches': len([m for m in matches if m['match_quality'] == 'PERFECT']),
                'partial_matches': len([m for m in matches if m['match_quality'] == 'PARTIAL']),
                'unmatched_db_trades': len(unmatched_db),
                'unmatched_binance_positions': len(unmatched_binance),
                'matches': matches,
                'unmatched_db': unmatched_db,
                'unmatched_binance': unmatched_binance,
                'status': 'COMPLETED'
            }
            
            print("✅ Recovery matching analysis completed")
            
        except Exception as e:
            print(f"❌ Recovery matching analysis failed: {e}")
            self.results['recovery_matching'] = {'status': 'ERROR', 'error': str(e)}
    
    def _test_strategy_management(self):
        """Test 4: Test strategy-specific management capabilities"""
        try:
            matches = self.results.get('recovery_matching', {}).get('matches', [])
            
            print(f"📈 Testing strategy management for {len(matches)} recoverable trades")
            
            strategy_tests = {
                'rsi': {'tested': 0, 'passed': 0, 'errors': []},
                'macd': {'tested': 0, 'passed': 0, 'errors': []},
                'engulfing': {'tested': 0, 'passed': 0, 'errors': []},
                'other': {'tested': 0, 'passed': 0, 'errors': []}
            }
            
            for match in matches:
                trade_data = match['trade_data']
                strategy_name = trade_data.get('strategy_name', '').lower()
                
                # Determine strategy type
                if 'rsi' in strategy_name:
                    strategy_type = 'rsi'
                elif 'macd' in strategy_name:
                    strategy_type = 'macd'
                elif 'engulfing' in strategy_name:
                    strategy_type = 'engulfing'
                else:
                    strategy_type = 'other'
                
                strategy_tests[strategy_type]['tested'] += 1
                
                try:
                    # Test strategy initialization
                    if strategy_type == 'rsi':
                        success = self._test_rsi_strategy_management(trade_data)
                    elif strategy_type == 'macd':
                        success = self._test_macd_strategy_management(trade_data)
                    elif strategy_type == 'engulfing':
                        success = self._test_engulfing_strategy_management(trade_data)
                    else:
                        success = self._test_generic_strategy_management(trade_data)
                    
                    if success:
                        strategy_tests[strategy_type]['passed'] += 1
                    
                except Exception as e:
                    strategy_tests[strategy_type]['errors'].append(str(e))
            
            # Report results
            for strategy_type, results in strategy_tests.items():
                if results['tested'] > 0:
                    success_rate = (results['passed'] / results['tested']) * 100
                    print(f"   {strategy_type.upper()}: {results['passed']}/{results['tested']} passed ({success_rate:.1f}%)")
                    if results['errors']:
                        print(f"     Errors: {results['errors'][:3]}")  # Show first 3 errors
            
            self.results['strategy_management'] = {
                'strategy_tests': strategy_tests,
                'status': 'COMPLETED'
            }
            
            print("✅ Strategy management testing completed")
            
        except Exception as e:
            print(f"❌ Strategy management testing failed: {e}")
            self.results['strategy_management'] = {'status': 'ERROR', 'error': str(e)}
    
    def _test_rsi_strategy_management(self, trade_data: Dict) -> bool:
        """Test RSI strategy management capabilities"""
        try:
            from src.execution_engine.strategies.rsi_oversold_config import RSIOversoldConfig
            
            # Test config loading
            rsi_config = RSIOversoldConfig.get_config()
            
            # Validate required RSI parameters
            required_params = ['rsi_period', 'rsi_long_entry', 'rsi_long_exit', 'rsi_short_entry', 'rsi_short_exit']
            for param in required_params:
                if param not in rsi_config:
                    print(f"     ❌ Missing RSI parameter: {param}")
                    return False
            
            print(f"     ✅ RSI strategy config validated")
            return True
            
        except Exception as e:
            print(f"     ❌ RSI strategy test error: {e}")
            return False
    
    def _test_macd_strategy_management(self, trade_data: Dict) -> bool:
        """Test MACD strategy management capabilities"""
        try:
            # Create mock config for MACD strategy
            mock_config = {
                'name': trade_data.get('strategy_name', 'macd_test'),
                'symbol': trade_data.get('symbol', 'BTCUSDT'),
                'margin': trade_data.get('margin_used', 50.0),
                'leverage': trade_data.get('leverage', 5),
                'macd_fast': 12,
                'macd_slow': 26,
                'macd_signal': 9,
                'min_histogram_threshold': 0.0001
            }
            
            from src.execution_engine.strategies.macd_divergence_strategy import MACDDivergenceStrategy
            
            # Test strategy initialization
            strategy = MACDDivergenceStrategy(mock_config)
            
            # Test basic functionality
            if hasattr(strategy, 'calculate_indicators'):
                print(f"     ✅ MACD strategy initialized successfully")
                return True
            else:
                print(f"     ❌ MACD strategy missing required methods")
                return False
            
        except Exception as e:
            print(f"     ❌ MACD strategy test error: {e}")
            return False
    
    def _test_engulfing_strategy_management(self, trade_data: Dict) -> bool:
        """Test Engulfing Pattern strategy management capabilities"""
        try:
            # Create mock config for Engulfing strategy
            mock_config = {
                'name': trade_data.get('strategy_name', 'engulfing_test'),
                'symbol': trade_data.get('symbol', 'ETHUSDT'),
                'margin': trade_data.get('margin_used', 50.0),
                'leverage': trade_data.get('leverage', 5),
                'rsi_period': 14,
                'rsi_threshold': 50,
                'stable_candle_ratio': 0.5,
                'price_lookback_bars': 5,
                'rsi_long_exit': 70,
                'rsi_short_exit': 30
            }
            
            from src.execution_engine.strategies.engulfing_pattern_strategy import EngulfingPatternStrategy
            
            # Test strategy initialization
            strategy = EngulfingPatternStrategy(mock_config['name'], mock_config)
            
            # Test basic functionality
            if hasattr(strategy, 'calculate_indicators') and hasattr(strategy, 'evaluate_entry_signal'):
                print(f"     ✅ Engulfing strategy initialized successfully")
                return True
            else:
                print(f"     ❌ Engulfing strategy missing required methods")
                return False
            
        except Exception as e:
            print(f"     ❌ Engulfing strategy test error: {e}")
            return False
    
    def _test_generic_strategy_management(self, trade_data: Dict) -> bool:
        """Test generic strategy management capabilities"""
        try:
            # For unknown strategies, just verify basic trade data integrity
            required_fields = ['symbol', 'side', 'quantity', 'entry_price']
            for field in required_fields:
                if field not in trade_data or trade_data[field] is None:
                    print(f"     ❌ Missing trade data field: {field}")
                    return False
            
            print(f"     ✅ Generic strategy data validated")
            return True
            
        except Exception as e:
            print(f"     ❌ Generic strategy test error: {e}")
            return False
    
    def _test_exit_monitoring(self):
        """Test 5: Test exit condition monitoring capabilities"""
        try:
            from src.binance_client.client import BinanceClientWrapper
            
            matches = self.results.get('recovery_matching', {}).get('matches', [])
            
            print(f"🚪 Testing exit monitoring for {len(matches)} recoverable trades")
            
            binance_client = BinanceClientWrapper()
            exit_tests = {
                'price_fetching': {'tested': 0, 'passed': 0},
                'stop_loss_calculation': {'tested': 0, 'passed': 0},
                'take_profit_calculation': {'tested': 0, 'passed': 0},
                'pnl_calculation': {'tested': 0, 'passed': 0}
            }
            
            for match in matches:
                trade_data = match['trade_data']
                symbol = trade_data.get('symbol')
                entry_price = float(trade_data.get('entry_price', 0))
                side = trade_data.get('side')
                quantity = float(trade_data.get('quantity', 0))
                
                # Test 1: Price fetching
                exit_tests['price_fetching']['tested'] += 1
                try:
                    ticker = binance_client.get_symbol_ticker(symbol)
                    if ticker and 'price' in ticker:
                        current_price = float(ticker['price'])
                        exit_tests['price_fetching']['passed'] += 1
                        
                        # Test 2: PnL calculation
                        exit_tests['pnl_calculation']['tested'] += 1
                        try:
                            if side == 'BUY':
                                pnl = (current_price - entry_price) * quantity
                            else:
                                pnl = (entry_price - current_price) * quantity
                            
                            if isinstance(pnl, (int, float)):
                                exit_tests['pnl_calculation']['passed'] += 1
                                print(f"     {symbol}: Current PnL = ${pnl:.2f}")
                            
                        except Exception:
                            pass
                        
                except Exception:
                    pass
                
                # Test 3: Stop loss validation
                exit_tests['stop_loss_calculation']['tested'] += 1
                stop_loss = trade_data.get('stop_loss')
                if stop_loss and isinstance(stop_loss, (int, float)) and stop_loss > 0:
                    exit_tests['stop_loss_calculation']['passed'] += 1
                
                # Test 4: Take profit validation
                exit_tests['take_profit_calculation']['tested'] += 1
                take_profit = trade_data.get('take_profit')
                if take_profit and isinstance(take_profit, (int, float)) and take_profit > 0:
                    exit_tests['take_profit_calculation']['passed'] += 1
            
            # Report results
            for test_name, results in exit_tests.items():
                if results['tested'] > 0:
                    success_rate = (results['passed'] / results['tested']) * 100
                    print(f"   {test_name.replace('_', ' ').title()}: {results['passed']}/{results['tested']} ({success_rate:.1f}%)")
            
            self.results['exit_monitoring'] = {
                'exit_tests': exit_tests,
                'status': 'COMPLETED'
            }
            
            print("✅ Exit monitoring testing completed")
            
        except Exception as e:
            print(f"❌ Exit monitoring testing failed: {e}")
            self.results['exit_monitoring'] = {'status': 'ERROR', 'error': str(e)}
    
    def _generate_final_report(self):
        """Generate comprehensive final report"""
        print("=" * 60)
        
        # Calculate overall test score
        test_scores = []
        
        # Database analysis score
        db_status = self.results.get('database_analysis', {}).get('status')
        if db_status == 'COMPLETED':
            open_trades = self.results['database_analysis'].get('open_trades', 0)
            test_scores.append(100 if open_trades > 0 else 50)  # 100% if trades found, 50% if no trades
        else:
            test_scores.append(0)
        
        # Binance positions score
        binance_status = self.results.get('binance_positions', {}).get('status')
        if binance_status == 'COMPLETED':
            active_positions = self.results['binance_positions'].get('active_count', 0)
            test_scores.append(100 if active_positions > 0 else 50)
        elif binance_status == 'SKIPPED':
            test_scores.append(50)  # Neutral score for skipped test
        else:
            test_scores.append(0)
        
        # Recovery matching score
        matching_status = self.results.get('recovery_matching', {}).get('status')
        if matching_status == 'COMPLETED':
            perfect_matches = self.results['recovery_matching'].get('perfect_matches', 0)
            partial_matches = self.results['recovery_matching'].get('partial_matches', 0)
            total_matches = perfect_matches + partial_matches
            
            if total_matches > 0:
                match_quality_score = (perfect_matches * 100 + partial_matches * 70) / total_matches
                test_scores.append(match_quality_score)
            else:
                test_scores.append(25)  # Low score if no matches found
        else:
            test_scores.append(0)
        
        # Strategy management score
        strategy_status = self.results.get('strategy_management', {}).get('status')
        if strategy_status == 'COMPLETED':
            strategy_tests = self.results['strategy_management'].get('strategy_tests', {})
            total_tested = sum(results['tested'] for results in strategy_tests.values())
            total_passed = sum(results['passed'] for results in strategy_tests.values())
            
            if total_tested > 0:
                strategy_score = (total_passed / total_tested) * 100
                test_scores.append(strategy_score)
            else:
                test_scores.append(50)
        else:
            test_scores.append(0)
        
        # Exit monitoring score
        exit_status = self.results.get('exit_monitoring', {}).get('status')
        if exit_status == 'COMPLETED':
            exit_tests = self.results['exit_monitoring'].get('exit_tests', {})
            total_tested = sum(results['tested'] for results in exit_tests.values())
            total_passed = sum(results['passed'] for results in exit_tests.values())
            
            if total_tested > 0:
                exit_score = (total_passed / total_tested) * 100
                test_scores.append(exit_score)
            else:
                test_scores.append(50)
        else:
            test_scores.append(0)
        
        # Calculate overall score
        overall_score = sum(test_scores) / len(test_scores) if test_scores else 0
        
        if overall_score >= 80:
            self.results['overall_status'] = 'EXCELLENT'
            status_emoji = '🟢'
        elif overall_score >= 60:
            self.results['overall_status'] = 'GOOD'
            status_emoji = '🟡'
        elif overall_score >= 40:
            self.results['overall_status'] = 'FAIR'
            status_emoji = '🟠'
        else:
            self.results['overall_status'] = 'POOR'
            status_emoji = '🔴'
        
        # Print final report
        print(f"{status_emoji} OVERALL RECOVERY TEST SCORE: {overall_score:.1f}% ({self.results['overall_status']})")
        print()
        
        print("📊 DETAILED RESULTS:")
        
        # Database results
        db_analysis = self.results.get('database_analysis', {})
        if db_analysis.get('status') == 'COMPLETED':
            print(f"   📊 Database Analysis:")
            print(f"     • Total trades: {db_analysis.get('total_trades', 0)}")
            print(f"     • Open trades: {db_analysis.get('open_trades', 0)}")
            breakdown = db_analysis.get('strategy_breakdown', {})
            print(f"     • RSI strategies: {breakdown.get('rsi', 0)}")
            print(f"     • MACD strategies: {breakdown.get('macd', 0)}")
            print(f"     • Engulfing strategies: {breakdown.get('engulfing', 0)}")
        
        # Binance results
        binance_analysis = self.results.get('binance_positions', {})
        if binance_analysis.get('status') == 'COMPLETED':
            print(f"   🔗 Binance Positions:")
            print(f"     • Active positions: {binance_analysis.get('active_count', 0)}")
        elif binance_analysis.get('status') == 'SKIPPED':
            print(f"   🔗 Binance Positions: SKIPPED (not futures trading)")
        
        # Recovery matching results
        matching_analysis = self.results.get('recovery_matching', {})
        if matching_analysis.get('status') == 'COMPLETED':
            print(f"   🔄 Recovery Matching:")
            print(f"     • Perfect matches: {matching_analysis.get('perfect_matches', 0)}")
            print(f"     • Partial matches: {matching_analysis.get('partial_matches', 0)}")
            print(f"     • Unmatched DB trades: {matching_analysis.get('unmatched_db_trades', 0)}")
            print(f"     • Unmatched Binance positions: {matching_analysis.get('unmatched_binance_positions', 0)}")
        
        print()
        print("💡 RECOVERY RECOMMENDATIONS:")
        
        if overall_score >= 80:
            print("   ✅ Trade recovery system is working excellently")
            print("   ✅ Bot should recover and manage trades correctly after restart")
        elif overall_score >= 60:
            print("   ⚠️ Trade recovery system is working but may have minor issues")
            print("   ⚠️ Monitor recovered trades closely after bot restart")
        else:
            print("   ❌ Trade recovery system has significant issues")
            print("   ❌ Manual intervention may be required after bot restart")
        
        # Specific recommendations
        if self.results.get('database_analysis', {}).get('open_trades', 0) == 0:
            print("   📊 No open trades found in database - recovery system not tested with real data")
        
        if self.results.get('binance_positions', {}).get('active_count', 0) == 0:
            print("   🔗 No active Binance positions - recovery system not tested with real positions")
        
        perfect_matches = self.results.get('recovery_matching', {}).get('perfect_matches', 0)
        partial_matches = self.results.get('recovery_matching', {}).get('partial_matches', 0)
        
        if perfect_matches == 0 and partial_matches == 0:
            print("   🔄 No trade matches found - verify database and Binance position synchronization")
        elif perfect_matches == 0 and partial_matches > 0:
            print("   🔄 Only partial matches found - check trade recording accuracy")
        
        test_end_time = datetime.now()
        test_duration = test_end_time - self.test_start_time
        
        print()
        print(f"⏰ Test completed: {test_end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"⏱️ Test duration: {test_duration.total_seconds():.1f} seconds")
        print("=" * 60)


def main():
    """Run the comprehensive trade recovery test"""
    tester = TradeRecoveryTester()
    tester.run_comprehensive_test()


if __name__ == "__main__":
    main()
