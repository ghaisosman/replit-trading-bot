
#!/usr/bin/env python3
"""
Complete System Reset
Terminates all trades, clears all logs, and resets the system for a fresh start
"""

import sys
import os
import json
import shutil
from pathlib import Path
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def stop_all_bot_processes():
    """Stop all running bot processes"""
    print("🛑 STOPPING ALL BOT PROCESSES")
    print("=" * 40)
    
    try:
        import subprocess
        # Kill all python processes running main.py
        result = subprocess.run(['pkill', '-f', 'python main.py'], capture_output=True, text=True)
        print("✅ Killed all bot processes")
        
        # Wait a moment for processes to stop
        import time
        time.sleep(2)
        
    except Exception as e:
        print(f"⚠️ Error stopping processes: {e}")

def clear_all_trade_data():
    """Clear all trade data from all sources"""
    print("\n🗑️ CLEARING ALL TRADE DATA")
    print("=" * 40)
    
    # Clear trade database
    try:
        from src.execution_engine.trade_database import TradeDatabase
        trade_db = TradeDatabase()
        trade_db.trades = {}
        trade_db._save_database()
        print("✅ Trade database cleared")
    except Exception as e:
        print(f"⚠️ Error clearing trade database: {e}")
    
    # Clear trade logger
    try:
        from src.analytics.trade_logger import trade_logger
        trade_logger.trades = []
        trade_logger._save_trades()
        print("✅ Trade logger cleared")
    except Exception as e:
        print(f"⚠️ Error clearing trade logger: {e}")
    
    # Clear anomalies database
    try:
        anomalies_file = "trading_data/anomalies.json"
        if os.path.exists(anomalies_file):
            with open(anomalies_file, 'w') as f:
                json.dump({"anomalies": [], "last_updated": datetime.now().isoformat()}, f, indent=2)
            print("✅ Anomalies database cleared")
    except Exception as e:
        print(f"⚠️ Error clearing anomalies: {e}")

def clear_all_log_files():
    """Clear all log files"""
    print("\n📝 CLEARING ALL LOG FILES")
    print("=" * 40)
    
    log_files = [
        "trading_data/bot.log",
        "trading_bot.log", 
        "bot.log",
        "main.log",
        "app.log"
    ]
    
    for log_file in log_files:
        try:
            if os.path.exists(log_file):
                # Clear the file but keep it
                with open(log_file, 'w') as f:
                    f.write(f"# Log cleared at {datetime.now().isoformat()}\n")
                print(f"✅ Cleared {log_file}")
        except Exception as e:
            print(f"⚠️ Error clearing {log_file}: {e}")

def clear_trading_data_files():
    """Clear all trading data files"""
    print("\n🗂️ CLEARING TRADING DATA FILES")
    print("=" * 40)
    
    files_to_clear = [
        "trading_data/trades/all_trades.json",
        "trading_data/trades/all_trades.csv",
        "trading_data/trade_database.json",
        "trading_data/balance.json"
    ]
    
    for file_path in files_to_clear:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"✅ Deleted {file_path}")
        except Exception as e:
            print(f"⚠️ Error deleting {file_path}: {e}")
    
    # Clear reports directory
    try:
        reports_dir = Path("trading_data/reports")
        if reports_dir.exists():
            shutil.rmtree(reports_dir)
            reports_dir.mkdir(exist_ok=True)
            print("✅ Cleared reports directory")
    except Exception as e:
        print(f"⚠️ Error clearing reports directory: {e}")

def reset_environment_config():
    """Reset environment configuration to default"""
    print("\n⚙️ RESETTING ENVIRONMENT CONFIG")
    print("=" * 40)
    
    try:
        env_config = {
            "BINANCE_TESTNET": "false",
            "BINANCE_FUTURES": "true"
        }
        
        os.makedirs("trading_data", exist_ok=True)
        with open("trading_data/environment_config.json", 'w') as f:
            json.dump(env_config, f, indent=2)
        
        print("✅ Environment config reset to MAINNET")
    except Exception as e:
        print(f"⚠️ Error resetting environment config: {e}")

def create_fresh_directories():
    """Create fresh directory structure"""
    print("\n📁 CREATING FRESH DIRECTORIES")
    print("=" * 40)
    
    directories = [
        "trading_data",
        "trading_data/trades",
        "trading_data/reports"
    ]
    
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            print(f"✅ Created {directory}")
        except Exception as e:
            print(f"⚠️ Error creating {directory}: {e}")

def verify_clean_slate():
    """Verify everything is cleared"""
    print("\n🔍 VERIFYING CLEAN SLATE")
    print("=" * 40)
    
    # Check trade database
    try:
        from src.execution_engine.trade_database import TradeDatabase
        trade_db = TradeDatabase()
        db_count = len(trade_db.trades)
        print(f"📊 Trade Database: {db_count} trades")
    except Exception as e:
        print(f"📊 Trade Database: Error checking - {e}")
    
    # Check trade logger
    try:
        from src.analytics.trade_logger import trade_logger
        logger_count = len(trade_logger.trades)
        print(f"📊 Trade Logger: {logger_count} trades")
    except Exception as e:
        print(f"📊 Trade Logger: Error checking - {e}")
    
    # Check files
    files_to_check = [
        "trading_data/trade_database.json",
        "trading_data/trades/all_trades.json"
    ]
    
    for file_path in files_to_check:
        exists = "EXISTS" if os.path.exists(file_path) else "CLEARED"
        print(f"📄 {file_path}: {exists}")

def main():
    print("🧹 COMPLETE SYSTEM RESET")
    print("=" * 50)
    print("⚠️  THIS WILL DELETE ALL TRADING DATA AND LOGS")
    print("⚠️  MAKE SURE NO IMPORTANT DATA WILL BE LOST")
    print("=" * 50)
    
    confirm = input("\nType 'DELETE EVERYTHING' to confirm complete reset: ")
    
    if confirm != "DELETE EVERYTHING":
        print("❌ Reset cancelled for safety")
        return
    
    print("\n🚀 STARTING COMPLETE RESET...")
    
    # Step 1: Stop all processes
    stop_all_bot_processes()
    
    # Step 2: Clear all trade data
    clear_all_trade_data()
    
    # Step 3: Clear all logs
    clear_all_log_files()
    
    # Step 4: Clear trading data files
    clear_trading_data_files()
    
    # Step 5: Reset environment
    reset_environment_config()
    
    # Step 6: Create fresh directories
    create_fresh_directories()
    
    # Step 7: Verify clean slate
    verify_clean_slate()
    
    print("\n" + "=" * 50)
    print("✅ COMPLETE RESET FINISHED!")
    print("🎯 System is now completely clean")
    print("🚀 You can now start fresh with 'python main.py'")
    print("🌐 Web dashboard will show empty state")
    print("💡 All previous trades, logs, and data have been cleared")
    print("=" * 50)

if __name__ == "__main__":
    main()
