#!/usr/bin/env python3
"""
Trading Bot Web Dashboard
Complete web interface for managing the trading bot
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for
import json
import asyncio
import threading
import os
from datetime import datetime, timedelta
import pandas as pd
import plotly.graph_objs as go
import plotly.utils
from pathlib import Path
from src.config.trading_config import trading_config_manager

def _persist_config_to_file():
    """Persist current trading config manager state to trading_config.py file"""
    try:
        # Read the current file
        config_file_path = 'src/config/trading_config.py'
        with open(config_file_path, 'r') as f:
            lines = f.readlines()
        
        # Find the start and end of strategy_overrides
        start_idx = None
        end_idx = None
        brace_count = 0
        
        for i, line in enumerate(lines):
            if 'self.strategy_overrides = {' in line:
                start_idx = i
                brace_count = line.count('{') - line.count('}')
                continue
            
            if start_idx is not None:
                brace_count += line.count('{') - line.count('}')
                if brace_count == 0:
                    end_idx = i
                    break
        
        if start_idx is None or end_idx is None:
            logger.error("Could not find strategy_overrides section in config file")
            return False
        
        # Build the new strategy_overrides section
        new_lines = []
        new_lines.append("        self.strategy_overrides = {\n")
        
        for strategy_name, overrides in trading_config_manager.strategy_overrides.items():
            new_lines.append(f"            '{strategy_name}': {{\n")
            for key, value in overrides.items():
                if isinstance(value, str):
                    new_lines.append(f"                '{key}': '{value}',\n")
                else:
                    new_lines.append(f"                '{key}': {value},\n")
            new_lines.append("            },\n")
        
        new_lines.append("        }\n")
        
        # Replace the section
        new_content = lines[:start_idx] + new_lines + lines[end_idx + 1:]
        
        # Write back to file
        with open(config_file_path, 'w') as f:
            f.writelines(new_content)
            
        logger.info("💾 Configuration persisted to trading_config.py")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to persist config to file: {e}")
        return False
from src.config.global_config import global_config
from src.binance_client.client import BinanceClientWrapper
from src.data_fetcher.price_fetcher import PriceFetcher
from src.data_fetcher.balance_fetcher import BalanceFetcher
from src.bot_manager import BotManager
import logging
from src.utils.logger import setup_logger
from src.analytics.ml_analyzer import MLTradeAnalyzer

# Define trades directory path
trades_dir = Path("trading_data/trades")

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

        # Get active positions from both shared and standalone bot
        active_positions = []
        current_bot = shared_bot_manager if shared_bot_manager else bot_manager
        
        if current_bot and hasattr(current_bot, 'order_manager') and current_bot.order_manager:
            for strategy_name, position in current_bot.order_manager.active_positions.items():
                current_price = get_current_price(position.symbol)
                pnl = calculate_pnl(position, current_price) if current_price else 0
                
                # Calculate PnL percentage against margin (for futures with leverage)
                position_value = position.entry_price * position.quantity
                margin_invested = position_value / 5  # Default 5x leverage
                pnl_percent = (pnl / margin_invested) * 100 if margin_invested > 0 else 0
                
                active_positions.append({
                    'strategy': strategy_name,
                    'symbol': position.symbol,
                    'side': position.side,
                    'entry_price': position.entry_price,
                    'quantity': position.quantity,
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

        # Update strategy parameters in config manager
        trading_config_manager.update_strategy_params(strategy_name, data)

        # PERSIST CHANGES TO FILE - Write updated config back to trading_config.py
        _persist_config_to_file()

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
        elif bot_manager and strategy_name in bot_manager.strategies:
            bot_manager.strategies[strategy_name].update(data)
            logger.info(f"📝 WEB INTERFACE: Updated {strategy_name} config in standalone bot: {data}")
            bot_updated = True

        message = f'Strategy {strategy_name} updated and saved to file'
        if bot_updated:
            message += ' (applied to running bot immediately)'
        else:
            message += ' (will persist after restart)'

        logger.info(f"💾 PERSISTED: {strategy_name} config saved to trading_config.py")

        return jsonify({'success': True, 'message': message})
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
        current_bot = shared_bot_manager if shared_bot_manager else bot_manager
        
        if current_bot and hasattr(current_bot, 'order_manager') and current_bot.order_manager:
            for strategy_name, position in current_bot.order_manager.active_positions.items():
                current_price = get_current_price(position.symbol)
                pnl = calculate_pnl(position, current_price) if current_price else 0
                
                # Calculate PnL percentage against margin (for futures with leverage)
                position_value = position.entry_price * position.quantity
                margin_invested = position_value / 5  # Default 5x leverage
                pnl_percent = (pnl / margin_invested) * 100 if margin_invested > 0 else 0
                
                positions.append({
                    'strategy': strategy_name,
                    'symbol': position.symbol,
                    'side': position.side,
                    'entry_price': position.entry_price,
                    'quantity': position.quantity,
                    'current_price': current_price,
                    'pnl': pnl,
                    'pnl_percent': pnl_percent
                })
        return jsonify({'success': True, 'positions': positions})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Failed to get positions: {e}'})

@app.route('/api/recent_trades')
def recent_trades():
    """Get recent trades data"""
    try:
        trades_file = trades_dir / "all_trades.json"
        if trades_file.exists():
            with open(trades_file, 'r') as f:
                trades = json.load(f)

            # Get last 10 trades
            recent = trades[-10:] if trades else []
            return jsonify({'success': True, 'trades': recent})
        else:
            return jsonify({'success': True, 'trades': []})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Initialize ML analyzer
ml_analyzer = MLTradeAnalyzer()

@app.route('/ml-reports')
def ml_reports():
    """ML Reports dashboard page"""
    return render_template('ml_reports.html')

@app.route('/api/train_models', methods=['POST'])
def train_ml_models():
    """Train ML models and return results"""
    try:
        results = ml_analyzer.train_models()
        if "error" in results:
            return jsonify({'success': False, 'error': results['error']})
        return jsonify({'success': True, **results})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Failed to train models: {e}'})

@app.route('/api/ml_insights')
def get_ml_insights():
    """Get ML trading insights"""
    try:
        insights = ml_analyzer.generate_insights()
        if "error" in insights:
            return jsonify({'success': False, 'error': insights['error']})
        return jsonify({'success': True, 'insights': insights})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Failed to generate insights: {e}'})

@app.route('/api/ml_predictions')
def get_ml_predictions():
    """Get ML market predictions"""
    try:
        # Sample predictions for current market conditions
        sample_features = [
            {
                'strategy': 'rsi_oversold',
                'symbol': 'BTCUSDT',
                'side': 'BUY',
                'leverage': 5,
                'position_size_usdt': 100,
                'rsi_entry': 25,
                'macd_entry': -0.5,
                'hour_of_day': datetime.now().hour,
                'day_of_week': datetime.now().weekday(),
                'month': datetime.now().month,
                'market_trend': 'BULLISH',
                'volatility_score': 0.3,
                'signal_strength': 0.8
            },
            {
                'strategy': 'macd_divergence',
                'symbol': 'ETHUSDT',
                'side': 'BUY',
                'leverage': 5,
                'position_size_usdt': 100,
                'rsi_entry': 45,
                'macd_entry': 0.2,
                'hour_of_day': datetime.now().hour,
                'day_of_week': datetime.now().weekday(),
                'month': datetime.now().month,
                'market_trend': 'BULLISH',
                'volatility_score': 0.4,
                'signal_strength': 0.7
            }
        ]
        
        predictions = []
        for features in sample_features:
            prediction = ml_analyzer.predict_trade_outcome(features)
            if "error" not in prediction:
                prediction['symbol'] = features['symbol']
                prediction['predicted_profitable'] = prediction.get('profit_probability', 0) > 0.5
                predictions.append(prediction)
        
        return jsonify({'success': True, 'predictions': predictions})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Failed to get predictions: {e}'})

@app.route('/api/daily-report')
def get_daily_report():
    """Get daily trading report"""
    try:
        from src.analytics.trade_logger import trade_logger
        from datetime import datetime, timedelta

        # Get yesterday's data by default
        date = request.args.get('date')
        if date:
            report_date = datetime.strptime(date, '%Y-%m-%d')
        else:
            report_date = datetime.now() - timedelta(days=1)

        daily_summary = trade_logger.get_daily_summary(report_date)
        return jsonify(daily_summary)
    except Exception as e:
        return jsonify({'error': f'Failed to get daily report: {e}'})

@app.route('/api/daily-report/send', methods=['POST'])
def send_daily_report():
    """Send daily report to Telegram"""
    try:
        from src.analytics.daily_reporter import DailyReporter
        from src.reporting.telegram_reporter import TelegramReporter
        from datetime import datetime, timedelta

        # Get date from request or use yesterday
        data = request.get_json() or {}
        date = data.get('date')
        if date:
            report_date = datetime.strptime(date, '%Y-%m-%d')
        else:
            report_date = datetime.now() - timedelta(days=1)

        # Initialize and send report
        telegram_reporter = TelegramReporter()
        daily_reporter = DailyReporter(telegram_reporter)
        success = daily_reporter.send_manual_report(report_date)

        return jsonify({'success': success, 'message': 'Report sent' if success else 'Failed to send report'})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Failed to send report: {e}'})

@app.route('/api/trade-data/export')
def export_trade_data():
    """Export trade data for ML analysis"""
    try:
        from src.analytics.trade_logger import trade_logger
        filename = trade_logger.export_for_ml()
        if filename:
            return jsonify({'success': True, 'filename': filename})
        else:
            return jsonify({'success': False, 'error': 'No data to export'})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Failed to export data: {e}'})

@app.route('/api/console-log')
def get_console_log():
    """Get recent console log output"""
    try:
        # Read recent logs from the logger
        import logging
        
        # Get the root logger's handlers
        root_logger = logging.getLogger()
        log_lines = []
        
        # Try to get logs from file handler if it exists
        try:
            log_file_path = "trading_data/bot.log"
            if os.path.exists(log_file_path):
                with open(log_file_path, 'r') as f:
                    lines = f.readlines()
                    # Get last 100 lines
                    recent_lines = lines[-100:] if len(lines) > 100 else lines
                    log_lines = [line.strip() for line in recent_lines if line.strip()]
        except Exception as e:
            logger.debug(f"Could not read log file: {e}")
        
        # If no file logs, provide basic status info
        if not log_lines:
            current_bot = shared_bot_manager if shared_bot_manager else bot_manager
            if current_bot:
                if hasattr(current_bot, 'is_running') and current_bot.is_running:
                    log_lines = [
                        f"🤖 Bot Status: RUNNING",
                        f"📊 Active Positions: {len(current_bot.order_manager.active_positions) if current_bot.order_manager else 0}",
                        f"⏰ {datetime.now().strftime('%H:%M:%S')} - Bot monitoring markets..."
                    ]
                else:
                    log_lines = [
                        f"🤖 Bot Status: STOPPED",
                        f"⏰ {datetime.now().strftime('%H:%M:%S')} - Use web interface to start bot"
                    ]
            else:
                log_lines = [
                    f"🤖 Bot Status: NOT INITIALIZED", 
                    f"⏰ {datetime.now().strftime('%H:%M:%S')} - Waiting for bot startup"
                ]
        
        return jsonify({'success': True, 'logs': log_lines})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Failed to get console log: {e}'})

@app.route('/api/current-config')
def get_current_config():
    """Get current bot configuration"""
    try:
        config_data = {}
        
        # Get default parameters
        config_data['default_params'] = trading_config_manager.default_params.to_dict()
        
        # Get strategy overrides
        config_data['strategy_overrides'] = trading_config_manager.strategy_overrides.copy()
        
        # Get final configurations for each strategy
        config_data['final_configs'] = {}
        for strategy_name in trading_config_manager.strategy_overrides.keys():
            base_config = {}
            final_config = trading_config_manager.get_strategy_config(strategy_name, base_config)
            config_data['final_configs'][strategy_name] = final_config
        
        # Check if bot is running and get its active config
        config_data['bot_status'] = {
            'running': False,
            'active_strategies': []
        }
        
        if bot_manager and hasattr(bot_manager, 'strategies'):
            config_data['bot_status']['running'] = getattr(bot_manager, 'is_running', False)
            config_data['bot_status']['active_strategies'] = list(bot_manager.strategies.keys()) if bot_manager.strategies else []
            
            # Get actual bot strategy configs
            if bot_manager.strategies:
                config_data['bot_active_configs'] = bot_manager.strategies.copy()
        
        # Also check shared bot manager
        shared_bot_manager = getattr(sys.modules.get('__main__', None), 'bot_manager', None)
        if shared_bot_manager and hasattr(shared_bot_manager, 'strategies'):
            config_data['bot_status']['running'] = getattr(shared_bot_manager, 'is_running', False)
            config_data['bot_status']['active_strategies'] = list(shared_bot_manager.strategies.keys()) if shared_bot_manager.strategies else []
            
            if shared_bot_manager.strategies:
                config_data['bot_active_configs'] = shared_bot_manager.strategies.copy()
        
        return jsonify({'success': True, 'config': config_data})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Failed to get configuration: {e}'})

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