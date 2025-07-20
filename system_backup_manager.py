
#!/usr/bin/env python3
"""
System Backup Manager for Replit
Creates complete backups of the current working system and provides restore functionality
"""

import os
import shutil
import json
import time
from datetime import datetime
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SystemBackupManager:
    """Manages complete system backups and restores"""
    
    def __init__(self):
        self.backup_root = Path("system_backups")
        self.backup_root.mkdir(exist_ok=True)
        
        # Critical files and directories to backup
        self.critical_paths = [
            "src/",
            "templates/",
            "trading_data/",
            "main.py",
            "web_dashboard.py",
            ".replit",
            "requirements.txt",
            "pyproject.toml"
        ]
        
        # Files to exclude from backup
        self.exclude_patterns = [
            "__pycache__",
            "*.pyc",
            "*.log",
            ".git",
            "system_backups",
            "node_modules"
        ]
    
    def should_exclude(self, path_str):
        """Check if path should be excluded from backup"""
        for pattern in self.exclude_patterns:
            if pattern in path_str:
                return True
        return False
    
    def create_backup(self, backup_name=None):
        """Create a complete system backup"""
        if not backup_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"pre_lock_mechanism_{timestamp}"
        
        backup_dir = self.backup_root / backup_name
        backup_dir.mkdir(exist_ok=True)
        
        logger.info(f"🔄 Creating system backup: {backup_name}")
        
        backed_up_files = 0
        backup_manifest = {
            "created_at": datetime.now().isoformat(),
            "backup_name": backup_name,
            "files": []
        }
        
        # Backup all critical paths
        for path_str in self.critical_paths:
            source_path = Path(path_str)
            
            if not source_path.exists():
                logger.warning(f"⚠️ Path not found, skipping: {path_str}")
                continue
            
            backup_target = backup_dir / path_str
            
            try:
                if source_path.is_file():
                    # Backup single file
                    backup_target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_path, backup_target)
                    backed_up_files += 1
                    backup_manifest["files"].append(str(path_str))
                    logger.info(f"✅ Backed up file: {path_str}")
                    
                elif source_path.is_dir():
                    # Backup entire directory
                    for root, dirs, files in os.walk(source_path):
                        # Filter out excluded directories
                        dirs[:] = [d for d in dirs if not self.should_exclude(d)]
                        
                        for file in files:
                            if self.should_exclude(file):
                                continue
                                
                            source_file = Path(root) / file
                            rel_path = source_file.relative_to(Path("."))
                            target_file = backup_dir / rel_path
                            
                            target_file.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(source_file, target_file)
                            backed_up_files += 1
                            backup_manifest["files"].append(str(rel_path))
                    
                    logger.info(f"✅ Backed up directory: {path_str}")
                    
            except Exception as e:
                logger.error(f"❌ Failed to backup {path_str}: {e}")
        
        # Save backup manifest
        manifest_file = backup_dir / "backup_manifest.json"
        with open(manifest_file, 'w') as f:
            json.dump(backup_manifest, f, indent=2)
        
        backup_manifest["total_files"] = backed_up_files
        
        logger.info(f"✅ Backup completed: {backup_name}")
        logger.info(f"📊 Total files backed up: {backed_up_files}")
        logger.info(f"📁 Backup location: {backup_dir}")
        
        return backup_name, backup_manifest
    
    def list_backups(self):
        """List all available backups"""
        backups = []
        
        if not self.backup_root.exists():
            return backups
        
        for backup_dir in self.backup_root.iterdir():
            if backup_dir.is_dir():
                manifest_file = backup_dir / "backup_manifest.json"
                
                if manifest_file.exists():
                    try:
                        with open(manifest_file, 'r') as f:
                            manifest = json.load(f)
                        
                        backups.append({
                            "name": backup_dir.name,
                            "created_at": manifest.get("created_at", "Unknown"),
                            "total_files": manifest.get("total_files", 0),
                            "path": str(backup_dir)
                        })
                    except Exception as e:
                        logger.warning(f"⚠️ Could not read manifest for {backup_dir.name}: {e}")
                        backups.append({
                            "name": backup_dir.name,
                            "created_at": "Unknown",
                            "total_files": 0,
                            "path": str(backup_dir)
                        })
        
        # Sort by creation time (newest first)
        backups.sort(key=lambda x: x["created_at"], reverse=True)
        return backups
    
    def restore_from_backup(self, backup_name):
        """Restore system from a specific backup"""
        backup_dir = self.backup_root / backup_name
        
        if not backup_dir.exists():
            logger.error(f"❌ Backup not found: {backup_name}")
            return False
        
        manifest_file = backup_dir / "backup_manifest.json"
        if not manifest_file.exists():
            logger.error(f"❌ Backup manifest not found: {backup_name}")
            return False
        
        logger.info(f"🔄 Restoring from backup: {backup_name}")
        
        try:
            # Read backup manifest
            with open(manifest_file, 'r') as f:
                manifest = json.load(f)
            
            restored_files = 0
            
            # Restore each file from the backup
            for file_path in manifest.get("files", []):
                backup_file = backup_dir / file_path
                target_file = Path(file_path)
                
                if backup_file.exists():
                    # Create target directory if needed
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Restore file
                    shutil.copy2(backup_file, target_file)
                    restored_files += 1
                    logger.debug(f"🔄 Restored: {file_path}")
                else:
                    logger.warning(f"⚠️ Backup file missing: {file_path}")
            
            logger.info(f"✅ System restored from backup: {backup_name}")
            logger.info(f"📊 Total files restored: {restored_files}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to restore from backup {backup_name}: {e}")
            return False
    
    def create_emergency_restore_script(self, backup_name):
        """Create an emergency restore script"""
        script_content = f'''#!/usr/bin/env python3
"""
Emergency Restore Script
Auto-generated restore script for backup: {backup_name}
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from system_backup_manager import SystemBackupManager

def main():
    print("🚨 EMERGENCY RESTORE")
    print(f"Restoring from backup: {backup_name}")
    
    backup_manager = SystemBackupManager()
    success = backup_manager.restore_from_backup("{backup_name}")
    
    if success:
        print("✅ Emergency restore completed successfully")
        print("🚀 You can now restart the system")
    else:
        print("❌ Emergency restore failed")
        print("📞 Manual intervention required")
    
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())
'''
        
        script_file = f"emergency_restore_{backup_name}.py"
        with open(script_file, 'w') as f:
            f.write(script_content)
        
        os.chmod(script_file, 0o755)  # Make executable
        
        logger.info(f"📄 Emergency restore script created: {script_file}")
        return script_file

