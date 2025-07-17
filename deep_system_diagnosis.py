
#!/usr/bin/env python3
"""
Deep System Diagnosis & Fix Tool
Identify and fix persistent configuration and position sync issues
"""

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

def print_section(title):
    print(f"\n{'='*60}")
    print(f"🔍 {title}")
    print('='*60)

def check_file_exists(file_path, description):
    exists = os.path.exists(file_path)
    status = "✅ EXISTS" if exists else "❌ MISSING"
    print(f"{status}: {description} ({file_path})")
    return exists

def show_file_content(file_path, description, max_lines=20):
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            print(f"\n📄 {description}:")
            print("-" * 40)
            lines = content.split('\n')
            for i, line in enumerate(lines[:max_lines], 1):
                print(f"{i:2}: {line}")
            if len(lines) > max_lines:
                print(f"... ({len(lines) - max_lines} more lines)")
            print("-" * 40)
            return content
        except Exception as e:
            print(f"❌ Error reading {file_path}: {e}")
            return None
    else:
        print(f"❌ File not found: {file_path}")
        return None

def force_kill_all_python():
    """Kill ALL Python processes to ensure clean state"""
    try:
        # Kill by process name
        subprocess.run(['pkill', '-f', 'python'], check=False)
        subprocess.run(['pkill', '-f', 'main.py'], check=False)
        subprocess.run(['pkill', '-f', 'web_dashboard'], check=False)
        
        # Additional kill methods
        subprocess.run(['killall', 'python'], check=False)
        subprocess.run(['killall', 'python3'], check=False)
        
        print("✅ All Python processes terminated")
        return True
    except Exception as e:
        print(f"⚠️ Process termination warning: {e}")
        return False

def nuclear_clean_data():
    """Nuclear option: Remove ALL trading data and config"""
    directories_to_clear = [
        'trading_data',
        '__pycache__',
        'src/__pycache__',
        '.pytest_cache'
    ]
    
    files_to_remove = [
        'trading_data/environment_config.json',
        'trading_data/trade_database.json',
        'trading_data/trades/all_trades.json',
        'trading_data/bot.log',
        'trading_bot.log',
        'bot.log',
        'main.log'
    ]
    
    print_section("NUCLEAR DATA CLEANUP")
    
    # Remove directories
    for directory in directories_to_clear:
        if os.path.exists(directory):
            try:
                shutil.rmtree(directory)
                print(f"🗑️ REMOVED: {directory}/")
            except Exception as e:
                print(f"❌ Failed to remove {directory}: {e}")
    
    # Remove individual files
    for file_path in files_to_remove:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"🗑️ REMOVED: {file_path}")
            except Exception as e:
                print(f"❌ Failed to remove {file_path}: {e}")
    
    # Recreate essential directories
    os.makedirs('trading_data/trades', exist_ok=True)
    os.makedirs('trading_data/reports', exist_ok=True)
    
    print("✅ Nuclear cleanup completed")

def create_clean_mainnet_config():
    """Create a fresh mainnet configuration"""
    config = {
        "BINANCE_TESTNET": "false",
        "BINANCE_FUTURES": "true",
        "last_updated": datetime.now().isoformat(),
        "forced_mainnet": True,
        "diagnostic_reset": True
    }
    
    config_path = "trading_data/environment_config.json"
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"✅ Created fresh MAINNET config: {config_path}")
    return config

def check_position_sources():
    """Check all possible sources of position data"""
    print_section("POSITION DATA SOURCES CHECK")
    
    sources = [
        ('trading_data/trade_database.json', 'Trade Database'),
        ('trading_data/trades/all_trades.json', 'Trade Logger'),
        ('trading_data/anomalies.json', 'Anomaly Tracker'),
    ]
    
    for file_path, description in sources:
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                
                if isinstance(data, dict):
                    if 'trades' in data:
                        trades = data['trades']
                        print(f"📊 {description}: {len(trades)} trades found")
                        
                        # Show open trades
                        open_trades = []
                        for trade_id, trade_data in trades.items():
                            if trade_data.get('trade_status') == 'OPEN':
                                open_trades.append((trade_id, trade_data))
                        
                        if open_trades:
                            print(f"🚨 FOUND {len(open_trades)} OPEN TRADES:")
                            for trade_id, trade_data in open_trades:
                                strategy = trade_data.get('strategy_name', 'Unknown')
                                symbol = trade_data.get('symbol', 'Unknown')
                                side = trade_data.get('side', 'Unknown')
                                print(f"   - {trade_id}: {strategy} | {symbol} | {side}")
                        else:
                            print(f"✅ {description}: No open trades")
                    else:
                        print(f"📊 {description}: {len(data)} items")
                else:
                    print(f"📊 {description}: {type(data).__name__} data")
            except Exception as e:
                print(f"❌ Error reading {description}: {e}")
        else:
            print(f"✅ {description}: File not found (clean)")

