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
                return jsonify({
                    'success': False,
                    'error': 'Rate limit exceeded',
                    'retry_after': int(limit_data['requests'][0] + limit_data['window'] - now)
                }), 429

            # Add current request
            limit_data['requests'].append(now)
            rate_limits[endpoint_key] = limit_data

            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Global bot instance - shared with main.py
bot_manager = None
bot_thread = None
bot_running = False

# Import the shared bot manager from main.py if it exists
import sys
shared_bot_manager = None

def get_shared_bot_manager():
    """Get the shared bot manager with proper error handling"""
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
                    'symbol': 'BTCUSDT', 'margin': 50.0, 'leverage': 5, 'timeframe': '15m',
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
@rate_limit('bot_status', max_requests=20, window_seconds=60)
def get_bot_status():
    """Get bot status with comprehensive error handling and fallback data"""
    try:
        # Always try to get the latest shared bot manager first
        import sys
        shared_bot_manager = getattr(sys.modules.get('__main__', None), 'bot_manager', None)

        # Initialize default response structure
        response_data = {
            'status': 'stopped',
            'message': 'Checking bot status...',
            'strategies': 0,
            'active_positions': 0,
            'running': False,
            'error': None
        }

        # Try shared bot manager first (from main.py)
        if shared_bot_manager:
            try:
                is_running = getattr(shared_bot_manager, 'is_running', False)
                strategies = getattr(shared_bot_manager, 'strategies', {})
                strategies_count = len(strategies) if strategies else 0

                # Safe access to active positions
                active_positions_count = 0
                if hasattr(shared_bot_manager, 'order_manager') and shared_bot_manager.order_manager:
                    try:
                        active_positions = getattr(shared_bot_manager.order_manager, 'active_positions', {})
                        active_positions_count = len(active_positions) if active_positions else 0
                    except Exception as pos_error:
                        logger.debug(f"Could not get active positions count: {pos_error}")
                        active_positions_count = 0

                response_data.update({
                    'status': 'running' if is_running else 'stopped',
                    'strategies': strategies_count,
                    'active_positions': active_positions_count,
                    'running': is_running,
                    'message': f'Bot {("running" if is_running else "stopped")} with {strategies_count} strategies'
                })

                logger.debug(f"API Status Success: {response_data}")
                return jsonify(response_data)
            except Exception as shared_error:
                logger.error(f"Error accessing shared bot manager: {shared_error}")
                # Continue to fallback logic

        # Fallback to standalone bot manager
        current_bot = globals().get('bot_manager', None)
        if current_bot:
            try:
                is_running = getattr(current_bot, 'is_running', False)
                strategies = getattr(current_bot, 'strategies', {})
                strategies_count = len(strategies) if strategies else 0

                # Safe access to active positions
                active_positions_count = 0
                if hasattr(current_bot, 'order_manager') and current_bot.order_manager:
                    try:
                        active_positions = getattr(current_bot.order_manager, 'active_positions', {})
                        active_positions_count = len(active_positions) if active_positions else 0
                    except Exception as pos_error:
                        logger.debug(f"Could not get active positions count: {pos_error}")
                        active_positions_count = 0

                response_data.update({
                    'status': 'running' if is_running else 'stopped',
                    'strategies': strategies_count,
                    'active_positions': active_positions_count,
                    'running': is_running,
                    'message': f'Standalone bot {("running" if is_running else "stopped")} with {strategies_count} strategies'
                })

                logger.debug(f"API Status Success: {response_data}")
                return jsonify(response_data)
            except Exception as standalone_error:
                logger.error(f"Error accessing standalone bot manager: {standalone_error}")

        # Final fallback - use configuration data if available
        if IMPORTS_AVAILABLE:
            try:
                strategies = trading_config_manager.get_all_strategies()
                strategies_count = len(strategies) if strategies else 0

                response_data.update({
                    'status': 'stopped',
                    'strategies': strategies_count,
                    'active_positions': 0,
                    'running': False,
                    'message': f'Bot stopped - {strategies_count} strategies configured'
                })
            except Exception as config_error:
                logger.error(f"Error getting strategies from config: {config_error}")
                response_data.update({
                    'message': 'Bot manager not available - using defaults'
                })

        logger.debug(f"API Status Fallback: {response_data}")
        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Critical error in get_bot_status endpoint: {e}")
        # Even in case of complete failure, return valid JSON structure
        fallback_response = {
            'status': 'error',
            'message': f'Status check failed: {str(e)}',
            'strategies': 0,
            'active_positions': 0,
            'running': False,
            'error': str(e)
        }
        return jsonify(fallback_response), 200  # Return 200 to prevent frontend errors

