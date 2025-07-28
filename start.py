#!/usr/bin/env python3
"""
Startup script for CursorBot
Handles dependency installation and startup
"""

import subprocess
import sys
import os

def check_dependencies():
    """Check if required dependencies are installed"""
    try:
        import flask
        import requests
        import pandas
        import numpy
        import ccxt
        import ta
        print("✅ All dependencies are already installed!")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        return False

def install_dependencies():
    """Install required dependencies only if missing"""
    try:
        print("📦 Installing missing dependencies...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False

def main():
    """Main startup function"""
    print("🚀 Starting CursorBot...")
    
    # Check if we're in a deployment environment
    is_deployment = os.environ.get('RENDER') == 'true' or os.environ.get('REPLIT_DEPLOYMENT') == '1'
    
    if is_deployment:
        print("🌐 Deployment environment detected")
        # In deployment, dependencies should be installed by the platform
        pass
    else:
        # In development, check if dependencies are installed
        if not check_dependencies():
            print("📦 Installing missing dependencies...")
            if not install_dependencies():
                print("⚠️ Continuing without dependency installation...")
        else:
            print("✅ Dependencies are ready!")
    
    # Import and run main application
    try:
        from main import main as main_func
        import asyncio
        asyncio.run(main_func())
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Please ensure all dependencies are installed:")
        print("pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Runtime error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()