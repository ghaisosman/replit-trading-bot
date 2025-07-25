
#!/usr/bin/env python3
"""
Strategy Entry Logic Validation Test
===================================

Tests the actual strategy implementation to ensure entry signals match RSI conditions.
Specifically designed to catch the issue where trades enter despite RSI not meeting thresholds.
"""

import sys
import os
import asyncio
import pandas as pd
from datetime import datetime
import json

# Add src to path
sys.path.append('src')

from binance_client.client import BinanceClientWrapper
from data_fetcher.price_fetcher import PriceFetcher
from strategy_processor.signal_processor import SignalProcessor
from execution_engine.strategies.rsi_oversold_config import RSIOversoldConfig

async def test_live_strategy_signals():
    """Test live strategy signal generation against actual RSI values"""
    print("🔍 TESTING LIVE STRATEGY SIGNAL GENERATION")
    print("=" * 60)
    
    try:
        # Initialize components
        binance_client = BinanceClientWrapper()
        price_fetcher = PriceFetcher(binance_client)
        signal_processor = SignalProcessor()
        
        # Test symbols that recently had trades
        test_symbols = ['ETHUSDT', 'XRPUSDT', 'BTCUSDT']
        
        results = {}
        
        for symbol in test_symbols:
            print(f"\n📊 TESTING STRATEGY SIGNALS: {symbol}")
            print("-" * 40)
            
            # Get market data
            df = await price_fetcher.get_market_data(symbol, '15m', 100)
            
            if df is None or df.empty:
                print(f"❌ No data for {symbol}")
                continue
            
            # Test RSI strategy specifically
            try:
                # Get RSI signal from strategy processor
                rsi_signal = await signal_processor.evaluate_rsi_strategy(
                    symbol=symbol,
                    df=df
                )
                
                # Calculate actual RSI manually for verification
                def calculate_rsi_manual(prices, period=14):
                    if len(prices) < period + 1:
                        return None
                    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
                    gains = [max(delta, 0) for delta in deltas]
                    losses = [max(-delta, 0) for delta in deltas]
                    avg_gain = sum(gains[:period]) / period
                    avg_loss = sum(losses[:period]) / period
                    for i in range(period, len(gains)):
                        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
                        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
                    if avg_loss == 0:
                        return 100.0
                    rs = avg_gain / avg_loss
                    return 100 - (100 / (1 + rs))
                
                actual_rsi = calculate_rsi_manual(df['close'].tolist(), 14)
                current_price = df['close'].iloc[-1]
                
                # Get config for comparison
                config = RSIOversoldConfig.get_config()
                long_entry = config.get('rsi_long_entry', 40)
                short_entry = config.get('rsi_short_entry', 60)
                
                print(f"💰 Current Price: ${current_price:.4f}")
                print(f"📊 Actual RSI: {actual_rsi:.2f}")
                print(f"⚙️  Long Entry Threshold: <= {long_entry}")
                print(f"⚙️  Short Entry Threshold: >= {short_entry}")
                
                # Check signal vs actual conditions
                if rsi_signal:
                    signal_type = rsi_signal.signal_type.name
                    signal_reason = rsi_signal.reason
                    
                    print(f"🚦 STRATEGY SIGNAL: {signal_type}")
                    print(f"📝 Signal Reason: {signal_reason}")
                    
                    # Validate signal correctness
                    signal_valid = False
                    validation_message = ""
                    
                    if signal_type == 'BUY':
                        if actual_rsi <= long_entry:
                            signal_valid = True
                            validation_message = f"✅ BUY signal valid: RSI {actual_rsi:.2f} <= {long_entry}"
                        else:
                            validation_message = f"❌ BUY signal INVALID: RSI {actual_rsi:.2f} > {long_entry}"
                    
                    elif signal_type == 'SELL':
                        if actual_rsi >= short_entry:
                            signal_valid = True
                            validation_message = f"✅ SELL signal valid: RSI {actual_rsi:.2f} >= {short_entry}"
                        else:
                            validation_message = f"❌ SELL signal INVALID: RSI {actual_rsi:.2f} < {short_entry}"
                    
                    print(f"🔍 VALIDATION: {validation_message}")
                    
                    if not signal_valid:
                        print(f"🚨 LOGIC ERROR DETECTED: Strategy generated {signal_type} signal when RSI conditions not met!")
                    
                else:
                    print(f"🚦 STRATEGY SIGNAL: None")
                    print(f"✅ No signal generated - checking if this is correct...")
                    
                    # Check if no signal is correct
                    if actual_rsi <= long_entry:
                        print(f"❌ MISSED BUY SIGNAL: RSI {actual_rsi:.2f} <= {long_entry} but no signal generated")
                    elif actual_rsi >= short_entry:
                        print(f"❌ MISSED SELL SIGNAL: RSI {actual_rsi:.2f} >= {short_entry} but no signal generated")
                    else:
                        print(f"✅ Correctly no signal: RSI {actual_rsi:.2f} in neutral zone ({long_entry} < RSI < {short_entry})")
                
                # Store results
                results[symbol] = {
                    'actual_rsi': actual_rsi,
                    'current_price': current_price,
                    'signal': signal_type if rsi_signal else None,
                    'signal_reason': signal_reason if rsi_signal else None,
                    'signal_valid': signal_valid if rsi_signal else None,
                    'config': {
                        'long_entry': long_entry,
                        'short_entry': short_entry
                    },
                    'timestamp': datetime.now().isoformat()
                }
                
            except Exception as strategy_error:
                print(f"❌ Strategy evaluation error for {symbol}: {strategy_error}")
                import traceback
                traceback.print_exc()
        
        return results
        
    except Exception as e:
        print(f"❌ Error during strategy testing: {e}")
        import traceback
        traceback.print_exc()
        return {}

async def main():
    """Run strategy entry validation test"""
    print("🧪 STRATEGY ENTRY LOGIC VALIDATION TEST")
    print("=" * 80)
    print("Testing actual strategy implementation against RSI conditions")
    print("=" * 80)
    
    # Run the test
    results = await test_live_strategy_signals()
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"strategy_entry_validation_test_{timestamp}.json"
    
    test_summary = {
        'timestamp': datetime.now().isoformat(),
        'test_type': 'strategy_entry_validation',
        'results': results,
        'summary': 'Strategy implementation validation completed'
    }
    
    with open(results_file, 'w') as f:
        json.dump(test_summary, f, indent=2, default=str)
    
    print(f"\n📊 TEST SUMMARY:")
    print(f"   • Results saved to: {results_file}")
    print(f"   • Symbols tested: {len(results)}")
    
    # Check for issues
    issues_found = []
    for symbol, data in results.items():
        if data.get('signal_valid') is False:
            issues_found.append(f"{symbol}: {data.get('signal')} signal when RSI was {data.get('actual_rsi'):.2f}")
    
    if issues_found:
        print(f"\n🚨 ISSUES DETECTED:")
        for issue in issues_found:
            print(f"   • {issue}")
    else:
        print(f"\n✅ No signal validation issues detected")

if __name__ == "__main__":
    asyncio.run(main())
