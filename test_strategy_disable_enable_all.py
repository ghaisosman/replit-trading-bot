
#!/usr/bin/env python3
"""
Comprehensive Strategy Disable/Enable Test
Tests the disable/enable functionality for ALL strategies through the web dashboard API
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

class StrategyToggleTest:
    def __init__(self):
        self.dashboard_base_url = "http://localhost:5000"
        self.strategies = {}
        self.test_results = {
            'phase1_discovery': {},
            'phase2_baseline': {},
            'phase3_disable': {},
            'phase4_enable': {},
            'phase5_final_verification': {},
            'summary': {}
        }

    def run_comprehensive_test(self):
        """Run the complete disable/enable test for all strategies"""
        print("🧪 COMPREHENSIVE STRATEGY DISABLE/ENABLE TEST")
        print("=" * 80)
        print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            # Phase 1: Discover all strategies
            if not self._phase1_discover_strategies():
                print("❌ CRITICAL: Could not discover strategies. Dashboard may not be running.")
                return False

            # Phase 2: Record baseline states
            self._phase2_record_baseline()

            # Phase 3: Test disable functionality
            self._phase3_test_disable_all()

            # Phase 4: Test enable functionality  
            self._phase4_test_enable_all()

            # Phase 5: Final verification
            self._phase5_final_verification()

            # Generate summary report
            self._generate_summary_report()

            # Save detailed results
            self._save_test_results()

            return True

        except Exception as e:
            print(f"❌ CRITICAL ERROR in test execution: {e}")
            return False

    def _phase1_discover_strategies(self) -> bool:
        """Phase 1: Discover all available strategies"""
        print("\n🔍 PHASE 1: STRATEGY DISCOVERY")
        print("-" * 50)

        try:
            response = requests.get(f"{self.dashboard_base_url}/api/strategies", timeout=10)
            
            if response.status_code != 200:
                print(f"❌ Dashboard API not accessible: {response.status_code}")
                return False

            data = response.json()
            
            # Handle both dictionary and list response formats
            if isinstance(data, dict):
                self.strategies = data
            elif isinstance(data, list):
                self.strategies = {strategy.get('name', f'strategy_{i}'): strategy for i, strategy in enumerate(data)}
            else:
                print(f"❌ Unexpected API response format: {type(data)}")
                return False

            print(f"✅ Discovered {len(self.strategies)} strategies:")
            for strategy_name in self.strategies.keys():
                print(f"   🎯 {strategy_name}")

            self.test_results['phase1_discovery'] = {
                'total_strategies': len(self.strategies),
                'strategy_names': list(self.strategies.keys()),
                'discovery_time': datetime.now().isoformat()
            }

            return len(self.strategies) > 0

        except Exception as e:
            print(f"❌ Error discovering strategies: {e}")
            return False

    def _phase2_record_baseline(self):
        """Phase 2: Record current state of all strategies"""
        print("\n📊 PHASE 2: BASELINE STATE RECORDING")
        print("-" * 50)

        baseline_states = {}

        for strategy_name in self.strategies.keys():
            try:
                current_state = self._get_strategy_state(strategy_name)
                baseline_states[strategy_name] = current_state
                
                state_display = current_state.get('current_state', 'UNKNOWN')
                assessment_interval = current_state.get('assessment_interval', 'N/A')
                enabled_flag = current_state.get('enabled_flag', 'N/A')
                
                print(f"📋 {strategy_name}")
                print(f"   State: {state_display}")
                print(f"   Assessment Interval: {assessment_interval}")
                print(f"   Enabled Flag: {enabled_flag}")

            except Exception as e:
                print(f"❌ Error recording baseline for {strategy_name}: {e}")
                baseline_states[strategy_name] = {'error': str(e)}

        self.test_results['phase2_baseline'] = baseline_states
        print(f"✅ Baseline recorded for {len(baseline_states)} strategies")

    def _phase3_test_disable_all(self):
        """Phase 3: Test disable functionality for all strategies"""
        print("\n🔴 PHASE 3: TESTING DISABLE FUNCTIONALITY")
        print("-" * 50)

        disable_results = {}

        for strategy_name in self.strategies.keys():
            print(f"\n🔴 Testing disable for {strategy_name}...")
            
            try:
                # Check current state first
                current_state = self._get_strategy_state(strategy_name)
                if current_state.get('current_state') == 'DISABLED':
                    print(f"   ⏭️ Already disabled - skipping")
                    disable_results[strategy_name] = {
                        'status': 'SKIPPED',
                        'reason': 'Already disabled'
                    }
                    continue

                # Test disable API call
                disable_response = requests.post(
                    f"{self.dashboard_base_url}/api/strategies/{strategy_name}/disable",
                    headers={'Content-Type': 'application/json'},
                    timeout=15
                )

                if disable_response.status_code == 200:
                    disable_data = disable_response.json()
                    api_success = disable_data.get('success', False)
                    
                    # Wait a moment for state to update
                    time.sleep(1)
                    
                    # Verify the disable worked
                    verification = self._verify_strategy_state(strategy_name, 'DISABLED')
                    
                    disable_results[strategy_name] = {
                        'status': 'SUCCESS' if api_success and verification['verified'] else 'FAILED',
                        'api_call_success': api_success,
                        'state_verification': verification,
                        'response_data': disable_data
                    }
                    
                    status_icon = "✅" if api_success and verification['verified'] else "❌"
                    print(f"   {status_icon} API: {api_success} | State: {verification['verified']}")
                    
                else:
                    disable_results[strategy_name] = {
                        'status': 'API_FAILED',
                        'api_call_success': False,
                        'http_status': disable_response.status_code,
                        'response': disable_response.text[:200]
                    }
                    print(f"   ❌ API call failed: {disable_response.status_code}")

            except Exception as e:
                disable_results[strategy_name] = {
                    'status': 'ERROR',
                    'error': str(e)
                }
                print(f"   ❌ Exception: {e}")

        self.test_results['phase3_disable'] = disable_results
        
        # Summary
        successful_disables = sum(1 for result in disable_results.values() 
                                if result.get('status') == 'SUCCESS')
        total_tested = len([r for r in disable_results.values() 
                          if r.get('status') not in ['SKIPPED']])
        
        print(f"\n📊 DISABLE PHASE SUMMARY: {successful_disables}/{total_tested} strategies successfully disabled")

    def _phase4_test_enable_all(self):
        """Phase 4: Test enable functionality for all strategies"""
        print("\n🟢 PHASE 4: TESTING ENABLE FUNCTIONALITY")
        print("-" * 50)

        enable_results = {}

        for strategy_name in self.strategies.keys():
            print(f"\n🟢 Testing enable for {strategy_name}...")
            
            try:
                # Check current state first
                current_state = self._get_strategy_state(strategy_name)
                if current_state.get('current_state') == 'ENABLED':
                    print(f"   ⏭️ Already enabled - skipping")
                    enable_results[strategy_name] = {
                        'status': 'SKIPPED',
                        'reason': 'Already enabled'
                    }
                    continue

                # Test enable API call
                enable_response = requests.post(
                    f"{self.dashboard_base_url}/api/strategies/{strategy_name}/enable",
                    headers={'Content-Type': 'application/json'},
                    timeout=15
                )

                if enable_response.status_code == 200:
                    enable_data = enable_response.json()
                    api_success = enable_data.get('success', False)
                    
                    # Wait a moment for state to update
                    time.sleep(1)
                    
                    # Verify the enable worked
                    verification = self._verify_strategy_state(strategy_name, 'ENABLED')
                    
                    enable_results[strategy_name] = {
                        'status': 'SUCCESS' if api_success and verification['verified'] else 'FAILED',
                        'api_call_success': api_success,
                        'state_verification': verification,
                        'response_data': enable_data
                    }
                    
                    status_icon = "✅" if api_success and verification['verified'] else "❌"
                    print(f"   {status_icon} API: {api_success} | State: {verification['verified']}")
                    
                else:
                    enable_results[strategy_name] = {
                        'status': 'API_FAILED',
                        'api_call_success': False,
                        'http_status': enable_response.status_code,
                        'response': enable_response.text[:200]
                    }
                    print(f"   ❌ API call failed: {enable_response.status_code}")

            except Exception as e:
                enable_results[strategy_name] = {
                    'status': 'ERROR',
                    'error': str(e)
                }
                print(f"   ❌ Exception: {e}")

        self.test_results['phase4_enable'] = enable_results
        
        # Summary
        successful_enables = sum(1 for result in enable_results.values() 
                               if result.get('status') == 'SUCCESS')
        total_tested = len([r for r in enable_results.values() 
                          if r.get('status') not in ['SKIPPED']])
        
        print(f"\n📊 ENABLE PHASE SUMMARY: {successful_enables}/{total_tested} strategies successfully enabled")

    def _phase5_final_verification(self):
        """Phase 5: Final verification of all strategies"""
        print("\n🔍 PHASE 5: FINAL STATE VERIFICATION")
        print("-" * 50)

        final_states = {}

        for strategy_name in self.strategies.keys():
            try:
                final_state = self._get_strategy_state(strategy_name)
                final_states[strategy_name] = final_state
                
                state_display = final_state.get('current_state', 'UNKNOWN')
                print(f"📋 {strategy_name}: {state_display}")

            except Exception as e:
                print(f"❌ Error verifying final state for {strategy_name}: {e}")
                final_states[strategy_name] = {'error': str(e)}

        self.test_results['phase5_final_verification'] = final_states

    def _get_strategy_state(self, strategy_name: str) -> Dict[str, Any]:
        """Get current state of a strategy"""
        try:
            response = requests.get(f"{self.dashboard_base_url}/api/strategies", timeout=10)
            
            if response.status_code == 200:
                strategies = response.json()
                
                # Handle both dict and list formats
                if isinstance(strategies, dict):
                    strategy_data = strategies.get(strategy_name, {})
                elif isinstance(strategies, list):
                    strategy_data = next((s for s in strategies if s.get('name') == strategy_name), {})
                else:
                    return {'error': 'Invalid response format'}

                # Extract state information
                config = strategy_data.get('config', {}) if isinstance(strategy_data, dict) else strategy_data
                assessment_interval = config.get('assessment_interval', 60)
                enabled_flag = config.get('enabled', True)
                
                # Determine current state
                if assessment_interval == 0 or enabled_flag == False:
                    current_state = 'DISABLED'
                else:
                    current_state = 'ENABLED'
                
                return {
                    'current_state': current_state,
                    'assessment_interval': assessment_interval,
                    'enabled_flag': enabled_flag,
                    'config': config
                }
            else:
                return {'error': f'API call failed: {response.status_code}'}
                
        except Exception as e:
            return {'error': str(e)}

    def _verify_strategy_state(self, strategy_name: str, expected_state: str) -> Dict[str, Any]:
        """Verify strategy is in expected state"""
        try:
            current_state_data = self._get_strategy_state(strategy_name)
            current_state = current_state_data.get('current_state', 'UNKNOWN')
            
            verified = current_state == expected_state
            
            return {
                'verified': verified,
                'current_state': current_state,
                'expected_state': expected_state,
                'assessment_interval': current_state_data.get('assessment_interval'),
                'enabled_flag': current_state_data.get('enabled_flag'),
                'reason': 'State matches expectation' if verified else f'Expected {expected_state}, got {current_state}'
            }
            
        except Exception as e:
            return {
                'verified': False,
                'error': str(e),
                'reason': f'Verification failed: {str(e)}'
            }

    def _generate_summary_report(self):
        """Generate comprehensive summary report"""
        print("\n📋 COMPREHENSIVE TEST SUMMARY")
        print("=" * 80)

        # Overall statistics
        total_strategies = self.test_results['phase1_discovery'].get('total_strategies', 0)
        
        # Disable phase stats
        disable_results = self.test_results.get('phase3_disable', {})
        successful_disables = sum(1 for result in disable_results.values() 
                                if result.get('status') == 'SUCCESS')
        failed_disables = sum(1 for result in disable_results.values() 
                            if result.get('status') in ['FAILED', 'API_FAILED', 'ERROR'])
        
        # Enable phase stats
        enable_results = self.test_results.get('phase4_enable', {})
        successful_enables = sum(1 for result in enable_results.values() 
                               if result.get('status') == 'SUCCESS')
        failed_enables = sum(1 for result in enable_results.values() 
                           if result.get('status') in ['FAILED', 'API_FAILED', 'ERROR'])

        print(f"🎯 TOTAL STRATEGIES TESTED: {total_strategies}")
        print(f"🔴 DISABLE OPERATIONS: {successful_disables} Success | {failed_disables} Failed")
        print(f"🟢 ENABLE OPERATIONS: {successful_enables} Success | {failed_enables} Failed")
        
        # Overall success rate
        total_operations = successful_disables + failed_disables + successful_enables + failed_enables
        total_successful = successful_disables + successful_enables
        
        if total_operations > 0:
            success_rate = (total_successful / total_operations) * 100
            print(f"📊 OVERALL SUCCESS RATE: {success_rate:.1f}%")
        
        # Strategy-by-strategy breakdown
        print(f"\n📋 STRATEGY-BY-STRATEGY RESULTS:")
        for strategy_name in self.strategies.keys():
            disable_status = disable_results.get(strategy_name, {}).get('status', 'N/A')
            enable_status = enable_results.get(strategy_name, {}).get('status', 'N/A')
            
            disable_icon = self._get_status_icon(disable_status)
            enable_icon = self._get_status_icon(enable_status)
            
            print(f"   🎯 {strategy_name}")
            print(f"      Disable: {disable_icon} {disable_status}")
            print(f"      Enable:  {enable_icon} {enable_status}")

        # Save summary
        self.test_results['summary'] = {
            'total_strategies': total_strategies,
            'disable_stats': {
                'successful': successful_disables,
                'failed': failed_disables
            },
            'enable_stats': {
                'successful': successful_enables,
                'failed': failed_enables
            },
            'overall_success_rate': success_rate if total_operations > 0 else 0,
            'test_completion_time': datetime.now().isoformat()
        }

    def _get_status_icon(self, status: str) -> str:
        """Get icon for status"""
        status_icons = {
            'SUCCESS': '✅',
            'FAILED': '❌', 
            'API_FAILED': '🔴',
            'ERROR': '💥',
            'SKIPPED': '⏭️',
            'N/A': '❓'
        }
        return status_icons.get(status, '❓')

    def _save_test_results(self):
        """Save detailed test results to file"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"strategy_disable_enable_test_{timestamp}.json"
        
        try:
            with open(filename, 'w') as f:
                json.dump(self.test_results, f, indent=2)
            
            print(f"\n💾 DETAILED RESULTS SAVED: {filename}")
            
        except Exception as e:
            print(f"❌ Error saving results: {e}")

def main():
    """Main test execution"""
    print("🚀 Starting Strategy Disable/Enable Test...")
    
    tester = StrategyToggleTest()
    success = tester.run_comprehensive_test()
    
    if success:
        print("\n🎉 TEST COMPLETED SUCCESSFULLY!")
    else:
        print("\n❌ TEST FAILED!")
    
    return success

if __name__ == "__main__":
    main()
