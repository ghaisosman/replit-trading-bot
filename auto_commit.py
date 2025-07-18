
#!/usr/bin/env python3
"""
Automatic Git Commit and Push Script
Monitors for changes and automatically commits/pushes to repository
"""

import os
import subprocess
import time
import logging
from datetime import datetime

def setup_logging():
    """Setup logging for the auto-commit script"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('auto_commit.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def run_git_command(command):
    """Run a git command and return the result"""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, cwd='.')
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def check_for_changes():
    """Check if there are any uncommitted changes"""
    success, stdout, stderr = run_git_command("git status --porcelain")
    if success:
        return len(stdout.strip()) > 0
    return False

def auto_commit_and_push():
    """Automatically commit and push changes"""
    logger = setup_logging()
    
    while True:
        try:
            if check_for_changes():
                logger.info("🔍 Changes detected, preparing to commit...")
                
                # Add all changes
                success, stdout, stderr = run_git_command("git add .")
                if not success:
                    logger.error(f"Failed to add changes: {stderr}")
                    time.sleep(60)
                    continue
                
                # Create commit message with timestamp
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                commit_message = f"Auto-commit: {timestamp}\n\nAutomatically committed changes to trading bot"
                
                # Commit changes
                success, stdout, stderr = run_git_command(f'git commit -m "{commit_message}"')
                if not success:
                    logger.error(f"Failed to commit: {stderr}")
                    time.sleep(60)
                    continue
                
                logger.info("✅ Changes committed successfully")
                
                # Push to remote
                success, stdout, stderr = run_git_command("git push origin main")
                if success:
                    logger.info("🚀 Changes pushed to GitHub successfully")
                else:
                    logger.error(f"Failed to push: {stderr}")
                    logger.info("Will retry on next cycle...")
            
            else:
                logger.info("📊 No changes detected, checking again in 5 minutes...")
            
            # Wait 5 minutes before checking again
            time.sleep(300)
            
        except KeyboardInterrupt:
            logger.info("🛑 Auto-commit stopped by user")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    print("⚠️  Auto-commit functionality is PERMANENTLY DISABLED")
    print("📝 Use manual git commands only")
    print("🚫 Auto-commit can cause conflicts and restart loops")
    
    # Kill this process immediately to prevent any file watching
    import os
    import sys
    print("🛑 Terminating auto-commit process to prevent restart loops")
    sys.exit(0)
