
#!/usr/bin/env python3
"""
Database Data Integrity Checker
Check what important data is missing in trade database compared to trade logger
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.analytics.trade_logger import trade_logger
from datetime import datetime
import json

def check_database_data_integrity():
    """Check what data is missing in database vs logger"""
    print("🔍 DATABASE DATA INTEGRITY CHECK")
    print("=" * 50)

    # Load both systems
    trade_db = TradeDatabase()

    print(f"\n📊 SYSTEM OVERVIEW")
    print("-" * 30)
    print(f"Database trades: {len(trade_db.trades)}")
    print(f"Logger trades: {len(trade_logger.trades)}")

    # Check data completeness for each trade
    missing_data_summary = {
        'technical_indicators': 0,
        'market_conditions': 0,
        'exit_data': 0,
        'performance_metrics': 0,
        'complete_trades': 0
    }

    # Expected fields that should be present
    expected_fields = {
        'technical_indicators': ['rsi_at_entry', 'macd_at_entry', 'sma_20_at_entry', 'sma_50_at_entry', 'volume_at_entry', 'entry_signal_strength'],
        'market_conditions': ['market_trend', 'volatility_score', 'market_phase'],
        'exit_data': ['exit_price', 'exit_reason', 'pnl_usdt', 'pnl_percentage', 'duration_minutes'],
        'performance_metrics': ['risk_reward_ratio', 'max_drawdown'],
        'required_fields': ['strategy_name', 'symbol', 'side', 'quantity', 'entry_price', 'leverage', 'margin_used', 'position_value_usdt']
    }

    print(f"\n🔍 DETAILED DATA ANALYSIS")
    print("-" * 30)

    trades_with_issues = []

    for trade_id, db_trade in trade_db.trades.items():
        issues = []
        
        # Check technical indicators
        tech_missing = []
        for field in expected_fields['technical_indicators']:
            if field not in db_trade or db_trade[field] is None:
                tech_missing.append(field)
        
        if tech_missing:
            missing_data_summary['technical_indicators'] += 1
            issues.append(f"Missing tech indicators: {tech_missing}")

        # Check market conditions
        market_missing = []
        for field in expected_fields['market_conditions']:
            if field not in db_trade or db_trade[field] is None:
                market_missing.append(field)
        
        if market_missing:
            missing_data_summary['market_conditions'] += 1
            issues.append(f"Missing market conditions: {market_missing}")

        # Check exit data (for closed trades)
        if db_trade.get('trade_status') == 'CLOSED':
            exit_missing = []
            for field in expected_fields['exit_data']:
                if field not in db_trade or db_trade[field] is None:
                    exit_missing.append(field)
            
            if exit_missing:
                missing_data_summary['exit_data'] += 1
                issues.append(f"Missing exit data: {exit_missing}")

        # Check performance metrics (for closed trades)
        if db_trade.get('trade_status') == 'CLOSED':
            perf_missing = []
            for field in expected_fields['performance_metrics']:
                if field not in db_trade or db_trade[field] is None:
                    perf_missing.append(field)
            
            if perf_missing:
                missing_data_summary['performance_metrics'] += 1
                issues.append(f"Missing performance metrics: {perf_missing}")

        # Record trades with issues
        if issues:
            trades_with_issues.append({
                'trade_id': trade_id,
                'strategy': db_trade.get('strategy_name', 'Unknown'),
                'symbol': db_trade.get('symbol', 'Unknown'),
                'status': db_trade.get('trade_status', 'Unknown'),
                'issues': issues
            })
        else:
            missing_data_summary['complete_trades'] += 1

    # Print summary
    print(f"\n📋 DATA COMPLETENESS SUMMARY")
    print("-" * 35)
    print(f"✅ Complete trades: {missing_data_summary['complete_trades']}")
    print(f"❌ Missing technical indicators: {missing_data_summary['technical_indicators']}")
    print(f"❌ Missing market conditions: {missing_data_summary['market_conditions']}")
    print(f"❌ Missing exit data: {missing_data_summary['exit_data']}")
    print(f"❌ Missing performance metrics: {missing_data_summary['performance_metrics']}")

    # Show detailed issues for first 10 problematic trades
    if trades_with_issues:
        print(f"\n🔍 DETAILED ISSUES (First 10)")
        print("-" * 35)
        for i, trade_info in enumerate(trades_with_issues[:10]):
            print(f"\n{i+1}. Trade: {trade_info['trade_id']}")
            print(f"   Strategy: {trade_info['strategy']}")
            print(f"   Symbol: {trade_info['symbol']}")
            print(f"   Status: {trade_info['status']}")
            for issue in trade_info['issues']:
                print(f"   ❌ {issue}")

    # Compare with trade logger data
    print(f"\n🔄 LOGGER vs DATABASE COMPARISON")
    print("-" * 35)

    logger_trades_dict = {t.trade_id: t for t in trade_logger.trades}
    
    # Find trades that exist in logger but have richer data
    richer_data_in_logger = 0
    
    for trade_id in set(trade_db.trades.keys()) & set(logger_trades_dict.keys()):
        db_trade = trade_db.trades[trade_id]
        logger_trade = logger_trades_dict[trade_id]
        
        # Check if logger has data that database is missing
        logger_has_more = False
        
        if (logger_trade.rsi_at_entry is not None and 
            db_trade.get('rsi_at_entry') is None):
            logger_has_more = True
            
        if (logger_trade.exit_price is not None and 
            db_trade.get('exit_price') is None):
            logger_has_more = True
            
        if logger_has_more:
            richer_data_in_logger += 1

    print(f"📊 Trades with richer data in logger: {richer_data_in_logger}")
    
    # Calculate data completeness percentage
    total_trades = len(trade_db.trades)
    if total_trades > 0:
        completeness_percentage = (missing_data_summary['complete_trades'] / total_trades) * 100
        print(f"📈 Overall data completeness: {completeness_percentage:.1f}%")
    
    return {
        'total_trades': total_trades,
        'missing_data_summary': missing_data_summary,
        'trades_with_issues': len(trades_with_issues),
        'richer_data_in_logger': richer_data_in_logger
    }

if __name__ == "__main__":
    results = check_database_data_integrity()
    print(f"\n✅ Data integrity check completed!")
    print(f"📊 {results['trades_with_issues']} trades have missing data")
    print(f"🔄 {results['richer_data_in_logger']} trades have richer data in logger")
