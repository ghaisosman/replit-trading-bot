import asyncio
import logging
import signal
import sys
import threading
import time
from src.bot_manager import BotManager
from src.utils.logger import setup_logger
from web_dashboard import app

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

def run_web_dashboard():
    """Run web dashboard in separate thread - keeps running even if bot stops"""
    global web_server_running
    logger = logging.getLogger(__name__)

    try:
        web_server_running = True
        logger.info("🌐 WEB DASHBOARD: Starting persistent web interface on http://0.0.0.0:5000")
        logger.info("🌐 WEB DASHBOARD: Dashboard will remain active even when bot stops")

        # Run Flask with minimal logging to reduce console noise
        import logging as flask_logging
        flask_log = flask_logging.getLogger('werkzeug')
        flask_log.setLevel(flask_logging.WARNING)

        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False, threaded=True)
    except Exception as e:
        logger.error(f"Web dashboard error: {e}")
    finally:
        web_server_running = False

async def main():
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
    import threading
    import time

    # Start the web dashboard in a separate thread
    def start_web_dashboard():
        time.sleep(2)  # Give the main bot time to initialize
        import subprocess
        subprocess.run(["python", "web_dashboard.py"])

    # Start web dashboard thread
    web_thread = threading.Thread(target=start_web_dashboard, daemon=True)
    web_thread.start()

    # Start the main trading bot
    asyncio.run(main())