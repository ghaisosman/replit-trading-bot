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
        # Check if port 5000 is available before starting
        if not check_port_available(5000):
            logger.error("🚨 PORT 5000 UNAVAILABLE: Attempting to clean up...")

            # Try to kill any processes using port 5000
            try:
                # Kill Python processes that might be using port 5000
                killed_count = 0
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        if proc.info['cmdline']:
                            cmdline_str = ' '.join(proc.info['cmdline'])
                            if ('python' in proc.info['name'].lower() and 
                                ('web_dashboard' in cmdline_str or 'flask' in cmdline_str or 'main.py' in cmdline_str)):
                                if proc.pid != os.getpid():  # Don't kill ourselves
                                    proc.terminate()
                                    logger.info(f"🔄 Terminated process {proc.pid}: {proc.info['name']}")
                                    killed_count += 1
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        continue

                if killed_count > 0:
                    logger.info(f"🔄 Terminated {killed_count} processes")
                else:
                    logger.info("🔍 No conflicting processes found")

                # Wait a moment for cleanup
                time.sleep(2)

                # Check again
                if not check_port_available(5000):
                    logger.error("🚨 CRITICAL: Port 5000 still unavailable after cleanup")
                    logger.error("💡 Please restart the entire Repl to clear port conflicts")
                    return
                else:
                    logger.info("✅ Port 5000 cleared successfully")

            except Exception as cleanup_error:
                logger.error(f"Error during port cleanup: {cleanup_error}")
                return

        web_server_running = True
        logger.info("🌐 WEB DASHBOARD: Starting persistent web interface on http://0.0.0.0:5000")
        logger.info("🌐 WEB DASHBOARD: Dashboard will remain active even when bot stops")

        # Run Flask with minimal logging to reduce console noise
        import logging as flask_logging
        flask_log = flask_logging.getLogger('werkzeug')
        flask_log.setLevel(flask_logging.WARNING)

        # Set Flask app configuration for better error handling
        app.config['TESTING'] = False
        app.config['DEBUG'] = False

        # Get port from environment for deployment compatibility
        port = int(os.environ.get('PORT', 5000))
        logger.info(f"🌐 Starting web dashboard on 0.0.0.0:{port}")
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)

    except Exception as e:
        logger.error(f"Web dashboard error: {e}")
        if "Address already in use" in str(e):
            logger.error("🚨 CRITICAL: Port conflict persists")
            logger.info("💡 Please restart the Repl to resolve port conflicts")
        else:
            logger.error(f"🚨 WEB DASHBOARD ERROR: {str(e)}")
            logger.info("🌐 Attempting to restart web dashboard...")
            # Try to restart after a delay
            time.sleep(5)
            if web_server_running:
                try:
                    # Get port from environment for deployment compatibility
                    port = int(os.environ.get('PORT', 5000))
                    logger.info(f"🌐 Restarting web dashboard on 0.0.0.0:{port}")
                    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)
                except:
                    logger.error("🚨 Web dashboard restart failed")
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
        bot_manager = BotManager()

        # Make bot manager accessible to web interface
        sys.modules['__main__'].bot_manager = bot_manager
        web_dashboard.bot_manager = bot_manager
        web_dashboard.shared_bot_manager = bot_manager

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

    # Start web dashboard in background thread - this will keep running
    web_thread = threading.Thread(target=run_web_dashboard, daemon=False)
    web_thread.start()

    # Give web dashboard time to start
    await asyncio.sleep(3)
    logger.info("🌐 Web Dashboard accessible and will remain active")

    try:
        # Initialize the bot manager
        bot_manager = BotManager()

        # Make bot manager accessible to web interface
        sys.modules['__main__'].bot_manager = bot_manager
        web_dashboard.bot_manager = bot_manager
        web_dashboard.shared_bot_manager = bot_manager

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

    # Check if running in deployment
    is_deployment = os.environ.get('REPLIT_DEPLOYMENT') == '1'

    if is_deployment:
        logger.info("🚀 STARTING IN REPLIT DEPLOYMENT MODE")

        # In deployment, run simplified version
        bot_manager = None
        sys.modules[__name__].bot_manager = None

        # Start web dashboard in background
        web_thread = threading.Thread(target=run_web_dashboard, daemon=False)
        web_thread.start()

        # Wait for web dashboard and keep alive
        time.sleep(2)
        logger.info("🌐 Deployment web dashboard active")
        logger.info("💡 Access your bot via the web interface at your deployment URL")
        logger.info("🔄 Bot can be started/stopped through the web dashboard")

        try:
            # Keep the process alive for web interface
            while True:
                time.sleep(10)
        except KeyboardInterrupt:
            logger.info("🔴 Deployment shutdown")
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

        # Start web dashboard in persistent background thread
        web_thread = threading.Thread(target=run_web_dashboard, daemon=False)
        web_thread.start()

        time.sleep(3)
        logger.info("🌐 Development Web Dashboard started")

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