@app.route('/api/strategies')
def get_strategies():
    """Get all strategy configurations - WEB DASHBOARD IS SINGLE SOURCE OF TRUTH"""
    try:
        if IMPORTS_AVAILABLE:
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

                # Liquidity Reversal Strategy Specific Parameters
                elif 'liquidity' in name.lower() or 'reversal' in name.lower():
                    config.setdefault('lookback_candles', 100)
                    config.setdefault('liquidity_threshold', 0.02)
                    config.setdefault('reclaim_timeout', 5)
                    config.setdefault('min_volume_spike', 1.5)
                    config.setdefault('max_risk_per_trade', 0.5)
                    config.setdefault('stop_loss_buffer', 0.1)
                    config.setdefault('profit_target_multiplier', 2.0)
                    config.setdefault('swing_strength', 3)
                    config.setdefault('min_wick_ratio', 0.6)
                    config.setdefault('min_volume', 5000000)
                    config.setdefault('decimals', 2)
                    config.setdefault('cooldown_period', 600)

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
                    'min_histogram_threshold': 0.0001, 'min_distance_threshold': 0.005, 'confirmation_candles': 2
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
            return jsonify({'success': False, 'message': 'Strategy creation not available in demo mode'})

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
        if 'rsi' not in strategy_name.lower() and 'macd' not in strategy_name.lower():
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

            if 'min_distance_threshold' in data:
                data['min_distance_threshold'] = float(data['min_distance_threshold'])
                if data['min_distance_threshold'] < 0.0001 or data['min_distance_threshold'] > 10.0:
                    return jsonify({'success': False, 'message': 'MACD Distance threshold must be between 0.0001 and 10.0'})

            if 'confirmation_candles' in data:
                data['confirmation_candles'] = int(data['confirmation_candles'])
                if data['confirmation_candles'] < 1 or data['confirmation_candles'] > 10:
                    return jsonify({'success': False, 'message': 'Confirmation candles must be between 1 and 10'})

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

        # 🎯 WEB DASHBOARD IS THE SINGLE SOURCE OF TRUTH - Save to persistent config
        trading_config_manager.update_strategy_params(strategy_name, data)

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

        return jsonify({
            'success': True, 
            'message': message,
            'updated_parameters': list(data.keys()),
            'live_update': live_update_applied,
            'strategy_name': strategy_name
        })

    except Exception as e:
        logger.error(f"❌ Error updating strategy {strategy_name}: {e}")
        return jsonify({'success': False, 'message': f'Failed to update strategy: {e}'})

@app.route('/api/balance')
@rate_limit('balance', max_requests=10, window_seconds=60)
def get_balance():
    try:
        if IMPORTS_AVAILABLE:
            # Get real balance from Binance with timeout protection
            try:
                usdt_balance = balance_fetcher.get_usdt_balance()
                if usdt_balance is None:
                    usdt_balance = 0.0

                balance_response = {
                    'total_balance': float(usdt_balance),
                    'available_balance': float(usdt_balance),
                    'used_balance': 0.0,
                    'last_updated': datetime.now().isoformat(),
                    'status': 'success'
                }
                logger.debug(f"API Balance Success: {balance_response}")
                return jsonify(balance_response)
            except Exception as balance_error:
                logger.error(f"Error getting live balance: {balance_error}")
                # Continue to fallback instead of failing

        # Fallback to file-based balance
        balance_file = "trading_data/balance.json"
        if os.path.exists(balance_file):
            try:
                with open(balance_file, 'r') as f:
                    balance_data = json.load(f)
                balance_data['status'] = 'file_cache'
                logger.debug(f"API Balance File Cache: {balance_data}")
                return jsonify(balance_data)
            except Exception as file_error:
                logger.error(f"Error reading balance file: {file_error}")

        # Default balance for demo/testnet
        default_balance = {
            'total_balance': 169.1,
            'available_balance': 169.1,
            'used_balance': 0.0,
            'last_updated': datetime.now().isoformat(),
            'status': 'default'
        }
        logger.debug(f"API Balance Default: {default_balance}")
        return jsonify(default_balance)
    except Exception as e:
        logger.error(f"Critical error in balance endpoint: {e}")
        # Always return valid JSON to prevent frontend errors
        error_balance = {
            'total_balance': 0.0,
            'available_balance': 0.0,
            'used_balance': 0.0,
            'last_updated': datetime.now().isoformat(),
            'status': 'error',
            'error': f'Balance unavailable: {str(e)}'
        }
        return jsonify(error_balance), 200

