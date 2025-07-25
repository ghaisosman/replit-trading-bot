
#!/usr/bin/env python3
"""
WebSocket Deployment Connection Test
==================================

Test WebSocket connectivity specifically for deployment environments like Render.
"""

import asyncio
import time
import logging
import json
import sys
import os
from datetime import datetime

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.utils.logger import setup_logger
from src.data_fetcher.websocket_manager import websocket_manager

class WebSocketDeploymentTester:
    """Test WebSocket in deployment environment"""
    
    def __init__(self):
        setup_logger()
        self.logger = logging.getLogger(__name__)
        self.test_results = {}
        
    async def test_websocket_deployment(self):
        """Test WebSocket connection for deployment"""
        print("🧪 WEBSOCKET DEPLOYMENT CONNECTION TEST")
        print("=" * 50)
        
        # Test configuration
        test_symbols = ['BTCUSDT', 'ETHUSDT']
        test_interval = '1m'
        
        # Add streams to WebSocket manager
        for symbol in test_symbols:
            websocket_manager.add_symbol_interval(symbol, test_interval)
            print(f"📡 Added: {symbol} {test_interval}")
        
        # Start WebSocket manager
        print("\n🚀 Starting WebSocket connection...")
        websocket_manager.start()
        
        # Wait for connection
        connection_timeout = 30
        wait_start = time.time()
        
        while not websocket_manager.is_connected and (time.time() - wait_start) < connection_timeout:
            print(f"⏳ Waiting for connection... ({int(time.time() - wait_start)}s)")
            await asyncio.sleep(2)
        
        if websocket_manager.is_connected:
            print("✅ WebSocket Connected!")
            
            # Wait for data
            print("\n📊 Waiting for real-time data...")
            data_timeout = 60
            data_start = time.time()
            
            while (time.time() - data_start) < data_timeout:
                # Check for cached data
                has_data = False
                for symbol in test_symbols:
                    latest = websocket_manager.get_latest_kline(symbol, test_interval)
                    if latest:
                        print(f"📈 {symbol}: ${latest['close']:.4f} (Updated: {datetime.fromtimestamp(latest['received_at']).strftime('%H:%M:%S')})")
                        has_data = True
                
                if has_data:
                    break
                    
                await asyncio.sleep(5)
            
            # Display statistics
            stats = websocket_manager.get_statistics()
            print(f"\n📊 WEBSOCKET STATISTICS:")
            print(f"   • Connected: {stats['is_connected']}")
            print(f"   • Messages received: {stats['messages_received']}")
            print(f"   • Klines processed: {stats['klines_processed']}")
            print(f"   • Uptime: {stats['uptime_seconds']:.1f}s")
            
            if stats['messages_received'] > 0:
                print("✅ SUCCESS: WebSocket is receiving data!")
                return True
            else:
                print("❌ ISSUE: WebSocket connected but no data received")
                return False
        else:
            print("❌ FAILED: WebSocket connection timeout")
            return False

async def main():
    """Run the test"""
    tester = WebSocketDeploymentTester()
    
    try:
        success = await tester.test_websocket_deployment()
        
        if success:
            print("\n🎉 WebSocket deployment test PASSED!")
        else:
            print("\n💥 WebSocket deployment test FAILED!")
            print("\n🔧 TROUBLESHOOTING TIPS:")
            print("1. Check server firewall settings")
            print("2. Verify outbound HTTPS/WSS connections are allowed")
            print("3. Check if WebSocket protocols are blocked")
            print("4. Test with different WebSocket endpoints")
            
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        import traceback
        print(f"Full traceback:\n{traceback.format_exc()}")
    
    finally:
        # Cleanup
        websocket_manager.stop()
        print("\n🧹 Cleanup completed")

if __name__ == "__main__":
    asyncio.run(main())
#!/usr/bin/env python3
"""
WebSocket Deployment Connection Test
===================================

Tests WebSocket connectivity specifically for deployment environments
to diagnose geographic restrictions and connection issues.
"""

import asyncio
import json
import logging
import os
import sys
import time
import websocket
import ssl
from datetime import datetime
from typing import Dict, Any, Optional
import threading

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.utils.logger import setup_logger
from src.config.global_config import global_config

