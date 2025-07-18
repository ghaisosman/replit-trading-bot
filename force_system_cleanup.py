
#!/usr/bin/env python3
"""
Force System Cleanup Script
Comprehensive cleanup to prevent restart loops and corruption
"""

import os
import sys
import time
import signal
import psutil
import logging

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

def kill_related_processes():
    """Kill all related processes"""
    logger = logging.getLogger(__name__)
    current_pid = os.getpid()
    killed_count = 0
    
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.pid == current_pid:
                    continue
                    
                cmdline = ' '.join(proc.info['cmdline'] or [])
                name = proc.info['name'] or ''
                
                # Kill processes related to the bot
                if any(keyword in cmdline.lower() for keyword in [
                    'main.py', 'web_dashboard.py', 'flask', 'trading', 'bot'
                ]) or any(keyword in name.lower() for keyword in [
                    'python', 'flask'
                ]):
                    if 'force_system_cleanup' not in cmdline:  # Don't kill ourselves
                        try:
                            proc.terminate()
                            proc.wait(timeout=3)
                            logger.info(f"Terminated process {proc.pid}: {name}")
                            killed_count += 1
                        except (psutil.TimeoutExpired, psutil.NoSuchProcess):
                            try:
                                proc.kill()
                                logger.info(f"Force killed process {proc.pid}: {name}")
                                killed_count += 1
                            except psutil.NoSuchProcess:
                                pass
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
                
    except Exception as e:
        logger.error(f"Error killing processes: {e}")
    
    logger.info(f"Killed {killed_count} related processes")
    return killed_count

def cleanup_files():
    """Clean up problematic files and directories"""
    logger = logging.getLogger(__name__)
    
    # Files and directories to remove
    cleanup_items = [
        '.git',
        '.gitignore', 
        '/tmp/web_dashboard.lock',
        '/tmp/bot_restart_lock',
        'trading_data/bot.log',
        'bot.log',
        'main.log'
    ]
    
    cleaned_count = 0
    
    for item in cleanup_items:
        try:
            if os.path.isfile(item):
                os.remove(item)
                logger.info(f"Removed file: {item}")
                cleaned_count += 1
            elif os.path.isdir(item):
                import shutil
                shutil.rmtree(item)
                logger.info(f"Removed directory: {item}")
                cleaned_count += 1
        except Exception as e:
            logger.debug(f"Could not remove {item}: {e}")
    
    logger.info(f"Cleaned {cleaned_count} items")
    return cleaned_count

def verify_cleanup():
    """Verify cleanup was successful"""
    logger = logging.getLogger(__name__)
    
    issues = []
    
    # Check for remaining git files
    if os.path.exists('.git'):
        issues.append("Git directory still exists")
    
    # Check for lock files
    if os.path.exists('/tmp/web_dashboard.lock'):
        issues.append("Web dashboard lock file still exists")
        
    if os.path.exists('/tmp/bot_restart_lock'):
        issues.append("Bot restart lock file still exists")
    
    # Check for running processes
    current_pid = os.getpid()
    running_processes = []
    
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            if proc.pid == current_pid:
                continue
                
            cmdline = ' '.join(proc.info['cmdline'] or [])
            if 'main.py' in cmdline or 'web_dashboard.py' in cmdline:
                running_processes.append(f"PID {proc.pid}: {cmdline}")
    except Exception:
        pass
    
    if running_processes:
        issues.append(f"Still running processes: {running_processes}")
    
    if issues:
        logger.warning("Cleanup verification found issues:")
        for issue in issues:
            logger.warning(f"  - {issue}")
        return False
    else:
        logger.info("✅ Cleanup verification passed - system is clean")
        return True

def main():
    """Main cleanup function"""
    logger = setup_logging()
    
    logger.info("🧹 Starting comprehensive system cleanup...")
    
    # Step 1: Kill related processes
    logger.info("Step 1: Terminating related processes...")
    killed = kill_related_processes()
    time.sleep(2)  # Allow processes to fully terminate
    
    # Step 2: Clean up files
    logger.info("Step 2: Cleaning up problematic files...")
    cleaned = cleanup_files()
    
    # Step 3: Verify cleanup
    logger.info("Step 3: Verifying cleanup...")
    success = verify_cleanup()
    
    # Summary
    logger.info("🔄 Cleanup Summary:")
    logger.info(f"  - Processes terminated: {killed}")
    logger.info(f"  - Files cleaned: {cleaned}")
    logger.info(f"  - Verification: {'PASSED' if success else 'FAILED'}")
    
    if success:
        logger.info("✅ System cleanup completed successfully")
        logger.info("💡 You can now safely restart the bot")
    else:
        logger.warning("⚠️ Some issues remain - manual intervention may be needed")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
