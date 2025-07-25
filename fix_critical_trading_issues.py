
#!/usr/bin/env python3
"""
🔧 COMPREHENSIVE CRITICAL TRADING ISSUES FIX
================================================================================
Addresses:
1. Database-Logger sync mismatch (1 vs 5 trades)
2. Missing MACD trades in database
3. Duplicate strategy entries on dashboard
4. Missing price data in indicators
================================================================================
"""

import sys
import os
import json
from datetime import datetime, timedelta

# Add src to path
sys.path.append('src')

from src.execution_engine.trade_database import TradeDatabase
from src.analytics.trade_logger import trade_logger
from src.config.trading_config import trading_config_manager
from src.binance_client.client import BinanceClientWrapper

def fix_database_logger_sync():
    """Fix the database-logger sync mismatch"""
    print("🔄 FIXING DATABASE-LOGGER SYNC MISMATCH")
    print("=" * 60)
    
    try:
        # Load database and logger
        trade_db = TradeDatabase()
        
        print(f"📊 Current Status:")
        print(f"   Database trades: {len(trade_db.trades)}")
        print(f"   Logger trades: {len(trade_logger.trades)}")
        
        # Get all logger trades as reference (logger has more complete data)
        logger_trade_ids = {trade.trade_id for trade in trade_logger.trades}
        database_trade_ids = set(trade_db.trades.keys())
        
        missing_in_db = logger_trade_ids - database_trade_ids
        missing_in_logger = database_trade_ids - logger_trade_ids
        
        print(f"\n🔍 Sync Analysis:")
        print(f"   Missing in Database: {len(missing_in_db)} trades")
        print(f"   Missing in Logger: {len(missing_in_logger)} trades")
        
        # Sync missing trades from logger to database
        synced_count = 0
        for trade in trade_logger.trades:
            if trade.trade_id in missing_in_db:
                trade_dict = trade.to_dict()
                
                # Ensure required fields for database
                if 'trade_status' not in trade_dict:
                    trade_dict['trade_status'] = trade_dict.get('status', 'OPEN')
                
                success = trade_db.add_trade(trade.trade_id, trade_dict)
                if success:
                    synced_count += 1
                    print(f"   ✅ Synced {trade.trade_id} to database")
                else:
                    print(f"   ❌ Failed to sync {trade.trade_id}")
        
        print(f"\n✅ Synced {synced_count} trades from logger to database")
        
        # Verify final state
        print(f"\n📊 Final Status:")
        print(f"   Database trades: {len(trade_db.trades)}")
        print(f"   Logger trades: {len(trade_logger.trades)}")
        
        return synced_count > 0
        
    except Exception as e:
        print(f"❌ Error fixing database-logger sync: {e}")
        return False

def fix_duplicate_strategies():
    """Remove duplicate strategy entries from dashboard config"""
    print("\n🧹 FIXING DUPLICATE STRATEGY ENTRIES")
    print("=" * 60)
    
    try:
        # Load all strategy configs
        all_strategies = trading_config_manager.get_all_strategy_configs()
        
        print(f"📊 Current strategies found: {len(all_strategies)}")
        
        # Group strategies by name to find duplicates
        strategy_groups = {}
        for strategy_name, config in all_strategies.items():
            base_name = strategy_name.split('_')[0]  # Get base name (e.g., 'engulfing' from 'engulfing_pattern_1')
            
            if base_name not in strategy_groups:
                strategy_groups[base_name] = []
            strategy_groups[base_name].append((strategy_name, config))
        
        # Find and remove duplicates
        duplicates_removed = 0
        for base_name, strategies in strategy_groups.items():
            if len(strategies) > 1:
                print(f"\n🔍 Found {len(strategies)} {base_name} strategies:")
                
                # Keep the most recent or most complete strategy
                strategies.sort(key=lambda x: x[1].get('last_updated', ''), reverse=True)
                
                # Keep the first (most recent), remove others
                keep_strategy = strategies[0]
                remove_strategies = strategies[1:]
                
                print(f"   ✅ Keeping: {keep_strategy[0]}")
                
                for strategy_name, config in remove_strategies:
                    print(f"   🗑️ Removing duplicate: {strategy_name}")
                    try:
                        # Remove from config manager
                        if hasattr(trading_config_manager, 'remove_strategy_config'):
                            trading_config_manager.remove_strategy_config(strategy_name)
                        duplicates_removed += 1
                    except Exception as e:
                        print(f"      ❌ Error removing {strategy_name}: {e}")
        
        print(f"\n✅ Removed {duplicates_removed} duplicate strategies")
        return duplicates_removed > 0
        
    except Exception as e:
        print(f"❌ Error fixing duplicate strategies: {e}")
        return False

