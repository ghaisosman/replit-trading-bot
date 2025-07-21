
#!/usr/bin/env python3
"""
Fix Missing Database Data
Backfill missing data from trade logger to trade database
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.analytics.trade_logger import trade_logger
from datetime import datetime

def fix_missing_database_data():
    """Backfill missing data from trade logger to database"""
    print("🔧 FIXING MISSING DATABASE DATA")
    print("=" * 50)

    trade_db = TradeDatabase()
    logger_trades_dict = {t.trade_id: t for t in trade_logger.trades}

    print(f"Database trades: {len(trade_db.trades)}")
    print(f"Logger trades: {len(logger_trades_dict)}")

    # Track fixes applied
    fixes_applied = {
        'technical_indicators': 0,
        'market_conditions': 0,
        'exit_data': 0,
        'performance_metrics': 0,
        'missing_trades': 0
    }

    # 1. Fix missing trades in database
    print(f"\n1️⃣ Adding missing trades to database...")
    for trade_id, logger_trade in logger_trades_dict.items():
        if trade_id not in trade_db.trades:
            print(f"   ➕ Adding missing trade: {trade_id}")
            
            # Convert logger trade to database format
            trade_data = logger_trade.to_dict()
            
            # Add required fields for database
            trade_data.update({
                'trade_status': logger_trade.trade_status,
                'sync_status': 'RECOVERED_FROM_LOGGER',
                'created_at': datetime.now().isoformat(),
                'last_verified': datetime.now().isoformat()
            })
            
            success = trade_db.add_trade(trade_id, trade_data)
            if success:
                fixes_applied['missing_trades'] += 1

    # 2. Backfill missing technical indicators
    print(f"\n2️⃣ Backfilling technical indicators...")
    for trade_id in set(trade_db.trades.keys()) & set(logger_trades_dict.keys()):
        db_trade = trade_db.trades[trade_id]
        logger_trade = logger_trades_dict[trade_id]
        
        updates = {}
        
        # Check and add missing technical indicators
        if (logger_trade.rsi_at_entry is not None and 
            db_trade.get('rsi_at_entry') is None):
            updates['rsi_at_entry'] = logger_trade.rsi_at_entry
            
        if (logger_trade.macd_at_entry is not None and 
            db_trade.get('macd_at_entry') is None):
            updates['macd_at_entry'] = logger_trade.macd_at_entry
            
        if (logger_trade.sma_20_at_entry is not None and 
            db_trade.get('sma_20_at_entry') is None):
            updates['sma_20_at_entry'] = logger_trade.sma_20_at_entry
            
        if (logger_trade.sma_50_at_entry is not None and 
            db_trade.get('sma_50_at_entry') is None):
            updates['sma_50_at_entry'] = logger_trade.sma_50_at_entry
            
        if (logger_trade.volume_at_entry is not None and 
            db_trade.get('volume_at_entry') is None):
            updates['volume_at_entry'] = logger_trade.volume_at_entry
            
        if (logger_trade.entry_signal_strength is not None and 
            db_trade.get('entry_signal_strength') is None):
            updates['entry_signal_strength'] = logger_trade.entry_signal_strength

        if updates:
            trade_db.update_trade(trade_id, updates)
            fixes_applied['technical_indicators'] += 1
            print(f"   🔧 Updated technical indicators for {trade_id}")

    # 3. Backfill missing market conditions
    print(f"\n3️⃣ Backfilling market conditions...")
    for trade_id in set(trade_db.trades.keys()) & set(logger_trades_dict.keys()):
        db_trade = trade_db.trades[trade_id]
        logger_trade = logger_trades_dict[trade_id]
        
        updates = {}
        
        if (logger_trade.market_trend is not None and 
            db_trade.get('market_trend') is None):
            updates['market_trend'] = logger_trade.market_trend
            
        if (logger_trade.volatility_score is not None and 
            db_trade.get('volatility_score') is None):
            updates['volatility_score'] = logger_trade.volatility_score
            
        if (logger_trade.market_phase is not None and 
            db_trade.get('market_phase') is None):
            updates['market_phase'] = logger_trade.market_phase

        if updates:
            trade_db.update_trade(trade_id, updates)
            fixes_applied['market_conditions'] += 1
            print(f"   🔧 Updated market conditions for {trade_id}")

    # 4. Backfill missing exit data
    print(f"\n4️⃣ Backfilling exit data...")
    for trade_id in set(trade_db.trades.keys()) & set(logger_trades_dict.keys()):
        db_trade = trade_db.trades[trade_id]
        logger_trade = logger_trades_dict[trade_id]
        
        # Only update if logger trade is closed and has exit data
        if logger_trade.trade_status == "CLOSED":
            updates = {}
            
            if (logger_trade.exit_price is not None and 
                db_trade.get('exit_price') is None):
                updates['exit_price'] = logger_trade.exit_price
                
            if (logger_trade.exit_reason is not None and 
                db_trade.get('exit_reason') is None):
                updates['exit_reason'] = logger_trade.exit_reason
                
            if (logger_trade.pnl_usdt is not None and 
                db_trade.get('pnl_usdt') is None):
                updates['pnl_usdt'] = logger_trade.pnl_usdt
                
            if (logger_trade.pnl_percentage is not None and 
                db_trade.get('pnl_percentage') is None):
                updates['pnl_percentage'] = logger_trade.pnl_percentage
                
            if (logger_trade.duration_minutes is not None and 
                db_trade.get('duration_minutes') is None):
                updates['duration_minutes'] = logger_trade.duration_minutes
                
            # Ensure trade status is synced
            if db_trade.get('trade_status') != 'CLOSED':
                updates['trade_status'] = 'CLOSED'

            if updates:
                trade_db.update_trade(trade_id, updates)
                fixes_applied['exit_data'] += 1
                print(f"   🔧 Updated exit data for {trade_id}")

    # 5. Backfill missing performance metrics
    print(f"\n5️⃣ Backfilling performance metrics...")
    for trade_id in set(trade_db.trades.keys()) & set(logger_trades_dict.keys()):
        db_trade = trade_db.trades[trade_id]
        logger_trade = logger_trades_dict[trade_id]
        
        updates = {}
        
        if (logger_trade.risk_reward_ratio is not None and 
            db_trade.get('risk_reward_ratio') is None):
            updates['risk_reward_ratio'] = logger_trade.risk_reward_ratio
            
        if (logger_trade.max_drawdown is not None and 
            db_trade.get('max_drawdown') is None):
            updates['max_drawdown'] = logger_trade.max_drawdown

        if updates:
            trade_db.update_trade(trade_id, updates)
            fixes_applied['performance_metrics'] += 1
            print(f"   🔧 Updated performance metrics for {trade_id}")

    # Print summary
    print(f"\n✅ FIXES APPLIED SUMMARY")
    print("-" * 30)
    print(f"➕ Missing trades added: {fixes_applied['missing_trades']}")
    print(f"📊 Technical indicators fixed: {fixes_applied['technical_indicators']}")
    print(f"🌍 Market conditions fixed: {fixes_applied['market_conditions']}")
    print(f"🔚 Exit data fixed: {fixes_applied['exit_data']}")
    print(f"📈 Performance metrics fixed: {fixes_applied['performance_metrics']}")
    
    total_fixes = sum(fixes_applied.values())
    print(f"\n🎯 Total fixes applied: {total_fixes}")
    
    if total_fixes > 0:
        print(f"✅ Database data integrity improved!")
        print(f"🔄 Run check_database_data_integrity.py to verify fixes")
    else:
        print(f"ℹ️ No fixes needed - database appears to be in sync")

    return fixes_applied

if __name__ == "__main__":
    fixes = fix_missing_database_data()
    print(f"\n🚀 Database data fix completed!")
