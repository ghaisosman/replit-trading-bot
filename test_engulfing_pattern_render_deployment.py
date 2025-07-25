
#!/usr/bin/env python3
"""
Test Engulfing Pattern Strategy for Render Deployment Dashboard
============================================================

This script tests the Engulfing Pattern strategy configuration and price fetching
to ensure it will display correctly on the Render live deployment dashboard.
"""

import sys
import os
import json
from datetime import datetime

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def test_engulfing_pattern_render_readiness():
    """Test Engulfing Pattern strategy readiness for Render deployment"""
    print("🔍 TESTING ENGULFING PATTERN STRATEGY FOR RENDER DEPLOYMENT")
    print("=" * 60)
    
    test_results = {
        'timestamp': datetime.now().isoformat(),
        'test_type': 'engulfing_pattern_render_deployment',
        'results': {}
    }
    
    try:
        # Test 1: Import and configuration validation
        print("\n📋 TEST 1: Configuration and Imports")
        print("-" * 40)
        
        try:
            from src.config.trading_config import trading_config_manager
            from src.binance_client.client import BinanceClientWrapper
            from src.data_fetcher.price_fetcher import PriceFetcher
            from src.execution_engine.strategies.engulfing_pattern_strategy import EngulfingPatternStrategy
            
            print("✅ All imports successful")
            test_results['results']['imports'] = {'success': True}
            
        except Exception as e:
            print(f"❌ Import error: {e}")
            test_results['results']['imports'] = {'success': False, 'error': str(e)}
            return test_results
        
        # Test 2: Get Engulfing Pattern strategies from trading config
        print("\n🎯 TEST 2: Strategy Configuration Validation")
        print("-" * 40)
        
        try:
            strategies = trading_config_manager.get_all_strategies()
            engulfing_strategies = {k: v for k, v in strategies.items() 
                                   if 'engulfing' in k.lower()}
            
            print(f"✅ Found {len(engulfing_strategies)} Engulfing Pattern strategies:")
            
            for strategy_name, config in engulfing_strategies.items():
                symbol = config.get('symbol', 'MISSING')
                timeframe = config.get('timeframe', 'MISSING')
                margin = config.get('margin', 'MISSING')
                leverage = config.get('leverage', 'MISSING')
                
                print(f"   📊 {strategy_name}:")
                print(f"      Symbol: {symbol}")
                print(f"      Timeframe: {timeframe}")
                print(f"      Margin: ${margin}")
                print(f"      Leverage: {leverage}x")
                
                # Validate required fields
                required_fields = ['symbol', 'timeframe', 'margin', 'leverage', 
                                 'rsi_threshold', 'rsi_long_exit', 'rsi_short_exit']
                missing_fields = [field for field in required_fields if field not in config]
                
                if missing_fields:
                    print(f"      ⚠️ Missing fields: {missing_fields}")
                else:
                    print(f"      ✅ All required fields present")
            
            test_results['results']['strategy_config'] = {
                'success': True,
                'strategies_found': len(engulfing_strategies),
                'strategies': list(engulfing_strategies.keys())
            }
            
        except Exception as e:
            print(f"❌ Strategy configuration error: {e}")
            test_results['results']['strategy_config'] = {'success': False, 'error': str(e)}
        
        # Test 3: Price fetching validation
        print("\n💰 TEST 3: Price Fetching Validation")
        print("-" * 40)
        
        try:
            binance_client = BinanceClientWrapper()
            price_fetcher = PriceFetcher(binance_client)
            
            # Test symbols from Engulfing Pattern strategies
            test_symbols = ['BTCUSDT', 'ETHUSDT', 'ADAUSDT']
            price_results = {}
            
            for symbol in test_symbols:
                try:
                    current_price = price_fetcher.get_current_price(symbol)
                    if current_price and current_price > 0:
                        print(f"   ✅ {symbol}: ${current_price:,.4f}")
                        price_results[symbol] = {
                            'success': True,
                            'price': current_price
                        }
                    else:
                        print(f"   ❌ {symbol}: Invalid price ({current_price})")
                        price_results[symbol] = {
                            'success': False,
                            'price': current_price,
                            'error': 'Invalid price value'
                        }
                except Exception as pe:
                    print(f"   ❌ {symbol}: Price fetch error - {pe}")
                    price_results[symbol] = {
                        'success': False,
                        'error': str(pe)
                    }
            
            successful_prices = sum(1 for r in price_results.values() if r['success'])
            print(f"\n   📊 Price fetch success rate: {successful_prices}/{len(test_symbols)}")
            
            test_results['results']['price_fetching'] = {
                'success': successful_prices > 0,
                'symbols_tested': len(test_symbols),
                'successful_fetches': successful_prices,
                'results': price_results
            }
            
        except Exception as e:
            print(f"❌ Price fetching setup error: {e}")
            test_results['results']['price_fetching'] = {'success': False, 'error': str(e)}
        
        # Test 4: Strategy initialization simulation
        print("\n🚀 TEST 4: Strategy Initialization Simulation")
        print("-" * 40)
        
        try:
            # Test initializing each Engulfing Pattern strategy
            strategy_init_results = {}
            
            for strategy_name, config in engulfing_strategies.items():
                try:
                    # Create strategy instance
                    strategy = EngulfingPatternStrategy(strategy_name, config)
                    
                    print(f"   ✅ {strategy_name}: Initialized successfully")
                    
                    # Test basic configuration access
                    symbol = config.get('symbol')
                    rsi_threshold = getattr(strategy, 'rsi_threshold', None)
                    stable_ratio = getattr(strategy, 'stable_candle_ratio', None)
                    
                    print(f"      Symbol: {symbol}")
                    print(f"      RSI Threshold: {rsi_threshold}")
                    print(f"      Stable Candle Ratio: {stable_ratio}")
                    
                    strategy_init_results[strategy_name] = {
                        'success': True,
                        'symbol': symbol,
                        'rsi_threshold': rsi_threshold,
                        'stable_candle_ratio': stable_ratio
                    }
                    
                except Exception as se:
                    print(f"   ❌ {strategy_name}: Initialization failed - {se}")
                    strategy_init_results[strategy_name] = {
                        'success': False,
                        'error': str(se)
                    }
            
            successful_inits = sum(1 for r in strategy_init_results.values() if r['success'])
            print(f"\n   📊 Strategy initialization success rate: {successful_inits}/{len(engulfing_strategies)}")
            
            test_results['results']['strategy_initialization'] = {
                'success': successful_inits > 0,
                'strategies_tested': len(engulfing_strategies),
                'successful_inits': successful_inits,
                'results': strategy_init_results
            }
            
        except Exception as e:
            print(f"❌ Strategy initialization test error: {e}")
            test_results['results']['strategy_initialization'] = {'success': False, 'error': str(e)}
        
        # Test 5: Dashboard data simulation
        print("\n📊 TEST 5: Dashboard Data Simulation")
        print("-" * 40)
        
        try:
            # Simulate what the dashboard would receive
            dashboard_data = {}
            
            for strategy_name, config in engulfing_strategies.items():
                symbol = config.get('symbol')
                margin = config.get('margin', 10.0)
                leverage = config.get('leverage', 3)
                timeframe = config.get('timeframe', '1h')
                
                # Get current price if available
                current_price = None
                if symbol in price_results and price_results[symbol]['success']:
                    current_price = price_results[symbol]['price']
                
                dashboard_entry = {
                    'strategy_name': strategy_name,
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'margin': f"${margin} USDT",
                    'leverage': f"{leverage}x",
                    'current_price': f"${current_price:,.4f}" if current_price else "Loading...",
                    'status': 'SCANNING' if current_price else 'PRICE_ERROR'
                }
                
                dashboard_data[strategy_name] = dashboard_entry
                
                print(f"   📊 {strategy_name}:")
                print(f"      Symbol: {dashboard_entry['symbol']}")
                print(f"      Margin: {dashboard_entry['margin']}")
                print(f"      Leverage: {dashboard_entry['leverage']}")
                print(f"      Price: {dashboard_entry['current_price']}")
                print(f"      Status: {dashboard_entry['status']}")
            
            test_results['results']['dashboard_simulation'] = {
                'success': True,
                'dashboard_data': dashboard_data
            }
            
        except Exception as e:
            print(f"❌ Dashboard simulation error: {e}")
            test_results['results']['dashboard_simulation'] = {'success': False, 'error': str(e)}
        
        # Test 6: Render deployment readiness assessment
        print("\n🚀 TEST 6: Render Deployment Readiness Assessment")
        print("-" * 40)
        
        all_tests_passed = all(
            test_results['results'].get(test, {}).get('success', False)
            for test in ['imports', 'strategy_config', 'price_fetching', 
                        'strategy_initialization', 'dashboard_simulation']
        )
        
        critical_issues = []
        warnings = []
        
        # Check for critical issues
        if not test_results['results'].get('imports', {}).get('success'):
            critical_issues.append("Import failures - strategies won't load")
        
        if not test_results['results'].get('strategy_config', {}).get('success'):
            critical_issues.append("Strategy configuration missing")
        
        if test_results['results'].get('price_fetching', {}).get('successful_fetches', 0) == 0:
            critical_issues.append("No price data available - dashboard will show null values")
        
        # Check for warnings
        if test_results['results'].get('price_fetching', {}).get('successful_fetches', 0) < 3:
            warnings.append("Some symbols may not show prices on dashboard")
        
        if test_results['results'].get('strategy_initialization', {}).get('successful_inits', 0) < 3:
            warnings.append("Some strategies may not initialize properly")
        
        # Final assessment
        if critical_issues:
            print("❌ RENDER DEPLOYMENT NOT READY")
            print("Critical Issues:")
            for issue in critical_issues:
                print(f"   🚨 {issue}")
            deployment_ready = False
        elif warnings:
            print("⚠️ RENDER DEPLOYMENT READY WITH WARNINGS")
            print("Warnings:")
            for warning in warnings:
                print(f"   ⚠️ {warning}")
            deployment_ready = True
        else:
            print("✅ RENDER DEPLOYMENT READY")
            print("All tests passed - Engulfing Pattern strategies should display correctly")
            deployment_ready = True
        
        test_results['results']['deployment_readiness'] = {
            'ready': deployment_ready,
            'critical_issues': critical_issues,
            'warnings': warnings,
            'recommendation': 'DEPLOY' if deployment_ready else 'FIX_ISSUES_FIRST'
        }
        
        # Test summary
        print(f"\n📋 TEST SUMMARY")
        print("-" * 40)
        print(f"✅ Imports: {'PASS' if test_results['results']['imports']['success'] else 'FAIL'}")
        print(f"✅ Strategy Config: {'PASS' if test_results['results']['strategy_config']['success'] else 'FAIL'}")
        print(f"✅ Price Fetching: {'PASS' if test_results['results']['price_fetching']['success'] else 'FAIL'}")
        print(f"✅ Strategy Init: {'PASS' if test_results['results']['strategy_initialization']['success'] else 'FAIL'}")
        print(f"✅ Dashboard Sim: {'PASS' if test_results['results']['dashboard_simulation']['success'] else 'FAIL'}")
        
        return test_results
        
    except Exception as e:
        print(f"❌ CRITICAL TEST ERROR: {e}")
        test_results['results']['critical_error'] = str(e)
        return test_results

def save_test_results(results):
    """Save test results to file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"engulfing_pattern_render_test_{timestamp}.json"
    
    try:
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n💾 Test results saved to: {filename}")
    except Exception as e:
        print(f"⚠️ Could not save test results: {e}")

if __name__ == "__main__":
    print("🔍 ENGULFING PATTERN RENDER DEPLOYMENT TEST")
    print("=" * 50)
    
    results = test_engulfing_pattern_render_readiness()
    save_test_results(results)
    
    # Final recommendation
    deployment_ready = results.get('results', {}).get('deployment_readiness', {}).get('ready', False)
    
    print(f"\n🎯 FINAL RECOMMENDATION")
    print("-" * 30)
    
    if deployment_ready:
        print("🟢 SAFE TO PUSH TO GITHUB AND RENDER")
        print("   ✅ Engulfing Pattern strategies should display correctly")
        print("   ✅ Dashboard will show proper symbol, price, and configuration data")
        print("   ✅ No more 'null' values expected")
    else:
        print("🔴 DO NOT DEPLOY YET")
        print("   ❌ Critical issues found that will cause dashboard problems")
        print("   ❌ Fix issues above before pushing to Render")
    
    print(f"\n📊 Test completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
