
#!/usr/bin/env python3
"""
Trading Bot Web Dashboard
Complete web interface for managing the trading bot
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for
import json
import asyncio
import threading
from datetime import datetime, timedelta
import pandas as pd
import plotly.graph_objs as go
import plotly.utils
from src.config.trading_config import trading_config_manager
from src.config.global_config import global_config
from src.binance_client.client import BinanceClientWrapper
from src.data_fetcher.price_fetcher import PriceFetcher
from src.data_fetcher.balance_fetcher import BalanceFetcher
from src.bot_manager import BotManager
import logging
from src.utils.logger import setup_logger

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Setup logging for web dashboard
setup_logger()
logger = logging.getLogger(__name__)

# Global bot instance - shared with main.py
bot_manager = None
bot_thread = None
bot_running = False

# Import the shared bot manager from main if it exists
import sys
shared_bot_manager = None
if hasattr(sys.modules.get('__main__', None), 'bot_manager'):
    shared_bot_manager = sys.modules['__main__'].bot_manager

# Initialize clients for web interface
binance_client = BinanceClientWrapper()
price_fetcher = PriceFetcher(binance_client)
balance_fetcher = BalanceFetcher(binance_client)

@app.route('/')
def dashboard():
    """Main dashboard page"""
    try:
        # Get current bot status
        status = get_bot_status()
        
        # Get balance
        balance = balance_fetcher.get_usdt_balance() or 0
        
        # Get current strategies
        strategies = trading_config_manager.strategy_overrides
        
        # Get active positions
        active_positions = []
        if bot_manager and bot_manager.order_manager:
            for strategy_name, position in bot_manager.order_manager.active_positions.items():
                current_price = get_current_price(position.symbol)
                pnl = calculate_pnl(position, current_price) if current_price else 0
                active_positions.append({
                    'strategy': strategy_name,
                    'symbol': position.symbol,
                    'side': position.side,
                    'entry_price': f"${position.entry_price:,.1f}",
                    'quantity': f"{position.quantity:,.1f}",
                    'current_price': f"${current_price:,.1f}" if current_price else "N/A",
                    'pnl': f"${pnl:,.1f}" if pnl else "$0.0",
                    'pnl_percent': f"{(pnl / (position.entry_price * position.quantity)) * 100:.1f}%" if position.entry_price * position.quantity > 0 else "0.0%"
                })
        
        return render_template('dashboard.html', 
                             status=status,
                             balance=balance,
                             strategies=strategies,
                             active_positions=active_positions)
    except Exception as e:
        return f"Error loading dashboard: {e}"

@app.route('/chart/<symbol>')
def chart(symbol):
    """Display trading chart for a symbol"""
    try:
        # Get OHLCV data
        df = price_fetcher.get_ohlcv_data(symbol, '15m', limit=100)
        if df is None or df.empty:
            return f"No data available for {symbol}"
        
        # Calculate indicators
        df = price_fetcher.calculate_indicators(df)
        
        # Create candlestick chart
        fig = go.Figure()
        
        # Add candlestick
        fig.add_trace(go.Candlestick(
            x=df.index,
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='Price'
        ))
        
        # Add RSI if available
        if 'rsi' in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index,
                y=df['rsi'],
                name='RSI',
                yaxis='y2',
                line=dict(color='purple')
            ))
        
        # Add MACD if available
        if 'macd' in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index,
                y=df['macd'],
                name='MACD',
                yaxis='y3',
                line=dict(color='blue')
            ))
            
        if 'macd_signal' in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index,
                y=df['macd_signal'],
                name='MACD Signal',
                yaxis='y3',
                line=dict(color='red')
            ))
        
        # Update layout
        fig.update_layout(
            title=f'{symbol} Trading Chart',
            yaxis=dict(title='Price', side='left'),
            yaxis2=dict(title='RSI', side='right', overlaying='y', range=[0, 100]),
            yaxis3=dict(title='MACD', side='right', overlaying='y', position=0.9),
            xaxis_rangeslider_visible=False,
            height=600
        )
        
        chart_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        
        return render_template('chart.html', symbol=symbol, chart=chart_json)
    except Exception as e:
        return f"Error loading chart: {e}"

@app.route('/api/bot/start', methods=['POST'])
def start_bot():
    """Start the trading bot"""
    global bot_manager, bot_thread, bot_running, shared_bot_manager
    
    try:
        # Always try to get the latest shared bot manager
        shared_bot_manager = getattr(sys.modules.get('__main__', None), 'bot_manager', None)
        
        # Check if there's a shared bot manager from main.py
        if shared_bot_manager and hasattr(shared_bot_manager, 'is_running'):
            if shared_bot_manager.is_running:
                return jsonify({'success': False, 'message': 'Bot is already running in console'})
            
            # Use the shared bot manager and start it
            bot_manager = shared_bot_manager
            
            # Log the web start action to console
            logger = logging.getLogger(__name__)
            logger.info("🌐 WEB INTERFACE: Starting bot via web dashboard")
            
            # Also log to bot manager's logger if available
            if hasattr(shared_bot_manager, 'logger'):
                shared_bot_manager.logger.info("🌐 WEB INTERFACE: Bot started via web dashboard")
            
            # Start the shared bot in the main event loop
            def start_shared_bot():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    # Set running state
                    shared_bot_manager.is_running = True
                    logger.info("🚀 BOT STARTED VIA WEB INTERFACE")
                    
                    # Send Telegram notification about web start
                    try:
                        from src.data_fetcher.balance_fetcher import BalanceFetcher
                        balance_fetcher = BalanceFetcher(shared_bot_manager.binance_client)
                        balance = balance_fetcher.get_usdt_balance() or 0
                        
                        pairs = [config['symbol'] for config in shared_bot_manager.strategies.values()]
                        strategy_names = list(shared_bot_manager.strategies.keys())
                        
                        shared_bot_manager.telegram_reporter.report_bot_startup(
                            pairs=pairs,
                            strategies=strategy_names,
                            balance=balance,
                            open_trades=0
                        )
                    except Exception as e:
                        logger.warning(f"Failed to send startup notification: {e}")
                    
                    # Start the bot's main trading loop
                    loop.run_until_complete(shared_bot_manager._main_trading_loop())
                except Exception as e:
                    logger.error(f"Bot error: {e}")
                finally:
                    shared_bot_manager.is_running = False
                    logger.info("🔴 BOT STOPPED VIA WEB INTERFACE")
                    loop.close()
            
            bot_thread = threading.Thread(target=start_shared_bot, daemon=True)
            bot_thread.start()
            bot_running = True
            
            return jsonify({'success': True, 'message': 'Bot started from web interface'})
        
        # Fallback: create new bot instance if no shared manager exists
        if bot_running:
            return jsonify({'success': False, 'message': 'Bot is already running'})
        
        logger = logging.getLogger(__name__)
        logger.info("🌐 WEB INTERFACE: Creating new bot instance via web dashboard")
        
        bot_manager = BotManager()
        bot_running = True
        
        # Start bot in separate thread
        def run_bot():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            logger = logging.getLogger(__name__)
            try:
                logger.info("🚀 STARTING BOT FROM WEB INTERFACE")
                loop.run_until_complete(bot_manager.start())
            except Exception as e:
                logger.error(f"Bot error: {e}")
            finally:
                global bot_running
                bot_running = False
                logger.info("🔴 BOT STOPPED FROM WEB INTERFACE")
                loop.close()
        
        bot_thread = threading.Thread(target=run_bot, daemon=True)
        bot_thread.start()
        
        return jsonify({'success': True, 'message': 'Bot started successfully'})
    except Exception as e:
        bot_running = False
        return jsonify({'success': False, 'message': f'Failed to start bot: {e}'})

@app.route('/api/bot/stop', methods=['POST'])
def stop_bot():
    """Stop the trading bot"""
    global bot_manager, bot_running, shared_bot_manager
    
    try:
        logger = logging.getLogger(__name__)
        
        # Always try to get the latest shared bot manager
        shared_bot_manager = getattr(sys.modules.get('__main__', None), 'bot_manager', None)
        
        # Check if there's a shared bot manager from main.py
        if shared_bot_manager and hasattr(shared_bot_manager, 'is_running'):
            if shared_bot_manager.is_running:
                logger.info("🌐 WEB INTERFACE: Stopping bot via web dashboard")
                
                # Also log to bot manager's logger if available
                if hasattr(shared_bot_manager, 'logger'):
                    shared_bot_manager.logger.info("🌐 WEB INTERFACE: Bot stopped via web dashboard")
                
                # Stop the shared bot by setting is_running to False
                shared_bot_manager.is_running = False
                
                # Send stop notification
                try:
                    shared_bot_manager.telegram_reporter.report_bot_stopped("Manual stop via web interface")
                    logger.info("🔴 BOT STOPPED VIA WEB INTERFACE")
                except Exception as e:
                    logger.warning(f"Failed to send stop notification: {e}")
                
                bot_running = False
                return jsonify({'success': True, 'message': 'Bot stopped from web interface'})
            else:
                return jsonify({'success': False, 'message': 'Bot is not running in console'})
        
        # Fallback to standalone bot
        if not bot_running or not bot_manager:
            return jsonify({'success': False, 'message': 'Bot is not running'})
        
        logger.info("🌐 WEB INTERFACE: Stopping standalone bot via web dashboard")
        
        # Stop the bot
        bot_manager.is_running = False
        bot_running = False
        
        # Send stop notification for standalone bot
        try:
            bot_manager.telegram_reporter.report_bot_stopped("Manual stop via web interface")
            logger.info("🔴 STANDALONE BOT STOPPED VIA WEB INTERFACE")
        except Exception as e:
            logger.warning(f"Failed to send stop notification: {e}")
        
        return jsonify({'success': True, 'message': 'Bot stopped successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to stop bot: {e}'})

@app.route('/api/bot/status')
def bot_status():
    """Get current bot status"""
    status = get_bot_status()
    return jsonify(status)

@app.route('/api/strategies')
def get_strategies():
    """Get all strategy configurations"""
    strategies = {}
    for name, overrides in trading_config_manager.strategy_overrides.items():
        strategies[name] = {
            **trading_config_manager.default_params.to_dict(),
            **overrides
        }
    return jsonify(strategies)

@app.route('/api/strategies/<strategy_name>', methods=['POST'])
def update_strategy(strategy_name):
    """Update strategy configuration"""
    try:
        data = request.get_json()
        
        # Update strategy parameters
        trading_config_manager.update_strategy_params(strategy_name, data)
        
        # If bot is running, update its configuration too
        if bot_manager and strategy_name in bot_manager.strategies:
            bot_manager.strategies[strategy_name].update(data)
        
        return jsonify({'success': True, 'message': f'Strategy {strategy_name} updated'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to update strategy: {e}'})

@app.route('/api/default-params', methods=['POST'])
def update_default_params():
    """Update default trading parameters"""
    try:
        data = request.get_json()
        trading_config_manager.update_default_params(data)
        
        return jsonify({'success': True, 'message': 'Default parameters updated'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to update parameters: {e}'})

@app.route('/api/balance')
def get_balance():
    """Get account balance"""
    try:
        balance = balance_fetcher.get_usdt_balance() or 0
        return jsonify({'balance': balance})
    except Exception as e:
        return jsonify({'error': f'Failed to get balance: {e}'})

@app.route('/api/price/<symbol>')
def get_price(symbol):
    """Get current price for symbol"""
    try:
        price = get_current_price(symbol)
        return jsonify({'symbol': symbol, 'price': price})
    except Exception as e:
        return jsonify({'error': f'Failed to get price: {e}'})

@app.route('/api/positions')
def get_positions():
    """Get active positions"""
    try:
        positions = []
        if bot_manager and bot_manager.order_manager:
            for strategy_name, position in bot_manager.order_manager.active_positions.items():
                current_price = get_current_price(position.symbol)
                pnl = calculate_pnl(position, current_price) if current_price else 0
                positions.append({
                    'strategy': strategy_name,
                    'symbol': position.symbol,
                    'side': position.side,
                    'entry_price': position.entry_price,
                    'quantity': position.quantity,
                    'current_price': current_price,
                    'pnl': pnl,
                    'pnl_percent': (pnl / (position.entry_price * position.quantity)) * 100 if position.entry_price * position.quantity > 0 else 0
                })
        return jsonify(positions)
    except Exception as e:
        return jsonify({'error': f'Failed to get positions: {e}'})

def get_bot_status():
    """Get current bot status"""
    global bot_running, bot_manager, shared_bot_manager
    
    # Always get fresh reference to shared bot manager
    shared_bot_manager = getattr(sys.modules.get('__main__', None), 'bot_manager', None)
    
    # Check shared bot manager first
    if shared_bot_manager and hasattr(shared_bot_manager, 'is_running'):
        try:
            return {
                'running': shared_bot_manager.is_running,
                'active_positions': len(shared_bot_manager.order_manager.active_positions) if shared_bot_manager.order_manager else 0,
                'strategies': list(shared_bot_manager.strategies.keys()) if shared_bot_manager.strategies else []
            }
        except Exception as e:
            logging.getLogger(__name__).debug(f"Error getting shared bot status: {e}")
    
    # Fallback to standalone bot
    if not bot_running or not bot_manager:
        return {
            'running': False,
            'active_positions': 0,
            'strategies': list(trading_config_manager.strategy_overrides.keys())
        }
    
    try:
        return {
            'running': True,
            'active_positions': len(bot_manager.order_manager.active_positions),
            'strategies': list(bot_manager.strategies.keys())
        }
    except:
        return {
            'running': bot_running,
            'active_positions': 0,
            'strategies': list(trading_config_manager.strategy_overrides.keys())
        }

def get_current_price(symbol):
    """Get current price for symbol"""
    try:
        ticker = binance_client.get_symbol_ticker(symbol)
        return float(ticker['price']) if ticker else None
    except:
        return None

def calculate_pnl(position, current_price):
    """Calculate PnL for position"""
    if not current_price:
        return 0
    
    if position.side == 'BUY':
        return (current_price - position.entry_price) * position.quantity
    else:
        return (position.entry_price - current_price) * position.quantity

if __name__ == '__main__':
    logger.info("🌐 WEB DASHBOARD: Starting web interface on http://0.0.0.0:5000")
    logger.info("🌐 WEB DASHBOARD: Dashboard ready for bot control")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
