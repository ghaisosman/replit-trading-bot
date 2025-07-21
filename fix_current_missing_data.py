
#!/usr/bin/env python3
"""
Fix Current Missing Data Issues
Address the immediate problems with missing technical indicators and sync issues
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.analytics.trade_logger import trade_logger
from src.binance_client.client import BinanceClientWrapper
from datetime import datetime
import json

def fix_missing_technical_indicators():
    """Fix missing technical indicators for existing trades"""
    print("🔧 FIXING MISSING TECHNICAL INDICATORS")
    print("=" * 50)
    
    trade_db = TradeDatabase()
    binance_client = BinanceClientWrapper()
    fixed_count = 0
    
    # Focus on SOL trades first
    for trade_id, trade_data in trade_db.trades.items():
        symbol = trade_data.get('symbol', '')
        if 'SOL' in symbol.upper():
            missing_indicators = []
            
            # Check for missing technical indicators
            if not trade_data.get('rsi_at_entry'):
                missing_indicators.append('rsi_at_entry')
            if not trade_data.get('macd_at_entry'):
                missing_indicators.append('macd_at_entry')
            if not trade_data.get('sma_20_at_entry'):
                missing_indicators.append('sma_20_at_entry')
            if not trade_data.get('sma_50_at_entry'):
                missing_indicators.append('sma_50_at_entry')
            
            if missing_indicators:
                print(f"\n🔧 Fixing {trade_id}")
                print(f"   Missing: {', '.join(missing_indicators)}")
                
                # Calculate indicators using current market data
                indicators = calculate_indicators_for_symbol(binance_client, symbol)
                
                if indicators:
                    updates = {}
                    for indicator in missing_indicators:
                        if indicator in ['rsi_at_entry'] and 'rsi' in indicators:
                            updates['rsi_at_entry'] = indicators['rsi']
                        elif indicator in ['macd_at_entry'] and 'macd' in indicators:
                            updates['macd_at_entry'] = indicators['macd']
                        elif indicator in ['sma_20_at_entry'] and 'sma_20' in indicators:
                            updates['sma_20_at_entry'] = indicators['sma_20']
                        elif indicator in ['sma_50_at_entry'] and 'sma_50' in indicators:
                            updates['sma_50_at_entry'] = indicators['sma_50']
                    
                    if updates:
                        trade_db.update_trade(trade_id, updates)
                        fixed_count += 1
                        print(f"   ✅ Added indicators: {list(updates.keys())}")
    
    print(f"\n✅ Fixed {fixed_count} trades with missing indicators")

def fix_logger_database_sync():
    """Fix sync issues between logger and database"""
    print("\n🔄 FIXING LOGGER-DATABASE SYNC ISSUES")
    print("=" * 40)
    
    trade_db = TradeDatabase()
    logger_trades_dict = {t.trade_id: t for t in trade_logger.trades}
    
    # Find trades in logger but not in database
    missing_in_db = []
    for trade_id, logger_trade in logger_trades_dict.items():
        if trade_id not in trade_db.trades:
            missing_in_db.append((trade_id, logger_trade))
    
    print(f"Found {len(missing_in_db)} trades in logger but not in database")
    
    for trade_id, logger_trade in missing_in_db:
        print(f"\n📝 Adding missing trade to database: {trade_id}")
        
        # Convert logger trade to database format
        trade_data = logger_trade.to_dict()
        
        # Ensure required fields
        trade_data.update({
            'trade_status': logger_trade.trade_status,
            'sync_status': 'RECOVERED_FROM_LOGGER',
            'created_at': datetime.now().isoformat(),
            'last_verified': datetime.now().isoformat()
        })
        
        success = trade_db.add_trade(trade_id, trade_data)
        if success:
            print(f"   ✅ Successfully added {trade_id}")
        else:
            print(f"   ❌ Failed to add {trade_id}")

def calculate_indicators_for_symbol(binance_client, symbol):
    """Calculate technical indicators for a symbol"""
    try:
        # Get recent klines
        klines = binance_client.client.futures_klines(
            symbol=symbol,
            interval='1h',
            limit=100
        )
        
        if not klines or len(klines) < 50:
            print(f"   ⚠️ Insufficient data for {symbol}")
            return {}
        
        closes = [float(kline[4]) for kline in klines]
        volumes = [float(kline[5]) for kline in klines]
        
        indicators = {}
        
        # Calculate RSI
        if len(closes) >= 14:
            indicators['rsi'] = calculate_rsi(closes)
        
        # Calculate MACD
        if len(closes) >= 26:
            indicators['macd'] = calculate_simple_macd(closes)
        
        # Calculate SMAs
        if len(closes) >= 20:
            indicators['sma_20'] = sum(closes[-20:]) / 20
        if len(closes) >= 50:
            indicators['sma_50'] = sum(closes[-50:]) / 50
        
        # Volume
        if volumes:
            indicators['volume'] = sum(volumes[-20:]) / min(20, len(volumes))
        
        return indicators
        
    except Exception as e:
        print(f"   ❌ Error calculating indicators for {symbol}: {e}")
        return {}

def calculate_rsi(prices, period=14):
    """Calculate RSI"""
    try:
        if len(prices) < period + 1:
            return None
        
        gains, losses = [], []
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            gains.append(max(change, 0))
            losses.append(max(-change, 0))
        
        if len(gains) < period:
            return None
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return round(rsi, 2)
        
    except Exception:
        return None

def calculate_simple_macd(prices):
    """Calculate simplified MACD"""
    try:
        if len(prices) < 26:
            return None
        
        ema_12 = sum(prices[-12:]) / 12
        ema_26 = sum(prices[-26:]) / 26
        macd = ema_12 - ema_26
        return round(macd, 4)
        
    except Exception:
        return None

def fix_current_open_trade():
    """Fix current open trade missing data"""
    print("\n🔧 FIXING CURRENT OPEN TRADE DATA")
    print("=" * 35)
    
    trade_db = TradeDatabase()
    
    # Find current open trades
    open_trades = [(tid, tdata) for tid, tdata in trade_db.trades.items() 
                   if tdata.get('trade_status') == 'OPEN']
    
    print(f"Found {len(open_trades)} open trades")
    
    for trade_id, trade_data in open_trades:
        symbol = trade_data.get('symbol', '')
        missing_fields = []
        
        # Check for missing critical fields
        if not trade_data.get('margin_used'):
            missing_fields.append('margin_used')
        if not trade_data.get('leverage'):
            missing_fields.append('leverage')
        if not trade_data.get('position_value_usdt'):
            missing_fields.append('position_value_usdt')
        
        # Check for missing technical indicators
        if not trade_data.get('rsi_at_entry'):
            missing_fields.append('rsi_at_entry')
        if not trade_data.get('macd_at_entry'):
            missing_fields.append('macd_at_entry')
        
        if missing_fields:
            print(f"\n🔧 Fixing {trade_id} ({symbol})")
            print(f"   Missing: {', '.join(missing_fields)}")
            
            updates = {}
            
            # Fix basic trade data
            if 'margin_used' in missing_fields or 'leverage' in missing_fields or 'position_value_usdt' in missing_fields:
                entry_price = trade_data.get('entry_price', 0)
                quantity = trade_data.get('quantity', 0)
                position_value = entry_price * quantity
                leverage = 5  # Default leverage
                margin_used = position_value / leverage
                
                updates.update({
                    'position_value_usdt': position_value,
                    'leverage': leverage,
                    'margin_used': margin_used
                })
            
            # Fix technical indicators
            if any(field.endswith('_at_entry') for field in missing_fields):
                binance_client = BinanceClientWrapper()
                indicators = calculate_indicators_for_symbol(binance_client, symbol)
                
                if indicators:
                    if 'rsi_at_entry' in missing_fields and 'rsi' in indicators:
                        updates['rsi_at_entry'] = indicators['rsi']
                    if 'macd_at_entry' in missing_fields and 'macd' in indicators:
                        updates['macd_at_entry'] = indicators['macd']
                    if 'sma_20_at_entry' in missing_fields and 'sma_20' in indicators:
                        updates['sma_20_at_entry'] = indicators['sma_20']
                    if 'sma_50_at_entry' in missing_fields and 'sma_50' in indicators:
                        updates['sma_50_at_entry'] = indicators['sma_50']
            
            if updates:
                trade_db.update_trade(trade_id, updates)
                print(f"   ✅ Fixed: {list(updates.keys())}")

def main():
    """Main execution function"""
    print("🚀 COMPREHENSIVE DATA FIX")
    print("=" * 30)
    
    # Step 1: Fix missing technical indicators
    fix_missing_technical_indicators()
    
    # Step 2: Fix logger-database sync issues
    fix_logger_database_sync()
    
    # Step 3: Fix current open trade
    fix_current_open_trade()
    
    print("\n✅ COMPREHENSIVE FIX COMPLETE")
    print("🔍 Run check_sol_trade_records.py to verify the fixes")

if __name__ == "__main__":
    main()
