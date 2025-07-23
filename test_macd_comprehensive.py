
#!/usr/bin/env python3
"""
Comprehensive MACD Signal Detection Test
Tests MACD strategy signal generation, configuration handling, and debug analysis
"""

import sys
import pandas as pd
import logging
from datetime import datetime, timedelta
import json

# Add src to path
sys.path.append('src')

from src.config.global_config import global_config
from src.binance_client.client import BinanceClientWrapper
from src.execution_engine.strategies.macd_divergence_strategy import MACDDivergenceStrategy
from src.strategy_processor.signal_processor import SignalProcessor
from src.utils.logger import setup_logger

# Setup logging with debug level
setup_logger()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def load_dashboard_configs():
    """Load MACD configurations from the web dashboard's strategy templates"""
    try:
        # Import the web dashboard to get strategy templates
        import web_dashboard
        app = web_dashboard.app
        
        with app.app_context():
            interface = web_dashboard.BacktestWebInterface()
            templates = interface.get_strategy_templates()
            
            macd_configs = []
            for template_name, template_config in templates.items():
                if 'macd' in template_name.lower():
                    macd_configs.append({
                        'name': template_name,
                        **template_config
                    })
            
            return macd_configs
    except Exception as e:
        logger.warning(f"Could not load dashboard configs: {e}")
        return []

