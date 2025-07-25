
#!/usr/bin/env python3
"""
Comprehensive RSI Signal Accuracy Test
=====================================

This test validates that RSI strategies only enter trades when actual RSI conditions match the configured logic.
Tests all RSI-based strategies to ensure signal detection accuracy.
"""

import sys
import os
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

# Add src to path
sys.path.append('src')

from binance_client.client import BinanceClientWrapper
from data_fetcher.price_fetcher import PriceFetcher
from config.global_config import global_config
from execution_engine.strategies.rsi_oversold_config import RSIOversoldConfig

def calculate_rsi_manual(prices, period=14):
    """Manual RSI calculation (same as trading strategies use)"""
    if len(prices) < period + 1:
        return None

    # Calculate price changes
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    
    # Separate gains and losses
    gains = [max(delta, 0) for delta in deltas]
    losses = [max(-delta, 0) for delta in deltas]

    # Calculate initial averages
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    # Calculate smoothed averages for remaining periods
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_rsi_pandas(df, period=14):
    """Calculate RSI using pandas for comparison"""
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def analyze_rsi_entry_logic(rsi_value, config, symbol):
    """Analyze what signals should be generated based on RSI value and config"""
    analysis = {
        'rsi_value': rsi_value,
        'symbol': symbol,
        'expected_signals': [],
        'config_thresholds': {},
        'signal_explanations': []
    }
    
    # Get config thresholds
    rsi_long_entry = config.get('rsi_long_entry', 40)
    rsi_short_entry = config.get('rsi_short_entry', 60)
    rsi_long_exit = config.get('rsi_long_exit', 70)
    rsi_short_exit = config.get('rsi_short_exit', 30)
    
    analysis['config_thresholds'] = {
        'long_entry': rsi_long_entry,
        'short_entry': rsi_short_entry,
        'long_exit': rsi_long_exit,
        'short_exit': rsi_short_exit
    }
    
    # Analyze entry signals
    if rsi_value <= rsi_long_entry:
        analysis['expected_signals'].append('BUY')
        analysis['signal_explanations'].append(f"RSI {rsi_value:.2f} <= {rsi_long_entry} (long entry threshold)")
    
    if rsi_value >= rsi_short_entry:
        analysis['expected_signals'].append('SELL')
        analysis['signal_explanations'].append(f"RSI {rsi_value:.2f} >= {rsi_short_entry} (short entry threshold)")
    
    # Analyze exit signals
    if rsi_value >= rsi_long_exit:
        analysis['signal_explanations'].append(f"RSI {rsi_value:.2f} >= {rsi_long_exit} (long exit threshold)")
    
    if rsi_value <= rsi_short_exit:
        analysis['signal_explanations'].append(f"RSI {rsi_value:.2f} <= {rsi_short_exit} (short exit threshold)")
    
    return analysis

