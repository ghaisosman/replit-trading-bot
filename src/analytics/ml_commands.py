
#!/usr/bin/env python3
"""
Machine Learning Commands for Trading Bot
Run ML analysis and get trade recommendations
"""

import sys
import asyncio
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.analytics.ml_analyzer import ml_analyzer
from src.analytics.trade_logger import trade_logger
from src.analytics.daily_reporter import DailyReporter
from src.reporting.telegram_reporter import TelegramReporter
from datetime import datetime, timedelta

def train_ml_models():
    """Train ML models on historical data"""
    print("🤖 Training ML models...")
    results = ml_analyzer.train_models()
    
    if "error" in results:
        print(f"❌ Error: {results['error']}")
    else:
        print("✅ ML models trained successfully!")
        print(f"📊 Profitability accuracy: {results.get('profitability_accuracy', 'N/A'):.2%}")
        print(f"📈 PnL R² score: {results.get('pnl_r2_score', 'N/A'):.2f}")
        print(f"⏱️ Duration R² score: {results.get('duration_r2_score', 'N/A'):.2f}")
        
        if 'profitability_features' in results:
            print("\n🔍 Top features for profitability:")
            for feature, importance in results['profitability_features'][:5]:
                print(f"  {feature}: {importance:.3f}")

def generate_insights():
    """Generate trading insights"""
    print("📊 Generating trading insights...")
    insights = ml_analyzer.generate_insights()
    
    if "error" in insights:
        print(f"❌ Error: {insights['error']}")
    else:
        print("✅ Insights generated successfully!")
        
        # Strategy performance
        if 'strategy_performance' in insights:
            print("\n🎯 Strategy Performance:")
            for strategy, stats in insights['strategy_performance'].items():
                print(f"  {strategy}: Win Rate {stats['was_profitable']['mean']:.2%}")
                
        # Time analysis
        if 'time_analysis' in insights:
            print("\n⏰ Best Trading Hours:")
            for hour, win_rate in insights['time_analysis']['best_trading_hours'].items():
                print(f"  {hour}:00 - {win_rate:.2%} win rate")

def test_prediction():
    """Test ML prediction with sample data"""
    print("🔮 Testing ML prediction...")
    
    # Sample trade features
    sample_features = {
        'strategy': 'rsi_oversold',
        'symbol': 'BTCUSDT',
        'side': 'BUY',
        'leverage': 5,
        'position_size_usdt': 100,
        'rsi_entry': 25,  # Oversold
        'macd_entry': -0.5,
        'hour_of_day': 14,  # London-NY overlap
        'day_of_week': 2,   # Wednesday
        'month': 12,
        'market_trend': 'BULLISH',
        'volatility_score': 0.3,
        'signal_strength': 0.8
    }
    
    prediction = ml_analyzer.predict_trade_outcome(sample_features)
    
    if "error" in prediction:
        print(f"❌ Error: {prediction['error']}")
    else:
        print("✅ Prediction generated!")
        print(f"📈 Profit probability: {prediction.get('profit_probability', 0):.2%}")
        print(f"💰 Predicted PnL: {prediction.get('predicted_pnl_percentage', 0):.2f}%")
        print(f"⏱️ Predicted duration: {prediction.get('predicted_duration_minutes', 0):.0f} minutes")
        print(f"🎯 Recommendation: {prediction.get('recommendation', 'UNKNOWN')}")
        print(f"🔮 Confidence: {prediction.get('confidence', 0):.2%}")

def send_manual_report():
    """Send manual daily report"""
    print("📊 Sending manual daily report...")
    
    # Initialize telegram reporter
    from src.config.global_config import global_config
    telegram_reporter = TelegramReporter()
    daily_reporter = DailyReporter(telegram_reporter)
    
    # Send report for yesterday
    yesterday = datetime.now() - timedelta(days=1)
    success = daily_reporter.send_manual_report(yesterday)
    
    if success:
        print("✅ Daily report sent successfully!")
    else:
        print("❌ Failed to send daily report")

def export_data():
    """Export trade data for external analysis"""
    print("📤 Exporting trade data...")
    
    filename = trade_logger.export_for_ml()
    if filename:
        print(f"✅ Data exported to: {filename}")
    else:
        print("❌ No data to export")

def main():
    """Main menu for ML commands"""
    print("🤖 TRADING BOT ML ANALYTICS")
    print("=" * 40)
    
    while True:
        print("\nOptions:")
        print("1. Train ML models")
        print("2. Generate insights")
        print("3. Test prediction")
        print("4. Send manual daily report")
        print("5. Export trade data")
        print("6. Exit")
        
        choice = input("\nSelect option (1-6): ")
        
        if choice == "1":
            train_ml_models()
        elif choice == "2":
            generate_insights()
        elif choice == "3":
            test_prediction()
        elif choice == "4":
            send_manual_report()
        elif choice == "5":
            export_data()
        elif choice == "6":
            break
        else:
            print("Invalid option")

if __name__ == "__main__":
    main()
