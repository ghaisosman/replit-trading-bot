
#!/usr/bin/env python3
"""
Test ML Training with Current Limited Data
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.analytics.ml_analyzer import ml_analyzer
from src.analytics.trade_logger import trade_logger

def main():
    print("🧪 TESTING ML WITH CURRENT DATA")
    print("=" * 40)
    
    # Check current data
    print(f"📊 Current trades in logger: {len(trade_logger.trades)}")
    
    # Try to prepare dataset
    dataset = ml_analyzer.prepare_ml_dataset()
    
    if dataset is not None:
        print(f"✅ Dataset prepared: {len(dataset)} rows, {len(dataset.columns)} columns")
        print(f"📊 Available features: {list(dataset.columns[:10])}")
        
        # Check for closed trades
        if 'was_profitable' in dataset.columns:
            closed_count = len(dataset)
            profitable_count = dataset['was_profitable'].sum()
            print(f"💰 Closed trades: {closed_count}, Profitable: {profitable_count}")
        
        # Try basic training with minimal data
        if len(dataset) >= 2:  # Even with 2 trades
            print("\n🤖 ATTEMPTING BASIC ML TRAINING...")
            results = ml_analyzer.train_models()
            
            if "error" not in results:
                print("✅ Basic ML training successful!")
                if 'profitability_accuracy' in results:
                    print(f"📈 Accuracy: {results['profitability_accuracy']:.2%}")
                    
                # Test prediction
                print("\n🔮 TESTING PREDICTION...")
                sample_trade = {
                    'strategy': 'rsi_oversold',
                    'symbol': 'SOLUSDT',
                    'side': 'BUY',
                    'leverage': 5,
                    'position_size_usdt': 100,
                    'rsi_entry': 25,
                    'hour_of_day': 14,
                    'day_of_week': 2,
                    'market_trend': 'BULLISH'
                }
                
                prediction = ml_analyzer.predict_trade_outcome(sample_trade)
                if "error" not in prediction:
                    print(f"✅ Prediction working: {prediction.get('recommendation', 'UNKNOWN')}")
                else:
                    print(f"❌ Prediction failed: {prediction['error']}")
            else:
                print(f"❌ Training failed: {results['error']}")
        else:
            print("⚠️ Need at least 2 closed trades for basic training")
    else:
        print("❌ Could not prepare dataset")
    
    print("\n💡 RECOMMENDATIONS:")
    print("1. 📈 Make some trades and close them to generate training data")
    print("2. 🔧 Enhanced technical indicators are now captured automatically")
    print("3. 🎯 ML system will improve as more trades are completed")
    print("4. 📊 Market conditions and volatility are now tracked")

if __name__ == "__main__":
    main()
