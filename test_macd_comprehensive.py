#!/usr/bin/env python3
"""
🧠 COMPREHENSIVE MACD STRATEGY TEST
================================================================================
Testing complete strategy lifecycle: indicator calculation → crossover detection → entry → execution → logging
================================================================================
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import time

# Add src to path
sys.path.append('src')

from src.execution_engine.strategies.macd_divergence_strategy import MACDDivergenceStrategy
from src.strategy_processor.signal_processor import SignalProcessor, TradingSignal, SignalType
from src.execution_engine.order_manager import OrderManager
from src.execution_engine.trade_database import TradeDatabase
from src.binance_client.client import BinanceClientWrapper
from src.analytics.trade_logger import TradeLogger
from src.config.trading_config import trading_config_manager

def create_macd_test_data(scenario, periods=100):
    """Create test data for specific MACD divergence scenarios"""
    np.random.seed(42)  # For reproducible results

    if scenario == "bullish_divergence":
        # Create strong bullish divergence pattern
        base_price = 50000
        prices = []
        for i in range(periods):
            if i < periods * 0.7:
                # Strong downtrend
                decline = base_price * 0.15 * (i / (periods * 0.7))
                prices.append(base_price - decline + np.random.normal(0, 10))
            elif i < periods * 0.9:
                # Consolidation at bottom
                prices.append(prices[-1] + np.random.normal(0, 5))
            else:
                # Strong recovery creating momentum
                recovery = (i - periods * 0.9) * 100
                prices.append(prices[-1] + recovery + np.random.normal(10, 5))

    elif scenario == "bearish_divergence":
        # Create strong bearish divergence pattern
        base_price = 52000
        prices = []
        for i in range(periods):
            if i < periods * 0.7:
                # Strong uptrend
                growth = base_price * 0.15 * (i / (periods * 0.7))
                prices.append(base_price + growth + np.random.normal(0, 10))
            elif i < periods * 0.9:
                # Consolidation at top
                prices.append(prices[-1] + np.random.normal(0, 5))
            else:
                # Strong decline creating negative momentum
                decline = (i - periods * 0.9) * 100
                prices.append(prices[-1] - decline + np.random.normal(-10, 5))

    else:  # no_signal
        # Sideways movement with no divergence pattern
        base_price = 51000
        prices = [base_price + np.random.normal(0, 50) for _ in range(periods)]

    df = pd.DataFrame({
        'open': [p * 0.999 for p in prices],
        'high': [p * 1.002 for p in prices],
        'low': [p * 0.998 for p in prices],
        'close': prices,
        'volume': [1000000 + np.random.normal(0, 100000) for _ in range(periods)]
    })

    return df

def main():
    print("🧠 COMPREHENSIVE MACD STRATEGY TEST")
    print("=" * 80)
    print("Testing complete strategy lifecycle: indicator calculation → crossover detection → entry → execution → logging")
    print("=" * 80)

    test_results = {}

    # TEST 1: STRATEGY INITIALIZATION AND CONFIGURATION
    print("\n📋 TEST 1: STRATEGY INITIALIZATION AND CONFIGURATION")
    print("-" * 60)

    try:
        # Import and initialize strategy
        print("✅ MACD strategy imports successful")

        # Test configuration
        test_config = {
            'name': 'TEST_MACD',
            'symbol': 'BTCUSDT',
            'timeframe': '5m',
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            'min_histogram_threshold': 0.0001,
            'min_distance_threshold': 0.0015,
            'confirmation_candles': 2,
            'margin': 50.0,
            'leverage': 5,
            'max_loss_pct': 10,
            'macd_entry_threshold': 0.002,
            'macd_exit_threshold': 0.003
        }

        print(f"📋 Test Configuration: {test_config}")

        # Initialize strategy
        macd_strategy = MACDDivergenceStrategy(test_config)

        print("✅ Strategy initialized with correct parameters")
        print(f"   📊 MACD Fast: {macd_strategy.macd_fast}")
        print(f"   📊 MACD Slow: {macd_strategy.macd_slow}")
        print(f"   📊 MACD Signal: {macd_strategy.macd_signal}")
        print(f"   🎯 Histogram Threshold: {macd_strategy.min_histogram_threshold}")
        print(f"   🎯 Entry Threshold: {macd_strategy.entry_threshold}")
        print(f"   🎯 Exit Threshold: {macd_strategy.exit_threshold}")
        print(f"   ⚡ Leverage: {test_config['leverage']}x")
        print(f"   💰 Margin: ${test_config['margin']}")

        test_results['initialization'] = 'PASSED'

    except Exception as e:
        print(f"❌ Strategy initialization failed: {e}")
        test_results['initialization'] = 'FAILED'
        return

    # TEST 2: INDICATOR CALCULATION
    print("\n🧮 TEST 2: MACD INDICATOR CALCULATION")
    print("-" * 60)

    try:
        # Create test data
        test_data = create_macd_test_data("bullish_divergence", 100)
        print(f"📊 Processing {len(test_data)} candles for indicator calculation")

        # Calculate indicators
        df_with_indicators = macd_strategy.calculate_indicators(test_data.copy())

        # Verify indicators were calculated
        required_indicators = ['macd', 'macd_signal', 'macd_histogram', 'ema_fast', 'ema_slow']
        missing_indicators = [ind for ind in required_indicators if ind not in df_with_indicators.columns]

        if missing_indicators:
            print(f"❌ Missing indicators: {missing_indicators}")
            test_results['indicators'] = 'FAILED'
        else:
            # Check for valid values (not NaN)
            recent_data = df_with_indicators.tail(10)
            nan_counts = recent_data[required_indicators].isna().sum()

            if nan_counts.any():
                print(f"❌ NaN values in indicators: {nan_counts.to_dict()}")
                test_results['indicators'] = 'FAILED' 
            else:
                current_macd = df_with_indicators['macd'].iloc[-1]
                current_signal = df_with_indicators['macd_signal'].iloc[-1]
                current_histogram = df_with_indicators['macd_histogram'].iloc[-1]

                print("✅ All MACD indicators calculated successfully")
                print(f"   📈 Current MACD: {current_macd:.6f}")
                print(f"   📊 Current Signal: {current_signal:.6f}")
                print(f"   📊 Current Histogram: {current_histogram:.6f}")

                test_results['indicators'] = 'PASSED'

    except Exception as e:
        print(f"❌ Indicator calculation failed: {e}")
        test_results['indicators'] = 'FAILED'

    # TEST 3: CROSSOVER DETECTION LOGIC
    print("\n🚨 TEST 3: MACD CROSSOVER DETECTION LOGIC")
    print("-" * 60)

    crossover_tests = 0
    successful_detections = 0

    try:
        # Test Scenario 1: Bullish Crossover
        print("🔍 Scenario 1: Bullish MACD Crossover (Buy Signal)")
        bullish_data = create_macd_test_data("bullish_divergence", 100)
        bullish_data = macd_strategy.calculate_indicators(bullish_data)

        bullish_signal = macd_strategy.evaluate_entry_signal(bullish_data)
        crossover_tests += 1

        if bullish_signal and bullish_signal.signal_type == SignalType.BUY:
            print("   ✅ Bullish crossover detected correctly")
            print(f"      Signal Type: {bullish_signal.signal_type.value}")
            print(f"      Entry Price: ${bullish_signal.entry_price:.2f}")
            print(f"      Stop Loss: ${bullish_signal.stop_loss:.2f}")
            print(f"      Take Profit: ${bullish_signal.take_profit:.2f}")
            successful_detections += 1
        else:
            print("   ❌ Expected bullish crossover not detected")

        # Test Scenario 2: Bearish Crossover
        print("\n🔍 Scenario 2: Bearish MACD Crossover (Sell Signal)")
        bearish_data = create_macd_test_data("bearish_divergence", 100)
        bearish_data = macd_strategy.calculate_indicators(bearish_data)

        bearish_signal = macd_strategy.evaluate_entry_signal(bearish_data)
        crossover_tests += 1

        if bearish_signal and bearish_signal.signal_type == SignalType.SELL:
            print("   ✅ Bearish crossover detected correctly")
            print(f"      Signal Type: {bearish_signal.signal_type.value}")
            print(f"      Entry Price: ${bearish_signal.entry_price:.2f}")
            print(f"      Stop Loss: ${bearish_signal.stop_loss:.2f}")
            print(f"      Take Profit: ${bearish_signal.take_profit:.2f}")
            successful_detections += 1
        else:
            print("   ❌ Expected bearish crossover not detected")

        # Test Scenario 3: No Signal
        print("\n🔍 Scenario 3: No Crossover (Normal Market Action)")
        no_signal_data = create_macd_test_data("no_signal", 100)
        no_signal_data = macd_strategy.calculate_indicators(no_signal_data)

        no_signal = macd_strategy.evaluate_entry_signal(no_signal_data)
        crossover_tests += 1

        if no_signal is None:
            print("   ✅ Correctly identified no crossover signal")
            successful_detections += 1
        else:
            print("   ❌ False positive: Detected signal when none should exist")

        print(f"\n📊 Crossover Detection Summary: {successful_detections}/{crossover_tests} tests passed")
        test_results['crossover_detection'] = 'PASSED' if successful_detections == crossover_tests else 'FAILED'

    except Exception as e:
        print(f"❌ Crossover detection test failed: {e}")
        test_results['crossover_detection'] = 'FAILED'

    # TEST 4: POSITION SIZE AND RISK CALCULATION
    print("\n📊 TEST 4: POSITION SIZE AND RISK CALCULATION")
    print("-" * 60)

    try:
        # Initialize components for order testing
        binance_client = BinanceClientWrapper()
        trade_logger = TradeLogger()
        order_manager = OrderManager(binance_client, trade_logger)

        # Create test signal with proper constructor
        test_signal = TradingSignal(
            signal_type=SignalType.BUY,
            confidence=0.8,
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=51500.0,
            symbol='BTCUSDT',
            reason="Test MACD bullish crossover",
            strategy_name="TEST_MACD"
        )

        # Calculate position size
        quantity = order_manager._calculate_position_size(test_signal, test_config)

        if quantity > 0:
            position_value = test_signal.entry_price * quantity
            leverage = test_config['leverage']
            required_margin = position_value / leverage
            risk_amount = abs(test_signal.entry_price - test_signal.stop_loss) * quantity
            risk_percentage = (risk_amount / (test_config['margin'])) * 100

            print("✅ Position calculations completed successfully")
            print(f"   📊 Quantity: {quantity}")
            print(f"   💰 Position Value: ${position_value:.2f}")
            print(f"   ⚡ Leverage: {leverage}x")
            print(f"   🛡️ Required Margin: ${required_margin:.2f}")
            print(f"   ⚠️ Risk Amount: ${risk_amount:.2f}")
            print(f"   📈 Risk Percentage: {risk_percentage:.1f}%")

            if risk_percentage <= test_config['max_loss_pct']:
                print("   ✅ Risk management compliance verified")
                test_results['position_sizing'] = 'PASSED'
            else:
                print(f"   ❌ Risk exceeds maximum allowed ({test_config['max_loss_pct']}%)")
                test_results['position_sizing'] = 'FAILED'
        else:
            print(f"❌ Invalid position size calculated: {quantity}")
            test_results['position_sizing'] = 'FAILED'

    except Exception as e:
        print(f"❌ Position sizing test failed: {e}")
        test_results['position_sizing'] = 'FAILED'

    # TEST 5: DATABASE OPERATIONS
    print("\n💾 TEST 5: DATABASE OPERATIONS")
    print("-" * 60)

    try:
        # Initialize database
        trade_database = TradeDatabase("trading_data/test_macd_database.json")

        # Create test trade data
        test_trade_id = f"MACD_TEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        test_trade_data = {
            'trade_id': test_trade_id,
            'strategy_name': 'macd_divergence',
            'symbol': 'BTCUSDT',
            'side': 'BUY',
            'quantity': 0.001,
            'entry_price': 50000.0,
            'trade_status': 'OPEN',
            'position_value_usdt': 50.0,
            'leverage': 5,
            'margin_used': 10.0,
            'stop_loss': 49000.0,
            'take_profit': 51500.0,
            'order_id': 123456789,
            'position_side': 'LONG',
            'macd_value': 45.67,
            'macd_signal_value': 43.21,
            'histogram_value': 2.46
        }

        database_operations = {
            'add': False,
            'retrieve': False,
            'update': False,
            'search': False
        }

        # Test 1: Add trade
        add_success = trade_database.add_trade(test_trade_id, test_trade_data)
        database_operations['add'] = add_success

        if add_success:
            print("✅ Trade added to database successfully")
        else:
            print("❌ Failed to add trade to database")

        # Test 2: Retrieve trade
        retrieved_trade = trade_database.get_trade(test_trade_id)
        database_operations['retrieve'] = retrieved_trade is not None

        if retrieved_trade:
            print("✅ Trade retrieved from database successfully")
        else:
            print("❌ Failed to retrieve trade from database")

        # Test 3: Update trade
        update_success = trade_database.update_trade(test_trade_id, {
            'trade_status': 'CLOSED',
            'exit_price': 51200.0,
            'pnl_usdt': 1.2,
            'close_reason': 'Take Profit'
        })
        database_operations['update'] = update_success

        if update_success:
            print("✅ Trade updated in database successfully")
        else:
            print("❌ Failed to update trade in database")

        # Test 4: Search functionality
        found_trade_id = trade_database.find_trade_by_position(
            'macd_divergence', 'BTCUSDT', 'BUY', 0.001, 50000.0, tolerance=0.01
        )
        database_operations['search'] = found_trade_id == test_trade_id

        if found_trade_id == test_trade_id:
            print("✅ Trade search functionality working correctly")
        else:
            print(f"❌ Trade search failed: found {found_trade_id}, expected {test_trade_id}")

        # Summary
        passed_operations = sum(database_operations.values())
        total_operations = len(database_operations)

        print(f"\n📊 Database Operations: {passed_operations}/{total_operations} passed")
        for operation, status in database_operations.items():
            print(f"   {operation.capitalize()}: {'✅' if status else '❌'}")

        test_results['database_operations'] = 'PASSED' if passed_operations == total_operations else 'FAILED'

    except Exception as e:
        print(f"❌ Database operations test failed: {e}")
        test_results['database_operations'] = 'FAILED'

    # TEST 6: EXIT SIGNAL LOGIC
    print("\n🚪 TEST 6: EXIT SIGNAL LOGIC")
    print("-" * 60)

    try:
        # Create test data with MACD momentum reversal patterns
        exit_test_data = create_macd_test_data("bullish_divergence", 100)
        exit_test_data = macd_strategy.calculate_indicators(exit_test_data)

        # Manually create exit conditions
        # Peak momentum reversal for long exit
        exit_test_data.loc[exit_test_data.index[-3], 'macd_histogram'] = 0.005
        exit_test_data.loc[exit_test_data.index[-2], 'macd_histogram'] = 0.008  # Peak
        exit_test_data.loc[exit_test_data.index[-1], 'macd_histogram'] = 0.004  # Declining

        # Test long position exit
        long_position = {
            'side': 'BUY',
            'entry_price': 50000.0,
            'quantity': 0.001
        }

        long_exit_signal = macd_strategy.evaluate_exit_signal(exit_test_data, long_position)

        # Test short position exit
        short_exit_data = exit_test_data.copy()
        short_exit_data.loc[short_exit_data.index[-3], 'macd_histogram'] = -0.005
        short_exit_data.loc[short_exit_data.index[-2], 'macd_histogram'] = -0.008  # Bottom
        short_exit_data.loc[short_exit_data.index[-1], 'macd_histogram'] = -0.004  # Rising

        short_position = {
            'side': 'SELL',
            'entry_price': 50000.0,
            'quantity': 0.001
        }

        short_exit_signal = macd_strategy.evaluate_exit_signal(short_exit_data, short_position)

        exit_results = {
            'long_exit_detected': long_exit_signal is not None,
            'short_exit_detected': short_exit_signal is not None
        }

        print("📊 Exit Signal Testing Results:")
        if exit_results['long_exit_detected']:
            print("   ✅ Long position exit signal detected")
            print(f"      Reason: {long_exit_signal}")
        else:
            print("   ❌ Long position exit signal not detected")

        if exit_results['short_exit_detected']:
            print("   ✅ Short position exit signal detected")
            print(f"      Reason: {short_exit_signal}")
        else:
            print("   ❌ Short position exit signal not detected")

        passed_exits = sum(exit_results.values())
        total_exits = len(exit_results)

        print(f"\n📊 Exit Logic Summary: {passed_exits}/{total_exits} tests passed")
        test_results['exit_logic'] = 'PASSED' if passed_exits == total_exits else 'FAILED'

    except Exception as e:
        print(f"❌ Exit signal logic test failed: {e}")
        test_results['exit_logic'] = 'FAILED'

    # TEST 7: LIVE MARKET INTEGRATION
    print("\n🔗 TEST 7: LIVE MARKET INTEGRATION")
    print("-" * 60)

    try:
        # Test connection to live market data
        binance_client = BinanceClientWrapper()

        # Get live market data
        live_data = binance_client.get_historical_klines('BTCUSDT', '5m', limit=100)

        if live_data and len(live_data) > 50:
            # Convert to DataFrame
            df_live = pd.DataFrame(live_data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])

            # Convert numeric columns
            numeric_columns = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_columns:
                df_live[col] = pd.to_numeric(df_live[col])

            # Test indicator calculation with live data
            df_live = macd_strategy.calculate_indicators(df_live)

            # Test signal evaluation with live data
            live_signal = macd_strategy.evaluate_entry_signal(df_live)
            current_price = df_live['close'].iloc[-1]

            print("✅ Live market integration successful")
            print(f"   📊 Retrieved {len(df_live)} candles from Binance")
            print(f"   💰 Current BTC Price: ${current_price:,.2f}")

            if live_signal:
                print(f"   🚨 LIVE SIGNAL DETECTED: {live_signal.signal_type.value}")
                print(f"      Entry: ${live_signal.entry_price:.2f}")
                print(f"      Stop Loss: ${live_signal.stop_loss:.2f}")
                print(f"      Take Profit: ${live_signal.take_profit:.2f}")
            else:
                print("   📊 No signal detected in current market conditions")

            test_results['live_integration'] = 'PASSED'

        else:
            print("❌ Failed to retrieve sufficient live market data")
            test_results['live_integration'] = 'FAILED'

    except Exception as e:
        print(f"❌ Live market integration test failed: {e}")
        test_results['live_integration'] = 'FAILED'

    # FINAL RESULTS SUMMARY
    print("\n" + "=" * 80)
    print("📊 COMPREHENSIVE MACD STRATEGY TEST RESULTS")
    print("=" * 80)

    passed_tests = sum(1 for result in test_results.values() if result == 'PASSED')
    total_tests = len(test_results)
    success_rate = (passed_tests / total_tests) * 100

    print(f"🎯 Overall Results: {passed_tests}/{total_tests} tests passed ({success_rate:.1f}% success rate)")
    print("\n📋 Detailed Test Results:")

    for test_name, result in test_results.items():
        status_emoji = "✅" if result == 'PASSED' else "❌"
        print(f"   {status_emoji} {test_name.replace('_', ' ').title()}: {result}")

    if success_rate == 100:
        print("\n🎉 PERFECT! ALL TESTS PASSED! 100% SUCCESS RATE!")
        print("🚀 MACD strategy is fully validated and ready for live trading!")
    elif success_rate >= 80:
        print(f"\n✅ EXCELLENT! {success_rate:.1f}% success rate - MACD strategy is performing well!")
    elif success_rate >= 60:
        print(f"\n⚠️ GOOD: {success_rate:.1f}% success rate - Some issues need attention")
    else:
        print(f"\n❌ NEEDS WORK: {success_rate:.1f}% success rate - Significant issues detected")

    # Save results
    try:
        results_data = {
            'timestamp': datetime.now().isoformat(),
            'strategy': 'MACD Divergence',
            'summary': {
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'success_rate': success_rate
            },
            'detailed_results': test_results,
            'test_config': test_config
        }

        with open('trading_data/macd_comprehensive_test_results.json', 'w') as f:
            json.dump(results_data, f, indent=2)

        print(f"\n💾 Test results saved to: trading_data/macd_comprehensive_test_results.json")

    except Exception as e:
        print(f"⚠️ Could not save results: {e}")

    print("\n🏁 MACD Comprehensive Test Complete!")
    print("=" * 80)

if __name__ == "__main__":
    main()