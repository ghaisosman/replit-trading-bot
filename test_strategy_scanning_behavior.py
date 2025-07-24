
#!/usr/bin/env python3
"""
Strategy Scanning Behavior Test
Tests whether disabling strategies actually stops entry scanning and enabling resumes it.
Monitors real-time bot behavior to verify strategies are truly paused/resumed.
"""

import requests
import json
import time
import threading
import queue
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import logging

class StrategyScanningTest:
    """Test strategy scanning behavior when enabled/disabled"""
    
    def __init__(self, base_url="http://localhost:5000"):
        self.base_url = base_url
        self.test_results = {}
        self.monitoring_data = {}
        self.stop_monitoring = threading.Event()
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
    def get_all_strategies(self) -> Optional[Dict[str, Any]]:
        """Get all available strategies"""
        try:
            response = requests.get(f"{self.base_url}/api/strategies", timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            self.logger.error(f"Error getting strategies: {e}")
            return None
    
    def get_bot_status(self) -> Optional[Dict[str, Any]]:
        """Get current bot status including strategy activities"""
        try:
            response = requests.get(f"{self.base_url}/api/bot_status", timeout=5)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            return None
    
    def get_trading_logs(self) -> Optional[List[str]]:
        """Get recent trading logs"""
        try:
            response = requests.get(f"{self.base_url}/api/logs", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get('logs', [])
            return None
        except Exception as e:
            return None
    
    def disable_strategy(self, strategy_name: str) -> bool:
        """Disable a strategy"""
        try:
            response = requests.post(f"{self.base_url}/api/strategies/{strategy_name}/disable",
                                   headers={'Content-Type': 'application/json'},
                                   timeout=15)
            if response.status_code == 200:
                result = response.json()
                return result.get('success', False)
            return False
        except Exception as e:
            self.logger.error(f"Error disabling {strategy_name}: {e}")
            return False
    
    def enable_strategy(self, strategy_name: str) -> bool:
        """Enable a strategy"""
        try:
            response = requests.post(f"{self.base_url}/api/strategies/{strategy_name}/enable",
                                   headers={'Content-Type': 'application/json'},
                                   timeout=15)
            if response.status_code == 200:
                result = response.json()
                return result.get('success', False)
            return False
        except Exception as e:
            self.logger.error(f"Error enabling {strategy_name}: {e}")
            return False
    
    def monitor_strategy_activity(self, strategy_name: str, duration_seconds: int = 90):
        """Monitor strategy activity for scanning behavior"""
        print(f"📊 Monitoring {strategy_name} activity for {duration_seconds} seconds...")
        
        activity_data = {
            'log_entries': [],
            'status_checks': [],
            'scanning_detected': False,
            'market_assessments': 0,
            'signal_evaluations': 0,
            'start_time': datetime.now(),
            'end_time': None
        }
        
        start_time = time.time()
        last_log_count = 0
        
        while (time.time() - start_time) < duration_seconds and not self.stop_monitoring.is_set():
            try:
                # Get current logs
                logs = self.get_trading_logs()
                if logs and len(logs) > last_log_count:
                    new_logs = logs[last_log_count:]
                    last_log_count = len(logs)
                    
                    for log_entry in new_logs:
                        log_lower = log_entry.lower()
                        
                        # Check if this log is related to our strategy
                        if strategy_name.lower() in log_lower:
                            activity_data['log_entries'].append({
                                'timestamp': datetime.now(),
                                'message': log_entry,
                                'type': self._classify_log_entry(log_entry)
                            })
                            
                            # Count different types of activities
                            if any(keyword in log_lower for keyword in ['scanning', 'evaluating', 'signal', 'entry']):
                                activity_data['scanning_detected'] = True
                                
                            if 'market assessment' in log_lower or 'analyzing' in log_lower:
                                activity_data['market_assessments'] += 1
                                
                            if 'signal' in log_lower or 'entry' in log_lower:
                                activity_data['signal_evaluations'] += 1
                
                # Get bot status
                status = self.get_bot_status()
                if status:
                    activity_data['status_checks'].append({
                        'timestamp': datetime.now(),
                        'status': status
                    })
                
                time.sleep(2)  # Check every 2 seconds
                
            except Exception as e:
                self.logger.debug(f"Monitoring error: {e}")
                time.sleep(1)
        
        activity_data['end_time'] = datetime.now()
        activity_data['duration'] = duration_seconds
        
        return activity_data
    
    def _classify_log_entry(self, log_entry: str) -> str:
        """Classify log entry type"""
        log_lower = log_entry.lower()
        
        if 'scanning' in log_lower or 'evaluating' in log_lower:
            return 'scanning'
        elif 'signal' in log_lower or 'entry' in log_lower:
            return 'signal'
        elif 'market assessment' in log_lower:
            return 'assessment'
        elif 'disabled' in log_lower or 'enabled' in log_lower:
            return 'status_change'
        elif 'error' in log_lower:
            return 'error'
        else:
            return 'general'
    
    def analyze_activity_data(self, activity_data: Dict, expected_state: str) -> Dict[str, Any]:
        """Analyze activity data to determine if strategy was actually scanning"""
        analysis = {
            'expected_state': expected_state,
            'total_log_entries': len(activity_data['log_entries']),
            'scanning_detected': activity_data['scanning_detected'],
            'market_assessments': activity_data['market_assessments'],
            'signal_evaluations': activity_data['signal_evaluations'],
            'duration': activity_data['duration'],
            'compliant': False,
            'evidence': []
        }
        
        # Analyze log entries by type
        log_types = {}
        for entry in activity_data['log_entries']:
            log_type = entry['type']
            if log_type not in log_types:
                log_types[log_type] = 0
            log_types[log_type] += 1
        
        analysis['log_types'] = log_types
        
        # Determine compliance based on expected state
        if expected_state == 'disabled':
            # When disabled, we should see minimal or no scanning activity
            if activity_data['market_assessments'] == 0 and activity_data['signal_evaluations'] == 0:
                analysis['compliant'] = True
                analysis['evidence'].append("✅ No market assessments detected")
                analysis['evidence'].append("✅ No signal evaluations detected")
            else:
                analysis['compliant'] = False
                analysis['evidence'].append(f"❌ Market assessments detected: {activity_data['market_assessments']}")
                analysis['evidence'].append(f"❌ Signal evaluations detected: {activity_data['signal_evaluations']}")
                
        elif expected_state == 'enabled':
            # When enabled, we should see active scanning
            if activity_data['market_assessments'] > 0 or activity_data['signal_evaluations'] > 0 or activity_data['scanning_detected']:
                analysis['compliant'] = True
                analysis['evidence'].append(f"✅ Market assessments detected: {activity_data['market_assessments']}")
                analysis['evidence'].append(f"✅ Signal evaluations detected: {activity_data['signal_evaluations']}")
                analysis['evidence'].append(f"✅ Scanning activity detected: {activity_data['scanning_detected']}")
            else:
                analysis['compliant'] = False
                analysis['evidence'].append("❌ No scanning activity detected")
                analysis['evidence'].append("❌ No market assessments detected")
        
        return analysis
    
    def test_strategy_scanning_behavior(self, strategy_name: str) -> Dict[str, Any]:
        """Test complete scanning behavior cycle for a strategy"""
        print(f"\n{'='*80}")
        print(f"🎯 TESTING STRATEGY SCANNING BEHAVIOR: {strategy_name.upper()}")
        print(f"{'='*80}")
        
        test_result = {
            'strategy': strategy_name,
            'test_start': datetime.now(),
            'phases': {},
            'overall_success': False,
            'summary': {}
        }
        
        try:
            # Phase 1: Enable strategy and monitor for active scanning
            print(f"\n📊 PHASE 1: Enable strategy and verify scanning activity")
            print(f"────────────────────────────────────────────────────────")
            
            enable_success = self.enable_strategy(strategy_name)
            if not enable_success:
                test_result['phases']['enable'] = {'success': False, 'error': 'Failed to enable strategy'}
                return test_result
            
            print(f"✅ Strategy {strategy_name} enabled successfully")
            time.sleep(5)  # Wait for changes to take effect
            
            # Monitor for active scanning
            enabled_activity = self.monitor_strategy_activity(strategy_name, 90)
            enabled_analysis = self.analyze_activity_data(enabled_activity, 'enabled')
            
            test_result['phases']['enabled_monitoring'] = {
                'activity_data': enabled_activity,
                'analysis': enabled_analysis,
                'success': enabled_analysis['compliant']
            }
            
            if enabled_analysis['compliant']:
                print(f"✅ ENABLED STATE VERIFIED: Strategy is actively scanning")
                for evidence in enabled_analysis['evidence']:
                    print(f"   {evidence}")
            else:
                print(f"❌ ENABLED STATE FAILED: Strategy not scanning as expected")
                for evidence in enabled_analysis['evidence']:
                    print(f"   {evidence}")
            
            # Phase 2: Disable strategy and monitor for stopped scanning
            print(f"\n📊 PHASE 2: Disable strategy and verify scanning stops")
            print(f"────────────────────────────────────────────────────────")
            
            disable_success = self.disable_strategy(strategy_name)
            if not disable_success:
                test_result['phases']['disable'] = {'success': False, 'error': 'Failed to disable strategy'}
                return test_result
            
            print(f"🔴 Strategy {strategy_name} disabled successfully")
            time.sleep(5)  # Wait for changes to take effect
            
            # Monitor for stopped scanning
            disabled_activity = self.monitor_strategy_activity(strategy_name, 90)
            disabled_analysis = self.analyze_activity_data(disabled_activity, 'disabled')
            
            test_result['phases']['disabled_monitoring'] = {
                'activity_data': disabled_activity,
                'analysis': disabled_analysis,
                'success': disabled_analysis['compliant']
            }
            
            if disabled_analysis['compliant']:
                print(f"✅ DISABLED STATE VERIFIED: Strategy scanning stopped")
                for evidence in disabled_analysis['evidence']:
                    print(f"   {evidence}")
            else:
                print(f"❌ DISABLED STATE FAILED: Strategy still scanning when disabled")
                for evidence in disabled_analysis['evidence']:
                    print(f"   {evidence}")
            
            # Phase 3: Re-enable strategy and verify scanning resumes
            print(f"\n📊 PHASE 3: Re-enable strategy and verify scanning resumes")
            print(f"────────────────────────────────────────────────────────")
            
            reenable_success = self.enable_strategy(strategy_name)
            if not reenable_success:
                test_result['phases']['reenable'] = {'success': False, 'error': 'Failed to re-enable strategy'}
                return test_result
            
            print(f"🟢 Strategy {strategy_name} re-enabled successfully")
            time.sleep(5)  # Wait for changes to take effect
            
            # Monitor for resumed scanning
            reenabled_activity = self.monitor_strategy_activity(strategy_name, 90)
            reenabled_analysis = self.analyze_activity_data(reenabled_activity, 'enabled')
            
            test_result['phases']['reenabled_monitoring'] = {
                'activity_data': reenabled_activity,
                'analysis': reenabled_analysis,
                'success': reenabled_analysis['compliant']
            }
            
            if reenabled_analysis['compliant']:
                print(f"✅ RE-ENABLED STATE VERIFIED: Strategy scanning resumed")
                for evidence in reenabled_analysis['evidence']:
                    print(f"   {evidence}")
            else:
                print(f"❌ RE-ENABLED STATE FAILED: Strategy scanning did not resume")
                for evidence in reenabled_analysis['evidence']:
                    print(f"   {evidence}")
            
            # Overall assessment
            all_phases_passed = (
                enabled_analysis['compliant'] and 
                disabled_analysis['compliant'] and 
                reenabled_analysis['compliant']
            )
            
            test_result['overall_success'] = all_phases_passed
            test_result['test_end'] = datetime.now()
            
            # Summary
            test_result['summary'] = {
                'enabled_scanning': enabled_analysis['compliant'],
                'disabled_scanning_stopped': disabled_analysis['compliant'],
                'reenabled_scanning_resumed': reenabled_analysis['compliant'],
                'total_phases': 3,
                'passed_phases': sum([
                    enabled_analysis['compliant'],
                    disabled_analysis['compliant'],
                    reenabled_analysis['compliant']
                ])
            }
            
            print(f"\n{'='*80}")
            if all_phases_passed:
                print(f"✅ {strategy_name.upper()} - ALL PHASES PASSED")
                print(f"   ✅ Enabled: Active scanning detected")
                print(f"   ✅ Disabled: Scanning stopped")  
                print(f"   ✅ Re-enabled: Scanning resumed")
            else:
                print(f"❌ {strategy_name.upper()} - SOME PHASES FAILED")
                print(f"   {'✅' if enabled_analysis['compliant'] else '❌'} Enabled: {'Active scanning' if enabled_analysis['compliant'] else 'No scanning detected'}")
                print(f"   {'✅' if disabled_analysis['compliant'] else '❌'} Disabled: {'Scanning stopped' if disabled_analysis['compliant'] else 'Still scanning'}")
                print(f"   {'✅' if reenabled_analysis['compliant'] else '❌'} Re-enabled: {'Scanning resumed' if reenabled_analysis['compliant'] else 'No scanning detected'}")
            print(f"{'='*80}")
            
            return test_result
            
        except Exception as e:
            self.logger.error(f"Error testing {strategy_name}: {e}")
            test_result['error'] = str(e)
            return test_result
    
    def test_all_strategies(self):
        """Test scanning behavior for all strategies"""
        print("🔬 STRATEGY SCANNING BEHAVIOR COMPREHENSIVE TEST")
        print("=" * 100)
        print(f"🕐 Test started at: {datetime.now()}")
        print(f"🌐 Testing against: {self.base_url}")
        print()
        
        # Get available strategies
        strategies = self.get_all_strategies()
        if not strategies:
            print("❌ Could not retrieve strategies from dashboard")
            return
        
        strategy_names = list(strategies.keys())
        print(f"📋 Found {len(strategy_names)} strategies: {strategy_names}")
        print()
        
        # Test each strategy
        test_results = {}
        passed_strategies = []
        failed_strategies = []
        
        for i, strategy_name in enumerate(strategy_names, 1):
            print(f"\n🎯 TESTING STRATEGY {i}/{len(strategy_names)}: {strategy_name}")
            print("─" * 100)
            
            try:
                result = self.test_strategy_scanning_behavior(strategy_name)
                test_results[strategy_name] = result
                
                if result.get('overall_success', False):
                    passed_strategies.append(strategy_name)
                else:
                    failed_strategies.append(strategy_name)
                    
            except Exception as e:
                print(f"❌ Critical error testing {strategy_name}: {e}")
                failed_strategies.append(strategy_name)
                test_results[strategy_name] = {
                    'strategy': strategy_name,
                    'error': str(e),
                    'overall_success': False
                }
            
            # Wait between strategies
            if i < len(strategy_names):
                print(f"\n⏳ Waiting 10 seconds before next strategy...")
                time.sleep(10)
        
        # Final summary
        self.print_final_summary(test_results, passed_strategies, failed_strategies)
        
        # Save results
        self.save_results(test_results)
        
        return test_results
    
    def print_final_summary(self, test_results: Dict, passed_strategies: List, failed_strategies: List):
        """Print final test summary"""
        total_strategies = len(test_results)
        passed_count = len(passed_strategies)
        failed_count = len(failed_strategies)
        
        print("\n" + "=" * 100)
        print("📊 FINAL TEST SUMMARY")
        print("=" * 100)
        print(f"🕐 Test completed at: {datetime.now()}")
        print(f"📈 Total strategies tested: {total_strategies}")
        print(f"✅ Passed: {passed_count}")
        print(f"❌ Failed: {failed_count}")
        print(f"📊 Success rate: {(passed_count/total_strategies)*100:.1f}%")
        print()
        
        if passed_strategies:
            print("✅ PASSED STRATEGIES:")
            for strategy in passed_strategies:
                print(f"   ✅ {strategy} - Scanning behavior works correctly")
        
        if failed_strategies:
            print("\n❌ FAILED STRATEGIES:")
            for strategy in failed_strategies:
                result = test_results.get(strategy, {})
                summary = result.get('summary', {})
                if summary:
                    phases_passed = summary.get('passed_phases', 0)
                    total_phases = summary.get('total_phases', 3)
                    print(f"   ❌ {strategy} - {phases_passed}/{total_phases} phases passed")
                else:
                    print(f"   ❌ {strategy} - Test failed with error")
        
        print("\n" + "=" * 100)
    
    def save_results(self, results: Dict):
        """Save test results to file"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"strategy_scanning_test_results_{timestamp}.json"
            
            # Prepare results for JSON serialization
            json_results = {}
            for strategy, result in results.items():
                json_results[strategy] = self._serialize_result(result)
            
            test_metadata = {
                "test_type": "strategy_scanning_behavior",
                "start_time": datetime.now().isoformat(),
                "base_url": self.base_url,
                "total_strategies": len(results),
                "passed_strategies": len([r for r in results.values() if r.get('overall_success', False)]),
                "failed_strategies": len([r for r in results.values() if not r.get('overall_success', False)])
            }
            
            output = {
                "test_metadata": test_metadata,
                "results": json_results
            }
            
            with open(filename, 'w') as f:
                json.dump(output, f, indent=2)
            
            print(f"💾 Test results saved to: {filename}")
            
        except Exception as e:
            print(f"⚠️  Could not save results to file: {e}")
    
    def _serialize_result(self, result: Dict) -> Dict:
        """Convert result to JSON-serializable format"""
        serialized = {}
        for key, value in result.items():
            if isinstance(value, datetime):
                serialized[key] = value.isoformat()
            elif isinstance(value, dict):
                serialized[key] = self._serialize_result(value)
            elif isinstance(value, list):
                serialized[key] = [self._serialize_result(item) if isinstance(item, dict) else str(item) for item in value]
            else:
                serialized[key] = value
        return serialized

def main():
    """Main test execution"""
    print("🔬 STRATEGY SCANNING BEHAVIOR TEST")
    print("=" * 100)
    print("This test verifies that:")
    print("  1. When a strategy is enabled, it actively scans for entry opportunities")
    print("  2. When a strategy is disabled, it stops scanning completely")
    print("  3. When a strategy is re-enabled, it resumes scanning")
    print("=" * 100)
    
    # Initialize test suite
    tester = StrategyScanningTest()
    
    # Check if web dashboard is running
    try:
        response = requests.get(f"{tester.base_url}/api/strategies", timeout=5)
        if response.status_code != 200:
            print(f"❌ Web dashboard not accessible at {tester.base_url}")
            print("   Please make sure the trading bot and web dashboard are running")
            return
    except Exception as e:
        print(f"❌ Cannot connect to web dashboard at {tester.base_url}")
        print(f"   Error: {e}")
        print("   Please make sure the trading bot and web dashboard are running")
        return
    
    print(f"✅ Web dashboard accessible at {tester.base_url}")
    print()
    
    # Run comprehensive test
    results = tester.test_all_strategies()
    
    print("\n🎯 TEST COMPLETED!")
    print("Check the generated JSON file for detailed results.")

if __name__ == "__main__":
    main()
