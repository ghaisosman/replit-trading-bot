
#!/usr/bin/env python3
"""
Quick Backup Script
Creates an immediate backup of the current working system
"""

from system_backup_manager import SystemBackupManager
from datetime import datetime

def main():
    print("🔄 QUICK SYSTEM BACKUP")
    print("Creating backup of current working system...")
    
    backup_manager = SystemBackupManager()
    
    # Create backup with current timestamp
    backup_name = f"github_commit_point_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    try:
        name, manifest = backup_manager.create_backup(backup_name)
        
        # Create emergency restore script
        script_file = backup_manager.create_emergency_restore_script(name)
        
        print(f"\n✅ BACKUP COMPLETED SUCCESSFULLY")
        print(f"📁 Backup name: {name}")
        print(f"📊 Files backed up: {manifest['total_files']}")
        print(f"📄 Emergency restore script: {script_file}")
        
        print(f"\n🚀 SYSTEM IS NOW SAFE TO MODIFY")
        print(f"💡 If changes cause issues, run:")
        print(f"   python {script_file}")
        print(f"💡 Or manually restore:")
        print(f"   python system_backup_manager.py")
        
        return True
        
    except Exception as e:
        print(f"❌ BACKUP FAILED: {e}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
