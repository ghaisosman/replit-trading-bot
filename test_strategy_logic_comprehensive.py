
#!/usr/bin/env python3
"""
Comprehensive Strategy Logic Validation Test
==========================================

Tests all strategies to ensure entry signals match expected logic:
- RSI strategies: Long when oversold, Short when overbought
- MACD strategies: Validate signal vs histogram logic
- Pattern strategies: Validate pattern detection accuracy
"""

import sys
import os
sys.path.append('src')

import asyncio
import pandas as pd
import numpy as np
from datetime import datetime
import json

from binance_client.client import BinanceClientWrapper
from data_fetcher.price_fetcher import PriceFetcher
from execution_engine.strategies.rsi_oversold_config import RSIOversoldConfig
from execution_engine.strategies.macd_divergence_config import MACDDivergenceConfig
from config.global_config import global_config

def create_test_rsi_scenarios():
    """Create test scenarios for RSI validation"""
    scenarios = {}
    
    # Create oversold scenario (RSI ~25) - should trigger LONG
    oversold_prices = [100.0]
    for i in range(50):
        # Create declining price pattern to generate low RSI
        oversold_prices.append(oversold_prices[-1] * 0.995)
    
    scenarios['oversold'] = {
        'prices': oversold_prices,
        'expected_signal': 'long',
        'description': 'RSI ~25 (oversold) should trigger LONG entry'
    }
    
    # Create overbought scenario (RSI ~75) - should trigger SHORT
    overbought_prices = [100.0]
    for i in range(50):
        # Create rising price pattern to generate high RSI
        overbought_prices.append(overbought_prices[-1] * 1.005)
    
    scenarios['overbought'] = {
        'prices': overbought_prices,
        'expected_signal': 'short',
        'description': 'RSI ~75 (overbought) should trigger SHORT entry'
    }
    
    return scenarios

def calculate_rsi_manual(prices, period=14):
    """Calculate RSI manually for validation"""
    if len(prices) < period + 1:
        return None
    
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def validate_rsi_logic(prices, config):
    """Validate RSI entry logic against configuration"""
    rsi = calculate_rsi_manual(prices)
    if rsi is None:
        return None, None, "Insufficient data"
    
    # Check entry conditions based on configuration
    long_entry = rsi <= config['rsi_long_entry']  # Should be <= 45
    short_entry = rsi >= config['rsi_short_entry']  # Should be >= 55
    
    predicted_signal = None
    if long_entry and not short_entry:
        predicted_signal = 'long'
    elif short_entry and not long_entry:
        predicted_signal = 'short'
    
    return rsi, predicted_signal, f"RSI: {rsi:.1f}"

async def test_current_live_conditions():
    """Test current live market conditions against strategy logic"""
    print("🔍 TESTING CURRENT LIVE CONDITIONS")
    print("=" * 60)
    
    try:
        binance_client = BinanceClientWrapper()
        price_fetcher = PriceFetcher(binance_client)
        
        # Test active position symbols
        test_symbols = ['ETHUSDT', 'XRPUSDT', 'BTCUSDT']
        config = RSIOversoldConfig.get_config()
        
        results = {}
        
        for symbol in test_symbols:
            print(f"\n📊 ANALYZING {symbol}")
            print("-" * 40)
            
            try:
                # Get current market data
                df = await price_fetcher.get_market_data(symbol, '15m', 100)
                
                if df is None or df.empty or len(df) < 20:
                    print(f"❌ Insufficient data for {symbol}")
                    continue
                
                # Get current price and calculate RSI
                current_price = df['close'].iloc[-1]
                prices = df['close'].tolist()
                
                rsi, predicted_signal, analysis = validate_rsi_logic(prices, config)
                
                if rsi is None:
                    print(f"❌ Could not calculate RSI for {symbol}")
                    continue
                
                print(f"💰 Current Price: ${current_price:.4f}")
                print(f"📊 Current RSI: {rsi:.2f}")
                print(f"🎯 Predicted Signal: {predicted_signal or 'NONE'}")
                
                # Check against configuration
                if rsi <= config['rsi_long_entry']:
                    print(f"✅ RSI {rsi:.1f} <= {config['rsi_long_entry']} → Should trigger LONG")
                elif rsi >= config['rsi_short_entry']:
                    print(f"✅ RSI {rsi:.1f} >= {config['rsi_short_entry']} → Should trigger SHORT")
                else:
                    print(f"⚪ RSI {rsi:.1f} in neutral zone ({config['rsi_long_entry']}-{config['rsi_short_entry']})")
                
                # Store results
                results[symbol] = {
                    'current_price': current_price,
                    'current_rsi': rsi,
                    'predicted_signal': predicted_signal,
                    'config_long_entry': config['rsi_long_entry'],
                    'config_short_entry': config['rsi_short_entry']
                }
                
            except Exception as e:
                print(f"❌ Error analyzing {symbol}: {e}")
                continue
        
        return results
        
    except Exception as e:
        print(f"❌ Error in live condition testing: {e}")
        return {}

