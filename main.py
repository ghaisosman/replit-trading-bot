import asyncio
import logging
import signal
import sys
import threading
from src.bot_manager import BotManager
from src.utils.logger import setup_logger
from web_dashboard import app

# Global bot manager for signal handling and web interface access
bot_manager = None
shutdown_event = asyncio.Event()

# Make bot manager accessible to web interface
import sys
sys.modules['__main__'].bot_manager = None

def signal_handler(signum, frame):
    """Handle termination signals"""
    print("\n🛑 Shutdown signal received...")
    # Set the shutdown event to trigger graceful shutdown
    if shutdown_event:
        shutdown_event.set()

async def main():
    global bot_manager

    # Setup logging
    setup_logger()
    logger = logging.getLogger(__name__)

    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("Starting Multi-Strategy Trading Bot")

    # Start web dashboard in background thread
    def run_web_dashboard():
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

    web_thread = threading.Thread(target=run_web_dashboard, daemon=True)
    web_thread.start()
    logger.info("🌐 Web Dashboard started at http://0.0.0.0:5000")

    try:
        # Initialize and start the bot
        bot_manager = BotManager()

        # Make bot manager accessible to web interface
        sys.modules['__main__'].bot_manager = bot_manager

        # Start the bot in a task so we can handle shutdown signals
        bot_task = asyncio.create_task(bot_manager.start())
        shutdown_task = asyncio.create_task(shutdown_event.wait())

        # Wait for either the bot to complete or shutdown signal
        done, pending = await asyncio.wait(
            [bot_task, shutdown_task],
            return_when=asyncio.FIRST_COMPLETED
        )

        # Check if shutdown was triggered
        if shutdown_task in done:
            logger.info("Shutdown signal received, stopping bot...")
            await bot_manager.stop("Manual shutdown via Ctrl+C or SIGTERM")

        # Cancel any pending tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        if bot_manager:
            await bot_manager.stop("Manual shutdown via keyboard interrupt")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if bot_manager:
            await bot_manager.stop(f"Unexpected error: {str(e)}")
        raise

if __name__ == "__main__":
    # Make bot_manager available to web dashboard
    bot_manager = BotManager()

    # Make it globally accessible for web interface
    import sys
    sys.modules[__name__].bot_manager = bot_manager

    try:
        # Run the bot
        asyncio.run(bot_manager.start())
    except KeyboardInterrupt:
        logger.info("🔴 BOT STOPPED: Manual shutdown via console (Ctrl+C)")
        # Send stop notification
        try:
            bot_manager.telegram_reporter.report_bot_stopped("Manual shutdown via Ctrl+C")
        except:
            pass