@app.route('/api/positions')
@rate_limit('positions', max_requests=15, window_seconds=60)
def get_positions():
    """Get active positions"""
    try:
        positions = []

        # Try shared bot manager first
        current_bot = shared_bot_manager if shared_bot_manager else bot_manager

        if current_bot and hasattr(current_bot, 'order_manager') and current_bot.order_manager:
            # Create a safe copy to prevent "dictionary changed size during iteration" error
            active_positions = dict(current_bot.order_manager.active_positions)

            for strategy_name, position in active_positions.items():
                try:
                    # Check if this position has an anomaly (orphan/ghost trade)
                    anomaly_status = None
                    if hasattr(current_bot, 'anomaly_detector'):
                        anomaly_status = current_bot.anomaly_detector.get_anomaly_status(strategy_name)

                    # Get current price
                    current_price = None
                    if IMPORTS_AVAILABLE:
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
                    else:
                        # Add position without current price/PnL data
                        positions.append({
                            'strategy': position.strategy_name,
                            'symbol': position.symbol,
                            'side': position.side,
                            'entry_price': position.entry_price,
                            'current_price': None,
                            'quantity': position.quantity,
                            'position_value_usdt': position.entry_price * position.quantity,
                            'margin_invested': 0.0,
                            'pnl': 0.0,
                            'pnl_percent': 0.0,
                            'anomaly_status': anomaly_status
                        })
                except Exception as pos_error:
                    logger.error(f"Error processing position {strategy_name}: {pos_error}")
                    continue

        positions_response = {'success': True, 'positions': positions}
        logger.debug(f"API Positions Success: {len(positions)} positions")
        return jsonify(positions_response)
    except Exception as e:
        logger.error(f"Critical error in get_positions endpoint: {e}")
        error_response = {
            'success': False, 
            'error': f'Positions unavailable: {str(e)}', 
            'positions': []
        }
        return jsonify(error_response), 200

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
    """Get recent console log entries with enhanced error handling"""
    try:
        # Get bot manager from main module with multiple fallback methods
        bot_manager = None

        # Method 1: Check main module
        main_module = sys.modules.get('__main__')
        if main_module and hasattr(main_module, 'bot_manager'):
            bot_manager = main_module.bot_manager

        # Method 2: Check global bot_manager variable
        if not bot_manager and 'bot_manager' in globals():
            bot_manager = globals()['bot_manager']

        # Method 3: Check web_dashboard module
        if not bot_manager and hasattr(sys.modules.get('web_dashboard', {}), 'bot_manager'):
            bot_manager = sys.modules['web_dashboard'].bot_manager

        if bot_manager and hasattr(bot_manager, 'log_handler'):
            try:
                logs = bot_manager.log_handler.get_recent_logs(50)
                if logs and len(logs) > 0:
                    return jsonify({'logs': logs, 'status': 'success'})
            except Exception as log_error:
                # Log handler exists but failed - return minimal info
                return jsonify({
                    'logs': [f'[{datetime.now().strftime("%H:%M:%S")}] Log handler error (non-critical)'],
                    'status': 'partial',
                    'error': str(log_error)
                })

        # Fallback: Return status message instead of error
        return jsonify({
            'logs': [f'[{datetime.now().strftime("%H:%M:%S")}] Bot starting up or log handler not ready...'],
            'status': 'initializing'
        })

    except Exception as e:
        # Return user-friendly error instead of 500 status
        return jsonify({
            'logs': [f'[{datetime.now().strftime("%H:%M:%S")}] Dashboard connecting to bot...'],
            'status': 'connecting',
            'debug_error': str(e)
        })

