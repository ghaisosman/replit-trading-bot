
#!/usr/bin/env python3
"""
Comprehensive Engulfing Pattern Strategy Investigation Test
=========================================================

This test investigates the complete flow of the Engulfing Pattern strategy:
1. Strategy initialization and configuration
2. Market data scanning and entry signal detection
3. Trade execution and database logging
4. Position management and exit conditions
5. Trade closure and final logging

The strategy hasn't entered any positions since creation, so this test will
help identify where the flow might be breaking down.
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def test_engulfing_strategy_flow():
    """Main test function to investigate the complete Engulfing strategy flow"""
    
    print("🔍 ENGULFING PATTERN STRATEGY INVESTIGATION")
    print("=" * 80)
    print("Testing complete flow from signal detection to trade closure")
    print("Strategy status: No positions entered since creation")
    print("=" * 80)
    
    # Test 1: Strategy Configuration and Initialization
    print("\n📋 TEST 1: STRATEGY CONFIGURATION AND INITIALIZATION")
    print("-" * 60)
    test_strategy_configuration()
    
    # Test 2: Market Data and Indicator Calculation
    print("\n📊 TEST 2: MARKET DATA AND INDICATOR CALCULATION")
    print("-" * 60)
    test_market_data_and_indicators()
    
    # Test 3: Entry Signal Detection Logic
    print("\n🚨 TEST 3: ENTRY SIGNAL DETECTION LOGIC")
    print("-" * 60)
    test_entry_signal_detection()
    
    # Test 4: Trade Execution Simulation
    print("\n⚡ TEST 4: TRADE EXECUTION SIMULATION")
    print("-" * 60)
    test_trade_execution_flow()
    
    # Test 5: Database Logging Investigation
    print("\n💾 TEST 5: DATABASE LOGGING INVESTIGATION")
    print("-" * 60)
    test_database_logging()
    
    # Test 6: Exit Signal and Trade Closure
    print("\n🚪 TEST 6: EXIT SIGNAL AND TRADE CLOSURE")
    print("-" * 60)
    test_exit_signal_detection()
    
    # Test 7: Live Configuration Analysis
    print("\n🔧 TEST 7: LIVE CONFIGURATION ANALYSIS")
    print("-" * 60)
    test_live_configuration()
    
    print("\n" + "=" * 80)
    print("🎯 INVESTIGATION COMPLETE - Review results above")
    print("=" * 80)

def test_strategy_configuration():
    """Test 1: Verify strategy configuration and initialization"""
    try:
        from src.execution_engine.strategies.engulfing_pattern_strategy import EngulfingPatternStrategy
        from src.execution_engine.strategies.engulfing_pattern_config import DEFAULT_PARAMETERS, STRATEGY_DESCRIPTION
        
        print("✅ Engulfing strategy imports successful")
        
        # Test default configuration
        print(f"📄 Strategy Description: {STRATEGY_DESCRIPTION[:100]}...")
        print(f"🔧 Default Parameters: {DEFAULT_PARAMETERS}")
        
        # Create test configuration
        test_config = {
            'name': 'TEST_ENGULFING',
            'symbol': 'BTCUSDT',
            'margin': 50.0,
            'leverage': 3,
            'rsi_period': 14,
            'rsi_threshold': 50,
            'rsi_long_exit': 70,
            'rsi_short_exit': 30,
            'stable_candle_ratio': 0.5,
            'price_lookback_bars': 5,
            'max_loss_pct': 10
        }
        
        # Initialize strategy
        strategy = EngulfingPatternStrategy('TEST_ENGULFING', test_config)
        print("✅ Strategy initialization successful")
        print(f"   📊 RSI Period: {strategy.rsi_period}")
        print(f"   🎯 RSI Threshold: {strategy.rsi_threshold}")
        print(f"   🕯️ Stable Candle Ratio: {strategy.stable_candle_ratio}")
        print(f"   📈 Price Lookback Bars: {strategy.price_lookback_bars}")
        print(f"   🚪 Long Exit RSI: {strategy.rsi_long_exit}")
        print(f"   🚪 Short Exit RSI: {strategy.rsi_short_exit}")
        
        return True, strategy, test_config
        
    except Exception as e:
        print(f"❌ Strategy configuration test failed: {e}")
        import traceback
        print(f"🔍 Traceback: {traceback.format_exc()}")
        return False, None, None

def test_market_data_and_indicators():
    """Test 2: Check market data fetching and indicator calculation"""
    try:
        from src.binance_client.client import BinanceClientWrapper
        
        # Initialize Binance client
        binance_client = BinanceClientWrapper()
        print("✅ Binance client initialized")
        
        # Test symbols that might be used with Engulfing strategy
        test_symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
        
        for symbol in test_symbols:
            print(f"\n🔍 Testing market data for {symbol}:")
            
            try:
                # Get recent klines
                klines = binance_client.client.futures_klines(
                    symbol=symbol,
                    interval='1h',
                    limit=100
                )
                
                if not klines:
                    print(f"   ❌ No klines data for {symbol}")
                    continue
                
                print(f"   ✅ Retrieved {len(klines)} klines")
                
                # Convert to DataFrame for indicator calculation
                df = pd.DataFrame(klines, columns=[
                    'timestamp', 'open', 'high', 'low', 'close', 'volume',
                    'close_time', 'quote_asset_volume', 'number_of_trades',
                    'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
                ])
                
                # Convert to numeric
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = pd.to_numeric(df[col])
                
                print(f"   📊 DataFrame shape: {df.shape}")
                print(f"   💵 Latest price: ${df['close'].iloc[-1]:,.2f}")
                print(f"   📈 Price range: ${df['low'].min():,.2f} - ${df['high'].max():,.2f}")
                
                # Test indicator calculation
                strategy_config = {
                    'rsi_period': 14,
                    'rsi_threshold': 50,
                    'stable_candle_ratio': 0.5,
                    'price_lookback_bars': 5
                }
                
                from src.execution_engine.strategies.engulfing_pattern_strategy import EngulfingPatternStrategy
                strategy = EngulfingPatternStrategy('TEST', strategy_config)
                
                # Calculate indicators
                df_with_indicators = strategy.calculate_indicators(df)
                print(f"   📊 Indicators calculated, columns: {len(df_with_indicators.columns)}")
                
                # Check latest indicator values
                if 'rsi' in df_with_indicators.columns:
                    latest_rsi = df_with_indicators['rsi'].iloc[-1]
                    print(f"   📊 Latest RSI: {latest_rsi:.2f}" if not pd.isna(latest_rsi) else "   ⚠️ RSI: NaN")
                
                if 'bullish_engulfing' in df_with_indicators.columns:
                    bullish_signals = df_with_indicators['bullish_engulfing'].sum()
                    bearish_signals = df_with_indicators['bearish_engulfing'].sum()
                    print(f"   🟢 Bullish engulfing patterns: {bullish_signals}")
                    print(f"   🔴 Bearish engulfing patterns: {bearish_signals}")
                
                if 'stable_candle' in df_with_indicators.columns:
                    stable_candles = df_with_indicators['stable_candle'].sum()
                    print(f"   🕯️ Stable candles: {stable_candles}")
                
            except Exception as e:
                print(f"   ❌ Error testing {symbol}: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Market data test failed: {e}")
        import traceback
        print(f"🔍 Traceback: {traceback.format_exc()}")
        return False

def test_entry_signal_detection():
    """Test 3: Investigate entry signal detection logic"""
    try:
        print("🔍 Testing entry signal detection with simulated market conditions")
        
        # Create test scenarios for engulfing patterns
        test_scenarios = [
            {
                'name': 'Strong Bullish Engulfing + Oversold RSI',
                'data': create_bullish_engulfing_scenario(rsi_value=45),
                'expected': 'BUY signal'
            },
            {
                'name': 'Strong Bearish Engulfing + Overbought RSI',  
                'data': create_bearish_engulfing_scenario(rsi_value=55),
                'expected': 'SELL signal'
            },
            {
                'name': 'Bullish Engulfing but High RSI (No Signal)',
                'data': create_bullish_engulfing_scenario(rsi_value=65),
                'expected': 'No signal'
            },
            {
                'name': 'No Engulfing Pattern',
                'data': create_no_pattern_scenario(),
                'expected': 'No signal'
            }
        ]
        
        from src.execution_engine.strategies.engulfing_pattern_strategy import EngulfingPatternStrategy
        
        strategy_config = {
            'symbol': 'BTCUSDT',
            'margin': 50.0,
            'leverage': 3,
            'rsi_period': 14,
            'rsi_threshold': 50,
            'rsi_long_exit': 70,
            'rsi_short_exit': 30,
            'stable_candle_ratio': 0.5,
            'price_lookback_bars': 5,
            'max_loss_pct': 10
        }
        
        strategy = EngulfingPatternStrategy('TEST_ENGULFING', strategy_config)
        
        for i, scenario in enumerate(test_scenarios, 1):
            print(f"\n📊 Scenario {i}: {scenario['name']}")
            print("-" * 40)
            
            # Get test data
            df = scenario['data']
            print(f"   📈 Data points: {len(df)}")
            print(f"   💵 Latest price: ${df['close'].iloc[-1]:,.2f}")
            
            # Calculate indicators
            df_with_indicators = strategy.calculate_indicators(df)
            
            # Check signal detection
            signal = strategy.evaluate_entry_signal(df_with_indicators)
            
            if signal:
                print(f"   🚨 SIGNAL DETECTED: {signal.signal_type.value}")
                print(f"   💰 Entry Price: ${signal.entry_price:,.2f}")
                print(f"   🛡️ Stop Loss: ${signal.stop_loss:,.2f}")
                print(f"   🎯 Take Profit: ${signal.take_profit:,.2f}")
                print(f"   📝 Reason: {signal.reason}")
                print(f"   🎯 Confidence: {signal.confidence}")
            else:
                print(f"   ⚪ No signal detected")
            
            # Verify against expected result
            if signal and scenario['expected'] != 'No signal':
                if signal.signal_type.value in scenario['expected']:
                    print(f"   ✅ Result matches expectation: {scenario['expected']}")
                else:
                    print(f"   ⚠️ Unexpected signal type: Expected {scenario['expected']}, got {signal.signal_type.value}")
            elif not signal and scenario['expected'] == 'No signal':
                print(f"   ✅ Result matches expectation: {scenario['expected']}")
            else:
                print(f"   ❌ Result doesn't match expectation: Expected {scenario['expected']}, got {'signal' if signal else 'no signal'}")
            
            # Show current indicator values
            if len(df_with_indicators) > 0:
                latest_idx = -1
                rsi = df_with_indicators['rsi'].iloc[latest_idx] if 'rsi' in df_with_indicators.columns else None
                bullish = df_with_indicators['bullish_engulfing'].iloc[latest_idx] if 'bullish_engulfing' in df_with_indicators.columns else None
                bearish = df_with_indicators['bearish_engulfing'].iloc[latest_idx] if 'bearish_engulfing' in df_with_indicators.columns else None
                stable = df_with_indicators['stable_candle'].iloc[latest_idx] if 'stable_candle' in df_with_indicators.columns else None
                
                print(f"   📊 Current RSI: {rsi:.2f}" if rsi and not pd.isna(rsi) else "   📊 Current RSI: N/A")
                print(f"   🟢 Bullish Engulfing: {bullish}")
                print(f"   🔴 Bearish Engulfing: {bearish}")
                print(f"   🕯️ Stable Candle: {stable}")
        
        return True
        
    except Exception as e:
        print(f"❌ Entry signal detection test failed: {e}")
        import traceback
        print(f"🔍 Traceback: {traceback.format_exc()}")
        return False

def test_trade_execution_flow():
    """Test 4: Simulate trade execution flow"""
    try:
        print("🔍 Simulating trade execution flow without actual orders")
        
        # Import required classes
        from src.execution_engine.order_manager import OrderManager
        from src.binance_client.client import BinanceClientWrapper
        from src.analytics.trade_logger import trade_logger
        from src.strategy_processor.signal_processor import TradingSignal, SignalType
        
        # Initialize components
        binance_client = BinanceClientWrapper()
        order_manager = OrderManager(binance_client, trade_logger)
        
        print("✅ Order manager initialized")
        
        # Create test signal
        test_signal = TradingSignal(
            signal_type=SignalType.BUY,
            confidence=0.85,
            entry_price=50000.0,  # Example BTC price
            stop_loss=48000.0,
            take_profit=52000.0,
            symbol='BTCUSDT',
            reason="TEST: Bullish Engulfing + RSI 45 < 50 + Price down 5 bars"
        )
        
        # Create test strategy config
        strategy_config = {
            'name': 'TEST_ENGULFING_PATTERN',
            'symbol': 'BTCUSDT',
            'margin': 50.0,
            'leverage': 3,
            'decimals': 3,
            'rsi_period': 14,
            'rsi_threshold': 50,
            'max_loss_pct': 10
        }
        
        print(f"📊 Test Signal Created:")
        print(f"   💱 Symbol: {test_signal.symbol}")
        print(f"   📊 Type: {test_signal.signal_type.value}")
        print(f"   💰 Entry: ${test_signal.entry_price:,.2f}")
        print(f"   🛡️ Stop Loss: ${test_signal.stop_loss:,.2f}")
        print(f"   🎯 Take Profit: ${test_signal.take_profit:,.2f}")
        print(f"   📝 Reason: {test_signal.reason}")
        
        # Test position size calculation
        print(f"\n🔧 Testing Position Size Calculation:")
        quantity = order_manager._calculate_position_size(test_signal, strategy_config)
        print(f"   📏 Calculated Quantity: {quantity}")
        
        if quantity > 0:
            position_value = quantity * test_signal.entry_price
            margin_used = position_value / strategy_config['leverage']
            print(f"   💵 Position Value: ${position_value:,.2f} USDT")
            print(f"   💰 Margin Used: ${margin_used:,.2f} USDT")
            print(f"   📊 Target Margin: ${strategy_config['margin']:.2f} USDT")
            
            margin_diff = abs(margin_used - strategy_config['margin'])
            margin_diff_pct = (margin_diff / strategy_config['margin']) * 100
            print(f"   📈 Margin Difference: ${margin_diff:,.2f} ({margin_diff_pct:.1f}%)")
        else:
            print(f"   ❌ Invalid quantity calculated")
        
        # Test symbol info fetching
        print(f"\n📋 Testing Symbol Info:")
        symbol_info = order_manager._get_symbol_info(test_signal.symbol)
        print(f"   📏 Min Quantity: {symbol_info['min_qty']}")
        print(f"   📏 Step Size: {symbol_info['step_size']}")
        print(f"   📏 Precision: {symbol_info['precision']}")
        
        # Test trade ID generation
        trade_id = order_manager._generate_trade_id(strategy_config['name'], test_signal.symbol)
        print(f"\n🆔 Generated Trade ID: {trade_id}")
        
        # Test technical indicators calculation
        print(f"\n📊 Testing Technical Indicators:")
        indicators = order_manager._calculate_entry_indicators(test_signal.symbol)
        print(f"   📊 Indicators calculated: {len(indicators)} values")
        for key, value in indicators.items():
            if isinstance(value, (int, float)):
                print(f"   📈 {key}: {value:.4f}")
            else:
                print(f"   📈 {key}: {value}")
        
        # Test market conditions analysis
        print(f"\n🌍 Testing Market Conditions:")
        conditions = order_manager._analyze_market_conditions(test_signal.symbol)
        print(f"   🌍 Market conditions: {len(conditions)} factors")
        for key, value in conditions.items():
            print(f"   📊 {key}: {value}")
        
        return True
        
    except Exception as e:
        print(f"❌ Trade execution flow test failed: {e}")
        import traceback
        print(f"🔍 Traceback: {traceback.format_exc()}")
        return False

def test_database_logging():
    """Test 5: Investigate database logging functionality"""
    try:
        print("🔍 Testing database logging functionality")
        
        from src.execution_engine.trade_database import TradeDatabase
        from src.analytics.trade_logger import trade_logger
        
        # Initialize database
        trade_db = TradeDatabase()
        print(f"✅ Trade database initialized")
        print(f"   📊 Current trades in database: {len(trade_db.trades)}")
        
        # Check for existing Engulfing strategy trades
        engulfing_trades = []
        for trade_id, trade_data in trade_db.trades.items():
            strategy_name = trade_data.get('strategy_name', '')
            if 'engulfing' in strategy_name.lower():
                engulfing_trades.append((trade_id, trade_data))
        
        print(f"   🎯 Engulfing strategy trades found: {len(engulfing_trades)}")
        
        if engulfing_trades:
            print(f"   📋 Existing Engulfing trades:")
            for trade_id, trade_data in engulfing_trades:
                symbol = trade_data.get('symbol', 'N/A')
                status = trade_data.get('trade_status', 'N/A')
                timestamp = trade_data.get('timestamp', 'N/A')
                print(f"      • {trade_id}: {symbol} | {status} | {timestamp}")
        else:
            print(f"   ⚪ No Engulfing strategy trades found in database")
        
        # Test database write functionality with sample trade
        print(f"\n💾 Testing Database Write Functionality:")
        test_trade_data = {
            'trade_id': 'TEST_ENGULFING_BTCUSDT_20240101_120000',
            'strategy_name': 'TEST_ENGULFING_PATTERN',
            'symbol': 'BTCUSDT',
            'side': 'BUY',
            'quantity': 0.001,
            'entry_price': 50000.0,
            'trade_status': 'OPEN',
            'position_value_usdt': 50.0,
            'leverage': 3,
            'margin_used': 16.67,
            'stop_loss': 48000.0,
            'take_profit': 52000.0,
            'order_id': 12345678,
            'position_side': 'LONG'
        }
        
        # Try to add test trade
        add_success = trade_db.add_trade(test_trade_data['trade_id'], test_trade_data)
        print(f"   ✅ Test trade add: {'Success' if add_success else 'Failed'}")
        
        if add_success:
            # Verify trade was added
            retrieved_trade = trade_db.get_trade(test_trade_data['trade_id'])
            if retrieved_trade:
                print(f"   ✅ Test trade retrieval: Success")
                print(f"      • Symbol: {retrieved_trade.get('symbol')}")
                print(f"      • Margin: ${retrieved_trade.get('margin_used', 0):.2f}")
                print(f"      • Status: {retrieved_trade.get('trade_status')}")
            else:
                print(f"   ❌ Test trade retrieval: Failed")
            
            # Clean up test trade
            if test_trade_data['trade_id'] in trade_db.trades:
                del trade_db.trades[test_trade_data['trade_id']]
                trade_db._save_database()
                print(f"   🧹 Test trade cleaned up")
        
        # Test trade logger functionality
        print(f"\n📝 Testing Trade Logger:")
        print(f"   📊 Current logger trades: {len(trade_logger.trades)}")
        
        # Check for Engulfing trades in logger
        logger_engulfing_trades = []
        for trade_record in trade_logger.trades:
            if 'engulfing' in trade_record.strategy_name.lower():
                logger_engulfing_trades.append(trade_record)
        
        print(f"   🎯 Engulfing trades in logger: {len(logger_engulfing_trades)}")
        
        if logger_engulfing_trades:
            for trade_record in logger_engulfing_trades:
                print(f"      • {trade_record.trade_id}: {trade_record.symbol} | {trade_record.trade_status}")
        
        # Test database sync
        print(f"\n🔄 Testing Database Sync:")
        sync_count = trade_db.sync_from_logger()
        print(f"   📊 Trades synced from logger: {sync_count}")
        
        return True
        
    except Exception as e:
        print(f"❌ Database logging test failed: {e}")
        import traceback
        print(f"🔍 Traceback: {traceback.format_exc()}")
        return False

def test_exit_signal_detection():
    """Test 6: Test exit signal detection and trade closure"""
    try:
        print("🔍 Testing exit signal detection and trade closure logic")
        
        from src.execution_engine.strategies.engulfing_pattern_strategy import EngulfingPatternStrategy
        
        strategy_config = {
            'rsi_period': 14,
            'rsi_threshold': 50,
            'rsi_long_exit': 70,
            'rsi_short_exit': 30,
            'stable_candle_ratio': 0.5,
            'price_lookback_bars': 5
        }
        
        strategy = EngulfingPatternStrategy('TEST_ENGULFING', strategy_config)
        
        # Test scenarios for exit signals
        exit_scenarios = [
            {
                'name': 'Long Position - RSI Above Exit Level',
                'position': {'side': 'BUY'},
                'data': create_rsi_scenario(rsi_value=75),
                'expected': 'Exit signal'
            },
            {
                'name': 'Short Position - RSI Below Exit Level',
                'position': {'side': 'SELL'},
                'data': create_rsi_scenario(rsi_value=25),
                'expected': 'Exit signal'
            },
            {
                'name': 'Long Position - RSI Not at Exit Level',
                'position': {'side': 'BUY'},
                'data': create_rsi_scenario(rsi_value=60),
                'expected': 'No exit'
            },
            {
                'name': 'Short Position - RSI Not at Exit Level',
                'position': {'side': 'SELL'},
                'data': create_rsi_scenario(rsi_value=40),
                'expected': 'No exit'
            }
        ]
        
        for i, scenario in enumerate(exit_scenarios, 1):
            print(f"\n🚪 Exit Scenario {i}: {scenario['name']}")
            print("-" * 40)
            
            df = scenario['data']
            position = scenario['position']
            
            # Calculate indicators
            df_with_indicators = strategy.calculate_indicators(df)
            
            # Test exit signal
            exit_signal = strategy.evaluate_exit_signal(df_with_indicators, position)
            
            if exit_signal:
                print(f"   🚪 EXIT SIGNAL: {exit_signal}")
            else:
                print(f"   ⚪ No exit signal")
            
            # Show current RSI
            if 'rsi' in df_with_indicators.columns:
                current_rsi = df_with_indicators['rsi'].iloc[-1]
                print(f"   📊 Current RSI: {current_rsi:.2f}" if not pd.isna(current_rsi) else "   📊 Current RSI: N/A")
                print(f"   🎯 Exit thresholds: Long>{strategy.rsi_long_exit}, Short<{strategy.rsi_short_exit}")
            
            # Verify expectation
            has_exit = exit_signal is not None
            expected_exit = scenario['expected'] == 'Exit signal'
            
            if has_exit == expected_exit:
                print(f"   ✅ Result matches expectation: {scenario['expected']}")
            else:
                print(f"   ❌ Result doesn't match expectation: Expected {scenario['expected']}, got {'exit' if has_exit else 'no exit'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Exit signal detection test failed: {e}")
        import traceback
        print(f"🔍 Traceback: {traceback.format_exc()}")
        return False

def test_live_configuration():
    """Test 7: Analyze live configuration and potential issues"""
    try:
        print("🔍 Analyzing live configuration for potential issues")
        
        # Check if there's a configuration file or web dashboard data
        config_files = [
            'src/execution_engine/strategies/engulfing_pattern_config.py',
            'trading_data/strategy_configs.json',
            'config.json'
        ]
        
        for config_file in config_files:
            if os.path.exists(config_file):
                print(f"✅ Found config file: {config_file}")
                try:
                    if config_file.endswith('.py'):
                        # Import Python config
                        if 'engulfing_pattern_config' in config_file:
                            from src.execution_engine.strategies.engulfing_pattern_config import DEFAULT_PARAMETERS
                            print(f"   📋 Default parameters: {DEFAULT_PARAMETERS}")
                    elif config_file.endswith('.json'):
                        # Read JSON config
                        with open(config_file, 'r') as f:
                            config_data = json.load(f)
                        print(f"   📋 Config data keys: {list(config_data.keys()) if isinstance(config_data, dict) else 'Not a dict'}")
                except Exception as e:
                    print(f"   ⚠️ Error reading {config_file}: {e}")
            else:
                print(f"⚪ Config file not found: {config_file}")
        
        # Check for strategy registration in the system
        print(f"\n🔧 Checking Strategy Registration:")
        try:
            from src.bot_manager import BotManager
            from src.binance_client.client import BinanceClientWrapper
            from src.analytics.trade_logger import trade_logger
            
            # This would show how strategies are loaded
            print(f"   ✅ BotManager can be imported")
            print(f"   📝 Check if Engulfing strategy is properly registered in BotManager")
            
        except Exception as e:
            print(f"   ❌ Error importing BotManager: {e}")
        
        # Check web dashboard configuration
        print(f"\n🌐 Checking Web Dashboard Integration:")
        try:
            import web_dashboard
            print(f"   ✅ Web dashboard module accessible")
            print(f"   📋 Strategy should be configurable via web interface")
        except Exception as e:
            print(f"   ❌ Error importing web_dashboard: {e}")
        
        # Analyze potential configuration issues
        print(f"\n⚠️ Potential Configuration Issues:")
        
        issues_found = []
        
        # Check if strategy is enabled
        issues_found.append("🔍 Verify Engulfing strategy is enabled in web dashboard")
        issues_found.append("🔍 Check if strategy has valid symbol configuration")
        issues_found.append("🔍 Verify margin and leverage settings are appropriate")
        issues_found.append("🔍 Check if RSI thresholds are properly configured")
        issues_found.append("🔍 Verify timeframe is set correctly for pattern detection")
        issues_found.append("🔍 Check if bot is actually running in live mode (not just dashboard)")
        
        for issue in issues_found:
            print(f"   {issue}")
        
        # Recommendations
        print(f"\n💡 Troubleshooting Recommendations:")
        recommendations = [
            "1. Check web dashboard to ensure Engulfing strategy is enabled",
            "2. Verify strategy has proper symbol (BTCUSDT, ETHUSDT, etc.)",
            "3. Confirm margin > $20 for minimum position sizes",
            "4. Check timeframe setting (1H recommended for engulfing patterns)",
            "5. Verify RSI threshold is set to 50 (default)",
            "6. Check if candle stability ratio allows for pattern detection",
            "7. Ensure bot is running in live mode, not just dashboard preview",
            "8. Check Binance API permissions for futures trading",
            "9. Verify symbol has sufficient volatility for pattern formation",
            "10. Check logs for any error messages during strategy evaluation"
        ]
        
        for rec in recommendations:
            print(f"   {rec}")
        
        return True
        
    except Exception as e:
        print(f"❌ Live configuration analysis failed: {e}")
        import traceback
        print(f"🔍 Traceback: {traceback.format_exc()}")
        return False

def create_bullish_engulfing_scenario(rsi_value=45):
    """Create test data with bullish engulfing pattern"""
    # Create 100 data points for proper indicator calculation
    dates = pd.date_range(start='2024-01-01', periods=100, freq='H')
    
    # Base price data trending down, then engulfing pattern
    base_price = 50000
    prices = []
    
    for i in range(100):
        if i < 95:
            # Gradual downtrend
            price = base_price - (i * 50) + np.random.normal(0, 100)
        elif i == 98:
            # Previous bearish candle
            price = base_price - 4800
        elif i == 99:
            # Current bullish engulfing candle
            price = base_price - 4600  # Higher than previous open
        else:
            price = base_price - (i * 50) + np.random.normal(0, 100)
        
        prices.append(max(price, 1000))  # Ensure positive prices
    
    # Create OHLC data
    data = []
    for i, price in enumerate(prices):
        if i == 98:  # Previous bearish candle
            open_price = price + 200
            high_price = price + 250
            low_price = price - 50
            close_price = price  # Close lower than open (bearish)
        elif i == 99:  # Current bullish engulfing candle  
            prev_open = data[98]['open']
            open_price = price - 100  # Open below previous close
            high_price = price + 300
            low_price = price - 150
            close_price = prev_open + 100  # Close above previous open (engulfing)
        else:
            volatility = np.random.uniform(0.005, 0.02)
            high_price = price * (1 + volatility)
            low_price = price * (1 - volatility)
            open_price = price + np.random.uniform(-200, 200)
            close_price = price + np.random.uniform(-150, 150)
        
        data.append({
            'timestamp': dates[i],
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'volume': np.random.uniform(100, 1000)
        })
    
    df = pd.DataFrame(data)
    
    # Manually set RSI to desired value for testing
    df['rsi'] = rsi_value
    
    return df

def create_bearish_engulfing_scenario(rsi_value=55):
    """Create test data with bearish engulfing pattern"""
    dates = pd.date_range(start='2024-01-01', periods=100, freq='H')
    
    # Base price data trending up, then engulfing pattern
    base_price = 50000
    prices = []
    
    for i in range(100):
        if i < 95:
            # Gradual uptrend
            price = base_price + (i * 50) + np.random.normal(0, 100)
        elif i == 98:
            # Previous bullish candle
            price = base_price + 4800
        elif i == 99:
            # Current bearish engulfing candle
            price = base_price + 4600  # Lower than previous open
        else:
            price = base_price + (i * 50) + np.random.normal(0, 100)
        
        prices.append(max(price, 1000))
    
    data = []
    for i, price in enumerate(prices):
        if i == 98:  # Previous bullish candle
            open_price = price - 200
            high_price = price + 50
            low_price = price - 250
            close_price = price  # Close higher than open (bullish)
        elif i == 99:  # Current bearish engulfing candle
            prev_open = data[98]['open']
            open_price = price + 100  # Open above previous close
            high_price = price + 150
            low_price = price - 300
            close_price = prev_open - 100  # Close below previous open (engulfing)
        else:
            volatility = np.random.uniform(0.005, 0.02)
            high_price = price * (1 + volatility)
            low_price = price * (1 - volatility)
            open_price = price + np.random.uniform(-200, 200)
            close_price = price + np.random.uniform(-150, 150)
        
        data.append({
            'timestamp': dates[i],
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'volume': np.random.uniform(100, 1000)
        })
    
    df = pd.DataFrame(data)
    df['rsi'] = rsi_value
    
    return df

def create_no_pattern_scenario():
    """Create test data with no clear engulfing pattern"""
    dates = pd.date_range(start='2024-01-01', periods=100, freq='H')
    
    base_price = 50000
    data = []
    
    for i in range(100):
        price = base_price + np.random.normal(0, 500)  # Random walk
        volatility = np.random.uniform(0.005, 0.02)
        
        high_price = price * (1 + volatility)
        low_price = price * (1 - volatility)
        open_price = price + np.random.uniform(-200, 200)
        close_price = price + np.random.uniform(-150, 150)
        
        data.append({
            'timestamp': dates[i],
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'volume': np.random.uniform(100, 1000)
        })
    
    df = pd.DataFrame(data)
    df['rsi'] = 50  # Neutral RSI
    
    return df

def create_rsi_scenario(rsi_value=70):
    """Create test data with specific RSI value for exit testing"""
    dates = pd.date_range(start='2024-01-01', periods=50, freq='H')
    
    base_price = 50000
    data = []
    
    for i in range(50):
        price = base_price + np.random.normal(0, 200)
        volatility = np.random.uniform(0.005, 0.015)
        
        high_price = price * (1 + volatility)
        low_price = price * (1 - volatility)
        open_price = price + np.random.uniform(-100, 100)
        close_price = price + np.random.uniform(-75, 75)
        
        data.append({
            'timestamp': dates[i],
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'volume': np.random.uniform(100, 1000)
        })
    
    df = pd.DataFrame(data)
    df['rsi'] = rsi_value
    
    return df

if __name__ == "__main__":
    test_engulfing_strategy_flow()
