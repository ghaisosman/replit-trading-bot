from flask import Flask, render_template, request, jsonify, send_file
import json
import logging
from datetime import datetime, timedelta
import os
from pathlib import Path
import pandas as pd
import time
import random

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
        return jsonify({
            'success': True,
            'strategies': strategies,
            'count': len(strategies),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"API strategies error: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'strategies': {},
            'count': 0,
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/strategies/<strategy_name>', methods=['POST'])
def update_strategy_api(strategy_name):
    """Update strategy configuration via API"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        # Update strategy with validation
        safety_warnings = trading_config_manager.update_strategy_params(strategy_name, data)

        response = {
            'success': True, 
            'message': f'Strategy {strategy_name} updated successfully',
            'timestamp': datetime.now().isoformat()
        }

        if safety_warnings:
            response['safety_warnings'] = safety_warnings

        return jsonify(response)

    except Exception as e:
        logger.error(f"Update strategy API error: {e}")
        return jsonify({
            'success': False, 
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/strategies/<strategy_name>/disable', methods=['POST'])
def disable_strategy_api(strategy_name):
    """Disable a strategy via API"""
    try:
        trading_config_manager.update_strategy_params(strategy_name, {'enabled': False})
        logger.info(f"🛑 Strategy {strategy_name} disabled via API")
        return jsonify({
            'success': True, 
            'message': f'Strategy {strategy_name} disabled',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Disable strategy API error: {e}")
        return jsonify({
            'success': False, 
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/strategies/<strategy_name>/enable', methods=['POST'])
def enable_strategy_api(strategy_name):
    """Enable a strategy via API"""
    try:
        trading_config_manager.update_strategy_params(strategy_name, {'enabled': True})
        logger.info(f"✅ Strategy {strategy_name} enabled via API")
        return jsonify({
            'success': True, 
            'message': f'Strategy {strategy_name} enabled',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Enable strategy API error: {e}")
        return jsonify({
            'success': False, 
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

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
        # Check if bot is running by looking for bot manager
        import sys
        main_module = sys.modules.get('__main__')
        bot_manager = getattr(main_module, 'bot_manager', None) if main_module else None

        is_running = False
        if bot_manager and hasattr(bot_manager, 'is_running'):
            is_running = bot_manager.is_running

        # Also check for processes as backup
        if not is_running:
            try:
                import psutil
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    if proc.info['cmdline'] and any('main.py' in str(cmd) for cmd in proc.info['cmdline']):
                        is_running = True
                        break
            except Exception:
                pass

        return jsonify({
            'success': True,
            'running': is_running,
            'is_running': is_running,
            'status': 'running' if is_running else 'stopped',
            'active_positions': 0,
            'strategies': 0,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Bot status API error: {e}")
        return jsonify({
            'success': False,
            'running': False,
            'is_running': False,
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/bot/start', methods=['POST'])
def start_bot():
    """Start the trading bot"""
    try:
        # Check if bot is already running
        import sys
        main_module = sys.modules.get('__main__')
        bot_manager = getattr(main_module, 'bot_manager', None) if main_module else None

        if bot_manager and hasattr(bot_manager, 'is_running') and bot_manager.is_running:
            return jsonify({
                'success': False, 
                'message': 'Bot is already running',
                'timestamp': datetime.now().isoformat()
            })

        # Start bot in subprocess
        import subprocess
        import os

        # Start the bot process
        subprocess.Popen(['python', 'main.py'], 
                        cwd=os.getcwd(),
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)

        logger.info("🤖 Bot start requested via web dashboard")
        return jsonify({
            'success': True, 
            'message': 'Bot starting...',
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Bot start API error: {e}")
        return jsonify({
            'success': False, 
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/bot/stop', methods=['POST'])
def stop_bot():
    """Stop the trading bot"""
    try:
        # First try to stop via bot manager
        import sys
        main_module = sys.modules.get('__main__')
        bot_manager = getattr(main_module, 'bot_manager', None) if main_module else None

        if bot_manager and hasattr(bot_manager, 'stop'):
            try:
                import asyncio
                # Try to stop gracefully
                asyncio.create_task(bot_manager.stop("Dashboard stop request"))
                logger.info("🛑 Bot stop requested via web dashboard (graceful)")
                return jsonify({
                    'success': True, 
                    'message': 'Bot stopping gracefully...',
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as graceful_error:
                logger.warning(f"Graceful stop failed: {graceful_error}")

        # Fallback to process termination
        import psutil
        stopped_processes = 0
        for proc in psutil.process_iter(['pid', 'cmdline']):
            try:
                if proc.info['cmdline'] and any('main.py' in str(cmd) for cmd in proc.info['cmdline']):
                    proc.terminate()
                    stopped_processes += 1
                    logger.info(f"🛑 Terminated bot process PID {proc.pid}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if stopped_processes > 0:
            return jsonify({
                'success': True, 
                'message': f'Bot stopped ({stopped_processes} processes terminated)',
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False, 
                'message': 'No bot processes found running',
                'timestamp': datetime.now().isoformat()
            })

    except Exception as e:
        logger.error(f"Bot stop API error: {e}")
        return jsonify({
            'success': False, 
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

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
        return jsonify({
            'success': False, 
            'error': str(e),
            'balance': 0,
            'currency': 'USDT'
        }), 200

@app.route('/api/positions')
def get_positions():
    """Get current positions"""
    try:
        # First try to get positions from trade database
        active_positions = []
        try:
            from src.execution_engine.trade_database import TradeDatabase
            trade_db = TradeDatabase()

            # Get active trades from database
            for trade_id, trade_data in trade_db.trades.items():
                if trade_data.get('status') == 'OPEN' or trade_data.get('trade_status') == 'OPEN':
                    active_positions.append({
                        'strategy': trade_data.get('strategy_name', 'Unknown'),
                        'symbol': trade_data.get('symbol', 'Unknown'),
                        'side': trade_data.get('side', 'Unknown'),
                        'entry_price': trade_data.get('entry_price', 0),
                        'margin_invested': trade_data.get('margin_used', 0),
                        'current_price': trade_data.get('entry_price', 0),  # Fallback to entry price
                        'pnl': trade_data.get('pnl_usdt', 0),
                        'pnl_percent': trade_data.get('pnl_percentage', 0)
                    })
        except Exception as db_error:
            logger.warning(f"Could not get positions from database: {db_error}")

        # If no database positions, try Binance API
        if not active_positions:
            try:
                from src.binance_client.client import BinanceClientWrapper
                binance_client = BinanceClientWrapper()
                positions = binance_client.client.futures_position_information()

                # Filter out zero positions
                binance_positions = [
                    pos for pos in positions 
                    if float(pos['positionAmt']) != 0
                ]

                for pos in binance_positions:
                    active_positions.append({
                        'strategy': 'Manual',
                        'symbol': pos['symbol'],
                        'side': 'LONG' if float(pos['positionAmt']) > 0 else 'SHORT',
                        'entry_price': float(pos['entryPrice']),
                        'margin_invested': abs(float(pos['positionAmt']) * float(pos['entryPrice'])),
                        'current_price': float(pos['markPrice']),
                        'pnl': float(pos['unRealizedProfit']),
                        'pnl_percent': float(pos['percentage']) if 'percentage' in pos else 0
                    })
            except Exception as api_error:
                logger.warning(f"Could not get positions from Binance API: {api_error}")

        return jsonify({
            'success': True,
            'positions': active_positions,
            'count': len(active_positions),
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Positions API error: {e}")
        return jsonify({
            'success': False, 
            'error': str(e),
            'positions': [],
            'count': 0,
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/console-log')
def get_console_log():
    """Get recent console logs"""
    try:
        # Return recent log entries from the log handler if available
        logs = []
        try:
            # Try to get logs from web log handler if bot is running
            import sys
            main_module = sys.modules.get('__main__')
            bot_manager = getattr(main_module, 'bot_manager', None) if main_module else None

            if bot_manager and hasattr(bot_manager, 'log_handler') and bot_manager.log_handler:
                logs = bot_manager.log_handler.get_recent_logs(limit=20)
            else:
                logs = [
                    '[' + datetime.now().strftime('%H:%M:%S') + '] 🌐 Web dashboard active - Bot can be controlled via interface',
                    '[' + datetime.now().strftime('%H:%M:%S') + '] 📊 System monitoring active',
                    '[' + datetime.now().strftime('%H:%M:%S') + '] ✅ Ready for trading operations'
                ]
        except Exception as e:
            current_time = datetime.now().strftime('%H:%M:%S')
            logs = [
                f'[{current_time}] 🌐 Dashboard active',
                f'[{current_time}] 📊 System ready'
            ]

        return jsonify({
            'success': True,
            'logs': logs,
            'timestamp': time.time()
        })
    except Exception as e:
        logger.error(f"Console log API error: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'logs': ['Error loading console logs'],
            'timestamp': time.time()
        }), 500

@app.route('/api/rsi/<symbol>')
def get_rsi_data(symbol):
    """Get RSI data for a symbol"""
    try:
        # Try to get real RSI data
        try:
            from src.binance_client.client import BinanceClientWrapper
            binance_client = BinanceClientWrapper()

            # Get recent klines for RSI calculation
            klines = binance_client.client.futures_klines(
                symbol=symbol,
                interval='1h',
                limit=50
            )

            if klines and len(klines) >= 14:
                # Simple RSI calculation
                closes = [float(kline[4]) for kline in klines]
                rsi = calculate_simple_rsi(closes)

                return jsonify({
                    'success': True,
                    'symbol': symbol,
                    'rsi': rsi,
                    'timestamp': time.time()
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Insufficient data for RSI calculation'
                })

        except Exception as e:
            # Return mock RSI data if connection fails
            import random
            mock_rsi = 30 + (random.random() * 40)  # RSI between 30-70
            return jsonify({
                'success': True,
                'symbol': symbol,
                'rsi': round(mock_rsi, 2),
                'timestamp': time.time(),
                'note': 'Mock data - Binance connection unavailable'
            })

    except Exception as e:
        logger.error(f"RSI API error for {symbol}: {e}")
        return jsonify({
            'success': False, 
            'error': str(e),
            'symbol': symbol,
            'rsi': 50.0,  # Default neutral RSI
            'timestamp': time.time(),
            'note': 'Error occurred - showing default value'
        }), 200

def calculate_simple_rsi(prices, period=14):
    """Calculate simple RSI"""
    try:
        if len(prices) < period + 1:
            return None

        gains = []
        losses = []

        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))

        if len(gains) < period:
            return None

        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return round(rsi, 2)

    except Exception:
        return None

if __name__ == '__main__':
    logger.info("🌐 Starting simplified web dashboard...")
    app.run(host='0.0.0.0', port=5000, debug=True)