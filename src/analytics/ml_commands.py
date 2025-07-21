
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
        duration_score = results.get('duration_r2_score', 'N/A')
        if isinstance(duration_score, (int, float)):
            print(f"⏱️ Duration R² score: {duration_score:.2f}")
        else:
            print(f"⏱️ Duration R² score: {duration_score}")

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
                win_rate = stats.get('win_rate', 0)
                total_trades = stats.get('total_trades', 0)
                avg_pnl = stats.get('avg_pnl', 0)
                print(f"  📊 {strategy}: {win_rate:.1f}% win rate ({total_trades} trades, {avg_pnl:+.2f}% avg PnL)")

        # Time analysis
        if 'best_trading_times' in insights:
            print("\n⏰ Best Trading Hours:")
            for time_data in insights['best_trading_times'][:3]:
                hour = time_data.get('hour', 0)
                profitability = time_data.get('profitability', 0)
                print(f"  🕐 {hour:02d}:00 - {profitability:.1f}% profitable")

def test_prediction():
    """Test ML prediction with sample data"""
    print("🔮 Testing ML prediction...")
    
    # Check if models are trained, if not, train them first
    if not ml_analyzer.profitability_model:
        print("📚 No trained models found. Training models first...")
        train_results = ml_analyzer.train_models()
        if "error" in train_results:
            print(f"❌ Failed to train models: {train_results['error']}")
            return

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

def run_parameter_optimization():
    """Run parameter optimization simulation"""
    print("🔧 Running parameter optimization...")
    from src.analytics.trade_logger import trade_logger
    
    closed_trades = [t for t in trade_logger.trades if t.trade_status == "CLOSED"]
    if len(closed_trades) < 5:
        print("❌ Need at least 5 closed trades for optimization")
        return
    
    results = ml_analyzer.simulate_parameter_optimization(closed_trades)
    
    if results:
        print("✅ Optimization complete!")
        for scenario_type, data in results.items():
            print(f"\n🎯 {scenario_type.upper()}:")
            print(f"  Average improvement: {data['avg_improvement']:.2f}%")
            print(f"  Best improvement: {data['best_improvement']:.2f}%")
            
            # Show best parameters
            best_params = data['parameters']
            for key, value in best_params.items():
                if key not in ['scenario_type']:
                    print(f"  Optimal {key}: {value}")
    else:
        print("❌ No optimization results generated")

def get_ai_insights():
    """Get insights from external AI advisor"""
    print("🤖 Getting AI advisor insights...")
    
    # Check if API key is set
    api_key = input("Enter OpenAI API key (or press Enter to skip): ").strip()
    
    if not api_key:
        print("⚠️ Skipping AI insights - no API key provided")
        print("💡 To enable AI insights, get an API key from OpenAI, Claude, or Gemini")
        return
    
    try:
        from src.analytics.ai_advisor import ai_advisor
        
        # Set API key
        ai_advisor.set_api_key('openai', api_key)
        
        # Prepare context
        context = ml_analyzer.prepare_ai_context()
        
        # Get AI analysis (mock for now)
        import asyncio
        
        async def get_analysis():
            return await ai_advisor.analyze_trading_performance(context)
        
        response = asyncio.run(get_analysis())
        
        if response.get('success'):
            analysis = response['analysis']
            
            print("\n🎯 AI PERFORMANCE ASSESSMENT:")
            perf = analysis['performance_assessment']
            print(f"  Overall Rating: {perf['overall_rating']}")
            print(f"  Trend: {perf['profitability_trend']}")
            
            print("\n💪 KEY STRENGTHS:")
            for strength in perf['key_strengths']:
                print(f"  ✅ {strength}")
            
            print("\n⚠️ AREAS FOR IMPROVEMENT:")
            for weakness in perf['main_weaknesses']:
                print(f"  📋 {weakness}")
            
            print("\n🔧 IMMEDIATE ACTIONS:")
            for action in analysis['optimization_recommendations']['immediate_actions']:
                print(f"  🎯 {action}")
            
            print("\n💡 TECHNICAL IMPROVEMENTS:")
            for improvement in analysis['technical_improvements']['ml_enhancements']:
                print(f"  🚀 {improvement}")
                
        else:
            print(f"❌ AI analysis failed: {response.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ Error getting AI insights: {e}")

