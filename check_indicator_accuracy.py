
#!/usr/bin/env python3
"""
Comprehensive Indicator Accuracy Checker
Compare our calculations with multiple methods and provide accuracy diagnostics
"""

import sys
import os
sys.path.append('src')

from binance_client.client import BinanceClientWrapper
from config.global_config import global_config
from data_fetcher.price_fetcher import PriceFetcher
import asyncio
import pandas as pd
import ta
import numpy as np
from datetime import datetime, timedelta

def calculate_rsi_binance_method(prices, period=14):
    """RSI calculation using Binance's exact methodology"""
    if len(prices) < period + 1:
        return None

    # Convert to pandas series for easier calculation
    price_series = pd.Series(prices)
    deltas = price_series.diff()

    # Separate gains and losses
    gains = deltas.where(deltas > 0, 0)
    losses = -deltas.where(deltas < 0, 0)

    # Use Wilder's smoothing (what Binance uses)
    # First average is simple moving average
    avg_gain = gains.rolling(window=period, min_periods=period).mean()
    avg_loss = losses.rolling(window=period, min_periods=period).mean()

    # Apply Wilder's smoothing for subsequent periods
    for i in range(period, len(gains)):
        avg_gain.iloc[i] = (avg_gain.iloc[i-1] * (period - 1) + gains.iloc[i]) / period
        avg_loss.iloc[i] = (avg_loss.iloc[i-1] * (period - 1) + losses.iloc[i]) / period

    # Calculate RSI
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else None

def calculate_macd_binance_method(prices, fast=12, slow=26, signal=9):
    """MACD calculation using Binance's exact methodology"""
    price_series = pd.Series(prices)
    
    # Calculate EMAs using pandas (more accurate)
    ema_fast = price_series.ewm(span=fast, min_periods=fast).mean()
    ema_slow = price_series.ewm(span=slow, min_periods=slow).mean()
    
    # MACD line
    macd_line = ema_fast - ema_slow
    
    # Signal line
    signal_line = macd_line.ewm(span=signal, min_periods=signal).mean()
    
    # Histogram
    histogram = macd_line - signal_line
    
    return {
        'macd': macd_line.iloc[-1] if not pd.isna(macd_line.iloc[-1]) else None,
        'signal': signal_line.iloc[-1] if not pd.isna(signal_line.iloc[-1]) else None,
        'histogram': histogram.iloc[-1] if not pd.isna(histogram.iloc[-1]) else None
    }

