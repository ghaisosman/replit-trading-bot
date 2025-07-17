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

def get_current_price(symbol):
    """Get current price for symbol"""
    try:
        if IMPORTS_AVAILABLE and price_fetcher:
            return price_fetcher.get_current_price(symbol)
        return None
    except:
        return None

def calculate_pnl(position, current_price):
    """Calculate PnL for position"""
    if not current_price:
        return 0
    
    try:
        if position.side == 'BUY':
            return (current_price - position.entry_price) * position.quantity
        else:
            return (position.entry_price - current_price) * position.quantity
    except:
        return 0

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
                config.setdefault('enabled', True)
                config.setdefault('symbol', 'BTCUSDT')
                config.setdefault('margin', 50.0)
                config.setdefault('leverage', 5)
                config.setdefault('timeframe', '15m')
                config.setdefault('max_loss_pct', 10.0)
                config.setdefault('assessment_interval', 60)

            return jsonify(strategies)
        else:
            return jsonify({
                'rsi_oversold': {'symbol': 'SOLUSDT', 'margin': 12.5, 'leverage': 25, 'timeframe': '15m'},
                'macd_divergence': {'symbol': 'BTCUSDT', 'margin': 50.0, 'leverage': 5, 'timeframe': '15m'}
            })
    except Exception as e:
        logger.error(f"Error getting strategies: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/strategies/<strategy_name>', methods=['POST'])
def update_strategy(strategy_name):
    """Update strategy configuration - WEB DASHBOARD IS SINGLE SOURCE OF TRUTH"""
    try:
        if not IMPORTS_AVAILABLE:
            return jsonify({'success': False, 'message': 'Trading configuration not available'})

        updates = request.json
        logger.info(f"🌐 WEB INTERFACE: Updating {strategy_name} config: {updates}")

        # Update configuration using web dashboard manager
        trading_config_manager.update_strategy_params(strategy_name, updates)

        # Force update any running bot instance
        try:
            import sys
            main_module = sys.modules.get('__main__')
            bot_manager = getattr(main_module, 'bot_manager', None) if main_module else None
            
            if bot_manager and hasattr(bot_manager, 'strategies') and strategy_name in bot_manager.strategies:
                bot_manager.strategies[strategy_name].update(updates)
                logger.info(f"🌐 WEB INTERFACE: Updated {strategy_name} config in shared bot: {bot_manager.strategies[strategy_name]}")
        except Exception as e:
            logger.warning(f"Could not update running bot: {e}")

        return jsonify({'success': True, 'message': f'Strategy {strategy_name} updated successfully'})

    except Exception as e:
        logger.error(f"Error updating strategy: {e}")
        return jsonify({'success': False, 'message': f'Error updating strategy: {e}'})

@app.route('/api/balance', methods=['GET'])
def get_balance():
    """Get current balance via API"""
    try:
        if IMPORTS_AVAILABLE and balance_fetcher:
            balance = balance_fetcher.get_usdt_balance() or 0
            return jsonify({'balance': balance})
        else:
            return jsonify({'balance': 0})
    except Exception as e:
        logger.error(f"Error getting balance: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/positions', methods=['GET'])
def get_positions():
    """Get active positions"""
    try:
        positions = []
        current_bot = shared_bot_manager if shared_bot_manager else bot_manager

        if current_bot and hasattr(current_bot, 'order_manager') and current_bot.order_manager:
            active_positions = dict(current_bot.order_manager.active_positions)

            for strategy_name, position in active_positions.items():
                anomaly_status = None
                if hasattr(current_bot, 'anomaly_detector'):
                    anomaly_status = current_bot.anomaly_detector.get_anomaly_status(strategy_name)

                current_price = None
                if IMPORTS_AVAILABLE and price_fetcher:
                    current_price = price_fetcher.get_current_price(position.symbol)

                if current_price:
                    entry_price = position.entry_price
                    quantity = position.quantity
                    side = position.side
                    
                    if side == 'BUY':
                        pnl = (current_price - entry_price) * quantity
                    elif side == 'SELL':
                        pnl = (entry_price - current_price) * quantity
                    else:
                        pnl = 0
                else:
                    pnl = 0

                position_value_usdt = position.entry_price * position.quantity
                strategy_config = current_bot.strategies.get(strategy_name, {}) if hasattr(current_bot, 'strategies') else {}
                leverage = strategy_config.get('leverage', 5)
                margin_invested = strategy_config.get('margin', 50.0)
                pnl_percent = (pnl / margin_invested) * 100 if margin_invested > 0 else 0

                positions.append({
                    'strategy': strategy_name,
                    'symbol': position.symbol,
                    'side': position.side,
                    'entry_price': position.entry_price,
                    'quantity': position.quantity,
                    'position_value_usdt': position_value_usdt,
                    'margin_invested': margin_invested,
                    'current_price': current_price,
                    'pnl': pnl,
                    'pnl_percent': pnl_percent,
                    'anomaly_status': anomaly_status
                })

        return jsonify({'success': True, 'positions': positions})
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/trades', methods=['GET'])
def get_trades():
    """Get recent trades"""
    try:
        trades = []
        trades_dir_path = os.path.join(os.getcwd(), 'trading_data', 'trades')
        if os.path.exists(trades_dir_path):
            for filename in sorted(os.listdir(trades_dir_path), reverse=True)[:10]:
                if filename.endswith(".json"):
                    filepath = os.path.join(trades_dir_path, filename)
                    with open(filepath, 'r') as f:
                        trade_data = json.load(f)
                        trades.append(trade_data)
        return jsonify(trades)
    except Exception as e:
        logger.error(f"Error getting trades: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/console/log', methods=['GET'])
def get_console_log():
    """Get recent console logs from bot manager"""
    try:
        current_bot = shared_bot_manager if shared_bot_manager else bot_manager

        if current_bot and hasattr(current_bot, 'log_handler'):
            logs = list(current_bot.log_handler.logs)
            return jsonify({'logs': logs})
        else:
            sample_logs = [
                {'timestamp': '15:44:53', 'message': '🌐 Web dashboard active - Bot can be started via Start Bot button'},
                {'timestamp': '15:44:53', 'message': '📊 Ready for trading operations'},
                {'timestamp': '15:44:53', 'message': '💡 Use the web interface to control the bot'}
            ]
            return jsonify({'logs': sample_logs})
    except Exception as e:
        logger.error(f"Error getting console log: {e}")
        return jsonify({'logs': [], 'error': str(e)}), 500

@app.route('/api/console-log', methods=['GET'])
def get_console_log_alt():
    """Alternative console log endpoint"""
    return get_console_log()

@app.route('/api/console/logs', methods=['GET'])
def get_console_logs_plural():
    """Console logs endpoint with plural naming"""
    return get_console_log()

@app.route('/api/bot-status', methods=['GET'])
def get_bot_status_alt():
    """Alternative bot status endpoint"""
    return get_bot_status()

@app.route('/api/status', methods=['GET'])
def get_status_alt():
    """Alternative status endpoint"""
    return get_bot_status()

@app.route('/api/trading/environment', methods=['GET'])
def get_trading_environment():
    """Get trading environment configuration"""
    try:
        current_bot = shared_bot_manager if shared_bot_manager else bot_manager

        if current_bot and hasattr(current_bot, 'is_running'):
            environment_info = {
                'bot_running': current_bot.is_running,
                'environment': 'MAINNET',
                'web_dashboard_active': True,
                'config_source': 'web_dashboard'
            }
        else:
            environment_info = {
                'bot_running': False,
                'environment': 'MAINNET',
                'web_dashboard_active': True,
                'config_source': 'web_dashboard'
            }

        return jsonify(environment_info)

    except Exception as e:
        logger.error(f"Error getting trading environment: {e}")
        return jsonify({'error': str(e), 'environment': 'UNKNOWN'}), 500

# Add a catch-all route for debugging 404s
@app.route('/<path:path>')
def catch_all(path):
    """Catch-all route to debug 404 errors"""
    logger.error(f"❌ 404 ERROR: Requested path not found: /{path}")
    logger.error(f"📍 Available routes:")
    for rule in app.url_map.iter_rules():
        if rule.rule != '/<path:path>':
            methods = ', '.join(sorted(rule.methods - {'OPTIONS', 'HEAD'}))
            logger.error(f"    {rule.rule} ({methods})")

    return jsonify({
        'error': 'Not Found',
        'message': f'The requested path /{path} was not found',
        'available_routes': [rule.rule for rule in app.url_map.iter_rules() if rule.rule != '/<path:path>']
    }), 404

if __name__ == '__main__':
    # This block should never execute in production
    # Web dashboard should ONLY be launched from main.py
    logger.warning("🚫 DIRECT WEB_DASHBOARD.PY LAUNCH BLOCKED")
    logger.warning("🔄 Web dashboard should only be started from main.py")
    logger.warning("💡 Run 'python main.py' instead")
    print("❌ Direct execution of web_dashboard.py is disabled")
    print("🔄 Please run 'python main.py' to start the bot with web dashboard")
    exit(1)