@app.route('/api/bot_status')
def get_bot_status():
    """Get current bot status with enhanced error handling"""
    try:
        # Multiple fallback methods to find bot manager
        bot_manager = None

        # Method 1: Check main module
        main_module = sys.modules.get('__main__')
        if main_module and hasattr(main_module, 'bot_manager'):
            bot_manager = main_module.bot_manager

        # Method 2: Check global variables
        if not bot_manager and 'bot_manager' in globals():
            bot_manager = globals()['bot_manager']

        # Method 3: Check web_dashboard module
        if not bot_manager and hasattr(sys.modules.get('web_dashboard', {}), 'bot_manager'):
            bot_manager = sys.modules['web_dashboard'].bot_manager

        if bot_manager:
            try:
                status = bot_manager.get_bot_status()
                status['connection_status'] = 'connected'
                status['last_update'] = datetime.now().isoformat()
                return jsonify(status)
            except Exception as status_error:
                # Bot manager exists but get_bot_status failed
                return jsonify({
                    'is_running': getattr(bot_manager, 'is_running', False),
                    'active_positions': len(getattr(bot_manager, 'order_manager', {}).get('active_positions', {})) if hasattr(bot_manager, 'order_manager') else 0,
                    'strategies': list(getattr(bot_manager, 'strategies', {}).keys()) if hasattr(bot_manager, 'strategies') else [],
                    'balance': 0,
                    'connection_status': 'partial',
                    'error': str(status_error),
                    'last_update': datetime.now().isoformat()
                })

        # Fallback: Bot not ready yet
        return jsonify({
            'is_running': False,
            'active_positions': 0,
            'strategies': [],
            'balance': 0,
            'connection_status': 'initializing',
            'status': 'Bot starting up...',
            'last_update': datetime.now().isoformat()
        })

    except Exception as e:
        # Return user-friendly status instead of error
        return jsonify({
            'is_running': False,
            'active_positions': 0,
            'strategies': [],
            'balance': 0,
            'connection_status': 'error',
            'status': f'Connection error: {str(e)}',
            'last_update': datetime.now().isoformat()
        })

