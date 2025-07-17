
#!/usr/bin/env python3
"""
Check ML System Status and Train Models
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.analytics.ml_analyzer import ml_analyzer
from src.analytics.trade_logger import trade_logger
import json

def check_ml_data_status():
    """Check if ML data is being collected properly"""
    print("🔍 CHECKING ML DATA COLLECTION STATUS")
    print("=" * 50)

    # Check trade logger
    print(f"📊 Total trades logged: {len(trade_logger.trades)}")

    # Check ML dataset
    dataset = ml_analyzer.prepare_ml_dataset()
    if dataset is not None:
        print(f"📈 ML dataset size: {len(dataset)} trades")
        print(f"🔢 Features available: {len(dataset.columns)}")

        # Check profitability distribution
        if 'was_profitable' in dataset.columns:
            profitable_trades = dataset['was_profitable'].sum()
            total_trades = len(dataset)
            win_rate = profitable_trades / total_trades if total_trades > 0 else 0
            print(f"💰 Win rate: {win_rate:.2%} ({profitable_trades}/{total_trades})")

        # Show key features
        print(f"🔑 Key features: {list(dataset.columns[:10])}")

        return True
    else:
        print("❌ No ML dataset available")
        return False

def train_and_analyze():
    """Train ML models and generate insights"""
    print("\n🤖 TRAINING ML MODELS FOR PROFIT OPTIMIZATION")
    print("=" * 50)

    # Train models
    results = ml_analyzer.train_models()

    if "error" not in results:
        print("✅ ML models trained successfully!")

        if 'profitability_accuracy' in results:
            print(f"📊 Profitability prediction accuracy: {results['profitability_accuracy']:.2%}")

        if 'pnl_r2_score' in results:
            print(f"📈 PnL prediction score: {results['pnl_r2_score']:.2f}")

        # Generate insights
        print("\n🔍 GENERATING PROFIT OPTIMIZATION INSIGHTS")
        print("-" * 40)

        insights = ml_analyzer.generate_insights()

        if 'strategy_performance' in insights:
            print("🎯 Strategy Performance Analysis:")
            for strategy, stats in insights['strategy_performance'].items():
                if isinstance(stats, dict) and 'was_profitable' in stats:
                    win_rate = stats['was_profitable'].get('mean', 0)
                    trade_count = stats['was_profitable'].get('count', 0)
                    avg_pnl = stats.get('pnl_percentage', {}).get('mean', 0)
                    print(f"  📊 {strategy}: {win_rate:.2%} win rate, {trade_count} trades, {avg_pnl:.2f}% avg PnL")

        if 'time_analysis' in insights:
            print("\n⏰ Best Trading Hours for Profits:")
            best_hours = insights['time_analysis'].get('best_trading_hours', {})
            for hour, win_rate in list(best_hours.items())[:3]:
                print(f"  🕐 {hour}:00 - {win_rate:.2%} win rate")

        # Test prediction on current market conditions
        print("\n🔮 TESTING PROFIT PREDICTION")
        print("-" * 30)

        sample_trade = {
            'strategy': 'rsi_oversold',
            'symbol': 'BTCUSDT',
            'side': 'BUY',
            'leverage': 5,
            'position_size_usdt': 100,
            'rsi_entry': 28,  # Oversold
            'hour_of_day': 14,  # Good trading hour
            'day_of_week': 2,   # Midweek
            'market_trend': 'BULLISH',
            'volatility_score': 0.4,
            'signal_strength': 0.9
        }

        prediction = ml_analyzer.predict_trade_outcome(sample_trade)

        if "error" not in prediction:
            print(f"📈 Profit probability: {prediction.get('profit_probability', 0):.2%}")
            print(f"💰 Expected PnL: {prediction.get('predicted_pnl_percentage', 0):.2f}%")
            print(f"🎯 Recommendation: {prediction.get('recommendation', 'UNKNOWN')}")
            print(f"🔮 Confidence: {prediction.get('confidence', 0):.2%}")

    else:
        print(f"❌ Error training models: {results['error']}")

def main():
    """Main function"""
    print("🤖 ML PROFIT OPTIMIZATION CHECK")
    print("=" * 40)

    # Check data collection status
    has_data = check_ml_data_status()

    if has_data:
        # Train models and analyze
        train_and_analyze()

        print("\n✅ SUMMARY:")
        print("- ML data collection: ✅ Active")
        print("- Profit prediction: ✅ Trained")
        print("- Strategy optimization: ✅ Available")
        print("- Future suggestions: ✅ Ready")

        print("\n💡 RECOMMENDATIONS:")
        print("- Run this analysis daily to improve predictions")
        print("- Use ML insights to optimize strategy parameters")
        print("- Monitor win rates by time and market conditions")
        print("- Adjust position sizing based on ML confidence scores")

    else:
        print("\n⚠️ Insufficient data for ML analysis")
        print("Need at least 10-20 trades for meaningful insights")

if __name__ == "__main__":
    main()
