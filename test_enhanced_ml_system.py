
#!/usr/bin/env python3
"""
Test Enhanced ML System with Real-Time Data Collection
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.analytics.ml_analyzer import ml_analyzer
from src.analytics.trade_logger import trade_logger

def main():
    print("🚀 TESTING ENHANCED ML SYSTEM")
    print("=" * 50)
    
    # Check current data status
    print(f"📊 Total trades: {len(trade_logger.trades)}")
    closed_trades = [t for t in trade_logger.trades if t.trade_status == "CLOSED"]
    print(f"✅ Closed trades: {len(closed_trades)}")
    
    # Check if we have technical indicators
    has_indicators = any(t.rsi_at_entry is not None for t in closed_trades)
    print(f"🔧 Technical indicators available: {has_indicators}")
    
    # Check if we have market conditions
    has_market_data = any(t.market_trend is not None for t in closed_trades)
    print(f"🌍 Market conditions available: {has_market_data}")
    
    if len(closed_trades) >= 3:
        print("\n🤖 TRAINING ML MODELS...")
        results = ml_analyzer.train_models()
        
        if "error" not in results:
            print("✅ ML training successful!")
            print(f"📊 Dataset size: {results.get('dataset_size', 0)}")
            print(f"🎯 Features count: {results.get('features_count', 0)}")
            
            if 'profitability_accuracy' in results:
                accuracy = results['profitability_accuracy']
                print(f"🎯 Profitability prediction accuracy: {accuracy:.1%}")
            
            # Test prediction system
            print("\n🔮 TESTING PREDICTION SYSTEM...")
            sample_trade = {
                'strategy': 'rsi_oversold',
                'symbol': 'SOLUSDT',
                'side': 'BUY',
                'leverage': 5,
                'position_size_usdt': 100,
                'rsi_entry': 25,
                'macd_entry': -0.5,
                'hour_of_day': 14,
                'day_of_week': 2,
                'market_trend': 'BULLISH',
                'volatility_score': 0.3,
                'signal_strength': 0.8
            }
            
            prediction = ml_analyzer.predict_trade_outcome(sample_trade)
            
            if "error" not in prediction:
                print(f"✅ Prediction working!")
                print(f"🎯 Recommendation: {prediction.get('recommendation', 'UNKNOWN')}")
                print(f"📈 Profit probability: {prediction.get('profit_probability', 0):.1%}")
                if 'predicted_pnl_percentage' in prediction:
                    print(f"💰 Expected PnL: {prediction['predicted_pnl_percentage']:+.2f}%")
            else:
                print(f"❌ Prediction failed: {prediction['error']}")
            
            # Generate insights
            print("\n📊 GENERATING INSIGHTS...")
            insights = ml_analyzer.generate_insights()
            
            if "error" not in insights:
                print("✅ Insights generated successfully!")
                
                # Show strategy performance
                if 'strategy_performance' in insights:
                    print("\n🏆 STRATEGY PERFORMANCE:")
                    for strategy, stats in insights['strategy_performance'].items():
                        print(f"   📊 {strategy}:")
                        print(f"      Win Rate: {stats['win_rate']:.1f}%")
                        print(f"      Avg PnL: {stats['avg_pnl']:+.2f}%")
                        print(f"      Total Trades: {stats['total_trades']}")
                
                # Show best trading times
                if 'best_trading_times' in insights:
                    print("\n⏰ BEST TRADING TIMES:")
                    for time_data in insights['best_trading_times']:
                        hour = time_data['hour']
                        profitability = time_data['profitability']
                        print(f"   🕐 {hour:02d}:00-{(hour+1)%24:02d}:00: {profitability:.1f}% profitable")
                
                print("\n🎯 ML SYSTEM STATUS: FULLY OPERATIONAL!")
                print("✅ Ready to provide intelligent trading suggestions")
                
            else:
                print(f"❌ Insights failed: {insights['error']}")
                
        else:
            print(f"❌ ML training failed: {results['error']}")
    else:
        print(f"\n⚠️ Need at least 3 closed trades for ML training (have {len(closed_trades)})")
        print("💡 Make some trades and close them to test the ML system")
    
    print("\n💡 NEXT STEPS:")
    print("1. 🔧 Technical indicators are now captured automatically")
    print("2. 🌍 Market conditions are tracked in real-time")
    print("3. 🤖 ML models will train automatically with more trades")
    print("4. 📊 Use insights to optimize strategy parameters")

if __name__ == "__main__":
    main()
