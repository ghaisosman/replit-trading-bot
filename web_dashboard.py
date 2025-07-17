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

# SINGLE SOURCE CONTROL: Web dashboard should only be launched from main.py
# This prevents conflicts and ensures proper startup sequence
app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Enable CORS for web dashboard with specific configuration
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Global error handler to prevent 502 errors
@app.errorhandler(Exception)
def handle_exception(e):
    """Global exception handler to prevent HTTP 502 errors"""
    try:
        logger.error(f"Unhandled exception: {e}")
    except:
        pass

    # Return a valid JSON response instead of letting Flask crash
    return jsonify({
        'success': False,
        'error': 'Internal server error',
        'message': 'Service temporarily unavailable'
    }), 200  # Return 200 to prevent 502

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

# Global variables for bot integration
bot_manager = None
shared_bot_manager = None
current_bot = None

def get_bot_manager_from_main():
    """Try to get bot manager from main module with better error handling"""
    try:
        import sys
        main_module = sys.modules.get('__main__')
        if main_module and hasattr(main_module, 'bot_manager'):
            manager = getattr(main_module, 'bot_manager')
            if manager is not None:
                print(f"✅ Bot manager loaded from main module: {type(manager).__name__}")
                return manager

        # Also try to get from global scope
        if 'bot_manager' in globals() and globals()['bot_manager'] is not None:
            manager = globals()['bot_manager']
            print(f"✅ Bot manager loaded from globals: {type(manager).__name__}")
            return manager

        print("⚠️ Bot manager not found in main module or globals")
        return None
    except Exception as e:
        print(f"❌ Error loading bot manager: {e}")
        return None

# Try to get bot manager from main module
bot_manager = get_bot_manager_from_main()
shared_bot_manager = bot_manager
current_bot = bot_manager

# Dummy classes for when bot manager is not available
class DummyBotManager:
    def __init__(self):
        self.is_running = False
        self.strategies = {
            'rsi_oversold': {
                'symbol': 'SOLUSDT', 'margin': 5.0, 'leverage': 5, 'timeframe': '15m',
                'max_loss_pct': 10, 'assessment_interval': 60,
                'rsi_long_entry': 40, 'rsi_long_exit': 70,
                'rsi_short_entry': 60, 'rsi_short_exit': 30,
                'decimals': 2
            },
            'macd_divergence': {
                'symbol': 'ETHUSDT', 'margin': 10.0, 'leverage': 5, 'timeframe': '15m',
                'max_loss_pct': 10, 'assessment_interval': 60,
                'macd_fast': 12, 'macd_slow': 26, 'macd_signal': 9,
                'min_histogram_threshold': 0.0001, 'min_distance_threshold': 0.005,
                'confirmation_candles': 2, 'decimals': 2
            },
            'RSI_OVERSOLD1': {
                'symbol': 'XRPUSDT', 'margin': 5.0, 'leverage': 5, 'timeframe': '15m',
                'max_loss_pct': 10, 'assessment_interval': 60,
                'rsi_long_entry': 40, 'rsi_long_exit': 70,
                'rsi_short_entry': 60, 'rsi_short_exit': 30,
                'decimals': 3
            },
            'liquidity_reversal': {
                'symbol': 'BTCUSDT', 'margin': 15.0, 'leverage': 5, 'timeframe': '15m',
                'max_loss_pct': 8, 'assessment_interval': 30,
                'swing_lookback': 20, 'sweep_threshold': 0.5,
                'volume_surge_multiplier': 2.0, 'confirmation_candles': 2,
                'profit_target_method': 'mean_reversion', 'fixed_profit_percent': 2.0,
                'mean_reversion_periods': 50, 'mean_reversion_buffer': 0.5,
                'rsi_exit_overbought': 70, 'rsi_exit_oversold': 30,
                'dynamic_profit_min': 1.0, 'dynamic_profit_max': 4.0,
                'decimals': 3
            }
        }

    def get_bot_status(self):
        return {
            'is_running': False,
            'active_positions': 0,
            'strategies': [],
            'balance': 0
        }

    def get_all_strategies(self):
        """Return default strategies for web dashboard configuration"""
        return self.strategies

    def update_strategy_config(self, strategy_name, updates):
        if strategy_name in self.strategies:
            self.strategies[strategy_name].update(updates)

