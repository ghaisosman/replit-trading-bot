
#!/usr/bin/env python3
"""
Generate Sample ML Training Data for Testing
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.analytics.trade_logger import trade_logger
from datetime import datetime, timedelta
import random

def generate_sample_trades():
    """Generate sample closed trades for ML training"""
    print("🎲 GENERATING SAMPLE ML TRAINING DATA")
    print("=" * 40)
    
    strategies = ['rsi_oversold', 'macd_divergence']
    symbols = ['SOLUSDT', 'ETHUSDT', 'BTCUSDT']
    
    sample_trades = []
    
    for i in range(8):  # Generate 8 sample trades
        strategy = random.choice(strategies)
        symbol = random.choice(symbols)
        side = 'BUY'  # Mostly long positions
        
        # Random trade parameters
        entry_price = random.uniform(20, 200)
        quantity = random.uniform(0.1, 5.0)
        leverage = random.choice([3, 5, 10])
        
        # Generate realistic indicators
        rsi = random.uniform(15, 85)
        is_profitable = random.choice([True, False, True])  # 67% profitable
        
        # Calculate PnL based on profitability
        if is_profitable:
            pnl_pct = random.uniform(0.5, 8.0)  # 0.5% to 8% profit
        else:
            pnl_pct = random.uniform(-5.0, -0.5)  # -5% to -0.5% loss
        
        position_value = entry_price * quantity
        pnl_usdt = (pnl_pct / 100) * position_value
        exit_price = entry_price * (1 + pnl_pct / 100)
        
        # Random market conditions
        market_trends = ['BULLISH', 'BEARISH', 'SIDEWAYS']
        market_phases = ['LONDON', 'NEW_YORK', 'ASIAN']
        
        trade_id = f"{strategy}_{symbol}_{datetime.now().strftime('%Y%m%d')}_{i:03d}_SAMPLE"
        
        trade_data = {
            'trade_id': trade_id,
            'strategy_name': strategy,
            'symbol': symbol,
            'side': side,
            'quantity': round(quantity, 3),
            'entry_price': round(entry_price, 2),
            'exit_price': round(exit_price, 2),
            'trade_status': 'CLOSED',
            'leverage': leverage,
            'position_size_usdt': round(position_value, 2),
            
            # Technical indicators
            'rsi_at_entry': round(rsi, 1),
            'macd_at_entry': random.uniform(-2, 2),
            'sma_20_at_entry': entry_price * random.uniform(0.98, 1.02),
            'sma_50_at_entry': entry_price * random.uniform(0.95, 1.05),
            'volume_at_entry': random.uniform(1000, 50000),
            
            # Market conditions
            'market_trend': random.choice(market_trends),
            'market_phase': random.choice(market_phases),
            'volatility_score': random.uniform(0.1, 0.8),
            
            # Performance data
            'pnl_usdt': round(pnl_usdt, 2),
            'pnl_percentage': round(pnl_pct, 2),
            'was_profitable': is_profitable,
            'duration_minutes': random.randint(30, 480),  # 30 min to 8 hours
            'exit_reason': 'Take Profit' if is_profitable else 'Stop Loss',
            
            # Timestamps
            'entry_time': (datetime.now() - timedelta(days=random.randint(1, 30))).isoformat(),
            'exit_time': datetime.now().isoformat()
        }
        
        sample_trades.append(trade_data)
    
    # Add sample trades to logger
    for trade_data in sample_trades:
        trade_logger.log_trade(trade_data)
        print(f"📊 Generated: {trade_data['trade_id']} | {trade_data['symbol']} | "
              f"{'✅ PROFIT' if trade_data['was_profitable'] else '❌ LOSS'} "
              f"({trade_data['pnl_percentage']:+.1f}%)")
    
    print(f"\n✅ Generated {len(sample_trades)} sample trades for ML training")
    print("🎯 You can now run ML training with realistic data!")

if __name__ == "__main__":
    generate_sample_trades()
