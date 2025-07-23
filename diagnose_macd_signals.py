
#!/usr/bin/env python3
"""
Comprehensive MACD Signal Diagnosis
Identifies exact issues preventing MACD strategy from detecting signals
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

# Correct imports based on the actual codebase structure
from src.config.trading_config import trading_config_manager
from src.binance_client.client import BinanceClientWrapper
from src.execution_engine.strategies.macd_divergence_strategy import MACDDivergenceStrategy

def calculate_macd_manually(prices, fast=12, slow=26, signal=9):
    """Manual MACD calculation for verification"""
    try:
        df = pd.DataFrame({'close': prices})
        
        # Calculate EMAs
        ema_fast = df['close'].ewm(span=fast).mean()
        ema_slow = df['close'].ewm(span=slow).mean()
        
        # MACD Line
        macd_line = ema_fast - ema_slow
        
        # Signal Line
        signal_line = macd_line.ewm(span=signal).mean()
        
        # Histogram
        histogram = macd_line - signal_line
        
        return macd_line.values, signal_line.values, histogram.values
        
    except Exception as e:
        print(f"❌ Error in manual MACD calculation: {e}")
        return None, None, None

def diagnose_macd_strategy():
    """Comprehensive MACD strategy diagnosis"""
    print("\n🔍 COMPREHENSIVE MACD SIGNAL DIAGNOSIS")
    print("=" * 60)
    
    try:
        # 1. GET MACD STRATEGY CONFIG
        print("\n📋 STEP 1: LOADING MACD STRATEGY CONFIG")
        macd_config = trading_config_manager.get_strategy_config('macd_divergence', {})
        
        print(f"✅ Config loaded successfully:")
        print(f"   Symbol: {macd_config.get('symbol', 'N/A')}")
        print(f"   Timeframe: {macd_config.get('timeframe', 'N/A')}")
        print(f"   MACD Fast: {macd_config.get('macd_fast', 'N/A')}")
        print(f"   MACD Slow: {macd_config.get('macd_slow', 'N/A')}")
        print(f"   MACD Signal: {macd_config.get('macd_signal', 'N/A')}")
        print(f"   Min Histogram Threshold: {macd_config.get('min_histogram_threshold', 'N/A')}")
        print(f"   Min Distance Threshold: {macd_config.get('min_distance_threshold', 'N/A')}")
        print(f"   Confirmation Candles: {macd_config.get('confirmation_candles', 'N/A')}")
        
    except Exception as e:
        print(f"❌ Error loading MACD config: {e}")
        return False
    
    try:
        # 2. INITIALIZE BINANCE CLIENT
        print("\n📊 STEP 2: INITIALIZING BINANCE CLIENT")
        binance_client = BinanceClientWrapper()
        
        symbol = macd_config.get('symbol', 'BTCUSDT')
        timeframe = macd_config.get('timeframe', '15m')
        
        print(f"✅ Binance client initialized")
        print(f"   Target Symbol: {symbol}")
        print(f"   Target Timeframe: {timeframe}")
        
    except Exception as e:
        print(f"❌ Error initializing Binance client: {e}")
        return False
    
    try:
        # 3. FETCH MARKET DATA
        print(f"\n💹 STEP 3: FETCHING MARKET DATA")
        
        # Get sufficient data for MACD calculation (need at least slow period + signal period)
        required_candles = max(macd_config.get('macd_slow', 26), 26) + max(macd_config.get('macd_signal', 9), 9) + 50
        
        print(f"   Fetching {required_candles} candles for {symbol} {timeframe}")
        
        klines = binance_client.get_klines(symbol=symbol, interval=timeframe, limit=required_candles)
        
        if not klines or len(klines) < 50:
            print(f"❌ Insufficient data: {len(klines) if klines else 0} candles")
            return False
            
        print(f"✅ Fetched {len(klines)} candles")
        
        # Convert to DataFrame
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])
        
        # Convert to proper data types
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        print(f"   Data range: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")
        print(f"   Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")
        print(f"   Latest close: ${df['close'].iloc[-1]:.2f}")
        
    except Exception as e:
        print(f"❌ Error fetching market data: {e}")
        return False
    
    try:
        # 4. MANUAL MACD CALCULATION
        print(f"\n🧮 STEP 4: MANUAL MACD CALCULATION")
        
        fast_period = macd_config.get('macd_fast', 12)
        slow_period = macd_config.get('macd_slow', 26)
        signal_period = macd_config.get('macd_signal', 9)
        
        macd_line, signal_line, histogram = calculate_macd_manually(
            df['close'].values, fast_period, slow_period, signal_period
        )
        
        if macd_line is None:
            print(f"❌ Manual MACD calculation failed")
            return False
            
        # Get recent values (last 10 candles)
        recent_data = []
        for i in range(-10, 0):
            if i >= -len(macd_line):
                recent_data.append({
                    'time': df['timestamp'].iloc[i].strftime('%Y-%m-%d %H:%M'),
                    'close': df['close'].iloc[i],
                    'macd': macd_line[i],
                    'signal': signal_line[i],
                    'histogram': histogram[i],
                    'macd_cross': 'BULLISH' if macd_line[i] > signal_line[i] and macd_line[i-1] <= signal_line[i-1] else 'BEARISH' if macd_line[i] < signal_line[i] and macd_line[i-1] >= signal_line[i-1] else 'NONE'
                })
        
        print(f"✅ MACD calculated successfully")
        print(f"   Fast EMA: {fast_period}, Slow EMA: {slow_period}, Signal: {signal_period}")
        print(f"   Current MACD: {macd_line[-1]:.6f}")
        print(f"   Current Signal: {signal_line[-1]:.6f}")
        print(f"   Current Histogram: {histogram[-1]:.6f}")
        
        print(f"\n📈 RECENT MACD DATA:")
        print(f"{'Time':<17} {'Close':<10} {'MACD':<12} {'Signal':<12} {'Histogram':<12} {'Cross'}")
        print("-" * 80)
        for data in recent_data[-5:]:  # Show last 5 candles
            print(f"{data['time']:<17} ${data['close']:<9.2f} {data['macd']:<12.6f} {data['signal']:<12.6f} {data['histogram']:<12.6f} {data['macd_cross']}")
        
    except Exception as e:
        print(f"❌ Error in manual MACD calculation: {e}")
        return False
    
    try:
        # 5. STRATEGY SIGNAL DETECTION ANALYSIS
        print(f"\n🎯 STEP 5: STRATEGY SIGNAL DETECTION ANALYSIS")
        
        min_histogram_threshold = macd_config.get('min_histogram_threshold', 0.0001)
        min_distance_threshold = macd_config.get('min_distance_threshold', 0.005)
        confirmation_candles = macd_config.get('confirmation_candles', 2)
        
        print(f"   Thresholds:")
        print(f"   - Min Histogram Threshold: {min_histogram_threshold}")
        print(f"   - Min Distance Threshold: {min_distance_threshold}")
        print(f"   - Confirmation Candles: {confirmation_candles}")
        
        # Analyze recent signals
        signals_detected = []
        
        for i in range(len(macd_line) - confirmation_candles, len(macd_line)):
            if i <= confirmation_candles:
                continue
                
            current_macd = macd_line[i]
            current_signal = signal_line[i]
            current_histogram = histogram[i]
            
            prev_macd = macd_line[i-1]
            prev_signal = signal_line[i-1]
            prev_histogram = histogram[i-1]
            
            # Check for bullish crossover
            if (current_macd > current_signal and prev_macd <= prev_signal and 
                abs(current_histogram) > min_histogram_threshold and
                abs(current_macd - current_signal) > min_distance_threshold):
                
                signals_detected.append({
                    'time': df['timestamp'].iloc[i].strftime('%Y-%m-%d %H:%M'),
                    'type': 'BULLISH_CROSS',
                    'macd': current_macd,
                    'signal': current_signal,
                    'histogram': current_histogram,
                    'distance': abs(current_macd - current_signal),
                    'meets_histogram_threshold': abs(current_histogram) > min_histogram_threshold,
                    'meets_distance_threshold': abs(current_macd - current_signal) > min_distance_threshold
                })
            
            # Check for bearish crossover
            elif (current_macd < current_signal and prev_macd >= prev_signal and 
                  abs(current_histogram) > min_histogram_threshold and
                  abs(current_macd - current_signal) > min_distance_threshold):
                
                signals_detected.append({
                    'time': df['timestamp'].iloc[i].strftime('%Y-%m-%d %H:%M'),
                    'type': 'BEARISH_CROSS',
                    'macd': current_macd,
                    'signal': current_signal,
                    'histogram': current_histogram,
                    'distance': abs(current_macd - current_signal),
                    'meets_histogram_threshold': abs(current_histogram) > min_histogram_threshold,
                    'meets_distance_threshold': abs(current_macd - current_signal) > min_distance_threshold
                })
        
        print(f"\n🔍 SIGNAL DETECTION RESULTS:")
        if signals_detected:
            print(f"✅ Found {len(signals_detected)} signals in recent data:")
            for signal in signals_detected:
                print(f"   {signal['time']} - {signal['type']}")
                print(f"      MACD: {signal['macd']:.6f}, Signal: {signal['signal']:.6f}")
                print(f"      Histogram: {signal['histogram']:.6f} (Threshold: {abs(signal['histogram']) > min_histogram_threshold})")
                print(f"      Distance: {signal['distance']:.6f} (Threshold: {signal['meets_distance_threshold']})")
        else:
            print(f"❌ NO SIGNALS DETECTED in recent data")
            print(f"   This indicates the issue is in the signal detection logic")
        
    except Exception as e:
        print(f"❌ Error in signal detection analysis: {e}")
        return False
    
    try:
        # 6. THRESHOLD ANALYSIS
        print(f"\n🔬 STEP 6: THRESHOLD SENSITIVITY ANALYSIS")
        
        print(f"   Analyzing if thresholds are too restrictive...")
        
        # Count how many recent crossovers fail each threshold
        threshold_failures = {
            'histogram_too_small': 0,
            'distance_too_small': 0,
            'both_too_small': 0,
            'total_crossovers': 0
        }
        
        for i in range(len(macd_line) - 20, len(macd_line)):
            if i <= 1:
                continue
                
            current_macd = macd_line[i]
            current_signal = signal_line[i]
            current_histogram = histogram[i]
            
            prev_macd = macd_line[i-1]
            prev_signal = signal_line[i-1]
            
            # Check for any crossover
            if ((current_macd > current_signal and prev_macd <= prev_signal) or
                (current_macd < current_signal and prev_macd >= prev_signal)):
                
                threshold_failures['total_crossovers'] += 1
                
                histogram_meets = abs(current_histogram) > min_histogram_threshold
                distance_meets = abs(current_macd - current_signal) > min_distance_threshold
                
                if not histogram_meets and not distance_meets:
                    threshold_failures['both_too_small'] += 1
                elif not histogram_meets:
                    threshold_failures['histogram_too_small'] += 1
                elif not distance_meets:
                    threshold_failures['distance_too_small'] += 1
        
        print(f"   Total crossovers found: {threshold_failures['total_crossovers']}")
        print(f"   Failed histogram threshold: {threshold_failures['histogram_too_small']}")
        print(f"   Failed distance threshold: {threshold_failures['distance_too_small']}")
        print(f"   Failed both thresholds: {threshold_failures['both_too_small']}")
        
        if threshold_failures['total_crossovers'] == 0:
            print(f"   ⚠️ NO CROSSOVERS DETECTED - Market may be trending strongly")
        elif (threshold_failures['histogram_too_small'] + threshold_failures['distance_too_small'] + 
              threshold_failures['both_too_small']) > 0:
            print(f"   ⚠️ THRESHOLDS ARE TOO RESTRICTIVE - Blocking valid signals")
            
    except Exception as e:
        print(f"❌ Error in threshold analysis: {e}")
        return False
    
    try:
        # 7. STRATEGY CLASS TESTING
        print(f"\n🧪 STEP 7: TESTING ACTUAL STRATEGY CLASS")
        
        print(f"   Initializing MACDDivergenceStrategy...")
        strategy = MACDDivergenceStrategy(macd_config)
        
        # Test with current market data
        test_data = {
            'open': df['open'].iloc[-1],
            'high': df['high'].iloc[-1],
            'low': df['low'].iloc[-1],
            'close': df['close'].iloc[-1],
            'volume': df['volume'].iloc[-1]
        }
        
        print(f"   Testing with latest candle data:")
        print(f"   Close: ${test_data['close']:.2f}")
        print(f"   Volume: {test_data['volume']:,.0f}")
        
        # Test signal detection
        result = strategy.should_enter_trade(test_data, df.to_dict('records'))
        
        print(f"\n   Strategy Result:")
        print(f"   Should Enter Trade: {result}")
        
        if not result:
            print(f"   ❌ Strategy is not generating entry signals")
            print(f"   This confirms there's an issue in the strategy logic")
        else:
            print(f"   ✅ Strategy would generate an entry signal")
            
    except Exception as e:
        print(f"❌ Error testing strategy class: {e}")
        print(f"   This indicates an issue with the strategy implementation")
        return False
    
    # 8. SUMMARY AND RECOMMENDATIONS
        print(f"\n📋 STEP 8: DIAGNOSIS SUMMARY AND RECOMMENDATIONS")
        print("=" * 60)
        
        print(f"\n🎯 FINDINGS:")
        if signals_detected:
            print(f"✅ MACD calculation is working correctly")
            print(f"✅ Signal detection logic can find crossovers")
            print(f"❓ Issue may be in strategy implementation or configuration")
        else:
            print(f"❌ No MACD signals detected in recent data")
            print(f"❓ Could be due to:")
            print(f"   - Thresholds too restrictive")
            print(f"   - Market conditions not suitable for MACD")
            print(f"   - Strategy implementation issues")
        
        print(f"\n💡 RECOMMENDATIONS:")
        
        if threshold_failures.get('total_crossovers', 0) > 0:
            if (threshold_failures.get('histogram_too_small', 0) + 
                threshold_failures.get('distance_too_small', 0) + 
                threshold_failures.get('both_too_small', 0)) > threshold_failures.get('total_crossovers', 1) * 0.5:
                print(f"1. 🔧 REDUCE THRESHOLDS - Current settings are too restrictive")
                print(f"   - Try min_histogram_threshold: 0.00005 (current: {min_histogram_threshold})")
                print(f"   - Try min_distance_threshold: 0.001 (current: {min_distance_threshold})")
        
        if not signals_detected:
            print(f"2. 📊 CHANGE TIMEFRAME - Try a different timeframe for more crossovers")
            print(f"   - Current: {timeframe}, Try: 5m or 1h")
        
        print(f"3. 🎛️ ADJUST MACD PARAMETERS - Try more sensitive settings")
        print(f"   - Current: Fast={fast_period}, Slow={slow_period}, Signal={signal_period}")
        print(f"   - Try: Fast=8, Slow=21, Signal=5 (more sensitive)")
        
        print(f"4. ⏰ CHECK DIFFERENT TIME PERIODS - Current market may not be suitable")
        
        print(f"\n✅ DIAGNOSIS COMPLETE")
        return True
        
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR IN DIAGNOSIS: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = diagnose_macd_strategy()
    if success:
        print(f"\n🎉 Diagnosis completed successfully!")
    else:
        print(f"\n💥 Diagnosis failed - Check the errors above")
