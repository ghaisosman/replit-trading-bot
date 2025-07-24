
#!/usr/bin/env python3
"""
Strategy Enable/Disable Test
Tests the enable/disable functionality for all strategies through the web dashboard API
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, List, Any

class StrategyToggleTest:
    def __init__(self, base_url="http://localhost:5000"):
        self.base_url = base_url
        self.results = {}
        self.test_start_time = datetime.now()
        
    def print_header(self, text: str):
        """Print formatted header"""
        print(f"\n{'='*80}")
        print(f"🧪 {text}")
        print(f"{'='*80}")
        
    def print_section(self, text: str):
        """Print formatted section"""
        print(f"\n{'─'*60}")
        print(f"📋 {text}")
        print(f"{'─'*60}")
        
    def print_result(self, strategy: str, action: str, success: bool, message: str = ""):
        """Print test result"""
        status = "✅" if success else "❌"
        print(f"{status} {strategy} - {action}: {message}")
        
    def get_all_strategies(self) -> Dict[str, Any]:
        """Get all available strategies from the API"""
        try:
            response = requests.get(f"{self.base_url}/api/strategies", timeout=10)
            if response.status_code == 200:
                strategies = response.json()
                print(f"📊 Found {len(strategies)} strategies: {list(strategies.keys())}")
                return strategies
            else:
                print(f"❌ Failed to get strategies: HTTP {response.status_code}")
                return {}
        except Exception as e:
            print(f"❌ Error getting strategies: {e}")
            return {}
    
    def test_strategy_disable(self, strategy_name: str) -> Dict[str, Any]:
        """Test disabling a specific strategy"""
        try:
            print(f"\n🔍 Testing DISABLE for {strategy_name}...")
            
            url = f"{self.base_url}/api/strategies/{strategy_name}/disable"
            response = requests.post(url, 
                                   headers={'Content-Type': 'application/json'},
                                   timeout=15)
            
            result = {
                'strategy': strategy_name,
                'action': 'disable',
                'status_code': response.status_code,
                'success': False,
                'response_data': {},
                'error': None
            }
            
            if response.status_code == 200:
                try:
                    result['response_data'] = response.json()
                    result['success'] = result['response_data'].get('success', False)
                    
                    if result['success']:
                        self.print_result(strategy_name, "DISABLE", True, "Successfully disabled")
                    else:
                        error_msg = result['response_data'].get('message', 'Unknown error')
                        self.print_result(strategy_name, "DISABLE", False, f"API returned success=false: {error_msg}")
                        result['error'] = error_msg
                        
                except json.JSONDecodeError as e:
                    result['error'] = f"JSON decode error: {e}"
                    self.print_result(strategy_name, "DISABLE", False, f"Invalid JSON response: {e}")
            else:
                result['error'] = f"HTTP {response.status_code}: {response.text[:200]}"
                self.print_result(strategy_name, "DISABLE", False, f"HTTP {response.status_code}")
                
            return result
            
        except requests.exceptions.Timeout:
            result = {
                'strategy': strategy_name,
                'action': 'disable',
                'success': False,
                'error': 'Request timeout (15s)'
            }
            self.print_result(strategy_name, "DISABLE", False, "Request timeout")
            return result
            
        except Exception as e:
            result = {
                'strategy': strategy_name,
                'action': 'disable',
                'success': False,
                'error': str(e)
            }
            self.print_result(strategy_name, "DISABLE", False, f"Exception: {e}")
            return result
    
    def test_strategy_enable(self, strategy_name: str) -> Dict[str, Any]:
        """Test enabling a specific strategy"""
        try:
            print(f"\n🔍 Testing ENABLE for {strategy_name}...")
            
            url = f"{self.base_url}/api/strategies/{strategy_name}/enable"
            response = requests.post(url, 
                                   headers={'Content-Type': 'application/json'},
                                   timeout=15)
            
            result = {
                'strategy': strategy_name,
                'action': 'enable',
                'status_code': response.status_code,
                'success': False,
                'response_data': {},
                'error': None
            }
            
            if response.status_code == 200:
                try:
                    result['response_data'] = response.json()
                    result['success'] = result['response_data'].get('success', False)
                    
                    if result['success']:
                        self.print_result(strategy_name, "ENABLE", True, "Successfully enabled")
                    else:
                        error_msg = result['response_data'].get('message', 'Unknown error')
                        self.print_result(strategy_name, "ENABLE", False, f"API returned success=false: {error_msg}")
                        result['error'] = error_msg
                        
                except json.JSONDecodeError as e:
                    result['error'] = f"JSON decode error: {e}"
                    self.print_result(strategy_name, "ENABLE", False, f"Invalid JSON response: {e}")
            else:
                result['error'] = f"HTTP {response.status_code}: {response.text[:200]}"
                self.print_result(strategy_name, "ENABLE", False, f"HTTP {response.status_code}")
                
            return result
            
        except requests.exceptions.Timeout:
            result = {
                'strategy': strategy_name,
                'action': 'enable',
                'success': False,
                'error': 'Request timeout (15s)'
            }
            self.print_result(strategy_name, "ENABLE", False, "Request timeout")
            return result
            
        except Exception as e:
            result = {
                'strategy': strategy_name,
                'action': 'enable',
                'success': False,
                'error': str(e)
            }
            self.print_result(strategy_name, "ENABLE", False, f"Exception: {e}")
            return result
    
    def verify_strategy_status(self, strategy_name: str, expected_status: str) -> bool:
        """Verify that a strategy has the expected status"""
        try:
            print(f"🔍 Verifying {strategy_name} status (expecting {expected_status})...")
            
            # Get current strategies
            strategies = self.get_all_strategies()
            if not strategies:
                print(f"❌ Could not get strategies for verification")
                return False
                
            if strategy_name not in strategies:
                print(f"❌ Strategy {strategy_name} not found in strategies list")
                return False
                
            config = strategies[strategy_name]
            
            # Check if strategy is disabled based on assessment_interval
            assessment_interval = config.get('assessment_interval', 60)
            enabled_flag = config.get('enabled', True)
            
            is_disabled = (assessment_interval == 0 or enabled_flag == False)
            current_status = 'disabled' if is_disabled else 'enabled'
            
            success = (current_status == expected_status)
            
            if success:
                print(f"✅ {strategy_name} status verified: {current_status}")
            else:
                print(f"❌ {strategy_name} status mismatch: expected {expected_status}, got {current_status}")
                print(f"   Assessment interval: {assessment_interval}")
                print(f"   Enabled flag: {enabled_flag}")
                
            return success
            
        except Exception as e:
            print(f"❌ Error verifying {strategy_name} status: {e}")
            return False
    
    def test_full_cycle(self, strategy_name: str) -> Dict[str, Any]:
        """Test full disable -> verify -> enable -> verify cycle for a strategy"""
        print(f"\n🔄 Testing FULL CYCLE for {strategy_name}")
        
        cycle_results = {
            'strategy': strategy_name,
            'disable_test': {},
            'disable_verification': False,
            'enable_test': {},
            'enable_verification': False,
            'overall_success': False
        }
        
        # Step 1: Disable strategy
        disable_result = self.test_strategy_disable(strategy_name)
        cycle_results['disable_test'] = disable_result
        
        if disable_result['success']:
            # Wait a moment for the change to propagate
            time.sleep(1)
            
            # Step 2: Verify it's disabled
            cycle_results['disable_verification'] = self.verify_strategy_status(strategy_name, 'disabled')
        
        # Wait between operations
        time.sleep(2)
        
        # Step 3: Enable strategy
        enable_result = self.test_strategy_enable(strategy_name)
        cycle_results['enable_test'] = enable_result
        
        if enable_result['success']:
            # Wait a moment for the change to propagate
            time.sleep(1)
            
            # Step 4: Verify it's enabled
            cycle_results['enable_verification'] = self.verify_strategy_status(strategy_name, 'enabled')
        
        # Overall success: all steps must pass
        cycle_results['overall_success'] = (
            disable_result['success'] and 
            cycle_results['disable_verification'] and
            enable_result['success'] and 
            cycle_results['enable_verification']
        )
        
        if cycle_results['overall_success']:
            print(f"✅ {strategy_name} - FULL CYCLE PASSED")
        else:
            print(f"❌ {strategy_name} - FULL CYCLE FAILED")
        
        return cycle_results
    
    def test_all_strategies(self):
        """Test enable/disable functionality for all strategies"""
        self.print_header("STRATEGY ENABLE/DISABLE COMPREHENSIVE TEST")
        
        print(f"🕐 Test started at: {self.test_start_time}")
        print(f"🌐 Testing against: {self.base_url}")
        
        # Get all available strategies
        self.print_section("Getting Available Strategies")
        strategies = self.get_all_strategies()
        
        if not strategies:
            print("❌ No strategies found. Cannot proceed with testing.")
            return
        
        strategy_names = list(strategies.keys())
        print(f"📋 Will test {len(strategy_names)} strategies: {', '.join(strategy_names)}")
        
        # Test each strategy
        self.print_section("Testing Strategy Toggle Functionality")
        
        for strategy_name in strategy_names:
            try:
                print(f"\n{'='*40}")
                print(f"🎯 TESTING STRATEGY: {strategy_name}")
                print(f"{'='*40}")
                
                # Test full cycle for this strategy
                cycle_result = self.test_full_cycle(strategy_name)
                self.results[strategy_name] = cycle_result
                
                # Add delay between strategies to avoid overwhelming the API
                time.sleep(1)
                
            except Exception as e:
                print(f"❌ Critical error testing {strategy_name}: {e}")
                self.results[strategy_name] = {
                    'strategy': strategy_name,
                    'overall_success': False,
                    'error': f"Critical error: {e}"
                }
        
        # Generate summary report
        self.generate_summary_report()
    
    def generate_summary_report(self):
        """Generate a comprehensive summary report"""
        self.print_header("COMPREHENSIVE TEST SUMMARY REPORT")
        
        test_end_time = datetime.now()
        test_duration = test_end_time - self.test_start_time
        
        print(f"🕐 Test completed at: {test_end_time}")
        print(f"⏱️  Total test duration: {test_duration}")
        
        # Count results
        total_strategies = len(self.results)
        successful_strategies = sum(1 for result in self.results.values() if result.get('overall_success', False))
        failed_strategies = total_strategies - successful_strategies
        
        success_rate = (successful_strategies / total_strategies * 100) if total_strategies > 0 else 0
        
        print(f"\n📊 OVERALL RESULTS:")
        print(f"   Total Strategies Tested: {total_strategies}")
        print(f"   ✅ Successful: {successful_strategies}")
        print(f"   ❌ Failed: {failed_strategies}")
        print(f"   📈 Success Rate: {success_rate:.1f}%")
        
        # Detailed results by strategy
        self.print_section("Detailed Results by Strategy")
        
        for strategy_name, result in self.results.items():
            overall_success = result.get('overall_success', False)
            status_icon = "✅" if overall_success else "❌"
            
            print(f"\n{status_icon} {strategy_name}:")
            
            if overall_success:
                print(f"   ✅ All operations successful")
            else:
                # Show specific failures
                disable_success = result.get('disable_test', {}).get('success', False)
                disable_verify = result.get('disable_verification', False)
                enable_success = result.get('enable_test', {}).get('success', False)
                enable_verify = result.get('enable_verification', False)
                
                print(f"   - Disable API: {'✅' if disable_success else '❌'}")
                print(f"   - Disable Verify: {'✅' if disable_verify else '❌'}")
                print(f"   - Enable API: {'✅' if enable_success else '❌'}")
                print(f"   - Enable Verify: {'✅' if enable_verify else '❌'}")
                
                # Show errors if any
                if 'error' in result:
                    print(f"   ⚠️  Error: {result['error']}")
                
                disable_error = result.get('disable_test', {}).get('error')
                if disable_error:
                    print(f"   ⚠️  Disable Error: {disable_error}")
                    
                enable_error = result.get('enable_test', {}).get('error')
                if enable_error:
                    print(f"   ⚠️  Enable Error: {enable_error}")
        
        # Recommendations
        self.print_section("Recommendations")
        
        if failed_strategies == 0:
            print("🎉 All strategy enable/disable functionality is working perfectly!")
        else:
            print("⚠️  Issues detected with strategy toggle functionality:")
            print("   1. Check web dashboard JavaScript console for errors")
            print("   2. Verify API endpoints are properly implemented")
            print("   3. Check database/config file write permissions")
            print("   4. Review strategy configuration management")
        
        # Save detailed results to file
        self.save_results_to_file()
    
    def save_results_to_file(self):
        """Save detailed test results to a file"""
        try:
            filename = f"strategy_toggle_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            report_data = {
                'test_metadata': {
                    'start_time': self.test_start_time.isoformat(),
                    'end_time': datetime.now().isoformat(),
                    'base_url': self.base_url,
                    'total_strategies': len(self.results)
                },
                'results': self.results,
                'summary': {
                    'total_tested': len(self.results),
                    'successful': sum(1 for r in self.results.values() if r.get('overall_success', False)),
                    'failed': sum(1 for r in self.results.values() if not r.get('overall_success', False))
                }
            }
            
            with open(filename, 'w') as f:
                json.dump(report_data, f, indent=2, default=str)
            
            print(f"\n💾 Detailed results saved to: {filename}")
            
        except Exception as e:
            print(f"⚠️  Could not save results to file: {e}")

def main():
    """Main test execution"""
    print("🧪 STRATEGY ENABLE/DISABLE FUNCTIONALITY TEST")
    print("=" * 80)
    
    # Initialize test suite
    tester = StrategyToggleTest()
    
    # Check if web dashboard is running
    try:
        response = requests.get(f"{tester.base_url}/api/strategies", timeout=5)
        if response.status_code != 200:
            print(f"❌ Web dashboard not accessible at {tester.base_url}")
            print("   Please make sure the web dashboard is running")
            return
    except Exception as e:
        print(f"❌ Cannot connect to web dashboard at {tester.base_url}")
        print(f"   Error: {e}")
        print("   Please make sure the web dashboard is running")
        return
    
    print(f"✅ Web dashboard accessible at {tester.base_url}")
    
    # Run comprehensive tests
    tester.test_all_strategies()

if __name__ == "__main__":
    main()
