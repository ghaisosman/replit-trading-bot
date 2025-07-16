
#!/usr/bin/env python3
"""
Force Clear Position Utility
Manually clear specific positions that are stuck in the system
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.order_manager import OrderManager
from src.execution_engine.trade_database import TradeDatabase
from src.binance_client.client import BinanceClientWrapper
from src.analytics.trade_logger import trade_logger
from src.config.global_config import GlobalConfig
from datetime import datetime


def check_position_status():
    """Check current position status across all systems"""
    print("🔍 POSITION STATUS CHECK")
    print("=" * 40)
    
    # Initialize components
    config = GlobalConfig()
    binance_client = BinanceClientWrapper(config)
    order_manager = OrderManager(binance_client, None)
    trade_db = TradeDatabase()
    
    # Check order manager
    active_positions = order_manager.get_active_positions()
    print(f"📊 Order Manager Active Positions: {len(active_positions)}")
    
    for strategy_name, position in active_positions.items():
        print(f"  {strategy_name}: {position.symbol} | {position.side} | Qty: {position.quantity}")
    
    # Check trade database
    open_trades = []
    for trade_id, trade_data in trade_db.trades.items():
        if trade_data.get('trade_status') == 'OPEN':
            open_trades.append((trade_id, trade_data))
    
    print(f"\n📊 Trade Database Open Trades: {len(open_trades)}")
    for trade_id, trade_data in open_trades:
        print(f"  {trade_id}: {trade_data.get('symbol')} | {trade_data.get('side')} | {trade_data.get('strategy_name')}")
    
    # Check trade logger
    open_logger_trades = [t for t in trade_logger.trades if t.trade_status == "OPEN"]
    print(f"\n📊 Trade Logger Open Trades: {len(open_logger_trades)}")
    for trade in open_logger_trades:
        print(f"  {trade.trade_id}: {trade.symbol} | {trade.side} | {trade.strategy_name}")
    
    # Check Binance positions
    try:
        if binance_client.is_futures:
            account_info = binance_client.client.futures_account()
            positions = account_info.get('positions', [])
            active_binance_positions = [pos for pos in positions if abs(float(pos.get('positionAmt', 0))) > 0.000001]
            
            print(f"\n📊 Binance Active Positions: {len(active_binance_positions)}")
            for pos in active_binance_positions:
                print(f"  {pos.get('symbol')}: {pos.get('positionAmt')} | Entry: ${pos.get('entryPrice')}")
    except Exception as e:
        print(f"Error checking Binance positions: {e}")
    
    return active_positions, open_trades, open_logger_trades


def force_clear_position():
    """Force clear a specific position"""
    active_positions, open_trades, open_logger_trades = check_position_status()
    
    if not active_positions:
        print("No active positions to clear")
        return
    
    print("\nActive positions in Order Manager:")
    position_list = list(active_positions.items())
    for i, (strategy_name, position) in enumerate(position_list, 1):
        print(f"{i}. {strategy_name} | {position.symbol} | {position.side} | Qty: {position.quantity}")
    
    try:
        choice = int(input("\nEnter position number to force clear (0 to cancel): "))
        if choice == 0:
            return
        
        if 1 <= choice <= len(position_list):
            strategy_name, position = position_list[choice - 1]
            
            confirm = input(f"Force clear {strategy_name} position on {position.symbol}? (y/N): ")
            if confirm.lower() == 'y':
                # Initialize order manager
                config = GlobalConfig()
                binance_client = BinanceClientWrapper(config)
                order_manager = OrderManager(binance_client, None)
                
                # Clear from order manager
                order_manager.clear_orphan_position(strategy_name)
                
                # Update trade database
                trade_db = TradeDatabase()
                for trade_id, trade_data in trade_db.trades.items():
                    if (trade_data.get('trade_status') == 'OPEN' and 
                        trade_data.get('strategy_name') == strategy_name and
                        trade_data.get('symbol') == position.symbol):
                        
                        trade_db.update_trade(trade_id, {
                            'trade_status': 'CLOSED',
                            'exit_reason': 'Force Clear - Manual Intervention',
                            'exit_price': trade_data.get('entry_price', 0),
                            'pnl_usdt': 0.0,
                            'pnl_percentage': 0.0,
                            'duration_minutes': 0
                        })
                        print(f"✅ Updated trade database: {trade_id}")
                
                # Update trade logger
                for trade in trade_logger.trades:
                    if (trade.trade_status == "OPEN" and 
                        trade.strategy_name == strategy_name and
                        trade.symbol == position.symbol):
                        
                        trade.trade_status = "CLOSED"
                        trade.exit_reason = "Force Clear - Manual Intervention"
                        trade.exit_price = trade.entry_price
                        trade.pnl_usdt = 0.0
                        trade.pnl_percentage = 0.0
                        print(f"✅ Updated trade logger: {trade.trade_id}")
                
                # Save trade logger
                trade_logger.save_trades()
                
                print(f"✅ Force cleared position: {strategy_name} | {position.symbol}")
                print("🔄 Please restart the bot for changes to take effect")
            else:
                print("❌ Cancelled")
        else:
            print("Invalid choice")
            
    except ValueError:
        print("Invalid input")


def main():
    print("🔧 FORCE CLEAR POSITION UTILITY")
    print("=" * 35)
    
    while True:
        print("\nOptions:")
        print("1. Check position status")
        print("2. Force clear position")
        print("3. Exit")
        
        choice = input("\nSelect option (1-3): ")
        
        if choice == "1":
            check_position_status()
        elif choice == "2":
            force_clear_position()
        elif choice == "3":
            break
        else:
            print("Invalid option")


if __name__ == "__main__":
    main()
