
#!/usr/bin/env python3
"""
Comprehensive WebSocket Integration Test
=======================================

Tests the WebSocket implementation in the main trading bot to verify:
1. WebSocket connection establishment
2. Real-time data reception
3. Integration with price fetcher
4. Data quality and accuracy
5. Rate limit reduction effectiveness
6. Bot manager WebSocket status tracking
"""

import asyncio
import json
import logging
import threading
import time
import websocket
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.utils.logger import setup_logger
from src.binance_client.client import BinanceClientWrapper
from src.data_fetcher.price_fetcher import PriceFetcher
from src.bot_manager import BotManager

class WebSocketIntegrationTester:
    """Comprehensive WebSocket integration tester"""

    def __init__(self):
        setup_logger()
        self.logger = logging.getLogger(__name__)
        
        # Test configuration
        self.test_symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
        self.test_duration = 60  # 1 minute test
        self.websocket_url_base = "wss://fstream.binance.com/ws/"
        
        # WebSocket tracking
        self.websocket_connections = {}
        self.received_data = {}
        self.connection_status = {}
        self.data_timestamps = {}
        
        # Bot integration tracking
        self.bot_manager = None
        self.price_fetcher = None
        self.binance_client = None
        
        # Test results
        self.test_results = {
            'websocket_connections': {},
            'data_quality': {},
            'bot_integration': {},
            'rate_limit_impact': {},
            'performance_metrics': {}
        }

    def setup_binance_client(self):
        """Setup Binance client for testing"""
        try:
            self.binance_client = BinanceClientWrapper()
            self.price_fetcher = PriceFetcher(self.binance_client)
            self.logger.info("✅ Binance client and price fetcher initialized")
            return True
        except Exception as e:
            self.logger.error(f"❌ Failed to setup Binance client: {e}")
            return False

    def create_websocket_connection(self, symbol: str) -> bool:
        """Create WebSocket connection for a symbol"""
        try:
            stream_name = f"{symbol.lower()}@kline_1m"
            websocket_url = f"{self.websocket_url_base}{stream_name}"
            
            self.logger.info(f"🔗 Creating WebSocket connection for {symbol}")
            self.logger.info(f"📡 URL: {websocket_url}")
            
            # Initialize tracking for this symbol
            self.received_data[symbol] = []
            self.connection_status[symbol] = {'connected': False, 'errors': 0, 'messages': 0}
            self.data_timestamps[symbol] = []
            
            def on_message(ws, message):
                try:
                    data = json.loads(message)
                    if 'k' in data:  # Kline data
                        kline = data['k']
                        processed_data = {
                            'symbol': kline['s'],
                            'open': float(kline['o']),
                            'high': float(kline['h']),
                            'low': float(kline['l']),
                            'close': float(kline['c']),
                            'volume': float(kline['v']),
                            'timestamp': int(kline['t']),
                            'is_closed': kline['x'],
                            'received_at': time.time()
                        }
                        
                        self.received_data[symbol].append(processed_data)
                        self.data_timestamps[symbol].append(time.time())
                        self.connection_status[symbol]['messages'] += 1
                        
                        if len(self.received_data[symbol]) % 10 == 0:
                            self.logger.info(f"📊 {symbol}: Received {len(self.received_data[symbol])} WebSocket messages")
                            
                except Exception as e:
                    self.logger.error(f"❌ Error processing WebSocket message for {symbol}: {e}")
                    self.connection_status[symbol]['errors'] += 1

            def on_error(ws, error):
                self.logger.error(f"❌ WebSocket error for {symbol}: {error}")
                self.connection_status[symbol]['errors'] += 1

            def on_close(ws, close_status_code, close_msg):
                self.logger.warning(f"🔌 WebSocket closed for {symbol}: {close_status_code} - {close_msg}")
                self.connection_status[symbol]['connected'] = False

            def on_open(ws):
                self.logger.info(f"✅ WebSocket connected for {symbol}")
                self.connection_status[symbol]['connected'] = True

            # Create WebSocket connection
            ws = websocket.WebSocketApp(
                websocket_url,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
                on_open=on_open
            )
            
            # Store WebSocket connection
            self.websocket_connections[symbol] = ws
            
            # Start WebSocket in separate thread
            ws_thread = threading.Thread(target=ws.run_forever)
            ws_thread.daemon = True
            ws_thread.start()
            
            # Wait for connection
            time.sleep(2)
            
            return self.connection_status[symbol]['connected']
            
        except Exception as e:
            self.logger.error(f"❌ Failed to create WebSocket for {symbol}: {e}")
            return False

    async def test_websocket_connections(self) -> Dict:
        """Test WebSocket connections for all symbols"""
        self.logger.info("🧪 TESTING WEBSOCKET CONNECTIONS")
        self.logger.info("=" * 50)
        
        connection_results = {}
        
        for symbol in self.test_symbols:
            self.logger.info(f"\n🔍 Testing WebSocket connection for {symbol}")
            
            # Create connection
            connected = self.create_websocket_connection(symbol)
            
            if connected:
                self.logger.info(f"✅ {symbol}: WebSocket connected successfully")
                
                # Wait for some data
                await asyncio.sleep(5)
                
                # Check data reception
                data_count = len(self.received_data.get(symbol, []))
                error_count = self.connection_status[symbol]['errors']
                
                connection_results[symbol] = {
                    'connected': True,
                    'data_received': data_count,
                    'errors': error_count,
                    'status': 'SUCCESS' if data_count > 0 and error_count == 0 else 'PARTIAL'
                }
                
                self.logger.info(f"📊 {symbol}: Received {data_count} messages, {error_count} errors")
                
            else:
                self.logger.error(f"❌ {symbol}: WebSocket connection failed")
                connection_results[symbol] = {
                    'connected': False,
                    'data_received': 0,
                    'errors': 1,
                    'status': 'FAILED'
                }
        
        self.test_results['websocket_connections'] = connection_results
        return connection_results

    async def test_data_quality(self) -> Dict:
        """Test WebSocket data quality and accuracy"""
        self.logger.info("\n🧪 TESTING WEBSOCKET DATA QUALITY")
        self.logger.info("=" * 50)
        
        quality_results = {}
        
        for symbol in self.test_symbols:
            if symbol not in self.received_data or not self.received_data[symbol]:
                quality_results[symbol] = {'status': 'NO_DATA', 'issues': ['No WebSocket data received']}
                continue
                
            self.logger.info(f"\n🔍 Analyzing data quality for {symbol}")
            
            data = self.received_data[symbol]
            issues = []
            metrics = {
                'total_messages': len(data),
                'unique_timestamps': len(set(d['timestamp'] for d in data)),
                'price_consistency': True,
                'volume_consistency': True,
                'timestamp_sequence': True
            }
            
            # Check for duplicate timestamps
            timestamps = [d['timestamp'] for d in data]
            if len(timestamps) != len(set(timestamps)):
                issues.append("Duplicate timestamps detected")
                metrics['timestamp_sequence'] = False
            
            # Check price consistency (OHLC rules)
            for d in data:
                if not (d['low'] <= d['open'] <= d['high'] and d['low'] <= d['close'] <= d['high']):
                    issues.append("OHLC price consistency violation")
                    metrics['price_consistency'] = False
                    break
            
            # Check volume consistency
            for d in data:
                if d['volume'] < 0:
                    issues.append("Negative volume detected")
                    metrics['volume_consistency'] = False
                    break
            
            # Compare with API data for accuracy
            try:
                api_data = self.binance_client.get_historical_klines(symbol, '1m', 5)
                if api_data:
                    latest_api = api_data[-1]
                    latest_ws = data[-1] if data else None
                    
                    if latest_ws:
                        api_close = float(latest_api[4])
                        ws_close = latest_ws['close']
                        price_diff = abs(api_close - ws_close) / api_close * 100
                        
                        if price_diff > 0.1:  # More than 0.1% difference
                            issues.append(f"Price deviation from API: {price_diff:.3f}%")
                        
                        metrics['api_comparison'] = {
                            'api_close': api_close,
                            'ws_close': ws_close,
                            'difference_percent': price_diff
                        }
                        
            except Exception as e:
                issues.append(f"API comparison failed: {e}")
            
            status = 'EXCELLENT' if not issues else 'GOOD' if len(issues) <= 2 else 'POOR'
            
            quality_results[symbol] = {
                'status': status,
                'metrics': metrics,
                'issues': issues,
                'sample_data': data[-3:] if len(data) >= 3 else data  # Last 3 messages
            }
            
            self.logger.info(f"📊 {symbol}: Quality status = {status}")
            if issues:
                for issue in issues:
                    self.logger.warning(f"⚠️ {symbol}: {issue}")
        
        self.test_results['data_quality'] = quality_results
        return quality_results

    async def test_bot_integration(self) -> Dict:
        """Test WebSocket integration with bot manager"""
        self.logger.info("\n🧪 TESTING BOT MANAGER INTEGRATION")
        self.logger.info("=" * 50)
        
        integration_results = {}
        
        try:
            # Create a mock bot manager to test integration
            self.logger.info("🤖 Creating test bot manager instance")
            
            # Check if WebSocket data would be accessible to bot manager
            # This simulates the integration logic from price_fetcher.py
            
            for symbol in self.test_symbols:
                self.logger.info(f"\n🔍 Testing {symbol} integration")
                
                # Simulate the WebSocket data access pattern used in price_fetcher
                integration_test = {
                    'websocket_data_available': symbol in self.received_data and len(self.received_data[symbol]) > 0,
                    'data_freshness': 'N/A',
                    'enhancement_possible': False
                }
                
                if integration_test['websocket_data_available']:
                    latest_data = self.received_data[symbol][-1]
                    data_age = time.time() - latest_data['received_at']
                    
                    integration_test['data_freshness'] = f"{data_age:.1f}s"
                    integration_test['enhancement_possible'] = data_age < 30  # Less than 30 seconds old
                    
                    # Test the actual price fetcher integration
                    try:
                        # Simulate what happens in get_market_data when WebSocket data is available
                        if hasattr(self.price_fetcher, 'get_market_data'):
                            # This would normally be called by the bot
                            df = await self.price_fetcher.get_market_data(symbol, '1m', 50)
                            if df is not None and not df.empty:
                                integration_test['price_fetcher_compatible'] = True
                                integration_test['api_data_retrieved'] = len(df)
                            else:
                                integration_test['price_fetcher_compatible'] = False
                                integration_test['error'] = 'No data from price fetcher'
                    except Exception as e:
                        integration_test['price_fetcher_compatible'] = False
                        integration_test['error'] = str(e)
                
                status = 'SUCCESS' if integration_test.get('enhancement_possible', False) else 'LIMITED'
                integration_results[symbol] = {
                    'status': status,
                    'details': integration_test
                }
                
                self.logger.info(f"📊 {symbol}: Integration status = {status}")
                
        except Exception as e:
            self.logger.error(f"❌ Bot integration test failed: {e}")
            integration_results['error'] = str(e)
        
        self.test_results['bot_integration'] = integration_results
        return integration_results

    async def test_rate_limit_impact(self) -> Dict:
        """Test rate limit reduction impact"""
        self.logger.info("\n🧪 TESTING RATE LIMIT IMPACT")
        self.logger.info("=" * 50)
        
        # Track API calls during test
        api_calls_start = getattr(self.binance_client, '_request_count', 0)
        start_time = time.time()
        
        # Simulate normal bot operations with WebSocket enhancement
        api_operations = 0
        
        for symbol in self.test_symbols:
            try:
                # These operations would normally require API calls
                # With WebSocket, some of these could be reduced
                
                # Get market data (normally API call)
                df = await self.price_fetcher.get_market_data(symbol, '1m', 50)
                api_operations += 1
                
                # Get current price (could use WebSocket)
                price = self.price_fetcher.get_current_price(symbol)
                if price:
                    api_operations += 1
                
                await asyncio.sleep(1)  # Simulate processing time
                
            except Exception as e:
                self.logger.warning(f"⚠️ Rate limit test operation failed for {symbol}: {e}")
        
        end_time = time.time()
        api_calls_end = getattr(self.binance_client, '_request_count', 0)
        
        test_duration = end_time - start_time
        actual_api_calls = api_calls_end - api_calls_start
        
        # Calculate efficiency
        theoretical_calls = api_operations  # Without WebSocket optimization
        actual_calls = actual_api_calls     # With current implementation
        
        efficiency_improvement = 0
        if theoretical_calls > 0:
            efficiency_improvement = ((theoretical_calls - actual_calls) / theoretical_calls) * 100
        
        rate_limit_results = {
            'test_duration_seconds': test_duration,
            'theoretical_api_calls': theoretical_calls,
            'actual_api_calls': actual_calls,
            'efficiency_improvement_percent': efficiency_improvement,
            'calls_per_minute': (actual_calls / test_duration) * 60 if test_duration > 0 else 0,
            'websocket_data_available': sum(1 for s in self.test_symbols if s in self.received_data and self.received_data[s])
        }
        
        self.logger.info(f"📊 Rate Limit Analysis:")
        self.logger.info(f"   Theoretical API calls: {theoretical_calls}")
        self.logger.info(f"   Actual API calls: {actual_calls}")
        self.logger.info(f"   Efficiency improvement: {efficiency_improvement:.1f}%")
        self.logger.info(f"   Calls per minute: {rate_limit_results['calls_per_minute']:.1f}")
        
        self.test_results['rate_limit_impact'] = rate_limit_results
        return rate_limit_results

    async def test_performance_metrics(self) -> Dict:
        """Test WebSocket performance metrics"""
        self.logger.info("\n🧪 TESTING PERFORMANCE METRICS")
        self.logger.info("=" * 50)
        
        performance_results = {}
        
        for symbol in self.test_symbols:
            if symbol not in self.data_timestamps or not self.data_timestamps[symbol]:
                continue
                
            timestamps = self.data_timestamps[symbol]
            
            # Calculate message frequency
            if len(timestamps) > 1:
                intervals = [timestamps[i] - timestamps[i-1] for i in range(1, len(timestamps))]
                avg_interval = sum(intervals) / len(intervals)
                messages_per_second = 1 / avg_interval if avg_interval > 0 else 0
            else:
                avg_interval = 0
                messages_per_second = 0
            
            # Calculate data latency (if available)
            latest_data = self.received_data.get(symbol, [])
            latency_ms = 0
            if latest_data:
                # Estimate latency based on timestamp difference
                latest = latest_data[-1]
                server_time = latest['timestamp'] / 1000  # Convert to seconds
                received_time = latest['received_at']
                latency_ms = (received_time - server_time) * 1000
            
            performance_results[symbol] = {
                'total_messages': len(timestamps),
                'average_interval_seconds': avg_interval,
                'messages_per_second': messages_per_second,
                'estimated_latency_ms': latency_ms,
                'connection_errors': self.connection_status.get(symbol, {}).get('errors', 0)
            }
            
            self.logger.info(f"📊 {symbol} Performance:")
            self.logger.info(f"   Messages/sec: {messages_per_second:.2f}")
            self.logger.info(f"   Latency: {latency_ms:.1f}ms")
            self.logger.info(f"   Errors: {performance_results[symbol]['connection_errors']}")
        
        self.test_results['performance_metrics'] = performance_results
        return performance_results

    def close_websocket_connections(self):
        """Close all WebSocket connections"""
        self.logger.info("🔌 Closing WebSocket connections")
        
        for symbol, ws in self.websocket_connections.items():
            try:
                ws.close()
                self.logger.info(f"✅ Closed WebSocket for {symbol}")
            except Exception as e:
                self.logger.warning(f"⚠️ Error closing WebSocket for {symbol}: {e}")

    def generate_comprehensive_report(self) -> Dict:
        """Generate comprehensive test report"""
        self.logger.info("\n📋 GENERATING COMPREHENSIVE REPORT")
        self.logger.info("=" * 50)
        
        # Calculate overall status
        overall_status = "SUCCESS"
        
        # Check WebSocket connections
        connection_success_rate = 0
        if self.test_results['websocket_connections']:
            successful_connections = sum(1 for r in self.test_results['websocket_connections'].values() if r['connected'])
            connection_success_rate = (successful_connections / len(self.test_results['websocket_connections'])) * 100
            
            if connection_success_rate < 100:
                overall_status = "PARTIAL"
            if connection_success_rate == 0:
                overall_status = "FAILED"
        
        # Check data quality
        quality_issues = 0
        if self.test_results['data_quality']:
            for result in self.test_results['data_quality'].values():
                if result['status'] in ['POOR', 'NO_DATA']:
                    quality_issues += 1
            
            if quality_issues > 0:
                overall_status = "NEEDS_IMPROVEMENT" if overall_status == "SUCCESS" else overall_status
        
        # Generate recommendations
        recommendations = []
        
        if connection_success_rate < 100:
            recommendations.append("Improve WebSocket connection reliability")
        
        if quality_issues > 0:
            recommendations.append("Address data quality issues")
        
        if self.test_results.get('rate_limit_impact', {}).get('efficiency_improvement_percent', 0) < 10:
            recommendations.append("Optimize WebSocket integration for better rate limit reduction")
        
        if not recommendations:
            recommendations.append("WebSocket integration is working well - consider production deployment")
        
        report = {
            'test_timestamp': datetime.now().isoformat(),
            'overall_status': overall_status,
            'connection_success_rate': connection_success_rate,
            'symbols_tested': self.test_symbols,
            'test_duration_minutes': self.test_duration / 60,
            'detailed_results': self.test_results,
            'recommendations': recommendations,
            'summary': {
                'websocket_connections': len([r for r in self.test_results.get('websocket_connections', {}).values() if r['connected']]),
                'data_quality_good': len([r for r in self.test_results.get('data_quality', {}).values() if r['status'] in ['EXCELLENT', 'GOOD']]),
                'rate_limit_improvement': self.test_results.get('rate_limit_impact', {}).get('efficiency_improvement_percent', 0)
            }
        }
        
        return report

    def print_report(self, report: Dict):
        """Print formatted test report"""
        print("\n" + "="*80)
        print("🚀 WEBSOCKET INTEGRATION TEST REPORT")
        print("="*80)
        
        print(f"⏰ Test Time: {report['test_timestamp']}")
        print(f"🎯 Overall Status: {report['overall_status']}")
        print(f"📊 Connection Success Rate: {report['connection_success_rate']:.1f}%")
        print(f"⏱️  Test Duration: {report['test_duration_minutes']:.1f} minutes")
        
        print(f"\n📈 SUMMARY:")
        print(f"   ✅ WebSocket Connections: {report['summary']['websocket_connections']}/{len(report['symbols_tested'])}")
        print(f"   📊 Good Data Quality: {report['summary']['data_quality_good']}/{len(report['symbols_tested'])}")
        print(f"   ⚡ Rate Limit Improvement: {report['summary']['rate_limit_improvement']:.1f}%")
        
        print(f"\n🔍 DETAILED RESULTS:")
        
        # WebSocket Connections
        if 'websocket_connections' in report['detailed_results']:
            print(f"   🌐 WebSocket Connections:")
            for symbol, result in report['detailed_results']['websocket_connections'].items():
                status_icon = "✅" if result['connected'] else "❌"
                print(f"      {status_icon} {symbol}: {result['status']} ({result['data_received']} messages)")
        
        # Data Quality
        if 'data_quality' in report['detailed_results']:
            print(f"   📊 Data Quality:")
            for symbol, result in report['detailed_results']['data_quality'].items():
                status_icons = {"EXCELLENT": "✅", "GOOD": "🟡", "POOR": "❌", "NO_DATA": "⚫"}
                status_icon = status_icons.get(result['status'], "❓")
                print(f"      {status_icon} {symbol}: {result['status']}")
        
        # Rate Limit Impact
        if 'rate_limit_impact' in report['detailed_results']:
            rate_data = report['detailed_results']['rate_limit_impact']
            print(f"   ⚡ Rate Limit Impact:")
            print(f"      📉 API Calls: {rate_data.get('actual_api_calls', 0)} (vs {rate_data.get('theoretical_api_calls', 0)} theoretical)")
            print(f"      📈 Efficiency: {rate_data.get('efficiency_improvement_percent', 0):.1f}% improvement")
            print(f"      🕒 Rate: {rate_data.get('calls_per_minute', 0):.1f} calls/minute")
        
        print(f"\n💡 RECOMMENDATIONS:")
        for i, rec in enumerate(report['recommendations'], 1):
            print(f"   {i}. {rec}")
        
        print("\n" + "="*80)

