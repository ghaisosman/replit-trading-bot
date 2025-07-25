
#!/usr/bin/env python3
"""
Strategy Entry Logic Validation Test - Offline Version
=====================================================

Tests RSI strategy logic using synthetic market data to work around
geographic restrictions that block WebSocket connections.
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

# Add src to path
sys.path.append('src')

from execution_engine.strategies.rsi_oversold_config import RSIOversoldConfig
from strategy_processor.signal_processor import SignalProcessor

def create_synthetic_market_data(base_price=50000, periods=100, scenario='neutral'):
    """Create synthetic market data with specific RSI scenarios"""
    dates = pd.date_range(start=datetime.now() - timedelta(hours=periods), periods=periods, freq='15T')
    
    if scenario == 'oversold':
        # Create declining price trend to generate low RSI
        trend = np.linspace(0, -0.15, periods)  # 15% decline
        noise = np.random.normal(0, 0.02, periods)  # 2% random noise
        price_changes = trend + noise
    elif scenario == 'overbought':
        # Create rising price trend to generate high RSI
        trend = np.linspace(0, 0.15, periods)  # 15% rise
        noise = np.random.normal(0, 0.02, periods)
        price_changes = trend + noise
    else:  # neutral
        # Create sideways movement
        price_changes = np.random.normal(0, 0.01, periods)  # 1% random walk
    
    # Generate OHLCV data
    prices = []
    current_price = base_price
    
    for change in price_changes:
        open_price = current_price
        # Create realistic OHLC based on the change
        if change > 0:  # Bullish candle
            close_price = open_price * (1 + abs(change))
            high_price = close_price * (1 + np.random.uniform(0, 0.005))  # Up to 0.5% wick
            low_price = open_price * (1 - np.random.uniform(0, 0.002))   # Small lower wick
        else:  # Bearish candle
            close_price = open_price * (1 + change)  # change is negative
            high_price = open_price * (1 + np.random.uniform(0, 0.002))  # Small upper wick
            low_price = close_price * (1 - np.random.uniform(0, 0.005))  # Up to 0.5% wick
        
        volume = np.random.uniform(100, 1000)
        
        prices.append({
            'timestamp': dates[len(prices)],
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'volume': volume
        })
        
        current_price = close_price
    
    df = pd.DataFrame(prices)
    df.set_index('timestamp', inplace=True)
    
    # Calculate RSI
    df = calculate_rsi(df)
    
    return df

def calculate_rsi(df, period=14):
    """Calculate RSI indicator"""
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    df['rsi'] = rsi
    return df

def test_rsi_strategy_logic():
    """Test RSI strategy with controlled scenarios"""
    print("🧪 TESTING RSI STRATEGY LOGIC WITH SYNTHETIC DATA")
    print("=" * 60)
    
    signal_processor = SignalProcessor()
    config = RSIOversoldConfig.get_config()
    
    # Test scenarios
    scenarios = [
        {
            'name': 'OVERSOLD_SCENARIO',
            'type': 'oversold',
            'expected_signal': 'BUY',
            'base_price': 50000
        },
        {
            'name': 'OVERBOUGHT_SCENARIO', 
            'type': 'overbought',
            'expected_signal': 'SELL',
            'base_price': 50000
        },
        {
            'name': 'NEUTRAL_SCENARIO',
            'type': 'neutral', 
            'expected_signal': 'NONE',
            'base_price': 50000
        }
    ]
    
    results = {}
    
    for scenario in scenarios:
        print(f"\n📊 TESTING {scenario['name']}")
        print("-" * 40)
        
        # Generate synthetic data
        df = create_synthetic_market_data(
            base_price=scenario['base_price'],
            periods=100,
            scenario=scenario['type']
        )
        
        # Get final RSI value
        final_rsi = df['rsi'].iloc[-1]
        current_price = df['close'].iloc[-1]
        
        print(f"💰 Final Price: ${current_price:.2f}")
        print(f"📊 Final RSI: {final_rsi:.2f}")
        
        # Test strategy signal generation
        try:
            signal = signal_processor._evaluate_rsi_oversold(df, current_price, config)
            
            # Get thresholds from config
            long_entry = config.get('rsi_long_entry', 40)
            short_entry = config.get('rsi_short_entry', 60)
            
            print(f"⚙️  Long Entry Threshold: <= {long_entry}")
            print(f"⚙️  Short Entry Threshold: >= {short_entry}")
            
            # Analyze results
            if signal:
                signal_type = signal.signal_type.name
                print(f"🚦 STRATEGY SIGNAL: {signal_type}")
                print(f"📝 Signal Reason: {signal.reason}")
                
                # Validate signal correctness
                if scenario['expected_signal'] == 'BUY':
                    if signal_type == 'BUY' and final_rsi <= long_entry:
                        print(f"✅ CORRECT: BUY signal when RSI {final_rsi:.2f} <= {long_entry}")
                        validation_result = "CORRECT"
                    else:
                        print(f"❌ ERROR: Expected BUY signal, got {signal_type}")
                        validation_result = "ERROR"
                        
                elif scenario['expected_signal'] == 'SELL':
                    if signal_type == 'SELL' and final_rsi >= short_entry:
                        print(f"✅ CORRECT: SELL signal when RSI {final_rsi:.2f} >= {short_entry}")
                        validation_result = "CORRECT"
                    else:
                        print(f"❌ ERROR: Expected SELL signal, got {signal_type}")
                        validation_result = "ERROR"
                else:
                    print(f"❌ UNEXPECTED: Got {signal_type} signal when expecting none")
                    validation_result = "UNEXPECTED_SIGNAL"
                    
            else:
                print(f"🚦 STRATEGY SIGNAL: None")
                
                if scenario['expected_signal'] == 'NONE':
                    if long_entry < final_rsi < short_entry:
                        print(f"✅ CORRECT: No signal in neutral zone ({long_entry} < RSI {final_rsi:.2f} < {short_entry})")
                        validation_result = "CORRECT"
                    else:
                        print(f"❌ MISSED: Should have generated signal at RSI {final_rsi:.2f}")
                        validation_result = "MISSED_SIGNAL"
                else:
                    print(f"❌ MISSED: Expected {scenario['expected_signal']} signal but got none")
                    validation_result = "MISSED_SIGNAL"
            
            results[scenario['name']] = {
                'final_rsi': final_rsi,
                'final_price': current_price,
                'expected_signal': scenario['expected_signal'],
                'actual_signal': signal_type if signal else None,
                'validation_result': validation_result,
                'config_used': {
                    'long_entry': long_entry,
                    'short_entry': short_entry
                }
            }
            
        except Exception as e:
            print(f"❌ ERROR: {e}")
            results[scenario['name']] = {
                'error': str(e),
                'validation_result': "ERROR"
            }
    
    return results

def main():
    """Run offline strategy validation test"""
    print("🧪 RSI STRATEGY LOGIC VALIDATION - OFFLINE MODE")
    print("=" * 80)
    print("Using synthetic market data to test strategy logic")
    print("(Bypasses WebSocket connectivity issues)")
    print("=" * 80)
    
    # Run the test
    results = test_rsi_strategy_logic()
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"rsi_strategy_validation_offline_{timestamp}.json"
    
    test_summary = {
        'timestamp': datetime.now().isoformat(),
        'test_type': 'rsi_strategy_validation_offline',
        'results': results,
        'summary': 'RSI strategy logic validation completed using synthetic data'
    }
    
    with open(results_file, 'w') as f:
        json.dump(test_summary, f, indent=2, default=str)
    
    print(f"\n📊 TEST SUMMARY:")
    print(f"   • Results saved to: {results_file}")
    print(f"   • Scenarios tested: {len(results)}")
    
    # Check for issues
    correct_count = sum(1 for r in results.values() if r.get('validation_result') == 'CORRECT')
    error_count = sum(1 for r in results.values() if r.get('validation_result') in ['ERROR', 'MISSED_SIGNAL', 'UNEXPECTED_SIGNAL'])
    
    if error_count == 0:
        print(f"\n🎉 ALL TESTS PASSED!")
        print(f"   ✅ {correct_count}/{len(results)} scenarios validated correctly")
        print(f"   ✅ RSI strategy logic is working as expected")
    else:
        print(f"\n⚠️ ISSUES DETECTED:")
        print(f"   ✅ Correct: {correct_count}")
        print(f"   ❌ Issues: {error_count}")
        
        for scenario, result in results.items():
            if result.get('validation_result') != 'CORRECT':
                print(f"      • {scenario}: {result.get('validation_result')}")

if __name__ == "__main__":
    main()
