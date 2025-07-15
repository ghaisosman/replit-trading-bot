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
from pathlib import Path
import logging

# Define trades directory path
trades_dir = Path("trading_data/trades")

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Setup logging for web dashboard
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global bot instance - shared with main.py
bot_manager = None
bot_thread = None
bot_running = False

# Import the shared bot manager from main if it exists
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

                # Calculate position value and margin invested
                position_value = position.entry_price * position.quantity

                # Get leverage from strategy config
                strategy_config = current_bot.strategies.get(strategy_name, {}) if hasattr(current_bot, 'strategies') else {}
                leverage = strategy_config.get('leverage', 5)  # Default 5x leverage
                margin_invested = position_value / leverage

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
def bot_status():
    """Get current bot status"""
    global bot_running, bot_manager, shared_bot_manager
    try:
        current_bot = shared_bot_manager if shared_bot_manager else bot_manager
        if current_bot and hasattr(current_bot, 'is_running'):
            status = {
                'running': current_bot.is_running,
                'active_positions': len(current_bot.order_manager.active_positions) if hasattr(current_bot, 'order_manager') and current_bot.order_manager else 0,
                'strategies': list(current_bot.strategies.keys()) if hasattr(current_bot, 'strategies') else [],
            }
            return jsonify(status)
        else:
            return jsonify({
                'running': False,
                'active_positions': 0,
                'strategies': []
            })
    except Exception as e:
        logger.error(f"Error getting bot status: {e}")
        return jsonify({
            'running': False,
            'active_positions': 0,
            'strategies': []
        })

@app.route('/api/strategies')
def get_strategies():
    """Get all strategy configurations"""
    if IMPORTS_AVAILABLE:
        strategies = {}
        for name, overrides in trading_config_manager.strategy_overrides.items():
            base_config = {
                **trading_config_manager.default_params.to_dict(),
                **overrides
            }
            
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
                'rsi_short_entry': 60, 'rsi_short_exit': 30
            },
            'macd_divergence': {
                'symbol': 'BTCUSDT', 'margin': 23.0, 'leverage': 5, 'timeframe': '5m',
                'max_loss_pct': 10, 'macd_fast': 12, 'macd_slow': 26, 'macd_signal': 9,
                'min_histogram_threshold': 0.0001, 'min_distance_threshold': 0.005, 'confirmation_candles': 2
            }
        })

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
        basic_params = {k: v for k, v in data.items() if k in ['symbol', 'margin', 'leverage', 'timeframe']}
        if basic_params:
            trading_config_manager.update_strategy_params(strategy_name, basic_params)

        # Update strategy-specific config files safely
        try:
            if 'rsi' in strategy_name.lower():
                from src.execution_engine.strategies.rsi_oversold_config import RSIOversoldConfig
                rsi_updates = {k: v for k, v in data.items() if k.startswith('rsi_') or k == 'max_loss_pct'}
                if rsi_updates:
                    logger.info(f"📝 WEB INTERFACE: Updating RSI strategy config: {rsi_updates}")

            elif 'macd' in strategy_name.lower():
                from src.execution_engine.strategies.macd_divergence_config import MACDDivergenceConfig
                macd_updates = {k: v for k, v in data.items() if k.startswith('macd_') or k.startswith('min_') or k in ['confirmation_candles', 'max_loss_pct']}
                if macd_updates:
                    logger.info(f"📝 WEB INTERFACE: Updating MACD strategy config: {macd_updates}")

        except ImportError as e:
            logger.warning(f"Could not update strategy-specific config for {strategy_name}: {e}")

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
    """Get account balance"""
    try:
        current_bot = shared_bot_manager if shared_bot_manager else bot_manager
        if current_bot and hasattr(current_bot, 'balance_fetcher'):
            balance = current_bot.balance_fetcher.get_usdt_balance() or 0
            return jsonify({'balance': balance})
        else:
            return jsonify({'balance': 0})
    except Exception as e:
        logger.error(f"Error getting balance: {e}")
        return jsonify({'balance': 0})

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

                    # Calculate position value and margin invested
                    position_value_usdt = entry_price * quantity

                    # Get leverage from strategy config (default 5x if not found)
                    strategy_config = current_bot.strategies.get(strategy_name, {}) if hasattr(current_bot, 'strategies') else {}
                    leverage = strategy_config.get('leverage', 5)
                    margin_invested = position_value_usdt / leverage

                    # For futures trading, PnL percentage should be calculated against margin invested, not position value
                    pnl_percent = (pnl / margin_invested) * 100 if margin_invested > 0 else 0</old_str>

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
                        'pnl_percent': pnl_percent
                    })

        return jsonify({'success': True, 'positions': positions})
    except Exception as e:
        logging.getLogger(__name__).error(f"Error getting positions: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/rsi/<symbol>')
def get_rsi(symbol):
    """Get RSI value for a symbol"""
    try:
        # Import RSI calculation utilities
        import pandas as pd

        # Get historical data for RSI calculation
        klines = binance_client.get_klines(symbol=symbol, interval='1h', limit=15)
        if not klines:
            return jsonify({'success': False, 'error': f'Could not fetch klines for {symbol}'})

        # Convert to pandas DataFrame for easier calculation
        closes = [float(kline[4]) for kline in klines]

        if len(closes) < 14:
            return jsonify({'success': False, 'error': f'Not enough data points for RSI calculation for {symbol}'})

        # Calculate RSI
        rsi = calculate_rsi(closes)

        return jsonify({'success': True, 'rsi': round(rsi, 2)})
    except Exception as e:
        logger.error(f"Error calculating RSI for {symbol}: {e}")
        return jsonify({'success': False, 'error': f'Failed to calculate RSI: {str(e)}'})

def calculate_rsi(closes, period=14):
    """Calculate RSI (Relative Strength Index)"""
    if len(closes) < period + 1:
        return 50.0  # Default RSI if not enough data

    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]

    gains = [delta if delta > 0 else 0 for delta in deltas]
    losses = [-delta if delta < 0 else 0 for delta in deltas]

    # Calculate average gains and losses
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi

@app.route('/api/console-log')
def get_console_log():
    """Get recent console log output"""
    try:
        log_lines = []

        # Try multiple log file locations
        log_file_paths = [
            "trading_bot.log",
            "trading_data/bot.log", 
            "bot.log"
        ]

        for log_file_path in log_file_paths:
            if os.path.exists(log_file_path):
                try:
                    with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                        # Get last 150 lines for more context
                        recent_lines = lines[-150:] if len(lines) > 150 else lines
                        log_lines = [line.rstrip('\n\r') for line in recent_lines if line.strip()]
                    break
                except Exception as e:
                    logger.debug(f"Could not read log file {log_file_path}: {e}")
                    continue

        # If no file logs found, try to capture live logger output
        if not log_lines:
            # Check if we have access to a logger with handlers
            try:
                import logging
                root_logger = logging.getLogger()

                # Look for file handlers
                for handler in root_logger.handlers:
                    if hasattr(handler, 'baseFilename'):
                        try:
                            with open(handler.baseFilename, 'r', encoding='utf-8', errors='ignore') as f:
                                lines = f.readlines()
                                recent_lines = lines[-150:] if len(lines) > 150 else lines
                                log_lines = [line.rstrip('\n\r') for line in recent_lines if line.strip()]
                            break
                        except Exception as e:
                            logger.debug(f"Could not read handler log file: {e}")
                            continue
            except Exception as e:
                logger.debug(f"Could not access logger handlers: {e}")

        # Final fallback: provide basic status info with better context
        if not log_lines:
            current_bot = shared_bot_manager if shared_bot_manager else bot_manager
            if current_bot:
                if hasattr(current_bot, 'is_running') and current_bot.is_running:
                    # Get more detailed status
                    active_positions = len(current_bot.order_manager.active_positions) if current_bot.order_manager else 0
                    strategies = list(current_bot.strategies.keys()) if hasattr(current_bot, 'strategies') and current_bot.strategies else []

                    log_lines = [
                        "╔═══════════════════════════════════════════════════╗",
                        "║ 🤖 BOT STATUS                                    ║",
                        f"║ ⏰ {datetime.now().strftime('%H:%M:%S')}                                        ║",
                        "║                                                   ║",
                        "║ 🟢 Status: RUNNING                               ║",
                        f"║ 📊 Active Positions: {active_positions}                         ║",
                        f"║ 🎯 Active Strategies: {', '.join(strategies)}║" if strategies else "║ 🎯 Active Strategies: Loading...                ║",
                        "║                                                   ║",
                        "║ 💡 Console logs will appear here when bot        ║",
                        "║    performs market analysis and trading          ║",
                        "║                                                   ║",
                        "╚═══════════════════════════════════════════════════╝"
                    ]
                else:
                    log_lines = [
                        "╔═══════════════════════════════════════════════════╗",
                        "║ 🤖 BOT STATUS                                    ║",
                        f"║ ⏰ {datetime.now().strftime('%H:%M:%S')}                                        ║",
                        "║                                                   ║",
                        "║ 🔴 Status: STOPPED                               ║",
                        "║ 💡 Use the Start Bot button to begin trading     ║",
                        "║                                                   ║",
                        "╚═══════════════════════════════════════════════════╝"
                    ]
            else:
                log_lines = [
                    "╔═══════════════════════════════════════════════════╗",
                    "║ 🤖 BOT STATUS                                    ║",
                    f"║ ⏰ {datetime.now().strftime('%H:%M:%S')}                                        ║",
                    "║                                                   ║",
                    "║ ⚪ Status: NOT INITIALIZED                        ║",
                    "║ 💡 Bot is starting up...                         ║",
                    "║                                                   ║",
                    "╚═══════════════════════════════════════════════════╝"
                ]

        return jsonify({'success': True, 'logs': log_lines})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Failed to get console log: {e}'})

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
        if IMPORTS_AVAILABLE:
            strategies = list(trading_config_manager.strategy_overrides.keys())
        else:
            strategies = ['rsi_oversold', 'macd_divergence']

        return {
            'running': False,
            'active_positions': 0,
            'strategies': strategies
        }

    try:
        return {
            'running': True,
            'active_positions': len(bot_manager.order_manager.active_positions),
            'strategies': list(bot_manager.strategies.keys())
        }
    except:
        if IMPORTS_AVAILABLE:
            strategies = list(trading_config_manager.strategy_overrides.keys())
        else:
            strategies = ['rsi_oversold', 'macd_divergence']

        return {
            'running': bot_running,
            'active_positions': 0,
            'strategies': strategies
        }

def get_current_price(symbol):
    """Get current price for symbol"""
    try:
        ticker = binance_client.get_symbol_ticker(symbol)
        return float(ticker['price']) if ticker else None
    except:
        return None

def calculate_pnl(position, current_price):
    """Calculate PnL for position - matches console calculation"""
    if not current_price:
        return 0

    # For futures trading, PnL calculation
    if position.side == 'BUY':  # Long position
        pnl = (current_price - position.entry_price) * position.quantity
    else:  # Short position (SELL)
        pnl = (position.entry_price - current_price) * position.quantity

    return pnl

if __name__ == '__main__':
    logger.info("🌐 WEB DASHBOARD: Starting web interface on http://0.0.0.0:5000")
    logger.info("🌐 WEB DASHBOARD: Dashboard ready for bot control")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)