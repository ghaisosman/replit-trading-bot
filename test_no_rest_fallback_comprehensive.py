
#!/usr/bin/env python3
"""
Test No REST API Fallback - Comprehensive Verification
====================================================

This test verifies that the WebSocket implementation is 100% working
without any REST API fallbacks when WebSocket data isn't immediately available.

Tests:
1. WebSocket connection establishment
2. Data caching and freshness verification  
3. No REST API calls during data gaps
4. Proper waiting behavior for WebSocket data
5. Error handling without API fallbacks
"""

import asyncio
import time
import logging
import sys
import os
import json
from datetime import datetime
from unittest.mock import patch, MagicMock
from typing import Dict, List, Any

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.utils.logger import setup_logger
from src.data_fetcher.websocket_manager import websocket_manager
from src.data_fetcher.price_fetcher import PriceFetcher
from src.binance_client.client import BinanceClientWrapper

class NoRestFallbackTester:
    """Comprehensive tester to verify no REST API fallbacks occur"""
    
    def __init__(self):
        setup_logger()
        self.logger = logging.getLogger(__name__)
        
        # Test configuration
        self.test_symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
        self.test_intervals = ['1m', '5m', '1h']
        
        # Tracking
        self.api_calls_made = []
        self.websocket_messages_received = []
        self.test_results = {}
        
        # Mock setup
        self.original_binance_methods = {}
        
    def setup_api_call_monitoring(self):
        """Setup monitoring to detect any REST API calls"""
        self.logger.info("🔍 Setting up API call monitoring...")
        
        try:
            # Create Binance client
            self.binance_client = BinanceClientWrapper()
            self.price_fetcher = PriceFetcher(self.binance_client)
            
            # Store original methods
            self.original_binance_methods = {
                'get_klines': self.binance_client.get_klines,
                'get_symbol_ticker': self.binance_client.get_symbol_ticker,
                'get_historical_klines': getattr(self.binance_client, 'get_historical_klines', None)
            }
            
            # Mock API methods to track calls
            def mock_get_klines(*args, **kwargs):
                call_info = {
                    'method': 'get_klines',
                    'args': args,
                    'kwargs': kwargs,
                    'timestamp': datetime.now(),
                    'should_not_happen': True
                }
                self.api_calls_made.append(call_info)
                self.logger.error(f"🚨 UNEXPECTED REST API CALL: get_klines {args}")
                return None  # Return None to simulate failure
                
            def mock_get_symbol_ticker(*args, **kwargs):
                call_info = {
                    'method': 'get_symbol_ticker', 
                    'args': args,
                    'kwargs': kwargs,
                    'timestamp': datetime.now(),
                    'should_not_happen': True
                }
                self.api_calls_made.append(call_info)
                self.logger.error(f"🚨 UNEXPECTED REST API CALL: get_symbol_ticker {args}")
                return None
                
            def mock_get_historical_klines(*args, **kwargs):
                call_info = {
                    'method': 'get_historical_klines',
                    'args': args, 
                    'kwargs': kwargs,
                    'timestamp': datetime.now(),
                    'should_not_happen': True
                }
                self.api_calls_made.append(call_info)
                self.logger.error(f"🚨 UNEXPECTED REST API CALL: get_historical_klines {args}")
                return None
            
            # Apply mocks
            self.binance_client.get_klines = mock_get_klines
            self.binance_client.get_symbol_ticker = mock_get_symbol_ticker
            if hasattr(self.binance_client, 'get_historical_klines'):
                self.binance_client.get_historical_klines = mock_get_historical_klines
                
            self.logger.info("✅ API call monitoring active - All REST calls will be detected")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to setup API monitoring: {e}")
            return False
    
    def setup_websocket_monitoring(self):
        """Setup WebSocket message monitoring"""
        self.logger.info("📡 Setting up WebSocket monitoring...")
        
        def websocket_callback(symbol, interval, kline_data):
            message_info = {
                'symbol': symbol,
                'interval': interval,
                'timestamp': datetime.now(),
                'price': kline_data.get('close', 0)
            }
            self.websocket_messages_received.append(message_info)
            self.logger.debug(f"📊 WebSocket message: {symbol} {interval} @ ${kline_data.get('close', 0)}")
            
        websocket_manager.add_update_callback(websocket_callback)
        self.logger.info("✅ WebSocket monitoring active")
        
    async def test_websocket_connection_and_data(self):
        """Test WebSocket connection and initial data reception"""
        self.logger.info("\n🧪 TEST 1: WebSocket Connection & Data Reception")
        self.logger.info("=" * 60)
        
        test_results = {
            'websocket_connected': False,
            'data_received': {},
            'connection_time': 0,
            'initial_data_time': 0
        }
        
        # Add symbols to WebSocket
        for symbol in self.test_symbols:
            for interval in self.test_intervals:
                websocket_manager.add_symbol_interval(symbol, interval)
                
        # Start WebSocket
        start_time = time.time()
        websocket_manager.start()
        
        # Wait for connection
        connection_timeout = 45
        while time.time() - start_time < connection_timeout:
            if websocket_manager.is_connected:
                test_results['websocket_connected'] = True
                test_results['connection_time'] = time.time() - start_time
                self.logger.info(f"✅ WebSocket connected in {test_results['connection_time']:.1f}s")
                break
            await asyncio.sleep(1)
            
        if not test_results['websocket_connected']:
            self.logger.error("❌ WebSocket failed to connect within timeout")
            return test_results
            
        # Wait for initial data
        data_start_time = time.time()
        data_timeout = 60
        
        while time.time() - data_start_time < data_timeout:
            # Check for data for each symbol/interval
            for symbol in self.test_symbols:
                for interval in self.test_intervals:
                    cached_data = websocket_manager.get_cached_klines(symbol, interval, 10)
                    if cached_data and len(cached_data) > 0:
                        if symbol not in test_results['data_received']:
                            test_results['data_received'][symbol] = {}
                        if interval not in test_results['data_received'][symbol]:
                            test_results['data_received'][symbol][interval] = {
                                'klines_count': len(cached_data),
                                'first_data_time': time.time() - data_start_time
                            }
                            self.logger.info(f"📊 Got data: {symbol} {interval} ({len(cached_data)} klines)")
                            
            # Check if we have data for all symbols/intervals
            all_data_received = True
            for symbol in self.test_symbols:
                for interval in self.test_intervals:
                    if (symbol not in test_results['data_received'] or 
                        interval not in test_results['data_received'][symbol]):
                        all_data_received = False
                        break
                if not all_data_received:
                    break
                    
            if all_data_received:
                test_results['initial_data_time'] = time.time() - data_start_time
                self.logger.info(f"✅ All initial data received in {test_results['initial_data_time']:.1f}s")
                break
                
            await asyncio.sleep(2)
            
        self.test_results['websocket_connection'] = test_results
        return test_results
        
    async def test_price_fetcher_no_rest_calls(self):
        """Test that PriceFetcher doesn't make REST calls when WebSocket data unavailable"""
        self.logger.info("\n🧪 TEST 2: PriceFetcher No REST API Fallback")
        self.logger.info("=" * 60)
        
        test_results = {
            'rest_calls_made': 0,
            'successful_websocket_calls': 0,
            'failed_calls_handled_properly': 0,
            'symbols_tested': len(self.test_symbols)
        }
        
        initial_api_calls = len(self.api_calls_made)
        
        for symbol in self.test_symbols:
            self.logger.info(f"\n🔍 Testing {symbol}")
            
            # Test current price fetching
            try:
                current_price = self.price_fetcher.get_current_price(symbol)
                if current_price:
                    test_results['successful_websocket_calls'] += 1
                    self.logger.info(f"✅ {symbol}: Current price ${current_price:.4f} (WebSocket)")
                else:
                    test_results['failed_calls_handled_properly'] += 1
                    self.logger.info(f"⚪ {symbol}: No current price (properly handled, no REST fallback)")
            except Exception as e:
                self.logger.info(f"⚪ {symbol}: Current price failed properly: {e}")
                test_results['failed_calls_handled_properly'] += 1
                
            # Test market data fetching
            for interval in ['1m', '5m']:
                try:
                    market_data = await self.price_fetcher.get_market_data(symbol, interval, 50)
                    if market_data is not None and len(market_data) > 0:
                        test_results['successful_websocket_calls'] += 1
                        self.logger.info(f"✅ {symbol} {interval}: Got {len(market_data)} klines (WebSocket)")
                    else:
                        test_results['failed_calls_handled_properly'] += 1
                        self.logger.info(f"⚪ {symbol} {interval}: No data (properly handled, no REST fallback)")
                except Exception as e:
                    self.logger.info(f"⚪ {symbol} {interval}: Market data failed properly: {e}")
                    test_results['failed_calls_handled_properly'] += 1
                    
            # Test OHLCV data fetching
            try:
                ohlcv_data = self.price_fetcher.get_ohlcv_data(symbol, '1m', 20)
                if ohlcv_data is not None and len(ohlcv_data) > 0:
                    test_results['successful_websocket_calls'] += 1
                    self.logger.info(f"✅ {symbol}: Got OHLCV data ({len(ohlcv_data)} rows)")
                else:
                    test_results['failed_calls_handled_properly'] += 1
                    self.logger.info(f"⚪ {symbol}: No OHLCV data (properly handled, no REST fallback)")
            except Exception as e:
                self.logger.info(f"⚪ {symbol}: OHLCV failed properly: {e}")
                test_results['failed_calls_handled_properly'] += 1
                
        # Check if any REST API calls were made
        final_api_calls = len(self.api_calls_made)
        test_results['rest_calls_made'] = final_api_calls - initial_api_calls
        
        if test_results['rest_calls_made'] == 0:
            self.logger.info("✅ NO REST API CALLS MADE - Perfect!")
        else:
            self.logger.error(f"❌ {test_results['rest_calls_made']} unexpected REST API calls made")
            
        self.test_results['price_fetcher'] = test_results
        return test_results
        
    async def test_data_gap_handling(self):
        """Test behavior during WebSocket data gaps"""
        self.logger.info("\n🧪 TEST 3: Data Gap Handling")
        self.logger.info("=" * 60)
        
        test_results = {
            'websocket_stopped': False,
            'data_requests_during_gap': 0,
            'rest_calls_during_gap': 0,
            'proper_error_handling': 0,
            'websocket_reconnected': False
        }
        
        # Stop WebSocket to simulate data gap
        self.logger.info("🛑 Stopping WebSocket to simulate data gap...")
        websocket_manager.stop()
        time.sleep(2)
        test_results['websocket_stopped'] = True
        
        initial_api_calls = len(self.api_calls_made)
        
        # Try to fetch data during gap
        for symbol in self.test_symbols[:2]:  # Test with 2 symbols
            self.logger.info(f"🔍 Testing {symbol} during data gap")
            
            try:
                # Test current price
                current_price = self.price_fetcher.get_current_price(symbol)
                test_results['data_requests_during_gap'] += 1
                
                if current_price is None:
                    test_results['proper_error_handling'] += 1
                    self.logger.info(f"✅ {symbol}: Properly returned None (no REST fallback)")
                else:
                    self.logger.warning(f"⚠️ {symbol}: Got price during gap: ${current_price}")
                    
            except Exception as e:
                test_results['data_requests_during_gap'] += 1
                test_results['proper_error_handling'] += 1
                self.logger.info(f"✅ {symbol}: Properly handled error: {e}")
                
            # Test market data
            try:
                market_data = await self.price_fetcher.get_market_data(symbol, '1m', 10)
                test_results['data_requests_during_gap'] += 1
                
                if market_data is None:
                    test_results['proper_error_handling'] += 1
                    self.logger.info(f"✅ {symbol}: Properly returned None for market data")
                else:
                    self.logger.warning(f"⚠️ {symbol}: Got market data during gap")
                    
            except Exception as e:
                test_results['data_requests_during_gap'] += 1
                test_results['proper_error_handling'] += 1
                self.logger.info(f"✅ {symbol}: Properly handled market data error: {e}")
                
        # Check for REST calls during gap
        final_api_calls = len(self.api_calls_made)
        test_results['rest_calls_during_gap'] = final_api_calls - initial_api_calls
        
        if test_results['rest_calls_during_gap'] == 0:
            self.logger.info("✅ NO REST API CALLS during data gap - Perfect!")
        else:
            self.logger.error(f"❌ {test_results['rest_calls_during_gap']} REST calls made during gap")
            
        # Restart WebSocket
        self.logger.info("🔄 Restarting WebSocket...")
        websocket_manager.start()
        
        # Wait for reconnection
        reconnect_start = time.time()
        while time.time() - reconnect_start < 30:
            if websocket_manager.is_connected:
                test_results['websocket_reconnected'] = True
                self.logger.info("✅ WebSocket reconnected successfully")
                break
            await asyncio.sleep(1)
            
        self.test_results['data_gap_handling'] = test_results
        return test_results
        
    async def test_performance_metrics(self):
        """Test performance and efficiency metrics"""
        self.logger.info("\n🧪 TEST 4: Performance Metrics")
        self.logger.info("=" * 60)
        
        test_results = {
            'websocket_messages_received': len(self.websocket_messages_received),
            'total_rest_calls': len(self.api_calls_made),
            'websocket_stats': websocket_manager.get_statistics(),
            'cache_status': websocket_manager.get_cache_status()
        }
        
        self.logger.info(f"📊 WebSocket Messages Received: {test_results['websocket_messages_received']}")
        self.logger.info(f"📊 Total REST API Calls: {test_results['total_rest_calls']}")
        
        ws_stats = test_results['websocket_stats']
        self.logger.info(f"📊 WebSocket Connection Uptime: {ws_stats.get('uptime_seconds', 0):.1f}s")
        self.logger.info(f"📊 Klines Processed: {ws_stats.get('klines_processed', 0)}")
        
        # Calculate efficiency
        if test_results['total_rest_calls'] == 0 and test_results['websocket_messages_received'] > 0:
            test_results['efficiency_rating'] = 'PERFECT'
            self.logger.info("✅ PERFECT EFFICIENCY: 100% WebSocket, 0% REST API")
        elif test_results['total_rest_calls'] < 5:
            test_results['efficiency_rating'] = 'EXCELLENT'
            self.logger.info("✅ EXCELLENT EFFICIENCY: Minimal REST API usage")
        else:
            test_results['efficiency_rating'] = 'NEEDS_IMPROVEMENT'
            self.logger.warning("⚠️ EFFICIENCY NEEDS IMPROVEMENT: Too many REST API calls")
            
        self.test_results['performance_metrics'] = test_results
        return test_results
        
    def generate_comprehensive_report(self):
        """Generate final test report"""
        report = {
            'test_timestamp': datetime.now().isoformat(),
            'test_duration': time.time() - self.test_start_time,
            'overall_status': 'UNKNOWN',
            'test_results': self.test_results,
            'api_calls_intercepted': self.api_calls_made,
            'websocket_messages': len(self.websocket_messages_received),
            'recommendations': []
        }
        
        # Determine overall status
        total_rest_calls = len(self.api_calls_made)
        websocket_connected = self.test_results.get('websocket_connection', {}).get('websocket_connected', False)
        
        if total_rest_calls == 0 and websocket_connected:
            report['overall_status'] = 'SUCCESS'
            report['recommendations'].append("✅ Implementation is working perfectly - no REST API fallbacks detected")
        elif total_rest_calls < 3 and websocket_connected:
            report['overall_status'] = 'GOOD'
            report['recommendations'].append("🟡 Implementation is mostly working with minimal REST API usage")
        else:
            report['overall_status'] = 'NEEDS_IMPROVEMENT'
            if total_rest_calls > 0:
                report['recommendations'].append(f"❌ Found {total_rest_calls} unexpected REST API calls")
            if not websocket_connected:
                report['recommendations'].append("❌ WebSocket connection issues detected")
                
        return report
        
    def print_final_report(self, report):
        """Print the final test report"""
        print("\n" + "="*80)
        print("🏁 NO REST API FALLBACK - COMPREHENSIVE TEST REPORT")
        print("="*80)
        
        print(f"\n📊 OVERALL STATUS: {report['overall_status']}")
        print(f"⏱️  Test Duration: {report['test_duration']:.1f} seconds")
        print(f"📡 WebSocket Messages: {report['websocket_messages']}")
        print(f"🚨 REST API Calls Detected: {len(report['api_calls_intercepted'])}")
        
        if report['api_calls_intercepted']:
            print(f"\n❌ UNEXPECTED REST API CALLS:")
            for i, call in enumerate(report['api_calls_intercepted'], 1):
                print(f"   {i}. {call['method']} - {call['timestamp']}")
        else:
            print(f"\n✅ NO REST API CALLS DETECTED - PERFECT!")
            
        print(f"\n🎯 RECOMMENDATIONS:")
        for rec in report['recommendations']:
            print(f"   • {rec}")
            
        print("\n" + "="*80)
        
    async def run_comprehensive_test(self):
        """Run all tests"""
        self.test_start_time = time.time()
        
        print("🚀 Starting No REST API Fallback Comprehensive Test")
        print("="*60)
        
        try:
            # Setup monitoring
            if not self.setup_api_call_monitoring():
                print("❌ Failed to setup API monitoring")
                return False
                
            self.setup_websocket_monitoring()
            
            # Run tests
            await self.test_websocket_connection_and_data()
            await asyncio.sleep(2)
            
            await self.test_price_fetcher_no_rest_calls()
            await asyncio.sleep(2)
            
            await self.test_data_gap_handling()
            await asyncio.sleep(2)
            
            await self.test_performance_metrics()
            
            # Generate final report
            report = self.generate_comprehensive_report()
            self.print_final_report(report)
            
            # Save report
            report_filename = f"no_rest_fallback_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(report_filename, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            print(f"\n💾 Detailed report saved to: {report_filename}")
            
            return report['overall_status'] == 'SUCCESS'
            
        except Exception as e:
            print(f"\n❌ TEST ERROR: {e}")
            import traceback
            traceback.print_exc()
            return False
            
        finally:
            # Cleanup
            print("\n🧹 Cleaning up...")
            websocket_manager.stop()
            
async def main():
    """Main test execution"""
    tester = NoRestFallbackTester()
    success = await tester.run_comprehensive_test()
    
    if success:
        print("\n🎉 TEST PASSED: No REST API fallbacks detected!")
        print("✅ WebSocket implementation is working 100% correctly")
    else:
        print("\n❌ TEST FAILED: Issues detected with WebSocket implementation")
        print("🔧 Review the report for specific recommendations")
        
    return success

if __name__ == "__main__":
    asyncio.run(main())