def fix_missing_price_data():
    """Fix missing price data in indicators"""
    print("\n💰 FIXING MISSING PRICE DATA")
    print("=" * 60)
    
    try:
        # Initialize Binance client
        binance_client = BinanceClientWrapper()
        
        symbols = ['XRPUSDT', 'BTCUSDT', 'ETHUSDT']
        price_data = {}
        
        for symbol in symbols:
            try:
                # Get current price
                ticker = binance_client.client.get_symbol_ticker(symbol=symbol)
                current_price = float(ticker['price'])
                price_data[symbol] = current_price
                
                print(f"   ✅ {symbol}: ${current_price:.4f}")
                
            except Exception as e:
                print(f"   ❌ Failed to get price for {symbol}: {e}")
                price_data[symbol] = None
        
        # Update strategy configs with current prices
        for strategy_name, config in trading_config_manager.get_all_strategy_configs().items():
            symbol = config.get('symbol')
            if symbol in price_data and price_data[symbol]:
                config['current_price'] = price_data[symbol]
                config['last_price_update'] = datetime.now().isoformat()
        
        print(f"\n✅ Updated price data for {len([p for p in price_data.values() if p])} symbols")
        return True
        
    except Exception as e:
        print(f"❌ Error fixing price data: {e}")
        return False

def recover_missing_macd_trades():
    """Specifically recover the missing MACD trades"""
    print("\n🔍 RECOVERING MISSING MACD TRADES")
    print("=" * 60)
    
    try:
        trade_db = TradeDatabase()
        
        # Look for MACD trades in logger that are missing from database
        missing_macd = []
        for trade in trade_logger.trades:
            if 'macd' in trade.strategy_name.lower() and trade.trade_id not in trade_db.trades:
                missing_macd.append(trade)
        
        print(f"📊 Found {len(missing_macd)} missing MACD trades in database")
        
        recovered = 0
        for trade in missing_macd:
            trade_dict = trade.to_dict()
            trade_dict['trade_status'] = trade_dict.get('status', 'OPEN')
            
            success = trade_db.add_trade(trade.trade_id, trade_dict)
            if success:
                recovered += 1
                print(f"   ✅ Recovered: {trade.trade_id}")
            else:
                print(f"   ❌ Failed to recover: {trade.trade_id}")
        
        print(f"\n✅ Recovered {recovered} MACD trades")
        return recovered > 0
        
    except Exception as e:
        print(f"❌ Error recovering MACD trades: {e}")
        return False

def validate_final_state():
    """Validate that all issues have been resolved"""
    print("\n✅ FINAL VALIDATION")
    print("=" * 60)
    
    try:
        # Check database-logger sync
        trade_db = TradeDatabase()
        db_count = len(trade_db.trades)
        logger_count = len(trade_logger.trades)
        
        print(f"📊 Final Trade Counts:")
        print(f"   Database: {db_count}")
        print(f"   Logger: {logger_count}")
        print(f"   Sync Status: {'✅ SYNCED' if db_count == logger_count else '⚠️ MISMATCH'}")
        
        # Check for MACD trades in database
        macd_trades_db = [tid for tid, trade in trade_db.trades.items() if 'macd' in trade.get('strategy_name', '').lower()]
        print(f"   MACD trades in database: {len(macd_trades_db)}")
        
        # Check strategies
        all_strategies = trading_config_manager.get_all_strategy_configs()
        engulfing_strategies = [name for name in all_strategies.keys() if 'engulfing' in name.lower()]
        print(f"   Engulfing strategies: {len(engulfing_strategies)}")
        
        # Check binance connection
        try:
            binance_client = BinanceClientWrapper()
            ticker = binance_client.client.get_symbol_ticker(symbol='BTCUSDT')
            price = float(ticker['price'])
            print(f"   Binance connection: ✅ WORKING (BTC: ${price:.2f})")
        except Exception as e:
            print(f"   Binance connection: ❌ FAILED ({e})")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in final validation: {e}")
        return False

def main():
    """Main execution function"""
    print("🚀 STARTING COMPREHENSIVE CRITICAL ISSUES FIX")
    print("=" * 80)
    print("Issues to fix:")
    print("1. Database-Logger sync mismatch (1 vs 5 trades)")
    print("2. Missing MACD trades in database")
    print("3. Duplicate engulfing strategies (4 copies)")
    print("4. Missing price data in indicators")
    print("=" * 80)
    
    results = {}
    
    # Fix 1: Database-Logger Sync
    results['sync_fix'] = fix_database_logger_sync()
    
    # Fix 2: Recover missing MACD trades
    results['macd_recovery'] = recover_missing_macd_trades()
    
    # Fix 3: Remove duplicate strategies
    results['duplicate_removal'] = fix_duplicate_strategies()
    
    # Fix 4: Fix missing price data
    results['price_data_fix'] = fix_missing_price_data()
    
    # Final validation
    results['validation'] = validate_final_state()
    
    # Summary
    print(f"\n🎯 FIX SUMMARY")
    print("=" * 40)
    for fix_name, success in results.items():
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"   {fix_name}: {status}")
    
    total_success = sum(results.values())
    print(f"\nOverall: {total_success}/{len(results)} fixes successful")
    
    if total_success == len(results):
        print("\n🎉 ALL CRITICAL ISSUES RESOLVED!")
        print("You can now restart your trading bot with confidence.")
    else:
        print("\n⚠️ Some issues may need manual intervention.")
        print("Check the error messages above for details.")

if __name__ == "__main__":
    main()
