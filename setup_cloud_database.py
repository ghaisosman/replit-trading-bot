
#!/usr/bin/env python3
"""
Setup Cloud Database Synchronization
Configure Replit Database URL for seamless sync between development and deployment
"""

import os
import sys

def setup_cloud_database():
    """Setup cloud database configuration"""
    print("🌐 CLOUD DATABASE SETUP")
    print("=" * 30)
    
    print("\n📋 Instructions:")
    print("1. Go to your Replit project")
    print("2. Open the Database tab (left sidebar)")
    print("3. Copy the Database URL")
    print("4. Set it as REPLIT_DB_URL in your Render environment variables")
    print("5. Also add it to your Replit secrets")
    
    # Check if running on Replit
    if 'REPL_ID' in os.environ:
        print("\n🔧 REPLIT ENVIRONMENT DETECTED")
        
        # Try to get database URL from Replit
        db_url = os.getenv('REPLIT_DB_URL')
        
        if db_url:
            print(f"✅ Database URL found: {db_url[:50]}...")
            print("\n📋 Next steps:")
            print("1. Copy this URL to your Render deployment environment variables")
            print("2. Variable name: REPLIT_DB_URL")
            print("3. Your bot will automatically sync between environments")
        else:
            print("❌ REPLIT_DB_URL not found in environment")
            print("\n🔧 Setup steps:")
            print("1. Open Database tab in Replit")
            print("2. Create a new key-value pair")
            print("3. The database URL will be available as REPLIT_DB_URL")
            
    else:
        print("\n🚀 DEPLOYMENT ENVIRONMENT")
        db_url = os.getenv('REPLIT_DB_URL')
        
        if db_url:
            print("✅ Database URL configured")
            print("🔄 Bot will sync with Replit database")
        else:
            print("❌ REPLIT_DB_URL not configured")
            print("⚠️ Add REPLIT_DB_URL to your environment variables")
    
    print(f"\n📊 Environment Variables Check:")
    print(f"   REPLIT_DB_URL: {'✅ Set' if os.getenv('REPLIT_DB_URL') else '❌ Missing'}")
    print(f"   RENDER: {'✅ Deployment' if os.getenv('RENDER') else '❌ Development'}")
    
    return bool(os.getenv('REPLIT_DB_URL'))

if __name__ == "__main__":
    setup_cloud_database()
