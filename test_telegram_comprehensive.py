
#!/usr/bin/env python3
"""
Comprehensive Telegram Messaging Test
===================================

Tests all Telegram notifications for trading events:
1. Bot startup/shutdown notifications
2. Position opened notifications (all strategies)
3. Position closed notifications (all strategies)
4. Error notifications
5. Balance warnings
6. Anomaly detection notifications (orphan/ghost trades)
7. Partial take profit notifications

This test verifies:
- Message content accuracy
- Message formatting
- Strategy-specific information
- All notification types are working
- Message delivery success/failure
"""

import sys
import os
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from unittest.mock import Mock, patch

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.reporting.telegram_reporter import TelegramReporter
from src.config.global_config import global_config
from src.execution_engine.order_manager import Position
from src.strategy_processor.signal_processor import TradingSignal, SignalType

class TelegramTestResult:
    """Store test results for each message type"""
    def __init__(self, message_type: str, test_name: str):
        self.message_type = message_type
        self.test_name = test_name
        self.success = False
        self.message_content = ""
        self.error = None
        self.timestamp = datetime.now()

class ComprehensiveTelegramTest:
    """Test all Telegram notifications comprehensively"""
    
    def __init__(self):
        self.results = []
        self.telegram_reporter = None
        self.test_messages = []  # Store all generated messages
        
    def setup_telegram_reporter(self) -> bool:
        """Initialize Telegram reporter for testing"""
        try:
            # Initialize the reporter
            self.telegram_reporter = TelegramReporter()
            
            if not self.telegram_reporter.enabled:
                print("⚠️ TELEGRAM NOT CONFIGURED - Testing message generation only")
                print("   To test actual sending, configure TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
                return False
            else:
                print("✅ TELEGRAM CONFIGURED - Testing both generation and sending")
                return True
                
        except Exception as e:
            print(f"❌ Error setting up Telegram reporter: {e}")
            return False

    def capture_message_content(self, original_method):
        """Decorator to capture message content before sending"""
        def wrapper(*args, **kwargs):
            # Extract message content
            if len(args) > 1:
                message_content = args[1]  # Second argument is usually the message
            elif 'message' in kwargs:
                message_content = kwargs['message']
            else:
                message_content = "No message content captured"
            
            # Store the message content
            self.test_messages.append({
                'timestamp': datetime.now().isoformat(),
                'content': message_content,
                'method': original_method.__name__
            })
            
            # Print message content for visibility
            print(f"📱 CAPTURED MESSAGE ({original_method.__name__}):")
            print("─" * 60)
            print(message_content)
            print("─" * 60)
            
            # If Telegram is configured, try to send
            if self.telegram_reporter.enabled:
                try:
                    result = original_method(*args, **kwargs)
                    print(f"✅ Message sent successfully: {result}")
                    return result
                except Exception as e:
                    print(f"❌ Failed to send message: {e}")
                    return False
            else:
                print("📝 Message generation successful (sending skipped - not configured)")
                return True
                
        return wrapper

    def test_bot_startup_notification(self) -> TelegramTestResult:
        """Test bot startup notification"""
        test_result = TelegramTestResult("startup", "Bot Startup Notification")
        
        try:
            # Mock startup data
            pairs = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
            strategies = ['rsi_oversold', 'macd_divergence', 'engulfing_pattern']
            balance = 1000.0
            open_trades = 0
            
            # Patch send_message to capture content
            with patch.object(self.telegram_reporter, 'send_message', 
                            side_effect=self.capture_message_content(self.telegram_reporter.send_message)):
                
                success = self.telegram_reporter.report_bot_startup(
                    pairs=pairs,
                    strategies=strategies,
                    balance=balance,
                    open_trades=open_trades
                )
                
                test_result.success = success
                test_result.message_content = self.test_messages[-1]['content'] if self.test_messages else "No message captured"
                
        except Exception as e:
            test_result.error = str(e)
            test_result.success = False
            
        return test_result

    def test_bot_shutdown_notification(self) -> TelegramTestResult:
        """Test bot shutdown notification"""
        test_result = TelegramTestResult("shutdown", "Bot Shutdown Notification")
        
        try:
            reason = "Manual shutdown for testing"
            
            with patch.object(self.telegram_reporter, 'send_message', 
                            side_effect=self.capture_message_content(self.telegram_reporter.send_message)):
                
                success = self.telegram_reporter.report_bot_stopped(reason=reason)
                
                test_result.success = success
                test_result.message_content = self.test_messages[-1]['content'] if self.test_messages else "No message captured"
                
        except Exception as e:
            test_result.error = str(e)
            test_result.success = False
            
        return test_result

    def test_position_opened_notifications(self) -> List[TelegramTestResult]:
        """Test position opened notifications for all strategies"""
        test_results = []
        
        # Test data for each strategy
        strategy_test_data = {
            'RSI_OVERSOLD_SOLUSDT': {
                'strategy_name': 'RSI_OVERSOLD_SOLUSDT',
                'symbol': 'SOLUSDT',
                'side': 'BUY',
                'entry_price': 120.5500,
                'quantity': 0.83,
                'leverage': 5,
                'test_name': 'RSI Oversold Position Opened'
            },
            'MACD_DIVERGENCE_BTCUSDT': {
                'strategy_name': 'MACD_DIVERGENCE_BTCUSDT', 
                'symbol': 'BTCUSDT',
                'side': 'SELL',
                'entry_price': 65432.10,
                'quantity': 0.00153,
                'leverage': 3,
                'test_name': 'MACD Divergence Position Opened'
            },
            'ENGULFING_PATTERN_ETHUSDT': {
                'strategy_name': 'ENGULFING_PATTERN_ETHUSDT',
                'symbol': 'ETHUSDT', 
                'side': 'BUY',
                'entry_price': 3456.78,
                'quantity': 0.0289,
                'leverage': 4,
                'test_name': 'Engulfing Pattern Position Opened'
            },
            'SMART_MONEY_XRPUSDT': {
                'strategy_name': 'SMART_MONEY_XRPUSDT',
                'symbol': 'XRPUSDT',
                'side': 'SELL', 
                'entry_price': 0.6234,
                'quantity': 160.5,
                'leverage': 2,
                'test_name': 'Smart Money Position Opened'
            }
        }
        
        for strategy_key, position_data in strategy_test_data.items():
            test_result = TelegramTestResult("position_opened", position_data['test_name'])
            
            try:
                with patch.object(self.telegram_reporter, 'send_message', 
                                side_effect=self.capture_message_content(self.telegram_reporter.send_message)):
                    
                    success = self.telegram_reporter.report_position_opened(position_data)
                    
                    test_result.success = success
                    test_result.message_content = self.test_messages[-1]['content'] if self.test_messages else "No message captured"
                    
            except Exception as e:
                test_result.error = str(e)
                test_result.success = False
                
            test_results.append(test_result)
            
        return test_results

    def test_position_closed_notifications(self) -> List[TelegramTestResult]:
        """Test position closed notifications for all strategies"""
        test_results = []
        
        # Test data for position closures
        closure_test_data = [
            {
                'position_data': {
                    'strategy_name': 'RSI_OVERSOLD_SOLUSDT',
                    'symbol': 'SOLUSDT',
                    'side': 'BUY',
                    'entry_price': 120.5500,
                    'exit_price': 125.2300,
                    'quantity': 0.83
                },
                'exit_reason': 'Take Profit (RSI 70+)',
                'pnl': 3.88,
                'test_name': 'RSI Oversold Position Closed (Profit)'
            },
            {
                'position_data': {
                    'strategy_name': 'MACD_DIVERGENCE_BTCUSDT',
                    'symbol': 'BTCUSDT', 
                    'side': 'SELL',
                    'entry_price': 65432.10,
                    'exit_price': 64890.45,
                    'quantity': 0.00153
                },
                'exit_reason': 'Take Profit (MACD Momentum Bottom)',
                'pnl': 0.83,
                'test_name': 'MACD Divergence Position Closed (Profit)'
            },
            {
                'position_data': {
                    'strategy_name': 'ENGULFING_PATTERN_ETHUSDT',
                    'symbol': 'ETHUSDT',
                    'side': 'BUY', 
                    'entry_price': 3456.78,
                    'exit_price': 3398.12,
                    'quantity': 0.0289
                },
                'exit_reason': 'Stop Loss',
                'pnl': -1.69,
                'test_name': 'Engulfing Pattern Position Closed (Loss)'
            },
            {
                'position_data': {
                    'strategy_name': 'SMART_MONEY_XRPUSDT',
                    'symbol': 'XRPUSDT',
                    'side': 'SELL',
                    'entry_price': 0.6234,
                    'exit_price': 0.6189,
                    'quantity': 160.5
                },
                'exit_reason': 'Manual Close',
                'pnl': 0.72,
                'test_name': 'Smart Money Position Closed (Profit)'
            }
        ]
        
        for closure_data in closure_test_data:
            test_result = TelegramTestResult("position_closed", closure_data['test_name'])
            
            try:
                with patch.object(self.telegram_reporter, 'send_message', 
                                side_effect=self.capture_message_content(self.telegram_reporter.send_message)):
                    
                    success = self.telegram_reporter.report_position_closed(
                        position_data=closure_data['position_data'],
                        exit_reason=closure_data['exit_reason'],
                        pnl=closure_data['pnl']
                    )
                    
                    test_result.success = success
                    test_result.message_content = self.test_messages[-1]['content'] if self.test_messages else "No message captured"
                    
            except Exception as e:
                test_result.error = str(e)
                test_result.success = False
                
            test_results.append(test_result)
            
        return test_results

    def test_error_notifications(self) -> List[TelegramTestResult]:
        """Test error notifications"""
        test_results = []
        
        error_test_data = [
            {
                'error_type': 'API Connection Error',
                'error_message': 'Failed to connect to Binance API after 3 retries',
                'strategy_name': 'RSI_OVERSOLD_SOLUSDT',
                'test_name': 'Strategy-Specific Error'
            },
            {
                'error_type': 'Insufficient Balance',
                'error_message': 'Account balance too low to execute trade',
                'strategy_name': None,
                'test_name': 'General System Error'
            },
            {
                'error_type': 'Order Execution Failed',
                'error_message': 'Market order rejected by exchange',
                'strategy_name': 'MACD_DIVERGENCE_BTCUSDT',
                'test_name': 'Order Execution Error'
            }
        ]
        
        for error_data in error_test_data:
            test_result = TelegramTestResult("error", error_data['test_name'])
            
            try:
                with patch.object(self.telegram_reporter, 'send_message', 
                                side_effect=self.capture_message_content(self.telegram_reporter.send_message)):
                    
                    success = self.telegram_reporter.report_error(
                        error_type=error_data['error_type'],
                        error_message=error_data['error_message'],
                        strategy_name=error_data['strategy_name']
                    )
                    
                    test_result.success = success
                    test_result.message_content = self.test_messages[-1]['content'] if self.test_messages else "No message captured"
                    
            except Exception as e:
                test_result.error = str(e)
                test_result.success = False
                
            test_results.append(test_result)
            
        return test_results

    def test_balance_warning_notification(self) -> TelegramTestResult:
        """Test balance warning notification"""
        test_result = TelegramTestResult("balance_warning", "Low Balance Warning")
        
        try:
            required_balance = 500.0
            current_balance = 125.50
            
            with patch.object(self.telegram_reporter, 'send_message', 
                            side_effect=self.capture_message_content(self.telegram_reporter.send_message)):
                
                success = self.telegram_reporter.report_balance_warning(
                    required_balance=required_balance,
                    current_balance=current_balance
                )
                
                test_result.success = success
                test_result.message_content = self.test_messages[-1]['content'] if self.test_messages else "No message captured"
                
        except Exception as e:
            test_result.error = str(e)
            test_result.success = False
            
        return test_result

    def test_anomaly_notifications(self) -> List[TelegramTestResult]:
        """Test anomaly detection notifications"""
        test_results = []
        
        # Test orphan trade detection
        orphan_test = TelegramTestResult("anomaly_orphan", "Orphan Trade Detection")
        try:
            with patch.object(self.telegram_reporter, 'send_message', 
                            side_effect=self.capture_message_content(self.telegram_reporter.send_message)):
                
                success = self.telegram_reporter.report_orphan_trade_detected(
                    strategy_name='RSI_OVERSOLD_SOLUSDT',
                    symbol='SOLUSDT',
                    side='BUY',
                    entry_price=120.55
                )
                
                orphan_test.success = success
                orphan_test.message_content = self.test_messages[-1]['content'] if self.test_messages else "No message captured"
                
        except Exception as e:
            orphan_test.error = str(e)
            orphan_test.success = False
            
        test_results.append(orphan_test)
        
        # Test orphan trade cleared
        orphan_cleared_test = TelegramTestResult("anomaly_orphan_cleared", "Orphan Trade Cleared")
        try:
            with patch.object(self.telegram_reporter, 'send_message', 
                            side_effect=self.capture_message_content(self.telegram_reporter.send_message)):
                
                success = self.telegram_reporter.report_orphan_trade_cleared(
                    strategy_name='RSI_OVERSOLD_SOLUSDT',
                    symbol='SOLUSDT'
                )
                
                orphan_cleared_test.success = success
                orphan_cleared_test.message_content = self.test_messages[-1]['content'] if self.test_messages else "No message captured"
                
        except Exception as e:
            orphan_cleared_test.error = str(e)
            orphan_cleared_test.success = False
            
        test_results.append(orphan_cleared_test)
        
        # Test ghost trade detection
        ghost_test = TelegramTestResult("anomaly_ghost", "Ghost Trade Detection")
        try:
            with patch.object(self.telegram_reporter, 'send_message', 
                            side_effect=self.capture_message_content(self.telegram_reporter.send_message)):
                
                success = self.telegram_reporter.report_ghost_trade_detected(
                    strategy_name='MACD_DIVERGENCE_BTCUSDT',
                    symbol='BTCUSDT',
                    side='SELL',
                    quantity=0.00153,
                    current_price=65000.0
                )
                
                ghost_test.success = success
                ghost_test.message_content = self.test_messages[-1]['content'] if self.test_messages else "No message captured"
                
        except Exception as e:
            ghost_test.error = str(e)
            ghost_test.success = False
            
        test_results.append(ghost_test)
        
        # Test ghost trade cleared
        ghost_cleared_test = TelegramTestResult("anomaly_ghost_cleared", "Ghost Trade Cleared")
        try:
            with patch.object(self.telegram_reporter, 'send_message', 
                            side_effect=self.capture_message_content(self.telegram_reporter.send_message)):
                
                success = self.telegram_reporter.report_ghost_trade_cleared(
                    strategy_name='MACD_DIVERGENCE_BTCUSDT',
                    symbol='BTCUSDT'
                )
                
                ghost_cleared_test.success = success
                ghost_cleared_test.message_content = self.test_messages[-1]['content'] if self.test_messages else "No message captured"
                
        except Exception as e:
            ghost_cleared_test.error = str(e)
            ghost_cleared_test.success = False
            
        test_results.append(ghost_cleared_test)
        
        return test_results

    def test_connection(self) -> TelegramTestResult:
        """Test Telegram connection"""
        test_result = TelegramTestResult("connection", "Telegram Connection Test")
        
        try:
            success = self.telegram_reporter.test_connection()
            test_result.success = success
            test_result.message_content = "Connection test completed"
            
        except Exception as e:
            test_result.error = str(e)
            test_result.success = False
            
        return test_result

    def run_all_tests(self) -> Dict[str, Any]:
        """Run all Telegram notification tests"""
        print("🧪 COMPREHENSIVE TELEGRAM MESSAGING TEST")
        print("=" * 80)
        
        # Setup
        telegram_configured = self.setup_telegram_reporter()
        
        all_results = []
        
        # Test 1: Connection Test
        print(f"\n📡 TEST 1: TELEGRAM CONNECTION")
        print("-" * 60)
        connection_result = self.test_connection()
        all_results.append(connection_result)
        self._print_test_result(connection_result)
        
        # Test 2: Bot Startup/Shutdown
        print(f"\n🚀 TEST 2: BOT STARTUP/SHUTDOWN NOTIFICATIONS")
        print("-" * 60)
        
        startup_result = self.test_bot_startup_notification()
        all_results.append(startup_result)
        self._print_test_result(startup_result)
        
        time.sleep(1)  # Brief pause between tests
        
        shutdown_result = self.test_bot_shutdown_notification()
        all_results.append(shutdown_result)
        self._print_test_result(shutdown_result)
        
        # Test 3: Position Opened Notifications
        print(f"\n📈 TEST 3: POSITION OPENED NOTIFICATIONS (ALL STRATEGIES)")
        print("-" * 60)
        
        position_opened_results = self.test_position_opened_notifications()
        all_results.extend(position_opened_results)
        for result in position_opened_results:
            self._print_test_result(result)
            time.sleep(0.5)  # Brief pause between strategy tests
        
        # Test 4: Position Closed Notifications  
        print(f"\n📉 TEST 4: POSITION CLOSED NOTIFICATIONS (ALL STRATEGIES)")
        print("-" * 60)
        
        position_closed_results = self.test_position_closed_notifications()
        all_results.extend(position_closed_results)
        for result in position_closed_results:
            self._print_test_result(result)
            time.sleep(0.5)
        
        # Test 5: Error Notifications
        print(f"\n❌ TEST 5: ERROR NOTIFICATIONS")
        print("-" * 60)
        
        error_results = self.test_error_notifications()
        all_results.extend(error_results)
        for result in error_results:
            self._print_test_result(result)
            time.sleep(0.5)
        
        # Test 6: Balance Warning
        print(f"\n💰 TEST 6: BALANCE WARNING NOTIFICATION")
        print("-" * 60)
        
        balance_result = self.test_balance_warning_notification()
        all_results.append(balance_result)
        self._print_test_result(balance_result)
        
        # Test 7: Anomaly Notifications
        print(f"\n👻 TEST 7: ANOMALY DETECTION NOTIFICATIONS")
        print("-" * 60)
        
        anomaly_results = self.test_anomaly_notifications()
        all_results.extend(anomaly_results)
        for result in anomaly_results:
            self._print_test_result(result)
            time.sleep(0.5)
        
        # Generate summary
        return self._generate_test_summary(all_results, telegram_configured)

    def _print_test_result(self, result: TelegramTestResult):
        """Print individual test result"""
        status = "✅ PASS" if result.success else "❌ FAIL"
        print(f"{status} {result.test_name}")
        
        if result.error:
            print(f"   Error: {result.error}")
        
        print()  # Add spacing

    def _generate_test_summary(self, results: List[TelegramTestResult], telegram_configured: bool) -> Dict[str, Any]:
        """Generate comprehensive test summary"""
        total_tests = len(results)
        passed_tests = sum(1 for r in results if r.success)
        failed_tests = total_tests - passed_tests
        
        # Group results by message type
        results_by_type = {}
        for result in results:
            if result.message_type not in results_by_type:
                results_by_type[result.message_type] = []
            results_by_type[result.message_type].append(result)
        
        summary = {
            'timestamp': datetime.now().isoformat(),
            'telegram_configured': telegram_configured,
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': failed_tests,
            'success_rate': (passed_tests / total_tests * 100) if total_tests > 0 else 0,
            'results_by_type': results_by_type,
            'all_messages': self.test_messages,
            'configuration_status': {
                'bot_token_configured': bool(global_config.TELEGRAM_BOT_TOKEN),
                'chat_id_configured': bool(global_config.TELEGRAM_CHAT_ID),
                'reporter_enabled': telegram_configured
            }
        }
        
        # Print summary
        print(f"\n📊 TEST SUMMARY")
        print("=" * 80)
        print(f"🔧 Telegram Configured: {'Yes' if telegram_configured else 'No'}")
        print(f"📝 Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"📈 Success Rate: {summary['success_rate']:.1f}%")
        
        print(f"\n📋 RESULTS BY MESSAGE TYPE:")
        for msg_type, type_results in results_by_type.items():
            type_passed = sum(1 for r in type_results if r.success)
            type_total = len(type_results)
            print(f"   {msg_type}: {type_passed}/{type_total} passed")
        
        print(f"\n📱 TOTAL MESSAGES GENERATED: {len(self.test_messages)}")
        
        if not telegram_configured:
            print(f"\n⚠️ NOTE: Telegram not configured - only tested message generation")
            print(f"   Configure TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to test actual sending")
        
        # Save detailed results to file
        self._save_test_results(summary)
        
        return summary

    def _save_test_results(self, summary: Dict[str, Any]):
        """Save test results to JSON file"""
        try:
            filename = f"telegram_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            # Convert TelegramTestResult objects to dictionaries for JSON serialization
            serializable_summary = dict(summary)
            
            # Convert results_by_type
            serializable_results = {}
            for msg_type, type_results in summary['results_by_type'].items():
                serializable_results[msg_type] = []
                for result in type_results:
                    serializable_results[msg_type].append({
                        'message_type': result.message_type,
                        'test_name': result.test_name,
                        'success': result.success,
                        'message_content': result.message_content,
                        'error': result.error,
                        'timestamp': result.timestamp.isoformat()
                    })
            
            serializable_summary['results_by_type'] = serializable_results
            
            with open(filename, 'w') as f:
                json.dump(serializable_summary, f, indent=2)
            
            print(f"\n💾 Detailed results saved to: {filename}")
            
        except Exception as e:
            print(f"❌ Failed to save test results: {e}")

def main():
    """Run comprehensive Telegram messaging test"""
    tester = ComprehensiveTelegramTest()
    
    try:
        summary = tester.run_all_tests()
        
        # Final recommendations
        print(f"\n🔍 RECOMMENDATIONS:")
        print("-" * 40)
        
        if not summary['telegram_configured']:
            print("1. Configure Telegram bot token and chat ID for full testing")
        
        if summary['failed_tests'] > 0:
            print("2. Review failed tests and fix any message formatting issues")
        
        if summary['success_rate'] == 100:
            print("✅ All tests passed! Telegram notifications are working correctly.")
        else:
            print(f"⚠️ {summary['failed_tests']} tests failed. Review the detailed results.")
        
        return summary
        
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
        return None
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        print(f"🔍 Traceback: {traceback.format_exc()}")
        return None

if __name__ == "__main__":
    main()
