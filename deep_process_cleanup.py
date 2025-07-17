
#!/usr/bin/env python3
"""
Deep Process Cleanup
Find and eliminate ALL conflicting processes
"""

import os
import sys
import time
import subprocess
import json
import psutil
import signal
from pathlib import Path

def find_all_python_processes():
    """Find all Python processes that might be related to our bot"""
    print("🔍 SCANNING ALL PYTHON PROCESSES...")
    
    conflicting_processes = []
    current_pid = os.getpid()
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time', 'status']):
        try:
            if proc.info['pid'] == current_pid:
                continue
                
            name = proc.info['name'].lower()
            cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
            
            # Check for Python processes
            if 'python' in name:
                # Check for bot-related processes
                if any(keyword in cmdline for keyword in [
                    'main.py', 'web_dashboard', 'flask', 'bot_manager', 
                    'trading', 'binance', 'order_manager'
                ]):
                    age_seconds = time.time() - proc.info['create_time']
                    conflicting_processes.append({
                        'pid': proc.info['pid'],
                        'name': name,
                        'cmdline': cmdline,
                        'age_minutes': age_seconds / 60,
                        'status': proc.info['status']
                    })
                    
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    return conflicting_processes

def find_port_users():
    """Find processes using port 5000"""
    print("🔍 CHECKING PORT 5000 USAGE...")
    
    port_users = []
    
    try:
        for conn in psutil.net_connections(kind='inet'):
            if conn.laddr.port == 5000:
                try:
                    proc = psutil.Process(conn.pid)
                    port_users.append({
                        'pid': conn.pid,
                        'name': proc.name(),
                        'cmdline': ' '.join(proc.cmdline()),
                        'status': conn.status
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    port_users.append({
                        'pid': conn.pid,
                        'name': 'Unknown',
                        'cmdline': 'Access Denied',
                        'status': conn.status
                    })
    except Exception as e:
        print(f"⚠️ Error checking port connections: {e}")
    
    return port_users

def kill_process_tree(pid):
    """Kill a process and all its children"""
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        
        # Kill children first
        for child in children:
            try:
                print(f"  🔧 Killing child process {child.pid}")
                child.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Kill parent
        try:
            print(f"  🔧 Killing parent process {pid}")
            parent.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        
        # Wait for termination
        gone, alive = psutil.wait_procs(children + [parent], timeout=3)
        
        # Force kill if still alive
        for proc in alive:
            try:
                print(f"  💥 Force killing {proc.pid}")
                proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
                
        return True
    except Exception as e:
        print(f"❌ Error killing process {pid}: {e}")
        return False

def nuclear_cleanup():
    """Nuclear option: kill everything related"""
    print("💣 NUCLEAR CLEANUP MODE")
    
    # Kill by process name patterns
    kill_patterns = [
        'python main.py',
        'python web_dashboard',
        'flask',
        'python -c'  # Sometimes Flask runs this way
    ]
    
    for pattern in kill_patterns:
        try:
            cmd = ['pkill', '-f', pattern]
            result = subprocess.run(cmd, capture_output=True, timeout=10)
            print(f"🔧 Executed: {' '.join(cmd)} (exit code: {result.returncode})")
        except Exception as e:
            print(f"⚠️ Pattern kill failed for '{pattern}': {e}")
    
    # Kill by port (if lsof is available)
    try:
        result = subprocess.run(['lsof', '-ti:5000'], capture_output=True, timeout=5)
        if result.returncode == 0:
            pids = result.stdout.decode().strip().split('\n')
            for pid in pids:
                if pid.strip():
                    try:
                        subprocess.run(['kill', '-9', pid.strip()], timeout=3)
                        print(f"🔧 Killed PID {pid.strip()} using port 5000")
                    except Exception as e:
                        print(f"⚠️ Failed to kill PID {pid}: {e}")
    except Exception as e:
        print(f"⚠️ lsof not available or failed: {e}")

def wait_for_port_clear():
    """Wait for port 5000 to become available"""
    print("⏳ WAITING FOR PORT 5000 TO CLEAR...")
    
    for attempt in range(30):  # 30 second timeout
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('localhost', 5000))
            sock.close()
            
            if result != 0:
                print("✅ Port 5000 is now free")
                return True
            else:
                print(f"⏳ Port 5000 still occupied (attempt {attempt + 1}/30)")
                time.sleep(1)
        except Exception as e:
            print(f"🔍 Port check error: {e}")
            time.sleep(1)
    
    print("❌ Port 5000 did not clear within 30 seconds")
    return False

def clean_filesystem():
    """Clean up filesystem artifacts"""
    print("🧹 CLEANING FILESYSTEM...")
    
    cleanup_items = [
        ".pytest_cache",
        "__pycache__",
        "*.pyc",
        ".flask_session",
        "flask_session",
        "trading_data/temp",
        "trading_data/*.lock",
        "*.pid"
    ]
    
    for item in cleanup_items:
        try:
            import glob
            for path in glob.glob(item, recursive=True):
                if os.path.isfile(path):
                    os.remove(path)
                    print(f"🗑️ Removed file: {path}")
                elif os.path.isdir(path):
                    import shutil
                    shutil.rmtree(path)
                    print(f"🗑️ Removed directory: {path}")
        except Exception as e:
            print(f"⚠️ Could not clean {item}: {e}")

def main():
    print("🕵️ DEEP PROCESS CLEANUP AND DIAGNOSIS")
    print("=" * 60)
    
    # Step 1: Find all conflicting processes
    python_processes = find_all_python_processes()
    
    if python_processes:
        print(f"\n🚨 FOUND {len(python_processes)} CONFLICTING PYTHON PROCESSES:")
        for proc in python_processes:
            print(f"  PID: {proc['pid']}")
            print(f"  Name: {proc['name']}")
            print(f"  Command: {proc['cmdline'][:100]}...")
            print(f"  Age: {proc['age_minutes']:.1f} minutes")
            print(f"  Status: {proc['status']}")
            print("  " + "-" * 50)
    
    # Step 2: Check port usage
    port_users = find_port_users()
    
    if port_users:
        print(f"\n🔌 FOUND {len(port_users)} PROCESSES USING PORT 5000:")
        for user in port_users:
            print(f"  PID: {user['pid']}")
            print(f"  Name: {user['name']}")
            print(f"  Command: {user['cmdline'][:100]}...")
            print(f"  Status: {user['status']}")
            print("  " + "-" * 50)
    
    # Step 3: Show summary
    if not python_processes and not port_users:
        print("\n✅ NO CONFLICTING PROCESSES FOUND")
        print("The issue might be elsewhere. Let's clean up anyway...")
    
    # Step 4: Kill everything
    print(f"\n💀 TERMINATING ALL CONFLICTING PROCESSES...")
    
    all_pids = set()
    
    # Collect all PIDs to kill
    for proc in python_processes:
        all_pids.add(proc['pid'])
    
    for user in port_users:
        all_pids.add(user['pid'])
    
    # Kill processes one by one
    for pid in all_pids:
        print(f"🎯 Targeting PID {pid}")
        kill_process_tree(pid)
    
    # Nuclear cleanup
    nuclear_cleanup()
    
    # Step 5: Clean filesystem
    clean_filesystem()
    
    # Step 6: Wait for port to clear
    port_cleared = wait_for_port_clear()
    
    # Step 7: Force environment reset
    print("\n⚙️ FORCING ENVIRONMENT RESET...")
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
    
    # Step 8: Final verification
    print("\n🔍 FINAL VERIFICATION...")
    remaining_processes = find_all_python_processes()
    remaining_port_users = find_port_users()
    
    if remaining_processes:
        print(f"⚠️ WARNING: {len(remaining_processes)} processes still running:")
        for proc in remaining_processes:
            print(f"  PID {proc['pid']}: {proc['cmdline'][:50]}...")
    else:
        print("✅ No conflicting Python processes found")
    
    if remaining_port_users:
        print(f"⚠️ WARNING: {len(remaining_port_users)} processes still using port 5000:")
        for user in remaining_port_users:
            print(f"  PID {user['pid']}: {user['name']}")
    else:
        print("✅ Port 5000 is clear")
    
    print("\n" + "=" * 60)
    print("🎯 CLEANUP COMPLETE")
    
    if not remaining_processes and not remaining_port_users and port_cleared:
        print("✅ SYSTEM IS CLEAN - Ready for fresh start")
        print("\n🚀 You can now start the bot with: python main.py")
    else:
        print("⚠️ SOME ISSUES REMAIN - Manual intervention may be needed")
        print("\n💡 Try restarting your Repl completely")

if __name__ == "__main__":
    main()