def get_bot_status():
    """Get current bot status with enhanced error handling - LEGACY FUNCTION"""
    global bot_running, bot_manager, shared_bot_manager

    try:
        # Always get fresh reference to shared bot manager
        shared_bot_manager = getattr(sys.modules.get('__main__', None), 'bot_manager', None)

        # Default safe response
        default_status = {
            'is_running': False,
            'active_positions': 0,
            'strategies': [],
            'balance': 0
        }

        # Check shared bot manager first
        if shared_bot_manager and hasattr(shared_bot_manager, 'is_running'):
            try:
                strategies_list = []
                if hasattr(shared_bot_manager, 'strategies'):
                    strategies_dict = getattr(shared_bot_manager, 'strategies', {})
                    strategies_list = list(strategies_dict.keys()) if strategies_dict else []

                active_positions_count = 0
                if hasattr(shared_bot_manager, 'order_manager') and shared_bot_manager.order_manager:
                    try:
                        active_positions = getattr(shared_bot_manager.order_manager, 'active_positions', {})
                        active_positions_count = len(active_positions) if active_positions else 0
                    except:
                        active_positions_count = 0

                status = {
                    'is_running': getattr(shared_bot_manager, 'is_running', False),
                    'active_positions': active_positions_count,
                    'strategies': strategies_list,
                    'balance': 0  # Will be updated separately
                }
                return status
            except Exception as e:
                logger.debug(f"Error getting shared bot status: {e}")
                return default_status

        # Fallback to global bot_running flag
        try:
            if IMPORTS_AVAILABLE:
                strategies = trading_config_manager.get_all_strategies()
                default_status['strategies'] = list(strategies.keys()) if strategies else []
        except Exception as config_error:
            logger.debug(f"Could not get strategies from config: {config_error}")

        return default_status

    except Exception as e:
        logger.warning(f"Error in legacy get_bot_status: {e}")
        return {
            'is_running': False,
            'active_positions': 0,
            'strategies': [],
            'balance': 0,
            'error': f'Status check failed: {str(e)}'
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
    return render_template('ml_reports.html')

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
                'margin_usdt': trade_data.get('margin_usdt', 0),
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

@app.route('/api/ml_predictions')
def get_ml_predictions():
    """Get ML predictions for current market conditions"""
    try:
        if not IMPORTS_AVAILABLE:
            return jsonify({'success': False, 'error': 'ML features not available in demo mode'})

        # Import ML analyzer
        from src.analytics.ml_analyzer import ml_analyzer

        # Sample predictions for current strategies
        predictions = []
        strategies = trading_config_manager.get_all_strategies()

        for strategy_name, config in strategies.items():
            # Create sample trade features
            sample_features = {
                'strategy': strategy_name,
                'symbol': config.get('symbol', 'BTCUSDT'),
                'side': 'BUY',
                'leverage': config.get('leverage', 5),
                'position_size_usdt': config.get('margin', 50),
                'hour_of_day': datetime.now().hour,
                'day_of_week': datetime.now().weekday(),
                'market_trend': 'BULLISH',
                'volatility_score': 0.3,
                'signal_strength': 0.7
            }

            # Add strategy-specific features
            if 'rsi' in strategy_name.lower():
                sample_features['rsi_entry'] = 30  # Oversold
            elif 'macd' in strategy_name.lower():
                sample_features['macd_entry'] = 0.1

            prediction = ml_analyzer.predict_trade_outcome(sample_features)

            if "error" not in prediction:
                predictions.append({
                    'strategy': strategy_name,
                    'symbol': config.get('symbol', 'BTCUSDT'),
                    'predicted_profitable': prediction.get('profit_probability', 0.5) > 0.5,
                    'predicted_pnl': prediction.get('predicted_pnl_percentage', 0),
                    'confidence': prediction.get('confidence', 0),
                    'recommendation': prediction.get('recommendation', 'HOLD')
                })

        return jsonify({'success': True, 'predictions': predictions})

    except Exception as e:
        logger.error(f"Error getting ML predictions: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/train_models', methods=['POST'])
def train_models():
    """Train ML models"""
    try:
        if notIMPORTS_AVAILABLE:
            return jsonify({'success': False, 'error': 'ML features not available in demo mode'})

        # Import ML analyzer
        from src.analytics.ml_analyzer import ml_analyzer

        # Train models
        results = ml_analyzer.train_models()

        if "error" in results:
            return jsonify({'success': False, 'error': results['error']})

        return jsonify({'success': True, 'results': results})

    except Exception as e:
        logger.error(f"Error training ML models: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/strategies/<strategy_name>', methods=['PUT'])
def update_strategy_config(strategy_name):
    """Update strategy configuration using PUT method"""
    return update_strategy(strategy_name)

@app.route('/api/environment', methods=['POST'])
def update_environment():
    """Update environment configuration"""
    try:
        data = request.get_json()
        if not data or 'environment' not in data:
            return jsonify({'success': False, 'message': 'Missing environment parameter'})

        environment = data['environment']
        is_testnet = environment == 'TESTNET'

        # Update global config
        if IMPORTS_AVAILABLE:
            global_config.BINANCE_TESTNET = is_testnet

        return jsonify({
            'success': True,
            'message': f'Environment updated to {environment}',
            'environment': environment
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to update environment: {e}'})

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

def run_web_dashboard():
    """Run the web dashboard"""
    try:
        # Get port from environment for deployment compatibility
        port = int(os.environ.get('PORT', 5000))
        logger.info(f"🌐 Starting web dashboard on 0.0.0.0:{port}")

        # Disable Flask's default request logging
        import logging as flask_logging
        werkzeug_logger = flask_logging.getLogger('werkzeug')
        werkzeug_logger.setLevel(flask_logging.WARNING)

        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)
    except Exception as e:
        logger.error(f"Web dashboard error: {e}")
        if "Address already in use" in str(e):
            logger.error("🚨 Port 5000 is already in use")
        else:
            logger.error(f"🚨 Web dashboard failed to start: {e}")

if __name__ == '__main__':
    run_web_dashboard()