async def comprehensive_accuracy_check():
    """Comprehensive accuracy check for all indicators"""
    try:
        print("🔍 COMPREHENSIVE INDICATOR ACCURACY CHECK")
        print("=" * 60)
        
        # Initialize clients
        binance_client = BinanceClientWrapper()
        price_fetcher = PriceFetcher(binance_client)
        
        # Test symbols from active strategies
        test_symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
        intervals = ['15m', '1h', '4h']
        
        for symbol in test_symbols:
            print(f"\n📊 TESTING ACCURACY FOR {symbol}")
            print("=" * 40)
            
            for interval in intervals:
                print(f"\n⏰ Timeframe: {interval}")
                print("-" * 25)
                
                # Get market data using enhanced method
                df = await price_fetcher.get_market_data(symbol, interval, 200)
                
                if df is None or df.empty or len(df) < 50:
                    print(f"❌ Insufficient data for {symbol} {interval}")
                    continue
                
                # Current price for context
                current_price = df['close'].iloc[-1]
                prev_price = df['close'].iloc[-2]
                price_change = ((current_price - prev_price) / prev_price) * 100
                
                print(f"💰 Current Price: ${current_price:.4f} ({price_change:+.2f}%)")
                
                # RSI Comparisons
                print(f"\n📈 RSI (14) COMPARISON:")
                
                # Method 1: Our manual calculation
                rsi_manual = calculate_rsi_binance_method(df['close'].values, 14)
                
                # Method 2: TA library
                rsi_ta = ta.momentum.RSIIndicator(df['close'], window=14).rsi().iloc[-1]
                
                # Method 3: Our enhanced method
                rsi_enhanced = df['rsi'].iloc[-1] if 'rsi' in df.columns else None
                
                print(f"   📊 Binance Method: {rsi_manual:.2f}" if rsi_manual else "   📊 Binance Method: N/A")
                print(f"   🔧 TA Library:     {rsi_ta:.2f}" if not pd.isna(rsi_ta) else "   🔧 TA Library:     N/A")
                print(f"   ⚡ Enhanced:       {rsi_enhanced:.2f}" if rsi_enhanced else "   ⚡ Enhanced:       N/A")
                
                # Calculate differences
                if rsi_manual and not pd.isna(rsi_ta):
                    diff_ta = abs(rsi_manual - rsi_ta)
                    print(f"   📏 Difference (Manual vs TA): {diff_ta:.4f}")
                    
                    if diff_ta > 1.0:
                        print(f"   ⚠️  SIGNIFICANT RSI DIFFERENCE DETECTED!")
                    else:
                        print(f"   ✅ RSI calculations match closely")
                
                # MACD Comparisons
                print(f"\n📈 MACD COMPARISON:")
                
                # Method 1: Our manual calculation
                macd_manual = calculate_macd_binance_method(df['close'].values)
                
                # Method 2: TA library
                macd_indicator = ta.trend.MACD(df['close'])
                macd_ta = {
                    'macd': macd_indicator.macd().iloc[-1],
                    'signal': macd_indicator.macd_signal().iloc[-1],
                    'histogram': macd_indicator.macd_diff().iloc[-1]
                }
                
                # Method 3: Our enhanced method
                macd_enhanced = {
                    'macd': df['macd'].iloc[-1] if 'macd' in df.columns else None,
                    'signal': df['macd_signal'].iloc[-1] if 'macd_signal' in df.columns else None,
                    'histogram': df['macd_histogram'].iloc[-1] if 'macd_histogram' in df.columns else None
                }
                
                print(f"   📊 MACD Line:")
                print(f"      Binance Method: {macd_manual['macd']:.6f}" if macd_manual['macd'] else "      Binance Method: N/A")
                print(f"      TA Library:     {macd_ta['macd']:.6f}" if not pd.isna(macd_ta['macd']) else "      TA Library:     N/A")
                print(f"      Enhanced:       {macd_enhanced['macd']:.6f}" if macd_enhanced['macd'] else "      Enhanced:       N/A")
                
                print(f"   📊 Signal Line:")
                print(f"      Binance Method: {macd_manual['signal']:.6f}" if macd_manual['signal'] else "      Binance Method: N/A")
                print(f"      TA Library:     {macd_ta['signal']:.6f}" if not pd.isna(macd_ta['signal']) else "      TA Library:     N/A")
                print(f"      Enhanced:       {macd_enhanced['signal']:.6f}" if macd_enhanced['signal'] else "      Enhanced:       N/A")
                
                print(f"   📊 Histogram:")
                print(f"      Binance Method: {macd_manual['histogram']:.6f}" if macd_manual['histogram'] else "      Binance Method: N/A")
                print(f"      TA Library:     {macd_ta['histogram']:.6f}" if not pd.isna(macd_ta['histogram']) else "      TA Library:     N/A")
                print(f"      Enhanced:       {macd_enhanced['histogram']:.6f}" if macd_enhanced['histogram'] else "      Enhanced:       N/A")
                
                # Data Quality Check
                print(f"\n📊 DATA QUALITY:")
                print(f"   📅 Latest Timestamp: {df.index[-1]}")
                print(f"   🔢 Data Points: {len(df)}")
                print(f"   ⏱️  Time Since Last: {datetime.now() - df.index[-1].to_pydatetime()}")
                
                # Check for gaps in data
                time_diffs = df.index.to_series().diff().dt.total_seconds()
                expected_interval = {'15m': 900, '1h': 3600, '4h': 14400}[interval]
                unusual_gaps = time_diffs[time_diffs > expected_interval * 1.5]
                
                if len(unusual_gaps) > 0:
                    print(f"   ⚠️  Found {len(unusual_gaps)} unusual time gaps in data")
                else:
                    print(f"   ✅ No unusual time gaps detected")
                
                print("-" * 25)
        
        print(f"\n🎯 RECOMMENDATIONS:")
        print("-" * 30)
        print("1. ✅ Use Binance methodology for RSI (Wilder's smoothing)")
        print("2. ✅ Use pandas ewm() for MACD EMAs (more precise)")
        print("3. ✅ Include real-time price updates for current candle")
        print("4. ✅ Use extended data buffer for accurate calculations")
        print("5. ✅ Monitor data quality and time gaps")
        
    except Exception as e:
        print(f"❌ Error during comprehensive accuracy check: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(comprehensive_accuracy_check())
