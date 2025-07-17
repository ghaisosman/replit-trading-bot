
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
    from src.config.trading_config import trading_config_manager, TradingConfig
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
        
        def get_all_strategies(self):
            return self.strategy_overrides
        
        def update_strategy_params(self, strategy_name, updates):
            if strategy_name not in self.strategy_overrides:
                self.strategy_overrides[strategy_name] = {}
            self.strategy_overrides[strategy_name].update(updates)

    class DummyBalanceFetcher:
        def get_usdt_balance(self):
            return 100.0

    trading_config_manager = DummyConfigManager()
    balance_fetcher = DummyBalanceFetcher()

def get_current_bot_manager():
    """Get the current bot manager instance from main module"""
    global bot_manager, shared_bot_manager, current_bot
    
    # Try multiple sources for bot manager
    if shared_bot_manager:
        return shared_bot_manager
    
    if bot_manager:
        return bot_manager
    
    # Try to get from main module
    try:
        import sys
        main_module = sys.modules.get('__main__')
        if main_module and hasattr(main_module, 'bot_manager'):
            return main_module.bot_manager
    except Exception as e:
        logger.debug(f"Could not get bot manager from main module: {e}")
    
    return None

@app.route('/')
def dashboard():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/api/bot/status')
def get_bot_status():
    """Get bot status"""
    try:
        current_bot = get_current_bot_manager()
        if current_bot:
            return jsonify({
                'running': getattr(current_bot, 'is_running', False),
                'strategies': list(getattr(current_bot, 'strategies', {}).keys()),
                'uptime': getattr(current_bot, 'uptime', 0)
            })
        else:
            return jsonify({'running': False, 'strategies': [], 'uptime': 0})
    except Exception as e:
        logger.error(f"❌ API ERROR: /api/bot/status - {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/balance', methods=['GET'])
def get_balance():
    """Get current balance via API"""
    try:
        current_bot = get_current_bot_manager()
        if current_bot and hasattr(current_bot, 'balance_fetcher'):
            balance = current_bot.balance_fetcher.get_usdt_balance() or 0
            return jsonify({'balance': balance})
        elif IMPORTS_AVAILABLE and balance_fetcher:
            balance = balance_fetcher.get_usdt_balance() or 0
            return jsonify({'balance': balance})
        else:
            return jsonify({'balance': 0})
    except Exception as e:
        print(f"❌ API ERROR: /api/balance - {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/positions', methods=['GET'])
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
                # Check if this position has an anomaly (orphan/ghost trade)
                anomaly_status = None
                if hasattr(current_bot, 'anomaly_detector'):
                    anomaly_status = current_bot.anomaly_detector.get_anomaly_status(strategy_name)

                # Get current price
                current_price = None
                if IMPORTS_AVAILABLE and price_fetcher:
                    current_price = price_fetcher.get_current_price(position.symbol)

                # Calculate PnL
                if current_price:
                    entry_price = position.entry_price
                    quantity = position.quantity
                    side = position.side

                    # For futures trading, PnL calculation (matches console calculation)
                    if side == 'BUY':  # Long position
                        pnl = (current_price - entry_price) * quantity
                    elif side == 'SELL':  # Short position
                        pnl = (entry_price - current_price) * quantity
                    else:
                        pnl = 0  # Unknown side
                else:
                    pnl = 0  # If current price is not available

                # Calculate position value in USDT
                position_value_usdt = position.entry_price * position.quantity

                # Get leverage and margin from strategy config (if available)
                strategy_config = current_bot.strategies.get(strategy_name, {}) if hasattr(current_bot, 'strategies') else {}
                leverage = strategy_config.get('leverage', 5)  # Default 5x leverage
                margin_invested = strategy_config.get('margin', 50.0)  # Use configured margin

                # Calculate PnL percentage against margin invested (correct for futures)
                pnl_percent = (pnl / margin_invested) * 100 if margin_invested > 0 else 0

                positions.append({
                    'strategy': strategy_name,
                    'symbol': position.symbol,
                    'side': position.side,
                    'entry_price': position.entry_price,
                    'quantity': position.quantity,
                    'position_value_usdt': position_value_usdt,  # Include position value
                    'margin_invested': margin_invested,  # Include margin invested
                    'current_price': current_price,
                    'pnl': pnl,
                    'pnl_percent': pnl_percent,
                    'anomaly_status': anomaly_status
                })

        return jsonify({'success': True, 'positions': positions})
    except Exception as e:
        print(f"❌ API ERROR: /api/positions - {e}")
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
        print(f"❌ API ERROR: /api/trades - {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/console/log', methods=['GET'])
def get_console_log():
    """Get recent console logs from bot manager"""
    try:
        current_bot = get_current_bot_manager()

        if current_bot and hasattr(current_bot, 'log_handler'):
            # Get logs from the web log handler
            logs = list(current_bot.log_handler.logs)
            return jsonify({'logs': logs})
        else:
            # Return sample logs if no bot is running
            sample_logs = [
                {'timestamp': '15:44:53', 'message': '🌐 Web dashboard active - Bot can be started via Start Bot button'},
                {'timestamp': '15:44:53', 'message': '📊 Ready for trading operations'},
                {'timestamp': '15:44:53', 'message': '💡 Use the web interface to control the bot'}
            ]
            return jsonify({'logs': sample_logs})
    except Exception as e:
        print(f"❌ API ERROR: /api/console/log - {e}")
        return jsonify({'logs': [], 'error': str(e)}), 500

@app.route('/api/console-log', methods=['GET'])
def get_console_log_alt():
    """Alternative console log endpoint that frontend might be calling"""
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

@app.route('/api/rsi/<symbol>', methods=['GET'])
def get_rsi_for_symbol(symbol):
    """Get RSI data for a specific symbol from bot manager"""
    try:
        current_bot = get_current_bot_manager()

        if current_bot:
            strategies = getattr(current_bot, 'strategies', {})

            # Get RSI data from any RSI-based strategy
            for strategy_name, strategy in strategies.items():
                if hasattr(strategy, 'get_rsi_data'):
                    try:
                        rsi_data = strategy.get_rsi_data(symbol)
                        if rsi_data:
                            return jsonify(rsi_data)
                    except Exception as e:
                        continue

        return jsonify({'error': 'No RSI data found for symbol'}), 404

    except Exception as e:
        print(f"❌ API ERROR: /api/rsi/{symbol} - {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/trading/environment', methods=['GET'])
def get_trading_environment():
    """Get trading environment configuration"""
    try:
        # Get current bot manager
        current_bot = get_current_bot_manager()

        if current_bot and hasattr(current_bot, 'is_running'):
            environment_info = {
                'bot_running': current_bot.is_running,
                'environment': 'MAINNET',  # Based on Instructions.md - now using mainnet
                'web_dashboard_active': True,
                'config_source': 'web_dashboard'  # Web dashboard is single source of truth
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
        print(f"❌ API ERROR: /api/trading/environment - {e}")
        return jsonify({'error': str(e), 'environment': 'UNKNOWN'}), 500

def get_current_price(symbol):
    """Helper function to get the current price of a symbol"""
    try:
        if IMPORTS_AVAILABLE and price_fetcher:
            current_price = price_fetcher.get_current_price(symbol)
            return current_price
        return None
    except Exception as e:
        print(f"❌ PRICE API ERROR: {e}")
        return None

def calculate_pnl(position, current_price):
    """Helper function to calculate P&L for a position"""
    try:
        entry_price = position.entry_price
        quantity = position.quantity
        side = position.side

        # For futures trading, PnL calculation
        if side == 'BUY':  # Long position
            pnl = (current_price - entry_price) * quantity
        elif side == 'SELL':  # Short position
            pnl = (entry_price - current_price) * quantity
        else:
            return 0  # Unknown side

        return pnl
    except Exception as e:
        print(f"❌ PNL CALC ERROR: {e}")
        return 0

# Add a catch-all route for debugging 404s
@app.route('/<path:path>')
def catch_all(path):
    """Catch-all route to debug 404 errors"""
    print(f"❌ 404 ERROR: Requested path not found: /{path}")
    print(f"📍 Available routes:")
    for rule in app.url_map.iter_rules():
        if rule.rule != '/<path:path>':  # Don't show the catch-all
            methods = ', '.join(sorted(rule.methods - {'OPTIONS', 'HEAD'}))
            print(f"    {rule.rule} ({methods})")

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
    exit(1)  # Prevent execution
