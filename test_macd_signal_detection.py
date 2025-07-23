
#!/usr/bin/env python3
"""
MACD Signal Detection Test
Test MACD strategy signal generation with current market data
"""

import sys
import pandas as pd
import logging
from datetime import datetime, timedelta

# Add src to path
sys.path.append('src')

from src.config.global_config import global_config
from src.binance_client.client import BinanceClientWrapper
from src.execution_engine.strategies.macd_divergence_strategy import MACDDivergenceStrategy
from src.strategy_processor.signal_processor import SignalProcessor
from src.utils.logger import setup_logger

# Setup logging
setup_logger()
logger = logging.getLogger(__name__)

def test_macd_signal_generation():
    """Test MACD signal generation with various configurations"""
    try:
        # Initialize Binance client
        binance_client = BinanceClientWrapper()
        
        # Test configurations - from most aggressive to most conservative
        test_configs = [
            {
                'name': 'macd_ultra_aggressive',
                'symbol': 'BTCUSDT',
                'timeframe': '15m',
                'margin': 50.0,
                'leverage': 5,
                'max_loss_pct': 10,
                'macd_fast': 8,
                'macd_slow': 21,
                'macd_signal': 5,
                'min_histogram_threshold': 0.00001,  # Ultra low
                'macd_entry_threshold': 0.0001,     # Ultra low
                'macd_exit_threshold': 0.001,
                'confirmation_candles': 1
            },
            {
                'name': 'macd_very_aggressive',
                'symbol': 'BTCUSDT',
                'timeframe': '15m',
                'margin': 50.0,
                'leverage': 5,
                'max_loss_pct': 10,
                'macd_fast': 10,
                'macd_slow': 22,
                'macd_signal': 7,
                'min_histogram_threshold': 0.0001,
                'macd_entry_threshold': 0.001,
                'macd_exit_threshold': 0.002,
                'confirmation_candles': 1
            },
            {
                'name': 'macd_aggressive',
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
        
        # Test each configuration
        for config in test_configs:
            logger.info(f"\n{'='*60}")
            logger.info(f"🔍 TESTING CONFIG: {config['name']}")
            logger.info(f"{'='*60}")
            
            try:
                # Get market data
                klines = binance_client.get_klines(
                    symbol=config['symbol'],
                    interval=config['timeframe'],
                    limit=100
                )
                
                if not klines:
                    logger.error(f"❌ No klines data for {config['symbol']}")
                    continue
                
                # Convert to DataFrame
                df = pd.DataFrame(klines, columns=[
                    'timestamp', 'open', 'high', 'low', 'close', 'volume',
                    'close_time', 'quote_asset_volume', 'number_of_trades',
                    'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
                ])
                
                # Convert to numeric
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = pd.to_numeric(df[col])
                
                logger.info(f"📊 Market data loaded: {len(df)} candles for {config['symbol']}")
                logger.info(f"📊 Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")
                
                # Test strategy directly
                strategy = MACDDivergenceStrategy(config['name'], config)
                
                # Calculate indicators
                df_with_indicators = strategy.calculate_indicators(df.copy())
                
                if df_with_indicators.empty:
                    logger.error(f"❌ Failed to calculate indicators")
                    continue
                
                # Check if indicators were calculated
                required_columns = ['macd', 'macd_signal', 'macd_histogram']
                missing_columns = [col for col in required_columns if col not in df_with_indicators.columns]
                
                if missing_columns:
                    logger.error(f"❌ Missing indicator columns: {missing_columns}")
                    continue
                
                # Get current indicator values
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
                signal = strategy.evaluate_entry_signal(df_with_indicators)
                
                if signal:
                    logger.info(f"✅ SIGNAL GENERATED!")
                    logger.info(f"   Type: {signal.signal_type.value}")
                    logger.info(f"   Entry Price: ${signal.entry_price:.4f}")
                    logger.info(f"   Stop Loss: ${signal.stop_loss:.4f}")
                    logger.info(f"   Reason: {signal.reason}")
                    logger.info(f"   Confidence: {signal.confidence}")
                else:
                    logger.warning(f"⚠️ NO SIGNAL GENERATED")
                    
                    # Analyze why no signal was generated
                    logger.info(f"🔍 SIGNAL ANALYSIS:")
                    
                    # Check bullish conditions
                    below_signal = macd_current < signal_current
                    momentum_up = histogram_current > histogram_prev
                    still_negative = histogram_current < 0
                    momentum_threshold = abs(histogram_current - histogram_prev) >= config['min_histogram_threshold']
                    
                    logger.info(f"   Bullish Conditions:")
                    logger.info(f"     MACD < Signal: {below_signal} ({macd_current:.6f} < {signal_current:.6f})")
                    logger.info(f"     Momentum Up: {momentum_up} ({histogram_current:.6f} > {histogram_prev:.6f})")
                    logger.info(f"     Still Negative: {still_negative} ({histogram_current:.6f} < 0)")
                    logger.info(f"     Momentum Threshold: {momentum_threshold} ({abs(histogram_current - histogram_prev):.6f} >= {config['min_histogram_threshold']})")
                    
                    # Check bearish conditions
                    above_signal = macd_current > signal_current
                    momentum_down = histogram_current < histogram_prev
                    still_positive = histogram_current > 0
                    
                    logger.info(f"   Bearish Conditions:")
                    logger.info(f"     MACD > Signal: {above_signal} ({macd_current:.6f} > {signal_current:.6f})")
                    logger.info(f"     Momentum Down: {momentum_down} ({histogram_current:.6f} < {histogram_prev:.6f})")
                    logger.info(f"     Still Positive: {still_positive} ({histogram_current:.6f} > 0)")
                    logger.info(f"     Momentum Threshold: {momentum_threshold}")
                    
                # Test with signal processor
                logger.info(f"\n🔍 TESTING VIA SIGNAL PROCESSOR:")
                signal_processor = SignalProcessor()
                signal_proc = signal_processor._evaluate_macd_divergence(df_with_indicators, df_with_indicators['close'].iloc[-1], config)
                
                if signal_proc:
                    logger.info(f"✅ SIGNAL PROCESSOR GENERATED SIGNAL!")
                    logger.info(f"   Type: {signal_proc.signal_type.value}")
                else:
                    logger.warning(f"⚠️ SIGNAL PROCESSOR: NO SIGNAL")
                    
            except Exception as config_error:
                logger.error(f"❌ Error testing config {config['name']}: {config_error}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                continue
                
        logger.info(f"\n{'='*60}")
        logger.info(f"🏁 MACD SIGNAL DETECTION TEST COMPLETE")
        logger.info(f"{'='*60}")
        
    except Exception as e:
        logger.error(f"❌ Error in MACD signal test: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    test_macd_signal_generation()
