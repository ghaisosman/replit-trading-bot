print(">>> main.py is running")

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
    """Run web dashboard with enhanced stability"""
    try:
        # Import here to avoid circular imports
        from web_dashboard import app
        
        # Configure Flask for maximum stability
        app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max request
        app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 300  # 5 minutes cache
        app.config['PERMANENT_SESSION_LIFETIME'] = 1800  # 30 minutes
        
        # Get port from environment
        port = int(os.environ.get('PORT', 5000))

        # Run Flask app with enhanced settings for stability
        app.run(
            host='0.0.0.0', 
            port=port, 
            debug=False, 
            use_reloader=False, 
            threaded=True,
            processes=1,  # Single process to prevent conflicts
            request_handler=None  # Use default handler
        )

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Web dashboard error: {e}")
        
        # Try to restart after a delay if the web dashboard crashes
        import time
        time.sleep(5)
        logger.info("Attempting to restart web dashboard after crash...")
        try:
            run_web_dashboard()  # Recursive restart attempt
        except Exception as restart_error:
            logger.error(f"Web dashboard restart failed: {restart_error}")

async def main():
    print(">>> ENTERED main()")
    # Setup logging
    print(">>> BEFORE setup_logger()")
    setup_logger()
    print(">>> AFTER setup_logger()")
    """Main bot function"""
    global bot_manager

    # Setup logging
    setup_logger()
    logger = logging.getLogger(__name__)

    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Check if running on Render (or any deployment)
    is_deployment = os.environ.get('RENDER') == 'true' or os.environ.get('REPLIT_DEPLOYMENT') == '1'

    if is_deployment:
        logger.info("🚀 RENDER DEPLOYMENT MODE: Starting web dashboard + bot with independent control")

        # Start web dashboard in background thread (always running)
        web_thread = threading.Thread(target=run_web_dashboard, daemon=False)  # Changed to non-daemon
        web_thread.start()

        # Give web dashboard time to start
        await asyncio.sleep(2)

        # Initialize bot manager but don't start it automatically
        bot_manager = BotManager()

        # Make bot manager available to web dashboard
        sys.modules['__main__'].bot_manager = bot_manager
        globals()['bot_manager'] = bot_manager

        logger.info("🌐 RENDER DEPLOYMENT: Web dashboard active - Bot can be controlled via web interface")
        logger.info("🎯 RENDER DEPLOYMENT: Access your dashboard to start/stop the bot")

        # Keep the process alive indefinitely - web dashboard controls everything
        try:
            restart_attempts = 0
            max_restart_attempts = 5  # Increased attempts
            syntax_error_detected = False
            
            while True:
                # Check if web thread is still alive
                if not web_thread.is_alive():
                    restart_attempts += 1
                    
                    logger.error(f"🔍 DEBUG: Web thread status - Alive: {web_thread.is_alive()}")
                    logger.error(f"🔍 DEBUG: Restart attempt {restart_attempts}/{max_restart_attempts}")
                    
                    if restart_attempts <= max_restart_attempts and not syntax_error_detected:
                        logger.error(f"🚨 Web dashboard thread died! Restarting... (Attempt {restart_attempts}/{max_restart_attempts})")
                        
                        # Check if it's a syntax error by looking at recent logs
                        # (This is a simple heuristic - in production you'd want more sophisticated error detection)
                        
                        # Wait a bit before restarting to avoid rapid restart loops
                        wait_time = min(10, 2 * restart_attempts)  # Progressive backoff
                        logger.info(f"🔍 DEBUG: Waiting {wait_time}s before restart attempt...")
                        await asyncio.sleep(wait_time)
                        
                        logger.info(f"🔍 DEBUG: Creating new web dashboard thread...")
                        web_thread = threading.Thread(target=run_web_dashboard, daemon=False)
                        web_thread.start()
                        
                        # Give it more time to start
                        startup_wait = 5
                        logger.info(f"🔍 DEBUG: Waiting {startup_wait}s for web dashboard startup...")
                        await asyncio.sleep(startup_wait)
                        
                        # Check if the new thread is alive
                        if web_thread.is_alive():
                            logger.info("✅ Web dashboard restart successful")
                        else:
                            logger.error("❌ Web dashboard restart failed immediately")
                            
                    else:
                        if syntax_error_detected:
                            logger.error(f"🚫 Syntax error detected - stopping restart attempts.")
                            logger.error("💡 Fix the syntax error in web_dashboard.py and restart manually.")
                        else:
                            logger.error(f"🚫 Web dashboard failed {max_restart_attempts} times. Stopping restart attempts.")
                            logger.error("💡 Check the error logs above and fix the underlying issue.")
                        break
                else:
                    # Reset restart counter if web dashboard is running fine
                    if restart_attempts > 0:
                        logger.info(f"✅ Web dashboard recovered after {restart_attempts} restart attempts")
                    restart_attempts = 0
                
                # Check every 10 seconds
                await asyncio.sleep(10)
                
        except KeyboardInterrupt:
            logger.info("🔴 Render deployment shutdown")
            if bot_manager and bot_manager.is_running:
                await bot_manager.stop("Deployment shutdown")

    else:
        logger.info("🛠️ DEVELOPMENT MODE: Starting web dashboard only")

        # Start web dashboard in background thread (NON-DAEMON for persistence)
        web_thread = threading.Thread(target=run_web_dashboard, daemon=False)
        web_thread.start()

        # Give web dashboard time to start
        await asyncio.sleep(2)

        # Initialize empty bot manager reference
        bot_manager = None
        sys.modules['__main__'].bot_manager = bot_manager
        globals()['bot_manager'] = bot_manager

        logger.info("🌐 DEVELOPMENT MODE: Web dashboard active - Bot can be started via web interface")
        logger.info("🎯 DEVELOPMENT MODE: Access your dashboard to start/stop the bot")

        # Keep the process alive indefinitely - web dashboard controls everything
        try:
            while True:
                # Check if web thread is still alive
                if not web_thread.is_alive():
                    logger.error("🚨 Web dashboard thread died! Restarting...")
                    web_thread = threading.Thread(target=run_web_dashboard, daemon=False)
                    web_thread.start()
                
                # Check if bot needs to be cleaned up
                current_bot = sys.modules['__main__'].bot_manager
                if current_bot and hasattr(current_bot, 'is_running') and not current_bot.is_running:
                    # Clean up stopped bot
                    sys.modules['__main__'].bot_manager = None
                    globals()['bot_manager'] = None
                
                await asyncio.sleep(5)
                
        except KeyboardInterrupt:
            logger.info("🔴 Development mode shutdown")
            current_bot = sys.modules['__main__'].bot_manager
            if current_bot and hasattr(current_bot, 'is_running') and current_bot.is_running:
                await current_bot.stop("Development shutdown")

if __name__ == "__main__":
    asyncio.run(main())