def generate_ai_ready_report():
    """Generate comprehensive report ready for AI analysis"""
    print("📊 Generating AI-ready comprehensive report...")
    
    # Generate detailed report
    report = ml_analyzer.generate_detailed_ai_report("comprehensive")
    
    # Save to file for easy copying
    from pathlib import Path
    reports_dir = Path("trading_data/ai_reports")
    reports_dir.mkdir(exist_ok=True, parents=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"ai_ready_report_{timestamp}.txt"
    filepath = reports_dir / filename
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"✅ Report generated successfully!")
    print(f"📄 Saved to: {filepath}")
    print(f"📋 Report length: {len(report)} characters")
    
    # Show preview
    print("\n" + "="*60)
    print("📖 REPORT PREVIEW (First 1000 characters):")
    print("="*60)
    print(report[:1000] + "..." if len(report) > 1000 else report)
    print("="*60)
    
    # Instructions for use
    print("\n💡 HOW TO USE THIS REPORT:")
    print("1. 📋 Copy the entire report from the saved file")
    print("2. 🤖 Paste it into ChatGPT, Claude, or Gemini")
    print("3. 📝 Ask for specific analysis or recommendations")
    print("4. 🎯 Use AI suggestions to optimize your trading strategy")
    
    print(f"\n📂 Full report available at: {filepath}")
    
    return str(filepath)

