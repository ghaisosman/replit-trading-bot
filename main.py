import asyncio
import logging
import os
import signal
import sys
import threading
import time
from src.bot_manager import BotManager
from src.utils.logger import setup_logger

# Global bot manager
bot_manager = None
shutdown_event = asyncio.Event()

def signal_handler(signum, frame):
    """Handle termination signals"""
    print(f"\n🛑 Shutdown signal received: {signum}")
    shutdown_event.set()

def run_web_dashboard():
    """Run web dashboard in separate thread"""
    try:
        # Import here to avoid circular imports
        from web_dashboard import app

        # Get port from environment
        port = int(os.environ.get('PORT', 5000))

        # Run Flask app
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Web dashboard error: {e}")

async def main():
    """Main bot function"""
    global bot_manager

    # Setup logging
    setup_logger()
    logger = logging.getLogger(__name__)

    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Check if running in deployment
    is_deployment = os.environ.get('REPLIT_DEPLOYMENT') == '1'

    if is_deployment:
        logger.info("🚀 DEPLOYMENT MODE: Starting web dashboard only")

        # Start web dashboard in main thread for deployment
        web_thread = threading.Thread(target=run_web_dashboard, daemon=False)
        web_thread.start()

        # Keep deployment running
        try:
            while True:
                await asyncio.sleep(10)
        except KeyboardInterrupt:
            logger.info("🔴 Deployment shutdown")

    else:
        logger.info("🛠️ DEVELOPMENT MODE: Starting bot + web dashboard")

        # Start web dashboard in background thread
        web_thread = threading.Thread(target=run_web_dashboard, daemon=True)
        web_thread.start()

        # Give web dashboard time to start
        await asyncio.sleep(2)

        try:
            # Initialize bot manager
            bot_manager = BotManager()

            # Make bot manager available to web dashboard
            sys.modules['__main__'].bot_manager = bot_manager

            # Start bot
            logger.info("🚀 Starting trading bot...")
            bot_task = asyncio.create_task(bot_manager.start())
            shutdown_task = asyncio.create_task(shutdown_event.wait())

            done, pending = await asyncio.wait(
                [bot_task, shutdown_task],
                return_when=asyncio.FIRST_COMPLETED
            )

            if shutdown_task in done:
                logger.info("🛑 Shutdown signal received, stopping bot...")
                await bot_manager.stop("Manual shutdown")

            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        except KeyboardInterrupt:
            logger.info("🔴 Keyboard interrupt received")
            if bot_manager:
                await bot_manager.stop("Keyboard interrupt")
        except Exception as e:
            logger.error(f"Bot error: {e}")
            if bot_manager:
                await bot_manager.stop(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())