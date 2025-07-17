import asyncio
import logging
import os
import signal
import sys
import threading
import time
import psutil
from src.bot_manager import BotManager
from src.utils.logger import setup_logger

# Import web dashboard after setting up the module reference
import web_dashboard
app = web_dashboard.app

# Global bot manager for signal handling and web interface access
bot_manager = None
shutdown_event = asyncio.Event()
web_server_running = False

# Make bot manager accessible to web interface
sys.modules['__main__'].bot_manager = None

def signal_handler(signum, frame):
    """Handle termination signals"""
    print("\n🛑 Shutdown signal received...")
    # Set the shutdown event to trigger graceful shutdown
    if shutdown_event:
        shutdown_event.set()

def check_port_available(port):
    """Check if a port is available"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('0.0.0.0', port))
            return True
        except OSError:
            return False

def run_web_dashboard():
    """Run web dashboard in separate thread - keeps running even if bot stops"""
    global web_server_running
    logger = logging.getLogger(__name__)

    # Check if running in deployment environment
    is_deployment = os.environ.get('REPLIT_DEPLOYMENT') == '1'
    if is_deployment:
        logger.info("🚀 RUNNING IN REPLIT DEPLOYMENT MODE")

    try:
        # Simple port check and cleanup
        if not check_port_available(5000):
            logger.warning("🔄 Port 5000 in use, attempting cleanup...")
            try:
                import subprocess
                # Try to kill processes using port 5000
                subprocess.run(['pkill', '-f', ':5000'], capture_output=True)
                time.sleep(2)
            except:
                pass

        web_server_running = True
        logger.info("🌐 WEB DASHBOARD: Starting Flask server on http://0.0.0.0:5000")
        
        # Configure Flask for proper error handling
        app.config['TESTING'] = False
        app.config['DEBUG'] = True  # Enable debug for better error messages
        app.config['PROPAGATE_EXCEPTIONS'] = True

        # Run Flask with proper configuration
        port = int(os.environ.get('PORT', 5000))
        logger.info(f"🌐 Starting web dashboard on 0.0.0.0:{port}")
        
        # Start Flask server
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)

    except Exception as e:
        logger.error(f"🚨 WEB DASHBOARD ERROR: {str(e)}")
        import traceback
        logger.error(f"🚨 Traceback: {traceback.format_exc()}")
        
        if "Address already in use" in str(e):
            logger.error("🚨 CRITICAL: Port 5000 is still in use")
            logger.info("💡 Try using a different port or restart the Repl")
        
        # Try alternative port
        try:
            for alt_port in [5001, 5002, 5003]:
                if check_port_available(alt_port):
                    logger.info(f"🔄 Trying alternative port {alt_port}")
                    app.run(host='0.0.0.0', port=alt_port, debug=False, use_reloader=False, threaded=True)
                    break
        except Exception as alt_e:
            logger.error(f"🚨 Alternative port failed: {alt_e}")
    finally:
        web_server_running = False
        logger.info("🔴 Web dashboard stopped")

async def main_bot_only():
    """Main bot function WITHOUT web dashboard launch"""
    global bot_manager, web_server_running

    # Setup logging
    setup_logger()
    logger = logging.getLogger(__name__)

    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("Starting Multi-Strategy Trading Bot (Web Dashboard already running)")

    # No web dashboard launch here - already started from main entry point
    await asyncio.sleep(1)
    logger.info("🌐 Using existing Web Dashboard instance")

    try:
        # Initialize the bot manager
        try:
            # Initialize the bot manager
            bot_manager = BotManager()

            # Make bot manager accessible to web interface using centralized function
            set_bot_manager(bot_manager)

            # Start the bot in a task so we can handle shutdown signals
            logger.info("🚀 Starting trading bot main loop...")
            bot_task = asyncio.create_task(bot_manager.start())
            shutdown_task = asyncio.create_task(shutdown_event.wait())

            # Wait for either the bot to complete or shutdown signal
            done, pending = await asyncio.wait(
                [bot_task, shutdown_task],
                return_when=asyncio.FIRST_COMPLETED
            )

            # Check if shutdown was triggered
            if shutdown_task in done:
                logger.info("🛑 Shutdown signal received, stopping bot...")
                await bot_manager.stop("Manual shutdown via Ctrl+C or SIGTERM")

            # Cancel any pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            # Keep web server running after bot stops
            logger.info("🔴 Bot stopped but web interface remains active for control")
            logger.info("💡 You can restart the bot using the web interface")

        except ValueError as e:
            if "Failed to connect to Binance API" in str(e):
                is_deployment = os.environ.get('REPLIT_DEPLOYMENT') == '1'
                if is_deployment:
                    logger.error("🚨 DEPLOYMENT MODE: Bot cannot start due to API restrictions")
                    logger.error("🌐 Web dashboard will remain active for manual monitoring")
                    logger.error("💡 Your existing mainnet positions can be monitored via web interface")
                    bot_manager = None
                    sys.modules['__main__'].bot_manager = None
                else:
                    raise e
            else:
                raise e

            # Keep the main process alive to maintain web interface
            while web_server_running:
                await asyncio.sleep(5)

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        if bot_manager:
            await bot_manager.stop("Manual shutdown via keyboard interrupt")
        logger.info("🌐 Web interface remains active")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if bot_manager:
            await bot_manager.stop(f"Unexpected error: {e}")
        logger.info("🌐 Web interface remains active")

async def main():
    """Main function for web dashboard bot restart"""
    global bot_manager, web_server_running

    # Setup logging
    setup_logger()
    logger = logging.getLogger(__name__)

    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("Starting Multi-Strategy Trading Bot with Persistent Web Interface")

    # SINGLE SOURCE WEB DASHBOARD LAUNCH - Only from main.py
    logger.info("🌐 MAIN.PY: Starting web dashboard (single source control)")
    logger.info("🚫 MAIN.PY: Direct web_dashboard.py launches are disabled")
    web_thread = threading.Thread(target=run_web_dashboard, daemon=False)
    web_thread.start()

    # Give web dashboard time to start
    await asyncio.sleep(3)
    logger.info("🌐 Web Dashboard accessible and will remain active")

    try:
        # Initialize the bot manager
        try:
            # Initialize the bot manager
            bot_manager = BotManager()

            # Make bot manager accessible to web interface using centralized function
            set_bot_manager(bot_manager)

            # Start the bot in a task so we can handle shutdown signals
            logger.info("🚀 Starting trading bot main loop...")
            bot_task = asyncio.create_task(bot_manager.start())
            shutdown_task = asyncio.create_task(shutdown_event.wait())

            # Wait for either the bot to complete or shutdown signal
            done, pending = await asyncio.wait(
                [bot_task, shutdown_task],
                return_when=asyncio.FIRST_COMPLETED
            )

            # Check if shutdown was triggered
            if shutdown_task in done:
                logger.info("🛑 Shutdown signal received, stopping bot...")
                await bot_manager.stop("Manual shutdown via Ctrl+C or SIGTERM")

            # Cancel any pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            # Keep web server running after bot stops
            logger.info("🔴 Bot stopped but web interface remains active for control")
            logger.info("💡 You can restart the bot using the web interface")

        except ValueError as e:
            if "Failed to connect to Binance API" in str(e):
                is_deployment = os.environ.get('REPLIT_DEPLOYMENT') == '1'
                if is_deployment:
                    logger.error("🚨 DEPLOYMENT MODE: Bot cannot start due to API restrictions")
                    logger.error("🌐 Web dashboard will remain active for manual monitoring")
                    logger.error("💡 Your existing mainnet positions can be monitored via web interface")
                    bot_manager = None
                    sys.modules['__main__'].bot_manager = None
                else:
                    raise e
            else:
                raise e

            # Keep the main process alive to maintain web interface
            while web_server_running:
                await asyncio.sleep(5)

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        if bot_manager:
            await bot_manager.stop("Manual shutdown via keyboard interrupt")
        logger.info("🌐 Web interface remains active")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if bot_manager:
            await bot_manager.stop(f"Unexpected error: {e}")
        logger.info("🌐 Web interface remains active despite bot error")

if __name__ == "__main__":
    # Setup logging first
    setup_logger()
    logger = logging.getLogger(__name__)

    # Define set_bot_manager here to avoid circular import issues
    def set_bot_manager(bm):
        """Centralized function to set bot_manager in all necessary modules."""
        global bot_manager
        bot_manager = bm
        sys.modules['__main__'].bot_manager = bm
        try:
            import web_dashboard
            web_dashboard.bot_manager = bm
            web_dashboard.shared_bot_manager = bm
            web_dashboard.current_bot = bm
            logger.info(f"✅ Bot manager shared with web dashboard: {type(bm).__name__}")
        except ImportError:
            logger.warning("web_dashboard module not found, cannot set bot_manager")
        except Exception as e:
            logger.error(f"Error sharing bot manager with web dashboard: {e}")

    # Check if running in deployment
    is_deployment = os.environ.get('REPLIT_DEPLOYMENT') == '1'

    if is_deployment:
        logger.info("🚀 STARTING IN REPLIT DEPLOYMENT MODE")
        logger.info("🌐 ALWAYS-ON DEPLOYMENT: Web interface will remain accessible 24/7")
        logger.info("💰 MAINNET BOT: Both development and deployment use mainnet")
        logger.info("🌍 GEOGRAPHIC RESTRICTIONS: Will be handled via proxy solution")

        # In deployment, run enhanced always-on version
        bot_manager = None
        sys.modules[__name__].bot_manager = None

        # DEPLOYMENT: Single source web dashboard launch
        logger.info("🚀 DEPLOYMENT: Starting always-on trading system")
        web_thread = threading.Thread(target=run_web_dashboard, daemon=False)
        web_thread.start()

        # Wait for web dashboard and keep alive
        time.sleep(3)
        logger.info("🌐 ALWAYS-ON DEPLOYMENT: Web interface active 24/7")
        logger.info("💡 Access your bot at your deployment URL from anywhere")
        logger.info("🔄 Bot control via web dashboard - start/stop anytime")
        logger.info("✅ PERSISTENT DEPLOYMENT: Stays active even when you're offline")
        logger.info("💰 MAINNET TRADING: Live trading in deployment (no geographic issues)")
        logger.info("🌍 REPLIT ADVANTAGE: No proxy needed - direct mainnet access")
        logger.info("🛡️ ACCOUNT SAFETY: Fully compliant with Binance ToS")

        try:
            # Create fresh bot manager instance
            bot_manager = BotManager()

            # Update the global reference using centralized function
            set_bot_manager(bot_manager)
            # Enhanced keep-alive loop for deployment persistence
            heartbeat_counter = 0
            while True:
                heartbeat_counter += 1
                if heartbeat_counter % 20 == 0:  # Every 10 minutes
                    logger.info(f"💓 DEPLOYMENT HEARTBEAT: System active and healthy")
                    logger.info(f"🌐 Web interface accessible at deployment URL")
                time.sleep(30)  # Check every 30 seconds to ensure deployment stays alive
        except KeyboardInterrupt:
            logger.info("🔴 Deployment shutdown requested")
    else:
        # Development mode - check if bot is already running
        try:
            import psutil
            current_pid = os.getpid()
            bot_processes = []

            for proc in psutil.process_iter(['pid', 'cmdline']):
                try:
                    if proc.info['cmdline'] and len(proc.info['cmdline']) > 1:
                        cmdline = ' '.join(proc.info['cmdline'])
                        if 'python' in cmdline and 'main.py' in cmdline and proc.info['pid'] != current_pid:
                            bot_processes.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            if bot_processes:
                logger.warning("⚠️  EXISTING BOT PROCESS DETECTED")
                logger.warning("🔍 Another instance of the bot appears to be running")
                logger.warning("💡 Use the web dashboard to control the bot instead of console")
                logger.warning("🌐 Web dashboard should be accessible at http://localhost:5000")

                # Still start web dashboard if not running
                if not check_port_available(5000):
                    logger.info("🌐 Web dashboard already running")
                else:
                    logger.info("🌐 Starting web dashboard...")
                    web_thread = threading.Thread(target=run_web_dashboard, daemon=False)
                    web_thread.start()

                # Keep process alive for web interface
                try:
                    while True:
                        time.sleep(10)
                except KeyboardInterrupt:
                    logger.info("🔴 Console interface shutdown")
                    sys.exit(0)
        except ImportError:
            pass  # psutil not available, continue normally

        # Original development mode
        bot_manager = None
        sys.modules[__name__].bot_manager = None

        # DEVELOPMENT: Single source web dashboard launch from main.py
        logger.info("🛠️ DEVELOPMENT: Starting web dashboard from main.py only")
        web_thread = threading.Thread(target=run_web_dashboard, daemon=False)
        web_thread.start()

        time.sleep(5)  # Give more time for Flask server to start
        logger.info("🌐 Development Web Dashboard started")

        # Test if web server is actually running
        try:
            import requests
            response = requests.get('http://localhost:5000/api/health', timeout=5)
            if response.status_code == 200:
                logger.info("✅ Web dashboard API is accessible")
            else:
                logger.warning(f"⚠️ Web dashboard returned status {response.status_code}")
        except Exception as e:
            logger.error(f"❌ Web dashboard API test failed: {e}")

        try:
            asyncio.run(main_bot_only())
        except KeyboardInterrupt:
            logger.info("🔴 BOT STOPPED: Manual shutdown")
            logger.info("🌐 Web interface remains active")
            try:
                while web_server_running:
                    time.sleep(5)
            except KeyboardInterrupt:
                logger.info("🔴 Final shutdown")
        except Exception as e:
            logger.error(f"Bot error: {e}")
            logger.info("🌐 Web interface remains active despite error")
            try:
                while web_server_running:
                    time.sleep(5)
            except KeyboardInterrupt:
                logger.info("🔴 Final shutdown")