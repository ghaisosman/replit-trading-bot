#!/usr/bin/env python3
"""
Trading Bot Web Dashboard
Simplified web interface for managing the trading bot
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
    'bot_status': {'requests': [], 'limit': 20, 'window': 60},
    'balance': {'requests': [], 'limit': 10, 'window': 60},
    'positions': {'requests': [], 'limit': 15, 'window': 60},
    'console_log': {'requests': [], 'limit': 30, 'window': 60}
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
                logger.warning(f"Rate limit exceeded for {endpoint_key}")
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

def get_shared_bot_manager():
    """Get the shared bot manager instance"""
    try:
        # Try to get from main module
        import sys
        if hasattr(sys.modules['__main__'], 'bot_manager'):
            return sys.modules['__main__'].bot_manager
        
        # Try to get from globals
        if 'bot_manager' in globals():
            return globals()['bot_manager']
        
        return None
    except Exception as e:
        logger.error(f"Error getting bot manager: {e}")
        return None

@app.route('/healthz')
def healthz():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/api/dashboard/health')
def dashboard_health():
    """Dashboard health check"""
    try:
        bot_manager = get_shared_bot_manager()
        return jsonify({
            'status': 'healthy',
            'bot_manager_available': bot_manager is not None,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/')
def dashboard():
    """Main dashboard page"""
    try:
        return render_template('dashboard.html')
    except Exception as e:
        logger.error(f"Error rendering dashboard: {e}")
        return f"Dashboard Error: {e}", 500

@app.route('/api/bot/start', methods=['POST'])
def start_bot():
    """Start the trading bot"""
    try:
        bot_manager = get_shared_bot_manager()
        if not bot_manager:
            return jsonify({'success': False, 'error': 'Bot manager not available'}), 500

        # Start bot in background thread
        def run_bot():
            try:
                asyncio.run(bot_manager.start_trading())
            except Exception as e:
                logger.error(f"Error starting bot: {e}")

        thread = threading.Thread(target=run_bot, daemon=True)
        thread.start()

        return jsonify({
            'success': True,
            'message': 'Bot starting...',
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Error in start_bot: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/bot/stop', methods=['POST'])
def stop_bot():
    """Stop the trading bot"""
    try:
        bot_manager = get_shared_bot_manager()
        if not bot_manager:
            return jsonify({'success': False, 'error': 'Bot manager not available'}), 500

        # Stop bot in background thread
        def stop_shared_bot():
            try:
                asyncio.run(bot_manager.stop_trading("Manual stop via web dashboard"))
            except Exception as e:
                logger.error(f"Error stopping bot: {e}")

        thread = threading.Thread(target=stop_shared_bot, daemon=True)
        thread.start()

        return jsonify({
            'success': True,
            'message': 'Bot stopping...',
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Error in stop_bot: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/bot/status')
@app.route('/api/bot_status')
@rate_limit('bot_status', max_requests=20, window_seconds=60)
def get_bot_status():
    """Get current bot status"""
    try:
        bot_manager = get_shared_bot_manager()
        
        if not bot_manager:
            return jsonify({
                'success': False,
                'error': 'Bot manager not available',
                'running': False,
                'is_running': False,
                'active_positions': 0,
                'strategies': 0,
                'balance': 0.0,
                'status': 'unavailable',
                'last_update': datetime.now().strftime('%H:%M:%S'),
                'timestamp': datetime.now().strftime('%H:%M:%S')
            })

        status = bot_manager.get_status()
        
        return jsonify({
            'success': True,
            'running': status.get('is_running', False),
            'is_running': status.get('is_running', False),
            'active_positions': status.get('active_positions', 0),
            'strategies': 4,  # Fixed number of strategies
            'balance': status.get('balance', 0.0),
            'status': 'running' if status.get('is_running') else 'stopped',
            'last_update': datetime.now().strftime('%H:%M:%S'),
            'timestamp': datetime.now().strftime('%H:%M:%S')
        })

    except Exception as e:
        logger.error(f"Error getting bot status: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'running': False,
            'is_running': False,
            'active_positions': 0,
            'strategies': 0,
            'balance': 0.0,
            'status': 'error',
            'last_update': datetime.now().strftime('%H:%M:%S'),
            'timestamp': datetime.now().strftime('%H:%M:%S')
        }), 500

@app.route('/api/strategies')
def get_strategies():
    """Get available strategies"""
    try:
        strategies = [
            {
                'name': 'smart_money',
                'display_name': 'Smart Money Liquidity Hunt',
                'description': 'Identifies liquidity sweeps and market maker activities',
                'enabled': True,
                'symbol': 'BTCUSDT',
                'margin': 10,
                'leverage': 3
            },
            {
                'name': 'macd_divergence',
                'display_name': 'MACD Divergence',
                'description': 'Detects MACD divergence patterns',
                'enabled': True,
                'symbol': 'ETHUSDT',
                'margin': 10,
                'leverage': 3
            },
            {
                'name': 'rsi_oversold',
                'display_name': 'RSI Oversold',
                'description': 'RSI oversold condition detection',
                'enabled': True,
                'symbol': 'SOLUSDT',
                'margin': 10,
                'leverage': 3
            },
            {
                'name': 'engulfing_pattern',
                'display_name': 'Engulfing Pattern',
                'description': 'Candlestick pattern recognition',
                'enabled': True,
                'symbol': 'XRPUSDT',
                'margin': 10,
                'leverage': 3
            }
        ]
        
        return jsonify({
            'success': True,
            'strategies': strategies
        })

    except Exception as e:
        logger.error(f"Error getting strategies: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/balance')
@rate_limit('balance', max_requests=10, window_seconds=60)
def get_balance():
    """Get account balance"""
    try:
        bot_manager = get_shared_bot_manager()
        
        if not bot_manager or not bot_manager.balance_fetcher:
            return jsonify({
                'success': False,
                'error': 'Balance fetcher not available',
                'balance': 0.0,
                'timestamp': datetime.now().isoformat()
            })

        balance = bot_manager.balance_fetcher.get_usdt_balance()
        
        return jsonify({
            'success': True,
            'balance': balance,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Error getting balance: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'balance': 0.0,
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/positions')
@rate_limit('positions', max_requests=15, window_seconds=60)
def get_positions():
    """Get current positions"""
    try:
        bot_manager = get_shared_bot_manager()
        
        if not bot_manager or not bot_manager.order_manager:
            return jsonify({
                'success': False,
                'error': 'Order manager not available',
                'positions': [],
                'timestamp': datetime.now().isoformat()
            })

        positions = bot_manager.order_manager.get_active_positions()
        
        # Convert positions to dict format
        positions_list = []
        for strategy_name, position in positions.items():
            positions_list.append({
                'strategy_name': strategy_name,
                'symbol': position.symbol,
                'side': position.side,
                'entry_price': position.entry_price,
                'quantity': position.quantity,
                'stop_loss': position.stop_loss,
                'take_profit': position.take_profit,
                'status': position.status
            })
        
        return jsonify({
            'success': True,
            'positions': positions_list,
            'count': len(positions_list),
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'positions': [],
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/console-log')
@rate_limit('console_log', max_requests=30, window_seconds=60)
def get_console_log():
    """Get recent console logs"""
    try:
        # Simple log retrieval - in production you'd want a proper log handler
        logs = [
            f"[{datetime.now().strftime('%H:%M:%S')}] System running normally",
            f"[{datetime.now().strftime('%H:%M:%S')}] Web dashboard active"
        ]
        
        return jsonify({
            'success': True,
            'logs': logs,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Error getting console log: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'logs': [],
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/trading/environment', methods=['GET'])
def get_trading_environment():
    """Get trading environment configuration"""
    try:
        config_file = "trading_data/environment_config.json"
        
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config = json.load(f)
        else:
            config = {
                'BINANCE_TESTNET': 'true',
                'BINANCE_FUTURES': 'true'
            }
        
        return jsonify({
            'success': True,
            'environment': config,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Error getting trading environment: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'environment': {},
            'timestamp': datetime.now().isoformat()
        }), 500

def start_web_dashboard(debug=False, use_reloader=False):
    """Start the web dashboard"""
    try:
        app.run(host='0.0.0.0', port=5000, debug=debug, use_reloader=use_reloader)
    except Exception as e:
        logger.error(f"Error starting web dashboard: {e}")

if __name__ == "__main__":
    start_web_dashboard(debug=True)