
import asyncio
import logging
from src.bot_manager import BotManager
from src.utils.logger import setup_logger

async def main():
    # Setup logging
    setup_logger()
    logger = logging.getLogger(__name__)
    
    logger.info("Starting Multi-Strategy Trading Bot")
    
    # Initialize and start the bot
    bot_manager = BotManager()
    await bot_manager.start()

if __name__ == "__main__":
    asyncio.run(main())
