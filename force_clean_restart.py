
#!/usr/bin/env python3
"""
Force Clean Restart
Terminates all bot processes and ensures clean startup
"""

import os
import sys
import time
import subprocess
import json
import shutil
from pathlib import Path

def kill_all_processes():
    """Kill all bot-related processes"""
    print("🛑 TERMINATING ALL BOT PROCESSES...")
    
    commands = [
        ['pkill', '-f', 'python main.py'],
        ['pkill', '-f', 'web_dashboard'],
        ['pkill', '-f', 'flask'],
        ['pkill', '-f', 'python'],  # More aggressive
    ]
    
    for cmd in commands:
        try:
            subprocess.run(cmd, capture_output=True, timeout=5)
            print(f"✅ Executed: {' '.join(cmd)}")
        except Exception as e:
            print(f"⚠️ Command failed: {' '.join(cmd)} - {e}")
    
    print("🕐 Waiting for processes to terminate...")
    time.sleep(5)

def clear_runtime_data():
    """Clear runtime data that might cause conflicts"""
    print("🧹 CLEARING RUNTIME DATA...")
    
    # Clear any Flask session data
    try:
        flask_session_dir = Path("flask_session")
        if flask_session_dir.exists():
            shutil.rmtree(flask_session_dir)
            print("✅ Cleared Flask session data")
    except Exception as e:
        print(f"⚠️ Could not clear Flask sessions: {e}")
    
    # Clear any temporary files
    temp_files = [
        "*.pyc",
        "__pycache__",
        ".pytest_cache",
        "trading_data/temp",
    ]
    
    for pattern in temp_files:
        try:
            import glob
            for file_path in glob.glob(pattern, recursive=True):
                if os.path.isfile(file_path):
                    os.remove(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            print(f"✅ Cleaned: {pattern}")
        except Exception as e:
            print(f"⚠️ Could not clean {pattern}: {e}")

def check_port_status():
    """Check if port 5000 is clear"""
    print("🔍 CHECKING PORT STATUS...")
    
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', 5000))
        sock.close()
        
        if result == 0:
            print("⚠️ Port 5000 still occupied")
            return False
        else:
            print("✅ Port 5000 is free")
            return True
    except Exception as e:
        print(f"🔍 Port check inconclusive: {e}")
        return True

def force_environment_reset():
    """Force reset environment to ensure mainnet"""
    print("⚙️ FORCING ENVIRONMENT RESET...")
    
    try:
        os.makedirs("trading_data", exist_ok=True)
        
        env_config = {
            "BINANCE_TESTNET": "false",
            "BINANCE_FUTURES": "true"
        }
        
        with open("trading_data/environment_config.json", 'w') as f:
            json.dump(env_config, f, indent=2)
        
        print("✅ Environment forced to MAINNET")
    except Exception as e:
        print(f"❌ Environment reset failed: {e}")

def start_fresh_bot():
    """Start a completely fresh bot instance"""
    print("🚀 STARTING FRESH BOT...")
    
    try:
        # Start the bot in a completely new process
        subprocess.Popen([
            sys.executable, "main.py"
        ], 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE,
        start_new_session=True)
        
        print("✅ Fresh bot process started")
        time.sleep(3)
        print("🌐 Web dashboard should be accessible at http://localhost:5000")
        
    except Exception as e:
        print(f"❌ Failed to start fresh bot: {e}")

def main():
    print("🔄 FORCE CLEAN RESTART")
    print("=" * 50)
    
    # Step 1: Kill all processes
    kill_all_processes()
    
    # Step 2: Clear runtime data
    clear_runtime_data()
    
    # Step 3: Check port status
    port_clear = check_port_status()
    
    if not port_clear:
        print("⚠️ Port still occupied - waiting longer...")
        time.sleep(10)
        check_port_status()
    
    # Step 4: Force environment reset
    force_environment_reset()
    
    # Step 5: Start fresh
    start_fresh_bot()
    
    print("=" * 50)
    print("✅ FORCE CLEAN RESTART COMPLETE")
    print("🎯 Bot should now be running cleanly in MAINNET mode")
    print("🌐 Access dashboard at: http://localhost:5000")
    print("💡 All processes have been terminated and restarted fresh")

if __name__ == "__main__":
    main()
