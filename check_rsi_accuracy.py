
import sys
import os
sys.path.append('src')

from binance_client.client import BinanceClientWrapper
from config.global_config import global_config
from data_fetcher.price_fetcher import PriceFetcher
import asyncio
import pandas as pd

def calculate_rsi_pandas(df, period=14):
    """Calculate RSI using pandas for comparison"""
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_rsi_manual(prices, period=14):
    """Manual RSI calculation (same as web dashboard)"""
    if len(prices) < period + 1:
        return None

    # Calculate price changes
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    
    # Separate gains and losses
    gains = [max(delta, 0) for delta in deltas]
    losses = [max(-delta, 0) for delta in deltas]

    # Calculate initial averages
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    # Calculate smoothed averages for remaining periods
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

async def check_rsi_accuracy():
    """Check RSI calculation accuracy for active symbols"""
    try:
        print("🔍 RSI ACCURACY CHECK")
        print("=" * 50)
        
        # Initialize clients
        binance_client = BinanceClientWrapper()
        price_fetcher = PriceFetcher(binance_client)
        
        # Test symbols from active strategies
        test_symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
        
        for symbol in test_symbols:
            print(f"\n📊 Testing RSI accuracy for {symbol}")
            print("-" * 30)
            
            # Get market data
            df = await price_fetcher.get_market_data(symbol, '15m', 100)
            
            if df is None or df.empty:
                print(f"❌ No data available for {symbol}")
                continue
                
            # Calculate RSI using different methods
            rsi_pandas = calculate_rsi_pandas(df, 14).iloc[-1]
            rsi_manual = calculate_rsi_manual(df['close'].tolist(), 14)
            
            # Get current price for context
            current_price = df['close'].iloc[-1]
            
            print(f"💰 Current Price: ${current_price:.4f}")
            print(f"📈 RSI (Pandas): {rsi_pandas:.2f}")
            print(f"🔧 RSI (Manual): {rsi_manual:.2f}")
            print(f"📏 Difference: {abs(rsi_pandas - rsi_manual):.4f}")
            
            # Check if difference is significant
            if abs(rsi_pandas - rsi_manual) > 0.1:
                print(f"⚠️  SIGNIFICANT DIFFERENCE DETECTED!")
            else:
                print(f"✅ RSI calculations match closely")
                
            # Print recent price movements for context
            print(f"📊 Recent prices (last 5):")
            recent_prices = df['close'].tail(5).tolist()
            for i, price in enumerate(recent_prices, 1):
                print(f"   {i}: ${price:.4f}")
                
    except Exception as e:
        print(f"❌ Error during RSI accuracy check: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_rsi_accuracy())
