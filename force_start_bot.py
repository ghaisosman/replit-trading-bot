
#!/usr/bin/env python3
"""
Force Start Bot
Cleans up all locks and forces bot startup
"""

import os
import sys
import time
import subprocess
import logging

def main():
    """Force clean startup"""
    print("🧹 FORCE STARTUP: Cleaning system...")
    
    # Clean all lock files
    lock_files = [
        "/tmp/bot_restart_lock",
        "/tmp/web_dashboard.lock", 
        "/tmp/bot_restart_count"
    ]
    
    for lock_file in lock_files:
        try:
            if os.path.exists(lock_file):
                os.remove(lock_file)
                print(f"🧹 Removed: {os.path.basename(lock_file)}")
        except Exception as e:
            print(f"⚠️ Could not remove {lock_file}: {e}")

    # Kill any existing bot processes
    print("🔄 Cleaning up existing processes...")
    try:
        subprocess.run(['pkill', '-f', 'python main.py'], capture_output=True)
        subprocess.run(['pkill', '-f', 'web_dashboard'], capture_output=True)
        subprocess.run(['pkill', '-f', 'flask'], capture_output=True)
        time.sleep(2)
        print("✅ Process cleanup completed")
    except Exception as e:
        print(f"⚠️ Process cleanup failed: {e}")

    print("🚀 Starting bot with clean slate...")
    
    # Start the bot
    try:
        result = subprocess.run([sys.executable, 'main.py'], 
                              capture_output=False, 
                              text=True)
        return result.returncode
    except KeyboardInterrupt:
        print("\n🔴 Startup interrupted by user")
        return 0
    except Exception as e:
        print(f"❌ Failed to start bot: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
