#!/usr/bin/env python3
"""
Trading Bot Web Dashboard
Complete web interface for managing the trading bot
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_cors import CORS
import json
import asyncio
import threading
import os
from datetime import datetime, timedelta
from pathlib import Path
import logging
from typing import Dict, Any

# Define trades directory path
trades_dir = Path("trading_data/trades")

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Enable CORS for web dashboard
CORS(app)

# Suppress Flask's default request logging to reduce console noise
import logging as flask_logging
werkzeug_logger = flask_logging.getLogger('werkzeug')
werkzeug_logger.setLevel(flask_logging.WARNING)

# Setup logging for web dashboard
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global bot instance - shared with main.py
bot_manager = None
bot_thread = None
bot_running = False

# Import the shared bot manager from main.py if it exists
import sys
shared_bot_manager = None

# Try to safely import required modules
try:
    from src.config.trading_config import trading_config_manager
    from src.config.global_config import global_config
    from src.binance_client.client import BinanceClientWrapper
    from src.data_fetcher.price_fetcher import PriceFetcher
    from src.data_fetcher.balance_fetcher import BalanceFetcher
    from src.bot_manager import BotManager
    from src.utils.logger import setup_logger

    # Setup proper logging
    setup_logger()
    logger = logging.getLogger(__name__)

    if hasattr(sys.modules.get('__main__', None), 'bot_manager'):
        shared_bot_manager = sys.modules['__main__'].bot_manager

    # Initialize clients for web interface
    binance_client = BinanceClientWrapper()
    price_fetcher = PriceFetcher(binance_client)
    balance_fetcher = BalanceFetcher(binance_client)

    IMPORTS_AVAILABLE = True
    logger.info("✅ All imports successful - Full functionality available")

except ImportError as e:
    logger.warning(f"⚠️ Import error - Limited functionality: {e}")
    IMPORTS_AVAILABLE = False

    # Create dummy objects for basic web interface
    class DummyConfigManager:
        strategy_overrides = {
            'rsi_oversold': {'symbol': 'SOLUSDT', 'margin': 12.5, 'leverage': 25, 'timeframe': '15m'},
            'macd_divergence': {'symbol': 'BTCUSDT', 'margin': 23.0, 'leverage': 5, 'timeframe': '5m'}
        }

    class DummyBalanceFetcher:
        def get_usdt_balance(self):
            return 100.0

    trading_config_manager = DummyConfigManager()
    balance_fetcher = DummyBalanceFetcher()

@app.route('/')
def dashboard():
    """Main dashboard page"""
    try:
        # Get current bot status
        status = get_bot_status()

        # Get balance and strategies
        if IMPORTS_AVAILABLE:
            balance = balance_fetcher.get_usdt_balance() or 0
            strategies = trading_config_manager.get_all_strategies()
            
            # Ensure we always have both strategies available for display
            if 'rsi_oversold' not in strategies:
                strategies['rsi_oversold'] = {
                    'symbol': 'SOLUSDT', 'margin': 12.5, 'leverage': 25, 'timeframe': '15m',
                    'max_loss_pct': 5, 'assessment_interval': 20
                }
            if 'macd_divergence' not in strategies:
                strategies['macd_divergence'] = {
                    'symbol': 'BTCUSDT', 'margin': 50.0, 'leverage': 5, 'timeframe': '15m',
                    'max_loss_pct': 10, 'assessment_interval': 60
                }
        else:
            balance = 100.0  # Default for demo
            strategies = {
                'rsi_oversold': {'symbol': 'SOLUSDT', 'margin': 12.5, 'leverage': 25, 'timeframe': '15m'},
                'macd_divergence': {'symbol': 'BTCUSDT', 'margin': 50.0, 'leverage': 5, 'timeframe': '15m'}
            }

        # Get active positions from both shared and standalone bot
        active_positions = []
        current_bot = shared_bot_manager if shared_bot_manager else bot_manager

        if current_bot and hasattr(current_bot, 'order_manager') and current_bot.order_manager:
            for strategy_name, position in current_bot.order_manager.active_positions.items():
                current_price = get_current_price(position.symbol)
                pnl = calculate_pnl(position, current_price) if current_price else 0

                # Calculate position value and get actual margin invested
                position_value = position.entry_price * position.quantity

                # Get leverage and margin from strategy config  
                strategy_config = current_bot.strategies.get(strategy_name, {}) if hasattr(current_bot, 'strategies') else {}
                leverage = strategy_config.get('leverage', 5)  # Default 5x leverage

                # Use the configured margin as the actual margin invested (matches trading logic)
                margin_invested = strategy_config.get('margin', 50.0)

                # Calculate PnL percentage against margin invested (correct for futures)
                pnl_percent = (pnl / margin_invested) * 100 if margin_invested > 0 else 0

                active_positions.append({
                    'strategy': strategy_name,
                    'symbol': position.symbol,
                    'side': position.side,
                    'entry_price': position.entry_price,
                    'quantity': position.quantity,
                    'position_value_usdt': position_value,  # Add position value in USDT
                    'margin_invested': margin_invested,     # Add margin invested
                    'current_price': current_price,
                    'pnl': pnl,
                    'pnl_percent': pnl_percent
                })

        return render_template('dashboard.html', 
                             status=status,
                             balance=balance,
                             strategies=strategies,
                             active_positions=active_positions)
    except Exception as e:
        return f"Error loading dashboard: {e}"

@app.route('/api/bot/start', methods=['POST'])
def start_bot():
    """Start the trading bot"""
    global bot_manager, bot_thread, bot_running, shared_bot_manager

    try:
        logger = logging.getLogger(__name__)

        # Always try to get the latest shared bot manager
        shared_bot_manager = getattr(sys.modules.get('__main__', None), 'bot_manager', None)

        # Check if there's a shared bot manager from main.py
        if shared_bot_manager and hasattr(shared_bot_manager, 'is_running'):
            if shared_bot_manager.is_running:
                return jsonify({'success': False, 'message': 'Bot is already running in console'})

            # Use the shared bot manager and start it
            bot_manager = shared_bot_manager

            # Log the web start action to console
            logger.info("🌐 WEB INTERFACE: Starting bot via web dashboard")

            # Also log to bot manager's logger if available
            if hasattr(shared_bot_manager, 'logger'):
                shared_bot_manager.logger.info("🌐 WEB INTERFACE: Bot started via web dashboard")

            # Start the shared bot in the main event loop
            def start_shared_bot():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    # FORCE reset startup notification flag for restart
                    shared_bot_manager.startup_notified = False

                    # Set running state
                    shared_bot_manager.is_running = True
                    logger.info("🚀 BOT RESTARTED VIA WEB INTERFACE")

                    # Force debug logging for notification state
                    logger.info(f"🔍 DEBUG: startup_notified reset to: {shared_bot_manager.startup_notified}")

                    # Start the bot's start method (this will handle startup notifications properly)
                    loop.run_until_complete(shared_bot_manager.start())
                except Exception as e:
                    logger.error(f"Bot error during restart: {e}")
                    # Send error notification
                    try:
                        shared_bot_manager.telegram_reporter.report_bot_stopped(f"Restart failed: {str(e)}")
                    except:
                        pass
                finally:
                    shared_bot_manager.is_running = False
                    logger.info("🔴 BOT STOPPED - Web interface remains active")
                    loop.close()

            bot_thread = threading.Thread(target=start_shared_bot, daemon=True)
            bot_thread.start()
            bot_running = True

            return jsonify({'success': True, 'message': 'Bot restarted successfully from web interface'})

        # Fallback: create new bot instance if no shared manager exists
        if bot_running:
            return jsonify({'success': False, 'message': 'Bot is already running'})

        logger.info("🌐 WEB INTERFACE: Creating new bot instance via web dashboard")

        # Create fresh bot manager instance
        bot_manager = BotManager()

        # Update the global reference
        sys.modules['__main__'].bot_manager = bot_manager

        bot_running = True

        # Start bot in separate thread
        def run_bot():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            logger = logging.getLogger(__name__)
            try:
                logger.info("🚀 STARTING NEW BOT INSTANCE FROM WEB INTERFACE")
                loop.run_until_complete(bot_manager.start())
            except Exception as e:
                logger.error(f"Bot error: {e}")
                # Send error notification
                try:
                    bot_manager.telegram_reporter.report_bot_stopped(f"Startup failed: {str(e)}")
                except:
                    pass
            finally:
                global bot_running
                bot_running = False
                logger.info("🔴 BOT STOPPED - Web interface remains active")
                loop.close()

        bot_thread = threading.Thread(target=run_bot, daemon=True)
        bot_thread.start()

        return jsonify({'success': True, 'message': 'New bot instance started successfully'})

    except Exception as e:
        bot_running = False
        logger.error(f"Failed to start bot: {e}")
        return jsonify({'success': False, 'message': f'Failed to start bot: {e}'})

@app.route('/api/bot/stop', methods=['POST'])
def stop_bot():
    """Stop the trading bot while keeping web interface active"""
    global bot_manager, bot_running, shared_bot_manager

    try:
        logger = logging.getLogger(__name__)

        # Always try to get the latest shared bot manager
        shared_bot_manager = getattr(sys.modules.get('__main__', None), 'bot_manager', None)

        # Check if there's a shared bot manager from main.py
        if shared_bot_manager and hasattr(shared_bot_manager, 'is_running'):
            if shared_bot_manager.is_running:
                logger.info("🌐 WEB INTERFACE: Stopping bot via web dashboard (web interface will remain active)")

                # Also log to bot manager's logger if available
                if hasattr(shared_bot_manager, 'logger'):
                    shared_bot_manager.logger.info("🌐 WEB INTERFACE: Bot stopped via web dashboard")

                # Stop the shared bot by setting is_running to False
                shared_bot_manager.is_running = False

                # Send stop notification
                try:
                    shared_bot_manager.telegram_reporter.report_bot_stopped("Manual stop via web interface")
                    logger.info("🔴 BOT STOPPED VIA WEB INTERFACE (Dashboard remains active)")
                except Exception as e:
                    logger.warning(f"Failed to send stop notification: {e}")

                bot_running = False

                # Important: Don't terminate the process, just stop the bot
                logger.info("💡 Web interface remains active - you can restart the bot anytime")

                return jsonify({
                    'success': True, 
                    'message': 'Bot stopped successfully. Web interface remains active for restart.'
                })
            else:
                return jsonify({'success': False, 'message': 'Bot is not running in console'})

        # Fallback to standalone bot
        if not bot_running or not bot_manager:
            return jsonify({'success': False, 'message': 'Bot is not running'})

        logger.info("🌐 WEB INTERFACE: Stopping standalone bot via web dashboard (web interface will remain active)")

        # Stop the bot gracefully
        if hasattr(bot_manager, 'is_running'):
            bot_manager.is_running = False

        bot_running = False

        # Send stop notification for standalone bot
        try:
            bot_manager.telegram_reporter.report_bot_stopped("Manual stop via web interface")
            logger.info("🔴 STANDALONE BOT STOPPED VIA WEB INTERFACE (Dashboard remains active)")
        except Exception as e:
            logger.warning(f"Failed to send stop notification: {e}")

        logger.info("💡 Web interface remains active - you can restart the bot anytime")

        return jsonify({
            'success': True, 
            'message': 'Bot stopped successfully. Web interface remains active for restart.'
        })

    except Exception as e:
        logger.error(f"Error stopping bot: {e}")
        return jsonify({'success': False, 'message': f'Failed to stop bot: {e}'})

@app.route('/api/bot/status')
def get_bot_status():
    """Get bot status"""
    try:
        # Get bot manager from main module
        import sys
        main_module = sys.modules.get('__main__')
        bot_manager = getattr(main_module, 'bot_manager', None) if main_module else None

        if not bot_manager:
            return jsonify({
                'status': 'stopped',
                'message': 'Bot manager not initialized',
                'strategies': 0,
                'active_positions': 0,
                'running': False
            })

        is_running = getattr(bot_manager, 'is_running', False)
        strategies_count = len(getattr(bot_manager, 'strategies', {}))

        # Safe access to order manager
        active_positions = 0
        if hasattr(bot_manager, 'order_manager') and bot_manager.order_manager:
            try:
                active_positions = len(bot_manager.order_manager.get_active_positions())
            except:
                active_positions = 0

        return jsonify({
            'status': 'running' if is_running else 'stopped',
            'strategies': strategies_count,
            'active_positions': active_positions,
            'running': is_running
        })
    except Exception as e:
        logger.error(f"Error in get_bot_status: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Status error: {str(e)}',
            'strategies': 0,
            'active_positions': 0,
            'running': False
        }), 500

@app.route('/api/strategies')
def get_strategies():
    """Get all strategy configurations - WEB DASHBOARD IS SINGLE SOURCE OF TRUTH"""
    try:
        if IMPORTS_AVAILABLE:
            # Get all strategies from web dashboard configuration manager
            strategies = trading_config_manager.get_all_strategies()

            # Ensure all required parameters are present for each strategy
            for name, config in strategies.items():
                # Ensure assessment_interval is included
                if 'assessment_interval' not in config:
                    config['assessment_interval'] = 60 if 'rsi' in name.lower() else 30

                # Ensure all required parameters exist with defaults
                if 'max_loss_pct' not in config:
                    config['max_loss_pct'] = 10

                # RSI strategy defaults
                if 'rsi' in name.lower():
                    config.setdefault('rsi_long_entry', 40)
                    config.setdefault('rsi_long_exit', 70)
                    config.setdefault('rsi_short_entry', 60)
                    config.setdefault('rsi_short_exit', 30)

                # MACD strategy defaults
                elif 'macd' in name.lower():
                    config.setdefault('macd_fast', 12)
                    config.setdefault('macd_slow', 26)
                    config.setdefault('macd_signal', 9)
                    config.setdefault('min_histogram_threshold', 0.0001)
                    config.setdefault('min_distance_threshold', 0.005)
                    config.setdefault('confirmation_candles', 2)

            logger.info(f"🌐 WEB DASHBOARD: Serving configurations for {len(strategies)} strategies")
            return jsonify(strategies)
        else:
            # Return default strategies for demo
            return jsonify({
                'rsi_oversold': {
                    'symbol': 'BTCUSDT', 'margin': 50.0, 'leverage': 5, 'timeframe': '15m',
                    'max_loss_pct': 10, 'rsi_long_entry': 40, 'rsi_long_exit': 70,
                    'rsi_short_entry': 60, 'rsi_short_exit': 30, 'assessment_interval': 60
                },
                'macd_divergence': {
                    'symbol': 'BTCUSDT', 'margin': 50.0, 'leverage': 5, 'timeframe': '15m',
                    'max_loss_pct': 10, 'macd_fast': 12, 'macd_slow': 26, 'macd_signal': 9,
                    'min_histogram_threshold': 0.0001, 'min_distance_threshold': 0.005, 'confirmation_candles': 2,
                    'assessment_interval': 60
                }
            })
    except Exception as e:
        logger.error(f"Error in get_strategies endpoint: {e}")
        return jsonify({'error': str(e), 'strategies': {}}), 500

@app.route('/api/strategies/<strategy_name>', methods=['POST'])
def update_strategy(strategy_name):
    """Update strategy configuration"""
    try:
        data = request.get_json()

        # Validate data to prevent errors
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'})

        # Basic parameter validation
        try:
            if 'margin' in data:
                data['margin'] = float(data['margin'])
                if data['margin'] <= 0:
                    return jsonify({'success': False, 'message': 'Margin must be positive'})

            if 'leverage' in data:
                data['leverage'] = int(data['leverage'])
                if data['leverage'] <= 0 or data['leverage'] > 125:
                    return jsonify({'success': False, 'message': 'Leverage must be between 1 and 125'})

            if 'assessment_interval' in data:
                data['assessment_interval'] = int(data['assessment_interval'])
                if data['assessment_interval'] < 5 or data['assessment_interval'] > 300:
                    return jsonify({'success': False, 'message': 'Assessment interval must be between 5 and 300 seconds'})

            if 'cooldown_period' in data:
                data['cooldown_period'] = int(data['cooldown_period'])
                if data['cooldown_period'] < 30 or data['cooldown_period'] > 3600:
                    return jsonify({'success': False, 'message': 'Cooldown period must be between 30 and 3600 seconds'})

            # Validate RSI parameters
            if 'rsi_long_entry' in data:
                data['rsi_long_entry'] = int(data['rsi_long_entry'])
                if data['rsi_long_entry'] < 10 or data['rsi_long_entry'] > 50:
                    return jsonify({'success': False, 'message': 'RSI Long Entry must be between 10 and 50'})

            if 'rsi_short_entry' in data:
                data['rsi_short_entry'] = int(data['rsi_short_entry'])
                if data['rsi_short_entry'] < 50 or data['rsi_short_entry'] > 90:
                    return jsonify({'success': False, 'message': 'RSI Short Entry must be between 50 and 90'})

            # Validate MACD parameters
            if 'macd_fast' in data:
                data['macd_fast'] = int(data['macd_fast'])
                if data['macd_fast'] < 5 or data['macd_fast'] > 20:
                    return jsonify({'success': False, 'message': 'MACD Fast must be between 5 and 20'})

        except ValueError as ve:
            return jsonify({'success': False, 'message': f'Invalid parameter value: {ve}'})

        # WEB DASHBOARD IS SINGLE SOURCE OF TRUTH - Update all parameters
        trading_config_manager.update_strategy_params(strategy_name, data)

        logger.info(f"🎯 WEB DASHBOARD: Setting as SINGLE SOURCE OF TRUTH for {strategy_name}")
        logger.info(f"🔄 UPDATING ALL PARAMETERS: {data}")
        logger.info(f"📁 CONFIG FILES IGNORED - Web dashboard overrides everything")

        # Always try to get the latest shared bot manager
        shared_bot_manager = getattr(sys.modules.get('__main__', None), 'bot_manager', None)

        # FORCE IMMEDIATE UPDATE to running bot configuration (WEB DASHBOARD PRIORITY)
        bot_updated = False

        # Check shared bot manager first - FORCE WEB DASHBOARD SETTINGS
        if shared_bot_manager and hasattr(shared_bot_manager, 'strategies') and strategy_name in shared_bot_manager.strategies:
            # COMPLETE OVERRIDE - Web dashboard is single source of truth
            shared_bot_manager.strategies[strategy_name].update(data)
            logger.info(f"🌐 WEB DASHBOARD OVERRIDE: {strategy_name} config FORCED in shared bot: {data}")
            logger.info(f"🎯 WEB DASHBOARD IS SINGLE SOURCE OF TRUTH - File configs ignored")
            bot_updated = True

        # Fallback to standalone bot - FORCE WEB DASHBOARD SETTINGS
        elif bot_manager and hasattr(bot_manager, 'strategies') and strategy_name in bot_manager.strategies:
            # COMPLETE OVERRIDE - Web dashboard is single source of truth
            bot_manager.strategies[strategy_name].update(data)
            logger.info(f"🌐 WEB DASHBOARD OVERRIDE: {strategy_name} config FORCED in standalone bot: {data}")
            logger.info(f"🎯 WEB DASHBOARD IS SINGLE SOURCE OF TRUTH - File configs ignored")
            bot_updated = True

        message = f'🌐 WEB DASHBOARD: {strategy_name} updated successfully'
        if bot_updated:
            message += ' (LIVE UPDATE - Web dashboard is single source of truth)'
        else:
            message += ' (Will apply on restart - Web dashboard overrides all files)'

        # Log final confirmation
        logger.info(f"✅ WEB DASHBOARD UPDATE COMPLETE | {strategy_name}")
        logger.info(f"🎯 YOUR RSI SHORT ENTRY: {data.get('rsi_short_entry', 'Not set')} (overrides file configs)")

        return jsonify({'success': True, 'message': message})
    except Exception as e:
        logger.error(f"Error updating strategy {strategy_name}: {e}")
        return jsonify({'success': False, 'message': f'Failed to update strategy: {e}'})

@app.route('/api/balance')
def get_balance():
    try:
        balance_file = "trading_data/balance.json"
        if os.path.exists(balance_file):
            with open(balance_file, 'r') as f:
                balance_data = json.load(f)
            return jsonify(balance_data)
        else:
            return jsonify({
                'total_balance': 1000.0,
                'available_balance': 1000.0,
                'used_balance': 0.0,
                'last_updated': datetime.now().isoformat()
            })
    except Exception as e:
        # Return safe fallback data instead of error
        return jsonify({
            'total_balance': 0.0,
            'available_balance': 0.0,
            'used_balance': 0.0,
            'last_updated': datetime.now().isoformat(),
            'error': 'Balance data unavailable'
        }), 200

@app.route('/api/positions')
def get_positions():
    """Get active positions"""
    try:
        positions = []

        # Try shared bot manager first
        current_bot = shared_bot_manager if shared_bot_manager else bot_manager

        if current_bot and hasattr(current_bot, 'order_manager') and current_bot.order_manager:
            active_positions = current_bot.order_manager.active_positions

            for strategy_name, position in active_positions.items():
                # Check if this position has an anomaly (orphan/ghost trade)
                anomaly_status = None
                if hasattr(current_bot, 'anomaly_detector'):
                    anomaly_status = current_bot.anomaly_detector.get_anomaly_status(strategy_name)

                # Get current price
                current_price = price_fetcher.get_current_price(position.symbol)

                # Calculate PnL
                if current_price:
                    entry_price = position.entry_price
                    quantity = position.quantity
                    side = position.side

                    # For futures trading, PnL calculation (matches console calculation)
                    if side == 'BUY':  # Long position
                        pnl = (current_price - entry_price) * quantity
                    else:  # Short position (SELL)
                        pnl = (entry_price - current_price) * quantity

                    # Calculate position value and get actual margin invested
                    position_value_usdt = entry_price * quantity

                    # Get leverage and margin from strategy config (default 5x if not found)
                    strategy_config = current_bot.strategies.get(strategy_name, {}) if hasattr(current_bot, 'strategies') else {}
                    leverage = strategy_config.get('leverage', 5)

                    # Use the configured margin as the actual margin invested (matches trading logic)
                    margin_invested = strategy_config.get('margin', 50.0)

                    # For futures trading, PnL percentage should be calculated against margin invested, not position value
                    pnl_percent = (pnl / margin_invested) * 100 if margin_invested > 0 else 0

                    positions.append({
                        'strategy': position.strategy_name,
                        'symbol': position.symbol,
                        'side': position.side,
                        'entry_price': entry_price,
                        'current_price': current_price,
                        'quantity': quantity,
                        'position_value_usdt': position_value_usdt,
                        'margin_invested': margin_invested,
                        'pnl': pnl,
                        'pnl_percent': pnl_percent,
                        'anomaly_status': anomaly_status  # Add anomaly status
                    })

        return jsonify({'success': True, 'positions': positions})
    except Exception as e:
        logger.error(f"Error in get_positions endpoint: {e}")
        return jsonify({'success': False, 'error': str(e), 'positions': []}), 200

@app.route('/api/rsi/<symbol>')
def get_rsi(symbol):
    """Get RSI value for a symbol"""
    try:
        if not IMPORTS_AVAILABLE:
            return jsonify({'success': False, 'error': 'Binance client not available'})

        # Get more historical data for accurate RSI calculation (same as bot uses)
        klines = binance_client.get_klines(symbol=symbol, interval='15m', limit=100)
        if not klines:
            return jsonify({'success': False, 'error': f'Could not fetch klines for {symbol}'})

        # Convert to closes
        closes = [float(kline[4]) for kline in klines]

        if len(closes) < 50:
            return jsonify({'success': False, 'error': f'Not enough data points for RSI calculation for {symbol}'})

        # Calculate RSI using the same method as the bot
        rsi = calculate_rsi(closes, period=14)

        return jsonify({'success': True, 'rsi': round(rsi, 2)})
    except Exception as e:
        logger.error(f"Error in get_rsi endpoint for {symbol}: {e}")
        return jsonify({'success': False, 'error': f'Failed to calculate RSI: {str(e)}'}), 200

def calculate_rsi(closes, period=14):
    """Calculate RSI (Relative Strength Index) - matches bot's calculation"""
    if len(closes) < period + 1:
        return 50.0  # Default RSI if not enough data

    # Calculate price changes
    deltas = []
    for i in range(1, len(closes)):
        deltas.append(closes[i] - closes[i-1])

    # Separate gains and losses
    gains = []
    losses = []
    for delta in deltas:
        if delta > 0:
            gains.append(delta)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(delta))

    # Use exponential moving average like the bot does
    if len(gains) < period:
        return 50.0

    # Calculate initial averages
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    # Calculate RSI using smoothed averages for remaining periods
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi

