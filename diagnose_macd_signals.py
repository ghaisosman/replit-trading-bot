
#!/usr/bin/env python3
"""
MACD Strategy Signal Detection Diagnosis Script
This script will perform intensive testing to identify why MACD signals aren't being detected.
"""

import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
import sys
import os

# Add src to path for imports
sys.path.append('src')

from binance_client.client import BinanceClientWrapper
from execution_engine.strategies.macd_divergence_strategy import MACDDivergenceStrategy
from strategy_processor.signal_processor import SignalProcessor
from config.trading_config import TradingConfig

class MACDSignalDiagnostic:
    def __init__(self):
        self.client = BinanceClientWrapper()
        self.config = TradingConfig()
        
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        print("🔍 MACD Signal Detection Diagnostic Tool")
        print("=" * 60)

    def get_test_symbols(self):
        """Get symbols to test MACD strategy on"""
        return ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'ADAUSDT', 'XRPUSDT']

    def get_macd_config_variants(self):
        """Get different MACD configuration variants to test"""
        return [
            # Ultra relaxed config
            {
                'name': 'macd_ultra_relaxed',
                'symbol': 'BTCUSDT',
                'margin': 50.0,
                'leverage': 5,
                'max_loss_pct': 10.0,
                'macd_fast': 8,
                'macd_slow': 21,
                'macd_signal': 5,
                'min_histogram_threshold': 0.00001,
                'macd_entry_threshold': 0.0001,
                'macd_exit_threshold': 0.0001,
                'confirmation_candles': 1
            },
            # Standard relaxed config
            {
                'name': 'macd_relaxed',
                'symbol': 'BTCUSDT',
                'margin': 50.0,
                'leverage': 5,
                'max_loss_pct': 10.0,
                'macd_fast': 12,
                'macd_slow': 26,
                'macd_signal': 9,
                'min_histogram_threshold': 0.0001,
                'macd_entry_threshold': 0.001,
                'macd_exit_threshold': 0.001,
                'confirmation_candles': 1
            },
            # Very sensitive config
            {
                'name': 'macd_sensitive',
                'symbol': 'BTCUSDT',
                'margin': 50.0,
                'leverage': 5,
                'max_loss_pct': 10.0,
                'macd_fast': 5,
                'macd_slow': 15,
                'macd_signal': 3,
                'min_histogram_threshold': 0.000001,
                'macd_entry_threshold': 0.0001,
                'macd_exit_threshold': 0.0001,
                'confirmation_candles': 1
            }
        ]

    def fetch_market_data(self, symbol, timeframe='15m', limit=200):
        """Fetch market data for testing"""
        try:
            print(f"📊 Fetching {symbol} {timeframe} data (last {limit} candles)...")
            
            klines = self.client.client.futures_klines(
                symbol=symbol,
                interval=timeframe,
                limit=limit
            )
            
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            
            # Convert to proper data types
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col])
            
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df = df.set_index('timestamp')
            
            print(f"✅ Fetched {len(df)} candles for {symbol}")
            print(f"   Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")
            print(f"   Time range: {df.index[0]} to {df.index[-1]}")
            
            return df
            
        except Exception as e:
            print(f"❌ Error fetching data for {symbol}: {e}")
            return pd.DataFrame()

    def analyze_macd_indicators(self, df, config):
        """Analyze MACD indicators in detail"""
        print(f"\n🔬 ANALYZING MACD INDICATORS")
        print(f"Config: Fast={config['macd_fast']}, Slow={config['macd_slow']}, Signal={config['macd_signal']}")
        
        strategy = MACDDivergenceStrategy('test_macd', config)
        df_with_indicators = strategy.calculate_indicators(df.copy())
        
        if 'macd' not in df_with_indicators.columns:
            print("❌ MACD indicators not calculated!")
            return df_with_indicators, []
        
        # Check recent MACD values
        recent_data = df_with_indicators.tail(10)
        
        print("\n📈 Recent MACD Values (last 10 candles):")
        print("Time                 | Price    | MACD      | Signal    | Histogram | Status")
        print("-" * 85)
        
        for i, (timestamp, row) in enumerate(recent_data.iterrows()):
            macd_val = row.get('macd', 0)
            signal_val = row.get('macd_signal', 0)
            hist_val = row.get('macd_histogram', 0)
            
            # Determine potential signal status
            status = "NEUTRAL"
            if macd_val < signal_val and hist_val > 0:
                status = "BULL_POTENTIAL"
            elif macd_val > signal_val and hist_val < 0:
                status = "BEAR_POTENTIAL"
            elif abs(macd_val - signal_val) < config['macd_entry_threshold'] * row['close']:
                status = "TOO_CLOSE"
            
            print(f"{timestamp.strftime('%Y-%m-%d %H:%M')} | ${row['close']:8.2f} | {macd_val:9.6f} | {signal_val:9.6f} | {hist_val:9.6f} | {status}")
        
        return df_with_indicators, recent_data

    def test_signal_generation(self, df, config):
        """Test signal generation with detailed logging"""
        print(f"\n🎯 TESTING SIGNAL GENERATION")
        
        strategy = MACDDivergenceStrategy('diagnostic_macd', config)
        df_with_indicators = strategy.calculate_indicators(df.copy())
        
        signals_found = []
        
        # Test signal generation on recent data windows
        for i in range(50, len(df_with_indicators), 5):  # Test every 5th candle
            test_window = df_with_indicators.iloc[:i+1]
            
            try:
                signal = strategy.evaluate_entry_signal(test_window)
                if signal:
                    signals_found.append({
                        'timestamp': test_window.index[-1],
                        'signal': signal,
                        'price': test_window['close'].iloc[-1],
                        'macd': test_window['macd'].iloc[-1],
                        'signal_line': test_window['macd_signal'].iloc[-1],
                        'histogram': test_window['macd_histogram'].iloc[-1]
                    })
                    print(f"✅ SIGNAL FOUND at {test_window.index[-1]}: {signal.signal_type.value} - {signal.reason}")
                    
            except Exception as e:
                print(f"❌ Error testing signal at index {i}: {e}")
        
        print(f"\n📊 Total signals found: {len(signals_found)}")
        return signals_found

    def test_entry_conditions_manually(self, df, config):
        """Manually test entry conditions step by step"""
        print(f"\n🔧 MANUAL ENTRY CONDITION TESTING")
        
        strategy = MACDDivergenceStrategy('manual_test', config)
        df_with_indicators = strategy.calculate_indicators(df.copy())
        
        if len(df_with_indicators) < 50:
            print("❌ Insufficient data for testing")
            return
        
        current_data = df_with_indicators.iloc[-10:]  # Last 10 candles
        
        for i, (timestamp, row) in enumerate(current_data.iterrows()):
            print(f"\n--- Testing candle {i+1}/10: {timestamp} ---")
            print(f"Price: ${row['close']:.2f}")
            
            if pd.isna(row.get('macd')) or pd.isna(row.get('macd_signal')) or pd.isna(row.get('macd_histogram')):
                print("❌ Missing MACD data")
                continue
            
            macd_current = row['macd']
            signal_current = row['macd_signal']
            histogram_current = row['macd_histogram']
            
            print(f"MACD: {macd_current:.6f}")
            print(f"Signal: {signal_current:.6f}")
            print(f"Histogram: {histogram_current:.6f}")
            
            # Check previous candle for momentum
            if i > 0:
                prev_row = current_data.iloc[i-1]
                histogram_prev = prev_row.get('macd_histogram', 0)
                histogram_momentum = histogram_current - histogram_prev
                
                print(f"Previous Histogram: {histogram_prev:.6f}")
                print(f"Momentum: {histogram_momentum:.6f}")
                
                line_distance = abs(macd_current - signal_current) / row['close']
                print(f"Line Distance: {line_distance:.6f} (threshold: {config['macd_entry_threshold']:.6f})")
                
                # Test bullish conditions
                print("\n🟢 BULLISH CONDITIONS:")
                print(f"  MACD < Signal: {macd_current < signal_current}")
                print(f"  Histogram Rising: {histogram_current > histogram_prev}")
                print(f"  Histogram Negative: {histogram_current < 0}")
                print(f"  Momentum >= Threshold: {abs(histogram_momentum) >= config['min_histogram_threshold']}")
                print(f"  Distance >= Threshold: {line_distance >= config['macd_entry_threshold']}")
                
                # Test bearish conditions
                print("\n🔴 BEARISH CONDITIONS:")
                print(f"  MACD > Signal: {macd_current > signal_current}")
                print(f"  Histogram Falling: {histogram_current < histogram_prev}")
                print(f"  Histogram Positive: {histogram_current > 0}")
                print(f"  Momentum >= Threshold: {abs(histogram_momentum) >= config['min_histogram_threshold']}")
                print(f"  Distance >= Threshold: {line_distance >= config['macd_entry_threshold']}")

    def run_comprehensive_test(self):
        """Run comprehensive MACD signal detection test"""
        print("🚀 Starting Comprehensive MACD Signal Detection Test\n")
        
        symbols = self.get_test_symbols()
        configs = self.get_macd_config_variants()
        
        total_signals = 0
        
        for symbol in symbols:
            print(f"\n{'='*60}")
            print(f"🎯 TESTING SYMBOL: {symbol}")
            print(f"{'='*60}")
            
            # Fetch data
            df = self.fetch_market_data(symbol, '15m', 200)
            if df.empty:
                continue
            
            for config in configs:
                config['symbol'] = symbol
                print(f"\n{'*'*40}")
                print(f"📊 Testing Config: {config['name']}")
                print(f"{'*'*40}")
                
                try:
                    # Analyze indicators
                    df_with_indicators, recent_data = self.analyze_macd_indicators(df, config)
                    
                    # Test signal generation
                    signals = self.test_signal_generation(df_with_indicators, config)
                    total_signals += len(signals)
                    
                    # Manual condition testing
                    self.test_entry_conditions_manually(df_with_indicators, config)
                    
                except Exception as e:
                    print(f"❌ Error testing config {config['name']}: {e}")
                    import traceback
                    traceback.print_exc()
        
        print(f"\n{'='*60}")
        print(f"🏁 DIAGNOSTIC COMPLETE")
        print(f"{'='*60}")
        print(f"Total signals detected across all tests: {total_signals}")
        
        if total_signals == 0:
            print("\n❌ CRITICAL ISSUE: No signals detected in any configuration!")
            print("Possible causes:")
            print("1. MACD calculation errors")
            print("2. Entry condition logic flaws") 
            print("3. Threshold values too restrictive")
            print("4. Data processing issues")
            print("5. Strategy class implementation bugs")
        else:
            print(f"\n✅ Signals were detected, issue may be configuration-specific")

    def test_live_data_stream(self):
        """Test with live streaming data to see real-time behavior"""
        print(f"\n🔴 LIVE DATA STREAM TEST")
        print("Testing MACD detection with live 1m data...")
        
        symbol = 'BTCUSDT'
        config = self.get_macd_config_variants()[0]  # Ultra relaxed
        config['symbol'] = symbol
        
        try:
            # Get recent 1m data
            df = self.fetch_market_data(symbol, '1m', 100)
            if df.empty:
                print("❌ No live data available")
                return
            
            strategy = MACDDivergenceStrategy('live_test', config)
            df_with_indicators = strategy.calculate_indicators(df.copy())
            
            print(f"📊 Live Data Analysis (last 5 candles):")
            recent = df_with_indicators.tail(5)
            
            for timestamp, row in recent.iterrows():
                print(f"{timestamp}: Price=${row['close']:.2f}, MACD={row.get('macd', 0):.6f}, Signal={row.get('macd_signal', 0):.6f}, Hist={row.get('macd_histogram', 0):.6f}")
                
                # Test signal on this specific candle
                signal = strategy.evaluate_entry_signal(df_with_indicators.loc[:timestamp])
                if signal:
                    print(f"  🎯 LIVE SIGNAL: {signal.signal_type.value} - {signal.reason}")
                    
        except Exception as e:
            print(f"❌ Live test error: {e}")

def main():
    diagnostic = MACDSignalDiagnostic()
    
    try:
        # Run comprehensive test
        diagnostic.run_comprehensive_test()
        
        # Test with live data
        diagnostic.test_live_data_stream()
        
    except KeyboardInterrupt:
        print("\n🛑 Diagnostic interrupted by user")
    except Exception as e:
        print(f"\n❌ Diagnostic failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