def export_structured_data():
    """Export structured data for AI analysis"""
    print("📤 Exporting structured data for AI analysis...")
    
    # Export in JSON format
    structured_data = ml_analyzer.export_ai_ready_data("json")
    
    if "error" in structured_data:
        print(f"❌ Export failed: {structured_data['error']}")
        return
    
    # Save to file
    from pathlib import Path
    import json
    
    reports_dir = Path("trading_data/ai_reports")
    reports_dir.mkdir(exist_ok=True, parents=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"structured_data_{timestamp}.json"
    filepath = reports_dir / filename
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(structured_data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Structured data exported successfully!")
    print(f"📄 Saved to: {filepath}")
    
    # Show summary
    metadata = structured_data.get("report_metadata", {})
    performance = structured_data.get("performance_summary", {})
    
    print(f"\n📊 EXPORT SUMMARY:")
    print(f"   • Total Trades: {metadata.get('total_trades', 0)}")
    print(f"   • Win Rate: {performance.get('win_rate', 0):.1f}%")
    print(f"   • Total PnL: {performance.get('total_pnl_percentage', 0):+.2f}%")
    print(f"   • Strategies: {len(structured_data.get('strategy_breakdown', {}))}")
    
    print("\n💡 This JSON data can be easily imported into AI tools for:")
    print("   • 📈 Statistical analysis")
    print("   • 🔍 Pattern recognition") 
    print("   • 🎯 Strategy optimization")
    print("   • 📊 Custom visualizations")
    
    return str(filepath)

def copy_to_clipboard_report():
    """Generate and copy report to clipboard"""
    print("📋 Generating report for clipboard...")
    
    # Generate the report
    report = ml_analyzer.generate_detailed_ai_report("comprehensive")
    
    try:
        # Try to copy to clipboard (if pyperclip is available)
        import pyperclip
        pyperclip.copy(report)
        print("✅ Report copied to clipboard!")
        print("🤖 You can now paste directly into AI services")
        
    except ImportError:
        print("⚠️ Clipboard copy not available (install pyperclip for this feature)")
        print("📄 Report generated - you can manually copy from the file")
        
        # Save to file as fallback
        from pathlib import Path
        reports_dir = Path("trading_data/ai_reports")
        reports_dir.mkdir(exist_ok=True, parents=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"clipboard_report_{timestamp}.txt"
        filepath = reports_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"📂 Saved to: {filepath}")
    
    print(f"\n📊 Report Stats:")
    print(f"   • Length: {len(report):,} characters") 
    print(f"   • Word count: {len(report.split()):,} words")
    print(f"   • Ready for AI analysis: ✅")
    
    return report

def analyze_what_if_scenarios():
    """Analyze what-if scenarios for trade optimization"""
    print("🔮 Analyzing what-if scenarios...")
    
    results = ml_analyzer.analyze_what_if_scenarios_for_commands()
    
    if "error" in results:
        print(f"❌ {results['error']}")
        return
    
    print(f"📊 Analyzing scenarios for trade: {results['base_trade_id']}")
    print(f"🎯 Actual PnL: {results['actual_pnl']:.2f}%")
    
    scenario_results = results['scenario_results']
    total_scenarios = sum(len(scenarios) for scenarios in scenario_results.values())
    print(f"\n🔍 Generated {total_scenarios} scenarios:")
    
    for scenario_type, scenarios in scenario_results.items():
        print(f"\n📋 {scenario_type.upper()} SCENARIOS:")
        
        for result in scenarios:
            scenario = result['scenario']
            predicted_pnl = result['predicted_pnl']
            improvement = result['improvement']
            leverage = scenario.get('leverage', 'N/A')
            size = scenario.get('position_size_usdt', 'N/A')
            print(f"  🔄 Leverage: {leverage}x, Size: ${size:.0f} → Predicted PnL: {predicted_pnl:.2f}% (improvement: {improvement:+.2f}%)")

def generate_enhanced_insights():
    """Generate enhanced insights with advanced analytics"""
    print("📊 Generating enhanced insights...")
    
    insights = ml_analyzer.get_enhanced_insights()
    
    if "error" in insights:
        print(f"❌ Error: {insights['error']}")
        return
    
    print("✅ Enhanced insights generated!")
    
    # Show parameter optimization results
    if 'optimization_scenarios' in insights:
        print("\n🎯 PARAMETER OPTIMIZATION RESULTS:")
        for scenario_type, data in insights['optimization_scenarios'].items():
            print(f"  📊 {scenario_type}: {data['avg_improvement']:+.2f}% avg improvement")
    
    # Show market regime analysis  
    if 'market_regime_analysis' in insights:
        print("\n🌊 MARKET REGIME ANALYSIS:")
        regimes = insights['market_regime_analysis']
        for regime, stats in regimes.items():
            print(f"  📈 {regime}: {stats['win_rate']:.1%} win rate ({stats['trade_count']} trades)")
    
    # Show traditional insights
    if 'strategy_performance' in insights:
        print("\n🏆 STRATEGY PERFORMANCE:")
        for strategy, stats in insights['strategy_performance'].items():
            print(f"  📊 {strategy}: {stats['win_rate']:.1f}% win rate, {stats['avg_pnl']:+.2f}% avg PnL")

def main():
    """Enhanced main menu for ML commands"""
    print("🤖 ENHANCED TRADING BOT ML ANALYTICS")
    print("=" * 50)

    while True:
        print("\n🎯 CORE ML FUNCTIONS:")
        print("1. Train ML models")
        print("2. Generate basic insights") 
        print("3. Test prediction")
        
        print("\n🚀 ADVANCED ANALYTICS:")
        print("4. Generate enhanced insights")
        print("5. Run parameter optimization")
        print("6. Analyze what-if scenarios")
        print("7. Get external AI insights")
        
        print("\n📊 AI-READY REPORTS:")
        print("8. Generate comprehensive AI report")
        print("9. Export structured data (JSON)")
        print("10. Copy report to clipboard")
        
        print("\n📋 REPORTING & DATA:")
        print("11. Send manual daily report")
        print("12. Export trade data")
        print("13. Exit")

        choice = input("\nSelect option (1-13): ")

        if choice == "1":
            train_ml_models()
        elif choice == "2":
            generate_insights()
        elif choice == "3":
            test_prediction()
        elif choice == "4":
            generate_enhanced_insights()
        elif choice == "5":
            run_parameter_optimization()
        elif choice == "6":
            analyze_what_if_scenarios()
        elif choice == "7":
            get_ai_insights()
        elif choice == "8":
            generate_ai_ready_report()
        elif choice == "9":
            export_structured_data()
        elif choice == "10":
            copy_to_clipboard_report()
        elif choice == "11":
            send_manual_report()
        elif choice == "12":
            export_data()
        elif choice == "13":
            break
        else:
            print("Invalid option")

if __name__ == "__main__":
    main()
