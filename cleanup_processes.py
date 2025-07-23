
#!/usr/bin/env python3
"""Simple process cleanup utility for trading bot"""

import psutil
import logging
import time

def cleanup_bot_processes():
    """Clean up any remaining bot processes"""
    logger = logging.getLogger(__name__)
    
    current_pid = os.getpid()
    cleaned = 0
    
    print("🧹 Cleaning up bot processes...")
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.pid == current_pid:
                continue
                
            cmdline = proc.info.get('cmdline', [])
            if cmdline and any('main.py' in str(cmd) for cmd in cmdline):
                print(f"🔧 Terminating process PID {proc.pid}")
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                    cleaned += 1
                except psutil.TimeoutExpired:
                    print(f"🔫 Force killing process PID {proc.pid}")
                    proc.kill()
                    cleaned += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    print(f"✅ Cleanup complete - {cleaned} processes cleaned")
    return cleaned

if __name__ == "__main__":
    import os
    cleanup_bot_processes()
