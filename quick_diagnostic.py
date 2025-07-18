
#!/usr/bin/env python3
"""
Quick Diagnostic Tool
Check what's preventing bot startup
"""

import sys
import os
import time
import signal
from datetime import datetime

def timeout_handler(signum, frame):
    print(f"❌ TIMEOUT: Step took too long")
    raise TimeoutError("Diagnostic step timed out")

def safe_test(test_name, test_func, timeout_seconds=5):
    """Safely run a test with timeout"""
    print(f"🔍 Testing {test_name}...")
    
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout_seconds)
    
    try:
        result = test_func()
        signal.alarm(0)
        if result:
            print(f"✅ {test_name}: PASSED")
        else:
            print(f"❌ {test_name}: FAILED")
        return result
    except TimeoutError:
        print(f"⏰ {test_name}: TIMEOUT after {timeout_seconds}s")
        return False
    except Exception as e:
        print(f"❌ {test_name}: ERROR - {e}")
        return False
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)

def test_imports():
    """Test if all imports work"""
    try:
        from src.config.global_config import global_config
        from src.binance_client.client import BinanceClientWrapper
        return True
    except Exception as e:
        print(f"Import error: {e}")
        return False

def test_config():
    """Test configuration loading"""
    try:
        from src.config.global_config import global_config
        return global_config.BINANCE_API_KEY is not None
    except Exception as e:
        print(f"Config error: {e}")
        return False

def test_binance_client():
    """Test Binance client creation"""
    try:
        from src.binance_client.client import BinanceClientWrapper
        client = BinanceClientWrapper()
        return True
    except Exception as e:
        print(f"Binance client error: {e}")
        return False

def test_connection():
    """Test Binance connection"""
    try:
        from src.binance_client.client import BinanceClientWrapper
        client = BinanceClientWrapper()
        return client.test_connection()
    except Exception as e:
        print(f"Connection error: {e}")
        return False

def main():
    print("🔍 QUICK DIAGNOSTIC TOOL")
    print("=" * 50)
    print(f"⏰ Time: {datetime.now().strftime('%H:%M:%S')}")
    print()
    
    # Test sequence
    tests = [
        ("Basic Imports", test_imports, 5),
        ("Configuration", test_config, 3),
        ("Binance Client Creation", test_binance_client, 10),
        ("API Connection", test_connection, 15)
    ]
    
    results = []
    for test_name, test_func, timeout in tests:
        result = safe_test(test_name, test_func, timeout)
        results.append((test_name, result))
        time.sleep(1)  # Brief pause between tests
    
    print()
    print("📊 DIAGNOSTIC SUMMARY:")
    print("=" * 30)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    failed_tests = [name for name, result in results if not result]
    
    if failed_tests:
        print(f"\n💡 RECOMMENDATIONS:")
        if "Basic Imports" in failed_tests:
            print("- Check if all required files exist in src/")
        if "Configuration" in failed_tests:
            print("- Verify API keys are set correctly")
        if "Binance Client Creation" in failed_tests:
            print("- Check src/binance_client/client.py for errors")
        if "API Connection" in failed_tests:
            print("- Network/geographic restrictions likely")
            print("- Try using a VPN or proxy")
    else:
        print("\n✅ ALL TESTS PASSED - Bot should start normally")

if __name__ == "__main__":
    main()