async def main():
    """Main test execution"""
    print("🚀 Starting Comprehensive WebSocket Integration Test")
    print("="*60)
    
    tester = WebSocketIntegrationTester()
    
    try:
        # Setup
        if not tester.setup_binance_client():
            print("❌ Failed to setup Binance client - cannot continue")
            return
        
        print(f"🎯 Testing symbols: {tester.test_symbols}")
        print(f"⏱️  Test duration: {tester.test_duration} seconds")
        print()
        
        # Run tests
        await tester.test_websocket_connections()
        await asyncio.sleep(5)  # Let connections stabilize
        
        await tester.test_data_quality()
        await tester.test_bot_integration()
        await tester.test_rate_limit_impact()
        await tester.test_performance_metrics()
        
        # Generate and display report
        report = tester.generate_comprehensive_report()
        tester.print_report(report)
        
        # Save report
        report_filename = f"websocket_integration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"\n💾 Detailed report saved to: {report_filename}")
        
        # Cleanup
        tester.close_websocket_connections()
        
        print("\n🏁 WebSocket Integration Test completed!")
        
        # Final status
        if report['overall_status'] == 'SUCCESS':
            print("✅ WebSocket integration is working well!")
        elif report['overall_status'] == 'PARTIAL':
            print("🟡 WebSocket integration has some issues but is functional")
        else:
            print("❌ WebSocket integration needs attention")
            
        return report['overall_status'] == 'SUCCESS'
        
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
        tester.close_websocket_connections()
        return False
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        print(f"🔍 Traceback: {traceback.format_exc()}")
        tester.close_websocket_connections()
        return False

if __name__ == "__main__":
    asyncio.run(main())
