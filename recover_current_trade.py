
#!/usr/bin/env python3
"""
Recover Current Missing Trade
Find and record the SOLUSDT trade that's open on Binance but missing from database
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.binance_client.client import BinanceClientWrapper
from src.execution_engine.trade_database import TradeDatabase
from src.analytics.trade_logger import trade_logger
from datetime import datetime
import json

def recover_missing_trade():
    print("🔄 RECOVERING MISSING TRADE")
    print("=" * 50)
    
    try:
        # Check Binance positions
        binance_client = BinanceClientWrapper()
        if not binance_client.is_futures:
            print("❌ Not in futures mode")
            return
            
        account_info = binance_client.client.futures_account()
        positions = account_info.get('positions', [])
        
        # Find active positions
        active_positions = []
        for position in positions:
            symbol = position.get('symbol')
            position_amt = float(position.get('positionAmt', 0))
            if abs(position_amt) > 0.0001:
                active_positions.append({
                    'symbol': symbol,
                    'position_amt': position_amt,
                    'entry_price': float(position.get('entryPrice', 0)),
                    'side': 'BUY' if position_amt > 0 else 'SELL',
                    'quantity': abs(position_amt),
                    'pnl': float(position.get('unRealizedProfit', 0))
                })
        
        print(f"📊 Found {len(active_positions)} active positions on Binance")
        
        if not active_positions:
            print("❌ No active positions found")
            return
        
        # Check database
        trade_db = TradeDatabase()
        
        for pos in active_positions:
            print(f"\n🔍 Processing {pos['symbol']} position...")
            print(f"   Side: {pos['side']}")
            print(f"   Quantity: {pos['quantity']}")
            print(f"   Entry Price: ${pos['entry_price']:.4f}")
            
            # Check if this position exists in database
            existing_trade_id = trade_db.find_trade_by_position(
                'UNKNOWN',  # Search all strategies
                pos['symbol'],
                pos['side'],
                pos['quantity'],
                pos['entry_price'],
                tolerance=0.05
            )
            
            if existing_trade_id:
                print(f"   ✅ Found existing trade in database: {existing_trade_id}")
                continue
            
            # Position missing from database - create recovery trade
            print(f"   ❌ Position missing from database - creating recovery trade")
            
            # Determine strategy based on symbol and current market conditions
            strategy_name = determine_strategy(pos['symbol'])
            
            # Create trade ID
            recovery_trade_id = f"{strategy_name}_{pos['symbol']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_RECOVERED"
            
            # Calculate trade data
            position_value_usdt = pos['entry_price'] * pos['quantity']
            leverage = 3  # Default leverage from config
            margin_used = position_value_usdt / leverage
            
            # Create comprehensive trade data
            trade_data = {
                'trade_id': recovery_trade_id,
                'strategy_name': strategy_name,
                'symbol': pos['symbol'],
                'side': pos['side'],
                'entry_price': float(pos['entry_price']),
                'quantity': float(pos['quantity']),
                'trade_status': 'OPEN',
                'timestamp': datetime.now().isoformat(),
                'margin_used': margin_used,
                'leverage': leverage,
                'position_value_usdt': position_value_usdt,
                'recovery_source': 'MANUAL_RECOVERY_SCRIPT',
                'binance_verified': True,
                'sync_status': 'RECOVERED'
            }
            
            # Add to database
            success = trade_db.add_trade(recovery_trade_id, trade_data)
            
            if success:
                print(f"   ✅ Successfully created recovery trade: {recovery_trade_id}")
                
                # Also add to trade logger for consistency
                try:
                    from src.analytics.trade_logger import TradeEntry
                    
                    trade_entry = TradeEntry(
                        trade_id=recovery_trade_id,
                        strategy_name=strategy_name,
                        symbol=pos['symbol'],
                        side=pos['side'],
                        entry_price=pos['entry_price'],
                        quantity=pos['quantity'],
                        margin_used=margin_used,
                        leverage=leverage,
                        position_value_usdt=position_value_usdt
                    )
                    
                    trade_logger.trades.append(trade_entry)
                    trade_logger._save_trades()
                    
                    print(f"   ✅ Also added to trade logger")
                    
                except Exception as logger_error:
                    print(f"   ⚠️ Failed to add to trade logger: {logger_error}")
                    
            else:
                print(f"   ❌ Failed to create recovery trade")
        
        print(f"\n🏁 RECOVERY COMPLETE")
        
    except Exception as e:
        print(f"❌ Recovery error: {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")

def determine_strategy(symbol):
    """Determine strategy based on symbol"""
    symbol_upper = symbol.upper()
    if 'SOL' in symbol_upper:
        return 'rsi_oversold'
    elif 'ETH' in symbol_upper:
        return 'RSI_ETH'  
    elif 'BTC' in symbol_upper:
        return 'macd_divergence'
    else:
        return 'AUTO_RECOVERED'

if __name__ == "__main__":
    recover_missing_trade()
