
#!/usr/bin/env python3
"""
Comprehensive ML System Status Check
Analyze all aspects of the ML trading system
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.analytics.ml_analyzer import ml_analyzer
from src.analytics.trade_logger import trade_logger
from datetime import datetime
import json

def check_data_collection():
    """Check if trade data is being collected properly"""
    print("🔍 CHECKING ML DATA COLLECTION")
    print("=" * 50)
    
    # Check trade logger
    total_trades = len(trade_logger.trades)
    print(f"📊 Total trades in logger: {total_trades}")
    
    if total_trades > 0:
        # Check data completeness
        recent_trade = trade_logger.trades[-1]
        print(f"📈 Most recent trade: {recent_trade.trade_id}")
        print(f"🔧 Technical indicators captured: {bool(recent_trade.rsi_at_entry)}")
        print(f"🌍 Market conditions captured: {bool(recent_trade.market_trend)}")
        print(f"💰 Performance data: {recent_trade.trade_status}")
        
        # Check closed trades for ML
        closed_trades = [t for t in trade_logger.trades if t.trade_status == "CLOSED"]
        print(f"✅ Closed trades available for ML: {len(closed_trades)}")
        
        return len(closed_trades) >= 5  # Need at least 5 closed trades
    
    return False

def check_ml_models():
    """Check ML model training and capabilities"""
    print("\n🤖 CHECKING ML MODELS & TRAINING")
    print("=" * 50)
    
    # Prepare dataset
    dataset = ml_analyzer.prepare_ml_dataset()
    
    if dataset is None:
        print("❌ No ML dataset available")
        return False
    
    print(f"📊 ML dataset size: {len(dataset)} trades")
    print(f"🔢 Features available: {len(dataset.columns)}")
    print(f"🎯 Key features: {list(dataset.columns[:10])}")
    
    # Check profitability distribution
    if 'was_profitable' in dataset.columns:
        profitable = dataset['was_profitable'].sum()
        total = len(dataset)
        win_rate = profitable / total if total > 0 else 0
        print(f"💰 Historical win rate: {win_rate:.2%} ({profitable}/{total})")
    
    # Train models
    print("\n🧠 Training ML models...")
    results = ml_analyzer.train_models()
    
    if "error" not in results:
        print("✅ ML models trained successfully!")
        
        if 'profitability_accuracy' in results:
            print(f"🎯 Profitability prediction accuracy: {results['profitability_accuracy']:.2%}")
        
        if 'pnl_r2_score' in results:
            print(f"📈 PnL prediction score: {results['pnl_r2_score']:.3f}")
            
        return True
    else:
        print(f"❌ ML training failed: {results['error']}")
        return False

def check_prediction_capabilities():
    """Test ML prediction capabilities"""
    print("\n🔮 TESTING PREDICTION CAPABILITIES")
    print("=" * 50)
    
    # Test prediction with sample data
    sample_trade = {
        'strategy': 'rsi_oversold',
        'symbol': 'SOLUSDT', 
        'side': 'BUY',
        'leverage': 5,
        'position_size_usdt': 100,
        'rsi_entry': 25,  # Oversold
        'macd_entry': -0.3,
        'hour_of_day': 14,  # London-NY overlap
        'day_of_week': 2,   # Tuesday
        'month': 12,
        'market_trend': 'BULLISH',
        'volatility_score': 0.3,
        'signal_strength': 0.8
    }
    
    prediction = ml_analyzer.predict_trade_outcome(sample_trade)
    
    if "error" not in prediction:
        print("✅ ML predictions working!")
        print(f"📈 Profit probability: {prediction.get('profit_probability', 0):.2%}")
        print(f"💰 Expected PnL: {prediction.get('predicted_pnl_percentage', 0):.2f}%")
        print(f"⏱️ Expected duration: {prediction.get('predicted_duration_minutes', 0):.0f} minutes")
        print(f"🎯 Recommendation: {prediction.get('recommendation', 'UNKNOWN')}")
        print(f"🔮 Confidence: {prediction.get('confidence', 0):.2%}")
        return True
    else:
        print(f"❌ Prediction failed: {prediction['error']}")
        return False

def check_insights_generation():
    """Check ML insights and strategy analysis"""
    print("\n📊 CHECKING INSIGHTS GENERATION")
    print("=" * 50)
    
    insights = ml_analyzer.generate_insights()
    
    if "error" not in insights:
        print("✅ Insights generation working!")
        
        # Strategy performance
        if 'strategy_performance' in insights:
            print("\n🎯 Strategy Performance Analysis:")
            for strategy, stats in insights['strategy_performance'].items():
                win_rate = stats.get('win_rate', 0)
                trades = stats.get('total_trades', 0)
                avg_pnl = stats.get('avg_pnl', 0)
                print(f"  📊 {strategy}: {win_rate:.1f}% win rate ({trades} trades, {avg_pnl:+.2f}% avg PnL)")
        
        # Time analysis
        if 'best_trading_times' in insights:
            print("\n⏰ Best Trading Times:")
            for time_data in insights['best_trading_times'][:3]:
                hour = time_data.get('hour', 0)
                profitability = time_data.get('profitability', 0)
                print(f"  🕐 {hour:02d}:00 - {profitability:.1f}% profitable")
        
        return True
    else:
        print(f"❌ Insights generation failed: {insights['error']}")
        return False

def analyze_profitability_improvements():
    """Analyze potential profitability improvements"""
    print("\n💡 PROFITABILITY IMPROVEMENT ANALYSIS")
    print("=" * 50)
    
    insights = ml_analyzer.generate_insights()
    
    if "error" not in insights and 'strategy_performance' in insights:
        strategies = insights['strategy_performance']
        
        # Find best and worst performing strategies
        best_strategy = max(strategies.items(), key=lambda x: x[1].get('win_rate', 0))
        worst_strategy = min(strategies.items(), key=lambda x: x[1].get('win_rate', 0))
        
        print("🏆 BEST PERFORMING STRATEGY:")
        print(f"   Strategy: {best_strategy[0]}")
        print(f"   Win Rate: {best_strategy[1].get('win_rate', 0):.1f}%")
        print(f"   Avg PnL: {best_strategy[1].get('avg_pnl', 0):+.2f}%")
        
        print("\n📉 NEEDS IMPROVEMENT:")
        print(f"   Strategy: {worst_strategy[0]}")
        print(f"   Win Rate: {worst_strategy[1].get('win_rate', 0):.1f}%")
        print(f"   Avg PnL: {worst_strategy[1].get('avg_pnl', 0):+.2f}%")
        
        # Time-based recommendations
        if 'best_trading_times' in insights:
            best_times = insights['best_trading_times'][:3]
            print(f"\n⏰ OPTIMIZE TRADING HOURS:")
            for time_data in best_times:
                hour = time_data.get('hour', 0)
                profitability = time_data.get('profitability', 0)
                print(f"   Focus on {hour:02d}:00-{(hour+1)%24:02d}:00 ({profitability:.1f}% profitable)")

def main():
    """Main analysis function"""
    print("🤖 COMPREHENSIVE ML SYSTEM ANALYSIS")
    print("=" * 60)
    
    # Check all components
    data_ok = check_data_collection()
    models_ok = check_ml_models() if data_ok else False
    predictions_ok = check_prediction_capabilities() if models_ok else False
    insights_ok = check_insights_generation() if models_ok else False
    
    # Final assessment
    print("\n" + "=" * 60)
    print("📋 FINAL ML SYSTEM ASSESSMENT")
    print("=" * 60)
    
    print(f"📊 Data Collection: {'✅ WORKING' if data_ok else '❌ NEEDS DATA'}")
    print(f"🤖 ML Models: {'✅ TRAINED' if models_ok else '❌ FAILED'}")
    print(f"🔮 Predictions: {'✅ WORKING' if predictions_ok else '❌ FAILED'}")
    print(f"📊 Insights: {'✅ WORKING' if insights_ok else '❌ FAILED'}")
    
    if all([data_ok, models_ok, predictions_ok, insights_ok]):
        print("\n🎉 ML SYSTEM STATUS: FULLY OPERATIONAL")
        print("✅ Ready to provide profitability suggestions")
        analyze_profitability_improvements()
        
        print("\n💡 NEXT STEPS FOR ENHANCED ML:")
        print("1. Integrate external market data APIs")
        print("2. Add real-time sentiment analysis")
        print("3. Implement ensemble models for better accuracy")
        print("4. Add automated strategy parameter optimization")
        
    else:
        print("\n⚠️ ML SYSTEM STATUS: NEEDS ATTENTION")
        if not data_ok:
            print("- Need more closed trades for training (minimum 5)")
        if not models_ok:
            print("- ML model training failed - check data quality")
        if not predictions_ok:
            print("- Prediction system not working")
        if not insights_ok:
            print("- Insights generation failed")

if __name__ == "__main__":
    main()
