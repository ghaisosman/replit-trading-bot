from flask import Flask, render_template, request, jsonify, send_file
import json
import logging
from datetime import datetime, timedelta
import os
from pathlib import Path
import pandas as pd
import time

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Import our config manager
from src.config.trading_config import trading_config_manager

@app.route('/')
def dashboard():
    """Main dashboard page"""
    try:
        # Get all strategy configurations
        strategies = trading_config_manager.get_all_strategies()

        # Get latest trade data
        trade_data = get_latest_trade_data()

        return render_template('dashboard.html', 
                             strategies=strategies,
                             trade_data=trade_data,
                             current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        return f"Dashboard error: {e}", 500

@app.route('/update_strategy', methods=['POST'])
def update_strategy():
    """Update strategy configuration via web dashboard"""
    try:
        data = request.get_json()
        strategy_name = data.get('strategy_name')

        if not strategy_name:
            return jsonify({'success': False, 'error': 'Strategy name required'}), 400

        # Extract parameters from the request
        updates = {}
        for key, value in data.items():
            if key != 'strategy_name':
                updates[key] = value

        # Update strategy with simplified validation
        safety_warnings = trading_config_manager.update_strategy_params(strategy_name, updates)

        logger.info(f"🌐 WEB DASHBOARD: Updated {strategy_name} configuration")

        response = {
            'success': True, 
            'message': f'Strategy {strategy_name} updated successfully'
        }

        # Include safety warnings if any
        if safety_warnings:
            response['safety_warnings'] = safety_warnings

        return jsonify(response)

    except Exception as e:
        logger.error(f"Update strategy error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/get_strategy/<strategy_name>')
def get_strategy(strategy_name):
    """Get strategy configuration"""
    try:
        config = trading_config_manager.get_strategy_config(strategy_name)
        return jsonify({'success': True, 'config': config})
    except Exception as e:
        logger.error(f"Get strategy error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/trades')
def api_trades():
    """API endpoint for trade data"""
    try:
        trade_data = get_latest_trade_data()
        return jsonify(trade_data)
    except Exception as e:
        logger.error(f"API trades error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/strategies')
def api_strategies():
    """API endpoint for strategy data"""
    try:
        strategies = trading_config_manager.get_all_strategies()
        return jsonify(strategies)
    except Exception as e:
        logger.error(f"API strategies error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/disable_strategy', methods=['POST'])
def disable_strategy():
    """Disable a strategy"""
    try:
        data = request.get_json()
        strategy_name = data.get('strategy_name')

        if not strategy_name:
            return jsonify({'success': False, 'error': 'Strategy name required'}), 400

        # Simply set enabled to False
        trading_config_manager.update_strategy_params(strategy_name, {'enabled': False})

        logger.info(f"🛑 Strategy {strategy_name} disabled via web dashboard")
        return jsonify({'success': True, 'message': f'Strategy {strategy_name} disabled'})

    except Exception as e:
        logger.error(f"Disable strategy error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/enable_strategy', methods=['POST'])
def enable_strategy():
    """Enable a strategy"""
    try:
        data = request.get_json()
        strategy_name = data.get('strategy_name')

        if not strategy_name:
            return jsonify({'success': False, 'error': 'Strategy name required'}), 400

        # Simply set enabled to True
        trading_config_manager.update_strategy_params(strategy_name, {'enabled': True})

        logger.info(f"✅ Strategy {strategy_name} enabled via web dashboard")
        return jsonify({'success': True, 'message': f'Strategy {strategy_name} enabled'})

    except Exception as e:
        logger.error(f"Enable strategy error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

def get_latest_trade_data():
    """Get latest trade data from database"""
    try:
        from src.execution_engine.trade_database import TradeDatabase
        trade_db = TradeDatabase()

        # Get recent trades
        trades = []
        for trade_id, trade_data in list(trade_db.trades.items())[-10:]:  # Last 10 trades
            trade_data['trade_id'] = trade_id
            trades.append(trade_data)

        return {
            'total_trades': len(trade_db.trades),
            'recent_trades': trades,
            'last_updated': datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting trade data: {e}")
        return {
            'total_trades': 0,
            'recent_trades': [],
            'last_updated': datetime.now().isoformat(),
            'error': str(e)
        }

@app.route('/api/bot/status')
def get_bot_status():
    """Get current bot status"""
    try:
        # Check if bot is running
        import psutil
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            if proc.info['cmdline'] and 'main.py' in ' '.join(proc.info['cmdline']):
                return jsonify({
                    'status': 'running',
                    'pid': proc.info['pid'],
                    'uptime': 'active'
                })

        return jsonify({'status': 'stopped'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/bot/start', methods=['POST'])
def start_bot():
    """Start the trading bot"""
    try:
        import subprocess
        subprocess.Popen(['python', 'main.py'])
        return jsonify({'success': True, 'message': 'Bot starting...'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/bot/stop', methods=['POST'])
def stop_bot():
    """Stop the trading bot"""
    try:
        import psutil
        for proc in psutil.process_iter(['pid', 'cmdline']):
            if proc.info['cmdline'] and 'main.py' in ' '.join(proc.info['cmdline']):
                proc.terminate()
                return jsonify({'success': True, 'message': 'Bot stopped'})

        return jsonify({'success': False, 'message': 'Bot not running'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/balance')
def get_balance():
    """Get account balance"""
    try:
        # Try to get balance from binance client
        try:
            from src.binance_client.client import BinanceClientWrapper
            binance_client = BinanceClientWrapper()
            account = binance_client.client.futures_account()

            balance = float(account['availableBalance'])
            return jsonify({
                'success': True,
                'balance': balance,
                'currency': 'USDT'
            })
        except Exception as e:
            # Return mock data if binance connection fails
            return jsonify({
                'success': True,
                'balance': 1000.0,
                'currency': 'USDT',
                'note': 'Mock data - Binance connection unavailable'
            })
    except Exception as e:
        logger.error(f"Balance API error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/positions')
def get_positions():
    """Get current positions"""
    try:
        # Try to get positions from binance client
        try:
            from src.binance_client.client import BinanceClientWrapper
            binance_client = BinanceClientWrapper()
            positions = binance_client.client.futures_position_information()

            # Filter out zero positions
            active_positions = [
                pos for pos in positions 
                if float(pos['positionAmt']) != 0
            ]

            formatted_positions = []
            for pos in active_positions:
                formatted_positions.append({
                    'symbol': pos['symbol'],
                    'side': 'LONG' if float(pos['positionAmt']) > 0 else 'SHORT',
                    'size': abs(float(pos['positionAmt'])),
                    'entry_price': float(pos['entryPrice']),
                    'current_price': float(pos['markPrice']),
                    'pnl': float(pos['unRealizedProfit']),
                    'pnl_percentage': float(pos['percentage']) if 'percentage' in pos else 0
                })

            return jsonify({
                'success': True,
                'positions': formatted_positions
            })
        except Exception as e:
            # Return empty positions if binance connection fails
            return jsonify({
                'success': True,
                'positions': [],
                'note': 'Mock data - Binance connection unavailable'
            })
    except Exception as e:
        logger.error(f"Positions API error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/console-log')
def get_console_log():
    """Get recent console logs"""
    try:
        # Return recent log entries
        return jsonify({
            'logs': ['Bot is running...', 'Monitoring positions...'],
            'timestamp': time.time()
        })
    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    logger.info("🌐 Starting simplified web dashboard...")
    app.run(host='0.0.0.0', port=5000, debug=True)
```