def main():
    """Main backup management interface"""
    backup_manager = SystemBackupManager()
    
    print("🔄 SYSTEM BACKUP MANAGER")
    print("=" * 50)
    print("1. Create new backup")
    print("2. List all backups") 
    print("3. Restore from backup")
    print("4. Create emergency restore script")
    print("5. Create pre-lock-mechanism backup (recommended)")
    print("=" * 50)
    
    try:
        choice = input("Select option (1-5): ").strip()
        
        if choice == "1":
            backup_name = input("Enter backup name (or press Enter for auto-name): ").strip()
            if not backup_name:
                backup_name = None
            
            name, manifest = backup_manager.create_backup(backup_name)
            print(f"\n✅ Backup created successfully: {name}")
            
            # Offer to create emergency restore script
            create_script = input("Create emergency restore script? (y/n): ").strip().lower()
            if create_script == 'y':
                script_file = backup_manager.create_emergency_restore_script(name)
                print(f"📄 Emergency script: {script_file}")
        
        elif choice == "2":
            backups = backup_manager.list_backups()
            
            if not backups:
                print("📋 No backups found")
            else:
                print(f"\n📋 Found {len(backups)} backups:")
                print("-" * 60)
                for i, backup in enumerate(backups, 1):
                    print(f"{i}. {backup['name']}")
                    print(f"   Created: {backup['created_at']}")
                    print(f"   Files: {backup['total_files']}")
                    print(f"   Path: {backup['path']}")
                    print()
        
        elif choice == "3":
            backups = backup_manager.list_backups()
            
            if not backups:
                print("❌ No backups available for restore")
                return
            
            print("\n📋 Available backups:")
            for i, backup in enumerate(backups, 1):
                print(f"{i}. {backup['name']} ({backup['created_at']})")
            
            try:
                selection = int(input("\nSelect backup number to restore: ")) - 1
                if 0 <= selection < len(backups):
                    backup_name = backups[selection]["name"]
                    
                    confirm = input(f"⚠️ Restore from '{backup_name}'? This will overwrite current files (y/n): ")
                    if confirm.lower() == 'y':
                        success = backup_manager.restore_from_backup(backup_name)
                        if success:
                            print("✅ Restore completed successfully")
                        else:
                            print("❌ Restore failed")
                    else:
                        print("❌ Restore cancelled")
                else:
                    print("❌ Invalid selection")
            except ValueError:
                print("❌ Invalid input")
        
        elif choice == "4":
            backups = backup_manager.list_backups()
            
            if not backups:
                print("❌ No backups available")
                return
            
            print("\n📋 Available backups:")
            for i, backup in enumerate(backups, 1):
                print(f"{i}. {backup['name']}")
            
            try:
                selection = int(input("\nSelect backup for emergency script: ")) - 1
                if 0 <= selection < len(backups):
                    backup_name = backups[selection]["name"]
                    script_file = backup_manager.create_emergency_restore_script(backup_name)
                    print(f"📄 Emergency script created: {script_file}")
                else:
                    print("❌ Invalid selection")
            except ValueError:
                print("❌ Invalid input")
        
        elif choice == "5":
            print("🎯 Creating pre-lock-mechanism backup...")
            name, manifest = backup_manager.create_backup("pre_lock_mechanism_safe_point")
            script_file = backup_manager.create_emergency_restore_script(name)
            
            print(f"\n✅ Safe point backup created: {name}")
            print(f"📄 Emergency restore script: {script_file}")
            print("\n🚀 You can now safely test the lock mechanism!")
            print("💡 If anything goes wrong, run the emergency script to restore")
        
        else:
            print("❌ Invalid option")
    
    except KeyboardInterrupt:
        print("\n❌ Operation cancelled")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
