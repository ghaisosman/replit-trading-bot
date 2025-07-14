
import asyncio
import logging
import signal
import sys
from src.bot_manager import BotManager
from src.utils.logger import setup_logger

# Global bot manager for signal handling
bot_manager = None
shutdown_event = asyncio.Event()

async def shutdown_handler():
    """Handle graceful shutdown"""
    global bot_manager
    if bot_manager:
        await bot_manager.stop("Manual shutdown via Ctrl+C or SIGTERM")
    shutdown_event.set()

def signal_handler(signum, frame):
    """Handle termination signals"""
    print("\n🛑 Shutdown signal received...")
    # Create a new event loop if we're not in one
    loop = None
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    # Run the shutdown handler and wait for it to complete
    loop.run_until_complete(shutdown_handler())
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
        
        # Start the bot in a task so we can handle shutdown signals
        bot_task = asyncio.create_task(bot_manager.start())
        
        # Wait for either the bot to complete or shutdown signal
        done, pending = await asyncio.wait(
            [bot_task, asyncio.create_task(shutdown_event.wait())],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Cancel any pending tasks
        for task in pending:
            task.cancel()
            
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
