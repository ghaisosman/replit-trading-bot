
import asyncio
import logging
import signal
import sys
from src.bot_manager import BotManager
from src.utils.logger import setup_logger

# Global bot manager for signal handling
bot_manager = None

async def shutdown_handler():
    """Handle graceful shutdown"""
    global bot_manager
    if bot_manager:
        await bot_manager.stop("Manual shutdown via Ctrl+C or SIGTERM")

def signal_handler(signum, frame):
    """Handle termination signals"""
    print("\n🛑 Shutdown signal received...")
    asyncio.create_task(shutdown_handler())
    sys.exit(0)

async def main():
    global bot_manager
    
    # Setup logging
    setup_logger()
    logger = logging.getLogger(__name__)
    
    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("Starting Multi-Strategy Trading Bot")
    
    try:
        # Initialize and start the bot
        bot_manager = BotManager()
        await bot_manager.start()
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
    asyncio.run(main())
