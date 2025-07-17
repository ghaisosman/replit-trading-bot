
#!/usr/bin/env python3
"""
Simple Cleanup - Replit Compatible
Clean process conflicts without requiring external tools
"""

import os
import sys
import time
import psutil
import subprocess

def kill_main_py_processes():
    """Kill all main.py processes except current one"""
    print("🎯 KILLING MAIN.PY PROCESSES...")
    
    current_pid = os.getpid()
    killed_count = 0
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['cmdline']:
                cmdline = ' '.join(proc.info['cmdline'])
                if 'main.py' in cmdline and proc.info['pid'] != current_pid:
                    proc.terminate()
                    print(f"🔧 Terminated PID {proc.info['pid']}")
                    killed_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    if killed_count == 0:
        print("✅ No main.py processes to kill")
    else:
        print(f"✅ Killed {killed_count} processes")

def clear_port_5000():
    """Clear port 5000 using psutil"""
    print("🔌 CLEARING PORT 5000...")
    
    cleared_count = 0
    
    try:
        for conn in psutil.net_connections(kind='inet'):
            if conn.laddr.port == 5000 and conn.pid:
                try:
                    proc = psutil.Process(conn.pid)
                    if proc.pid != os.getpid():
                        proc.terminate()
                        print(f"🔧 Killed PID {proc.pid} on port 5000")
                        cleared_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
    except Exception as e:
        print(f"⚠️ Port clearing failed: {e}")
    
    if cleared_count == 0:
        print("✅ Port 5000 was already clear")
    else:
        print(f"✅ Cleared {cleared_count} processes from port 5000")

def test_port_status():
    """Test if port 5000 is free"""
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', 5000))
        sock.close()
        
        if result == 0:
            print("❌ Port 5000 is still occupied")
            return False
        else:
            print("✅ Port 5000 is free")
            return True
    except Exception as e:
        print(f"🔍 Port test inconclusive: {e}")
        return True

def main():
    print("🧹 SIMPLE CLEANUP - REPLIT COMPATIBLE")
    print("=" * 50)
    
    # Step 1: Kill main.py processes
    kill_main_py_processes()
    
    # Step 2: Clear port 5000
    clear_port_5000()
    
    # Step 3: Wait a moment
    print("⏳ Waiting 3 seconds...")
    time.sleep(3)
    
    # Step 4: Test port status
    port_free = test_port_status()
    
    # Step 5: Final result
    print("=" * 50)
    if port_free:
        print("✅ CLEANUP SUCCESSFUL")
        print("🚀 You can now start the bot")
    else:
        print("⚠️ CLEANUP INCOMPLETE")
        print("💡 Try restarting your Repl")

if __name__ == "__main__":
    main()