class DummyConfigManagerFull:
    def __init__(self):
        self.strategy_overrides = {
            'rsi_oversold': {'symbol': 'SOLUSDT', 'margin': 5.0, 'leverage': 5, 'timeframe': '15m'},
            'macd_divergence': {'symbol': 'ETHUSDT', 'margin': 10.0, 'leverage': 5, 'timeframe': '15m'},
            'RSI_OVERSOLD1': {'symbol': 'XRPUSDT', 'margin': 5.0, 'leverage': 5, 'timeframe': '15m'},
            'liquidity_reversal': {'symbol': 'BTCUSDT', 'margin': 15.0, 'leverage': 5, 'timeframe': '15m'}
        }

    def get_all_strategies(self):
        return self.strategy_overrides

    def update_strategy_params(self, strategy_name, updates):
        if strategy_name not in self.strategy_overrides:
            self.strategy_overrides[strategy_name] = {}
        self.strategy_overrides[strategy_name].update(updates)

class DummyBalanceFetcher:
    def get_usdt_balance(self):
        return 0.0

# Initialize fallback instances only if no real bot manager exists
if not bot_manager and not IMPORTS_AVAILABLE:
    bot_manager = DummyBotManager()
    shared_bot_manager = bot_manager
    current_bot = bot_manager
    print("🔄 Using dummy bot manager for API endpoints")
elif not bot_manager:
    print("⚠️ No bot manager available but imports are working")

# Create instances for dashboard - WEB DASHBOARD IS SINGLE SOURCE OF TRUTH
try:
    # Always use the trading_config_manager for configuration management
    from src.config.trading_config import trading_config_manager
    print("✅ Trading config manager loaded - Web dashboard is single source of truth")
    
    # Set up balance fetcher
    try:
        if current_bot and hasattr(current_bot, 'balance_fetcher'):
            balance_fetcher = current_bot.balance_fetcher
        else:
            from src.data_fetcher.balance_fetcher import BalanceFetcher
            from src.binance_client.client import BinanceClientWrapper
            binance_client = BinanceClientWrapper()
            balance_fetcher = BalanceFetcher(binance_client)
    except:
        balance_fetcher = DummyBalanceFetcher()
        
except ImportError:
    # Fallback to dummy config manager only if imports fail
    trading_config_manager = DummyConfigManagerFull()
    balance_fetcher = DummyBalanceFetcher()
    print("⚠️ Using dummy config manager - Limited functionality")

