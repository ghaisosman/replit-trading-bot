
#!/usr/bin/env python3
"""
Investigate MACD Strategy Margin Discrepancy
Analyzes why MACD strategy used 39 USDT margin instead of expected amount
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.trade_database import TradeDatabase
from src.binance_client.client import BinanceClientWrapper
from src.config.trading_config import trading_config_manager
from datetime import datetime, timedelta

def investigate_macd_margin_discrepancy():
    """Investigate the MACD margin discrepancy issue"""
    print("🔍 INVESTIGATING MACD STRATEGY MARGIN DISCREPANCY")
    print("=" * 70)
    print("Expected: 10 USDT margin with 3x leverage")
    print("Actual: 39 USDT margin used")
    print("=" * 70)
    
    # Get current MACD strategy configuration
    print("\n📋 STEP 1: ANALYZING CURRENT MACD CONFIGURATION")
    try:
        macd_config = trading_config_manager.get_strategy_config('macd_divergence', {})
        
        configured_margin = macd_config.get('margin', 'N/A')
        configured_leverage = macd_config.get('leverage', 'N/A')
        configured_symbol = macd_config.get('symbol', 'N/A')
        
        print(f"✅ Current MACD Configuration:")
        print(f"   💰 Configured Margin: {configured_margin} USDT")
        print(f"   ⚡ Configured Leverage: {configured_leverage}x")
        print(f"   💱 Symbol: {configured_symbol}")
        print(f"   📊 Expected Position Value: {configured_margin * configured_leverage if isinstance(configured_margin, (int, float)) and isinstance(configured_leverage, (int, float)) else 'N/A'} USDT")
        
        # Check if configuration matches expected values
        if configured_margin == 10 and configured_leverage == 3:
            print(f"   ✅ Configuration matches your description")
        else:
            print(f"   ⚠️ Configuration differs from your description (10 USDT, 3x)")
            
    except Exception as e:
        print(f"❌ Error loading MACD config: {e}")
        return False

    # Check local database for recent MACD trades
    print(f"\n📊 STEP 2: CHECKING LOCAL DATABASE FOR RECENT MACD TRADES")
    try:
        trade_db = TradeDatabase()
        
        # Find recent MACD trades (last 7 days)
        cutoff_date = datetime.now() - timedelta(days=7)
        macd_trades = []
        
        for trade_id, trade_data in trade_db.trades.items():
            trade_timestamp = trade_data.get('timestamp')
            strategy_name = trade_data.get('strategy_name', '').lower()
            
            # Parse timestamp
            try:
                if isinstance(trade_timestamp, str):
                    trade_time = datetime.fromisoformat(trade_timestamp.replace('Z', '+00:00'))
                elif isinstance(trade_timestamp, datetime):
                    trade_time = trade_timestamp
                else:
                    continue
                    
                if trade_time > cutoff_date and 'macd' in strategy_name:
                    macd_trades.append((trade_id, trade_data, trade_time))
            except:
                continue
        
        # Sort by timestamp (newest first)
        macd_trades.sort(key=lambda x: x[2], reverse=True)
        
        print(f"📊 Found {len(macd_trades)} MACD trades in local database (last 7 days)")
        
        if macd_trades:
            print(f"\n🔍 ANALYZING RECENT MACD TRADES:")
            
            for i, (trade_id, trade_data, trade_time) in enumerate(macd_trades[:5]):  # Check last 5 trades
                margin_used = trade_data.get('margin_used', 'N/A')
                leverage = trade_data.get('leverage', 'N/A')
                position_value = trade_data.get('position_value_usdt', 'N/A')
                entry_price = trade_data.get('entry_price', 'N/A')
                quantity = trade_data.get('quantity', 'N/A')
                symbol = trade_data.get('symbol', 'N/A')
                trade_status = trade_data.get('trade_status', 'N/A')
                
                print(f"\n   📋 MACD Trade #{i+1}: {trade_id}")
                print(f"      ⏰ Time: {trade_time.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"      💱 Symbol: {symbol}")
                print(f"      📊 Status: {trade_status}")
                print(f"      💰 Margin Used: {margin_used} USDT")
                print(f"      ⚡ Leverage: {leverage}x")
                print(f"      💵 Position Value: {position_value} USDT")
                print(f"      🔢 Entry Price: {entry_price}")
                print(f"      📏 Quantity: {quantity}")
                
                # Check if this matches the 39 USDT margin issue
                if isinstance(margin_used, (int, float)) and abs(margin_used - 39) < 1:
                    print(f"      🚨 POTENTIAL MATCH: This trade used ~39 USDT margin!")
                    
                    # Analyze the discrepancy
                    if isinstance(position_value, (int, float)) and isinstance(leverage, (int, float)) and leverage > 0:
                        expected_margin = position_value / leverage
                        print(f"      🔧 MARGIN CALCULATION CHECK:")
                        print(f"         Position Value: ${position_value:.2f}")
                        print(f"         Leverage: {leverage}x")
                        print(f"         Expected Margin: ${expected_margin:.2f}")
                        print(f"         Actual Margin: ${margin_used:.2f}")
                        print(f"         Discrepancy: ${abs(margin_used - expected_margin):.2f}")
        else:
            print(f"   ⚠️ No MACD trades found in local database")
            print(f"   📝 Note: Since bot is deployed on Render, recent trades may not be in local database")
            
    except Exception as e:
        print(f"❌ Error checking local database: {e}")

    # Check Binance positions for current MACD positions
    print(f"\n🌐 STEP 3: CHECKING BINANCE FOR CURRENT POSITIONS")
    try:
        binance_client = BinanceClientWrapper()
        
        # Get current positions
        if binance_client.is_futures:
            positions = binance_client.client.futures_position_information()
            
            macd_positions = []
            for position in positions:
                position_amt = float(position.get('positionAmt', 0))
                if abs(position_amt) > 0.000001:  # Position exists
                    symbol = position.get('symbol', '')
                    # Check if this could be a MACD position (common MACD symbols)
                    if symbol in ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'ADAUSDT', 'XRPUSDT']:
                        macd_positions.append(position)
            
            print(f"📊 Found {len(macd_positions)} active positions on potential MACD symbols")
            
            if macd_positions:
                print(f"\n🔍 ANALYZING CURRENT POSITIONS:")
                
                for i, position in enumerate(macd_positions):
                    symbol = position.get('symbol', 'N/A')
                    position_amt = float(position.get('positionAmt', 0))
                    entry_price = float(position.get('entryPrice', 0))
                    mark_price = float(position.get('markPrice', 0))
                    unrealized_pnl = float(position.get('unRealizedProfit', 0))
                    initial_margin = float(position.get('initialMargin', 0))
                    
                    # Calculate position value
                    position_value = abs(position_amt) * mark_price
                    
                    print(f"\n   📋 Position #{i+1}: {symbol}")
                    print(f"      📏 Quantity: {position_amt}")
                    print(f"      💵 Entry Price: ${entry_price:.4f}")
                    print(f"      📊 Mark Price: ${mark_price:.4f}")
                    print(f"      💰 Position Value: ${position_value:.2f} USDT")
                    print(f"      💸 Initial Margin: ${initial_margin:.2f} USDT")
                    print(f"      📈 Unrealized PnL: ${unrealized_pnl:.2f} USDT")
                    
                    # Check if this matches the 39 USDT margin issue
                    if abs(initial_margin - 39) < 1:
                        print(f"      🚨 POTENTIAL MATCH: This position uses ~39 USDT margin!")
                        
                        # Calculate what the leverage would be
                        if initial_margin > 0:
                            actual_leverage = position_value / initial_margin
                            print(f"      🔧 LEVERAGE ANALYSIS:")
                            print(f"         Position Value: ${position_value:.2f}")
                            print(f"         Margin Used: ${initial_margin:.2f}")
                            print(f"         Actual Leverage: {actual_leverage:.2f}x")
                            
                            # Compare with expected configuration
                            if configured_margin == 10 and configured_leverage == 3:
                                expected_position_value = 10 * 3  # 30 USDT
                                print(f"         Expected Position Value: ${expected_position_value:.2f}")
                                print(f"         Position Value Difference: ${abs(position_value - expected_position_value):.2f}")
            else:
                print(f"   ℹ️ No active positions found on common MACD symbols")
                
    except Exception as e:
        print(f"❌ Error checking Binance positions: {e}")

    # Analyze potential causes
    print(f"\n🔧 STEP 4: POTENTIAL CAUSES ANALYSIS")
    print(f"Based on order manager logic, here are potential causes for the discrepancy:")
    
    print(f"\n🎯 POSSIBLE CAUSE 1: MINIMUM QUANTITY ADJUSTMENT")
    print(f"   • Order manager enforces Binance minimum quantity requirements")
    print(f"   • If calculated quantity < minimum, it uses minimum quantity")
    print(f"   • This increases margin beyond configured amount")
    
    print(f"\n🎯 POSSIBLE CAUSE 2: SYMBOL PRECISION ROUNDING")
    print(f"   • Quantities are rounded to meet symbol step size requirements")
    print(f"   • Rounding up increases the actual position value and margin")
    
    print(f"\n🎯 POSSIBLE CAUSE 3: PRICE MOVEMENT DURING ORDER")
    print(f"   • Market orders execute at current market price")
    print(f"   • If price moved between calculation and execution, margin changes")
    
    print(f"\n🎯 POSSIBLE CAUSE 4: CONFIGURATION MISMATCH")
    print(f"   • Web dashboard config might differ from expected values")
    print(f"   • Multiple config sources could cause inconsistency")
    
    print(f"\n🎯 POSSIBLE CAUSE 5: LEVERAGE SETTING FAILURE")
    print(f"   • If leverage setting failed, Binance might use account default")
    print(f"   • Lower actual leverage = higher margin requirement")

    # Recommendation for further investigation
    print(f"\n📋 STEP 5: RECOMMENDATIONS FOR FURTHER INVESTIGATION")
    print(f"To get complete information about the deployed bot's recent trade:")
    
    print(f"\n1. 🌐 CHECK RENDER DEPLOYMENT LOGS:")
    print(f"   • Look for margin calculation logs during trade execution")
    print(f"   • Search for '🔧 MARGIN CALCULATION RESULTS' messages")
    
    print(f"\n2. 📊 CHECK BINANCE API DIRECTLY:")
    print(f"   • Use Binance API to get recent trade history")
    print(f"   • Check actual order execution details")
    
    print(f"\n3. 🔍 MONITOR NEXT TRADE:")
    print(f"   • Enable debug logging for margin calculations")
    print(f"   • Watch the calculation process in real-time")
    
    print(f"\n4. 🧪 SIMULATE THE CALCULATION:")
    print(f"   • Use current market data to simulate the calculation")
    print(f"   • Check if minimum quantity rules cause the issue")

    return True

def simulate_margin_calculation():
    """Simulate margin calculation with current market data"""
    print(f"\n🧪 BONUS: SIMULATING MARGIN CALCULATION")
    print("=" * 50)
    
    try:
        binance_client = BinanceClientWrapper()
        macd_config = trading_config_manager.get_strategy_config('macd_divergence', {})
        
        symbol = macd_config.get('symbol', 'BTCUSDT')
        margin = macd_config.get('margin', 10)
        leverage = macd_config.get('leverage', 3)
        
        # Get current price
        ticker = binance_client.get_symbol_ticker(symbol)
        if not ticker:
            print(f"❌ Could not fetch current price for {symbol}")
            return
            
        current_price = float(ticker['price'])
        
        print(f"📊 SIMULATION PARAMETERS:")
        print(f"   Symbol: {symbol}")
        print(f"   Current Price: ${current_price:.4f}")
        print(f"   Configured Margin: ${margin} USDT")
        print(f"   Configured Leverage: {leverage}x")
        
        # Calculate ideal quantity
        target_position_value = margin * leverage
        ideal_quantity = target_position_value / current_price
        
        print(f"\n🔧 IDEAL CALCULATION:")
        print(f"   Target Position Value: ${target_position_value:.2f} USDT")
        print(f"   Ideal Quantity: {ideal_quantity:.6f}")
        
        # Get symbol info for minimum requirements
        try:
            if binance_client.is_futures:
                exchange_info = binance_client.client.futures_exchange_info()
            else:
                exchange_info = binance_client.client.get_exchange_info()
            
            symbol_info = None
            for s in exchange_info['symbols']:
                if s['symbol'] == symbol:
                    symbol_info = s
                    break
            
            if symbol_info:
                filters = {f['filterType']: f for f in symbol_info.get('filters', [])}
                lot_size = filters.get('LOT_SIZE', {})
                min_qty = float(lot_size.get('minQty', 0.1))
                step_size = float(lot_size.get('stepSize', 0.1))
                
                # Calculate precision
                precision = len(str(step_size).rstrip('0').split('.')[-1]) if '.' in str(step_size) else 0
                
                print(f"\n📋 SYMBOL REQUIREMENTS:")
                print(f"   Minimum Quantity: {min_qty}")
                print(f"   Step Size: {step_size}")
                print(f"   Precision: {precision}")
                
                # Apply rounding and minimum quantity
                quantity = round(ideal_quantity / step_size) * step_size
                quantity = round(quantity, precision)
                
                if quantity < min_qty:
                    quantity = min_qty
                    print(f"   ⚠️ Quantity adjusted to minimum: {quantity}")
                
                # Calculate actual values
                actual_position_value = quantity * current_price
                actual_margin_used = actual_position_value / leverage
                
                print(f"\n💰 ACTUAL CALCULATION AFTER ADJUSTMENTS:")
                print(f"   Final Quantity: {quantity}")
                print(f"   Actual Position Value: ${actual_position_value:.2f} USDT")
                print(f"   Actual Margin Used: ${actual_margin_used:.2f} USDT")
                print(f"   Margin Difference: ${actual_margin_used - margin:+.2f} USDT")
                
                # Check if this explains the 39 USDT margin
                if abs(actual_margin_used - 39) < 5:
                    print(f"   🚨 THIS SIMULATION PRODUCES SIMILAR MARGIN TO YOUR ISSUE!")
                    print(f"   🔍 The discrepancy is likely due to minimum quantity requirements")
                
        except Exception as e:
            print(f"❌ Error getting symbol info: {e}")
            
    except Exception as e:
        print(f"❌ Error in simulation: {e}")

def main():
    print("🔍 MACD STRATEGY MARGIN DISCREPANCY INVESTIGATION")
    print("=" * 80)
    print("This script will investigate why your MACD strategy used 39 USDT margin")
    print("instead of the expected amount based on 10 USDT margin with 3x leverage.")
    print("=" * 80)
    
    try:
        success = investigate_macd_margin_discrepancy()
        if success:
            simulate_margin_calculation()
        
        print(f"\n✅ INVESTIGATION COMPLETED")
        print(f"Check the analysis above to understand the potential causes.")
        print(f"Since your bot is deployed on Render, the most complete information")
        print(f"will be in your Render deployment logs during trade execution.")
        
    except Exception as e:
        print(f"❌ Investigation failed: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    main()
