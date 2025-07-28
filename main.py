#!/usr/bin/env python3
"""
Trading Bot Main Entry Point
Fixed version with proper error handling and simplified logic
"""

import asyncio
import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime

# Setup logging first
from src.utils.logger import setup_logger

# Global bot manager
bot_manager = None
shutdown_event = asyncio.Event()

def signal_handler(signum, frame):
    """Handle termination signals"""
    print(f"\n🛑 Shutdown signal received: {signum}")
    shutdown_event.set()

def run_web_dashboard():
    """Run web dashboard in separate thread with port conflict resolution"""
    try:
        # Import here to avoid circular imports
        from web_dashboard import app

        # Get port from environment, with fallback ports
        primary_port = int(os.environ.get('PORT', 5000))
        fallback_ports = [5000, 5001, 5002, 5003, 8000, 8080, 3000, 4000, 6000, 7000, 9000, 10000]

        # Ensure primary port is in fallback list
        if primary_port not in fallback_ports:
            fallback_ports.insert(0, primary_port)

        logger = logging.getLogger(__name__)

        import socket

        for port in fallback_ports:
            try:
                # Test if port is available before trying to bind
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex(('localhost', port))
                sock.close()

                if result == 0:
                    logger.warning(f"⚠️ Port {port} is already in use, trying next port...")
                    continue

                logger.info(f"🌐 Starting web dashboard on port {port}")
                app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)
                break
            except Exception as e:
                logger.warning(f"⚠️ Port {port} failed: {e}, trying next port...")
                continue
        else:
            # If all ports fail, try a random port
            import random
            random_port = random.randint(10000, 65535)
            logger.info(f"🌐 Trying random port {random_port}")
            try:
                app.run(host='0.0.0.0', port=random_port, debug=False, use_reloader=False, threaded=True)
            except Exception as e:
                logger.error(f"❌ Could not start web dashboard on any port: {e}")

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Web dashboard error: {e}")

async def main():
    """Main bot function with improved error handling"""
    global bot_manager

    # Setup logging
    setup_logger()
    logger = logging.getLogger(__name__)

    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Check if running on deployment platform
    is_deployment = os.environ.get('RENDER') == 'true' or os.environ.get('REPLIT_DEPLOYMENT') == '1'

    if is_deployment:
        logger.info("🚀 DEPLOYMENT MODE: Starting web dashboard + bot with independent control")

        # Start web dashboard in background thread
        web_thread = threading.Thread(target=run_web_dashboard, daemon=False)
        web_thread.start()

        # Give web dashboard time to start
        await asyncio.sleep(2)

        # Initialize bot manager but don't start it automatically
        try:
            from src.bot_manager import BotManager
            bot_manager = BotManager()
            
            # Make bot manager available to web dashboard
            sys.modules['__main__'].bot_manager = bot_manager
            globals()['bot_manager'] = bot_manager

            logger.info("🌐 DEPLOYMENT: Web dashboard active - Bot can be controlled via web interface")
            logger.info("🎯 DEPLOYMENT: Access your dashboard to start/stop the bot")

        except Exception as e:
            logger.error(f"❌ Failed to initialize bot manager: {e}")
            bot_manager = None

        # Keep the process alive indefinitely - web dashboard controls everything
        try:
            restart_attempts = 0
            max_restart_attempts = 5

            while True:
                # Check if web thread is still alive
                if not web_thread.is_alive():
                    restart_attempts += 1

                    if restart_attempts <= max_restart_attempts:
                        logger.error(f"🚨 Web dashboard thread died! Restarting... (Attempt {restart_attempts}/{max_restart_attempts})")

                        # Wait before restarting to avoid rapid restart loops
                        wait_time = min(10, 2 * restart_attempts)
                        await asyncio.sleep(wait_time)

                        web_thread = threading.Thread(target=run_web_dashboard, daemon=False)
                        web_thread.start()

                        # Give it time to start
                        await asyncio.sleep(5)

                        if web_thread.is_alive():
                            logger.info("✅ Web dashboard restart successful")
                        else:
                            logger.error("❌ Web dashboard restart failed immediately")
                    else:
                        logger.error(f"🚫 Web dashboard failed {max_restart_attempts} times. Stopping restart attempts.")
                        break
                else:
                    # Reset restart counter if web dashboard is running fine
                    if restart_attempts > 0:
                        logger.info(f"✅ Web dashboard recovered after {restart_attempts} restart attempts")
                    restart_attempts = 0

                # Check every 10 seconds
                await asyncio.sleep(10)

        except KeyboardInterrupt:
            logger.info("🔴 Deployment shutdown")
            if bot_manager and hasattr(bot_manager, 'is_running') and bot_manager.is_running:
                await bot_manager.stop("Deployment shutdown")

    else:
        logger.info("🛠️ DEVELOPMENT MODE: Starting web dashboard only")

        # Start web dashboard in background thread
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