
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
    """Check RSI configuration from dashboard API - checks both local and live"""
    print("📊 CHECKING DASHBOARD RSI CONFIGURATION")
    print("-" * 50)
    
    # Try live dashboard first (Render deployment)
    live_dashboard_urls = [
        "https://your-app-name.onrender.com/api/strategies",  # Replace with your actual Render URL
        "http://localhost:5000/api/strategies"  # Fallback to local
    ]
    
    dashboard_found = False
    
    for url in live_dashboard_urls:
        try:
            print(f"🔍 Checking dashboard: {url}")
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                strategies = response.json().get('strategies', [])
                
                rsi_strategies = [s for s in strategies if 'rsi' in s.get('name', '').lower()]
                
                if rsi_strategies:
                    dashboard_found = True
                    print(f"✅ Connected to dashboard: {url}")
                    
                    for strategy in rsi_strategies:
                        print(f"✅ Found RSI Strategy: {strategy.get('name')}")
                        print(f"   Symbol: {strategy.get('symbol', 'N/A')}")
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
                    print(f"ℹ️  No RSI strategies found in {url}")
            else:
                print(f"❌ Dashboard API error ({url}): {response.status_code}")
                
        except Exception as e:
            print(f"ℹ️  Could not connect to {url}: {e}")
    
    if not dashboard_found:
        print("❌ No RSI strategies found in any dashboard")
        print("💡 TIP: Make sure your live dashboard URL is correct")
        
    return dashboard_found

def check_file_config():
    """Check RSI configuration from file"""
    print("\n📁 CHECKING FILE RSI CONFIGURATION")
    print("-" * 50)
    
    file_path = "src/execution_engine/strategies/rsi_config_data.json"
    
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                config = json.load(f)
            
            print(f"✅ Found RSI config file: {file_path}")
            print(f"   Config: {json.dumps(config, indent=4)}")
            
            # Validate configuration logic
            long_entry = config.get('rsi_long_entry', 0)
            short_entry = config.get('rsi_short_entry', 0)
            
            if long_entry < 50:
                print(f"   ✅ Long entry ({long_entry}) is properly oversold")
            else:
                print(f"   ❌ Long entry ({long_entry}) should be < 50 for oversold")
                
            if short_entry > 50:
                print(f"   ✅ Short entry ({short_entry}) is properly overbought")
            else:
                print(f"   ❌ Short entry ({short_entry}) should be > 50 for overbought")
            
            return True
            
        except Exception as e:
            print(f"❌ Error reading config file: {e}")
            return False
    else:
        print(f"❌ RSI config file not found: {file_path}")
        return False

def check_config_class():
    """Check RSI config class loading"""
    print("\n🏗️  CHECKING RSI CONFIG CLASS")
    print("-" * 50)
    
    try:
        from src.execution_engine.strategies.rsi_oversold_config import RSIOversoldConfig
        
        config = RSIOversoldConfig.get_config()
        print(f"✅ RSI Config Class loaded successfully")
        print(f"   Config: {json.dumps(config, indent=4)}")
        
        # Validate configuration logic
        long_entry = config.get('rsi_long_entry', 0)
        short_entry = config.get('rsi_short_entry', 0)
        
        if long_entry < 50:
            print(f"   ✅ Long entry ({long_entry}) is properly oversold")
        else:
            print(f"   ❌ Long entry ({long_entry}) should be < 50 for oversold")
            
        if short_entry > 50:
            print(f"   ✅ Short entry ({short_entry}) is properly overbought")
        else:
            print(f"   ❌ Short entry ({short_entry}) should be > 50 for overbought")
        
        return True
        
    except Exception as e:
        print(f"❌ Error loading RSI Config Class: {e}")
        return False

def check_signal_processor():
    """Check signal processor RSI evaluation"""
    print("\n🔍 CHECKING SIGNAL PROCESSOR RSI EVALUATION")
    print("-" * 50)
    
    try:
        import pandas as pd
        from src.strategy_processor.signal_processor import SignalProcessor
        from src.execution_engine.strategies.rsi_oversold_config import RSIOversoldConfig
        
        processor = SignalProcessor()
        config = RSIOversoldConfig.get_config()
        config['name'] = 'rsi_test'
        
        # Create test dataframe with RSI values
        test_data = {
            'close': [100.0] * 50,
            'rsi': [50.0] * 47 + [25.0, 75.0, 50.0]  # oversold, overbought, neutral
        }
        df = pd.DataFrame(test_data)
        
        # Test oversold signal (RSI 25)
        df_oversold = df.copy()
        df_oversold['rsi'].iloc[-1] = 25.0
        signal_oversold = processor._evaluate_rsi_oversold(df_oversold, 100.0, config)
        
        if signal_oversold:
            print(f"✅ Signal generated for RSI 25 (oversold)")
            print(f"   Signal Type: {signal_oversold.signal_type.value}")
            print(f"   Reason: {signal_oversold.reason}")
        else:
            print(f"❌ No signal generated for RSI 25 (oversold)")
        
        # Test overbought signal (RSI 75)
        df_overbought = df.copy()
        df_overbought['rsi'].iloc[-1] = 75.0
        signal_overbought = processor._evaluate_rsi_oversold(df_overbought, 100.0, config)
        
        if signal_overbought:
            print(f"✅ Signal generated for RSI 75 (overbought)")
            print(f"   Signal Type: {signal_overbought.signal_type.value}")
            print(f"   Reason: {signal_overbought.reason}")
        else:
            print(f"❌ No signal generated for RSI 75 (overbought)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing signal processor: {e}")
        return False

def main():
    """Run complete RSI configuration flow diagnostic"""
    print("🧪 RSI CONFIGURATION FLOW DIAGNOSTIC")
    print("=" * 60)
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run all checks
    dashboard_ok = check_dashboard_config()
    file_ok = check_file_config()
    class_ok = check_config_class()
    processor_ok = check_signal_processor()
    
    # Summary
    print("\n📋 DIAGNOSTIC SUMMARY")
    print("=" * 60)
    print(f"{'✅' if dashboard_ok else '❌'} Dashboard Config: {'PASS' if dashboard_ok else 'FAIL'}")
    print(f"{'✅' if file_ok else '❌'} File Config: {'PASS' if file_ok else 'FAIL'}")
    print(f"{'✅' if class_ok else '❌'} Config Class: {'PASS' if class_ok else 'FAIL'}")
    print(f"{'✅' if processor_ok else '❌'} Signal Processor: {'PASS' if processor_ok else 'FAIL'}")
    
    passed_checks = sum([dashboard_ok, file_ok, class_ok, processor_ok])
    print(f"\n🎯 Overall Result: {passed_checks}/4 checks passed")
    
    if passed_checks == 4:
        print("✅ RSI configuration flow is working perfectly!")
    else:
        print("❌ RSI configuration flow has issues - check failed items above")
    
    print("\n💡 RECOMMENDATIONS")
    print("-" * 50)
    if not dashboard_ok:
        print("• Update the live dashboard URL in this diagnostic")
        print("• Verify your RSI strategy exists in the live dashboard")
        print("• Check that the live dashboard API is accessible")
    if passed_checks >= 3:
        print("• Configuration flow is mostly working - strategy will use file config as fallback")

if __name__ == "__main__":
    main()
