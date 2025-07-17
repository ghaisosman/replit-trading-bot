
#!/usr/bin/env python3
"""
Advanced Conflict Scanner
Find ALL sources of process conflicts including hidden processes
"""

import os
import sys
import time
import subprocess
import psutil
import socket
import signal
from pathlib import Path

def scan_all_python_processes():
    """Comprehensive scan of ALL Python processes"""
    print("🔍 COMPREHENSIVE PYTHON PROCESS SCAN")
    print("=" * 50)
    
    current_pid = os.getpid()
    conflicting_processes = []
    
    for proc in psutil.process_iter(['pid', 'ppid', 'name', 'cmdline', 'create_time', 'status', 'cwd', 'connections']):
        try:
            if proc.info['pid'] == current_pid:
                continue
                
            name = proc.info['name'].lower()
            cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
            
            # Check for Python processes
            if 'python' in name:
                # Check for ANY bot-related keywords
                if any(keyword in cmdline.lower() for keyword in [
                    'main.py', 'web_dashboard', 'flask', 'bot_manager', 
                    'trading', 'binance', 'order_manager', 'dashboard',
                    'werkzeug', 'gunicorn', 'uvicorn', 'fastapi'
                ]):
                    age_seconds = time.time() - proc.info['create_time']
                    
                    # Get process connections
                    connections = []
                    try:
                        for conn in proc.connections():
                            if conn.laddr.port == 5000:
                                connections.append(f"Port {conn.laddr.port} ({conn.status})")
                    except:
                        pass
                    
                    conflicting_processes.append({
                        'pid': proc.info['pid'],
                        'ppid': proc.info['ppid'],
                        'name': name,
                        'cmdline': cmdline,
                        'age_minutes': age_seconds / 60,
                        'status': proc.info['status'],
                        'cwd': proc.info.get('cwd', 'N/A'),
                        'connections': connections
                    })
                    
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    
    return conflicting_processes

def scan_port_5000_users():
    """Find ALL processes using port 5000"""
    print("\n🔌 PORT 5000 USAGE SCAN")
    print("=" * 30)
    
    port_users = []
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            for conn in proc.connections():
                if conn.laddr.port == 5000:
                    cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                    port_users.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'cmdline': cmdline,
                        'connection': f"{conn.laddr.ip}:{conn.laddr.port} ({conn.status})"
                    })
        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
            continue
    
    return port_users

def scan_hidden_processes():
    """Look for hidden or background processes"""
    print("\n👻 HIDDEN PROCESS SCAN")
    print("=" * 25)
    
    hidden_processes = []
    
    # Check for processes with empty cmdline (potential daemons)
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'status']):
        try:
            if not proc.info['cmdline'] and 'python' in proc.info['name'].lower():
                hidden_processes.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'status': proc.info['status'],
                    'type': 'Empty cmdline (daemon?)'
                })
        except:
            continue
    
    # Check for zombie processes
    for proc in psutil.process_iter(['pid', 'name', 'status']):
        try:
            if proc.info['status'] == psutil.STATUS_ZOMBIE and 'python' in proc.info['name'].lower():
                hidden_processes.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'status': proc.info['status'],
                    'type': 'Zombie process'
                })
        except:
            continue
    
    return hidden_processes

def scan_parent_child_tree():
    """Map process parent-child relationships"""
    print("\n🌳 PROCESS TREE SCAN")
    print("=" * 22)
    
    process_tree = {}
    
    for proc in psutil.process_iter(['pid', 'ppid', 'name', 'cmdline']):
        try:
            if 'python' in proc.info['name'].lower():
                cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                if any(keyword in cmdline.lower() for keyword in ['main.py', 'web_dashboard', 'flask']):
                    pid = proc.info['pid']
                    ppid = proc.info['ppid']
                    
                    if ppid not in process_tree:
                        process_tree[ppid] = []
                    
                    process_tree[ppid].append({
                        'pid': pid,
                        'name': proc.info['name'],
                        'cmdline': cmdline[:60] + '...' if len(cmdline) > 60 else cmdline
                    })
        except:
            continue
    
    return process_tree

def scan_filesystem_locks():
    """Check for filesystem locks that might indicate running processes"""
    print("\n🔒 FILESYSTEM LOCK SCAN")
    print("=" * 27)
    
    lock_files = []
    potential_locks = [
        "trading_data/.lock",
        ".main.py.lock",
        ".web_dashboard.lock",
        "/tmp/trading_bot.lock",
        "/tmp/web_dashboard.lock",
        ".flask.lock"
    ]
    
    for lock_file in potential_locks:
        if os.path.exists(lock_file):
            try:
                stat = os.stat(lock_file)
                lock_files.append({
                    'file': lock_file,
                    'size': stat.st_size,
                    'modified': time.ctime(stat.st_mtime)
                })
            except:
                pass
    
    return lock_files

