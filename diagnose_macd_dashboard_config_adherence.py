
#!/usr/bin/env python3
"""
🔍 MACD Dashboard Configuration Adherence Diagnostic
Identifies if MACD strategy is properly using dashboard configurations
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime
import json

# Add src to path
sys.path.append('src')

from src.config.trading_config import trading_config_manager
from src.execution_engine.strategies.macd_divergence_strategy import MACDDivergenceStrategy
from src.binance_client.client import BinanceClientWrapper

def diagnose_macd_dashboard_adherence():
    """Comprehensive MACD dashboard configuration adherence check"""
    print("🔍 MACD DASHBOARD CONFIGURATION ADHERENCE DIAGNOSTIC")
    print("=" * 80)
    
    results = {
        'timestamp': datetime.now().isoformat(),
        'dashboard_config': {},
        'strategy_config': {},
        'adherence_check': {},
        'issues_found': [],
        'recommendations': []
    }
    
    # STEP 1: GET DASHBOARD CONFIGURATION
    print("\n📋 STEP 1: LOADING DASHBOARD CONFIGURATION")
    print("-" * 50)
    
    try:
        dashboard_config = trading_config_manager.get_strategy_config('macd_divergence', {})
        results['dashboard_config'] = dashboard_config
        
        print(f"✅ Dashboard Configuration Loaded:")
        print(f"   🎯 Strategy Name: {dashboard_config.get('name', 'N/A')}")
        print(f"   💱 Symbol: {dashboard_config.get('symbol', 'N/A')}")
        print(f"   💰 Margin: {dashboard_config.get('margin', 'N/A')} USDT")
        print(f"   ⚡ Leverage: {dashboard_config.get('leverage', 'N/A')}x")
        print(f"   📊 Timeframe: {dashboard_config.get('timeframe', 'N/A')}")
        print(f"   🔄 Assessment Interval: {dashboard_config.get('assessment_interval', 'N/A')}s")
        print(f"   🟢 Enabled: {dashboard_config.get('enabled', 'N/A')}")
        
        print(f"\n📊 MACD Technical Parameters:")
        print(f"   ⚡ Fast EMA: {dashboard_config.get('macd_fast', 'N/A')}")
        print(f"   🐌 Slow EMA: {dashboard_config.get('macd_slow', 'N/A')}")
        print(f"   📶 Signal: {dashboard_config.get('macd_signal', 'N/A')}")
        print(f"   📈 Entry Threshold: {dashboard_config.get('macd_entry_threshold', 'N/A')}")
        print(f"   📉 Exit Threshold: {dashboard_config.get('macd_exit_threshold', 'N/A')}")
        print(f"   📊 Min Histogram Threshold: {dashboard_config.get('min_histogram_threshold', 'N/A')}")
        print(f"   🔍 Confirmation Candles: {dashboard_config.get('confirmation_candles', 'N/A')}")
        
    except Exception as e:
        print(f"❌ Error loading dashboard config: {e}")
        results['issues_found'].append(f"Dashboard config loading error: {e}")
        return results
    
    # STEP 2: INITIALIZE STRATEGY WITH DASHBOARD CONFIG
    print("\n🤖 STEP 2: INITIALIZING STRATEGY WITH DASHBOARD CONFIG")
    print("-" * 50)
    
    try:
        macd_strategy = MACDDivergenceStrategy(dashboard_config)
        
        # Extract strategy's internal configuration
        strategy_internal_config = {
            'strategy_name': macd_strategy.strategy_name,
            'macd_fast': macd_strategy.macd_fast,
            'macd_slow': macd_strategy.macd_slow,
            'macd_signal': macd_strategy.macd_signal,
            'min_histogram_threshold': macd_strategy.min_histogram_threshold,
            'entry_threshold': macd_strategy.entry_threshold,
            'exit_threshold': macd_strategy.exit_threshold,
            'confirmation_candles': macd_strategy.confirmation_candles
        }
        
        results['strategy_config'] = strategy_internal_config
        
        print(f"✅ Strategy Initialized with Internal Config:")
        print(f"   🎯 Strategy Name: {strategy_internal_config['strategy_name']}")
        print(f"   ⚡ Fast EMA: {strategy_internal_config['macd_fast']}")
        print(f"   🐌 Slow EMA: {strategy_internal_config['macd_slow']}")
        print(f"   📶 Signal: {strategy_internal_config['macd_signal']}")
        print(f"   📈 Entry Threshold: {strategy_internal_config['entry_threshold']}")
        print(f"   📉 Exit Threshold: {strategy_internal_config['exit_threshold']}")
        print(f"   📊 Min Histogram Threshold: {strategy_internal_config['min_histogram_threshold']}")
        print(f"   🔍 Confirmation Candles: {strategy_internal_config['confirmation_candles']}")
        
    except Exception as e:
        print(f"❌ Error initializing strategy: {e}")
        results['issues_found'].append(f"Strategy initialization error: {e}")
        return results
    
    # STEP 3: CONFIGURATION ADHERENCE CHECK
    print("\n🔍 STEP 3: CONFIGURATION ADHERENCE VERIFICATION")
    print("-" * 50)
    
    adherence_results = {}
    
    # Check MACD technical parameters
    macd_params = {
        'macd_fast': 12,  # Expected default
        'macd_slow': 26,  # Expected default
        'macd_signal': 9  # Expected default
    }
    
    for param, expected_default in macd_params.items():
        dashboard_value = dashboard_config.get(param, expected_default)
        strategy_value = getattr(macd_strategy, param, None)
        
        matches = dashboard_value == strategy_value
        adherence_results[param] = {
            'dashboard_value': dashboard_value,
            'strategy_value': strategy_value,
            'matches': matches
        }
        
        status = "✅" if matches else "❌"
        print(f"   {status} {param}: Dashboard={dashboard_value}, Strategy={strategy_value}")
        
        if not matches:
            results['issues_found'].append(f"{param} mismatch: Dashboard={dashboard_value}, Strategy={strategy_value}")
    
    # Check threshold parameters
    threshold_params = {
        'min_histogram_threshold': 0.0001,
        'macd_entry_threshold': 0.0015,
        'macd_exit_threshold': 0.002
    }
    
    for param, expected_default in threshold_params.items():
        dashboard_value = dashboard_config.get(param, expected_default)
        
        # Map dashboard parameter names to strategy attribute names
        if param == 'macd_entry_threshold':
            strategy_attr = 'entry_threshold'
        elif param == 'macd_exit_threshold':
            strategy_attr = 'exit_threshold'
        else:
            strategy_attr = param
            
        strategy_value = getattr(macd_strategy, strategy_attr, None)
        
        matches = abs(float(dashboard_value) - float(strategy_value)) < 0.000001 if dashboard_value is not None and strategy_value is not None else dashboard_value == strategy_value
        
        adherence_results[param] = {
            'dashboard_value': dashboard_value,
            'strategy_value': strategy_value,
            'matches': matches
        }
        
        status = "✅" if matches else "❌"
        print(f"   {status} {param}: Dashboard={dashboard_value}, Strategy={strategy_value}")
        
        if not matches:
            results['issues_found'].append(f"{param} mismatch: Dashboard={dashboard_value}, Strategy={strategy_value}")
    
    # Check confirmation candles
    dashboard_confirmation = dashboard_config.get('confirmation_candles', 1)
    strategy_confirmation = macd_strategy.confirmation_candles
    confirmation_matches = dashboard_confirmation == strategy_confirmation
    
    adherence_results['confirmation_candles'] = {
        'dashboard_value': dashboard_confirmation,
        'strategy_value': strategy_confirmation,
        'matches': confirmation_matches
    }
    
    status = "✅" if confirmation_matches else "❌"
    print(f"   {status} confirmation_candles: Dashboard={dashboard_confirmation}, Strategy={strategy_confirmation}")
    
    if not confirmation_matches:
        results['issues_found'].append(f"confirmation_candles mismatch: Dashboard={dashboard_confirmation}, Strategy={strategy_confirmation}")
    
    results['adherence_check'] = adherence_results
    
    # STEP 4: TEST REAL MARKET DATA WITH CONFIGURATIONS
    print("\n📊 STEP 4: TESTING WITH REAL MARKET DATA")
    print("-" * 50)
    
    try:
        binance_client = BinanceClientWrapper()
        symbol = dashboard_config.get('symbol', 'BTCUSDT')
        timeframe = dashboard_config.get('timeframe', '5m')
        
        print(f"📈 Fetching data for {symbol} on {timeframe} timeframe...")
        
        # Get historical data
        klines = binance_client.client.get_historical_klines(symbol, timeframe, "100")
        
        if klines:
            # Convert to DataFrame
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            
            # Convert to proper types
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col])
            
            print(f"✅ Retrieved {len(df)} candles of data")
            
            # Calculate indicators using strategy
            df_with_indicators = macd_strategy.calculate_indicators(df.copy())
            
            if 'macd' in df_with_indicators.columns:
                current_macd = df_with_indicators['macd'].iloc[-1]
                current_signal = df_with_indicators['macd_signal'].iloc[-1]
                current_histogram = df_with_indicators['macd_histogram'].iloc[-1]
                current_price = df_with_indicators['close'].iloc[-1]
                
                print(f"📊 Current Market Indicators (using strategy config):")
                print(f"   💰 Price: ${current_price:.4f}")
                print(f"   📈 MACD: {current_macd:.6f}")
                print(f"   📶 Signal: {current_signal:.6f}")
                print(f"   📊 Histogram: {current_histogram:.6f}")
                
                # Test signal generation
                signal = macd_strategy.evaluate_entry_signal(df_with_indicators)
                
                if signal:
                    print(f"🎯 Signal Generated: {signal.signal_type.value}")
                    print(f"📝 Reason: {signal.reason}")
                    print(f"💰 Entry Price: ${signal.entry_price:.4f}")
                    print(f"🛑 Stop Loss: ${signal.stop_loss:.4f}")
                    print(f"🎯 Take Profit: ${signal.take_profit:.4f}")
                else:
                    print(f"⚪ No signal generated under current market conditions")
                
                # Test strategy status
                status = macd_strategy.get_strategy_status(df_with_indicators)
                print(f"📊 Strategy Status: {status.get('divergence_status', 'N/A')}")
                
            else:
                print(f"❌ Indicators not calculated properly")
                results['issues_found'].append("Indicators not calculated properly")
                
        else:
            print(f"❌ No market data retrieved")
            results['issues_found'].append("No market data retrieved")
            
    except Exception as e:
        print(f"❌ Error testing with market data: {e}")
        results['issues_found'].append(f"Market data test error: {e}")
    
    # STEP 5: ANALYSIS AND RECOMMENDATIONS
    print("\n📋 STEP 5: ANALYSIS AND RECOMMENDATIONS")
    print("-" * 50)
    
    total_params_checked = len(adherence_results)
    matching_params = sum(1 for result in adherence_results.values() if result['matches'])
    adherence_percentage = (matching_params / total_params_checked) * 100 if total_params_checked > 0 else 0
    
    print(f"📊 Configuration Adherence: {matching_params}/{total_params_checked} ({adherence_percentage:.1f}%)")
    
    if adherence_percentage == 100:
        print("✅ PERFECT ADHERENCE: Strategy is using all dashboard configurations correctly")
        results['recommendations'].append("No issues found - strategy is properly adhering to dashboard configurations")
    elif adherence_percentage >= 80:
        print("⚠️ MOSTLY ADHERING: Minor configuration mismatches found")
        results['recommendations'].append("Review and fix minor configuration mismatches")
    else:
        print("❌ POOR ADHERENCE: Significant configuration mismatches found")
        results['recommendations'].append("Major configuration synchronization issues need immediate attention")
    
    # Specific recommendations based on issues found
    if results['issues_found']:
        print(f"\n🔧 Issues Found ({len(results['issues_found'])}):")
        for i, issue in enumerate(results['issues_found'], 1):
            print(f"   {i}. {issue}")
        
        # Generate specific recommendations
        if any('macd_fast' in issue or 'macd_slow' in issue or 'macd_signal' in issue for issue in results['issues_found']):
            results['recommendations'].append("Check MACD period parameters in dashboard configuration")
        
        if any('threshold' in issue for issue in results['issues_found']):
            results['recommendations'].append("Review threshold parameters for entry/exit sensitivity")
        
        if any('confirmation' in issue for issue in results['issues_found']):
            results['recommendations'].append("Verify confirmation candles setting for signal reliability")
    
    # Save results
    results_filename = f"macd_dashboard_adherence_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    try:
        with open(results_filename, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n💾 Results saved to: {results_filename}")
    except Exception as e:
        print(f"⚠️ Could not save results: {e}")
    
    return results

if __name__ == "__main__":
    try:
        results = diagnose_macd_dashboard_adherence()
        
        print("\n" + "="*80)
        print("🎯 DIAGNOSTIC COMPLETE")
        print("="*80)
        
        if not results['issues_found']:
            print("✅ SUCCESS: MACD strategy is properly adhering to dashboard configurations")
        else:
            print(f"⚠️ {len(results['issues_found'])} configuration adherence issues found")
            print("🔧 Review the detailed analysis above for specific recommendations")
            
    except Exception as e:
        print(f"💥 Diagnostic failed: {e}")
        import traceback
        traceback.print_exc()
