/api/balance', methods=['GET'])
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
    exit(1)  # Prevent execution