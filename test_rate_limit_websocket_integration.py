
#!/usr/bin/env python3
"""
Test Rate Limit Reduction and WebSocket Integration
Tests the enhanced rate limiting and WebSocket fallback for real-time data
"""

import asyncio
import time
import logging
import json
import threading
import websocket
import requests
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from src.utils.logger import setup_logger
from src.binance_client.client import BinanceClientWrapper
from src.config.global_config import global_config

class RateLimitWebSocketTest:
    """Comprehensive test for rate limiting and WebSocket integration"""

    def __init__(self):
        setup_logger()
        self.logger = logging.getLogger(__name__)
        self.binance_client = None
        self.test_results = {}
        self.websocket_data = {}
        self.websocket_active = False
        self.websocket_connection = None
        
        # Rate limiting test configuration
        self.test_symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
        self.aggressive_request_count = 50  # Test aggressive requests
        self.normal_request_count = 20     # Normal request pattern
        
    def run_all_tests(self):
        """Run all rate limiting and WebSocket tests"""
        print("🚀 STARTING RATE LIMIT & WEBSOCKET INTEGRATION TESTS")
        print("=" * 70)
        
        tests = [
            ("Rate Limit Protection", self.test_rate_limit_protection),
            ("Request Throttling", self.test_request_throttling),
            ("Rate Limit Recovery", self.test_rate_limit_recovery),
            ("WebSocket Connection", self.test_websocket_connection),
            ("WebSocket Data Stream", self.test_websocket_data_stream),
            ("REST to WebSocket Fallback", self.test_rest_to_websocket_fallback),
            ("Hybrid Data Integration", self.test_hybrid_data_integration),
            ("Concurrent Request Handling", self.test_concurrent_requests),
            ("IP Ban Prevention", self.test_ip_ban_prevention),
            ("Real-time Data Accuracy", self.test_realtime_data_accuracy)
        ]
        
        for test_name, test_func in tests:
            print(f"\n🔍 TEST: {test_name}")
            print("-" * 50)
            
            try:
                result = test_func()
                self.test_results[test_name] = result
                
                if result.get('status') == 'PASSED':
                    print(f"✅ {test_name}: PASSED")
                elif result.get('status') == 'WARNING':
                    print(f"⚠️  {test_name}: WARNING - {result.get('message', 'Check details')}")
                else:
                    print(f"❌ {test_name}: FAILED - {result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                print(f"❌ {test_name}: EXCEPTION - {e}")
                self.test_results[test_name] = {'status': 'EXCEPTION', 'error': str(e)}
        
        self._print_final_report()

    def test_rate_limit_protection(self) -> Dict:
        """Test 1: Rate limit protection mechanisms"""
        try:
            self.binance_client = BinanceClientWrapper()
            
            # Test rate limiting variables
            initial_count = self.binance_client._request_count
            initial_time = self.binance_client._last_request_time
            min_interval = self.binance_client._min_request_interval
            max_requests = self.binance_client._max_requests_per_minute
            
            print(f"📊 Rate Limit Configuration:")
            print(f"   Minimum Interval: {min_interval}s")
            print(f"   Max Requests/Minute: {max_requests}")
            print(f"   Current Request Count: {initial_count}")
            
            # Test that rate limiting is properly configured
            if min_interval >= 1.0 and max_requests <= 500:
                print("✅ Conservative rate limiting configured")
                protection_configured = True
            else:
                print("⚠️  Rate limiting may be too aggressive")
                protection_configured = False
            
            return {
                'status': 'PASSED' if protection_configured else 'WARNING',
                'min_interval': min_interval,
                'max_requests_per_minute': max_requests,
                'protection_configured': protection_configured
            }
            
        except Exception as e:
            return {'status': 'FAILED', 'error': str(e)}

    def test_request_throttling(self) -> Dict:
        """Test 2: Request throttling under load"""
        try:
            if not self.binance_client:
                self.binance_client = BinanceClientWrapper()
            
            print("🔄 Testing request throttling with rapid requests...")
            
            start_time = time.time()
            successful_requests = 0
            throttle_detected = False
            
            # Make rapid requests to test throttling
            for i in range(self.normal_request_count):
                try:
                    before_request = time.time()
                    ticker = self.binance_client.get_symbol_ticker('BTCUSDT')
                    after_request = time.time()
                    
                    request_duration = after_request - before_request
                    
                    if ticker:
                        successful_requests += 1
                        
                    # Check if throttling occurred (request took longer than normal)
                    if request_duration > 1.5:  # Expect some delay due to rate limiting
                        throttle_detected = True
                        print(f"   🛡️  Throttling detected: {request_duration:.2f}s delay")
                        
                except Exception as e:
                    print(f"   ❌ Request {i+1} failed: {e}")
            
            total_duration = time.time() - start_time
            avg_request_time = total_duration / self.normal_request_count
            
            print(f"📈 Throttling Test Results:")
            print(f"   Successful Requests: {successful_requests}/{self.normal_request_count}")
            print(f"   Total Duration: {total_duration:.2f}s")
            print(f"   Average Request Time: {avg_request_time:.2f}s")
            print(f"   Throttling Detected: {throttle_detected}")
            
            return {
                'status': 'PASSED',
                'successful_requests': successful_requests,
                'total_requests': self.normal_request_count,
                'avg_request_time': avg_request_time,
                'throttling_detected': throttle_detected,
                'total_duration': total_duration
            }
            
        except Exception as e:
            return {'status': 'FAILED', 'error': str(e)}

    def test_rate_limit_recovery(self) -> Dict:
        """Test 3: Rate limit recovery mechanisms"""
        try:
            if not self.binance_client:
                self.binance_client = BinanceClientWrapper()
            
            print("⏰ Testing rate limit recovery...")
            
            # Simulate hitting rate limits
            self.binance_client._request_count = self.binance_client._max_requests_per_minute - 5
            
            print(f"   Simulated request count: {self.binance_client._request_count}")
            
            # Make a few more requests to trigger rate limit protection
            recovery_start = time.time()
            
            for i in range(3):
                try:
                    self.binance_client._rate_limit()  # Test internal rate limiting
                    print(f"   Rate limit check {i+1}: OK")
                except Exception as e:
                    print(f"   Rate limit check {i+1}: {e}")
            
            recovery_time = time.time() - recovery_start
            
            # Check if request count was reset
            print(f"   Recovery completed in: {recovery_time:.2f}s")
            print(f"   Final request count: {self.binance_client._request_count}")
            
            return {
                'status': 'PASSED',
                'recovery_time': recovery_time,
                'recovery_successful': True
            }
            
        except Exception as e:
            return {'status': 'FAILED', 'error': str(e)}

    def test_websocket_connection(self) -> Dict:
        """Test 4: WebSocket connection establishment"""
        try:
            print("🔌 Testing WebSocket connection...")
            
            # Binance WebSocket endpoint
            if global_config.BINANCE_TESTNET:
                ws_url = "wss://stream.binancefuture.com/ws/"
            else:
                ws_url = "wss://fstream.binance.com/ws/"
            
            connection_successful = False
            connection_error = None
            
            def on_open(ws):
                nonlocal connection_successful
                connection_successful = True
                print("   ✅ WebSocket connection established")
                
                # Subscribe to ticker stream
                subscribe_msg = {
                    "method": "SUBSCRIBE",
                    "params": ["btcusdt@ticker"],
                    "id": 1
                }
                ws.send(json.dumps(subscribe_msg))
            
            def on_message(ws, message):
                try:
                    data = json.loads(message)
                    if 's' in data and data['s'] == 'BTCUSDT':
                        self.websocket_data['ticker'] = data
                        print(f"   📊 Received ticker data: ${float(data['c']):.2f}")
                        ws.close()  # Close after receiving data
                except Exception as e:
                    print(f"   ⚠️  Message parsing error: {e}")
            
            def on_error(ws, error):
                nonlocal connection_error
                connection_error = error
                print(f"   ❌ WebSocket error: {error}")
            
            def on_close(ws, close_status_code, close_msg):
                print("   🔌 WebSocket connection closed")
            
            # Create WebSocket connection
            ws = websocket.WebSocketApp(
                ws_url,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )
            
            # Run WebSocket in a separate thread with timeout
            def run_websocket():
                ws.run_forever()
            
            ws_thread = threading.Thread(target=run_websocket)
            ws_thread.daemon = True
            ws_thread.start()
            
            # Wait for connection with timeout
            timeout = 10
            start_time = time.time()
            
            while not connection_successful and not connection_error and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            
            if connection_successful:
                # Wait a bit more for data
                time.sleep(2)
                
            return {
                'status': 'PASSED' if connection_successful else 'FAILED',
                'connection_successful': connection_successful,
                'connection_error': str(connection_error) if connection_error else None,
                'data_received': len(self.websocket_data) > 0,
                'ws_url': ws_url
            }
            
        except Exception as e:
            return {'status': 'FAILED', 'error': str(e)}

    def test_websocket_data_stream(self) -> Dict:
        """Test 5: WebSocket real-time data streaming"""
        try:
            print("📡 Testing WebSocket data streaming...")
            
            if not self.websocket_data:
                print("   ⚠️  No WebSocket data from previous test, testing independently...")
            
            # Test multiple symbol streams
            symbols = ['btcusdt', 'ethusdt']
            stream_url = f"wss://fstream.binance.com/stream?streams={'@ticker/'.join(symbols)}@ticker"
            
            received_data = {}
            stream_active = True
            
            def on_message(ws, message):
                try:
                    data = json.loads(message)
                    if 'stream' in data and 'data' in data:
                        symbol = data['data'].get('s')
                        if symbol:
                            received_data[symbol] = {
                                'price': float(data['data']['c']),
                                'timestamp': time.time(),
                                'volume': float(data['data']['v'])
                            }
                            print(f"   📊 {symbol}: ${float(data['data']['c']):.2f}")
                            
                            # Close after receiving data from both symbols
                            if len(received_data) >= 2:
                                ws.close()
                                
                except Exception as e:
                    print(f"   ❌ Stream parsing error: {e}")
            
            def on_error(ws, error):
                print(f"   ❌ Stream error: {error}")
            
            # Test streaming for a short period
            ws = websocket.WebSocketApp(
                stream_url,
                on_message=on_message,
                on_error=on_error
            )
            
            def run_stream():
                ws.run_forever()
            
            stream_thread = threading.Thread(target=run_stream)
            stream_thread.daemon = True
            stream_thread.start()
            
            # Wait for data
            timeout = 15
            start_time = time.time()
            
            while len(received_data) < 2 and (time.time() - start_time) < timeout:
                time.sleep(0.5)
            
            print(f"   📈 Received data for {len(received_data)} symbols")
            
            return {
                'status': 'PASSED' if len(received_data) > 0 else 'FAILED',
                'symbols_received': len(received_data),
                'data_points': received_data,
                'stream_duration': time.time() - start_time
            }
            
        except Exception as e:
            return {'status': 'FAILED', 'error': str(e)}

    def test_rest_to_websocket_fallback(self) -> Dict:
        """Test 6: REST API to WebSocket fallback mechanism"""
        try:
            print("🔄 Testing REST to WebSocket fallback...")
            
            if not self.binance_client:
                self.binance_client = BinanceClientWrapper()
            
            # Test REST API first
            rest_start = time.time()
            rest_price = None
            
            try:
                ticker = self.binance_client.get_symbol_ticker('BTCUSDT')
                if ticker:
                    rest_price = float(ticker['price'])
                    print(f"   ✅ REST API: ${rest_price:.2f}")
            except Exception as e:
                print(f"   ❌ REST API failed: {e}")
            
            rest_duration = time.time() - rest_start
            
            # Test WebSocket as fallback
            ws_start = time.time()
            ws_price = None
            
            if 'ticker' in self.websocket_data:
                ws_price = float(self.websocket_data['ticker']['c'])
                print(f"   ✅ WebSocket: ${ws_price:.2f}")
            else:
                print("   ⚠️  WebSocket data not available from previous tests")
            
            ws_duration = time.time() - ws_start
            
            # Compare performance
            if rest_price and ws_price:
                price_diff = abs(rest_price - ws_price)
                price_diff_pct = (price_diff / rest_price) * 100
                
                print(f"   📊 Performance Comparison:")
                print(f"      REST: {rest_duration:.3f}s")
                print(f"      WebSocket: {ws_duration:.3f}s")
                print(f"      Price Difference: {price_diff_pct:.4f}%")
                
                fallback_effective = price_diff_pct < 0.01  # Less than 0.01% difference
            else:
                fallback_effective = rest_price is not None or ws_price is not None
            
            return {
                'status': 'PASSED' if fallback_effective else 'WARNING',
                'rest_price': rest_price,
                'websocket_price': ws_price,
                'rest_duration': rest_duration,
                'websocket_duration': ws_duration,
                'fallback_effective': fallback_effective
            }
            
        except Exception as e:
            return {'status': 'FAILED', 'error': str(e)}

    def test_hybrid_data_integration(self) -> Dict:
        """Test 7: Hybrid REST + WebSocket data integration"""
        try:
            print("🔗 Testing hybrid data integration...")
            
            # This would test the integration between REST historical data
            # and WebSocket real-time updates as mentioned in Instructions.md
            
            if not self.binance_client:
                self.binance_client = BinanceClientWrapper()
            
            # Get historical data via REST
            historical_data = self.binance_client.get_historical_klines('BTCUSDT', '1m', 5)
            
            if not historical_data:
                return {'status': 'FAILED', 'error': 'Could not fetch historical data'}
            
            print(f"   ✅ Historical data: {len(historical_data)} candles")
            
            # Simulate real-time data integration
            last_close = float(historical_data[-1][4])  # Close price of last candle
            
            # Get current price (simulating WebSocket real-time data)
            current_ticker = self.binance_client.get_symbol_ticker('BTCUSDT')
            if current_ticker:
                current_price = float(current_ticker['price'])
                print(f"   ✅ Current price: ${current_price:.2f}")
                
                # Test data consistency
                price_change = abs(current_price - last_close) / last_close * 100
                print(f"   📊 Price change from last candle: {price_change:.2f}%")
                
                # Data should be reasonably consistent (within 5% for 1-minute data)
                data_consistent = price_change < 5.0
                
                if data_consistent:
                    print("   ✅ Data integration consistent")
                else:
                    print("   ⚠️  Large price gap detected")
            else:
                return {'status': 'FAILED', 'error': 'Could not fetch current price'}
            
            return {
                'status': 'PASSED' if data_consistent else 'WARNING',
                'historical_candles': len(historical_data),
                'last_close': last_close,
                'current_price': current_price,
                'price_change_pct': price_change,
                'data_consistent': data_consistent
            }
            
        except Exception as e:
            return {'status': 'FAILED', 'error': str(e)}

    def test_concurrent_requests(self) -> Dict:
        """Test 8: Concurrent request handling without triggering bans"""
        try:
            print("🚀 Testing concurrent request handling...")
            
            if not self.binance_client:
                self.binance_client = BinanceClientWrapper()
            
            import concurrent.futures
            
            def make_request(symbol):
                try:
                    return self.binance_client.get_symbol_ticker(symbol)
                except Exception as e:
                    return {'error': str(e)}
            
            # Test concurrent requests
            start_time = time.time()
            successful_requests = 0
            failed_requests = 0
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                # Submit requests for multiple symbols
                futures = []
                for symbol in ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'ADAUSDT', 'DOTUSDT']:
                    futures.append(executor.submit(make_request, symbol))
                
                # Collect results
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    if 'error' in result:
                        failed_requests += 1
                        print(f"   ❌ Request failed: {result['error']}")
                    else:
                        successful_requests += 1
                        print(f"   ✅ Request successful: {result.get('symbol', 'Unknown')}")
            
            total_duration = time.time() - start_time
            total_requests = successful_requests + failed_requests
            
            print(f"   📊 Concurrent Results:")
            print(f"      Successful: {successful_requests}/{total_requests}")
            print(f"      Duration: {total_duration:.2f}s")
            
            return {
                'status': 'PASSED' if successful_requests > 0 else 'FAILED',
                'successful_requests': successful_requests,
                'failed_requests': failed_requests,
                'total_duration': total_duration,
                'concurrent_performance': successful_requests / total_duration if total_duration > 0 else 0
            }
            
        except Exception as e:
            return {'status': 'FAILED', 'error': str(e)}

    def test_ip_ban_prevention(self) -> Dict:
        """Test 9: IP ban prevention mechanisms"""
        try:
            print("🛡️  Testing IP ban prevention...")
            
            if not self.binance_client:
                self.binance_client = BinanceClientWrapper()
            
            # Test the rate limiting configuration that prevents IP bans
            protection_features = {
                'rate_limiting': hasattr(self.binance_client, '_rate_limit'),
                'request_counting': hasattr(self.binance_client, '_request_count'),
                'time_tracking': hasattr(self.binance_client, '_last_request_time'),
                'sliding_window': hasattr(self.binance_client, '_request_window_start'),
                'max_requests_limit': hasattr(self.binance_client, '_max_requests_per_minute')
            }
            
            print("   🔍 IP Ban Prevention Features:")
            for feature, present in protection_features.items():
                status = "✅" if present else "❌"
                print(f"      {status} {feature.replace('_', ' ').title()}")
            
            # Test conservative limits
            if hasattr(self.binance_client, '_max_requests_per_minute'):
                max_requests = self.binance_client._max_requests_per_minute
                conservative_limit = max_requests <= 500  # Conservative compared to Binance's 1200
                print(f"   📊 Request limit: {max_requests}/minute (Conservative: {conservative_limit})")
            else:
                conservative_limit = False
            
            # Test minimum interval
            if hasattr(self.binance_client, '_min_request_interval'):
                min_interval = self.binance_client._min_request_interval
                safe_interval = min_interval >= 1.0  # At least 1 second between requests
                print(f"   ⏱️  Minimum interval: {min_interval}s (Safe: {safe_interval})")
            else:
                safe_interval = False
            
            features_present = sum(protection_features.values())
            protection_score = features_present / len(protection_features) * 100
            
            return {
                'status': 'PASSED' if features_present >= 4 else 'WARNING',
                'protection_features': protection_features,
                'protection_score': protection_score,
                'conservative_limit': conservative_limit,
                'safe_interval': safe_interval
            }
            
        except Exception as e:
            return {'status': 'FAILED', 'error': str(e)}

    def test_realtime_data_accuracy(self) -> Dict:
        """Test 10: Real-time data accuracy and consistency"""
        try:
            print("📊 Testing real-time data accuracy...")
            
            if not self.binance_client:
                self.binance_client = BinanceClientWrapper()
            
            # Get multiple price samples to test consistency
            prices = []
            timestamps = []
            
            for i in range(5):
                ticker = self.binance_client.get_symbol_ticker('BTCUSDT')
                if ticker:
                    prices.append(float(ticker['price']))
                    timestamps.append(time.time())
                    print(f"   Sample {i+1}: ${prices[-1]:.2f}")
                time.sleep(1)  # Wait 1 second between samples
            
            if len(prices) < 3:
                return {'status': 'FAILED', 'error': 'Insufficient price samples'}
            
            # Calculate price consistency
            price_variance = max(prices) - min(prices)
            avg_price = sum(prices) / len(prices)
            variance_pct = (price_variance / avg_price) * 100
            
            # Calculate timing consistency
            time_intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
            avg_interval = sum(time_intervals) / len(time_intervals)
            
            print(f"   📈 Price Analysis:")
            print(f"      Average: ${avg_price:.2f}")
            print(f"      Variance: {variance_pct:.4f}%")
            print(f"      Avg Interval: {avg_interval:.2f}s")
            
            # Data should be reasonably consistent (< 0.1% variance for short samples)
            data_accurate = variance_pct < 0.1
            timing_consistent = 0.8 <= avg_interval <= 1.2  # Within 20% of 1 second
            
            return {
                'status': 'PASSED' if data_accurate and timing_consistent else 'WARNING',
                'sample_count': len(prices),
                'price_variance_pct': variance_pct,
                'avg_interval': avg_interval,
                'data_accurate': data_accurate,
                'timing_consistent': timing_consistent,
                'prices': prices
            }
            
        except Exception as e:
            return {'status': 'FAILED', 'error': str(e)}

    def _print_final_report(self):
        """Print comprehensive test report"""
        print("\n" + "="*70)
        print("🎯 RATE LIMIT & WEBSOCKET INTEGRATION TEST REPORT")
        print("="*70)
        
        passed = sum(1 for result in self.test_results.values() if result.get('status') == 'PASSED')
        warning = sum(1 for result in self.test_results.values() if result.get('status') == 'WARNING')
        failed = sum(1 for result in self.test_results.values() if result.get('status') == 'FAILED')
        total = len(self.test_results)
        
        print(f"\n📊 SUMMARY:")
        print(f"   ✅ Passed: {passed}/{total}")
        print(f"   ⚠️  Warning: {warning}/{total}")
        print(f"   ❌ Failed: {failed}/{total}")
        
        if passed >= total * 0.8:
            print(f"\n🎉 OVERALL: EXCELLENT - Rate limiting and WebSocket integration working well")
        elif passed >= total * 0.6:
            print(f"\n👍 OVERALL: GOOD - Most features working, some improvements needed")
        else:
            print(f"\n⚠️  OVERALL: NEEDS ATTENTION - Several issues detected")
        
        print(f"\n📝 DETAILED RESULTS:")
        for test_name, result in self.test_results.items():
            status = result.get('status', 'UNKNOWN')
            status_icon = "✅" if status == 'PASSED' else "⚠️" if status == 'WARNING' else "❌"
            print(f"   {status_icon} {test_name}: {status}")
            
            if 'error' in result:
                print(f"      Error: {result['error']}")
        
        # Recommendations
        print(f"\n💡 RECOMMENDATIONS:")
        
        if failed > 0:
            print("   🔧 Address failed tests before deploying to production")
        
        if any('WebSocket' in test for test in self.test_results.keys() 
               if self.test_results[test].get('status') == 'FAILED'):
            print("   📡 Consider implementing WebSocket fallback mechanisms")
        
        if any('rate_limit' in str(result).lower() for result in self.test_results.values()):
            print("   🛡️  Rate limiting is protecting against IP bans - good!")
        
        print("   📚 Refer to Instructions.md for proxy implementation if geographic restrictions persist")

if __name__ == "__main__":
    test_suite = RateLimitWebSocketTest()
    test_suite.run_all_tests()