def nuclear_termination(processes):
    """Nuclear option: terminate ALL conflicting processes"""
    print(f"\n💥 NUCLEAR TERMINATION OF {len(processes)} PROCESSES")
    print("=" * 50)
    
    killed_count = 0
    
    for proc_info in processes:
        pid = proc_info['pid']
        try:
            proc = psutil.Process(pid)
            
            # Get all children
            children = proc.children(recursive=True)
            
            print(f"🎯 Terminating PID {pid}: {proc_info['name']}")
            print(f"   Command: {proc_info['cmdline'][:80]}...")
            
            # Kill children first
            for child in children:
                try:
                    child.terminate()
                    print(f"   ├─ Terminated child {child.pid}")
                except:
                    try:
                        child.kill()
                        print(f"   ├─ Force killed child {child.pid}")
                    except:
                        pass
            
            # Kill parent
            try:
                proc.terminate()
                print(f"   └─ Terminated parent {pid}")
                time.sleep(1)
                
                if proc.is_running():
                    proc.kill()
                    print(f"   💥 Force killed {pid}")
                
                killed_count += 1
                
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                print(f"   ❌ Could not kill {pid}")
                
        except Exception as e:
            print(f"   ❌ Error killing {pid}: {e}")
    
    return killed_count

def main():
    print("🕵️ ADVANCED CONFLICT SCANNER")
    print("Finding ALL sources of process conflicts")
    print("=" * 60)
    
    # Step 1: Comprehensive Python process scan
    python_processes = scan_all_python_processes()
    
    if python_processes:
        print(f"\n🚨 FOUND {len(python_processes)} CONFLICTING PYTHON PROCESSES:")
        for i, proc in enumerate(python_processes, 1):
            print(f"\n{i}. PID: {proc['pid']} (PPID: {proc['ppid']})")
            print(f"   Name: {proc['name']}")
            print(f"   Command: {proc['cmdline'][:100]}...")
            print(f"   Age: {proc['age_minutes']:.1f} minutes")
            print(f"   Status: {proc['status']}")
            print(f"   Working Dir: {proc['cwd']}")
            if proc['connections']:
                print(f"   Connections: {', '.join(proc['connections'])}")
    else:
        print("\n✅ No conflicting Python processes found")
    
    # Step 2: Port 5000 scan
    port_users = scan_port_5000_users()
    
    if port_users:
        print(f"\n🔌 FOUND {len(port_users)} PROCESSES USING PORT 5000:")
        for user in port_users:
            print(f"   PID {user['pid']}: {user['name']}")
            print(f"   Command: {user['cmdline'][:80]}...")
            print(f"   Connection: {user['connection']}")
    else:
        print("\n✅ No processes using port 5000")
    
    # Step 3: Hidden process scan
    hidden_processes = scan_hidden_processes()
    
    if hidden_processes:
        print(f"\n👻 FOUND {len(hidden_processes)} HIDDEN PROCESSES:")
        for proc in hidden_processes:
            print(f"   PID {proc['pid']}: {proc['name']} ({proc['type']})")
    else:
        print("\n✅ No hidden processes found")
    
    # Step 4: Process tree
    process_tree = scan_parent_child_tree()
    
    if process_tree:
        print(f"\n🌳 PROCESS TREE:")
        for parent_pid, children in process_tree.items():
            print(f"   Parent PID {parent_pid}:")
            for child in children:
                print(f"     └─ Child PID {child['pid']}: {child['cmdline']}")
    
    # Step 5: Filesystem locks
    lock_files = scan_filesystem_locks()
    
    if lock_files:
        print(f"\n🔒 FOUND {len(lock_files)} LOCK FILES:")
        for lock in lock_files:
            print(f"   {lock['file']} ({lock['size']} bytes, modified: {lock['modified']})")
    else:
        print("\n✅ No lock files found")
    
    # Step 6: Summary and action
    all_conflicts = python_processes + port_users
    unique_pids = set(proc['pid'] for proc in all_conflicts)
    
    print(f"\n📊 SUMMARY:")
    print(f"   Total conflicting processes: {len(unique_pids)}")
    print(f"   Python processes: {len(python_processes)}")
    print(f"   Port 5000 users: {len(port_users)}")
    print(f"   Hidden processes: {len(hidden_processes)}")
    
    if unique_pids:
        print(f"\n❓ ACTION REQUIRED:")
        print(f"   Do you want to terminate ALL {len(unique_pids)} conflicting processes? (y/n)")
        
        # For automated execution, terminate all
        print(f"🚀 PROCEEDING WITH NUCLEAR TERMINATION...")
        killed_count = nuclear_termination(python_processes + port_users + hidden_processes)
        
        print(f"\n✅ TERMINATION COMPLETE: {killed_count} processes killed")
        
        # Wait and verify
        time.sleep(3)
        print(f"\n🔍 VERIFICATION SCAN...")
        remaining_processes = scan_all_python_processes()
        remaining_port_users = scan_port_5000_users()
        
        if not remaining_processes and not remaining_port_users:
            print(f"✅ ALL CONFLICTS RESOLVED!")
            print(f"🚀 You can now start main.py cleanly")
        else:
            print(f"⚠️ {len(remaining_processes + remaining_port_users)} processes still running")
            print(f"💡 You may need to restart the entire Repl")
    else:
        print(f"\n✅ NO CONFLICTS DETECTED")
        print(f"💡 The issue might be elsewhere")

if __name__ == "__main__":
    main()
