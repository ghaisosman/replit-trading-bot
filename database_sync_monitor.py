#!/usr/bin/env python3
"""
Database Sync Health Monitor
Continuously monitors database sync and orphan detection health
"""

import sys
import os
import time
import json
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.execution_engine.trade_database import TradeDatabase
from src.execution_engine.reliable_orphan_detector import ReliableOrphanDetector
from src.binance_client.client import BinanceClientWrapper
from src.reporting.telegram_reporter import TelegramReporter

def monitor_sync_health():
    """Monitor sync health continuously"""
    try:
        print("🔍 Database Sync Health Monitor Started")
        
        # Initialize components
        binance_client = BinanceClientWrapper()
        telegram_reporter = TelegramReporter()
        trade_db = TradeDatabase()
        orphan_detector = ReliableOrphanDetector(binance_client, trade_db, telegram_reporter)
        
        iteration = 0
        while True:
            iteration += 1
            print(f"\n🔄 Health Check #{iteration} - {datetime.now().strftime('%H:%M:%S')}")
            
            # Check database health
            trades_count = len(trade_db.get_all_trades())
            print(f"📊 Database: {trades_count} trades")
            
            # Check orphan detector health
            status = orphan_detector.get_status()
            failures = status.get('consecutive_failures', 0)
            next_check = status.get('next_verification_in', 0)
            print(f"👻 Orphan Detector: {failures} failures, next check in {next_check:.0f}s")
            
            # Run verification if needed
            if orphan_detector.should_run_verification():
                print("🔍 Running orphan verification...")
                result = orphan_detector.run_verification_cycle()
                print(f"✅ Verification: {result.get('status', 'unknown')}")
            
            # Wait before next check
            time.sleep(60)  # Check every minute
            
    except KeyboardInterrupt:
        print("\n⏹️ Monitor stopped by user")
    except Exception as e:
        print(f"❌ Monitor error: {e}")

if __name__ == "__main__":
    monitor_sync_health()