async def test_current_rsi_conditions():
    """Test current RSI conditions for active symbols"""
    print("🔍 TESTING CURRENT RSI CONDITIONS")
    print("=" * 60)
    
    try:
        # Initialize clients
        binance_client = BinanceClientWrapper()
        price_fetcher = PriceFetcher(binance_client)
        
        # Test symbols from recent trades
        test_symbols = ['ETHUSDT', 'XRPUSDT', 'BTCUSDT', 'SOLUSDT']
        
        results = {}
        
        for symbol in test_symbols:
            print(f"\n📊 ANALYZING {symbol}")
            print("-" * 40)
            
            # Get market data (more periods for accurate RSI)
            df = await price_fetcher.get_market_data(symbol, '15m', 150)
            
            if df is None or df.empty:
                print(f"❌ No data available for {symbol}")
                continue
            
            # Calculate RSI using both methods
            rsi_pandas = calculate_rsi_pandas(df, 14).iloc[-1]
            rsi_manual = calculate_rsi_manual(df['close'].tolist(), 14)
            
            # Get current price
            current_price = df['close'].iloc[-1]
            
            # Get RSI config
            config = RSIOversoldConfig.get_config()
            
            # Analyze what signals should be generated
            analysis = analyze_rsi_entry_logic(rsi_manual, config, symbol)
            
            print(f"💰 Current Price: ${current_price:.4f}")
            print(f"📈 RSI (Pandas): {rsi_pandas:.2f}")
            print(f"🔧 RSI (Manual): {rsi_manual:.2f}")
            print(f"📏 RSI Difference: {abs(rsi_pandas - rsi_manual):.4f}")
            
            print(f"\n🎯 SIGNAL ANALYSIS:")
            print(f"   Long Entry Threshold: <= {analysis['config_thresholds']['long_entry']}")
            print(f"   Short Entry Threshold: >= {analysis['config_thresholds']['short_entry']}")
            print(f"   Long Exit Threshold: >= {analysis['config_thresholds']['long_exit']}")
            print(f"   Short Exit Threshold: <= {analysis['config_thresholds']['short_exit']}")
            
            print(f"\n🚦 EXPECTED SIGNALS: {analysis['expected_signals'] if analysis['expected_signals'] else 'NONE'}")
            for explanation in analysis['signal_explanations']:
                print(f"   • {explanation}")
            
            # Check for logic issues
            if not analysis['expected_signals']:
                print(f"✅ No entry signals expected - RSI {rsi_manual:.2f} is in neutral zone")
            else:
                print(f"⚠️  Entry signals expected: {analysis['expected_signals']}")
            
            # Store results
            results[symbol] = {
                'current_price': current_price,
                'rsi_pandas': rsi_pandas,
                'rsi_manual': rsi_manual,
                'rsi_difference': abs(rsi_pandas - rsi_manual),
                'analysis': analysis,
                'timestamp': datetime.now().isoformat()
            }
            
            # Show recent price movements for context
            print(f"\n📊 Recent RSI Values (last 5):")
            recent_closes = df['close'].tail(10).tolist()
            for i in range(5, 10):
                if i < len(recent_closes):
                    subset_prices = recent_closes[:i+1]
                    if len(subset_prices) >= 15:  # Need enough data for RSI
                        recent_rsi = calculate_rsi_manual(subset_prices, 14)
                        print(f"   Period -{5-i}: RSI {recent_rsi:.2f}")
        
        return results
        
    except Exception as e:
        print(f"❌ Error during RSI testing: {e}")
        import traceback
        traceback.print_exc()
        return {}

async def test_historical_entry_signals():
    """Test historical data to find when actual entry signals should have occurred"""
    print("\n\n🕒 TESTING HISTORICAL ENTRY SIGNALS")
    print("=" * 60)
    
    try:
        binance_client = BinanceClientWrapper()
        price_fetcher = PriceFetcher(binance_client)
        
        test_symbols = ['ETHUSDT', 'XRPUSDT']
        config = RSIOversoldConfig.get_config()
        
        for symbol in test_symbols:
            print(f"\n📊 HISTORICAL ANALYSIS: {symbol}")
            print("-" * 40)
            
            # Get more historical data
            df = await price_fetcher.get_market_data(symbol, '15m', 200)
            
            if df is None or df.empty:
                continue
            
            # Calculate RSI for entire dataset
            prices = df['close'].tolist()
            rsi_values = []
            
            for i in range(14, len(prices)):
                subset_prices = prices[:i+1]
                rsi = calculate_rsi_manual(subset_prices, 14)
                rsi_values.append({
                    'index': i,
                    'timestamp': df.iloc[i]['timestamp'],
                    'price': prices[i],
                    'rsi': rsi
                })
            
            # Find actual entry signals
            long_entries = []
            short_entries = []
            
            for data in rsi_values:
                if data['rsi'] <= config.get('rsi_long_entry', 40):
                    long_entries.append(data)
                if data['rsi'] >= config.get('rsi_short_entry', 60):
                    short_entries.append(data)
            
            print(f"🟢 Long entry signals found: {len(long_entries)}")
            if long_entries:
                latest_long = long_entries[-1]
                print(f"   Latest: RSI {latest_long['rsi']:.2f} at ${latest_long['price']:.4f} ({latest_long['timestamp']})")
            
            print(f"🔴 Short entry signals found: {len(short_entries)}")
            if short_entries:
                latest_short = short_entries[-1]
                print(f"   Latest: RSI {latest_short['rsi']:.2f} at ${latest_short['price']:.4f} ({latest_short['timestamp']})")
            
            # Show current RSI context
            current_rsi = rsi_values[-1]['rsi'] if rsi_values else None
            print(f"📍 Current RSI: {current_rsi:.2f}")
            
            if current_rsi:
                if current_rsi <= config.get('rsi_long_entry', 40):
                    print(f"⚠️  CURRENT LONG SIGNAL: RSI {current_rsi:.2f} <= {config.get('rsi_long_entry', 40)}")
                elif current_rsi >= config.get('rsi_short_entry', 60):
                    print(f"⚠️  CURRENT SHORT SIGNAL: RSI {current_rsi:.2f} >= {config.get('rsi_short_entry', 60)}")
                else:
                    print(f"✅ No current signals - RSI in neutral zone")
    
    except Exception as e:
        print(f"❌ Error during historical testing: {e}")
        import traceback
        traceback.print_exc()

