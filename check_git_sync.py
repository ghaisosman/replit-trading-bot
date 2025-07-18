
#!/usr/bin/env python3
"""
Git Sync Status Checker
"""

import subprocess
import sys

def run_command(cmd):
    """Run shell command and return output"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return False, "", str(e)

def check_git_sync():
    print("🔍 CHECKING GIT SYNC STATUS")
    print("=" * 40)
    
    # Check git status
    success, output, error = run_command("git status --porcelain")
    if success:
        if output:
            print(f"⚠️  Uncommitted changes found:")
            print(output)
        else:
            print("✅ Working directory clean")
    
    # Check if local is ahead of remote
    success, output, error = run_command("git rev-list --count HEAD..origin/main")
    if success and output:
        behind_count = int(output)
        if behind_count > 0:
            print(f"⚠️  Local is {behind_count} commits behind remote")
        else:
            print("✅ Local is up to date with remote")
    
    # Check if local is ahead of remote
    success, output, error = run_command("git rev-list --count origin/main..HEAD")
    if success and output:
        ahead_count = int(output)
        if ahead_count > 0:
            print(f"⚠️  Local is {ahead_count} commits ahead of remote - needs push")
        else:
            print("✅ Local matches remote")
    
    # Show last commit
    success, output, error = run_command("git log -1 --oneline")
    if success:
        print(f"📝 Last commit: {output}")
    
    print("\n💡 Run 'python check_git_sync.py' anytime to check sync status")

if __name__ == "__main__":
    check_git_sync()