@app.route('/')
def dashboard():
    """Main dashboard page"""
    try:
        # Get current bot status directly from bot manager
        current_bot = get_current_bot_manager()

        if current_bot and hasattr(current_bot, 'get_bot_status') and not isinstance(current_bot, DummyBotManager):
            bot_status_data = current_bot.get_bot_status()
            status = {
                'is_running': bot_status_data.get('is_running', False),
                'active_positions': bot_status_data.get('active_positions', 0),
                'strategies': bot_status_data.get('strategies', [])
            }
        else:
            status = {
                'is_running': False,
                'active_positions': 0,
                'strategies': []
            }

        # Get current bot manager
        current_bot = get_current_bot_manager()

        # Get balance and strategies with improved error handling
        if IMPORTS_AVAILABLE:
            try:
                balance = balance_fetcher.get_usdt_balance() or 0
            except:
                balance = 0

            # Try to get strategies from bot manager first, then fallback to config manager
            strategies = {}
            if current_bot and hasattr(current_bot, 'strategies'):
                strategies = current_bot.strategies
                print(f"✅ Got strategies from bot manager: {list(strategies.keys())}")
            elif hasattr(trading_config_manager, 'get_all_strategies'):
                try:
                    strategies = trading_config_manager.get_all_strategies()
                    print(f"✅ Got strategies from config manager: {list(strategies.keys())}")
                except Exception as e:
                    print(f"Error getting strategies from config manager: {e}")
                    strategies = {}

            # Ensure we always have strategies available for display
            if not strategies:
                strategies = {
                    'rsi_oversold': {
                        'symbol': 'SOLUSDT', 'margin': 5.0, 'leverage': 5, 'timeframe': '15m',
                        'max_loss_pct': 10, 'assessment_interval': 60
                    },
                    'macd_divergence': {
                        'symbol': 'ETHUSDT', 'margin': 10.0, 'leverage': 5, 'timeframe': '15m',
                        'max_loss_pct': 10, 'assessment_interval': 60
                    },
                    'RSI_OVERSOLD1': {
                        'symbol': 'XRPUSDT', 'margin': 5.0, 'leverage': 5, 'timeframe': '15m',
                        'max_loss_pct': 10, 'assessment_interval': 60
                    },
                    'liquidity_reversal': {
                        'symbol': 'BTCUSDT', 'margin': 15.0, 'leverage': 5, 'timeframe': '15m',
                        'max_loss_pct': 10, 'assessment_interval': 60
                    }
                }
                print("✅ Using default strategies for display")
        else:
            balance = 100.0  # Default for demo
            strategies = {
                'rsi_oversold': {'symbol': 'SOLUSDT', 'margin': 5.0, 'leverage': 5, 'timeframe': '15m'},
                'macd_divergence': {'symbol': 'ETHUSDT', 'margin': 10.0, 'leverage': 5, 'timeframe': '15m'}
            }

        # Get active positions from bot manager
        active_positions = []

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

def get_current_bot_manager():
    """Get the current bot manager instance"""

    # Try to get from main module first (most reliable)
    try:
        main_module = sys.modules.get('__main__')
        if main_module and hasattr(main_module, 'bot_manager') and main_module.bot_manager:
            return main_module.bot_manager
    except Exception as e:
        pass

    # Fallback to global bot_manager
    global bot_manager
    if bot_manager and not isinstance(bot_manager, DummyBotManager):
        return bot_manager

    # Last resort - return dummy
    return DummyBotManager()

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint to verify API is working"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'message': 'Web dashboard API is running'
    })