def check_environment_sources():
    """Check all sources that could affect environment detection"""
    print_section("ENVIRONMENT CONFIGURATION SOURCES")
    
    # Check environment config file
    env_file = "trading_data/environment_config.json"
    env_content = show_file_content(env_file, "Environment Config File")
    
    # Check if environment variables exist
    print(f"\n🔧 ENVIRONMENT VARIABLES:")
    env_vars = ['BINANCE_TESTNET', 'BINANCE_FUTURES', 'REPLIT_DEPLOYMENT']
    for var in env_vars:
        value = os.getenv(var, 'NOT SET')
        print(f"   {var}: {value}")
    
    # Check for deployment detection
    is_deployment = os.environ.get('REPLIT_DEPLOYMENT') == '1'
    print(f"\n🚀 DEPLOYMENT MODE: {'YES' if is_deployment else 'NO'}")
    
    return env_content

def main():
    print("🔍 DEEP SYSTEM DIAGNOSIS & REPAIR TOOL")
    print("=====================================")
    print("This tool will diagnose and fix persistent configuration issues")
    
    # Step 1: Check current state
    print_section("CURRENT STATE ANALYSIS")
    check_file_exists("main.py", "Main Application")
    check_file_exists("web_dashboard.py", "Web Dashboard")
    check_file_exists("src/config/global_config.py", "Global Config Module")
    
    # Step 2: Check processes
    print_section("PROCESS CHECK")
    try:
        result = subprocess.run(['pgrep', '-f', 'python'], capture_output=True, text=True)
        if result.stdout.strip():
            print("🚨 PYTHON PROCESSES STILL RUNNING:")
            for line in result.stdout.strip().split('\n'):
                if line:
                    print(f"   PID: {line}")
        else:
            print("✅ No Python processes running")
    except:
        print("⚠️ Could not check processes")
    
    # Step 3: Analyze position data
    check_position_sources()
    
    # Step 4: Analyze environment config
    env_content = check_environment_sources()
    
    # Step 5: Offer repair options
    print_section("REPAIR OPTIONS")
    print("1. 🧹 Nuclear cleanup (remove ALL data and configs)")
    print("2. 🔧 Force mainnet config only")
    print("3. 💥 Kill all processes + nuclear cleanup + fresh config")
    print("4. 📊 Analysis only (no changes)")
    
    choice = input("\nSelect repair option (1-4): ").strip()
    
    if choice == "1":
        print("\n🚨 PERFORMING NUCLEAR CLEANUP...")
        nuclear_clean_data()
        create_clean_mainnet_config()
        print("\n✅ Nuclear cleanup completed!")
        
    elif choice == "2":
        print("\n🔧 FORCING MAINNET CONFIG...")
        create_clean_mainnet_config()
        print("\n✅ Mainnet config created!")
        
    elif choice == "3":
        print("\n💥 FULL SYSTEM RESET...")
        force_kill_all_python()
        nuclear_clean_data()
        create_clean_mainnet_config()
        print("\n✅ Full system reset completed!")
        print("🚀 You can now run 'python main.py' for a completely clean start")
        
    elif choice == "4":
        print("\n📊 Analysis completed - no changes made")
        
    else:
        print("❌ Invalid option selected")
    
    print(f"\n🏁 Diagnosis completed at {datetime.now()}")
    print("💡 If issues persist, run option 3 for the most thorough reset")

if __name__ == "__main__":
    main()