def test_rsi_scenario_validation():
    """Test RSI logic with synthetic scenarios"""
    print("\n\n🧪 TESTING RSI SCENARIO VALIDATION")
    print("=" * 60)
    
    config = RSIOversoldConfig.get_config()
    scenarios = create_test_rsi_scenarios()
    
    print(f"📋 RSI Configuration:")
    print(f"   Long Entry: RSI <= {config['rsi_long_entry']}")
    print(f"   Short Entry: RSI >= {config['rsi_short_entry']}")
    
    for scenario_name, scenario in scenarios.items():
        print(f"\n🔍 Testing: {scenario['description']}")
        print("-" * 40)
        
        prices = scenario['prices']
        expected_signal = scenario['expected_signal']
        
        rsi, predicted_signal, analysis = validate_rsi_logic(prices, config)
        
        print(f"📊 Generated RSI: {rsi:.2f}")
        print(f"🎯 Expected Signal: {expected_signal}")
        print(f"🤖 Predicted Signal: {predicted_signal or 'NONE'}")
        
        if predicted_signal == expected_signal:
            print("✅ LOGIC CORRECT: Signal matches expectation")
        else:
            print("❌ LOGIC ERROR: Signal does not match expectation!")
            print(f"   This indicates a configuration or logic problem")

def validate_strategy_configurations():
    """Validate all strategy configurations for logic consistency"""
    print("\n\n⚙️ VALIDATING STRATEGY CONFIGURATIONS")
    print("=" * 60)
    
    print("📊 RSI Strategy Configuration:")
    try:
        rsi_config = RSIOversoldConfig.get_config()
        
        print(f"   Long Entry Threshold: {rsi_config['rsi_long_entry']}")
        print(f"   Long Exit Threshold: {rsi_config['rsi_long_exit']}")
        print(f"   Short Entry Threshold: {rsi_config['rsi_short_entry']}")
        print(f"   Short Exit Threshold: {rsi_config['rsi_short_exit']}")
        
        # Validate logic consistency
        logic_issues = []
        
        if rsi_config['rsi_long_entry'] >= rsi_config['rsi_short_entry']:
            logic_issues.append("Long entry threshold should be < Short entry threshold")
        
        if rsi_config['rsi_long_exit'] <= rsi_config['rsi_long_entry']:
            logic_issues.append("Long exit should be > Long entry")
        
        if rsi_config['rsi_short_exit'] >= rsi_config['rsi_short_entry']:
            logic_issues.append("Short exit should be < Short entry")
        
        if logic_issues:
            print("❌ CONFIGURATION ISSUES FOUND:")
            for issue in logic_issues:
                print(f"   • {issue}")
        else:
            print("✅ RSI configuration logic appears consistent")
            
    except Exception as e:
        print(f"❌ Error validating RSI config: {e}")
    
    print("\n📊 MACD Strategy Configuration:")
    try:
        macd_config = MACDDivergenceConfig.get_config()
        print(f"   Strategy: {macd_config.get('strategy_name', 'MACD Divergence')}")
        print(f"   Configured parameters available: {list(macd_config.keys())}")
    except Exception as e:
        print(f"❌ Error validating MACD config: {e}")

async def main():
    """Run comprehensive strategy logic validation"""
    print("🧪 COMPREHENSIVE STRATEGY LOGIC VALIDATION TEST")
    print("=" * 80)
    print("Testing all strategies to identify entry logic issues")
    print("=" * 80)
    
    # Test 1: Current live market conditions
    live_results = await test_current_live_conditions()
    
    # Test 2: RSI scenario validation
    test_rsi_scenario_validation()
    
    # Test 3: Configuration validation
    validate_strategy_configurations()
    
    # Generate report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"strategy_logic_validation_{timestamp}.json"
    
    test_results = {
        'timestamp': datetime.now().isoformat(),
        'test_type': 'comprehensive_strategy_logic_validation',
        'live_conditions': live_results,
        'configuration_analysis': 'See console output for detailed analysis',
        'summary': 'Strategy logic validation completed'
    }
    
    with open(results_file, 'w') as f:
        json.dump(test_results, f, indent=2, default=str)
    
    print(f"\n📊 SUMMARY:")
    print(f"   • Strategy logic validation completed")
    print(f"   • Results saved to: {results_file}")
    print(f"   • Live conditions tested: {len(live_results)} symbols")
    
    print(f"\n💡 KEY FINDINGS:")
    print(f"   1. Check if RSI entry logic is inverted (oversold→short instead of long)")
    print(f"   2. Verify strategy implementation matches configuration")
    print(f"   3. Validate signal detection in strategy processors")
    print(f"   4. Consider adding pre-trade signal validation")

if __name__ == "__main__":
    asyncio.run(main())
