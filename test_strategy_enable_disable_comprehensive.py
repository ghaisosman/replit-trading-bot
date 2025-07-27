
#!/usr/bin/env python3
"""
Comprehensive Strategy Enable/Disable Test
Tests the enable/disable functionality for all strategies through the web dashboard API
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

class StrategyToggleTest:
    def __init__(self):
        self.dashboard_base_url = "http://0.0.0.0:5000"
        self.test_start_time = datetime.now()
        self.results = {}
        self.strategies = []
        self.original_states = {}
        
    def run_complete_test(self):
        """Run the complete strategy enable/disable test suite"""
        print("🔘 STRATEGY ENABLE/DISABLE COMPREHENSIVE TEST")
        print("=" * 60)
        print(f"⏰ Test started at: {self.test_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            # Phase 1: Dashboard connectivity and initial setup
            self._phase1_setup_and_connectivity()
            
            # Phase 2: Discover strategies and their current states
            self._phase2_discover_strategy_states()
            
            # Phase 3: Test disable functionality
            self._phase3_test_disable_functionality()
            
            # Phase 4: Test enable functionality  
            self._phase4_test_enable_functionality()
            
            # Phase 5: Test rapid toggle scenarios
            self._phase5_test_rapid_toggle()
            
            # Phase 6: Test state persistence
            self._phase6_test_state_persistence()
            
            # Phase 7: Restore original states
            self._phase7_restore_original_states()
            
            # Generate final report
            self._generate_final_report()
            
        except Exception as e:
            print(f"❌ CRITICAL TEST ERROR: {e}")
            self.results['critical_error'] = str(e)
            self._generate_final_report()
    
    def _phase1_setup_and_connectivity(self):
        """Phase 1: Test dashboard connectivity and API availability"""
        print("\n📡 PHASE 1: Dashboard Connectivity Test")
        print("-" * 40)
        
        connectivity_results = {}
        
        # Test basic dashboard connectivity
        try:
            print("🔍 Testing dashboard home page...")
            response = requests.get(f"{self.dashboard_base_url}/", timeout=10)
            dashboard_accessible = response.status_code == 200
            connectivity_results['dashboard_home'] = {
                'accessible': dashboard_accessible,
                'status_code': response.status_code
            }
            print(f"   {'✅' if dashboard_accessible else '❌'} Dashboard home: {'ACCESSIBLE' if dashboard_accessible else 'FAILED'}")
            
        except Exception as e:
            connectivity_results['dashboard_home'] = {'accessible': False, 'error': str(e)}
            print(f"   ❌ Dashboard home: ERROR - {e}")
        
        # Test strategies API endpoint
        try:
            print("🔍 Testing strategies API endpoint...")
            response = requests.get(f"{self.dashboard_base_url}/api/strategies", timeout=10)
            strategies_api_accessible = response.status_code == 200
            connectivity_results['strategies_api'] = {
                'accessible': strategies_api_accessible,
                'status_code': response.status_code
            }
            if strategies_api_accessible:
                strategies_data = response.json()
                connectivity_results['strategies_api']['strategy_count'] = len(strategies_data)
                print(f"   ✅ Strategies API: ACCESSIBLE ({len(strategies_data)} strategies found)")
            else:
                print(f"   ❌ Strategies API: FAILED (HTTP {response.status_code})")
                
        except Exception as e:
            connectivity_results['strategies_api'] = {'accessible': False, 'error': str(e)}
            print(f"   ❌ Strategies API: ERROR - {e}")
        
        # Test bot status API
        try:
            print("🔍 Testing bot status API...")
            response = requests.get(f"{self.dashboard_base_url}/api/bot/status", timeout=10)
            bot_status_accessible = response.status_code == 200
            connectivity_results['bot_status_api'] = {
                'accessible': bot_status_accessible,
                'status_code': response.status_code
            }
            if bot_status_accessible:
                bot_data = response.json()
                connectivity_results['bot_status_api']['bot_running'] = bot_data.get('running', False)
                print(f"   ✅ Bot Status API: ACCESSIBLE (Bot running: {bot_data.get('running', False)})")
            else:
                print(f"   ❌ Bot Status API: FAILED (HTTP {response.status_code})")
                
        except Exception as e:
            connectivity_results['bot_status_api'] = {'accessible': False, 'error': str(e)}
            print(f"   ❌ Bot Status API: ERROR - {e}")
        
        self.results['phase1_connectivity'] = connectivity_results
        
        # Check if we can proceed
        critical_apis_working = (
            connectivity_results.get('strategies_api', {}).get('accessible', False) and
            connectivity_results.get('dashboard_home', {}).get('accessible', False)
        )
        
        if not critical_apis_working:
            raise Exception("Critical dashboard APIs not accessible - cannot proceed with test")
        
        print("✅ Phase 1 complete: Dashboard connectivity verified")
    
    def _phase2_discover_strategy_states(self):
        """Phase 2: Discover all strategies and their current enable/disable states"""
        print("\n🔍 PHASE 2: Strategy Discovery and State Analysis")
        print("-" * 40)
        
        try:
            # Get all strategies
            response = requests.get(f"{self.dashboard_base_url}/api/strategies", timeout=10)
            if response.status_code != 200:
                raise Exception(f"Failed to get strategies: HTTP {response.status_code}")
            
            strategies_data = response.json()
            self.strategies = list(strategies_data.keys())
            
            print(f"📊 Found {len(self.strategies)} strategies:")
            
            # Analyze each strategy's current state
            strategy_analysis = {}
            
            for strategy_name in self.strategies:
                strategy_config = strategies_data[strategy_name]
                
                # Determine current state based on config
                assessment_interval = strategy_config.get('assessment_interval', 60)
                enabled_flag = strategy_config.get('enabled', True)
                
                # Strategy is considered disabled if assessment_interval is 0 OR enabled is False
                is_disabled = (assessment_interval == 0 or not enabled_flag)
                current_state = 'DISABLED' if is_disabled else 'ENABLED'
                
                self.original_states[strategy_name] = current_state
                
                strategy_analysis[strategy_name] = {
                    'symbol': strategy_config.get('symbol', 'UNKNOWN'),
                    'current_state': current_state,
                    'assessment_interval': assessment_interval,
                    'enabled_flag': enabled_flag,
                    'margin': strategy_config.get('margin', 0),
                    'leverage': strategy_config.get('leverage', 1)
                }
                
                print(f"   📈 {strategy_name}")
                print(f"      Symbol: {strategy_config.get('symbol', 'UNKNOWN')}")
                print(f"      State: {current_state}")
                print(f"      Assessment Interval: {assessment_interval}s")
                print(f"      Enabled Flag: {enabled_flag}")
            
            self.results['phase2_discovery'] = {
                'strategy_count': len(self.strategies),
                'strategies': strategy_analysis,
                'original_states': self.original_states.copy()
            }
            
            print(f"✅ Phase 2 complete: {len(self.strategies)} strategies analyzed")
            
        except Exception as e:
            print(f"❌ Phase 2 failed: {e}")
            self.results['phase2_discovery'] = {'status': 'FAILED', 'error': str(e)}
            raise
    
    def _phase3_test_disable_functionality(self):
        """Phase 3: Test disabling strategies"""
        print("\n🔴 PHASE 3: Testing Disable Functionality")
        print("-" * 40)
        
        disable_results = {}
        
        for strategy_name in self.strategies:
            print(f"\n🔍 Testing disable for {strategy_name}...")
            
            try:
                # Skip if already disabled
                if self.original_states[strategy_name] == 'DISABLED':
                    print(f"   ⏭️ Already disabled - skipping disable test")
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
                    
                    if api_success:
                        print(f"   ✅ Disable API call: SUCCESS")
                        
                        # Wait a moment for changes to take effect
                        time.sleep(2)
                        
                        # Verify the strategy is actually disabled
                        verification_result = self._verify_strategy_state(strategy_name, 'DISABLED')
                        
                        disable_results[strategy_name] = {
                            'status': 'SUCCESS',
                            'api_call_success': True,
                            'state_verification': verification_result,
                            'response_data': disable_data
                        }
                        
                        if verification_result['verified']:
                            print(f"   ✅ State verification: PASSED - Strategy is disabled")
                        else:
                            print(f"   ❌ State verification: FAILED - {verification_result['reason']}")
                    else:
                        print(f"   ❌ Disable API call: FAILED - API returned success=False")
                        disable_results[strategy_name] = {
                            'status': 'API_FAILURE',
                            'api_call_success': False,
                            'response_data': disable_data
                        }
                else:
                    print(f"   ❌ Disable API call: HTTP ERROR {disable_response.status_code}")
                    disable_results[strategy_name] = {
                        'status': 'HTTP_ERROR',
                        'status_code': disable_response.status_code,
                        'response_text': disable_response.text[:200]
                    }
                
            except Exception as e:
                print(f"   ❌ Disable test ERROR: {e}")
                disable_results[strategy_name] = {
                    'status': 'ERROR',
                    'error': str(e)
                }
        
        self.results['phase3_disable'] = disable_results
        
        # Summary
        successful_disables = sum(1 for result in disable_results.values() 
                                if result.get('status') == 'SUCCESS' and 
                                   result.get('state_verification', {}).get('verified', False))
        total_tested = len([r for r in disable_results.values() if r.get('status') != 'SKIPPED'])
        
        print(f"\n✅ Phase 3 complete: {successful_disables}/{total_tested} strategies successfully disabled")
    
    def _phase4_test_enable_functionality(self):
        """Phase 4: Test enabling strategies"""
        print("\n🟢 PHASE 4: Testing Enable Functionality")
        print("-" * 40)
        
        enable_results = {}
        
        for strategy_name in self.strategies:
            print(f"\n🔍 Testing enable for {strategy_name}...")
            
            try:
                # Get current state to determine if we should test enable
                current_verification = self._verify_strategy_state(strategy_name, None)
                current_state = current_verification.get('current_state', 'UNKNOWN')
                
                if current_state == 'ENABLED':
                    print(f"   ⏭️ Already enabled - skipping enable test")
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
                    
                    if api_success:
                        print(f"   ✅ Enable API call: SUCCESS")
                        
                        # Wait a moment for changes to take effect
                        time.sleep(2)
                        
                        # Verify the strategy is actually enabled
                        verification_result = self._verify_strategy_state(strategy_name, 'ENABLED')
                        
                        enable_results[strategy_name] = {
                            'status': 'SUCCESS',
                            'api_call_success': True,
                            'state_verification': verification_result,
                            'response_data': enable_data
                        }
                        
                        if verification_result['verified']:
                            print(f"   ✅ State verification: PASSED - Strategy is enabled")
                        else:
                            print(f"   ❌ State verification: FAILED - {verification_result['reason']}")
                    else:
                        print(f"   ❌ Enable API call: FAILED - API returned success=False")
                        enable_results[strategy_name] = {
                            'status': 'API_FAILURE',
                            'api_call_success': False,
                            'response_data': enable_data
                        }
                else:
                    print(f"   ❌ Enable API call: HTTP ERROR {enable_response.status_code}")
                    enable_results[strategy_name] = {
                        'status': 'HTTP_ERROR',
                        'status_code': enable_response.status_code,
                        'response_text': enable_response.text[:200]
                    }
                
            except Exception as e:
                print(f"   ❌ Enable test ERROR: {e}")
                enable_results[strategy_name] = {
                    'status': 'ERROR',
                    'error': str(e)
                }
        
        self.results['phase4_enable'] = enable_results
        
        # Summary
        successful_enables = sum(1 for result in enable_results.values() 
                               if result.get('status') == 'SUCCESS' and 
                                  result.get('state_verification', {}).get('verified', False))
        total_tested = len([r for r in enable_results.values() if r.get('status') != 'SKIPPED'])
        
        print(f"\n✅ Phase 4 complete: {successful_enables}/{total_tested} strategies successfully enabled")
    
    def _phase5_test_rapid_toggle(self):
        """Phase 5: Test rapid enable/disable toggling"""
        print("\n⚡ PHASE 5: Testing Rapid Toggle Scenarios")
        print("-" * 40)
        
        if not self.strategies:
            print("❌ No strategies available for rapid toggle test")
            self.results['phase5_rapid_toggle'] = {'status': 'SKIPPED', 'reason': 'No strategies'}
            return
        
        # Pick the first strategy for rapid toggle test
        test_strategy = self.strategies[0]
        print(f"🎯 Using {test_strategy} for rapid toggle test")
        
        rapid_toggle_results = {
            'test_strategy': test_strategy,
            'toggle_sequence': []
        }
        
        try:
            # Perform 3 rapid toggles: disable -> enable -> disable
            toggle_sequence = ['disable', 'enable', 'disable']
            
            for i, action in enumerate(toggle_sequence):
                print(f"\n🔄 Rapid toggle {i+1}/3: {action.upper()}")
                
                start_time = time.time()
                
                # Make API call
                response = requests.post(
                    f"{self.dashboard_base_url}/api/strategies/{test_strategy}/{action}",
                    headers={'Content-Type': 'application/json'},
                    timeout=10
                )
                
                api_duration = time.time() - start_time
                
                if response.status_code == 200:
                    response_data = response.json()
                    api_success = response_data.get('success', False)
                    
                    # Brief wait then verify state
                    time.sleep(1)
                    expected_state = 'DISABLED' if action == 'disable' else 'ENABLED'
                    verification = self._verify_strategy_state(test_strategy, expected_state)
                    
                    toggle_result = {
                        'action': action,
                        'api_success': api_success,
                        'api_duration': round(api_duration, 3),
                        'state_verification': verification,
                        'response_data': response_data
                    }
                    
                    if api_success and verification['verified']:
                        print(f"   ✅ {action.upper()}: SUCCESS ({api_duration:.3f}s)")
                    else:
                        print(f"   ❌ {action.upper()}: FAILED")
                        if not api_success:
                            print(f"      API call failed")
                        if not verification['verified']:
                            print(f"      State verification failed: {verification['reason']}")
                else:
                    toggle_result = {
                        'action': action,
                        'api_success': False,
                        'api_duration': round(api_duration, 3),
                        'http_error': response.status_code,
                        'response_text': response.text[:200]
                    }
                    print(f"   ❌ {action.upper()}: HTTP ERROR {response.status_code}")
                
                rapid_toggle_results['toggle_sequence'].append(toggle_result)
                
                # Small delay between rapid toggles
                time.sleep(0.5)
            
            # Calculate overall success rate
            successful_toggles = sum(1 for t in rapid_toggle_results['toggle_sequence'] 
                                   if t.get('api_success') and 
                                      t.get('state_verification', {}).get('verified', False))
            
            rapid_toggle_results['success_rate'] = successful_toggles / len(toggle_sequence)
            rapid_toggle_results['status'] = 'SUCCESS' if successful_toggles == len(toggle_sequence) else 'PARTIAL'
            
            print(f"\n⚡ Rapid toggle test: {successful_toggles}/{len(toggle_sequence)} successful")
            
        except Exception as e:
            print(f"❌ Rapid toggle test ERROR: {e}")
            rapid_toggle_results['status'] = 'ERROR'
            rapid_toggle_results['error'] = str(e)
        
        self.results['phase5_rapid_toggle'] = rapid_toggle_results
        print("✅ Phase 5 complete: Rapid toggle testing finished")
    
    def _phase6_test_state_persistence(self):
        """Phase 6: Test if state changes persist across API calls"""
        print("\n💾 PHASE 6: Testing State Persistence")
        print("-" * 40)
        
        persistence_results = {}
        
        for strategy_name in self.strategies:
            print(f"\n🔍 Testing persistence for {strategy_name}...")
            
            try:
                # Get initial state
                initial_check = self._verify_strategy_state(strategy_name, None)
                initial_state = initial_check.get('current_state', 'UNKNOWN')
                
                print(f"   📊 Initial state: {initial_state}")
                
                # Toggle the state
                target_action = 'disable' if initial_state == 'ENABLED' else 'enable'
                target_state = 'DISABLED' if target_action == 'disable' else 'ENABLED'
                
                print(f"   🔄 Performing {target_action}...")
                
                # Make the toggle
                response = requests.post(
                    f"{self.dashboard_base_url}/api/strategies/{strategy_name}/{target_action}",
                    headers={'Content-Type': 'application/json'},
                    timeout=15
                )
                
                if response.status_code == 200 and response.json().get('success', False):
                    time.sleep(2)  # Wait for change to take effect
                    
                    # Check state multiple times to verify persistence
                    persistence_checks = []
                    
                    for check_num in range(3):
                        time.sleep(1)  # 1 second between checks
                        check_result = self._verify_strategy_state(strategy_name, target_state)
                        persistence_checks.append({
                            'check_number': check_num + 1,
                            'verified': check_result['verified'],
                            'current_state': check_result['current_state'],
                            'timestamp': datetime.now().isoformat()
                        })
                        print(f"   📊 Persistence check {check_num + 1}: {check_result['current_state']} ({'✅' if check_result['verified'] else '❌'})")
                    
                    # Determine if state persisted consistently
                    all_verified = all(check['verified'] for check in persistence_checks)
                    
                    persistence_results[strategy_name] = {
                        'status': 'SUCCESS' if all_verified else 'INCONSISTENT',
                        'initial_state': initial_state,
                        'target_state': target_state,
                        'action': target_action,
                        'persistence_checks': persistence_checks,
                        'consistent_persistence': all_verified
                    }
                    
                    if all_verified:
                        print(f"   ✅ State persistence: CONSISTENT")
                    else:
                        print(f"   ❌ State persistence: INCONSISTENT")
                else:
                    persistence_results[strategy_name] = {
                        'status': 'API_FAILURE',
                        'initial_state': initial_state,
                        'target_action': target_action,
                        'api_error': 'Toggle API call failed'
                    }
                    print(f"   ❌ Could not toggle state for persistence test")
            
            except Exception as e:
                print(f"   ❌ Persistence test ERROR: {e}")
                persistence_results[strategy_name] = {
                    'status': 'ERROR',
                    'error': str(e)
                }
        
        self.results['phase6_persistence'] = persistence_results
        
        # Summary
        consistent_strategies = sum(1 for result in persistence_results.values() 
                                  if result.get('consistent_persistence', False))
        total_tested = len(persistence_results)
        
        print(f"\n✅ Phase 6 complete: {consistent_strategies}/{total_tested} strategies showed consistent state persistence")
    
    def _phase7_restore_original_states(self):
        """Phase 7: Restore all strategies to their original states"""
        print("\n🔄 PHASE 7: Restoring Original States")
        print("-" * 40)
        
        restore_results = {}
        
        for strategy_name in self.strategies:
            original_state = self.original_states.get(strategy_name, 'UNKNOWN')
            
            if original_state == 'UNKNOWN':
                continue
            
            print(f"\n🔄 Restoring {strategy_name} to {original_state}...")
            
            try:
                # Check current state
                current_check = self._verify_strategy_state(strategy_name, None)
                current_state = current_check.get('current_state', 'UNKNOWN')
                
                if current_state == original_state:
                    print(f"   ✅ Already in correct state ({original_state})")
                    restore_results[strategy_name] = {
                        'status': 'NO_ACTION_NEEDED',
                        'original_state': original_state,
                        'current_state': current_state
                    }
                    continue
                
                # Determine required action
                required_action = 'enable' if original_state == 'ENABLED' else 'disable'
                
                # Perform restoration
                response = requests.post(
                    f"{self.dashboard_base_url}/api/strategies/{strategy_name}/{required_action}",
                    headers={'Content-Type': 'application/json'},
                    timeout=15
                )
                
                if response.status_code == 200 and response.json().get('success', False):
                    time.sleep(2)
                    
                    # Verify restoration
                    verification = self._verify_strategy_state(strategy_name, original_state)
                    
                    restore_results[strategy_name] = {
                        'status': 'SUCCESS' if verification['verified'] else 'FAILED',
                        'original_state': original_state,
                        'current_state': current_state,
                        'required_action': required_action,
                        'verification': verification
                    }
                    
                    if verification['verified']:
                        print(f"   ✅ Successfully restored to {original_state}")
                    else:
                        print(f"   ❌ Restoration failed: {verification['reason']}")
                else:
                    restore_results[strategy_name] = {
                        'status': 'API_FAILURE',
                        'original_state': original_state,
                        'current_state': current_state,
                        'api_error': f"HTTP {response.status_code}"
                    }
                    print(f"   ❌ API call failed: HTTP {response.status_code}")
            
            except Exception as e:
                print(f"   ❌ Restoration ERROR: {e}")
                restore_results[strategy_name] = {
                    'status': 'ERROR',
                    'error': str(e)
                }
        
        self.results['phase7_restoration'] = restore_results
        
        successful_restorations = sum(1 for result in restore_results.values() 
                                    if result.get('status') in ['SUCCESS', 'NO_ACTION_NEEDED'])
        total_strategies = len(restore_results)
        
        print(f"\n✅ Phase 7 complete: {successful_restorations}/{total_strategies} strategies restored to original state")
    
    def _verify_strategy_state(self, strategy_name: str, expected_state: Optional[str]) -> Dict:
        """Verify the current state of a strategy"""
        try:
            # Get current strategy configuration
            response = requests.get(f"{self.dashboard_base_url}/api/strategies", timeout=10)
            if response.status_code != 200:
                return {
                    'verified': False,
                    'reason': f'Could not fetch strategies: HTTP {response.status_code}',
                    'current_state': 'UNKNOWN'
                }
            
            strategies_data = response.json()
            if strategy_name not in strategies_data:
                return {
                    'verified': False,
                    'reason': f'Strategy {strategy_name} not found',
                    'current_state': 'UNKNOWN'
                }
            
            strategy_config = strategies_data[strategy_name]
            
            # Determine current state
            assessment_interval = strategy_config.get('assessment_interval', 60)
            enabled_flag = strategy_config.get('enabled', True)
            
            # Strategy is disabled if assessment_interval is 0 OR enabled is False
            is_disabled = (assessment_interval == 0 or not enabled_flag)
            current_state = 'DISABLED' if is_disabled else 'ENABLED'
            
            # If no expected state specified, just return current state
            if expected_state is None:
                return {
                    'verified': True,
                    'current_state': current_state,
                    'assessment_interval': assessment_interval,
                    'enabled_flag': enabled_flag
                }
            
            # Verify against expected state
            verified = (current_state == expected_state)
            
            return {
                'verified': verified,
                'current_state': current_state,
                'expected_state': expected_state,
                'assessment_interval': assessment_interval,
                'enabled_flag': enabled_flag,
                'reason': f'State is {current_state}, expected {expected_state}' if not verified else 'State matches expectation'
            }
            
        except Exception as e:
            return {
                'verified': False,
                'reason': f'Verification error: {str(e)}',
                'current_state': 'ERROR'
            }
    
    def _generate_final_report(self):
        """Generate comprehensive final test report"""
        print("\n📊 COMPREHENSIVE TEST REPORT")
        print("=" * 60)
        
        test_duration = datetime.now() - self.test_start_time
        print(f"⏱️ Test Duration: {test_duration.total_seconds():.1f} seconds")
        
        # Phase Results Summary
        print(f"\n📋 PHASE RESULTS:")
        
        phases = [
            ('Phase 1', 'Connectivity', 'phase1_connectivity'),
            ('Phase 2', 'Strategy Discovery', 'phase2_discovery'),
            ('Phase 3', 'Disable Functionality', 'phase3_disable'),
            ('Phase 4', 'Enable Functionality', 'phase4_enable'),
            ('Phase 5', 'Rapid Toggle', 'phase5_rapid_toggle'),
            ('Phase 6', 'State Persistence', 'phase6_persistence'),
            ('Phase 7', 'State Restoration', 'phase7_restoration')
        ]
        
        for phase_name, description, result_key in phases:
            result = self.results.get(result_key, {})
            if result:
                status = self._determine_phase_status(result_key, result)
                print(f"   {phase_name}: {description:<20} - {status}")
            else:
                print(f"   {phase_name}: {description:<20} - NOT_RUN")
        
        # Overall Test Assessment
        print(f"\n🎯 OVERALL ASSESSMENT:")
        
        # Calculate success metrics
        if 'phase3_disable' in self.results and 'phase4_enable' in self.results:
            disable_results = self.results['phase3_disable']
            enable_results = self.results['phase4_enable']
            
            successful_disables = sum(1 for result in disable_results.values() 
                                    if result.get('status') == 'SUCCESS' and 
                                       result.get('state_verification', {}).get('verified', False))
            
            successful_enables = sum(1 for result in enable_results.values() 
                                   if result.get('status') == 'SUCCESS' and 
                                      result.get('state_verification', {}).get('verified', False))
            
            total_strategies = len(self.strategies)
            
            print(f"   Successful Disables: {successful_disables}/{total_strategies}")
            print(f"   Successful Enables: {successful_enables}/{total_strategies}")
            
            overall_success_rate = ((successful_disables + successful_enables) / (total_strategies * 2)) * 100 if total_strategies > 0 else 0
            print(f"   Overall Success Rate: {overall_success_rate:.1f}%")
            
            if overall_success_rate >= 90:
                print("   ✅ EXCELLENT: Enable/Disable functionality working perfectly")
            elif overall_success_rate >= 70:
                print("   ⚠️ GOOD: Enable/Disable functionality mostly working")
            elif overall_success_rate >= 50:
                print("   ⚠️ FAIR: Enable/Disable functionality partially working")
            else:
                print("   ❌ POOR: Enable/Disable functionality has significant issues")
        
        # Save detailed results to file
        try:
            report_filename = f"strategy_toggle_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(report_filename, 'w') as f:
                json.dump(self.results, f, indent=2, default=str)
            
            print(f"\n💾 Detailed results saved to: {report_filename}")
            
        except Exception as e:
            print(f"⚠️ Could not save results file: {e}")
        
        print(f"\n✅ Test completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("🔘" + "=" * 58 + "🔘")
    
    def _determine_phase_status(self, phase_key: str, result: Dict) -> str:
        """Determine the status of a phase based on its results"""
        if phase_key == 'phase1_connectivity':
            critical_working = (
                result.get('dashboard_home', {}).get('accessible', False) and
                result.get('strategies_api', {}).get('accessible', False)
            )
            return "✅ SUCCESS" if critical_working else "❌ FAILED"
        
        elif phase_key == 'phase2_discovery':
            return "✅ SUCCESS" if result.get('strategy_count', 0) > 0 else "❌ FAILED"
        
        elif phase_key in ['phase3_disable', 'phase4_enable']:
            successful = sum(1 for r in result.values() 
                           if r.get('status') == 'SUCCESS' and 
                              r.get('state_verification', {}).get('verified', False))
            total = len([r for r in result.values() if r.get('status') != 'SKIPPED'])
            
            if total == 0:
                return "⏭️ SKIPPED"
            elif successful == total:
                return "✅ SUCCESS"
            elif successful > 0:
                return f"⚠️ PARTIAL ({successful}/{total})"
            else:
                return "❌ FAILED"
        
        elif phase_key == 'phase5_rapid_toggle':
            status = result.get('status', 'UNKNOWN')
            if status == 'SUCCESS':
                return "✅ SUCCESS"
            elif status == 'PARTIAL':
                success_rate = result.get('success_rate', 0) * 100
                return f"⚠️ PARTIAL ({success_rate:.0f}%)"
            else:
                return "❌ FAILED"
        
        elif phase_key == 'phase6_persistence':
            consistent = sum(1 for r in result.values() if r.get('consistent_persistence', False))
            total = len(result)
            
            if total == 0:
                return "⏭️ SKIPPED"
            elif consistent == total:
                return "✅ SUCCESS"
            elif consistent > 0:
                return f"⚠️ PARTIAL ({consistent}/{total})"
            else:
                return "❌ FAILED"
        
        elif phase_key == 'phase7_restoration':
            successful = sum(1 for r in result.values() if r.get('status') in ['SUCCESS', 'NO_ACTION_NEEDED'])
            total = len(result)
            
            if total == 0:
                return "⏭️ SKIPPED"
            elif successful == total:
                return "✅ SUCCESS"
            elif successful > 0:
                return f"⚠️ PARTIAL ({successful}/{total})"
            else:
                return "❌ FAILED"
        
        return "❓ UNKNOWN"

def main():
    """Main test function"""
    test = StrategyToggleTest()
    test.run_complete_test()

if __name__ == "__main__":
    main()