def test_macd_signal_detection_comprehensive():
    """Comprehensive test of MACD signal detection with multiple configurations"""
    try:
        logger.info("🚀 STARTING COMPREHENSIVE MACD SIGNAL DETECTION TEST")
        logger.info("=" * 80)
        
        # Initialize Binance client
        binance_client = BinanceClientWrapper()
        
        # Load configurations from dashboard
        dashboard_configs = load_dashboard_configs()
        
        # Test configurations - from dashboard + custom test configs
        test_configs = [
            # Ultra aggressive for testing
            {
                'name': 'macd_ultra_test',
                'symbol': 'BTCUSDT',
                'timeframe': '15m',
                'margin': 50.0,
                'leverage': 5,
                'max_loss_pct': 10,
                'macd_fast': 8,
                'macd_slow': 21,
                'macd_signal': 5,
                'min_histogram_threshold': 0.000001,  # Ultra low
                'macd_entry_threshold': 0.00001,     # Ultra low
                'macd_exit_threshold': 0.001,
                'confirmation_candles': 1
            },
            # Standard configuration
            {
                'name': 'macd_standard_test',
                'symbol': 'BTCUSDT',
                'timeframe': '15m',
                'margin': 50.0,
                'leverage': 5,
                'max_loss_pct': 10,
                'macd_fast': 12,
                'macd_slow': 26,
                'macd_signal': 9,
                'min_histogram_threshold': 0.0001,
                'macd_entry_threshold': 0.005,
                'macd_exit_threshold': 0.01,
                'confirmation_candles': 1
            }
        ]
        
        # Add dashboard configs to test
        test_configs.extend(dashboard_configs)
        
        # Get market data for testing
        logger.info("📊 FETCHING MARKET DATA...")
        klines = binance_client.get_klines(
            symbol='BTCUSDT',
            interval='15m',
            limit=200  # More data for better testing
        )
        
        if not klines:
            logger.error("❌ No market data available!")
            return False
        
        # Convert to DataFrame
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])
        
        # Convert to numeric
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col])
        
        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        logger.info(f"✅ Market data loaded: {len(df)} candles")
        logger.info(f"📊 Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")
        logger.info(f"📅 Time range: {df.index[0]} to {df.index[-1]}")
        
        results = []
        
        # Test each configuration
        for i, config in enumerate(test_configs, 1):
            logger.info(f"\n{'='*80}")
            logger.info(f"🔍 TEST {i}/{len(test_configs)}: {config['name']}")
            logger.info(f"{'='*80}")
            
            try:
                result = test_single_macd_config(df.copy(), config)
                results.append(result)
                
            except Exception as config_error:
                logger.error(f"❌ Error testing config {config['name']}: {config_error}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                
                results.append({
                    'config_name': config['name'],
                    'success': False,
                    'error': str(config_error)
                })
                continue
        
        # Generate summary report
        logger.info(f"\n{'='*80}")
        logger.info(f"📋 COMPREHENSIVE TEST RESULTS SUMMARY")
        logger.info(f"{'='*80}")
        
        successful_tests = sum(1 for r in results if r.get('success', False))
        total_signals = sum(r.get('signals_generated', 0) for r in results if r.get('success', False))
        
        logger.info(f"✅ Successful Tests: {successful_tests}/{len(results)}")
        logger.info(f"🎯 Total Signals Generated: {total_signals}")
        
        # Detailed results
        for result in results:
            if result.get('success', False):
                logger.info(f"✅ {result['config_name']}: {result['signals_generated']} signals")
                if result.get('signal_details'):
                    for signal in result['signal_details']:
                        logger.info(f"   📈 {signal['type']} at ${signal['price']:.4f} - {signal['reason']}")
            else:
                logger.error(f"❌ {result['config_name']}: {result.get('error', 'Unknown error')}")
        
        # Save detailed results to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"trading_data/macd_test_results_{timestamp}.json"
        
        try:
            with open(results_file, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            logger.info(f"💾 Detailed results saved to: {results_file}")
        except Exception as e:
            logger.warning(f"Could not save results file: {e}")
        
        logger.info(f"\n{'='*80}")
        logger.info(f"🏁 COMPREHENSIVE MACD TEST COMPLETE")
        logger.info(f"{'='*80}")
        
        return successful_tests > 0
        
    except Exception as e:
        logger.error(f"❌ Error in comprehensive MACD test: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return False

def test_single_macd_config(df: pd.DataFrame, config: Dict) -> Dict:
    """Test a single MACD configuration"""
    config_name = config.get('name', 'unknown')
    
    try:
        logger.info(f"🔧 CONFIG PARAMETERS:")
        for key, value in config.items():
            if 'macd' in key.lower() or key in ['margin', 'leverage', 'max_loss_pct', 'symbol', 'timeframe']:
                logger.info(f"   {key}: {value}")
        
        # Test 1: Strategy Class Direct Test
        logger.info(f"\n🧪 TEST 1: STRATEGY CLASS DIRECT")
        strategy = MACDDivergenceStrategy(config_name, config)
        
        # Calculate indicators
        df_with_indicators = strategy.calculate_indicators(df.copy())
        
        if df_with_indicators.empty or 'macd' not in df_with_indicators.columns:
            raise Exception("Failed to calculate MACD indicators")
        
        # Check indicator values
        macd_current = df_with_indicators['macd'].iloc[-1]
        signal_current = df_with_indicators['macd_signal'].iloc[-1]
        histogram_current = df_with_indicators['macd_histogram'].iloc[-1]
        histogram_prev = df_with_indicators['macd_histogram'].iloc[-2]
        
        logger.info(f"📊 CURRENT INDICATORS:")
        logger.info(f"   MACD Line: {macd_current:.6f}")
        logger.info(f"   Signal Line: {signal_current:.6f}")
        logger.info(f"   Histogram: {histogram_current:.6f} (prev: {histogram_prev:.6f})")
        logger.info(f"   Momentum: {histogram_current - histogram_prev:.6f}")
        
        # Test signal generation
        signal_direct = strategy.evaluate_entry_signal(df_with_indicators)
        
        # Test 2: Signal Processor Test
        logger.info(f"\n🧪 TEST 2: SIGNAL PROCESSOR")
        signal_processor = SignalProcessor()
        signal_processor_result = signal_processor._evaluate_macd_divergence(df_with_indicators, df_with_indicators['close'].iloc[-1], config)
        
        # Test 3: Historical Signal Scan
        logger.info(f"\n🧪 TEST 3: HISTORICAL SIGNAL SCAN")
        historical_signals = scan_historical_signals(df_with_indicators, strategy, config)
        
        # Compile results
        signals_generated = 0
        signal_details = []
        
        if signal_direct:
            signals_generated += 1
            signal_details.append({
                'type': signal_direct.signal_type.value,
                'price': signal_direct.entry_price,
                'reason': signal_direct.reason,
                'confidence': signal_direct.confidence,
                'source': 'strategy_direct'
            })
            logger.info(f"✅ DIRECT SIGNAL: {signal_direct.signal_type.value} at ${signal_direct.entry_price:.4f}")
        
        if signal_processor_result:
            signals_generated += 1
            signal_details.append({
                'type': signal_processor_result.signal_type.value,
                'price': signal_processor_result.entry_price,
                'reason': signal_processor_result.reason,
                'confidence': signal_processor_result.confidence,
                'source': 'signal_processor'
            })
            logger.info(f"✅ PROCESSOR SIGNAL: {signal_processor_result.signal_type.value} at ${signal_processor_result.entry_price:.4f}")
        
        # Add historical signals
        for hist_signal in historical_signals:
            signal_details.append({
                **hist_signal,
                'source': 'historical'
            })
        
        signals_generated += len(historical_signals)
        
        logger.info(f"📊 TOTAL SIGNALS FOUND: {signals_generated}")
        
        # Signal Analysis
        if signals_generated == 0:
            logger.warning(f"⚠️ NO SIGNALS GENERATED - ANALYZING CONDITIONS")
            analyze_signal_conditions(df_with_indicators, config)
        
        return {
            'config_name': config_name,
            'success': True,
            'signals_generated': signals_generated,
            'signal_details': signal_details,
            'macd_current': macd_current,
            'signal_current': signal_current,
            'histogram_current': histogram_current,
            'histogram_momentum': histogram_current - histogram_prev
        }
        
    except Exception as e:
        logger.error(f"❌ Error testing config {config_name}: {e}")
        return {
            'config_name': config_name,
            'success': False,
            'error': str(e)
        }

def scan_historical_signals(df: pd.DataFrame, strategy: MACDDivergenceStrategy, config: Dict) -> List[Dict]:
    """Scan historical data for signals"""
    signals = []
    
    # Look at last 50 candles for historical signals
    for i in range(len(df) - 50, len(df)):
        try:
            if i < 50:  # Need enough data for indicators
                continue
                
            df_slice = df.iloc[:i+1].copy()
            signal = strategy.evaluate_entry_signal(df_slice)
            
            if signal:
                signals.append({
                    'type': signal.signal_type.value,
                    'price': signal.entry_price,
                    'reason': signal.reason,
                    'confidence': signal.confidence,
                    'timestamp': df.index[i],
                    'candle_index': i
                })
                
        except Exception as e:
            continue
    
    if signals:
        logger.info(f"📈 HISTORICAL SIGNALS FOUND: {len(signals)}")
        for signal in signals[-3:]:  # Show last 3
            logger.info(f"   {signal['timestamp']}: {signal['type']} at ${signal['price']:.4f}")
    
    return signals

def analyze_signal_conditions(df: pd.DataFrame, config: Dict):
    """Analyze why no signals were generated"""
    logger.info(f"🔍 SIGNAL CONDITION ANALYSIS:")
    
    macd_current = df['macd'].iloc[-1]
    signal_current = df['macd_signal'].iloc[-1]
    histogram_current = df['macd_histogram'].iloc[-1]
    histogram_prev = df['macd_histogram'].iloc[-2]
    
    min_histogram_threshold = config.get('min_histogram_threshold', 0.0001)
    
    # Check bullish conditions
    below_signal = macd_current < signal_current
    momentum_up = histogram_current > histogram_prev
    still_negative = histogram_current < 0
    momentum_threshold = abs(histogram_current - histogram_prev) >= min_histogram_threshold
    
    logger.info(f"   🟢 BULLISH CONDITIONS:")
    logger.info(f"     MACD < Signal: {below_signal} ({macd_current:.6f} < {signal_current:.6f})")
    logger.info(f"     Momentum Up: {momentum_up} ({histogram_current:.6f} > {histogram_prev:.6f})")
    logger.info(f"     Still Negative: {still_negative} ({histogram_current:.6f} < 0)")
    logger.info(f"     Momentum Threshold: {momentum_threshold} ({abs(histogram_current - histogram_prev):.6f} >= {min_histogram_threshold})")
    
    # Check bearish conditions
    above_signal = macd_current > signal_current
    momentum_down = histogram_current < histogram_prev
    still_positive = histogram_current > 0
    
    logger.info(f"   🔴 BEARISH CONDITIONS:")
    logger.info(f"     MACD > Signal: {above_signal} ({macd_current:.6f} > {signal_current:.6f})")
    logger.info(f"     Momentum Down: {momentum_down} ({histogram_current:.6f} < {histogram_prev:.6f})")
    logger.info(f"     Still Positive: {still_positive} ({histogram_current:.6f} > 0)")
    logger.info(f"     Momentum Threshold: {momentum_threshold}")
    
    # Suggestions
    if not momentum_threshold:
        logger.warning(f"💡 SUGGESTION: Try lowering min_histogram_threshold (current: {min_histogram_threshold})")
    
    if abs(histogram_current) < 0.00001:
        logger.warning(f"💡 SUGGESTION: MACD values are very small, market may be in consolidation")

if __name__ == "__main__":
    success = test_macd_signal_detection_comprehensive()
    if success:
        print("\n✅ MACD signal detection test completed successfully")
    else:
        print("\n❌ MACD signal detection test failed")
