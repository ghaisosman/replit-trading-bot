
#!/usr/bin/env python3
"""
Ultimate Process Killer
Eliminate ALL conflicting processes with extreme prejudice
"""

import os
import sys
import time
import subprocess
import signal
import psutil

def find_main_py_processes():
    """Find all main.py processes"""
    processes = []
    current_pid = os.getpid()
    
    for proc in psutil.process_iter(['pid', 'ppid', 'name', 'cmdline', 'create_time']):
        try:
            if proc.info['cmdline']:
                cmdline = ' '.join(proc.info['cmdline'])
                if 'main.py' in cmdline and proc.info['pid'] != current_pid:
                    processes.append({
                        'pid': proc.info['pid'],
                        'ppid': proc.info['ppid'],
                        'cmdline': cmdline,
                        'age': time.time() - proc.info['create_time']
                    })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    return processes

def kill_process_and_children(pid):
    """Kill a process and all its children recursively"""
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        
        print(f"🎯 Killing PID {pid} and {len(children)} children")
        
        # Kill children first
        for child in children:
            try:
                child.terminate()
                print(f"  ├─ Terminated child {child.pid}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Kill parent
        try:
            parent.terminate()
            print(f"  └─ Terminated parent {pid}")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        
        # Wait for graceful termination
        gone, alive = psutil.wait_procs(children + [parent], timeout=3)
        
        # Force kill survivors
        for p in alive:
            try:
                p.kill()
                print(f"  💥 Force killed {p.pid}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        return True
    except Exception as e:
        print(f"❌ Error killing {pid}: {e}")
        return False

def nuclear_port_cleanup():
    """Nuclear cleanup of port 5000 - Replit compatible"""
    print("💣 NUCLEAR PORT 5000 CLEANUP")
    
    # Method 1: Check with psutil (more reliable in Replit)
    try:
        for conn in psutil.net_connections(kind='inet'):
            if conn.laddr.port == 5000 and conn.pid:
                try:
                    proc = psutil.Process(conn.pid)
                    proc.terminate()
                    print(f"🔫 Terminated PID {conn.pid} using port 5000")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
    except Exception as e:
        print(f"⚠️ psutil port check failed: {e}")
    
    # Method 2: Direct socket test and process elimination
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', 5000))
        sock.close()
        
        if result == 0:
            print("🔍 Port 5000 still occupied, scanning all Python processes...")
            # Kill all Python processes that might be web servers
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'].lower() in ['python', 'python3']:
                        if proc.info['cmdline']:
                            cmdline = ' '.join(proc.info['cmdline'])
                            if any(keyword in cmdline for keyword in ['flask', 'web_dashboard', 'main.py', ':5000']):
                                if proc.pid != os.getpid():
                                    proc.terminate()
                                    print(f"🔫 Killed potential web server PID {proc.pid}")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        else:
            print("✅ Port 5000 appears free")
    except Exception as e:
        print(f"⚠️ Socket test failed: {e}")
    
    # Method 3: Alternative pkill approach
    try:
        subprocess.run(['pkill', '-f', 'flask'], capture_output=True, timeout=5)
        subprocess.run(['pkill', '-f', 'web_dashboard'], capture_output=True, timeout=5)
        print("🔫 pkill cleanup executed")
    except Exception as e:
        print(f"⚠️ pkill cleanup failed: {e}")

def main():
    print("💀 ULTIMATE PROCESS KILLER")
    print("=" * 50)
    
    # Step 1: Find all main.py processes
    main_processes = find_main_py_processes()
    
    if main_processes:
        print(f"🚨 FOUND {len(main_processes)} main.py PROCESSES:")
        for proc in main_processes:
            print(f"  PID {proc['pid']} (PPID {proc['ppid']}) - Age: {proc['age']:.1f}s")
            print(f"    {proc['cmdline']}")
    else:
        print("✅ No main.py processes found")
    
    # Step 2: Kill all main.py processes
    for proc in main_processes:
        kill_process_and_children(proc['pid'])
    
    # Step 3: Nuclear port cleanup
    nuclear_port_cleanup()
    
    # Step 4: Kill any remaining Python processes
    print("\n🧹 CLEANING REMAINING PYTHON PROCESSES")
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['name'].lower() in ['python', 'python3']:
                if proc.info['cmdline']:
                    cmdline = ' '.join(proc.info['cmdline'])
                    if any(keyword in cmdline for keyword in ['flask', 'web_dashboard', 'main.py']):
                        if proc.pid != os.getpid():
                            try:
                                proc.kill()
                                print(f"🔫 Killed Python process {proc.pid}")
                            except:
                                pass
        except:
            continue
    
    # Step 5: Wait and verify
    print("\n⏳ WAITING FOR CLEANUP...")
    time.sleep(3)
    
    # Final verification
    remaining = find_main_py_processes()
    if remaining:
        print(f"⚠️ {len(remaining)} processes still running:")
        for proc in remaining:
            print(f"  PID {proc['pid']}: {proc['cmdline'][:50]}...")
    else:
        print("✅ ALL PROCESSES ELIMINATED")
    
    # Check port
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', 5000))
        sock.close()
        
        if result == 0:
            print("❌ Port 5000 still occupied")
        else:
            print("✅ Port 5000 is free")
    except:
        print("✅ Port 5000 appears free")

if __name__ == "__main__":
    main()
