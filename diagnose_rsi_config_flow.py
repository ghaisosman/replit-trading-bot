
#!/usr/bin/env python3
"""
RSI Configuration Flow Diagnostic
=================================

Diagnoses the complete RSI configuration flow from dashboard to strategy execution
"""

import sys
import os
import json
import requests
from datetime import datetime

# Add src to path
sys.path.append('src')

def check_dashboard_config():
    """Check RSI configuration from dashboard API"""
    print("📊 CHECKING DASHBOARD RSI CONFIGURATION")
    print("-" * 50)
    
    try:
        response = requests.get('http://localhost:5000/api/strategies', timeout=5)
        if response.status_code == 200:
            strategies = response.json().get('strategies', [])
            
            rsi_strategies = [s for s in strategies if 'rsi' in s.get('name', '').lower()]
            
            if rsi_strategies:
                for strategy in rsi_strategies:
                    print(f"✅ Found RSI Strategy: {strategy.get('name')}")
                    print(f"   Enabled: {strategy.get('enabled', False)}")
                    config = strategy.get('config', {})
                    print(f"   Config: {json.dumps(config, indent=4)}")
                    
                    # Validate RSI levels
                    long_entry = config.get('rsi_long_entry', 0)
                    short_entry = config.get('rsi_short_entry', 0)
                    
                    if long_entry >= 50:
                        print(f"   ❌ WARNING: Long entry ({long_entry}) should be < 50 for oversold")
                    else:
                        print(f"   ✅ Long entry ({long_entry}) is properly oversold")
                        
                    if short_entry <= 50:
                        print(f"   ❌ WARNING: Short entry ({short_entry}) should be > 50 for overbought")
                    else:
                        print(f"   ✅ Short entry ({short_entry}) is properly overbought")
                        
                return True
            else:
                print("❌ No RSI strategies found in dashboard")
                return False
        else:
            print(f"❌ Dashboard API error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Failed to connect to dashboard: {e}")
        return False

def check_file_config():
    """Check RSI configuration from file"""
    print("\n📁 CHECKING FILE RSI CONFIGURATION")
    print("-" * 50)
    
    config_file = "src/execution_engine/strategies/rsi_config_data.json"
    
    try:
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config = json.load(f)
                
            print(f"✅ Found RSI config file: {config_file}")
            print(f"   Config: {json.dumps(config, indent=4)}")
            
            # Validate RSI levels
            long_entry = config.get('rsi_long_entry', 0)
            short_entry = config.get('rsi_short_entry', 0)
            
            if long_entry >= 50:
                print(f"   ❌ WARNING: Long entry ({long_entry}) should be < 50 for oversold")
            else:
                print(f"   ✅ Long entry ({long_entry}) is properly oversold")
                
            if short_entry <= 50:
                print(f"   ❌ WARNING: Short entry ({short_entry}) should be > 50 for overbought")
            else:
                print(f"   ✅ Short entry ({short_entry}) is properly overbought")
                
            return True
        else:
            print(f"❌ Config file not found: {config_file}")
            return False
            
    except Exception as e:
        print(f"❌ Failed to read config file: {e}")
        return False

def check_config_class():
    """Check RSI configuration class"""
    print("\n🏗️  CHECKING RSI CONFIG CLASS")
    print("-" * 50)
    
    try:
        from execution_engine.strategies.rsi_oversold_config import RSIOversoldConfig
        
        config = RSIOversoldConfig.get_config()
        print(f"✅ RSI Config Class loaded successfully")
        print(f"   Config: {json.dumps(config, indent=4)}")
        
        # Validate RSI levels
        long_entry = config.get('rsi_long_entry', 0)
        short_entry = config.get('rsi_short_entry', 0)
        
        if long_entry >= 50:
            print(f"   ❌ WARNING: Long entry ({long_entry}) should be < 50 for oversold")
        else:
            print(f"   ✅ Long entry ({long_entry}) is properly oversold")
            
        if short_entry <= 50:
            print(f"   ❌ WARNING: Short entry ({short_entry}) should be > 50 for overbought")
        else:
            print(f"   ✅ Short entry ({short_entry}) is properly overbought")
            
        return True
        
    except Exception as e:
        print(f"❌ Failed to load RSI config class: {e}")
        return False

def check_signal_processor():
    """Check signal processor RSI evaluation"""
    print("\n🔍 CHECKING SIGNAL PROCESSOR RSI EVALUATION")
    print("-" * 50)
    
    try:
        from strategy_processor.signal_processor import SignalProcessor
        import pandas as pd
        import numpy as np
        
        processor = SignalProcessor()
        
        # Create test data with RSI = 25 (oversold)
        test_data = {
            'close': [100] * 50,
            'rsi': [25.0] * 50
        }
        df = pd.DataFrame(test_data)
        
        # Test config with proper oversold levels
        config = {
            'name': 'rsi_oversold',
            'rsi_long_entry': 30,
            'rsi_short_entry': 70,
            'margin': 50.0,
            'leverage': 5,
            'max_loss_pct': 5
        }
        
        signal = processor._evaluate_rsi_oversold(df, 100.0, config)
        
        if signal:
            print(f"✅ Signal generated for RSI 25 (oversold)")
            print(f"   Signal Type: {signal.signal_type}")
            print(f"   Reason: {signal.reason}")
        else:
            print(f"❌ No signal generated for RSI 25 (should be oversold)")
            
        # Test with RSI = 75 (overbought)
        test_data['rsi'] = [75.0] * 50
        df = pd.DataFrame(test_data)
        
        signal = processor._evaluate_rsi_oversold(df, 100.0, config)
        
        if signal:
            print(f"✅ Signal generated for RSI 75 (overbought)")
            print(f"   Signal Type: {signal.signal_type}")
            print(f"   Reason: {signal.reason}")
        else:
            print(f"❌ No signal generated for RSI 75 (should be overbought)")
            
        return True
        
    except Exception as e:
        print(f"❌ Failed to test signal processor: {e}")
        return False

def main():
    """Run complete RSI configuration flow diagnostic"""
    print("🧪 RSI CONFIGURATION FLOW DIAGNOSTIC")
    print("=" * 60)
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    results = {
        'dashboard_config': False,
        'file_config': False,
        'config_class': False,
        'signal_processor': False
    }
    
    # Run all checks
    results['dashboard_config'] = check_dashboard_config()
    results['file_config'] = check_file_config()
    results['config_class'] = check_config_class()
    results['signal_processor'] = check_signal_processor()
    
    # Summary
    print("\n📋 DIAGNOSTIC SUMMARY")
    print("=" * 60)
    
    passed = sum(results.values())
    total = len(results)
    
    for check, status in results.items():
        status_icon = "✅" if status else "❌"
        print(f"{status_icon} {check.replace('_', ' ').title()}: {'PASS' if status else 'FAIL'}")
    
    print(f"\n🎯 Overall Result: {passed}/{total} checks passed")
    
    if passed == total:
        print("✅ RSI configuration flow is working correctly")
    else:
        print("❌ RSI configuration flow has issues - check failed items above")
        
    # Recommendations
    print("\n💡 RECOMMENDATIONS")
    print("-" * 50)
    
    if not results['dashboard_config']:
        print("• Start the dashboard to enable API-based configuration")
        
    if not results['file_config']:
        print("• Fix or create the RSI config file with proper oversold/overbought levels")
        
    if not results['config_class']:
        print("• Check RSI config class implementation for errors")
        
    if not results['signal_processor']:
        print("• Fix signal processor RSI evaluation logic")

if __name__ == "__main__":
    main()