@app.route('/api/console-log')
def get_console_log():
    """Get console logs"""
    try:
        # Try to get logs from file
        log_files = ["trading_bot.log", "bot.log", "main.log"]
        logs = []

        for log_file in log_files:
            if os.path.exists(log_file):
                try:
                    with open(log_file, 'r') as f:
                        lines = f.readlines()
                    # Get last 30 lines
                    recent_lines = lines[-30:] if len(lines) > 30 else lines
                    logs.extend([line.strip() for line in recent_lines if line.strip()])
                    break
                except:
                    continue

        if not logs:
            # Get current bot manager
            current_bot = shared_bot_manager if shared_bot_manager else bot_manager
            status = "Running" if current_bot and getattr(current_bot, 'is_running', False) else "Stopped"
            logs = [
                f"Bot Status: {status}",
                "Console log will appear here when bot runs",
                f"Last checked: {datetime.now().strftime('%H:%M:%S')}"
            ]

        return jsonify({'success': True, 'logs': logs})
    except Exception as e:
        logger.error(f"Error in console log endpoint: {e}")
        return jsonify({'success': False, 'logs': [f'Error loading logs: {str(e)}'], 'error': str(e)}), 200

def get_bot_status():
    """Get current bot status with enhanced error handling"""
    global bot_running, bot_manager,shared_bot_manager

    try:
        # Always get fresh reference to shared bot manager
        shared_bot_manager = getattr(sys.modules.get('__main__', None), 'bot_manager', None)

        # Check shared bot manager first
        if shared_bot_manager and hasattr(shared_bot_manager, 'is_running'):
            try:
                status = {
                    'is_running': getattr(shared_bot_manager, 'is_running', False),
                    'active_positions': len(getattr(shared_bot_manager.order_manager, 'active_positions', {})) if hasattr(shared_bot_manager, 'order_manager') else 0,
                    'strategies': list(getattr(shared_bot_manager, 'strategies', {}).keys()) if hasattr(shared_bot_manager, 'strategies') else [],
                    'balance': 0  # Will be updated separately
                }
                return status
            except Exception as e:
                logger.error(f"Error getting shared bot status: {e}")
                return {
                    'is_running': False,
                    'active_positions': 0,
                    'strategies': [],
                    'balance': 0,
                    'error': f'Status error: {str(e)}'
                }

        # Fallback status
        return {
            'is_running': False,
            'active_positions': 0,
            'strategies': [],
            'balance': 0,
            'error': 'Bot manager not available'
        }
    except Exception as e:
        logger.error(f"Error in get_bot_status: {e}")
        return {
            'is_running': False,
            'active_positions': 0,
            'strategies': [],
            'balance': 0,
            'error': f'Critical status error: {str(e)}'
        }
    except Exception as e:
        logger.error(f"Error in get_bot_status: {e}")
        return {
            'is_running': False,
            'active_positions': 0,
            'strategies': [],
            'balance': 0,
            'error': f'Critical status error: {str(e)}'
        }