class WebSocketDeploymentTester:
    """Test WebSocket connectivity in deployment environment"""
    
    def __init__(self):
        setup_logger()
        self.logger = logging.getLogger(__name__)
        
        # Test configuration
        self.test_symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
        self.test_intervals = ['1m', '5m']
        self.test_timeout = 30  # seconds
        
        # Connection tracking
        self.connection_results = {}
        self.received_messages = []
        self.connection_errors = []
        
        # WebSocket instances
        self.test_connections = {}
        
    def detect_environment(self) -> Dict[str, Any]:
        """Detect deployment environment and configuration"""
        env_info = {
            'is_deployment': os.environ.get('REPLIT_DEPLOYMENT') == '1',
            'is_replit': 'REPL_ID' in os.environ,
            'environment': 'DEPLOYMENT' if os.environ.get('REPLIT_DEPLOYMENT') == '1' else 'DEVELOPMENT',
            'binance_testnet': global_config.BINANCE_TESTNET,
            'binance_futures': global_config.BINANCE_FUTURES,
            'timestamp': datetime.now().isoformat()
        }
        
        self.logger.info(f"🌐 ENVIRONMENT DETECTION")
        self.logger.info(f"   Environment: {env_info['environment']}")
        self.logger.info(f"   Is Deployment: {env_info['is_deployment']}")
        self.logger.info(f"   Is Replit: {env_info['is_replit']}")
        self.logger.info(f"   Binance Testnet: {env_info['binance_testnet']}")
        self.logger.info(f"   Binance Futures: {env_info['binance_futures']}")
        
        return env_info
        
    def test_basic_websocket_connection(self) -> Dict[str, Any]:
        """Test basic WebSocket connection to Binance"""
        self.logger.info(f"\n🧪 TESTING BASIC WEBSOCKET CONNECTION")
        self.logger.info("=" * 50)
        
        test_result = {
            'success': False,
            'connection_time': None,
            'error': None,
            'messages_received': 0,
            'test_duration': 0
        }
        
        # Use futures WebSocket endpoint
        ws_url = "wss://fstream.binance.com/ws/btcusdt@kline_1m"
        
        connection_event = threading.Event()
        error_event = threading.Event()
        start_time = time.time()
        
        def on_open(ws):
            self.logger.info("✅ WebSocket connection opened successfully")
            test_result['success'] = True
            test_result['connection_time'] = time.time() - start_time
            connection_event.set()
            
        def on_message(ws, message):
            try:
                data = json.loads(message)
                test_result['messages_received'] += 1
                self.received_messages.append({
                    'timestamp': datetime.now().isoformat(),
                    'data': data
                })
                self.logger.info(f"📊 Received message #{test_result['messages_received']}")
                
                # Close after receiving first message
                if test_result['messages_received'] >= 1:
                    ws.close()
                    
            except Exception as e:
                self.logger.error(f"Error processing message: {e}")
                
        def on_error(ws, error):
            error_str = str(error)
            self.logger.error(f"❌ WebSocket error: {error}")
            
            # Analyze error type
            if "403" in error_str or "Forbidden" in error_str:
                self.logger.error("🚫 Geographic restriction detected")
                test_result['error'] = "GEOGRAPHIC_RESTRICTION"
            elif "timeout" in error_str.lower():
                test_result['error'] = "CONNECTION_TIMEOUT"
            elif "refused" in error_str.lower():
                test_result['error'] = "CONNECTION_REFUSED"
            else:
                test_result['error'] = f"UNKNOWN_ERROR: {error_str}"
                
            error_event.set()
            
        def on_close(ws, close_status_code, close_msg):
            self.logger.info(f"🔌 WebSocket closed: {close_status_code} - {close_msg}")
            
        try:
            self.logger.info(f"🔗 Connecting to: {ws_url}")
            
            ws = websocket.WebSocketApp(
                ws_url,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )
            
            # Run in thread with timeout
            ws_thread = threading.Thread(target=lambda: ws.run_forever(
                sslopt={"cert_reqs": ssl.CERT_NONE},
                ping_interval=20,
                ping_timeout=10
            ))
            ws_thread.daemon = True
            ws_thread.start()
            
            # Wait for connection or error
            if connection_event.wait(timeout=self.test_timeout):
                # Wait a bit for messages
                time.sleep(5)
                ws.close()
            elif error_event.wait(timeout=0.1):
                pass  # Error already logged
            else:
                self.logger.error("❌ Connection timeout")
                test_result['error'] = "CONNECTION_TIMEOUT"
                ws.close()
                
            ws_thread.join(timeout=2)
            
        except Exception as e:
            self.logger.error(f"❌ WebSocket test failed: {e}")
            test_result['error'] = f"EXCEPTION: {str(e)}"
            
        test_result['test_duration'] = time.time() - start_time
        
        # Log results
        if test_result['success']:
            self.logger.info(f"✅ Connection successful in {test_result['connection_time']:.2f}s")
            self.logger.info(f"📊 Received {test_result['messages_received']} messages")
        else:
            self.logger.error(f"❌ Connection failed: {test_result['error']}")
            
        return test_result
        
    def test_multiple_streams(self) -> Dict[str, Any]:
        """Test multiple WebSocket streams like the bot uses"""
        self.logger.info(f"\n🧪 TESTING MULTIPLE WEBSOCKET STREAMS")
        self.logger.info("=" * 50)
        
        # Create combined stream URL like the bot does
        streams = []
        for symbol in self.test_symbols[:2]:  # Test with 2 symbols
            for interval in ['1m']:  # Test with 1m only
                streams.append(f"{symbol.lower()}@kline_{interval}")
                
        combined_stream = "/".join(streams)
        ws_url = f"wss://fstream.binance.com/ws/{combined_stream}"
        
        test_result = {
            'success': False,
            'streams_tested': len(streams),
            'messages_received': 0,
            'unique_symbols': set(),
            'error': None,
            'connection_time': None
        }
        
        self.logger.info(f"🔗 Testing {len(streams)} streams: {streams}")
        self.logger.info(f"🔗 URL: {ws_url}")
        
        connection_event = threading.Event()
        start_time = time.time()
        
        def on_open(ws):
            self.logger.info(f"✅ Multi-stream connection opened")
            test_result['success'] = True
            test_result['connection_time'] = time.time() - start_time
            connection_event.set()
            
        def on_message(ws, message):
            try:
                data = json.loads(message)
                test_result['messages_received'] += 1
                
                # Extract symbol from stream data
                if 'stream' in data:
                    symbol = data['stream'].split('@')[0].upper()
                    test_result['unique_symbols'].add(symbol)
                    
                self.logger.info(f"📊 Message #{test_result['messages_received']} from {symbol}")
                
                # Close after receiving messages from all symbols
                if len(test_result['unique_symbols']) >= len(self.test_symbols[:2]):
                    ws.close()
                    
            except Exception as e:
                self.logger.error(f"Error processing multi-stream message: {e}")
                
        def on_error(ws, error):
            error_str = str(error)
            self.logger.error(f"❌ Multi-stream WebSocket error: {error}")
            
            if "403" in error_str or "Forbidden" in error_str:
                test_result['error'] = "GEOGRAPHIC_RESTRICTION"
            else:
                test_result['error'] = f"ERROR: {error_str}"
                
        def on_close(ws, close_status_code, close_msg):
            self.logger.info(f"🔌 Multi-stream WebSocket closed")
            
        try:
            ws = websocket.WebSocketApp(
                ws_url,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )
            
            ws_thread = threading.Thread(target=lambda: ws.run_forever(
                sslopt={"cert_reqs": ssl.CERT_NONE}
            ))
            ws_thread.daemon = True
            ws_thread.start()
            
            # Wait for connection and messages
            if connection_event.wait(timeout=self.test_timeout):
                time.sleep(10)  # Wait longer for multiple messages
                ws.close()
            else:
                self.logger.error("❌ Multi-stream connection timeout")
                test_result['error'] = "CONNECTION_TIMEOUT"
                
            ws_thread.join(timeout=2)
            
        except Exception as e:
            self.logger.error(f"❌ Multi-stream test failed: {e}")
            test_result['error'] = f"EXCEPTION: {str(e)}"
            
        # Convert set to list for JSON serialization
        test_result['unique_symbols'] = list(test_result['unique_symbols'])
        
        self.logger.info(f"📊 Multi-stream results:")
        self.logger.info(f"   Messages received: {test_result['messages_received']}")
        self.logger.info(f"   Unique symbols: {test_result['unique_symbols']}")
        
        return test_result
        
    def test_websocket_manager_integration(self) -> Dict[str, Any]:
        """Test the actual WebSocket manager used by the bot"""
        self.logger.info(f"\n🧪 TESTING BOT WEBSOCKET MANAGER INTEGRATION")
        self.logger.info("=" * 50)
        
        from src.data_fetcher.websocket_manager import websocket_manager
        
        test_result = {
            'manager_initialized': False,
            'streams_added': 0,
            'connection_started': False,
            'data_received': False,
            'cache_populated': False,
            'error': None
        }
        
        try:
            # Add test symbols
            for symbol in self.test_symbols[:2]:
                websocket_manager.add_symbol_interval(symbol, '1m')
                test_result['streams_added'] += 1
                
            self.logger.info(f"✅ Added {test_result['streams_added']} streams to manager")
            test_result['manager_initialized'] = True
            
            # Start WebSocket manager
            websocket_manager.start()
            test_result['connection_started'] = True
            self.logger.info("✅ WebSocket manager started")
            
            # Wait for connection and data
            self.logger.info("⏱️ Waiting for WebSocket data...")
            max_wait = 30
            wait_time = 0
            
            while wait_time < max_wait:
                time.sleep(2)
                wait_time += 2
                
                # Check if we have cached data
                for symbol in self.test_symbols[:2]:
                    cached_data = websocket_manager.get_cached_klines(symbol, '1m', 5)
                    if cached_data and len(cached_data) > 0:
                        test_result['data_received'] = True
                        test_result['cache_populated'] = True
                        self.logger.info(f"✅ Received data for {symbol}: {len(cached_data)} klines")
                        break
                        
                if test_result['data_received']:
                    break
                    
                # Check connection status
                stats = websocket_manager.get_statistics()
                self.logger.info(f"📊 Manager stats: Connected={stats['is_connected']}, "
                               f"Messages={stats['messages_received']}")
                               
            # Get final statistics
            final_stats = websocket_manager.get_statistics()
            test_result['final_stats'] = final_stats
            
            if not test_result['data_received']:
                test_result['error'] = "NO_DATA_RECEIVED"
                self.logger.error("❌ No WebSocket data received within timeout")
            else:
                self.logger.info("✅ WebSocket manager test successful")
                
            # Stop manager
            websocket_manager.stop()
            
        except Exception as e:
            self.logger.error(f"❌ WebSocket manager test failed: {e}")
            test_result['error'] = f"EXCEPTION: {str(e)}"
            
        return test_result
        
    def generate_deployment_report(self, env_info: Dict, basic_test: Dict, 
                                 multi_test: Dict, manager_test: Dict) -> Dict[str, Any]:
        """Generate comprehensive deployment test report"""
        
        # Determine overall status
        overall_success = (
            basic_test.get('success', False) and
            multi_test.get('success', False) and
            manager_test.get('data_received', False)
        )
        
        # Analyze issues
        issues = []
        recommendations = []
        
        if not basic_test.get('success', False):
            issues.append(f"Basic WebSocket connection failed: {basic_test.get('error', 'Unknown')}")
            
            if basic_test.get('error') == 'GEOGRAPHIC_RESTRICTION':
                recommendations.append("Implement proxy infrastructure as described in Instructions.md")
                recommendations.append("Consider using VPN/proxy service for deployment")
                
        if not multi_test.get('success', False):
            issues.append(f"Multi-stream connection failed: {multi_test.get('error', 'Unknown')}")
            
        if not manager_test.get('data_received', False):
            issues.append("Bot WebSocket manager not receiving data")
            recommendations.append("Check WebSocket manager configuration")
            
        if not issues:
            recommendations.append("WebSocket connectivity is working - no action needed")
        else:
            recommendations.append("WebSocket connectivity issues detected - requires proxy solution")
            
        report = {
            'test_timestamp': datetime.now().isoformat(),
            'environment': env_info,
            'overall_success': overall_success,
            'test_results': {
                'basic_connection': basic_test,
                'multi_stream': multi_test,
                'manager_integration': manager_test
            },
            'issues_detected': issues,
            'recommendations': recommendations,
            'deployment_status': 'READY' if overall_success else 'NEEDS_PROXY_SOLUTION'
        }
        
        return report
        
    def print_report(self, report: Dict[str, Any]):
        """Print formatted test report"""
        print("\n" + "="*80)
        print("🧪 WEBSOCKET DEPLOYMENT TEST REPORT")
        print("="*80)
        
        print(f"\n📊 OVERALL STATUS: {'✅ PASSED' if report['overall_success'] else '❌ FAILED'}")
        print(f"🌐 Environment: {report['environment']['environment']}")
        print(f"📅 Test Time: {report['test_timestamp']}")
        
        print(f"\n🔍 TEST RESULTS:")
        for test_name, result in report['test_results'].items():
            success = result.get('success', False) or result.get('data_received', False)
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"   {test_name.replace('_', ' ').title()}: {status}")
            
            if not success and 'error' in result:
                print(f"      Error: {result['error']}")
                
        if report['issues_detected']:
            print(f"\n⚠️ ISSUES DETECTED:")
            for i, issue in enumerate(report['issues_detected'], 1):
                print(f"   {i}. {issue}")
                
        print(f"\n💡 RECOMMENDATIONS:")
        for i, rec in enumerate(report['recommendations'], 1):
            print(f"   {i}. {rec}")
            
        print(f"\n🚀 DEPLOYMENT STATUS: {report['deployment_status']}")
        print("="*80)

async def main():
    """Main test execution"""
    print("🚀 Starting WebSocket Deployment Connection Test")
    print("="*60)
    
    tester = WebSocketDeploymentTester()
    
    # Detect environment
    env_info = tester.detect_environment()
    
    # Run tests
    basic_test = tester.test_basic_websocket_connection()
    multi_test = tester.test_multiple_streams()
    manager_test = tester.test_websocket_manager_integration()
    
    # Generate and display report
    report = tester.generate_deployment_report(env_info, basic_test, multi_test, manager_test)
    tester.print_report(report)
    
    # Save report
    report_filename = f"websocket_deployment_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_filename, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"\n💾 Detailed report saved to: {report_filename}")

if __name__ == "__main__":
    asyncio.run(main())
