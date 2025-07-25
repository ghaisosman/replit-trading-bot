
#!/usr/bin/env python3
"""
Environment Database Information
===============================

Shows which database files are being used in different environments.
"""

import os
import json
from datetime import datetime

def show_environment_database_info():
    """Show database configuration for current environment"""
    print("📊 ENVIRONMENT DATABASE CONFIGURATION")
    print("=" * 50)
    
    # Detect current environment
    is_render = os.environ.get('RENDER') == 'true'
    is_replit_deployment = os.environ.get('REPLIT_DEPLOYMENT') == '1'
    
    if is_render:
        env_name = "RENDER DEPLOYMENT"
        db_file = "trading_data/trade_database_render.json"
        log_file = "trading_data/trade_log_render.json"
    elif is_replit_deployment:
        env_name = "REPLIT DEPLOYMENT"
        db_file = "trading_data/trade_database_replit.json"
        log_file = "trading_data/trade_log_replit.json"
    else:
        env_name = "DEVELOPMENT"
        db_file = "trading_data/trade_database_dev.json"
        log_file = "trading_data/trade_log_dev.json"
    
    print(f"🌍 Current Environment: {env_name}")
    print(f"📂 Database File: {db_file}")
    print(f"📝 Log File: {log_file}")
    print()
    
    # Check if files exist and show stats
    print("📈 FILE STATUS:")
    
    # Database file
    if os.path.exists(db_file):
        try:
            with open(db_file, 'r') as f:
                data = json.load(f)
                trades = data.get('trades', {}) if isinstance(data, dict) else {}
                print(f"✅ Database: {len(trades)} trades")
        except:
            print(f"⚠️ Database: File exists but unreadable")
    else:
        print(f"❌ Database: File not found (will be created on first use)")
    
    # Log file
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r') as f:
                data = json.load(f)
                trades = data.get('trades', []) if isinstance(data, dict) else []
                print(f"✅ Log File: {len(trades)} trade records")
        except:
            print(f"⚠️ Log File: File exists but unreadable")
    else:
        print(f"❌ Log File: File not found (will be created on first use)")
    
    print()
    print("🔒 ISOLATION BENEFITS:")
    print("✅ Development trades stay in development")
    print("✅ Render deployment has its own persistent database")
    print("✅ No data wiping during code updates")
    print("✅ Complete environment separation")
    
    return {
        'environment': env_name,
        'database_file': db_file,
        'log_file': log_file,
        'timestamp': datetime.now().isoformat()
    }

if __name__ == "__main__":
    info = show_environment_database_info()
    print(f"\n💾 Environment info generated at {info['timestamp']}")
