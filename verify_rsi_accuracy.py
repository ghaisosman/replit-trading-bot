
#!/usr/bin/env python3
"""
RSI Strategy Accuracy Verification Tool
Verifies that RSI stop loss calculations are working correctly
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.binance_client.client import BinanceClientWrapper
from src.data_fetcher.price_fetcher import PriceFetcher
from src.strategy_processor.signal_processor import SignalProcessor
import pandas as pd

async def verify_rsi_accuracy():
    """Verify RSI strategy accuracy with different configurations"""
    try:
        print("🔍 RSI STRATEGY ACCURACY VERIFICATION")
        print("=" * 60)
        
        # Initialize components
        binance_client = BinanceClientWrapper()
        price_fetcher = PriceFetcher(binance_client)
        signal_processor = SignalProcessor()
        
        # Test configurations
        test_configs = [
            {
                'name': 'rsi_test_conservative',
                'symbol': 'BTCUSDT',
                'margin': 50.0,
                'leverage': 5,
                'max_loss_pct': 5,  # Conservative 5%
                'rsi_long_entry': 30,
                'rsi_short_entry': 70,
                'rsi_long_exit': 70,
                'rsi_short_exit': 30
            },
            {
                'name': 'rsi_test_moderate',
                'symbol': 'BTCUSDT',
                'margin': 100.0,
                'leverage': 10,
                'max_loss_pct': 10,  # Standard 10%
                'rsi_long_entry': 40,
                'rsi_short_entry': 60,
                'rsi_long_exit': 70,
                'rsi_short_exit': 30
            }
        ]
        
        for i, config in enumerate(test_configs, 1):
            print(f"\n📊 TEST {i}: {config['name'].upper()}")
            print("-" * 40)
            
            # Get current market data
            df = await price_fetcher.get_market_data(config['symbol'], '15m', 100)
            
            if df is None or df.empty:
                print(f"❌ No data for {config['symbol']}")
                continue
            
            # Calculate indicators
            df = price_fetcher.calculate_indicators(df)
            
            if 'rsi' not in df.columns:
                print(f"❌ RSI not calculated")
                continue
                
            current_price = df['close'].iloc[-1]
            current_rsi = df['rsi'].iloc[-1]
            
            print(f"💰 Current Price: ${current_price:.2f}")
            print(f"📈 Current RSI: {current_rsi:.1f}")
            print(f"⚙️ Config: Margin=${config['margin']} | Leverage={config['leverage']}x | Max Loss={config['max_loss_pct']}%")
            
            # Test signal generation
            signal = signal_processor.evaluate_entry_conditions(df, config)
            
            if signal:
                print(f"🎯 SIGNAL GENERATED: {signal.signal_type.value}")
                print(f"🏁 Entry: ${signal.entry_price:.4f}")
                print(f"🛡️ Stop Loss: ${signal.stop_loss:.4f}")
                print(f"📝 Reason: {signal.reason}")
                
                # Calculate stop loss verification
                if signal.signal_type.value == 'BUY':
                    sl_distance_pct = ((signal.entry_price - signal.stop_loss) / signal.entry_price) * 100
                else:
                    sl_distance_pct = ((signal.stop_loss - signal.entry_price) / signal.entry_price) * 100
                
                # Expected max loss calculation
                position_size = config['margin'] * config['leverage']
                expected_max_loss_usdt = config['margin'] * (config['max_loss_pct'] / 100)
                expected_sl_pct = (expected_max_loss_usdt / position_size) * 100
                
                print(f"🔍 VERIFICATION:")
                print(f"   Stop Loss Distance: {sl_distance_pct:.3f}%")
                print(f"   Expected Distance: {expected_sl_pct:.3f}%")
                print(f"   Max Loss USDT: ${expected_max_loss_usdt:.2f}")
                print(f"   Position Size: ${position_size:.2f}")
                
                # Check accuracy
                accuracy_diff = abs(sl_distance_pct - expected_sl_pct)
                if accuracy_diff < 0.01:  # Within 0.01%
                    print(f"✅ ACCURACY: EXCELLENT (diff: {accuracy_diff:.4f}%)")
                elif accuracy_diff < 0.1:
                    print(f"✅ ACCURACY: GOOD (diff: {accuracy_diff:.4f}%)")
                else:
                    print(f"⚠️ ACCURACY: NEEDS IMPROVEMENT (diff: {accuracy_diff:.4f}%)")
                    
            else:
                print(f"⏳ No signal at current RSI level {current_rsi:.1f}")
                print(f"   Long Entry: RSI <= {config['rsi_long_entry']}")
                print(f"   Short Entry: RSI >= {config['rsi_short_entry']}")
        
        print(f"\n✅ RSI ACCURACY VERIFICATION COMPLETE")
        
    except Exception as e:
        print(f"❌ Error during verification: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(verify_rsi_accuracy())
