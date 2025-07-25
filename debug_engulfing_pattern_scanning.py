
#!/usr/bin/env python3
"""
Debug Engulfing Pattern Strategy Scanning Issues
==============================================

This script investigates why the Engulfing Pattern strategy is not triggering
while other strategies are working correctly.
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime
import json

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def debug_engulfing_strategy():
    """Debug the Engulfing Pattern strategy scanning loop"""
    
    print("🔍 ENGULFING PATTERN STRATEGY DEBUGGING")
    print("=" * 60)
    
    try:
        # Import required modules
        from src.execution_engine.strategies.engulfing_pattern_strategy import EngulfingPatternStrategy
        from src.data_fetcher.price_fetcher import PriceFetcher
        from src.binance_client.client import BinanceClientWrapper
        from src.data_fetcher.websocket_manager import websocket_manager
        
        print("✅ All imports successful")
        
        # Initialize components
        binance_client = BinanceClientWrapper()
        price_fetcher = PriceFetcher(binance_client)
        
        # Test symbols that other strategies are working with
        test_symbols = ['BTCUSDT', 'ETHUSDT', 'ADAUSDT']
        test_interval = '1h'
        
        for symbol in test_symbols:
            print(f"\n📊 TESTING SYMBOL: {symbol}")
            print("-" * 40)
            
            # Get current price
            current_price = price_fetcher.get_current_price(symbol)
            print(f"💰 Current Price: ${current_price:.4f}" if current_price else "❌ Price fetch failed")
            
            # Get market data
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                df = loop.run_until_complete(price_fetcher.get_market_data(symbol, test_interval, limit=100))
            finally:
                loop.close()
            
            if df is None or df.empty:
                print(f"❌ No market data available for {symbol}")
                continue
                
            print(f"📈 Market Data: {len(df)} candles available")
            
            # Test strategy configuration
            strategy_config = {
                'name': f'ENGULFING_PATTERN_{symbol}',
                'symbol': symbol,
                'margin': 10.0,
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
            strategy = EngulfingPatternStrategy(strategy_config['name'], strategy_config)
            print(f"✅ Strategy initialized: {strategy_config['name']}")
            
            # Calculate indicators
            print("🔧 Calculating indicators...")
            df_with_indicators = strategy.calculate_indicators(df.copy())
            
            if df_with_indicators is None or df_with_indicators.empty:
                print("❌ Indicator calculation failed")
                continue
                
            # Check required indicators
            required_indicators = ['rsi', 'bullish_engulfing', 'bearish_engulfing', 'stable_candle']
            missing_indicators = []
            
            for indicator in required_indicators:
                if indicator not in df_with_indicators.columns:
                    missing_indicators.append(indicator)
                else:
                    non_null_count = df_with_indicators[indicator].count()
                    print(f"   ✅ {indicator}: {non_null_count} values")
            
            if missing_indicators:
                print(f"❌ Missing indicators: {missing_indicators}")
                continue
            
            # Check current conditions
            current_idx = -1
            current_rsi = df_with_indicators['rsi'].iloc[current_idx]
            current_price_df = df_with_indicators['close'].iloc[current_idx]
            
            bullish_engulfing = df_with_indicators['bullish_engulfing'].iloc[current_idx]
            bearish_engulfing = df_with_indicators['bearish_engulfing'].iloc[current_idx]
            stable_candle = df_with_indicators['stable_candle'].iloc[current_idx]
            
            # Check price lookback
            price_lookback_col = f'close_{strategy_config["price_lookback_bars"]}_ago'
            if price_lookback_col in df_with_indicators.columns:
                close_5_ago = df_with_indicators[price_lookback_col].iloc[current_idx]
                price_momentum_up = current_price_df > close_5_ago
                price_momentum_down = current_price_df < close_5_ago
            else:
                print(f"❌ Missing price lookback column: {price_lookback_col}")
                continue
            
            print(f"\n📊 CURRENT CONDITIONS:")
            print(f"   💰 Price: ${current_price_df:.4f}")
            print(f"   📈 RSI: {current_rsi:.2f}")
            print(f"   🕯️ Bullish Engulfing: {bullish_engulfing}")
            print(f"   🕯️ Bearish Engulfing: {bearish_engulfing}")
            print(f"   ⚖️ Stable Candle: {stable_candle}")
            print(f"   📉 Price vs 5 bars ago: ${current_price_df:.4f} vs ${close_5_ago:.4f}")
            print(f"   📊 Price Momentum Up: {price_momentum_up}")
            print(f"   📊 Price Momentum Down: {price_momentum_down}")
            
            # Check recent pattern activity
            recent_bullish = df_with_indicators['bullish_engulfing'].tail(10).sum()
            recent_bearish = df_with_indicators['bearish_engulfing'].tail(10).sum()
            recent_stable = df_with_indicators['stable_candle'].tail(10).sum()
            
            print(f"\n📈 RECENT ACTIVITY (Last 10 candles):")
            print(f"   🟢 Bullish Engulfing: {recent_bullish}")
            print(f"   🔴 Bearish Engulfing: {recent_bearish}")
            print(f"   ⚖️ Stable Candles: {recent_stable}")
            
            # Test signal evaluation
            print(f"\n🎯 SIGNAL EVALUATION:")
            signal = strategy.evaluate_entry_signal(df_with_indicators)
            
            if signal:
                print(f"   ✅ SIGNAL DETECTED!")
                print(f"   📊 Type: {signal.signal_type.value}")
                print(f"   💰 Entry: ${signal.entry_price:.4f}")
                print(f"   🛡️ Stop Loss: ${signal.stop_loss:.4f}")
                print(f"   🎯 Take Profit: ${signal.take_profit:.4f}")
                print(f"   📝 Reason: {signal.reason}")
            else:
                print(f"   ⚪ No signal generated")
                
                # Analyze why no signal
                print(f"\n🔍 WHY NO SIGNAL:")
                rsi_threshold = strategy_config['rsi_threshold']
                
                if not (bullish_engulfing or bearish_engulfing):
                    print(f"   ❌ No engulfing pattern detected")
                    
                if not stable_candle:
                    print(f"   ❌ Candle not stable enough (ratio < {strategy_config['stable_candle_ratio']})")
                    
                if bullish_engulfing:
                    if current_rsi >= rsi_threshold:
                        print(f"   ❌ RSI too high for long: {current_rsi:.2f} >= {rsi_threshold}")
                    if not price_momentum_down:
                        print(f"   ❌ Price not declining for long entry")
                        
                if bearish_engulfing:
                    if current_rsi <= rsi_threshold:
                        print(f"   ❌ RSI too low for short: {current_rsi:.2f} <= {rsi_threshold}")
                    if not price_momentum_up:
                        print(f"   ❌ Price not rising for short entry")
            
            print("-" * 40)
    
    except Exception as e:
        print(f"❌ Error during debugging: {e}")
        import traceback
        print(f"🔍 Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    debug_engulfing_strategy()