def get_current_price(symbol):
    """Get current price for a symbol"""
    try:
        if IMPORTS_AVAILABLE:
            return price_fetcher.get_current_price(symbol)
        return None
    except:
        return None

def calculate_pnl(position, current_price):
    """Calculate P&L for a position"""
    if not current_price:
        return 0

    if position.side == 'BUY':  # Long position
        return (current_price - position.entry_price) * position.quantity
    else:  # Short position
        return (position.entry_price - current_price) * position.quantity

@app.route('/api/binance/positions', methods=['GET'])
def get_binance_positions():
    """Get Binance positions data"""
    try:
        if not IMPORTS_AVAILABLE:
            return jsonify({'success': False, 'error': 'Binance client not available'})
        
        # Return basic positions response
        return jsonify({
            'success': True,
            'positions': [],
            'message': 'Binance positions endpoint active'
        })
    except Exception as e:
        logger.error(f"Error in get_binance_positions: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'positions': []
        }), 500

@app.route('/api/trading/environment', methods=['GET'])
def get_trading_environment():
    """Get current trading environment configuration"""
    try:
        if IMPORTS_AVAILABLE:
            return jsonify({
                'success': True,
                'environment': {
                    'is_testnet': global_config.BINANCE_TESTNET,
                    'is_futures': global_config.BINANCE_FUTURES,
                    'api_key_configured': bool(global_config.BINANCE_API_KEY),
                    'secret_key_configured': bool(global_config.BINANCE_SECRET_KEY),
                    'mode': 'FUTURES TESTNET' if global_config.BINANCE_TESTNET else 'FUTURES MAINNET'
                }
            })
        else:
            return jsonify({
                'success': True,
                'environment': {
                    'is_testnet': True,
                    'is_futures': True,
                    'api_key_configured': False,
                    'secret_key_configured': False,
                    'mode': 'DEMO MODE'
                }
            })
    except Exception as e:
        logger.error(f"Error getting trading environment: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/trading/environment', methods=['POST'])
def update_trading_environment():
    """Update trading environment (testnet/mainnet)"""
    try:
        if not IMPORTS_AVAILABLE:
            return jsonify({'success': False, 'message': 'Configuration update not available in demo mode'})
        
        data = request.get_json()
        
        if not data or 'is_testnet' not in data:
            return jsonify({'success': False, 'message': 'Missing is_testnet parameter'})
        
        is_testnet = bool(data['is_testnet'])
        
        # Update the global config in memory
        global_config.BINANCE_TESTNET = is_testnet
        
        # Save to environment configuration file for persistence
        env_config = {
            'BINANCE_TESTNET': str(is_testnet).lower(),
            'BINANCE_FUTURES': str(global_config.BINANCE_FUTURES).lower()
        }
        
        # Write to a config file for persistence across restarts
        config_file = "trading_data/environment_config.json"
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        
        with open(config_file, 'w') as f:
            json.dump(env_config, f, indent=2)
        
        mode = 'FUTURES TESTNET' if is_testnet else 'FUTURES MAINNET'
        
        # Log the environment change
        logger.info(f"🔄 ENVIRONMENT CHANGED: {mode}")
        logger.info(f"🌐 WEB DASHBOARD: Trading environment updated via web interface")
        
        # Check if bot is running and warn about restart requirement
        current_bot = shared_bot_manager if shared_bot_manager else bot_manager
        bot_running = current_bot and getattr(current_bot, 'is_running', False)
        
        message = f'Trading environment updated to {mode}'
        if bot_running:
            message += ' (Bot restart required to apply changes)'
            logger.warning("⚠️ Bot restart required for environment change to take effect")
        
        return jsonify({
            'success': True, 
            'message': message,
            'environment': {
                'is_testnet': is_testnet,
                'is_futures': global_config.BINANCE_FUTURES,
                'mode': mode,
                'restart_required': bot_running
            }
        })
        
    except Exception as e:
        logger.error(f"Error updating trading environment: {e}")
        return jsonify({'success': False, 'message': f'Failed to update environment: {e}'})