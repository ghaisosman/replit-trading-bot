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

        # Get balance
        if IMPORTS_AVAILABLE:
            balance = balance_fetcher.get_usdt_balance() or 0
            strategies = trading_config_manager.strategy_overrides
        else:
            balance = 100.0  # Default for demo
            strategies = {
                'rsi_oversold': {'symbol': 'SOLUSDT', 'margin': 12.5, 'leverage': 25, 'timeframe': '15m'},
                'macd_divergence': {'symbol': 'BTCUSDT', 'margin': 23.0, 'leverage': 5, 'timeframe': '5m'}
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
    """Get all strategy configurations"""
    try:
        if IMPORTS_AVAILABLE:
            strategies = {}
            for name, overrides in trading_config_manager.strategy_overrides.items():
                base_config = {
                    **trading_config_manager.default_params.to_dict(),
                    **overrides
                }

                # Ensure assessment_interval is included
                if 'assessment_interval' not in base_config:
                    base_config['assessment_interval'] = 300

                # Add strategy-specific parameters from config files
                try:
                    if 'rsi' in name.lower():
                        from src.execution_engine.strategies.rsi_oversold_config import RSIOversoldConfig
                        rsi_config = RSIOversoldConfig.get_config()
                        base_config.update({
                            'max_loss_pct': rsi_config.get('max_loss_pct', 10),
                            'rsi_long_entry': rsi_config.get('rsi_long_entry', 40),
                            'rsi_long_exit': rsi_config.get('rsi_long_exit', 70),
                            'rsi_short_entry': rsi_config.get('rsi_short_entry', 60),
                            'rsi_short_exit': rsi_config.get('rsi_short_exit', 30)
                        })
                    elif 'macd' in name.lower():
                        from src.execution_engine.strategies.macd_divergence_config import MACDDivergenceConfig
                        macd_config = MACDDivergenceConfig.get_config()
                        base_config.update({
                            'max_loss_pct': macd_config.get('max_loss_pct', 10),
                            'macd_fast': macd_config.get('macd_fast', 12),
                            'macd_slow': macd_config.get('macd_slow', 26),
                            'macd_signal': macd_config.get('macd_signal', 9),
                            'min_histogram_threshold': macd_config.get('min_histogram_threshold', 0.0001),
                            'min_distance_threshold': macd_config.get('min_distance_threshold', 0.005),
                            'confirmation_candles': macd_config.get('confirmation_candles', 2)
                        })
                except ImportError as e:
                    logger.warning(f"Could not import strategy config for {name}: {e}")

                strategies[name] = base_config
            return jsonify(strategies)
        else:
            # Return default strategies for demo with strategy-specific parameters
            return jsonify({
                'rsi_oversold': {
                    'symbol': 'SOLUSDT', 'margin': 12.5, 'leverage': 25, 'timeframe': '15m',
                    'max_loss_pct': 10, 'rsi_long_entry': 40, 'rsi_long_exit': 70,
                    'rsi_short_entry': 60, 'rsi_short_exit': 30, 'assessment_interval': 300
                },
                'macd_divergence': {
                    'symbol': 'BTCUSDT', 'margin': 23.0, 'leverage': 5, 'timeframe': '5m',
                    'max_loss_pct': 10, 'macd_fast': 12, 'macd_slow': 26, 'macd_signal': 9,
                    'min_histogram_threshold': 0.0001, 'min_distance_threshold': 0.005, 'confirmation_candles': 2,
                    'assessment_interval': 300
                }
            })
    except Exception as e:
        logger.error(f"Error in get_strategies endpoint: {e}")
        return jsonify({'error': str(e), 'strategies': {}}), 200

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

        # Update strategy parameters in config manager (basic params only)
        basic_params = {k: v for k, v in data.items() if k in ['symbol', 'margin', 'leverage', 'timeframe', 'assessment_interval']}
        if basic_params:
            trading_config_manager.update_strategy_params(strategy_name, basic_params)

        # Update strategy-specific config files safely
        try:
            if 'rsi' in strategy_name.lower():
                from src.execution_engine.strategies.rsi_oversold_config import RSIOversoldConfig
                rsi_updates = {k: v for k, v in data.items() if k.startswith('rsi_') or k == 'max_loss_pct'}
                if rsi_updates:
                    logger.info(f"📝 WEB INTERFACE: Updating RSI strategy config: {rsi_updates}")
                    # Save to config file
                    RSIOversoldConfig.update_config(rsi_updates)

            elif 'macd' in strategy_name.lower():
                from src.execution_engine.strategies.macd_divergence_config import MACDDivergenceConfig
                macd_updates = {k: v for k, v in data.items() if k.startswith('macd_') or k.startswith('min_') or k in ['confirmation_candles', 'max_loss_pct']}
                if macd_updates:
                    logger.info(f"📝 WEB INTERFACE: Updating MACD strategy config: {macd_updates}")
                    # Save to config file
                    MACDDivergenceConfig.update_config(macd_updates)

        except ImportError as e:
            logger.warning(f"Could not update strategy-specific config for {strategy_name}: {e}")
        except Exception as e:
            logger.error(f"Error updating strategy config file for {strategy_name}: {e}")

        # Always try to get the latest shared bot manager
        shared_bot_manager = getattr(sys.modules.get('__main__', None), 'bot_manager', None)

        # Update running bot configuration if available
        bot_updated = False

        # Check shared bot manager first
        if shared_bot_manager and hasattr(shared_bot_manager, 'strategies') and strategy_name in shared_bot_manager.strategies:
            shared_bot_manager.strategies[strategy_name].update(data)
            logger.info(f"📝 WEB INTERFACE: Updated {strategy_name} config in shared bot: {data}")
            bot_updated = True

        # Fallback to standalone bot
        elif bot_manager and hasattr(bot_manager, 'strategies') and strategy_name in bot_manager.strategies:
            bot_manager.strategies[strategy_name].update(data)
            logger.info(f"📝 WEB INTERFACE: Updated {strategy_name} config in standalone bot: {data}")
            bot_updated = True

        message = f'Strategy {strategy_name} updated successfully'
        if bot_updated:
            message += ' (applied to running bot immediately)'
        else:
            message += ' (will apply after restart)'

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
                "No log file found - logs will appear here when bot runs",
                f"Last checked: {datetime.now().strftime('%H:%M:%S')}"
            ]
        
        return jsonify({'logs': logs})
    except Exception as e:
        return jsonify({'logs': [f'Error loading logs: {str(e)}']})

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
    """Fetch and return open positions from the positions.json file."""
    try:
        # Construct the absolute path to the positions.json file
        script_dir = os.path.dirname(os.path.abspath(__file__))
        positions_file_path = os.path.join(script_dir, 'trading_data', 'positions.json')

        # Check if the positions.json file exists
        if not os.path.exists(positions_file_path):
            return jsonify({'error': 'positions.json file not found'}), 404

        # Read position data from the positions.json file
        with open(positions_file_path, 'r') as file:
            positions_data = json.load(file)

        # Check if positions_data is a list; if not, return an error
        if not isinstance(positions_data, list):
            return jsonify({'error': 'positions.json data is not a list'}), 500

        positions = []
        for pos in positions_data:
            # Extract relevant information from each position
            symbol = pos.get('symbol', 'N/A')
            position_amt = float(pos.get('positionAmt', 0))

            # Filter out positions with insignificant amounts
            if abs(position_amt) > 0.001:
                unrealized_pnl_usdt = float(pos.get('unRealizedPnl', 0))
                entry_price = float(pos.get('entryPrice', 0))
                liquidation_price = float(pos.get('liquidationPrice', 0))
                leverage = int(float(pos.get('leverage', 1)))

                # Determine the side based on the position amount
                side = 'BUY' if position_amt > 0 else 'SELL'

                # Append position data to the list
                positions.append({
                    'symbol': symbol,
                    'side': side,
                    'entryPrice': entry_price,
                    'unrealizedPnl': unrealized_pnl_usdt,
                    'liquidationPrice': liquidation_price,
                    'leverage': leverage,
                    'positionAmt': position_amt
                })

        # Log success
        logger.info(f"Successfully processed {len(positions)} positions from positions.json")

        # Return the structured position data
        return jsonify(positions), 200

    except FileNotFoundError:
        logger.error("positions.json file not found")
        return jsonify({'error': 'positions.json file not found'}), 404
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode positions.json: {e}")
        return jsonify({'error': 'Failed to decode positions.json'}), 500
    except Exception as e:
        logger.exception("An unexpected error occurred")
        return jsonify({'error': str(e)}), 500

