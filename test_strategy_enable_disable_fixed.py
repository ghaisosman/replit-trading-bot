
#!/usr/bin/env python3
"""
Fixed Strategy Enable/Disable Test
Tests the enable/disable functionality for all strategies through the web dashboard API
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, List, Any

class StrategyEnableDisableTest:
    def __init__(self):
        self.dashboard_base_url = "http://localhost:5000"
        self.test_results = {}
        
    def test_strategy_enable_disable(self):
        """Test enable/disable functionality for all strategies"""
        print("🚀 Starting Fixed Strategy Disable/Enable Test...")
        print("🧪 FIXED STRATEGY DISABLE/ENABLE TEST")
        print("=" * 80)
        print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Get all strategies
        strategies = self.get_all_strategies()
        if not strategies:
            print("❌ No strategies found")
            return False
            
        print(f"🔍 PHASE 1: STRATEGY DISCOVERY")
        print("-" * 50)
        
        if strategies:
            print(f"✅ Discovered {len(strategies)} valid strategies:")
            for strategy_name, config in strategies.items():
                symbol = config.get('symbol', 'N/A')
                margin = config.get('margin', 'N/A')
                print(f"   🎯 {strategy_name} (Symbol: {symbol}, Margin: {margin})")
        else:
            print("❌ No valid strategies discovered")
            return False
        print()
        
        # Test each strategy
        all_passed = True
        for strategy_name in strategies.keys():
            print(f"🧪 TESTING STRATEGY: {strategy_name}")
            print("-" * 50)
            
            # Test disable
            disable_success = self.test_disable_strategy(strategy_name)
            print(f"🔴 Disable result: {'✅ SUCCESS' if disable_success else '❌ FAILED'}")
            
            # Wait a moment
            time.sleep(1)
            
            # Test enable
            enable_success = self.test_enable_strategy(strategy_name)
            print(f"🟢 Enable result: {'✅ SUCCESS' if enable_success else '❌ FAILED'}")
            
            if not (disable_success and enable_success):
                all_passed = False
                
            print()
        
        # Final summary
        print("📋 FINAL TEST SUMMARY")
        print("=" * 80)
        if all_passed:
            print("✅ ALL TESTS PASSED - Strategy enable/disable functionality working correctly!")
        else:
            print("❌ SOME TESTS FAILED - Strategy enable/disable functionality needs fixing")
            
        return all_passed
    
    def get_all_strategies(self) -> Dict[str, Any]:
        """Get all available strategies"""
        try:
            response = requests.get(f"{self.dashboard_base_url}/api/strategies")
            if response.status_code == 200:
                data = response.json()
                
                # Debug the response to understand the structure
                print(f"🔍 DEBUG: Raw API response keys: {list(data.keys())}")
                
                actual_strategies = {}
                
                # Check if we have strategy_configs (preferred source)
                if 'strategy_configs' in data and isinstance(data['strategy_configs'], dict):
                    print(f"✅ Found strategy_configs with {len(data['strategy_configs'])} strategies")
                    actual_strategies = data['strategy_configs']
                
                # Also check strategies list format
                elif 'strategies' in data and isinstance(data['strategies'], list):
                    print(f"✅ Found strategies list with {len(data['strategies'])} strategies")
                    for strategy in data['strategies']:
                        if isinstance(strategy, dict) and 'name' in strategy:
                            strategy_name = strategy['name']
                            strategy_config = strategy.get('config', strategy)
                            actual_strategies[strategy_name] = strategy_config
                
                # Fallback: treat top-level keys as strategies
                else:
                    for key, value in data.items():
                        if isinstance(value, dict) and ('symbol' in value or 'margin' in value or 'enabled' in value):
                            actual_strategies[key] = value
                
                # Validate we found strategies
                if actual_strategies:
                    print(f"✅ Successfully parsed {len(actual_strategies)} strategies:")
                    for name, config in actual_strategies.items():
                        symbol = config.get('symbol', 'N/A')
                        enabled = config.get('enabled', 'N/A')
                        print(f"   🎯 {name}: {symbol} (enabled: {enabled})")
                else:
                    print(f"❌ No valid strategies found in response")
                    print(f"🔍 Full response structure: {data}")
                
                return actual_strategies
            else:
                print(f"❌ Failed to get strategies: HTTP {response.status_code}")
                return {}
        except Exception as e:
            print(f"❌ Error getting strategies: {e}")
            return {}
    
    def test_disable_strategy(self, strategy_name: str) -> bool:
        """Test disabling a strategy"""
        try:
            response = requests.post(
                f"{self.dashboard_base_url}/api/strategies/{strategy_name}/disable",
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('success', False)
            else:
                print(f"   ❌ HTTP {response.status_code}: {response.text[:100]}")
                return False
                
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            return False
    
    def test_enable_strategy(self, strategy_name: str) -> bool:
        """Test enabling a strategy"""
        try:
            response = requests.post(
                f"{self.dashboard_base_url}/api/strategies/{strategy_name}/enable",
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('success', False)
            else:
                print(f"   ❌ HTTP {response.status_code}: {response.text[:100]}")
                return False
                
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            return False

if __name__ == "__main__":
    test_runner = StrategyEnableDisableTest()
    success = test_runner.test_strategy_enable_disable()
    exit(0 if success else 1)
