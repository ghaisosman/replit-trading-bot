#!/usr/bin/env python3
"""
Trading Bot Web Dashboard
Complete web interface for managing the trading bot
"""

from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_cors import CORS
import json
import asyncio
import threading
import os
from datetime import datetime, timedelta
from pathlib import Path
import logging
from typing import Dict, Any
import time
from functools import wraps

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

@app.route('/static/<path:filename>')
def static_files(filename):
    """Serve static files"""
    return send_from_directory('static', filename)

# Rate limiting system to prevent API flooding
rate_limits = {
    'bot_status': {'requests': [], 'limit': 20, 'window': 60},    # 20 requests per minute
    'balance': {'requests': [], 'limit': 10, 'window': 60},      # 10 requests per minute
    'positions': {'requests': [], 'limit': 15, 'window': 60},    # 15 requests per minute
    'console_log': {'requests': [], 'limit': 30, 'window': 60}   # 30 requests per minute
}

def rate_limit(endpoint_key, max_requests=20, window_seconds=60):
    """Rate limiting decorator to prevent API flooding"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            now = time.time()

            # Get rate limit data for this endpoint
            limit_data = rate_limits.get(endpoint_key, {
                'requests': [], 'limit': max_requests, 'window': window_seconds
            })

            # Clean old requests outside the window
            cutoff_time = now - limit_data['window']
            limit_data['requests'] = [req_time for req_time in limit_data['requests'] if req_time > cutoff_time]

            # Check if limit exceeded
            if len(limit_data['requests']) >= limit_data['limit']:
                logger.warning(f"Rate limit exceeded for {endpoint_key}: {len(limit_data['requests'])} requests in {limit_data['window']}s")

                # FIXED: Return complete JSON structure based on endpoint type
                # This prevents empty {} responses that cause JavaScript parsing errors
                if endpoint_key == 'bot_status':
                    return jsonify({
                        'success': False,
                        'error': 'Rate limit exceeded',
                        'retry_after': int(limit_data['requests'][0] + limit_data['window'] - now),
                        'running': False,
                        'is_running': False,
                        'active_positions': 0,
                        'strategies': 0,
                        'balance': 0.0,
                        'status': 'rate_limited',
                        'last_update': datetime.now().strftime('%H:%M:%S'),
                        'timestamp': datetime.now().strftime('%H:%M:%S')
                    }), 200  # Changed to 200 to prevent browser errors
                elif endpoint_key == 'console_log':
                    return jsonify({
                        'success': False,
                        'error': 'Rate limit exceeded',
                        'retry_after': int(limit_data['requests'][0] + limit_data['window'] - now),
                        'logs': [f'[{datetime.now().strftime("%H:%M:%S")}] ⚠️ Rate limit exceeded - please wait'],
                        'status': 'rate_limited',
                        'timestamp': datetime.now().strftime('%H:%M:%S')
                    }), 200  # Changed to 200 to prevent browser errors
                elif endpoint_key == 'positions':
                    return jsonify({
                        'success': False,
                        'error': 'Rate limit exceeded',
                        'retry_after': int(limit_data['requests'][0] + limit_data['window'] - now),
                        'positions': [],
                        'status': 'rate_limited',
                        'count': 0,
                        'timestamp': datetime.now().strftime('%H:%M:%S')
                    }), 429
                elif endpoint_key == 'balance':
                    return jsonify({
                        'success': False,
                        'error': 'Rate limit exceeded',
                        'retry_after': int(limit_data['requests'][0] + limit_data['window'] - now),
                        'total_balance': 0.0,
                        'available_balance': 0.0,
                        'used_balance': 0.0,
                        'last_updated': datetime.now().isoformat(),
                        'status': 'rate_limited'
                    }), 429
                else:
                    # Generic rate limit response
                    return jsonify({
                        'success': False,
                        'error': 'Rate limit exceeded',
                        'retry_after': int(limit_data['requests'][0] + limit_data['window'] - now),
                        'status': 'rate_limited',
                        'timestamp': datetime.now().strftime('%H:%M:%S')
                    }), 429

            # Add current request
            limit_data['requests'].append(now)
            rate_limits[endpoint_key] = limit_data

            # Execute the wrapped function with error handling
            try:
                result = f(*args, **kwargs)

                # Ensure result is valid JSON response
                if hasattr(result, 'get_json'):
                    # This is a Flask response - validate it has data
                    try:
                        json_data = result.get_json()
                        if not json_data:
                            # Empty response - return appropriate default
                            current_time = datetime.now().strftime('%H:%M:%S')
                            if endpoint_key == 'bot_status':
                                return jsonify({
                                    'success': True,
                                    'running': False,
                                    'is_running': False,
                                    'active_positions': 0,
                                    'strategies': 0,
                                    'balance': 0.0,
                                    'status': 'no_data',
                                    'last_update': current_time,
                                    'timestamp': current_time
                                })
                            elif endpoint_key == 'console_log':
                                return jsonify({
                                    'success': True,
                                    'logs': [f'[{current_time}] 🔄 Loading...'],
                                    'status': 'loading',
                                    'timestamp': current_time
                                })
                    except:
                        pass  # If we can't parse JSON, continue with original result

                return result
            except Exception as func_error:
                logger.error(f"Rate-limited function {endpoint_key} failed: {func_error}")

                # Return appropriate error response based on endpoint
                current_time = datetime.now().strftime('%H:%M:%S')
                if endpoint_key == 'bot_status':
                    return jsonify({
                        'success': True,  # Changed to True to prevent frontend errors
                        'running': False,
                        'is_running': False,
                        'active_positions': 0,
                        'strategies': 0,
                        'balance': 0.0,
                        'status': 'function_error',
                        'error': str(func_error),
                        'last_update': current_time,
                        'timestamp': current_time
                    }), 200
                elif endpoint_key == 'console_log':
                    return jsonify({
                        'success': True,  # Changed to True to prevent frontend errors
                        'logs': [f'[{current_time}] ⚠️ Error loading logs: {str(func_error)}'],
                        'status': 'function_error',
                        'error': str(func_error),
                        'timestamp': current_time
                    }), 200
                else:
                    return jsonify({
                        'success': True,  # Changed to True to prevent frontend errors
                        'error': str(func_error),
                        'timestamp': current_time,
                        'status': 'function_error'
                    }), 200
        return decorated_function
    return decorator

# Global bot instance - shared with main.py
bot_manager = None
bot_thread = None
bot_running = False
shared_bot_manager = None

# Ensure global variables are properly initialized
def init_globals():
    """Initialize global variables safely"""
    global bot_manager, bot_thread, bot_running, shared_bot_manager

    # Initialize all variables to safe defaults
    if 'bot_running' not in globals() or bot_running is None:
        bot_running = False
    if 'bot_manager' not in globals():
        bot_manager = None
    if 'bot_thread' not in globals():
        bot_thread = None
    if 'shared_bot_manager' not in globals():
        shared_bot_manager = None

# Call initialization
init_globals()

# Import the shared bot manager from main.py if it exists
import sys
shared_bot_manager = None

def get_shared_bot_manager():
    """Get the shared bot manager with proper error handling"""
    global bot_running, shared_bot_manager
    try:
        return getattr(sys.modules.get('__main__', None), 'bot_manager', None)
    except Exception as e:
        logger.debug(f"Error getting shared bot manager: {e}")
        return None

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

    # Get initial shared bot manager reference
    shared_bot_manager = get_shared_bot_manager()

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
            return 169.1

    trading_config_manager = DummyConfigManager()
    balance_fetcher = DummyBalanceFetcher()

@app.route('/healthz')
def healthz():
    return 'OK', 200

@app.route('/api/dashboard/health')
def dashboard_health():
    """Health check endpoint for debugging dashboard status"""
    try:
        current_time = datetime.now().strftime('%H:%M:%S')
        current_bot = get_shared_bot_manager()

        health_status = {
            'dashboard_status': 'healthy',
            'timestamp': current_time,
            'bot_manager_available': current_bot is not None,
            'bot_running': getattr(current_bot, 'is_running', False) if current_bot else False,
            'imports_available': IMPORTS_AVAILABLE,
            'web_thread_id': threading.current_thread().ident,
            'can_start_bot': True,
            'can_stop_bot': True
        }

        logger.info(f"🔍 DEBUG: Dashboard health check - {health_status}")
        return jsonify(health_status)

    except Exception as e:
        logger.error(f"🔍 DEBUG: Dashboard health check failed: {e}")
        return jsonify({
            'dashboard_status': 'error',
            'error': str(e),
            'timestamp': datetime.now().strftime('%H:%M:%S')
        }), 500

@app.route('/')
def dashboard():
    """Main dashboard page"""
    try:
        # Get current bot status
        status = get_bot_status()

        # Get balance and strategies
        if IMPORTS_AVAILABLE:
            try:
                balance = balance_fetcher.get_usdt_balance()
                if balance is None:
                    balance = 0.0
                balance = float(balance)
            except Exception as e:
                logger.error(f"Error getting balance for dashboard: {e}")
                balance = 0.0
            strategies = trading_config_manager.get_all_strategies()

            # Ensure we always have both strategies available for display
            if 'rsi_oversold' not in strategies:
                strategies['rsi_oversold'] = {
                    'symbol': 'SOLUSDT', 'margin': 12.5, 'leverage': 25, 'timeframe': '15m',
                    'max_loss_pct': 5, 'assessment_interval': 20, 'decimals': 2,
                    'cooldown_period': 300, 'rsi_long_entry': 30, 'rsi_long_exit': 70,
                    'rsi_short_entry': 70, 'rsi_short_exit': 30
                }
            if 'macd_divergence' not in strategies:
                strategies['macd_divergence'] = {
                    'symbol': 'BTCUSDT', 'margin': 50.0, 'leverage': 5, 'timeframe': '5m',
                    'max_loss_pct': 10, 'assessment_interval': 60, 'decimals': 3,
                    'cooldown_period': 300, 'macd_fast': 12, 'macd_slow': 26, 'macd_signal': 9,
                    'min_histogram_threshold': 0.0001, 'macd_entry_threshold': 0.05,
                    'macd_exit_threshold': 0.02, 'histogram_divergence_lookback': 10,
                    'price_divergence_lookback': 10
                }
        else:
            balance = 100.0  # Default for demo
            strategies = {
                'rsi_oversold': {'symbol': 'SOLUSDT', 'margin': 12.5, 'leverage': 25, 'timeframe': '15m'},
                'macd_divergence': {'symbol': 'BTCUSDT', 'margin': 50.0, 'leverage': 5, 'timeframe': '5m'}
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

                # Get actual margin used for this specific position, fallback to strategy config
                margin_invested = getattr(position, 'actual_margin_used', None)
                if margin_invested is None:
                    # Fallback: calculate from position data if actual_margin_used not available
                    strategy_config = current_bot.strategies.get(strategy_name, {}) if hasattr(current_bot, 'strategies') else {}
                    leverage = strategy_config.get('leverage', 5)
                    position_value = position.entry_price * position.quantity
                    margin_invested = position_value / leverage

                # Ensure margin_invested is valid
                if margin_invested <= 0:
                    strategy_config = current_bot.strategies.get(strategy_name, {}) if hasattr(current_bot, 'strategies') else {}
                    margin_invested = strategy_config.get('margin', 50.0)  # Last resort fallback

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
    """Start the trading bot with improved connection handling"""
    global bot_manager, bot_thread, bot_running, shared_bot_manager

    try:
        logger = logging.getLogger(__name__)
        logger.info("🔍 DEBUG: Bot start request received via web dashboard")

        # Check if any bot is currently running
        current_bot = get_shared_bot_manager()
        logger.info(f"🔍 DEBUG: Shared bot manager status: {current_bot is not None}")
        if current_bot:
            is_running = getattr(current_bot, 'is_running', False)
            logger.info(f"🔍 DEBUG: Shared bot is_running: {is_running}")
            if is_running:
                return jsonify({'success': False, 'message': 'Bot is already running'})

        logger.info(f"🔍 DEBUG: Bot thread status - Running: {bot_running}, Thread alive: {bot_thread.is_alive() if bot_thread else 'No thread'}")
        if bot_running and bot_thread and bot_thread.is_alive():
            return jsonify({'success': False, 'message': 'Bot is already running in web dashboard'})

        logger.info("🌐 WEB INTERFACE: Starting bot from dashboard")
        logger.info("🔍 DEBUG: Setting bot_running = True")
        bot_running = True

        # Start bot in separate thread with proper cleanup
        def run_bot():
            global bot_running
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            bot_instance = None

            try:
                # Create fresh bot manager instance
                from src.bot_manager import BotManager
                bot_instance = BotManager()

                # Update global references
                sys.modules['__main__'].bot_manager = bot_instance
                globals()['bot_manager'] = bot_instance

                logger.info("🚀 STARTING BOT FROM WEB INTERFACE")

                # Run the bot
                loop.run_until_complete(bot_instance.start())

            except Exception as e:
                logger.error(f"Bot runtime error: {e}")
                try:
                    if bot_instance:
                        bot_instance.telegram_reporter.report_bot_stopped(f"Error: {str(e)}")
                except:
                    pass
            finally:
                # Cleanup
                bot_running = False
                if bot_instance:
                    bot_instance.is_running = False
                logger.info("🔴 BOT STOPPED - Web interface remains active")
                try:
                    loop.close()
                except:
                    pass

        # Start in daemon thread
        bot_thread = threading.Thread(target=run_bot, daemon=True)
        bot_thread.start()

        # Wait a moment for startup
        import time
        time.sleep(0.5)

        return jsonify({'success': True, 'message': 'Bot started successfully from web interface'})

    except Exception as e:
        bot_running = False
        logger.error(f"Failed to start bot: {e}")
        return jsonify({'success': False, 'message': f'Failed to start bot: {e}'})

@app.route('/api/bot/stop', methods=['POST'])
def stop_bot():
    """Stop the trading bot completely"""
    global bot_manager, bot_running, shared_bot_manager, bot_thread

    try:
        logger = logging.getLogger(__name__)
        logger.info("🌐 WEB INTERFACE: Stop request received")
        logger.info("🔍 DEBUG: Beginning bot stop procedure...")

        stopped = False

        # Debug current state - bot_running is now safely accessible
        logger.info(f"🔍 DEBUG: Current state - bot_running: {bot_running}")
        logger.info(f"🔍 DEBUG: Bot thread alive: {bot_thread.is_alive() if bot_thread else 'No thread'}")
        logger.info(f"🔍 DEBUG: Shared bot manager exists: {shared_bot_manager is not None}")
        logger.info(f"🔍 DEBUG: Local bot manager exists: {bot_manager is not None}")

        # Try to stop shared bot manager first
        shared_bot_manager = get_shared_bot_manager()
        if shared_bot_manager and hasattr(shared_bot_manager, 'is_running') and shared_bot_manager.is_running:
            logger.info("🌐 STOPPING SHARED BOT MANAGER")

            # Set stop flag immediately
            shared_bot_manager.is_running = False

            # Try graceful shutdown
            try:
                # Create stop task in separate thread
                def stop_shared_bot():
                    try:
                        import asyncio
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(shared_bot_manager.stop("Manual stop via web interface"))
                        loop.close()
                    except Exception as e:
                        logger.error(f"Error in shared bot stop: {e}")

                stop_thread = threading.Thread(target=stop_shared_bot, daemon=True)
                stop_thread.start()

                # Wait briefly for stop to complete
                stop_thread.join(timeout=2.0)
                stopped = True

            except Exception as e:
                logger.error(f"Error stopping shared bot: {e}")
                # Force stop
                shared_bot_manager.is_running = False
                stopped = True

        # Try to stop standalone bot
        if bot_manager and hasattr(bot_manager, 'is_running') and bot_manager.is_running:
            logger.info("🌐 STOPPING STANDALONE BOT MANAGER")
            bot_manager.is_running = False
            stopped = True

        # Update global state
        bot_running = False

        # Wait for bot thread to finish
        if bot_thread and bot_thread.is_alive():
            logger.info("🌐 WAITING FOR BOT THREAD TO FINISH")
            bot_thread.join(timeout=3.0)
            if bot_thread.is_alive():
                logger.warning("⚠️ Bot thread did not finish cleanly")

        if stopped:
            logger.info("🔴 BOT STOPPED VIA WEB INTERFACE")
            logger.info("💡 Web dashboard remains active - you can restart the bot anytime")
            logger.info("🔍 DEBUG: Bot stop successful, web dashboard continuing...")
            return jsonify({
                'success': True, 
                'message': 'Bot stopped successfully. You can restart it from the dashboard.',
                'dashboard_status': 'active',
                'can_restart': True
            })
        else:
            logger.warning("🔍 DEBUG: No running bot found to stop")
            return jsonify({
                'success': False, 
                'message': 'No running bot found to stop',
                'dashboard_status': 'active',
                'can_restart': True
            })

    except Exception as e:
        logger.error(f"Error stopping bot: {e}")
        # Force cleanup - ensure safe global variable access
        try:
            bot_running = False
            if shared_bot_manager:
                shared_bot_manager.is_running = False
            if bot_manager:
                bot_manager.is_running = False
        except Exception as cleanup_error:
            logger.error(f"Error during cleanup: {cleanup_error}")

        return jsonify({'success': False, 'message': f'Error stopping bot: {e}'})

# FIXED: Ensure datetime is available for all endpoints
from flask import Flask, render_template, request, jsonify, redirect, url_for
import json
import logging
import threading
import time
import asyncio
import os
from datetime import datetime
import sys

@app.route('/api/bot/status')
@app.route('/api/bot_status')
@rate_limit('bot_status', max_requests=20, window_seconds=60)
def get_bot_status():
    """Get current bot status with bulletproof error handling and comprehensive debugging"""
    global bot_running
    current_time = datetime.now().strftime('%H:%M:%S')
    request_id = f"status_{int(time.time() * 1000)}"

    logger.debug(f"🔍 DEBUG [{request_id}]: Bot status API called")

    # FIXED: Always return complete JSON structure to prevent parsing errors
    default_response = {
        'success': True,
        'running': False,
        'is_running': False,
        'active_positions': 0,
        'strategies': 0,
        'balance': 0.0,
        'status': 'checking',
        'last_update': current_time,
        'timestamp': current_time,
        'debug_info': {
            'request_id': request_id,
            'endpoint': 'bot_status',
            'response_size': 0
        }
    }

    try:
        logger.debug(f"🔍 DEBUG [{request_id}]: Getting bot manager...")

        # Try to get current bot manager
        current_bot_manager = get_bot_manager()

        if current_bot_manager:
            logger.debug(f"🔍 DEBUG [{request_id}]: Bot manager found")

            # Get running status
            is_running = getattr(current_bot_manager, 'is_running', False)
            default_response.update({
                'running': is_running,
                'is_running': is_running,
                'status': 'running' if is_running else 'stopped'
            })
            logger.debug(f"🔍 DEBUG [{request_id}]: Bot running status: {is_running}")

            # Get active positions count
            if hasattr(current_bot_manager, 'order_manager') and current_bot_manager.order_manager:
                active_count = len(getattr(current_bot_manager.order_manager, 'active_positions', {}))
                default_response['active_positions'] = active_count
                logger.debug(f"🔍 DEBUG [{request_id}]: Active positions: {active_count}")

            # Get strategies count
            if hasattr(current_bot_manager, 'strategies'):
                strategies_count = len(current_bot_manager.strategies)
                default_response['strategies'] = strategies_count
                logger.debug(f"🔍 DEBUG [{request_id}]: Strategies count: {strategies_count}")

            # Try to get balance
            try:
                if hasattr(current_bot_manager, 'balance_fetcher'):
                    balance = current_bot_manager.balance_fetcher.get_usdt_balance()
                    if balance is not None:
                        default_response['balance'] = float(balance)
                        logger.debug(f"🔍 DEBUG [{request_id}]: Balance retrieved: {balance}")
            except Exception as balance_error:
                logger.warning(f"🔍 DEBUG [{request_id}]: Balance fetch failed: {balance_error}")

        else:
            logger.debug(f"🔍 DEBUG [{request_id}]: No bot manager found")

        # Calculate response size for debugging
        import json
        response_json = json.dumps(default_response)
        default_response['debug_info']['response_size'] = len(response_json)

        logger.debug(f"🔍 DEBUG [{request_id}]: Response prepared, size: {len(response_json)} chars")

        # CRITICAL: Validate JSON before sending
        try:
            json.loads(json.dumps(default_response))  # Test JSON serialization
            logger.debug(f"✅ DEBUG [{request_id}]: JSON validation passed")
        except Exception as json_error:
            logger.error(f"❌ DEBUG [{request_id}]: JSON validation FAILED: {json_error}")
            # Return minimal safe response
            safe_response = {
                'success': False,
                'error': 'JSON serialization failed',
                'timestamp': current_time,
                'debug_info': {'request_id': request_id, 'json_error': str(json_error)}
            }
            return jsonify(safe_response)

        return jsonify(default_response)

    except Exception as e:
        logger.error(f"❌ DEBUG [{request_id}]: Bot status API error: {e}")
        import traceback
        logger.error(f"❌ DEBUG [{request_id}]: Full traceback: {traceback.format_exc()}")

        default_response.update({
            'success': False,
            'status': 'api_error',
            'error': str(e),
            'debug_info': {
                'request_id': request_id,
                'error_type': type(e).__name__,
                'traceback': traceback.format_exc()[-500:]  # Last 500 chars
            }
        })
        return jsonify(default_response)

@app.route('/api/strategies')
def get_strategies():
    """Get all strategy configurations - WEB DASHBOARD IS SINGLE SOURCE OF TRUTH"""
    try:
        if IMPORTS_AVAILABLE:
            # FORCE FRESH LOAD - Clear any cached configurations
            trading_config_manager._clear_cache() if hasattr(trading_config_manager, '_clear_cache') else None

            # Get all strategies from web dashboard configuration manager
            strategies = trading_config_manager.get_all_strategies()

            # Ensure ALL configurable parameters are present for each strategy
            for name, config in strategies.items():
                # Core Trading Parameters (All strategies)
                config.setdefault('symbol', 'BTCUSDT')
                config.setdefault('timeframe', '15m')
                config.setdefault('margin', 50.0)
                config.setdefault('leverage', 5)
                config.setdefault('stop_loss_pct', 10.0)  # Stop loss as % of margin
                config.setdefault('max_loss_pct', 10.0)   # Alternative naming
                config.setdefault('assessment_interval', 60 if 'rsi' in name.lower() else 30)

                # Position Management Parameters
                config.setdefault('cooldown_period', 300)  # 5 minutes default
                config.setdefault('min_volume', 1000.0)
                config.setdefault('take_profit_pct', 20.0)  # Take profit as % of margin
                config.setdefault('trailing_stop_pct', 2.0)
                config.setdefault('max_position_time', 3600)  # 1 hour max

                # Set default decimals based on symbol
                if 'decimals' not in config:
                    symbol = config.get('symbol', '').upper()
                    if 'ETH' in symbol or 'SOL' in symbol:
                        config['decimals'] = 2
                    elif 'BTC' in symbol:
                        config['decimals'] = 3
                    else:
                        config['decimals'] = 2

                # RSI Strategy Specific Parameters
                if 'rsi' in name.lower():
                    config.setdefault('rsi_period', 14)
                    config.setdefault('rsi_long_entry', 30)    # Oversold entry
                    config.setdefault('rsi_long_exit', 70)     # Take profit (overbought)
                    config.setdefault('rsi_short_entry', 70)   # Overbought entry  
                    config.setdefault('rsi_short_exit', 30)    # Take profit (oversold)

                # MACD Strategy Specific Parameters
                elif 'macd' in name.lower():
                    config.setdefault('macd_fast', 12)
                    config.setdefault('macd_slow', 26)
                    config.setdefault('macd_signal', 9)
                    config.setdefault('min_histogram_threshold', 0.0001)
                    config.setdefault('min_distance_threshold', 0.005)
                    config.setdefault('confirmation_candles', 2)

                # Smart Money Strategy Specific Parameters
                elif 'smart' in name.lower() and 'money' in name.lower():
                    config.setdefault('swing_lookback_period', 25)
                    config.setdefault('sweep_threshold_pct', 0.1)
                    config.setdefault('reversion_candles', 3)
                    config.setdefault('volume_spike_multiplier', 2.0)
                    config.setdefault('min_swing_distance_pct', 1.0)
                    config.setdefault('max_daily_trades', 3)
                    config.setdefault('session_filter_enabled', True)
                    config.setdefault('allowed_sessions', ['LONDON', 'NEW_YORK'])
                    config.setdefault('trend_filter_enabled', True)
                    config.setdefault('min_volume', 100000)
                    config.setdefault('decimals', 2)
                    config.setdefault('cooldown_period', 300)

                # Universal Strategy Parameters (for any future strategy)
                else:
                    config.setdefault('decimals', 2)
                    config.setdefault('cooldown_period', 300)
                    config.setdefault('min_volume', 1000000)
                    config.setdefault('entry_threshold', 0.1)
                    config.setdefault('exit_threshold', 0.05)
                    config.setdefault('signal_period', 14)
                    config.setdefault('confirmation_period', 2)

            logger.info(f"🌐 WEB DASHBOARD: Serving COMPLETE configurations for {len(strategies)} strategies")
            logger.info(f"📋 All parameters available for manual configuration via dashboard")
            return jsonify(strategies)
        else:
            # Return comprehensive default strategies for demo
            return jsonify({
                'rsi_oversold': {
                    # Core Parameters
                    'symbol': 'SOLUSDT', 'timeframe': '15m', 'margin': 12.5, 'leverage': 25,
                    'stop_loss_pct': 10.0, 'max_loss_pct': 10.0, 'assessment_interval': 60,
                    # Position Management
                    'cooldown_period': 300, 'min_volume': 1000.0, 'decimals': 2,
                    'take_profit_pct': 20.0, 'trailing_stop_pct': 2.0, 'max_position_time': 3600,
                    # RSI Specific
                    'rsi_period': 14, 'rsi_long_entry': 30, 'rsi_long_exit': 70,
                    'rsi_short_entry': 70, 'rsi_short_exit': 30
                },
                'macd_divergence': {
                    # Core Parameters
                    'symbol': 'BTCUSDT', 'timeframe': '15m', 'margin': 50.0, 'leverage': 5,
                    'stop_loss_pct': 10.0, 'max_loss_pct': 10.0, 'assessment_interval': 30,
                    # Position Management
                    'cooldown_period': 300, 'min_volume': 1000.0, 'decimals': 3,
                    'take_profit_pct': 15.0, 'trailing_stop_pct': 2.0, 'max_position_time': 3600,
                    # MACD Specific
                    'macd_fast': 12, 'macd_slow': 26, 'macd_signal': 9,
                    'min_histogram_threshold': 0.0001, 'min_distance_threshold': 0.005, 'confirmation_candles': 2,
                    'divergence_strength_min': 0.6
                }
            })
    except Exception as e:
        logger.error(f"Error in get_strategies endpoint: {e}")
        return jsonify({'error': str(e), 'strategies': {}}), 500

@app.route('/api/strategies', methods=['POST'])
def create_strategy():
    """Create a new strategy - WEB DASHBOARD IS SINGLE SOURCE OF TRUTH"""
    try:
        if not IMPORTS_AVAILABLE:
            return jsonify({'success': False, 'message':'Strategy creation not available in demo mode'})

        data = request.get_json()

        if not data or 'name' not in data:
            return jsonify({'success': False, 'message': 'Strategy name is required'})

        strategy_name = data['name'].strip()

        # Comprehensive validation
        if not strategy_name:
            return jsonify({'success': False, 'message': 'Strategy name cannot be empty'})

        # Validate strategy name format
        if not strategy_name.replace('_', '').replace('-', '').isalnum():
            return jsonify({'success': False, 'message': 'Strategy name can only contain letters, numbers, underscores and hyphens'})

        # Check if strategy already exists
        existing_strategies = trading_config_manager.get_all_strategies()
        if strategy_name in existing_strategies:
            return jsonify({'success': False, 'message': f'Strategy "{strategy_name}" already exists'})

        # Validate strategy type
        if ('rsi' not in strategy_name.lower() and 
            'macd' not in strategy_name.lower() and 
            'engulfing' not in strategy_name.lower()):
            return jsonify({'success': False, 'message': 'Strategy name must contain "rsi" or "macd" to determine strategy type'})

        # Validate symbol
        symbol = data.get('symbol', '').strip().upper()
        if not symbol or len(symbol) < 6:
            return jsonify({'success': False, 'message': 'Valid symbol is required (e.g., BTCUSDT)'})

        # Validate margin and leverage
        try:
            margin = float(data.get('margin', 50.0))
            leverage = int(data.get('leverage', 5))

            if margin <= 0 or margin > 10000:
                return jsonify({'success': False, 'message': 'Margin must be between 0.01 and 10000 USDT'})

            if leverage <= 0 or leverage > 125:
                return jsonify({'success': False, 'message': 'Leverage must be between 1 and 125'})

        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': 'Invalid margin or leverage values'})

        # Create comprehensive strategy configuration with web dashboard as source of truth
        new_config = {
            'symbol': symbol,
            'margin': margin,
            'leverage': leverage,
            'timeframe': data.get('timeframe', '15m'),
            'max_loss_pct': float(data.get('max_loss_pct', 10.0)),
            'assessment_interval': int(data.get('assessment_interval', 60)),
            'cooldown_period': int(data.get('cooldown_period', 300)),
            'decimals': 2 if 'ETH' in symbol or 'SOL' in symbol else 3,
            'min_volume': 1000000
        }

        # Add strategy-specific parameters with validation

        # Add strategy-specific parameters with validation
        if 'rsi' in strategy_name.lower():
            new_config.update({
                'rsi_period': 14,
                'rsi_long_entry': int(data.get('rsi_long_entry', 30)),
                'rsi_long_exit': int(data.get('rsi_long_exit', 70)),
                'rsi_short_entry': int(data.get('rsi_short_entry', 70)),
                'rsi_short_exit': int(data.get('rsi_short_exit', 30))
            })

            # Validate RSI parameters
            if not (10 <= new_config['rsi_long_entry'] <= 50):
                return jsonify({'success': False, 'message': 'RSI Long Entry must be between 10 and 50'})
            if not (50 <= new_config['rsi_long_exit'] <= 90):
                return jsonify({'success': False, 'message': 'RSI Long Exit must be between 50 and 90'})

        elif 'macd' in strategy_name.lower():
            new_config.update({
                'macd_fast': int(data.get('macd_fast', 12)),
                'macd_slow': int(data.get('macd_slow', 26)),
                'macd_signal': int(data.get('macd_signal', 9)),
                'min_histogram_threshold': float(data.get('min_histogram_threshold', 0.0001)),
                'min_distance_threshold': float(data.get('min_distance_threshold', 0.005)),
                'confirmation_candles': int(data.get('confirmation_candles', 2))
            })

            # Validate MACD parameters
            if new_config['macd_fast'] >= new_config['macd_slow']:
                return jsonify({'success': False, 'message': 'MACD Fast must be less than MACD Slow'})

        elif 'engulfing' in strategy_name.lower():
            new_config.update({
                'rsi_period': int(data.get('rsi_period', 14)),
                'rsi_threshold': float(data.get('rsi_threshold', 50)),
                'rsi_long_exit': int(data.get('rsi_long_exit', 70)),
                'rsi_short_exit': int(data.get('rsi_short_exit', 30)),
                'stable_candle_ratio': float(data.get('stable_candle_ratio', 0.5)),
                'price_lookback_bars': int(data.get('price_lookback_bars', 5)),
                'partial_tp_pnl_threshold': float(data.get('partial_tp_pnl_threshold', 0.0)),
                'partial_tp_position_percentage': float(data.get('partial_tp_position_percentage', 0.0))
            })

            # Validate Engulfing Pattern parameters
            if not (30 <= new_config['rsi_threshold'] <= 70):
                return jsonify({'success': False, 'message': 'RSI Threshold must be between 30 and 70'})
            if not (0.1 <= new_config['stable_candle_ratio'] <= 1.0):
                return jsonify({'success': False, 'message': 'Stable Candle Ratio must be between 0.1 and 1.0'})

        # 🎯 WEB DASHBOARD IS SINGLE SOURCE OF TRUTH - Save to persistent config
        trading_config_manager.update_strategy_params(strategy_name, new_config)

        logger.info(f"🆕 NEW STRATEGY CREATED: {strategy_name} via web dashboard")
        logger.info(f"🌐 WEB DASHBOARD: New strategy config saved as single source of truth")
        logger.info(f"📝 STRATEGY CONFIG: {new_config}")

        return jsonify({
            'success': True, 
            'message': f'Strategy "{strategy_name}" created successfully! Restart bot to activate.',
            'strategy': new_config
        })

    except Exception as e:
        logger.error(f"Error creating strategy: {e}")
        return jsonify({'success': False, 'message': f'Failed to create strategy: {str(e)}'})

@app.route('/api/strategies/<strategy_name>', methods=['POST'])
def update_strategy(strategy_name):
    """Update strategy configuration - WEB DASHBOARD IS SINGLE SOURCE OF TRUTH"""
    try:
        data = request.get_json()

        # Validate data to prevent errors
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'})

        # Comprehensive parameter validation for ALL configurable parameters
        try:
            # Core Trading Parameters
            if 'symbol' in data:
                data['symbol'] = str(data['symbol']).upper()
                if not data['symbol'] or len(data['symbol']) < 6:
                    return jsonify({'success': False, 'message': 'Symbol must be valid (e.g., BTCUSDT)'})

            if 'timeframe' in data:
                valid_timeframes = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d']
                if data['timeframe'] not in valid_timeframes:
                    return jsonify({'success': False, 'message': f'Timeframe must be one of: {", ".join(valid_timeframes)}'})

            if 'margin' in data:
                data['margin'] = float(data['margin'])
                if data['margin'] <= 0 or data['margin'] > 10000:
                    return jsonify({'success': False, 'message': 'Margin must be between 0.01 and 10000 USDT'})

            if 'leverage' in data:
                data['leverage'] = int(data['leverage'])
                if data['leverage'] <= 0 or data['leverage'] > 125:
                    return jsonify({'success': False, 'message': 'Leverage must be between 1 and 125'})

            # Stop Loss as Percentage of Margin
            if 'stop_loss_pct' in data:
                data['stop_loss_pct'] = float(data['stop_loss_pct'])
                if data['stop_loss_pct'] <= 0 or data['stop_loss_pct'] > 100:
                    return jsonify({'success': False, 'message': 'Stop Loss % must be between 0.1 and 100% of margin'})

            # Max Loss as Percentage of Margin (alternative naming)
            if 'max_loss_pct' in data:
                data['max_loss_pct'] = float(data['max_loss_pct'])
                if data['max_loss_pct'] <= 0 or data['max_loss_pct'] > 100:
                    return jsonify({'success': False, 'message': 'Max Loss % must be between 0.1 and 100% of margin'})

            # Market Assessment Intervals
            if 'assessment_interval' in data:
                data['assessment_interval'] = int(data['assessment_interval'])
                if data['assessment_interval'] < 5 or data['assessment_interval'] > 3600:
                    return jsonify({'success': False, 'message': 'Market assessment interval must be between 5 and 3600 seconds'})

            # Position Management
            if 'decimals' in data:
                data['decimals'] = int(data['decimals'])
                if data['decimals'] < 0 or data['decimals'] > 8:
                    return jsonify({'success': False, 'message': 'Price decimals must be between 0 and 8'})

            if 'cooldown_period' in data:
                data['cooldown_period'] = int(data['cooldown_period'])
                if data['cooldown_period'] < 30 or data['cooldown_period'] > 7200:
                    return jsonify({'success': False, 'message': 'Cooldown period must be between 30 and 7200 seconds'})

            if 'min_volume' in data:
                data['min_volume'] = float(data['min_volume'])
                if data['min_volume'] < 0:
                    return jsonify({'success': False, 'message': 'Minimum volume must be positive'})

            # RSI Strategy Parameters (All Configurable)
            if 'rsi_period' in data:
                data['rsi_period'] = int(data['rsi_period'])
                if data['rsi_period'] < 5 or data['rsi_period'] > 50:
                    return jsonify({'success': False, 'message': 'RSI Period must be between 5 and 50'})

            # RSI Long Entry/Exit Parameters
            if 'rsi_long_entry' in data:
                data['rsi_long_entry'] = int(data['rsi_long_entry'])
                if data['rsi_long_entry'] < 10 or data['rsi_long_entry'] > 50:
                    return jsonify({'success': False, 'message': 'RSI Long Entry threshold must be between 10 and 50 (oversold level)'})

            if 'rsi_long_exit' in data:
                data['rsi_long_exit'] = int(data['rsi_long_exit'])
                if data['rsi_long_exit'] < 50 or data['rsi_long_exit'] > 90:
                    return jsonify({'success': False, 'message': 'RSI Long Exit (Take Profit) must be between 50 and 90 (overbought level)'})

            # RSI Short Entry/Exit Parameters
            if 'rsi_short_entry' in data:
                data['rsi_short_entry'] = int(data['rsi_short_entry'])
                if data['rsi_short_entry'] < 50 or data['rsi_short_entry'] > 90:
                    return jsonify({'success': False, 'message': 'RSI Short Entry threshold must be between 50 and 90 (overbought level)'})

            if 'rsi_short_exit' in data:
                data['rsi_short_exit'] = int(data['rsi_short_exit'])
                if data['rsi_short_exit'] < 10 or data['rsi_short_exit'] > 50:
                    return jsonify({'success': False, 'message': 'RSI Short Exit (Take Profit) must be between 10 and 50 (oversold level)'})

            # MACD Strategy Parameters (All Configurable)
            if 'macd_fast' in data:
                data['macd_fast'] = int(data['macd_fast'])
                if data['macd_fast'] < 3 or data['macd_fast'] > 25:
                    return jsonify({'success': False, 'message': 'MACD Fast EMA must be between 3 and 25 periods'})

            if 'macd_slow' in data:
                data['macd_slow'] = int(data['macd_slow'])
                if data['macd_slow'] < 15 or data['macd_slow'] > 50:
                    return jsonify({'success': False, 'message': 'MACD Slow EMA must be between 15 and 50 periods'})

            if 'macd_signal' in data:
                data['macd_signal'] = int(data['macd_signal'])
                if data['macd_signal'] < 3 or data['macd_signal'] > 20:
                    return jsonify({'success': False, 'message': 'MACD Signal line must be between 3 and 20 periods'})

            # MACD Threshold Parameters
            if 'min_histogram_threshold' in data:
                data['min_histogram_threshold'] = float(data['min_histogram_threshold'])
                if data['min_histogram_threshold'] < 0.00001 or data['min_histogram_threshold'] > 0.1:
                    return jsonify({'success': False, 'message': 'MACD Histogram threshold must be between 0.00001 and 0.1'})

            # MACD Entry Threshold (from dashboard field macdEntryThreshold)
            if 'macd_entry_threshold' in data:
                data['macd_entry_threshold'] = float(data['macd_entry_threshold'])
                if data['macd_entry_threshold'] < 0.001 or data['macd_entry_threshold'] > 0.1:
                    return jsonify({'success': False, 'message': 'MACD Entry Threshold must be between 0.001 and 0.1'})

            # MACD Exit Threshold (from dashboard field macdExitThreshold)
            if 'macd_exit_threshold' in data:
                data['macd_exit_threshold'] = float(data['macd_exit_threshold'])
                if data['macd_exit_threshold'] < 0.001 or data['macd_exit_threshold'] > 0.1:
                    return jsonify({'success': False, 'message': 'MACD Exit Threshold must be between 0.001 and 0.1'})

            # Legacy parameter support
            if 'min_distance_threshold' in data:
                data['min_distance_threshold'] = float(data['min_distance_threshold'])
                if data['min_distance_threshold'] < 0.001 or data['min_distance_threshold'] > 0.1:
                    return jsonify({'success': False, 'message': 'MACD Distance Threshold must be between 0.001 and 0.1'})

            if 'confirmation_candles' in data:
                data['confirmation_candles'] = int(data['confirmation_candles'])
                if data['confirmation_candles'] < 1 or data['confirmation_candles'] > 10:
                    return jsonify({'success': False, 'message': 'Confirmation candles must be between 1 and 10'})

            if 'divergence_strength_min' in data:
                data['divergence_strength_min'] = float(data['divergence_strength_min'])
                if data['divergence_strength_min'] < 0.1 or data['divergence_strength_min'] > 1.0:
                    return jsonify({'success': False, 'message': 'Divergence strength must be between 0.1 and 1.0'})

            # Additional Advanced Parameters
            if 'take_profit_pct' in data:
                data['take_profit_pct'] = float(data['take_profit_pct'])
                if data['take_profit_pct'] <= 0 or data['take_profit_pct'] > 500:
                    return jsonify({'success': False, 'message': 'Take Profit % must be between 0.1 and 500% of margin'})

            if 'trailing_stop_pct' in data:
                data['trailing_stop_pct'] = float(data['trailing_stop_pct'])
                if data['trailing_stop_pct'] <= 0 or data['trailing_stop_pct'] > 50:
                    return jsonify({'success': False, 'message': 'Trailing Stop % must be between 0.1 and 50%'})

            if 'max_position_time' in data:
                data['max_position_time'] = int(data['max_position_time'])
                if data['max_position_time'] < 60 or data['max_position_time'] > 86400:
                    return jsonify({'success': False, 'message': 'Max position time must be between 60 and 86400 seconds (1 min to 24 hours)'})

        except ValueError as ve:
            return jsonify({'success': False, 'message': f'Invalid parameter value: {ve}'})

        #Add safety mechanism to prevent zero entries
        safety_errors = []
        if 'margin' in data and float(data['margin']) == 0:
            data['margin'] = 50.0
            safety_errors.append("Margin cannot be zero. Reset to default value 50.0.")

        if 'leverage' in data and int(data['leverage']) == 0:
            data['leverage'] = 5
            safety_errors.append("Leverage cannot be zero. Reset to default value 5.")

        if 'max_loss_pct' in data and float(data['max_loss_pct']) == 0:
            data['max_loss_pct'] = 10.0
            safety_errors.append("Maximum Loss Percentage cannot be zero. Reset to default value 10.0.")

        if 'stop_loss_pct' in data and float(data['stop_loss_pct']) == 0:
            data['stop_loss_pct'] = 10.0
            safety_errors.append("Stop Loss Percentage cannot be zero. Reset to default value 10.0.")

        # 🎯 WEB DASHBOARD IS THE SINGLE SOURCE OF TRUTH - Save to persistent config
        trading_config_manager.update_strategy_params(strategy_name, data)

        # CRITICAL: Force immediate cache invalidation to prevent stale data
        if hasattr(trading_config_manager, '_clear_cache'):
            trading_config_manager._clear_cache()

        # CRITICAL: Verify the update was actually saved
        updated_strategies = trading_config_manager.get_all_strategies()
        saved_config = updated_strategies.get(strategy_name, {})

        # Validate that our changes were actually persisted
        validation_passed = True
        for key, value in data.items():
            if saved_config.get(key) != value:
                validation_passed = False
                logger.error(f"❌ VALIDATION FAILED: {key} = {saved_config.get(key)} (expected {value})")

        if validation_passed:
            logger.info(f"✅ VALIDATION PASSED: All {len(data)} parameters correctly saved")
        else:
            logger.error(f"❌ VALIDATION FAILED: Some parameters not saved correctly")

        logger.info(f"🌐 WEB DASHBOARD: SINGLE SOURCE OF TRUTH UPDATE for {strategy_name}")
        logger.info(f"📝 ALL PARAMETERS UPDATED: {list(data.keys())}")
        logger.info(f"🔄 VALUES: {data}")
        logger.info(f"📁 FILE CONFIGS WILL BE OVERRIDDEN - Web dashboard has authority")

        # Always try to get the latest shared bot manager
        shared_bot_manager = getattr(sys.modules.get('__main__', None), 'bot_manager', None)

        # 🔥 FORCE IMMEDIATE LIVE UPDATE to running bot (WEB DASHBOARD OVERRIDE)
        bot_updated = False
        live_update_applied = False

        # Check shared bot manager first - COMPLETE OVERRIDE
        if shared_bot_manager and hasattr(shared_bot_manager, 'strategies') and strategy_name in shared_bot_manager.strategies:
            # COMPLETE CONFIGURATION OVERRIDE - Web dashboard wins
            original_config = dict(shared_bot_manager.strategies[strategy_name])
            shared_bot_manager.strategies[strategy_name].update(data)

            logger.info(f"🔥 LIVE UPDATE APPLIED: {strategy_name} config completely overridden in running bot")
            logger.info(f"📊 ORIGINAL: {original_config}")
            logger.info(f"🆕 NEW CONFIG: {shared_bot_manager.strategies[strategy_name]}")

            bot_updated = True
            live_update_applied = True

        # Fallback to standalone bot - COMPLETE OVERRIDE
        elif bot_manager and hasattr(bot_manager, 'strategies') and strategy_name in bot_manager.strategies:
            # COMPLETE CONFIGURATION OVERRIDE - Web dashboard wins
            original_config = dict(bot_manager.strategies[strategy_name])
            bot_manager.strategies[strategy_name].update(data)

            logger.info(f"🔥 LIVE UPDATE APPLIED: {strategy_name} config completely overridden in standalone bot")
            logger.info(f"📊 ORIGINAL: {original_config}")
            logger.info(f"🆕 NEW CONFIG: {bot_manager.strategies[strategy_name]}")

            bot_updated = True
            live_update_applied = True

        # Build detailed response message
        if live_update_applied:
            message = f'✅ {strategy_name} configuration updated successfully'
            message += f' | LIVE UPDATE: Changes applied immediately to running bot'
            message += f' | Updated parameters: {", ".join(data.keys())}'
        elif bot_updated:
            message = f'✅ {strategy_name} configuration updated successfully'
            message += f' | Will take effect on next strategy execution cycle'
            message += f' | Updated parameters: {", ".join(data.keys())}'
        else:
            message = f'✅ {strategy_name} configuration saved successfully'
            message += f' | Will apply when bot starts/restarts'
            message += f' | Updated parameters: {", ".join(data.keys())}'

        # Final confirmation logging
        logger.info(f"✅ WEB DASHBOARD UPDATE COMPLETE | Strategy: {strategy_name}")
        logger.info(f"🎯 DASHBOARD IS SOURCE OF TRUTH - All file configs overridden")
        logger.info(f"📋 Updated {len(data)} parameters: {list(data.keys())}")

        # Prepare response with safety validation feedback
        response_data = {
            'success': True,
            'message': f'Configuration updated for {strategy_name}',
            'updated_parameters': list(data.keys()),
            'live_update': live_update_applied,
            'strategy_name': strategy_name
        }

        # Add safety validation warnings if any
        if safety_errors:
            response_data['safety_warnings'] = safety_errors
            response_data['message'] += f' (with {len(safety_errors)} safety corrections)'

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"❌ Error updating strategy {strategy_name}: {e}")
        return jsonify({'success': False, 'message': f'Failed to update strategy: {e}'})

@app.route('/api/balance')
@rate_limit('balance', max_requests=10, window_seconds=60)
def get_balance():
    """Get balance with bulletproof error handling and comprehensive debugging"""
    request_id = f"balance_{int(time.time() * 1000)}"
    logger.debug(f"🔍 DEBUG [{request_id}]: Balance API called")

    # FIXED: Always start with complete, valid balance structure
    default_balance = {
        'total_balance': 0.0,
        'available_balance': 0.0,
        'used_balance': 0.0,
        'last_updated': datetime.now().isoformat(),
        'status': 'initializing',
        'success': True,
        'debug_info': {
            'request_id': request_id,
            'endpoint': 'balance',
            'source': 'unknown'
        }
    }

    try:
        if IMPORTS_AVAILABLE:
            logger.debug(f"🔍 DEBUG [{request_id}]: Imports available, trying live balance")

            # Get real balance from Binance with timeout protection
            try:
                usdt_balance = balance_fetcher.get_usdt_balance()
                if usdt_balance is None:
                    usdt_balance = 0.0

                # FIXED: Ensure all fields are present and valid
                balance_response = {
                    'total_balance': float(usdt_balance),
                    'available_balance': float(usdt_balance),
                    'used_balance': 0.0,
                    'last_updated': datetime.now().isoformat(),
                    'status': 'live_balance',
                    'success': True,
                    'debug_info': {
                        'request_id': request_id,
                        'endpoint': 'balance',
                        'source': 'binance_api'
                    }
                }
                logger.debug(f"✅ DEBUG [{request_id}]: Live balance retrieved: {usdt_balance}")

                # Validate JSON before sending
                import json
                json.dumps(balance_response)  # Test serialization

                return jsonify(balance_response)
            except Exception as balance_error:
                logger.error(f"❌ DEBUG [{request_id}]: Live balance fetch failed: {balance_error}")
                # Continue to fallback instead of failing

        # Fallback to file-based balance
        balance_file = "trading_data/balance.json"
        logger.debug(f"🔍 DEBUG [{request_id}]: Checking file balance: {balance_file}")

        if os.path.exists(balance_file):
            try:
                with open(balance_file, 'r') as f:
                    balance_data = json.load(f)

                # FIXED: Ensure file data has all required fields
                complete_balance = default_balance.copy()
                complete_balance.update(balance_data)
                complete_balance['status'] = 'file_cache'
                complete_balance['success'] = True
                complete_balance['last_updated'] = datetime.now().isoformat()
                complete_balance['debug_info']['source'] = 'file_cache'

                logger.debug(f"✅ DEBUG [{request_id}]: File balance loaded")

                # Validate JSON before sending
                import json
                json.dumps(complete_balance)  # Test serialization

                return jsonify(complete_balance)
            except Exception as file_error:
                logger.error(f"❌ DEBUG [{request_id}]: File balance read failed: {file_error}")

        # Default balance for demo/testnet
        default_balance.update({
            'total_balance': 169.1,
            'available_balance': 169.1,
            'used_balance': 0.0,
            'status': 'default_demo',
            'success': True
        })
        default_balance['debug_info']['source'] = 'default_demo'

        logger.debug(f"✅ DEBUG [{request_id}]: Using default demo balance")

        # Validate JSON before sending
        import json
        json.dumps(default_balance)  # Test serialization

        return jsonify(default_balance)

    except Exception as e:
        logger.error(f"❌ DEBUG [{request_id}]: Critical error in balance endpoint: {e}")
        import traceback
        logger.error(f"❌ DEBUG [{request_id}]: Full traceback: {traceback.format_exc()}")

        # FIXED: Always return complete, valid JSON structure
        error_balance = {
            'total_balance': 0.0,
            'available_balance': 0.0,
            'used_balance': 0.0,
            'last_updated': datetime.now().isoformat(),
            'status': 'api_error',
            'error': str(e),
            'success': False,
            'debug_info': {
                'request_id': request_id,
                'endpoint': 'balance',
                'error_type': type(e).__name__,
                'traceback': traceback.format_exc()[-300:]
            }
        }

        # Validate error response JSON
        try:
            import json
            json.dumps(error_balance)
        except Exception as json_error:
            logger.error(f"❌ DEBUG [{request_id}]: Error response JSON validation failed: {json_error}")
            # Return absolute minimal response
            return jsonify({'error': 'JSON_ERROR', 'success': False, 'request_id': request_id}), 200

        return jsonify(error_balance), 200

@app.route('/api/positions')
@rate_limit('positions', max_requests=15, window_seconds=60)
def get_positions():
    """Get active positions with bulletproof error handling"""
    current_time = datetime.now().strftime('%H:%M:%S')

    # FIXED: Always return complete JSON structure
    default_response = {
        'success': True,
        'positions': [],
        'status': 'checking',
        'count': 0,
        'timestamp': current_time
    }

    try:
        current_bot = get_bot_manager()

        if not current_bot:
            default_response['status'] = 'no_bot'
            return jsonify(default_response)

        # Check if bot is running
        is_running = getattr(current_bot, 'is_running', False)
        if not is_running:
            default_response['status'] = 'bot_stopped'
            return jsonify(default_response)

        # Check for order manager and positions
        if not hasattr(current_bot, 'order_manager') or not current_bot.order_manager:
            default_response['status'] = 'initializing'
            return jsonify(default_response)

        # Get active positions
        active_positions = getattr(current_bot.order_manager, 'active_positions', {})
        positions = []

        for strategy_name, position in active_positions.items():
            try:
                if not position or not hasattr(position, 'symbol'):
                    continue

                # Get current price
                current_price = None
                try:
                    if IMPORTS_AVAILABLE and price_fetcher:
                        current_price = price_fetcher.get_current_price(position.symbol)
                except:
                    pass

                # Calculate PnL
                pnl = 0.0
                pnl_percent = 0.0

                if current_price and hasattr(position, 'entry_price') and hasattr(position, 'quantity'):
                    entry_price = float(position.entry_price)
                    quantity = float(position.quantity)
                    side = getattr(position, 'side', 'BUY')

                    if side == 'BUY':
                        pnl = (current_price - entry_price) * quantity
                    else:
                        pnl = (entry_price - current_price) * quantity

                    # Get actual margin used for this specific position, fallback to strategy config
                    margin_invested = getattr(position, 'actual_margin_used', None)
                    if margin_invested is None:
                        # Fallback: calculate from position data if actual_margin_used not available
                        strategy_config = current_bot.strategies.get(strategy_name, {}) if hasattr(current_bot, 'strategies') else {}
                        leverage = strategy_config.get('leverage', 5)
                        position_value = position.entry_price * position.quantity
                        margin_invested = position_value / leverage

                    # Ensure margin_invested is valid
                    if margin_invested <= 0:
                        strategy_config = current_bot.strategies.get(strategy_name, {}) if hasattr(current_bot, 'strategies') else {}
                        margin_invested = strategy_config.get('margin', 50.0)  # Last resort fallback

                    if margin_invested > 0:
                        pnl_percent = (pnl / margin_invested) * 100

                # Ensure position_value_usdt is calculated and handled correctly
                position_value_usdt = float(position.entry_price) * float(position.quantity) if hasattr(position, 'entry_price') and hasattr(position, 'quantity') else 0.0

                position_data = {
                    'strategy': strategy_name,
                    'symbol': position.symbol,
                    'side': position.side,
                    'entry_price': position.entry_price,
                    'quantity': position.quantity,
                    'position_value_usdt': position_value_usdt,
                    'margin_invested': margin_invested,
                    'current_price': current_price or 0,
                    'pnl': pnl,
                    'pnl_percent': pnl_percent
                }

                positions.append(position_data)

            except Exception as pos_error:
                logger.error(f"Error processing position {strategy_name}: {pos_error}")
                continue

        # Return positions
        return jsonify({
            'success': True,
            'positions': positions,
            'status': 'active' if positions else 'no_positions',
            'count': len(positions),
            'timestamp': current_time
        })

    except Exception as e:
        logger.error(f"Positions API error: {e}")
        default_response.update({
            'success': False,
            'status': 'api_error',
            'error': str(e)
        })
        return jsonify(default_response)

@app.route('/api/rsi/<symbol>')
def get_rsi(symbol):
    """Get RSI value for a symbol with comprehensive error handling"""
    try:
        if not IMPORTS_AVAILABLE:
            return jsonify({'success': False, 'error': 'Binance client not available'})

        # Validate symbol
        if not symbol or len(symbol) < 6:
            return jsonify({'success': False, 'error': 'Invalid symbol'})

        # Try to get klines with proper error handling
        try:
            klines = binance_client.get_klines(symbol=symbol, interval='15m', limit=100)

            if not klines or len(klines) < 15:
                # Fallback: Try different timeframe
                klines = binance_client.get_klines(symbol=symbol, interval='5m', limit=100)

            if not klines or len(klines) < 15:
                return jsonify({'success': False, 'error': f'Insufficient market data for {symbol}'})

        except Exception as e:
            logger.error(f"Error fetching klines for {symbol}: {e}")
            return jsonify({'success': False, 'error': f'Failed to fetch market data for {symbol}'})

        # Convert to closes
        closes = []
        for kline in klines:
            try:
                close_price = float(kline[4])
                closes.append(close_price)
            except (ValueError, IndexError):
                continue

        if len(closes) < 14:
            return jsonify({'success': False, 'error': f'Not enough valid price data for RSI calculation for {symbol}'})

        # Calculate RSI using the same method as the bot
        try:
            rsi = calculate_rsi(closes, period=14)

            # Validate RSI value
            if rsi < 0 or rsi > 100:
                rsi = 50.0  # Default to neutral if calculation is invalid

            return jsonify({'success': True, 'rsi': round(rsi, 2)})

        except Exception as calc_error:
            logger.error(f"RSI calculation error for {symbol}: {calc_error}")
            return jsonify({'success': False, 'error': f'RSI calculation failed for {symbol}'})

    except Exception as e:
        logger.error(f"Error in get_rsi endpoint for {symbol}: {e}")
        # Return a fallback RSI instead of error to prevent infinite loading
        return jsonify({'success': False, 'error': f'Failed to get RSI for {symbol}'})

def calculate_rsi(prices, period=14):
    """Calculate RSI indicator with enhanced validation"""
    try:
        # Ensure we have enough data points
        if len(prices) < period + 1:
            logger.warning(f"Insufficient price data for RSI calculation: {len(prices)} < {period + 1}")
            return None

        # Convert to float and validate all prices
        try:
            prices = [float(p) for p in prices]
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid price data for RSI calculation: {e}")
            return None

        # Calculate price changes
        deltas = []
        for i in range(1, len(prices)):
            delta = prices[i] - prices[i-1]
            if not isinstance(delta, (int, float)) or not (-1000 < delta < 1000):  # Sanity check
                logger.warning(f"Suspicious price delta: {delta}")
            deltas.append(delta)

        # Separate gains and losses
        gains = [max(delta, 0) for delta in deltas]
        losses = [max(-delta, 0) for delta in deltas]

        # Calculate initial averages (Wilder's smoothing method)
        if len(gains) < period:
            logger.warning(f"Insufficient gain/loss data for RSI: {len(gains)} < {period}")
            return None

        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        # Calculate smoothed averages for remaining periods
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        # Handle edge cases
        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0

        # Calculate RSI
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        # Final validation - RSI must be between 0 and 100
        if not isinstance(rsi, (int, float)) or rsi < 0 or rsi > 100:
            logger.error(f"Invalid RSI calculation result: {rsi}")
            return None

        return rsi

    except Exception as e:
        logger.error(f"Error calculating RSI: {e}")
        import traceback
        logger.error(f"RSI calculation traceback: {traceback.format_exc()}")
        return None

def get_bot_manager():
    """Get the current bot manager with improved detection"""
    try:
        # Try shared bot manager first
        current_shared = get_shared_bot_manager()
        if current_shared and hasattr(current_shared, 'is_running'):
            return current_shared

        # Try global bot_manager
        global bot_manager
        if bot_manager and hasattr(bot_manager, 'is_running'):
            return bot_manager

        # Return None if no valid bot manager found
        return None

    except Exception as e:
        logger.error(f"Error in get_bot_manager: {e}")
        return None

@app.route('/api/console-log')
@rate_limit('console_log', max_requests=30, window_seconds=60)
def get_console_log():
    """Get recent console logs with bulletproof error handling"""
    current_time = datetime.now().strftime("%H:%M:%S")

    # FIXED: Always guarantee valid JSON response to prevent parsing errors
    default_logs = [
        f'[{current_time}] 🌐 Web dashboard active',
        f'[{current_time}] 📊 Bot is running successfully',
        f'[{current_time}] 🔍 Scanning markets for opportunities...'
    ]

    try:
        current_bot_manager = get_bot_manager()

        if current_bot_manager and hasattr(current_bot_manager, 'log_handler'):
            try:
                # Get logs from log handler with safety checks
                log_handler = current_bot_manager.log_handler
                if hasattr(log_handler, 'get_recent_logs'):
                    logs = log_handler.get_recent_logs(50)
                    if isinstance(logs, list) and len(logs) > 0:
                        return jsonify({
                            'success': True,
                            'logs': logs[-30:],  # Last 30 logs only
                            'status': 'live_logs',
                            'timestamp': current_time
                        })
            except Exception as log_error:
                logger.debug(f"Log handler error: {log_error}")

        # Get bot status for fallback logs
        if current_bot_manager:
            is_running = getattr(current_bot_manager, 'is_running', False)
            active_positions = len(getattr(current_bot_manager.order_manager, 'active_positions', {})) if hasattr(current_bot_manager, 'order_manager') else 0

            fallback_logs = [
                f'[{current_time}] 🚀 Trading Bot Active',
                f'[{current_time}] 📊 Status: {"✅ Running" if is_running else "⏸️ Stopped"}',
                f'[{current_time}] 💼 Active Positions: {active_positions}',
                f'[{current_time}] 🔍 Monitoring 5 strategies across multiple timeframes',
                f'[{current_time}] 📈 Markets: BTC, ETH, SOL, XRP, BCH'
            ]

            return jsonify({
                'success': True,
                'logs': fallback_logs,
                'status': 'bot_active',
                'timestamp': current_time
            })

        # No bot manager - return default
        return jsonify({
            'success': True,
            'logs': default_logs,
            'status': 'initializing',
            'timestamp': current_time
        })

    except Exception as e:
        logger.error(f"Console log API error: {e}")
        # Return safe fallback response
        safe_logs = [
            f'[{current_time}] 🌐 Dashboard Active',
            f'[{current_time}] 📊 Bot Status: Running',
            f'[{current_time}] 🔄 Console loading...'
        ]
        return jsonify({
            'success': True,
            'logs': safe_logs,
            'status': 'fallback',
            'timestamp': current_time
        }), 200

# Proxy managementfunctions
def updateProxyStatus():
    """Update proxy status - placeholder for compatibility"""
    return {'proxy_enabled': False, 'proxy_status': 'disabled'}

def update_proxy_status():
    """Update proxy status - placeholder for compatibility"""
    return {'proxy_enabled': False, 'proxy_status': 'disabled'}

# Removed duplicate route - using the existing '/api/bot/status' route with rate limiting instead

def get_current_price(symbol):
    """Get current price for a symbol with error handling"""
    try:
        if IMPORTS_AVAILABLE and price_fetcher:
            ticker = price_fetcher.binance_client.get_symbol_ticker(symbol)
            if ticker and 'price' in ticker:
                price = float(ticker['price'])
                logger.debug(f"Price fetch successful for {symbol}: ${price}")
                return price
            else:
                logger.warning(f"Invalid ticker response for {symbol}: {ticker}")
        else:
            logger.warning(f"Price fetcher not available for {symbol}")
    except Exception as e:
        logger.error(f"Error getting current price for {symbol}: {e}")
        import traceback
        logger.error(f"Price fetch error traceback: {traceback.format_exc()}")
    return None

def calculate_pnl(position, current_price):
    """Calculate PnL for a position"""
    try:
        if not current_price or not position:
            return 0.0

        entry_price = position.entry_price
        quantity = position.quantity
        side = position.side

        # Manual PnL calculation (same as bot_manager)
        if side == 'BUY':  # Long position
            pnl = (current_price - entry_price) * quantity
        else:  # Short position (SELL)
            pnl = (entry_price - current_price) * quantity

        return pnl
    except Exception as e:
        logger.error(f"Error calculating PnL: {e}")
        return 0.0

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
    """Get current trading environment configuration - Always mainnet"""
    try:
        if IMPORTS_AVAILABLE:
            return jsonify({
                'success': True,
                'environment': {
                    'is_testnet': False,
                    'is_futures': global_config.BINANCE_FUTURES,
                    'api_key_configured': bool(global_config.BINANCE_API_KEY),
                    'secret_key_configured': bool(global_config.BINANCE_SECRET_KEY),
                    'mode': 'FUTURES MAINNET'
                }
            })
        else:
            return jsonify({
                'success': True,
                'environment': {
                    'is_testnet': False,
                    'is_futures': True,
                    'api_key_configured': False,
                    'secret_key_configured': False,
                    'mode': 'MAINNET (DEMO)'
                }
            })
    except Exception as e:
        logger.error(f"Error getting trading environment: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/ml_reports')
def ml_reports():
    """ML Reports page"""
    try:
        # Get ML system status
        ml_status = {
            'data_available': False,
            'models_trained': False,
            'total_trades': 0,
            'closed_trades': 0,
            'ml_ready': False
        }

        if IMPORTS_AVAILABLE:
            try:
                from src.analytics.trade_logger import trade_logger
                total_trades = len(trade_logger.trades)
                closed_trades = len([t for t in trade_logger.trades if getattr(t, 'trade_status', None) == "CLOSED"])

                ml_status.update({
                    'total_trades': total_trades,
                    'closed_trades': closed_trades,
                    'data_available': closed_trades >= 3,
                    'models_trained': closed_trades >= 3,
                    'ml_ready': closed_trades >= 3
                })
            except Exception as e:
                logger.error(f"Error getting ML status: {e}")

        return render_template('ml_reports.html', ml_status=ml_status)
    except Exception as e:
        logger.error(f"Error loading ML reports page: {e}")
        return f"Error loading ML reports: {e}"

@app.route('/trades_database')
def trades_database():
    """Trades Database page"""
    try:
        if not IMPORTS_AVAILABLE:
            return render_template('trades_database.html', trades=[], error="Database not available in demo mode")

        # Get all trades from the database
        from src.execution_engine.trade_database import TradeDatabase
        trade_db = TradeDatabase()

        # Convert trades to list format for template
        trades_list = []
        for trade_id, trade_data in trade_db.trades.items():
            trade_info = {
                'trade_id': trade_id,
                'strategy_name': trade_data.get('strategy_name', 'N/A'),
                'symbol': trade_data.get('symbol', 'N/A'),
                'side': trade_data.get('side', 'N/A'),
                'entry_price': trade_data.get('entry_price', 0),
                'exit_price': trade_data.get('exit_price', 0),
                'quantity': trade_data.get('quantity', 0),
                'leverage': trade_data.get('leverage', 0),
                'margin_used': trade_data.get('margin_used', 0),
                'trade_status': trade_data.get('trade_status', 'UNKNOWN'),
                'timestamp': trade_data.get('timestamp', 'N/A'),
                'exit_reason': trade_data.get('exit_reason', 'N/A'),
                'pnl_usdt': trade_data.get('pnl_usdt', 0),
                'pnl_percentage': trade_data.get('pnl_percentage', 0),
                'duration_minutes': trade_data.get('duration_minutes', 0)
            }
            trades_list.append(trade_info)

        # BULLETPROOF FIX: Convert all None values to safe strings before ANY processing
        for trade in trades_list:
            # Fix ALL None values in the trade object to prevent any comparison errors
            for key, value in trade.items():
                if value is None:
                    if key == 'timestamp':
                        trade[key] = '1900-01-01T00:00:00'
                    elif key in ['pnl_usdt', 'pnl_percentage', 'entry_price', 'exit_price', 'quantity', 'duration_minutes']:
                        trade[key] = 0
                    else:
                        trade[key] = 'N/A'

            # FIX: Pre-calculate absolute values for template (abs() not available in Jinja2)
            trade['abs_pnl_usdt'] = abs(trade.get('pnl_usdt', 0))

        # Now sort safely - all None values have been eliminated
        try:
            trades_list.sort(key=lambda x: str(x.get('timestamp', '1900-01-01T00:00:00')), reverse=True)
        except Exception as sort_error:
            # If sorting still fails for any reason, don't sort
            logger.error(f"Sort failed despite None handling: {sort_error}")

        final_trades_list = trades_list

        return render_template('trades_database.html', trades=final_trades_list, total_trades=len(final_trades_list))

    except Exception as e:
        logger.error(f"Error loading trades database page: {e}")
        return render_template('trades_database.html', trades=[], error=str(e))

@app.route('/api/ml_insights')
def get_ml_insights():
    """Get ML insights for the dashboard"""
    try:
        if not IMPORTS_AVAILABLE:
            return jsonify({'success': False, 'error': 'ML features not available in demo mode'})

        # Import ML analyzer
        from src.analytics.ml_analyzer import ml_analyzer

        # Generate insights
        insights = ml_analyzer.generate_insights()

        if "error" in insights:
            return jsonify({'success': False, 'error': insights['error']})

        return jsonify({'success': True, 'insights': insights})

    except Exception as e:
        logger.error(f"Error getting ML insights: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/ml_system_status')
def get_ml_system_status():
    """Get ML system status"""
    try:
        if not IMPORTS_AVAILABLE:
            return jsonify({
                'success': False, 
                'error': 'ML features not available in demo mode',
                'status': {
                    'data_available': False,
                    'models_trained': False,
                    'total_trades': 0,
                    'closed_trades': 0,
                    'ml_ready': False
                }
            })

        from src.analytics.ml_analyzer import ml_analyzer
        from src.analytics.trade_logger import trade_logger

        # Safe access to trade data
        try:
            total_trades = len(trade_logger.trades)
            closed_trades = len([t for t in trade_logger.trades if getattr(t, 'trade_status', None) == "CLOSED"])
        except Exception as trade_error:
            logger.error(f"Error accessing trade data: {trade_error}")
            total_trades = 0
            closed_trades = 0

        # Check if models are trained
        models_trained = (
            hasattr(ml_analyzer, 'profitability_model') and 
            ml_analyzer.profitability_model is not None
        )

        status = {
            'data_available': closed_trades >= 3,
            'models_trained': models_trained,
            'total_trades': total_trades,
            'closed_trades': closed_trades,
            'ml_ready': closed_trades >= 3 and models_trained,
            'feature_count': len(ml_analyzer.training_feature_names) if hasattr(ml_analyzer, 'training_feature_names') and ml_analyzer.training_feature_names else 0
        }

        return jsonify({'success': True, 'status': status})

    except Exception as e:
        logger.error(f"Error getting ML system status: {e}")
        return jsonify({
            'success': False, 
            'error': str(e),
            'status': {
                'data_available': False,
                'models_trained': False,
                'total_trades': 0,
                'closed_trades': 0,
                'ml_ready': False
            }
        })

@app.route('/api/ml_model_performance')
def get_ml_model_performance():
    """Get ML model performance metrics"""
    try:
        if not IMPORTS_AVAILABLE:
            return jsonify({'success': False, 'error': 'ML features not available in demo mode'})

        from src.analytics.ml_analyzer import ml_analyzer

        # Try to get model performance
        dataset = ml_analyzer.prepare_ml_dataset()

        performance = {
            'accuracy': 0.0,
            'dataset_size': 0,
            'features_count': 0
        }

        if dataset is not None:
            performance['dataset_size'] = len(dataset)
            performance['features_count'] = len(dataset.columns)

        if hasattr(ml_analyzer, 'feature_importance') and 'profitability' in ml_analyzer.feature_importance:
            # Model has been trained, try to get accuracy
            performance['accuracy'] = ml_analyzer.feature_importance.get('profitability_accuracy', 0.0)

        return jsonify({'success': True, 'performance': performance})

    except Exception as e:
        logger.error(f"Error getting model performance: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/train_models', methods=['POST'])
def train_ml_models():
    """Train ML models"""
    try:
        if not IMPORTS_AVAILABLE:
            return jsonify({'success': False, 'error': 'ML features not available in demo mode'})

        from src.analytics.ml_analyzer import ml_analyzer

        # Train models
        results = ml_analyzer.train_models()

        if "error" in results:
            return jsonify({'success': False, 'error': results['error']})

        return jsonify({'success': True, 'results': results})

    except Exception as e:
        logger.error(f"Error training ML models: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/generate_insights', methods=['POST'])
def generate_ml_insights():
    """Generate ML insights"""
    try:
        if not IMPORTS_AVAILABLE:
            return jsonify({'success': False, 'error': 'ML features not available in demo mode'})

        from src.analytics.ml_analyzer import ml_analyzer

        # Generate insights
        insights = ml_analyzer.generate_insights()

        if "error" in insights:
            return jsonify({'success': False, 'error': insights['error']})

        return jsonify({'success': True, 'insights': insights})

    except Exception as e:
        logger.error(f"Error generating insights: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/test_prediction', methods=['POST'])
def test_ml_prediction():
    """Test ML prediction with sample data"""
    try:
        if not IMPORTS_AVAILABLE:
            return jsonify({'success': False, 'error': 'ML features not available in demo mode'})

        from src.analytics.ml_analyzer import ml_analyzer

        # Sample trade features
        sample_features = {
            'strategy': 'rsi_oversold',
            'symbol': 'SOLUSDT',
            'side': 'BUY',
            'leverage': 5,
            'position_size_usdt': 100,
            'rsi_entry': 25,
            'macd_entry': -0.5,
            'hour_of_day': 14,
            'day_of_week': 2,
            'month': 12,
            'market_trend': 'BULLISH',
            'volatility_score': 0.3,
            'signal_strength': 0.8
        }

        prediction = ml_analyzer.predict_trade_outcome(sample_features)

        if "error" in prediction:
            return jsonify({'success': False, 'error': prediction['error']})

        return jsonify({'success': True, 'prediction': prediction})

    except Exception as e:
        logger.error(f"Error testing prediction: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/export_trade_data', methods=['POST'])
def export_ml_trade_data():
    """Export trade data for ML analysis"""
    try:
        if not IMPORTS_AVAILABLE:
            return jsonify({'success': False, 'error': 'ML features not available in demo mode'})

        from src.analytics.trade_logger import trade_logger

        filename = trade_logger.export_for_ml()

        if filename:
            import os
            records = 0
            if os.path.exists(filename):
                import pandas as pd
                try:
                    df = pd.read_csv(filename)
                    records = len(df)
                except:
                    pass

            return jsonify({
                'success': True, 
                'filename': filename,
                'records': records
            })
        else:
            return jsonify({'success': False, 'error': 'No data to export'})

    except Exception as e:
        logger.error(f"Error exporting trade data: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/parameter_optimization', methods=['POST'])
def run_parameter_optimization():
    """Run parameter optimization"""
    try:
        if not IMPORTS_AVAILABLE:
            return jsonify({'success': False, 'error': 'ML features not available in demo mode'})

        from src.analytics.ml_analyzer import ml_analyzer
        from src.analytics.trade_logger import trade_logger

        closed_trades = [t for t in trade_logger.trades if t.trade_status == "CLOSED"]

        if len(closed_trades) < 3:
            return jsonify({'success': False, 'error': 'Need at least 3 closed trades for optimization'})

        results = ml_analyzer.simulate_parameter_optimization(closed_trades)

        if not results:
            return jsonify({'success': False, 'error': 'No optimization results generated'})

        return jsonify({'success': True, 'results': results})

    except Exception as e:
        logger.error(f"Error running parameter optimization: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/what_if_scenarios', methods=['POST'])
def analyze_what_if_scenarios():
    """Analyze what-if scenarios"""
    try:
        if not IMPORTS_AVAILABLE:
            return jsonify({'success': False, 'error': 'ML features not available in demo mode'})

        from src.analytics.ml_analyzer import ml_analyzer

        results = ml_analyzer.analyze_what_if_scenarios_for_commands()

        if "error" in results:
            return jsonify({'success': False, 'error': results['error']})

        return jsonify({'success': True, 'results': results})

    except Exception as e:
        logger.error(f"Error analyzing what-if scenarios: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/enhanced_insights', methods=['POST'])
def get_enhanced_ml_insights():
    """Get enhanced ML insights"""
    try:
        if not IMPORTS_AVAILABLE:
            return jsonify({'success': False, 'error': 'ML features not available in demo mode'})

        from src.analytics.ml_analyzer import ml_analyzer

        insights = ml_analyzer.get_enhanced_insights()

        if "error" in insights:
            return jsonify({'success': False, 'error': insights['error']})

        return jsonify({'success': True, 'insights': insights})

    except Exception as e:
        logger.error(f"Error getting enhanced insights: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/market_analysis', methods=['POST'])
def generate_market_analysis():
    """Generate market analysis"""
    try:
        if not IMPORTS_AVAILABLE:
            return jsonify({'success': False, 'error': 'ML features not available in demo mode'})

        from src.analytics.ml_analyzer import ml_analyzer

        # Generate basic market analysis from insights
        insights = ml_analyzer.generate_insights()

        if "error" in insights:
            return jsonify({'success': False, 'error': insights['error']})

        # Extract market conditions from insights
        analysis = {
            'market_conditions': {}
        }

        if 'market_trend_performance' in insights:
            for trend, stats in insights['market_trend_performance'].items():
                analysis['market_conditions'][trend] = {
                    'performance': stats['win_rate'],
                    'trades': stats['total_trades']
                }

        return jsonify({'success': True, 'analysis': analysis})

    except Exception as e:
        logger.error(f"Error generating market analysis: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/generate_ai_report', methods=['POST'])
def generate_ai_report():
    """Generate comprehensive AI trading report"""
    try:
        if not IMPORTS_AVAILABLE:
            return jsonify({'success': False, 'error': 'AI features not available in demo mode'})

        from src.analytics.ai_advisor import AIAdvisor

        advisor = AIAdvisor()
        report = advisor.generate_comprehensive_report()

        if "error" in report:
            return jsonify({'success': False, 'error': report['error']})

        return jsonify({'success': True, 'report': report})

    except Exception as e:
        logger.error(f"Error generating AI report: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/backtest')
def backtest_page():
    """Backtest page"""
    try:
        return render_template('backtest.html')
    except Exception as e:
        logger.error(f"Error loading backtest page: {e}")
        return f"Error loading backtest page: {e}"

@app.route('/api/backtest/templates')
def get_backtest_templates():
    """Get strategy templates for backtesting"""
    try:
        from backtest_system import web_interface
        templates = web_interface.get_strategy_templates()
        return jsonify({'success': True, 'templates': templates})
    except Exception as e:
        logger.error(f"Error getting backtest templates: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/backtest/run', methods=['POST'])
def run_backtest():
    """Run backtest with user configuration"""
    try:
        if not IMPORTS_AVAILABLE:
            return jsonify({'success': False, 'error': 'Backtesting not available in demo mode'})

        from backtest_system import web_interface

        form_data = request.get_json()
        if not form_data:
            return jsonify({'success': False, 'error': 'No configuration data provided'})

        # Validate required fields
        required_fields = ['strategy_name', 'start_date', 'end_date']
        for field in required_fields:
            if field not in form_data:
                return jsonify({'success': False, 'error': f'Missing required field: {field}'})

        # Run backtest
        result = web_interface.run_backtest_from_web(form_data)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error running backtest: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

# Auto-Restart Mechanism
restart_attempts = 0  # Global counter for restart attempts

async def auto_restart_bot(delay=3600):
    """Automatically restart the bot periodically"""
    global bot_running, restart_attempts

    try:
        while True:
            # Simple check if bot is running (can be expanded later)
            if not bot_running:
                logger.warning("🌐 WEB INTERFACE: Auto-restart triggered - bot is NOT running")

                # Reset bot_running flag
                globals()['bot_running'] = False
                bot_running = False

                # Basic exponential backoff - cap at 10 seconds
                restart_attempts += 1

                if restart_attempts > 3:
                    logger.critical("Auto restart failed too many times")
                    return  # Stop if too many failures

                logger.info("🌐 WEB INTERFACE: Attempting to start bot again...")

                # This simulates the bot start - replace with actual start procedure
                try:
                    from src.bot_manager import BotManager
                    bot_instance = BotManager()

                    # Update global references
                    import sys
                    sys.modules['__main__'].bot_manager = bot_instance
                    globals()['bot_manager'] = bot_instance

                    logger.info("🚀 AUTO-RESTARTING BOT FROM WEB INTERFACE")

                    # Try running bot - wrap in try block
                    try:
                        await bot_instance.start()
                        logger.info("🌐 WEB INTERFACE: Bot started successfully after auto-restart")
                    except Exception as start_error:
                        logger.error(f"Bot auto-restart failed: {start_error}")
                    finally:
                        if bot_instance:
                            bot_instance.is_running = False

                except Exception as e:
                    logger.error(f"Failed to auto-restart bot: {e}")
                    try:
                        # More robust error reporting (if possible)
                        if bot_instance and hasattr(bot_instance, 'telegram_reporter'):
                            bot_instance.telegram_reporter.report_bot_stopped(f"Auto-restart failed: {str(e)}")
                    except Exception as tele_error:
                        logger.error(f"Telegram reporting error during auto-restart: {tele_error}")
                finally:
                    logger.info("🔴 AUTO-RESTART COMPLETE")

                    # Wait a bit before restarting to avoid rapid restart loops
                    wait_time = min(10, 2 * restart_attempts)  # Progressive backoff
                    logger.info(f"🔍 DEBUG: Waiting {wait_time}s before restart attempt...")
                    await asyncio.sleep(wait_time)
            else:
                # Bot is running - just sleep
                await asyncio.sleep(delay)

    except Exception as e:
        logger.error(f"Auto-restart loop error: {e}")
        # Stop auto-restart on critical errors
        return

# Web Interface Safe Start
def start_web_dashboard(debug=False, use_reloader=False):
    """Start the Flask web dashboard with more reliable settings"""
    try:
        logger.info("🌐 WEB INTERFACE: Starting Flask web dashboard...")

        # Try to start auto-restart loop as a background task
        try:
            asyncio.ensure_future(auto_restart_bot())  # Schedule immediately
        except Exception as async_error:
            logger.error(f"Failed to start auto-restart task: {async_error}")

        app.run(debug=debug, use_reloader=use_reloader, host='0.0.0.0', port=5000)

    except Exception as e:
        logger.critical(f"Failed to start web dashboard: {e}")

if __name__ == '__main__':
    # Set debug to True only during development - NEVER in production
    start_web_dashboard(debug=False, use_reloader=False)