@app.route('/api/health')
def health_check():
    """Simple health check endpoint"""
    return jsonify({
        'status': 'ok',
        'service': 'Trading Bot Web Dashboard',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0'
    })

@app.route('/api/clear-orphan/<strategy_name>', methods=['POST'])
def clear_orphan_trade(strategy_name):
    """Clear orphan trade for a specific strategy"""
    try:
        current_bot = shared_bot_manager if shared_bot_manager else bot_manager
        
        if not current_bot:
            return jsonify({'success': False, 'error': 'Bot not available'})
        
        # Clear the orphan position from order manager
        if hasattr(current_bot, 'order_manager') and current_bot.order_manager:
            current_bot.order_manager.clear_orphan_position(strategy_name)
            logger.info(f"🌐 WEB INTERFACE: Manually cleared orphan trade for {strategy_name}")
            
            # Also clear from anomaly detector if available
            if hasattr(current_bot, 'anomaly_detector'):
                anomaly_id = f"orphan_{strategy_name}_SOLUSDT"  # Assuming SOLUSDT for now
                current_bot.anomaly_detector.clear_anomaly_by_id(anomaly_id, "Manual clear via web interface")
            
            return jsonify({'success': True, 'message': f'Orphan trade cleared for {strategy_name}'})
        else:
            return jsonify({'success': False, 'error': 'Order manager not available'})
            
    except Exception as e:
        logger.error(f"Error clearing orphan trade: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/ml_insights')
def get_ml_insights():
    """Get ML insights"""
    try:
        # Mock data for ML insights
        insights = {
            'prediction_accuracy': 78.5,
            'next_signal': 'BUY SOLUSDT',
            'confidence': 85.2,
            'model_status': 'active'
        }
        return jsonify({'success': True, 'insights': insights})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.errorhandler(404)
def handle_404(e):
    """Handle 404 errors gracefully"""
    # For API endpoints, return JSON
    if request.path.startswith('/api/'):
        return jsonify({
            'success': False,
            'error': 'API endpoint not found',
            'message': f'The requested API endpoint {request.path} is not available',
            'available_endpoints': [
                '/api/bot/status',
                '/api/bot/start', 
                '/api/bot/stop',
                '/api/console-log',
                '/api/strategies',
                '/api/positions',
                '/api/balance'
            ]
        }), 404
    
    # For regular routes, redirect to dashboard
    return redirect(url_for('dashboard'))

@app.errorhandler(500)
def handle_500(e):
    """Handle 500 errors gracefully"""
    return jsonify({
        'success': False,
        'error': 'Internal server error',
        'message': 'An error occurred while processing your request'
    }), 500

if __name__ == '__main__':
    logger.warning("🌐 WEB DASHBOARD: This module is designed to be imported by main.py")
    logger.info("💡 Please run 'python main.py' instead - it includes the web dashboard")
    print("⚠️  web_dashboard.py should not be run directly")
    print("💡 Run 'python main.py' instead - it includes the web dashboard")

@app.route('/api/strategy/update', methods=['POST'])
def update_strategy_config():
    try:
        data = request.get_json()
        strategy_name = data.get('strategy_name')
        updates = data.get('updates', {})

        if not strategy_name or not updates:
            return jsonify({'success': False, 'error': 'Missing strategy name or updates'})

        # Log the incoming update request
        print(f"🔧 WEB DASHBOARD UPDATE REQUEST | Strategy: {strategy_name} | Updates: {updates}")

        current_bot = shared_bot_manager if shared_bot_manager else bot_manager

        if current_bot and hasattr(current_bot, 'strategies'):
            # Apply the updates to the strategy in the bot
            if strategy_name in current_bot.strategies:
                current_bot.strategies[strategy_name].update(updates)

                # Log the successful update
                logger.info(f"📝 WEB INTERFACE: Updated {strategy_name} config in bot: {updates}")

                # Verify the updates were applied (optional)
                updated_config = current_bot.strategies[strategy_name]
                logger.debug(f"📊 Current Config for {strategy_name}: {updated_config}")

                return jsonify({
                    'success': True,
                    'message': f'Strategy {strategy_name} updated successfully',
                    'current_config': updated_config  # Include for verification
                })
            else:
                return jsonify({'success': False, 'error': f'Strategy {strategy_name} not found in bot'})
        else:
            return jsonify({'success': False, 'error': 'Bot not running or strategies not available'})

    except Exception as e:
        logger.error(f"❌ WEB DASHBOARD UPDATE ERROR | {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

# This section was causing duplicate Flask instances - removed to prevent port conflicts
# The web dashboard should only run when imported by main.py