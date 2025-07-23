
#!/usr/bin/env python3
"""
Clean MACD Test Runner - Isolated test environment
"""

import sys
import os
import signal
import logging
from datetime import datetime

# Clean environment setup
sys.path.insert(0, 'src')

def cleanup_processes():
    """Clean up any hanging processes"""
    try:
        # Kill any existing python processes that might interfere
        os.system("pkill -f 'test_macd' 2>/dev/null || true")
        os.system("pkill -f 'macd_test' 2>/dev/null || true")
    except:
        pass

def run_macd_test():
    """Run MACD test in clean environment"""
    cleanup_processes()
    
    try:
        # Import and run the test
        from test_macd_comprehensive import test_macd_signal_detection_comprehensive
        
        print("🚀 Starting Clean MACD Signal Detection Test")
        print("=" * 80)
        
        success = test_macd_signal_detection_comprehensive()
        
        if success:
            print("\n✅ MACD TEST COMPLETED SUCCESSFULLY")
            return True
        else:
            print("\n❌ MACD TEST FAILED")
            return False
            
    except Exception as e:
        print(f"❌ Error running MACD test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Set up signal handlers for clean exit
    def signal_handler(signum, frame):
        print("\n🛑 Test interrupted - cleaning up...")
        cleanup_processes()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run the test
    success = run_macd_test()
    sys.exit(0 if success else 1)