@app.route('/api/bot/status', methods=['GET'])
def get_bot_status():
    """Get current bot status"""
    try:
        current_bot = get_current_bot_manager()

        if current_bot and hasattr(current_bot, 'get_bot_status') and not isinstance(current_bot, DummyBotManager):
            bot_status = current_bot.get_bot_status()
            return jsonify(bot_status)
        else:
            return jsonify({
                'is_running': False,
                'active_positions': 0,
                'strategies': [],
                'balance': 0.0,
                'status': 'dummy'
            })
    except Exception as e:
        print(f"❌ API ERROR: /api/bot/status - {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/strategies', methods=['GET'])
def get_strategies():
    """Get all strategy configurations - WEB DASHBOARD IS SINGLE SOURCE OF TRUTH"""
    try:
        # Always prioritize web dashboard configuration
        print("🌐 WEB DASHBOARD: Getting strategies as single source of truth")
        
        if IMPORTS_AVAILABLE and hasattr(trading_config_manager, 'get_all_strategies'):
            # Get all strategies from web dashboard configuration manager
            strategies = trading_config_manager.get_all_strategies()
            print(f"✅ Got {len(strategies)} strategies from web dashboard config manager")
        else:
            # Use dummy manager if real one not available
            dummy_manager = DummyConfigManagerFull()
            strategies = dummy_manager.get_all_strategies()
            print(f"⚠️ Using dummy config manager with {len(strategies)} default strategies")

        # Ensure all required parameters are present for each strategy
        for name, config in strategies.items():
                # Ensure assessment_interval is included
                if 'assessment_interval' not in config:
                    config['assessment_interval'] = 60 if 'rsi' in name.lower() else 30

                # Ensure all required parameters exist with defaults
                if 'max_loss_pct' not in config:
                    config['max_loss_pct'] = 10

                # RSI strategy defaults
                if 'rsi' in name.lower():
                    config.setdefault('rsi_long_entry', 40)
                    config.setdefault('rsi_long_exit', 70)
                    config.setdefault('rsi_short_entry', 60)
                    config.setdefault('rsi_short_exit', 30)
                    # Set default decimals based on symbol
                    if not config.get('decimals'):
                        symbol = config.get('symbol', '').upper()
                        if 'ETH' in symbol or 'SOL' in symbol:
                            config.setdefault('decimals', 2)
                        elif 'BTC' in symbol:
                            config.setdefault('decimals', 3)
                        else:
                            config.setdefault('decimals', 2)

                # Show and populate MACD parameters if it's a MACD strategy
                elif 'macd' in name.lower():
                    config.setdefault('macd_fast', 12)
                    config.setdefault('macd_slow', 26)
                    config.setdefault('macd_signal', 9)
                    config.setdefault('min_histogram_threshold', 0.0001)
                    config.setdefault('min_distance_threshold', 0.005)
                    config.setdefault('confirmation_candles', 2)
                    # Set default decimals based on symbol
                    if not config.get('decimals'):
                        symbol = config.get('symbol', '').upper()
                        if 'ETH' in symbol or 'SOL' in symbol:
                            config.setdefault('decimals', 2)
                        elif 'BTC' in symbol:
                            config.setdefault('decimals', 3)
                        else:
                            config.setdefault('decimals', 2)
                    config.setdefault('confirmation_candles', 2)

                # Liquidity Reversal strategy defaults
                elif 'liquidity' in name.lower():
                    # Core detection parameters
                    config.setdefault('swing_lookback', 20)
                    config.setdefault('sweep_threshold', 0.5)
                    config.setdefault('volume_surge_multiplier', 2.0)
                    config.setdefault('confirmation_candles', 2)

                    # Profit targeting parameters
                    config.setdefault('profit_target_method', 'mean_reversion')
                    config.setdefault('fixed_profit_percent', 2.0)
                    config.setdefault('mean_reversion_periods', 50)
                    config.setdefault('mean_reversion_buffer', 0.5)

                    # RSI-based exit parameters
                    config.setdefault('rsi_exit_overbought', 70)
                    config.setdefault('rsi_exit_oversold', 30)

                    # Dynamic profit parameters
                    config.setdefault('dynamic_profit_min', 1.0)
                    config.setdefault('dynamic_profit_max', 4.0)

                    # Set default decimals based on symbol
                    if not config.get('decimals'):
                        symbol = config.get('symbol', '').upper()
                        if 'ETH' in symbol or 'SOL' in symbol:
                            config.setdefault('decimals', 2)
                        elif 'BTC' in symbol:
                            config.setdefault('decimals', 3)
                        else:
                            config.setdefault('decimals', 3)

            logger.info(f"🌐 WEB DASHBOARD: Serving configurations for {len(strategies)} strategies")
        
        return jsonify(strategies)
        
    except Exception as e:
        logger.error(f"Error in get_strategies endpoint: {e}")
        return jsonify({'error': str(e), 'strategies': {}}), 500

@app.route('/api/strategies', methods=['POST'])
def create_strategy():
    """Create a new strategy"""
    try:
        data = request.get_json()

        if not data or 'name' not in data:
            return jsonify({'success': False, 'message': 'Strategy name is required'})

        strategy_name = data['name']

        # Validate strategy name
        if not strategy_name.lower().strip():
            return jsonify({'success': False, 'message': 'Strategy name cannot be empty'})

        # Check if strategy already exists
        existing_strategies = trading_config_manager.get_all_strategies()
        if strategy_name in existing_strategies:
            return jsonify({'success': False, 'message': f'Strategy {strategy_name} already exists'})

        # Validate strategy type
        if 'rsi' not in strategy_name.lower() and 'macd' not in strategy_name.lower():
            return jsonify({'success': False, 'message': 'Strategy name must contain "rsi" or "macd"'})

        # Create strategy configuration
        new_config = {
            'symbol': data.get('symbol', 'BTCUSDT'),
            'margin': float(data.get('margin', 50.0)),
            'leverage': int(data.get('leverage', 5)),
            'timeframe': data.get('timeframe', '15m'),
            'max_loss_pct': float(data.get('max_loss_pct', 10.0)),
            'assessment_interval': int(data.get('assessment_interval', 60)),
            'cooldown_period': int(data.get('cooldown_period', 300))
        }

        # Add strategy-specific parameters
        if 'rsi' in strategy_name.lower():
            new_config.update({
                'rsi_long_entry': int(data.get('rsi_long_entry', 40)),
                'rsi_long_exit': int(data.get('rsi_long_exit', 70)),
                'rsi_short_entry': int(data.get('rsi_short_entry', 60)),
                'rsi_short_exit': int(data.get('rsi_short_exit', 30))
            })
        elif 'macd' in strategy_name.lower():
            new_config.update({
                'macd_fast': int(data.get('macd_fast', 12)),
                'macd_slow': int(data.get('macd_slow', 26)),
                'macd_signal': int(data.get('macd_signal', 9)),
                'min_histogram_threshold': float(data.get('min_histogram_threshold', 0.0001)),
                'min_distance_threshold': float(data.get('min_distance_threshold', 0.005)),
                'confirmation_candles': int(data.get('confirmation_candles', 2))
            })

        # Save the new strategy
        trading_config_manager.update_strategy_params(strategy_name, new_config)

        logger.info(f"🆕 NEW STRATEGY CREATED: {strategy_name} via web dashboard")

        return jsonify({
            'success': True, 
            'message': f'Strategy {strategy_name} created successfully',
            'strategy': new_config
        })

    except Exception as e:
        logger.error(f"Error creating strategy: {e}")
        return jsonify({'success': False, 'message': f'Failed to create strategy: {e}'})

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

            if 'assessment_interval' in data:
                data['assessment_interval'] = int(data['assessment_interval'])
                if data['assessment_interval'] < 5 or data['assessment_interval'] > 300:
                    return jsonify({'success': False, 'message': 'Assessment interval must be between 5 and 300 seconds'})

            if 'cooldown_period' in data:
                data['cooldown_period'] = int(data['cooldown_period'])
                if data['cooldown_period'] < 30 or data['cooldown_period'] > 3600:
                    return jsonify({'success': False, 'message': 'Cooldown period must be between 30 and 3600 seconds'})

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

        # WEB DASHBOARD IS SINGLE SOURCE OF TRUTH - Update all parameters
        trading_config_manager.update_strategy_params(strategy_name, data)

        logger.info(f"🎯 WEB DASHBOARD: Setting as SINGLE SOURCE OF TRUTH for {strategy_name}")
        logger.info(f"🔄 UPDATING ALL PARAMETERS: {data}")
        logger.info(f"📁 CONFIG FILES IGNORED - Web dashboard overrides everything")

        # Always try to get the latest shared bot manager
        shared_bot_manager = getattr(sys.modules.get('__main__', None), 'bot_manager', None)

        # FORCE IMMEDIATE UPDATE to running bot configuration (WEB DASHBOARD PRIORITY)
        bot_updated = False

        # Check shared bot manager first - FORCE WEB DASHBOARD SETTINGS
        if shared_bot_manager and hasattr(shared_bot_manager, 'strategies') and strategy_name in shared_bot_manager.strategies:
            # COMPLETE OVERRIDE - Web dashboard is single source of truth
            shared_bot_manager.strategies[strategy_name].update(data)
            logger.info(f"🌐 WEB DASHBOARD OVERRIDE: {strategy_name} config FORCED in shared bot: {data}")
            logger.info(f"🎯 WEB DASHBOARD IS SINGLE SOURCE OF TRUTH - File configs ignored")
            bot_updated = True

        # Fallback to standalone bot - FORCE WEB DASHBOARD SETTINGS
        elif bot_manager and hasattr(bot_manager, 'strategies') and strategy_name in bot_manager.strategies:
            # COMPLETE OVERRIDE - Web dashboard is single source of truth
            bot_manager.strategies[strategy_name].update(data)
            logger.info(f"🌐 WEB DASHBOARD OVERRIDE: {strategy_name} config FORCED in standalone bot: {data}")
            logger.info(f"🎯 WEB DASHBOARD IS SINGLE SOURCE OF TRUTH - File configs ignored")
            bot_updated = True

        message = f'🌐 WEB DASHBOARD: {strategy_name} updated successfully'
        if bot_updated:
            message += ' (LIVE UPDATE - Web dashboard is single source of truth)'
        else:
            message += ' (Will apply on restart - Web dashboard overrides all files)'

        # Log final confirmation
        logger.info(f"✅ WEB DASHBOARD UPDATE COMPLETE | {strategy_name}")
        logger.info(f"🎯 YOUR RSI SHORT ENTRY: {data.get('rsi_short_entry', 'Not set')} (overrides file configs)")

        return jsonify({'success': True, 'message': message})
    except Exception as e:
        logger.error(f"Error updating strategy {strategy_name}: {e}")
        return jsonify({'success': False, 'message': f'Failed to update strategy: {e}'})

@app.route('/api/balance', methods=['GET'])
def get_balance():
    """Get current balance via API"""
    try:
        current_bot = get_current_bot_manager()
        if current_bot and hasattr(current_bot, 'balance_fetcher'):
            balance = current_bot.balance_fetcher.get_usdt_balance() or 0
            return jsonify({'balance': balance})
        elif balance_fetcher:
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
                if IMPORTS_AVAILABLE and 'price_fetcher' in globals():
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
        for filename in sorted(os.listdir(trades_dir), reverse=True)[:10]:
            if filename.endswith(".json"):
                filepath = os.path.join(trades_dir, filename)
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
                {'timestamp': '14:20:39', 'message': '🌐 Web dashboard active - Bot can be started via Start Bot button'},
                {'timestamp': '14:20:39', 'message': '📊 Ready for trading operations'},
                {'timestamp': '14:20:39', 'message': '💡 Use the web interface to control the bot'}
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

        if current_bot and not isinstance(current_bot, DummyBotManager):
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
        current_price = price_fetcher.get_current_price(symbol)
        return current_price
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

# Route debugging function
def log_routes():
    """Log all registered routes for debugging"""
    print("🔍 FLASK ROUTES REGISTERED:")
    for rule in app.url_map.iter_rules():
        methods = ', '.join(sorted(rule.methods - {'OPTIONS', 'HEAD'}))
        print(f"  {rule.rule} -> {rule.endpoint} ({methods})")

# Route verification function (will be called in main block)
def verify_routes():
    """Verify all routes are properly registered"""
    logger.info("🔍 ROUTE VERIFICATION:")
    critical_routes = ['/api/health', '/api/bot/status', '/api/balance', '/api/console/log']
    for route in app.url_map.iter_rules():
        status = "✅ FOUND" if route in critical_routes else "❌ MISSING"
        logger.info(f"  {route}: {status}")
    logger.info("🔍 Route verification complete")

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

# Ensure all routes are registered before any blocking checks
print("Flask app routes:")
for rule in app.url_map.iter_rules():
    methods = ', '.join(sorted(rule.methods - {'OPTIONS', 'HEAD'}))
    print(f"  {rule.rule} -> {rule.endpoint}")
print("RSI endpoint check complete")

if __name__ == '__main__':
    # This block should never execute in production
    # Web dashboard should ONLY be launched from main.py
    logger.warning("🚫 DIRECT WEB_DASHBOARD.PY LAUNCH BLOCKED")
    logger.warning("🔄 Web dashboard should only be started from main.py")
    logger.warning("💡 Run 'python main.py' instead")
    print("❌ Direct execution of web_dashboard.py is disabled")
    print("🔄 Please run 'python main.py' to start the bot with web dashboard")