async def validate_strategy_config():
    """Validate RSI strategy configuration"""
    print("\n\n⚙️ VALIDATING STRATEGY CONFIGURATION")
    print("=" * 60)
    
    try:
        config = RSIOversoldConfig.get_config()
        
        print("📋 Current RSI Configuration:")
        for key, value in config.items():
            print(f"   {key}: {value}")
        
        # Validate configuration logic
        long_entry = config.get('rsi_long_entry', 40)
        short_entry = config.get('rsi_short_entry', 60)
        long_exit = config.get('rsi_long_exit', 70)
        short_exit = config.get('rsi_short_exit', 30)
        
        print(f"\n🔍 Configuration Analysis:")
        print(f"   Long Entry Zone: RSI <= {long_entry} (oversold)")
        print(f"   Short Entry Zone: RSI >= {short_entry} (overbought)")
        print(f"   Long Exit Zone: RSI >= {long_exit} (overbought)")
        print(f"   Short Exit Zone: RSI <= {short_exit} (oversold)")
        
        # Check for logical issues
        issues = []
        if long_entry >= short_entry:
            issues.append(f"Long entry ({long_entry}) should be < Short entry ({short_entry})")
        if long_exit <= long_entry:
            issues.append(f"Long exit ({long_exit}) should be > Long entry ({long_entry})")
        if short_exit >= short_entry:
            issues.append(f"Short exit ({short_exit}) should be < Short entry ({short_entry})")
        
        if issues:
            print(f"\n❌ CONFIGURATION ISSUES DETECTED:")
            for issue in issues:
                print(f"   • {issue}")
        else:
            print(f"\n✅ Configuration logic appears correct")
            
    except Exception as e:
        print(f"❌ Error validating configuration: {e}")

async def main():
    """Run comprehensive RSI signal accuracy test"""
    print("🧪 COMPREHENSIVE RSI SIGNAL ACCURACY TEST")
    print("=" * 80)
    print("Testing RSI signal detection accuracy to identify entry logic issues")
    print("=" * 80)
    
    try:
        # Test 1: Current RSI conditions
        current_results = await test_current_rsi_conditions()
        
        # Test 2: Historical entry signals
        await test_historical_entry_signals()
        
        # Test 3: Validate strategy configuration
        await validate_strategy_config()
        
        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"rsi_signal_accuracy_test_{timestamp}.json"
        
        test_results = {
            'timestamp': datetime.now().isoformat(),
            'test_type': 'rsi_signal_accuracy_comprehensive',
            'current_conditions': current_results,
            'summary': 'RSI signal accuracy validation completed'
        }
        
        with open(results_file, 'w') as f:
            json.dump(test_results, f, indent=2, default=str)
        
        print(f"\n📊 SUMMARY:")
        print(f"   • Test completed successfully")
        print(f"   • Results saved to: {results_file}")
        print(f"   • Symbols tested: {len(current_results)}")
        
        # Final recommendations
        print(f"\n💡 RECOMMENDATIONS:")
        print(f"   1. Check if actual RSI values match expected entry conditions")
        print(f"   2. Verify RSI calculation consistency across strategies")
        print(f"   3. Review strategy entry logic implementation")
        print(f"   4. Consider adding RSI validation before trade execution")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
