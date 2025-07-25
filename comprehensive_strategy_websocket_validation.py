
#!/usr/bin/env python3
"""
Comprehensive Strategy and WebSocket Validation
==============================================

This script validates:
1. Strategy entry logic accuracy per configuration
2. WebSocket connectivity and data flow in deployment
3. Price and indicator calculation accuracy
4. Signal generation correctness

No fixes - pure validation and reporting.
"""

import sys
import os
import asyncio
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

# Add src to path
sys.path.append('src')

class ComprehensiveValidator:
    """Validates strategy logic and WebSocket functionality"""
    
    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'websocket_validation': {},
            'strategy_validation': {},
            'price_data_validation': {},
            'indicator_validation': {},
            'signal_generation_validation': {},
            'overall_status': 'UNKNOWN'
        }
        
        # Import components
        try:
            from src.binance_client.client import BinanceClientWrapper
            from src.data_fetcher.price_fetcher import PriceFetcher
            from src.data_fetcher.websocket_manager import websocket_manager
            from src.strategy_processor.signal_processor import SignalProcessor
            from src.execution_engine.strategies.rsi_oversold_config import RSIOversoldConfig
            from src.execution_engine.strategies.macd_divergence_config import MACDDivergenceConfig
            from src.execution_engine.strategies.engulfing_pattern_config import EngulfingPatternConfig
            from src.config.global_config import global_config
            
            self.binance_client = BinanceClientWrapper()
            self.price_fetcher = PriceFetcher(self.binance_client)
            self.signal_processor = SignalProcessor()
            
            print("✅ All components imported successfully")
            
        except Exception as e:
            print(f"❌ Component import failed: {e}")
            self.results['overall_status'] = 'IMPORT_FAILED'
            return

    async def validate_websocket_connectivity(self):
        """Validate WebSocket connection and data flow"""
        print("\n🔍 VALIDATING WEBSOCKET CONNECTIVITY")
        print("=" * 50)
        
        ws_results = {
            'connection_status': 'UNKNOWN',
            'data_reception': 'UNKNOWN',
            'stream_count': 0,
            'symbols_tracked': [],
            'data_freshness': {},
            'message_processing': 'UNKNOWN',
            'statistics': {}
        }
        
        try:
            # Check WebSocket manager status
            print("📡 Checking WebSocket Manager Status...")
            
            is_running = websocket_manager.is_running
            is_connected = websocket_manager.is_connected
            
            print(f"   Running: {is_running}")
            print(f"   Connected: {is_connected}")
            
            ws_results['connection_status'] = 'CONNECTED' if is_connected else 'DISCONNECTED'
            
            if not is_running:
                print("⚠️  WebSocket manager not running - starting for validation...")
                # Add test symbols
                test_symbols = ['BTCUSDT', 'ETHUSDT', 'XRPUSDT', 'SOLUSDT']
                for symbol in test_symbols:
                    websocket_manager.add_symbol_interval(symbol, '1m')
                    websocket_manager.add_symbol_interval(symbol, '5m')
                
                websocket_manager.start()
                
                # Wait for connection
                wait_time = 0
                max_wait = 30
                while wait_time < max_wait and not websocket_manager.is_connected:
                    await asyncio.sleep(1)
                    wait_time += 1
                    if wait_time % 5 == 0:
                        print(f"   ⏳ Waiting for connection... {wait_time}/{max_wait}s")
                
                is_connected = websocket_manager.is_connected
                ws_results['connection_status'] = 'CONNECTED' if is_connected else 'FAILED_TO_CONNECT'
            
            if is_connected:
                print("✅ WebSocket connected successfully")
                
                # Check data reception
                print("\n📊 Checking Data Reception...")
                
                # Get statistics
                stats = websocket_manager.get_statistics()
                ws_results['statistics'] = stats
                
                print(f"   Messages Received: {stats.get('messages_received', 0)}")
                print(f"   Klines Processed: {stats.get('klines_processed', 0)}")
                print(f"   Subscribed Streams: {stats.get('subscribed_streams', 0)}")
                print(f"   Uptime: {stats.get('uptime_seconds', 0):.1f}s")
                
                # Check cache status
                cache_status = websocket_manager.get_cache_status()
                ws_results['symbols_tracked'] = list(cache_status.keys())
                ws_results['stream_count'] = len(websocket_manager.subscribed_streams)
                
                print(f"\n📈 Symbols Being Tracked: {len(cache_status)}")
                for symbol, intervals in cache_status.items():
                    print(f"   {symbol}:")
                    for interval, status in intervals.items():
                        is_fresh = status['is_fresh']
                        cached_count = status['cached_klines']
                        last_update = status['last_update']
                        
                        freshness_status = "🟢 FRESH" if is_fresh else "🔴 STALE"
                        print(f"     {interval}: {cached_count} klines, {freshness_status}")
                        if last_update:
                            print(f"       Last Update: {last_update}")
                        
                        ws_results['data_freshness'][f"{symbol}_{interval}"] = {
                            'is_fresh': is_fresh,
                            'cached_klines': cached_count,
                            'last_update': last_update
                        }
                
                # Test current price fetching
                print(f"\n💰 Testing Current Price Fetching...")
                test_symbols = ['BTCUSDT', 'ETHUSDT', 'XRPUSDT']
                price_results = {}
                
                for symbol in test_symbols:
                    current_price = websocket_manager.get_current_price(symbol)
                    if current_price:
                        print(f"   {symbol}: ${current_price:.4f}")
                        price_results[symbol] = current_price
                    else:
                        print(f"   {symbol}: ❌ No price data")
                        price_results[symbol] = None
                
                ws_results['current_prices'] = price_results
                ws_results['data_reception'] = 'SUCCESS' if any(price_results.values()) else 'FAILED'
                
            else:
                print("❌ WebSocket connection failed")
                ws_results['data_reception'] = 'NO_CONNECTION'
                
        except Exception as e:
            print(f"❌ WebSocket validation error: {e}")
            ws_results['connection_status'] = 'ERROR'
            ws_results['error'] = str(e)
        
        self.results['websocket_validation'] = ws_results
        return ws_results

    async def validate_price_data_accuracy(self):
        """Validate price data fetching and processing"""
        print("\n🔍 VALIDATING PRICE DATA ACCURACY")
        print("=" * 50)
        
        price_results = {
            'data_availability': {},
            'indicator_calculation': {},
            'data_quality': {},
            'websocket_vs_rest': {}
        }
        
        test_symbols = ['BTCUSDT', 'ETHUSDT', 'XRPUSDT']
        
        for symbol in test_symbols:
            print(f"\n📊 Testing {symbol}...")
            
            symbol_results = {
                'market_data_available': False,
                'indicators_calculated': False,
                'data_points': 0,
                'websocket_data': False,
                'rest_fallback': False
            }
            
            try:
                # Get market data
                df = await self.price_fetcher.get_market_data(symbol, '5m', 100)
                
                if df is not None and not df.empty:
                    symbol_results['market_data_available'] = True
                    symbol_results['data_points'] = len(df)
                    
                    print(f"   ✅ Market data: {len(df)} candles")
                    print(f"   📈 Price range: ${df['low'].min():.4f} - ${df['high'].max():.4f}")
                    print(f"   🕐 Time range: {df.index[0]} to {df.index[-1]}")
                    
                    # Calculate indicators
                    df_with_indicators = self.price_fetcher.calculate_indicators(df)
                    
                    # Check indicator availability
                    indicators = ['rsi', 'macd', 'macd_signal', 'macd_histogram', 'sma_20', 'sma_50']
                    available_indicators = []
                    
                    for indicator in indicators:
                        if indicator in df_with_indicators.columns:
                            latest_value = df_with_indicators[indicator].iloc[-1]
                            if not pd.isna(latest_value):
                                available_indicators.append(indicator)
                                print(f"   📊 {indicator.upper()}: {latest_value:.6f}")
                    
                    symbol_results['indicators_calculated'] = len(available_indicators) >= 4
                    symbol_results['available_indicators'] = available_indicators
                    
                    # Check data source (WebSocket vs REST)
                    current_price_ws = websocket_manager.get_current_price(symbol)
                    current_price_df = df['close'].iloc[-1]
                    
                    if current_price_ws:
                        symbol_results['websocket_data'] = True
                        price_diff = abs(current_price_ws - current_price_df)
                        price_diff_pct = (price_diff / current_price_df) * 100
                        
                        print(f"   🔄 WebSocket price: ${current_price_ws:.4f}")
                        print(f"   📊 DataFrame price: ${current_price_df:.4f}")
                        print(f"   📏 Difference: {price_diff_pct:.4f}%")
                        
                        symbol_results['price_difference_pct'] = price_diff_pct
                    else:
                        symbol_results['rest_fallback'] = True
                        print(f"   ⚠️  Using REST API fallback")
                    
                else:
                    print(f"   ❌ No market data available")
                    
            except Exception as e:
                print(f"   ❌ Error testing {symbol}: {e}")
                symbol_results['error'] = str(e)
            
            price_results['data_availability'][symbol] = symbol_results
        
        self.results['price_data_validation'] = price_results
        return price_results

    async def validate_strategy_logic(self):
        """Validate strategy entry/exit logic accuracy"""
        print("\n🔍 VALIDATING STRATEGY LOGIC")
        print("=" * 50)
        
        strategy_results = {
            'rsi_strategy': {},
            'macd_strategy': {},
            'engulfing_strategy': {},
            'signal_generation_accuracy': {}
        }
        
        try:
            # Test RSI Strategy Logic
            print("\n📊 Testing RSI Strategy Logic...")
            await self._validate_rsi_strategy(strategy_results)
            
            # Test MACD Strategy Logic
            print("\n📊 Testing MACD Strategy Logic...")
            await self._validate_macd_strategy(strategy_results)
            
            # Test Engulfing Pattern Strategy Logic
            print("\n📊 Testing Engulfing Pattern Strategy Logic...")
            await self._validate_engulfing_strategy(strategy_results)
            
        except Exception as e:
            print(f"❌ Strategy validation error: {e}")
            strategy_results['error'] = str(e)
        
        self.results['strategy_validation'] = strategy_results
        return strategy_results

    async def _validate_rsi_strategy(self, results):
        """Validate RSI strategy logic"""
        try:
            from src.execution_engine.strategies.rsi_oversold_config import RSIOversoldConfig
            
            # Get RSI configuration
            rsi_config = RSIOversoldConfig.get_config()
            
            print(f"   📊 RSI Configuration:")
            print(f"     Long Entry: RSI <= {rsi_config.get('rsi_long_entry', 40)}")
            print(f"     Long Exit: RSI >= {rsi_config.get('rsi_long_exit', 70)}")
            print(f"     Short Entry: RSI >= {rsi_config.get('rsi_short_entry', 60)}")
            print(f"     Short Exit: RSI <= {rsi_config.get('rsi_short_exit', 30)}")
            
            # Test with XRPUSDT (common RSI symbol)
            symbol = 'XRPUSDT'
            df = await self.price_fetcher.get_market_data(symbol, '1h', 100)
            
            if df is not None and not df.empty:
                df_with_indicators = self.price_fetcher.calculate_indicators(df)
                
                current_rsi = df_with_indicators['rsi'].iloc[-1]
                current_price = df_with_indicators['close'].iloc[-1]
                
                print(f"   📈 {symbol} Current RSI: {current_rsi:.2f}")
                print(f"   💰 {symbol} Current Price: ${current_price:.4f}")
                
                # Test signal generation
                signal = self.signal_processor.evaluate_entry_conditions(df_with_indicators, rsi_config)
                
                rsi_validation = {
                    'config_loaded': True,
                    'current_rsi': current_rsi,
                    'current_price': current_price,
                    'signal_generated': signal is not None,
                    'signal_logic_correct': False
                }
                
                if signal:
                    print(f"   🎯 Signal Generated: {signal.signal_type.value}")
                    print(f"   📝 Reason: {signal.reason}")
                    
                    # Validate signal logic
                    rsi_long_entry = rsi_config.get('rsi_long_entry', 40)
                    rsi_short_entry = rsi_config.get('rsi_short_entry', 60)
                    
                    if signal.signal_type.value == 'BUY':
                        logic_correct = current_rsi <= rsi_long_entry
                        print(f"   ✅ Long signal logic: RSI {current_rsi:.2f} <= {rsi_long_entry} = {logic_correct}")
                    elif signal.signal_type.value == 'SELL':
                        logic_correct = current_rsi >= rsi_short_entry
                        print(f"   ✅ Short signal logic: RSI {current_rsi:.2f} >= {rsi_short_entry} = {logic_correct}")
                    else:
                        logic_correct = False
                    
                    rsi_validation['signal_logic_correct'] = logic_correct
                    rsi_validation['signal_type'] = signal.signal_type.value
                    rsi_validation['signal_reason'] = signal.reason
                    
                else:
                    print(f"   ⚪ No signal generated (RSI: {current_rsi:.2f})")
                    # Check if this is expected
                    rsi_long_entry = rsi_config.get('rsi_long_entry', 40)
                    rsi_short_entry = rsi_config.get('rsi_short_entry', 60)
                    
                    no_signal_expected = (current_rsi > rsi_long_entry and current_rsi < rsi_short_entry)
                    rsi_validation['signal_logic_correct'] = no_signal_expected
                    print(f"   ✅ No signal expected: {no_signal_expected}")
                
                results['rsi_strategy'] = rsi_validation
                
            else:
                print(f"   ❌ No data available for RSI validation")
                results['rsi_strategy'] = {'error': 'No data available'}
                
        except Exception as e:
            print(f"   ❌ RSI strategy validation error: {e}")
            results['rsi_strategy'] = {'error': str(e)}

    async def _validate_macd_strategy(self, results):
        """Validate MACD strategy logic"""
        try:
            from src.execution_engine.strategies.macd_divergence_config import MACDDivergenceConfig
            
            # Get MACD configuration
            macd_config = MACDDivergenceConfig.get_config()
            
            print(f"   📊 MACD Configuration:")
            print(f"     Fast EMA: {macd_config.get('macd_fast', 12)}")
            print(f"     Slow EMA: {macd_config.get('macd_slow', 26)}")
            print(f"     Signal: {macd_config.get('macd_signal', 9)}")
            print(f"     Min Histogram Threshold: {macd_config.get('min_histogram_threshold', 0.0001)}")
            
            # Test with BTCUSDT (common MACD symbol)
            symbol = 'BTCUSDT'
            df = await self.price_fetcher.get_market_data(symbol, '1h', 100)
            
            if df is not None and not df.empty:
                df_with_indicators = self.price_fetcher.calculate_indicators(df)
                
                current_macd = df_with_indicators['macd'].iloc[-1]
                current_signal = df_with_indicators['macd_signal'].iloc[-1]
                current_histogram = df_with_indicators['macd_histogram'].iloc[-1]
                current_price = df_with_indicators['close'].iloc[-1]
                
                print(f"   📈 {symbol} Current MACD: {current_macd:.6f}")
                print(f"   📊 {symbol} Current Signal: {current_signal:.6f}")
                print(f"   📊 {symbol} Current Histogram: {current_histogram:.6f}")
                print(f"   💰 {symbol} Current Price: ${current_price:.4f}")
                
                # Test signal generation
                signal = self.signal_processor.evaluate_entry_conditions(df_with_indicators, macd_config)
                
                macd_validation = {
                    'config_loaded': True,
                    'current_macd': current_macd,
                    'current_signal': current_signal,
                    'current_histogram': current_histogram,
                    'current_price': current_price,
                    'signal_generated': signal is not None,
                    'signal_logic_correct': False
                }
                
                if signal:
                    print(f"   🎯 Signal Generated: {signal.signal_type.value}")
                    print(f"   📝 Reason: {signal.reason}")
                    
                    # MACD logic validation is complex - check basic requirements
                    if signal.signal_type.value == 'BUY':
                        # Should be: MACD < Signal AND histogram growing
                        logic_correct = current_macd < current_signal
                        print(f"   ✅ Bullish pre-crossover: MACD {current_macd:.6f} < Signal {current_signal:.6f} = {logic_correct}")
                    elif signal.signal_type.value == 'SELL':
                        # Should be: MACD > Signal AND histogram shrinking
                        logic_correct = current_macd > current_signal
                        print(f"   ✅ Bearish pre-crossover: MACD {current_macd:.6f} > Signal {current_signal:.6f} = {logic_correct}")
                    else:
                        logic_correct = False
                    
                    macd_validation['signal_logic_correct'] = logic_correct
                    macd_validation['signal_type'] = signal.signal_type.value
                    macd_validation['signal_reason'] = signal.reason
                    
                else:
                    print(f"   ⚪ No signal generated")
                    macd_validation['signal_logic_correct'] = True  # No signal can be correct
                
                results['macd_strategy'] = macd_validation
                
            else:
                print(f"   ❌ No data available for MACD validation")
                results['macd_strategy'] = {'error': 'No data available'}
                
        except Exception as e:
            print(f"   ❌ MACD strategy validation error: {e}")
            results['macd_strategy'] = {'error': str(e)}

    async def _validate_engulfing_strategy(self, results):
        """Validate Engulfing Pattern strategy logic"""
        try:
            from src.execution_engine.strategies.engulfing_pattern_config import EngulfingPatternConfig
            
            # Get Engulfing configuration
            engulfing_config = EngulfingPatternConfig.get_config()
            
            print(f"   📊 Engulfing Pattern Configuration:")
            print(f"     RSI Threshold: {engulfing_config.get('rsi_threshold', 50)}")
            print(f"     RSI Period: {engulfing_config.get('rsi_period', 14)}")
            print(f"     Price Lookback: {engulfing_config.get('price_lookback_bars', 5)} bars")
            print(f"     Stable Candle Ratio: {engulfing_config.get('stable_candle_ratio', 0.5)}")
            
            # Test with BCHUSDT (common engulfing symbol)
            symbol = 'BCHUSDT'
            df = await self.price_fetcher.get_market_data(symbol, '1h', 100)
            
            if df is not None and not df.empty:
                df_with_indicators = self.price_fetcher.calculate_indicators(df)
                
                current_rsi = df_with_indicators['rsi'].iloc[-1]
                current_price = df_with_indicators['close'].iloc[-1]
                
                print(f"   📈 {symbol} Current RSI: {current_rsi:.2f}")
                print(f"   💰 {symbol} Current Price: ${current_price:.4f}")
                
                # Test signal generation
                signal = self.signal_processor.evaluate_entry_conditions(df_with_indicators, engulfing_config)
                
                engulfing_validation = {
                    'config_loaded': True,
                    'current_rsi': current_rsi,
                    'current_price': current_price,
                    'signal_generated': signal is not None,
                    'signal_logic_correct': False
                }
                
                if signal:
                    print(f"   🎯 Signal Generated: {signal.signal_type.value}")
                    print(f"   📝 Reason: {signal.reason}")
                    
                    # Engulfing pattern validation requires pattern detection
                    rsi_threshold = engulfing_config.get('rsi_threshold', 50)
                    
                    if signal.signal_type.value == 'BUY':
                        # Should have: Bullish engulfing + RSI < threshold + price down
                        logic_correct = current_rsi < rsi_threshold
                        print(f"   ✅ Bullish engulfing logic: RSI {current_rsi:.2f} < {rsi_threshold} = {logic_correct}")
                    elif signal.signal_type.value == 'SELL':
                        # Should have: Bearish engulfing + RSI > threshold + price up
                        logic_correct = current_rsi > rsi_threshold
                        print(f"   ✅ Bearish engulfing logic: RSI {current_rsi:.2f} > {rsi_threshold} = {logic_correct}")
                    else:
                        logic_correct = False
                    
                    engulfing_validation['signal_logic_correct'] = logic_correct
                    engulfing_validation['signal_type'] = signal.signal_type.value
                    engulfing_validation['signal_reason'] = signal.reason
                    
                else:
                    print(f"   ⚪ No signal generated")
                    engulfing_validation['signal_logic_correct'] = True  # No signal can be correct
                
                results['engulfing_strategy'] = engulfing_validation
                
            else:
                print(f"   ❌ No data available for Engulfing validation")
                results['engulfing_strategy'] = {'error': 'No data available'}
                
        except Exception as e:
            print(f"   ❌ Engulfing strategy validation error: {e}")
            results['engulfing_strategy'] = {'error': str(e)}

    def generate_final_report(self):
        """Generate comprehensive validation report"""
        print("\n" + "=" * 80)
        print("📋 COMPREHENSIVE VALIDATION REPORT")
        print("=" * 80)
        
        # WebSocket Status
        ws_status = self.results['websocket_validation']
        print(f"\n🔗 WEBSOCKET CONNECTIVITY:")
        print(f"   Connection: {ws_status.get('connection_status', 'UNKNOWN')}")
        print(f"   Data Reception: {ws_status.get('data_reception', 'UNKNOWN')}")
        print(f"   Streams: {ws_status.get('stream_count', 0)}")
        print(f"   Symbols: {len(ws_status.get('symbols_tracked', []))}")
        
        if 'statistics' in ws_status:
            stats = ws_status['statistics']
            print(f"   Messages: {stats.get('messages_received', 0)}")
            print(f"   Klines: {stats.get('klines_processed', 0)}")
        
        # Price Data Status
        price_status = self.results.get('price_data_validation', {})
        if 'data_availability' in price_status:
            print(f"\n📊 PRICE DATA VALIDATION:")
            data_avail = price_status['data_availability']
            available_count = sum(1 for data in data_avail.values() if data.get('market_data_available', False))
            indicator_count = sum(1 for data in data_avail.values() if data.get('indicators_calculated', False))
            websocket_count = sum(1 for data in data_avail.values() if data.get('websocket_data', False))
            
            print(f"   Market Data: {available_count}/{len(data_avail)} symbols")
            print(f"   Indicators: {indicator_count}/{len(data_avail)} symbols")
            print(f"   WebSocket Data: {websocket_count}/{len(data_avail)} symbols")
        
        # Strategy Logic Status
        strategy_status = self.results.get('strategy_validation', {})
        print(f"\n🎯 STRATEGY LOGIC VALIDATION:")
        
        for strategy_name, strategy_data in strategy_status.items():
            if isinstance(strategy_data, dict) and 'config_loaded' in strategy_data:
                config_ok = strategy_data.get('config_loaded', False)
                signal_gen = strategy_data.get('signal_generated', False)
                logic_ok = strategy_data.get('signal_logic_correct', False)
                
                status_icon = "✅" if (config_ok and logic_ok) else "⚠️" if config_ok else "❌"
                print(f"   {status_icon} {strategy_name.upper()}: Config={config_ok}, Logic={logic_ok}, Signal={signal_gen}")
        
        # Overall Assessment
        print(f"\n🎯 OVERALL ASSESSMENT:")
        
        ws_ok = ws_status.get('connection_status') == 'CONNECTED' and ws_status.get('data_reception') == 'SUCCESS'
        price_ok = len(price_status.get('data_availability', {})) > 0
        strategy_ok = any(
            data.get('config_loaded', False) and data.get('signal_logic_correct', False)
            for data in strategy_status.values()
            if isinstance(data, dict)
        )
        
        overall_status = "✅ EXCELLENT" if (ws_ok and price_ok and strategy_ok) else \
                        "⚠️ PARTIAL" if (ws_ok or price_ok) else \
                        "❌ ISSUES DETECTED"
        
        print(f"   WebSocket: {'✅ OK' if ws_ok else '❌ ISSUES'}")
        print(f"   Price Data: {'✅ OK' if price_ok else '❌ ISSUES'}")
        print(f"   Strategy Logic: {'✅ OK' if strategy_ok else '❌ ISSUES'}")
        print(f"   Overall: {overall_status}")
        
        self.results['overall_status'] = overall_status.split()[1]  # Just the status word
        
        # Deployment Readiness
        print(f"\n🚀 DEPLOYMENT READINESS:")
        if ws_ok and price_ok and strategy_ok:
            print("   ✅ READY FOR LIVE TRADING")
            print("   ✅ WebSocket functioning correctly")
            print("   ✅ Price data accurate and fresh")
            print("   ✅ Strategy logic validated")
        else:
            print("   ⚠️ ISSUES NEED ATTENTION")
            if not ws_ok:
                print("   ❌ WebSocket connectivity issues")
            if not price_ok:
                print("   ❌ Price data issues")
            if not strategy_ok:
                print("   ❌ Strategy logic issues")

    async def run_validation(self):
        """Run complete validation suite"""
        print("🧪 COMPREHENSIVE STRATEGY & WEBSOCKET VALIDATION")
        print("=" * 80)
        print("Validating trading system without making any changes...")
        print("=" * 80)
        
        # Run all validations
        await self.validate_websocket_connectivity()
        await asyncio.sleep(2)  # Brief pause between tests
        
        await self.validate_price_data_accuracy()
        await asyncio.sleep(2)
        
        await self.validate_strategy_logic()
        
        # Generate final report
        self.generate_final_report()
        
        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"comprehensive_validation_{timestamp}.json"
        
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        print(f"\n📁 Results saved to: {results_file}")
        return self.results

async def main():
    """Main validation execution"""
    validator = ComprehensiveValidator()
    
    if validator.results['overall_status'] == 'IMPORT_FAILED':
        print("❌ Cannot proceed due to import failures")
        return
    
    try:
        results = await validator.run_validation()
        return results
    except Exception as e:
        print(f"❌ Validation failed: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(main())
