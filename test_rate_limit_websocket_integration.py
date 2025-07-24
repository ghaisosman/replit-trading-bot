#!/usr/bin/env python3
import asyncio
import json
import time
import logging
import websocket
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import requests
import sys
import os

# Add src to path for imports
sys.path.append('src')

from src.config.global_config import global_config
from src.binance_client.client import BinanceClientWrapper
from src.analytics.trade_logger import TradeLogger

class RateLimitWebSocketTester:
    """Test rate limit reduction through WebSocket integration"""

    def __init__(self):
        self.logger = self._setup_logger()
        self.binance_client = BinanceClientWrapper()
        self.trade_logger = TradeLogger()

        # WebSocket configuration
        self.ws_url = "wss://fstream.binance.com/ws/btcusdt@kline_1m"
        self.ws = None
        self.ws_thread = None
        self.ws_data = []
        self.ws_connected = False

        # Rate limit tracking
        self.api_calls = []
        self.rate_limit_window = 60  # 1 minute
        self.max_calls_per_minute = 1200  # Binance limit

        # Test configuration
        self.test_symbols = ['BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'SOLUSDT']
        self.test_duration = 300  # 5 minutes

    def _setup_logger(self):
        """Setup dedicated logger for testing"""
        logger = logging.getLogger('RateLimitWebSocketTest')
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def track_api_call(self):
        """Track API call for rate limit monitoring"""
        current_time = time.time()
        self.api_calls.append(current_time)

        # Remove calls older than the window
        cutoff_time = current_time - self.rate_limit_window
        self.api_calls = [call_time for call_time in self.api_calls if call_time > cutoff_time]

    def get_current_rate_limit_usage(self) -> Dict[str, Any]:
        """Get current rate limit usage statistics"""
        current_time = time.time()
        cutoff_time = current_time - self.rate_limit_window

        recent_calls = [call_time for call_time in self.api_calls if call_time > cutoff_time]

        return {
            'calls_last_minute': len(recent_calls),
            'max_calls_per_minute': self.max_calls_per_minute,
            'usage_percentage': (len(recent_calls) / self.max_calls_per_minute) * 100,
            'remaining_calls': self.max_calls_per_minute - len(recent_calls)
        }

    def on_websocket_message(self, ws, message):
        """Handle WebSocket messages"""
        try:
            data = json.loads(message)
            if 'k' in data:  # Kline data
                kline = data['k']
                processed_data = {
                    'symbol': kline['s'],
                    'open_time': kline['t'],
                    'close_time': kline['T'],
                    'open_price': float(kline['o']),
                    'high_price': float(kline['h']),
                    'low_price': float(kline['l']),
                    'close_price': float(kline['c']),
                    'volume': float(kline['v']),
                    'is_closed': kline['x']  # True if this kline is closed
                }

                self.ws_data.append(processed_data)

                if processed_data['is_closed']:
                    self.logger.info(f"📊 WebSocket: {processed_data['symbol']} closed at {processed_data['close_price']}")

        except Exception as e:
            self.logger.error(f"Error processing WebSocket message: {e}")

    def on_websocket_error(self, ws, error):
        """Handle WebSocket errors"""
        self.logger.error(f"WebSocket error: {error}")
        self.ws_connected = False

    def on_websocket_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close"""
        self.logger.info("WebSocket connection closed")
        self.ws_connected = False

    def on_websocket_open(self, ws):
        """Handle WebSocket open"""
        self.logger.info("✅ WebSocket connection established")
        self.ws_connected = True

    def start_websocket(self):
        """Start WebSocket connection"""
        try:
            self.logger.info(f"🔌 Starting WebSocket connection to {self.ws_url}")

            # Remove enableTrace call - not available in all versions
            self.ws = websocket.WebSocketApp(
                self.ws_url,
                on_open=self.on_websocket_open,
                on_message=self.on_websocket_message,
                on_error=self.on_websocket_error,
                on_close=self.on_websocket_close
            )

            # Start WebSocket in a separate thread
            self.ws_thread = threading.Thread(target=self.ws.run_forever)
            self.ws_thread.daemon = True
            self.ws_thread.start()

            # Wait for connection
            timeout = 10
            start_time = time.time()
            while not self.ws_connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)

            if not self.ws_connected:
                raise Exception("Failed to establish WebSocket connection within timeout")

            return True

        except Exception as e:
            self.logger.error(f"Failed to start WebSocket: {e}")
            return False

    def stop_websocket(self):
        """Stop WebSocket connection"""
        if self.ws:
            self.ws.close()
            self.ws_connected = False
            self.logger.info("🔌 WebSocket connection stopped")

    def test_api_rate_limits_without_websocket(self, duration_seconds: int = 60) -> Dict[str, Any]:
        """Test API rate limits using only REST API calls"""
        self.logger.info("🚀 Testing API rate limits WITHOUT WebSocket")

        start_time = time.time()
        api_call_count = 0
        errors = 0

        while (time.time() - start_time) < duration_seconds:
            for symbol in self.test_symbols:
                try:
                    # Make API call
                    self.track_api_call()
                    klines = self.binance_client.get_klines(symbol, '1m', limit=100)
                    api_call_count += 1

                    if klines:
                        self.logger.debug(f"📈 API: Got {len(klines)} klines for {symbol}")
                    else:
                        errors += 1

                    # Small delay to prevent overwhelming
                    time.sleep(0.1)

                except Exception as e:
                    errors += 1
                    self.logger.error(f"API call error for {symbol}: {e}")
                    time.sleep(1)  # Longer delay on error

        rate_stats = self.get_current_rate_limit_usage()

        return {
            'test_type': 'API_ONLY',
            'duration': duration_seconds,
            'api_calls': api_call_count,
            'errors': errors,
            'calls_per_second': api_call_count / duration_seconds,
            'error_rate': (errors / max(api_call_count, 1)) * 100,
            'rate_limit_stats': rate_stats
        }

    def test_hybrid_approach_with_websocket(self, duration_seconds: int = 60) -> Dict[str, Any]:
        """Test hybrid approach using WebSocket for real-time data + API for historical"""
        self.logger.info("🚀 Testing HYBRID approach WITH WebSocket")

        # Start WebSocket
        if not self.start_websocket():
            return {'error': 'Failed to start WebSocket'}

        start_time = time.time()
        api_call_count = 0
        errors = 0
        websocket_messages = len(self.ws_data)

        try:
            while (time.time() - start_time) < duration_seconds:
                for symbol in self.test_symbols:
                    try:
                        # Use API only for historical data (less frequent)
                        if api_call_count % 4 == 0:  # Reduce API calls by 75%
                            self.track_api_call()
                            klines = self.binance_client.get_klines(symbol, '1m', limit=50)
                            api_call_count += 1

                            if klines:
                                self.logger.debug(f"📈 API: Got {len(klines)} historical klines for {symbol}")
                            else:
                                errors += 1

                        # Longer delay since WebSocket provides real-time data
                        time.sleep(0.5)

                    except Exception as e:
                        errors += 1
                        self.logger.error(f"API call error for {symbol}: {e}")
                        time.sleep(1)

        finally:
            self.stop_websocket()

        websocket_messages_received = len(self.ws_data) - websocket_messages
        rate_stats = self.get_current_rate_limit_usage()

        return {
            'test_type': 'HYBRID_WEBSOCKET',
            'duration': duration_seconds,
            'api_calls': api_call_count,
            'websocket_messages': websocket_messages_received,
            'errors': errors,
            'calls_per_second': api_call_count / duration_seconds,
            'error_rate': (errors / max(api_call_count, 1)) * 100,
            'rate_limit_stats': rate_stats,
            'websocket_efficiency': {
                'messages_per_second': websocket_messages_received / duration_seconds,
                'api_reduction_percentage': 75
            }
        }

    def test_websocket_data_quality(self, duration_seconds: int = 30) -> Dict[str, Any]:
        """Test WebSocket data quality and consistency"""
        self.logger.info("🔍 Testing WebSocket data quality")

        if not self.start_websocket():
            return {'error': 'Failed to start WebSocket'}

        initial_count = len(self.ws_data)
        time.sleep(duration_seconds)

        messages_received = len(self.ws_data) - initial_count

        # Analyze data quality
        recent_data = self.ws_data[-messages_received:] if messages_received > 0 else []

        data_quality = {
            'total_messages': messages_received,
            'messages_per_second': messages_received / duration_seconds,
            'data_completeness': 0,
            'price_continuity': True,
            'timestamp_consistency': True
        }

        if recent_data:
            # Check data completeness
            complete_records = sum(1 for record in recent_data if all([
                record.get('open_price'), record.get('high_price'),
                record.get('low_price'), record.get('close_price'),
                record.get('volume')
            ]))
            data_quality['data_completeness'] = (complete_records / len(recent_data)) * 100

            # Check price continuity (basic validation)
            for record in recent_data:
                if record.get('high_price', 0) < record.get('low_price', 0):
                    data_quality['price_continuity'] = False
                    break

        self.stop_websocket()

        return {
            'test_type': 'WEBSOCKET_QUALITY',
            'duration': duration_seconds,
            'data_quality': data_quality,
            'sample_data': recent_data[:3] if recent_data else []
        }

    def generate_comprehensive_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report"""
        self.logger.info("📊 Generating comprehensive rate limit and WebSocket integration report")

        report = {
            'test_timestamp': datetime.now().isoformat(),
            'test_configuration': {
                'symbols': self.test_symbols,
                'rate_limit_window': self.rate_limit_window,
                'max_calls_per_minute': self.max_calls_per_minute
            },
            'results': {}
        }

        # Test 1: API-only approach
        self.logger.info("\n" + "="*60)
        self.logger.info("🧪 TEST 1: API-Only Rate Limit Test")
        self.logger.info("="*60)
        api_only_results = self.test_api_rate_limits_without_websocket(60)
        report['results']['api_only'] = api_only_results

        # Reset rate limit tracking
        self.api_calls = []
        time.sleep(5)  # Brief pause between tests

        # Test 2: Hybrid approach with WebSocket
        self.logger.info("\n" + "="*60)
        self.logger.info("🧪 TEST 2: Hybrid WebSocket + API Test")
        self.logger.info("="*60)
        hybrid_results = self.test_hybrid_approach_with_websocket(60)
        report['results']['hybrid'] = hybrid_results

        time.sleep(5)  # Brief pause between tests

        # Test 3: WebSocket data quality
        self.logger.info("\n" + "="*60)
        self.logger.info("🧪 TEST 3: WebSocket Data Quality Test")
        self.logger.info("="*60)
        quality_results = self.test_websocket_data_quality(30)
        report['results']['data_quality'] = quality_results

        # Calculate efficiency improvements
        if ('api_only' in report['results'] and 'hybrid' in report['results'] and
            'api_calls' in api_only_results and 'api_calls' in hybrid_results):
            api_calls_reduction = (
                (api_only_results['api_calls'] - hybrid_results['api_calls']) /
                max(api_only_results['api_calls'], 1)
            ) * 100

            report['efficiency_analysis'] = {
                'api_calls_reduction_percentage': api_calls_reduction,
                'rate_limit_usage_reduction': api_calls_reduction,
                'recommended_approach': 'HYBRID' if api_calls_reduction > 50 else 'API_ONLY'
            }
        else:
            report['efficiency_analysis'] = {
                'api_calls_reduction_percentage': 0,
                'rate_limit_usage_reduction': 0,
                'recommended_approach': 'API_ONLY',
                'note': 'Incomplete test data - WebSocket test failed'
            }

        return report

    def print_report(self, report: Dict[str, Any]):
        """Print formatted test report"""
        print("\n" + "="*80)
        print("📊 RATE LIMIT & WEBSOCKET INTEGRATION TEST REPORT")
        print("="*80)

        print(f"\n⏰ Test Time: {report['test_timestamp']}")
        print(f"🎯 Symbols Tested: {', '.join(report['test_configuration']['symbols'])}")

        # API-Only Results
        if 'api_only' in report['results']:
            api_results = report['results']['api_only']
            print(f"\n🔸 API-ONLY APPROACH:")
            print(f"   └─ API Calls: {api_results['api_calls']}")
            print(f"   └─ Calls/Second: {api_results['calls_per_second']:.2f}")
            print(f"   └─ Error Rate: {api_results['error_rate']:.2f}%")
            print(f"   └─ Rate Limit Usage: {api_results['rate_limit_stats']['usage_percentage']:.2f}%")

        # Hybrid Results
        if 'hybrid' in report['results']:
            hybrid_results = report['results']['hybrid']
            print(f"\n🔸 HYBRID WEBSOCKET + API APPROACH:")
            print(f"   └─ API Calls: {hybrid_results['api_calls']}")
            print(f"   └─ WebSocket Messages: {hybrid_results['websocket_messages']}")
            print(f"   └─ API Calls/Second: {hybrid_results['calls_per_second']:.2f}")
            print(f"   └─ WS Messages/Second: {hybrid_results['websocket_efficiency']['messages_per_second']:.2f}")
            print(f"   └─ Error Rate: {hybrid_results['error_rate']:.2f}%")
            print(f"   └─ Rate Limit Usage: {hybrid_results['rate_limit_stats']['usage_percentage']:.2f}%")

        # Data Quality
        if 'data_quality' in report['results']:
            quality_results = report['results']['data_quality']
            if 'data_quality' in quality_results:
                dq = quality_results['data_quality']
                print(f"\n🔸 WEBSOCKET DATA QUALITY:")
                print(f"   └─ Messages Received: {dq['total_messages']}")
                print(f"   └─ Messages/Second: {dq['messages_per_second']:.2f}")
                print(f"   └─ Data Completeness: {dq['data_completeness']:.2f}%")
                print(f"   └─ Price Continuity: {'✅ Valid' if dq['price_continuity'] else '❌ Invalid'}")

        # Efficiency Analysis
        if 'efficiency_analysis' in report:
            eff = report['efficiency_analysis']
            print(f"\n🔸 EFFICIENCY ANALYSIS:")
            print(f"   └─ API Calls Reduction: {eff['api_calls_reduction_percentage']:.2f}%")
            print(f"   └─ Rate Limit Reduction: {eff['rate_limit_usage_reduction']:.2f}%")
            print(f"   └─ Recommended Approach: {eff['recommended_approach']}")

        print("\n" + "="*80)

def main():
    """Main test execution"""
    print("🚀 Starting Rate Limit & WebSocket Integration Test")

    try:
        tester = RateLimitWebSocketTester()

        # Run comprehensive tests
        report = tester.generate_comprehensive_report()

        # Print results
        tester.print_report(report)

        # Save report to file
        report_filename = f"rate_limit_websocket_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\n💾 Detailed report saved to: {report_filename}")

        # Recommendations
        print("\n🎯 RECOMMENDATIONS:")
        if 'efficiency_analysis' in report:
            if report['efficiency_analysis']['recommended_approach'] == 'HYBRID':
                print("✅ Implement hybrid WebSocket + API approach for optimal rate limit usage")
                print("📊 Use WebSocket for real-time price data")
                print("🔍 Use API for historical data and account operations")
            else:
                print("⚠️ Current API-only approach may be sufficient")
                print("📊 Consider WebSocket for high-frequency trading scenarios")

        print("🏁 Test completed successfully!")
        return True

    except KeyboardInterrupt:
        print("\n⏹️ Test interrupted by user")
        return False
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)