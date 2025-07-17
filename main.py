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
web_thread = None
flask_server = None

# Make bot manager accessible to web interface
sys.modules['__main__'].bot_manager = None

def signal_handler(signum, frame):
    """Handle termination signals"""
    print("\n🛑 Shutdown signal received...")
    global web_server_running, flask_server
    
    # Set the shutdown event to trigger graceful shutdown
    if shutdown_event:
        shutdown_event.set()
    
    # Stop web server gracefully
    web_server_running = False
    
    # Force Flask server shutdown if running
    if flask_server:
        try:
            flask_server.shutdown()
        except:
            pass
    
    print("🔄 Cleanup initiated...")

def check_port_available(port):
    """Check if a port is available"""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(('0.0.0.0', port))
            return True
    except OSError as e:
        # Port is in use or other socket error
        return False
    except Exception as e:
        # Unexpected error
        return False

def run_web_dashboard():
    """Run web dashboard in separate thread - keeps running even if bot stops"""
    global web_server_running, flask_server
    logger = logging.getLogger(__name__)

    # Singleton check - prevent multiple instances
    if web_server_running:
        logger.info("🌐 Web dashboard already running - skipping duplicate start")
        return

    # Check if running in deployment environment
    is_deployment = os.environ.get('REPLIT_DEPLOYMENT') == '1'
    if is_deployment:
        logger.info("🚀 RUNNING IN REPLIT DEPLOYMENT MODE")

    try:
        # Import and run web dashboard
        from web_dashboard import app
        
        # Create process lock file to prevent conflicts
        lock_file = "/tmp/web_dashboard.lock"
        if os.path.exists(lock_file):
            try:
                with open(lock_file, 'r') as f:
                    existing_pid = int(f.read().strip())
                
                # Check if process is still running AND is actually a web dashboard
                try:
                    # First check if PID exists
                    os.kill(existing_pid, 0)
                    
                    # Then check if it's actually a web dashboard process
                    try:
                        proc = psutil.Process(existing_pid)
                        cmdline = ' '.join(proc.cmdline())
                        
                        # If it's actually a web dashboard process, prevent duplicate
                        if ('web_dashboard' in cmdline or 'flask' in cmdline.lower() or 'main.py' in cmdline):
                            logger.error(f"🚨 Another web dashboard is running (PID: {existing_pid})")
                            logger.error("🚫 MAIN.PY: Preventing duplicate instance")
                            return
                        else:
                            # PID exists but not a web dashboard, remove stale lock
                            os.remove(lock_file)
                            logger.info("🔄 Removed stale lock file (PID not web dashboard)")
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        # Process exists but can't access details, remove stale lock
                        os.remove(lock_file)
                        logger.info("🔄 Removed stale lock file (process access denied)")
                        
                except OSError:
                    # Process doesn't exist, remove stale lock file
                    os.remove(lock_file)
                    logger.info("🔄 Removed stale lock file (process doesn't exist)")
            except (ValueError, FileNotFoundError):
                # Invalid or missing lock file, remove it
                try:
                    os.remove(lock_file)
                except:
                    pass

        # Create lock file with current PID
        try:
            with open(lock_file, 'w') as f:
                f.write(str(os.getpid()))
            logger.info(f"🔒 Created web dashboard lock file (PID: {os.getpid()})")
        except Exception as e:
            logger.warning(f"Could not create lock file: {e}")

        # SINGLE SOURCE CHECK - Ensure no duplicate web dashboard instances
        if not check_port_available(5000):
            logger.error("🚨 PORT 5000 UNAVAILABLE: Another web dashboard instance detected")
            logger.error("🚫 MAIN.PY: Cleaning up duplicate instances")
            
            # Kill existing processes using port 5000 - Replit compatible method
            try:
                # Use psutil instead of lsof for Replit compatibility
                import psutil
                killed_count = 0
                
                for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'connections']):
                    try:
                        # Check if process is using port 5000
                        if proc.info['connections']:
                            for conn in proc.info['connections']:
                                if hasattr(conn, 'laddr') and conn.laddr and conn.laddr.port == 5000:
                                    if proc.pid != os.getpid():  # Don't kill ourselves
                                        proc.terminate()
                                        logger.info(f"🔄 Killed process {proc.pid} using port 5000")
                                        killed_count += 1
                                        break
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        continue
                
                if killed_count > 0:
                    logger.info(f"🔄 Terminated {killed_count} processes using port 5000")
                    # Wait for port to be freed
                    time.sleep(3)
                    
                    # Check if port is now available
                    if check_port_available(5000):
                        logger.info("✅ Port 5000 successfully freed")
                    else:
                        logger.error("❌ Port 5000 still unavailable after cleanup")
                        return
                else:
                    logger.info("🔍 No processes found using port 5000")
            except Exception as e:
                logger.error(f"Error during psutil port cleanup: {e}")
                # Fallback to simple process termination
                try:
                    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                        try:
                            if proc.info['cmdline']:
                                cmdline_str = ' '.join(proc.info['cmdline'])
                                if ('flask' in cmdline_str.lower() or 'web_dashboard' in cmdline_str.lower()):
                                    if proc.pid != os.getpid():
                                        proc.terminate()
                                        logger.info(f"🔄 Terminated Flask process {proc.pid}")
                        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                            continue
                    time.sleep(2)
                except:
                    logger.error("Fallback cleanup also failed")
                    return

        web_server_running = True
        logger.info("🌐 Starting web dashboard on 0.0.0.0:5000")
        
        # Get port from environment for deployment compatibility
        port = int(os.environ.get('PORT', 5000))
        
        # Store Flask server reference for shutdown
        from werkzeug.serving import make_server
        
        flask_server = make_server('0.0.0.0', port, app, threaded=True)
        logger.info(f"🌐 Flask server created on port {port}")
        
        # Set up signal handlers for this thread
        import signal
        def cleanup_handler(signum, frame):
            global web_server_running
            logger.info("🔄 Web dashboard cleanup signal received")
            web_server_running = False
            if flask_server:
                flask_server.shutdown()
        
        signal.signal(signal.SIGTERM, cleanup_handler)
        signal.signal(signal.SIGINT, cleanup_handler)
        
        # Start Flask server
        try:
            flask_server.serve_forever()
        except KeyboardInterrupt:
            logger.info("🔄 Web dashboard interrupted")
        finally:
            web_server_running = False

    except Exception as e:
        logger.error(f"Web dashboard error: {e}")
        if "Address already in use" in str(e):
            logger.error("🚨 PORT 5000 UNAVAILABLE: Another web dashboard instance detected")
            logger.error("🚫 MAIN.PY: Cleaning up duplicate instances...")
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
                                    # Wait for process to terminate
                                    try:
                                        proc.wait(timeout=3)
                                    except psutil.TimeoutExpired:
                                        proc.kill()  # Force kill if it doesn't terminate
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        continue

                if killed_count > 0:
                    logger.info(f"🔄 Terminated {killed_count} processes")
                    # Wait longer for cleanup to complete
                    time.sleep(5)
                else:
                    logger.info("🔍 No conflicting processes found")

                # Wait a moment for cleanup
                time.sleep(2)

                # Check again
                if not check_port_available(5000):
                    logger.error("🚨 CRITICAL: Port 5000 still unavailable after cleanup")
                    logger.error("💡 Trying alternative port cleanup method...")
                    
                    # Alternative cleanup using psutil connection check
                    try:
                        import psutil
                        for proc in psutil.process_iter(['pid', 'name', 'connections']):
                            try:
                                if proc.info['connections']:
                                    for conn in proc.info['connections']:
                                        if hasattr(conn, 'laddr') and conn.laddr and conn.laddr.port == 5000:
                                            logger.info(f"🔍 Found process {proc.pid} ({proc.info['name']}) using port 5000")
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                continue
                    except:
                        pass
                    
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
        
        # Comprehensive cleanup
        logger.info("🧹 Starting comprehensive cleanup...")
        
        # 1. Clean up Flask server
        global flask_server
        if flask_server:
            try:
                flask_server.shutdown()
                logger.info("✅ Flask server shut down")
            except Exception as e:
                logger.warning(f"Error shutting down Flask server: {e}")
            finally:
                flask_server = None
        
        # 2. Clean up lock file with enhanced verification
        lock_file = "/tmp/web_dashboard.lock"
        try:
            if os.path.exists(lock_file):
                # Verify it's our lock file before removing
                with open(lock_file, 'r') as f:
                    lock_pid = int(f.read().strip())
                
                current_pid = os.getpid()
                if lock_pid == current_pid:
                    os.remove(lock_file)
                    logger.info("🔓 Removed web dashboard lock file")
                else:
                    # Check if the lock PID still exists
                    try:
                        os.kill(lock_pid, 0)  # Check if process exists
                        logger.warning(f"Lock file belongs to active process ({lock_pid}), not removing")
                    except OSError:
                        # Process doesn't exist, safe to remove stale lock
                        os.remove(lock_file)
                        logger.info(f"🔓 Removed stale lock file (PID {lock_pid} no longer exists)")
            else:
                logger.info("🔍 No lock file to clean up")
                
        except Exception as e:
            logger.warning(f"Could not remove lock file: {e}")
            # Force removal as last resort
            try:
                if os.path.exists(lock_file):
                    os.remove(lock_file)
                    logger.info("🔓 Force removed lock file")
            except:
                pass
        
        # 3. Close any remaining network connections
        try:
            import socket
            # Give time for connections to close naturally
            time.sleep(1)
        except:
            pass
        
        logger.info("🔴 Web dashboard stopped and cleaned up")

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

        # Start the trading bot
        logger.info("🚀 Starting trading bot main loop...")

        # Set startup source for notifications
        logger.info("🌐 BOT STARTUP INITIATED FROM: Console")

        # Ensure web dashboard is running from main thread management
        if not web_server_running:
            logger.info("🌐 Starting web dashboard alongside bot...")
            web_thread = threading.Thread(target=run_web_dashboard, daemon=False)
            web_thread.start()
            await asyncio.sleep(2)  # Give web dashboard time to start

        # Start the bot
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

def cleanup_process_resources():
    """Clean up process resources before shutdown"""
    logger = logging.getLogger(__name__)
    current_pid = os.getpid()
    
    try:
        # Close all open file descriptors except stdin, stdout, stderr
        import resource
        max_fd = resource.getrlimit(resource.RLIMIT_NOFILE)[0]
        for fd in range(3, min(max_fd, 1024)):  # Skip stdin(0), stdout(1), stderr(2)
            try:
                os.close(fd)
            except OSError:
                pass
        
        logger.info("🧹 Closed excess file descriptors")
    except Exception as e:
        logger.warning(f"Could not close file descriptors: {e}")
    
    try:
        # Release any remaining network resources
        import socket
        import gc
        gc.collect()  # Force garbage collection
        logger.info("🧹 Released network resources")
    except Exception as e:
        logger.warning(f"Could not release network resources: {e}")

async def main():
    """Main function for web dashboard bot restart"""
    global bot_manager, web_server_running, web_thread

    # Setup logging
    setup_logger()
    logger = logging.getLogger(__name__)

    # Enhanced signal handlers for graceful shutdown
    def enhanced_signal_handler(signum, frame):
        logger.info(f"🛑 Received signal {signum}, starting graceful shutdown...")
        signal_handler(signum, frame)
        
        # Additional cleanup
        global web_thread
        if web_thread and web_thread.is_alive():
            logger.info("🔄 Waiting for web thread to finish...")
            web_thread.join(timeout=5)  # Wait up to 5 seconds
            if web_thread.is_alive():
                logger.warning("⚠️ Web thread did not finish gracefully")
        
        cleanup_process_resources()
        
        # Exit cleanly
        os._exit(0)
    
    signal.signal(signal.SIGINT, enhanced_signal_handler)
    signal.signal(signal.SIGTERM, enhanced_signal_handler)

    logger.info("Starting Multi-Strategy Trading Bot with Persistent Web Interface")

    # SINGLE SOURCE WEB DASHBOARD LAUNCH - Only from main.py
    logger.info("🌐 MAIN.PY: Starting web dashboard (single source control)")
    logger.info("🚫 MAIN.PY: Direct web_dashboard.py launches are disabled")
    
    global web_thread
    web_thread = threading.Thread(target=run_web_dashboard, daemon=False)
    web_thread.daemon = False  # Explicitly set to non-daemon for proper cleanup
    web_thread.start()
    
    # Ensure thread started successfully
    time.sleep(1)
    if not web_thread.is_alive():
        logger.error("❌ Web dashboard thread failed to start")
        return
    else:
        logger.info("✅ Web dashboard thread started successfully")

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

        # DEPLOYMENT: Single source web dashboard launch
        logger.info("🚀 DEPLOYMENT: Starting web dashboard from main.py only")
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
        # Development mode - start normally without instance detection
        logger.info("🛠️ Development mode: Starting bot normally")

        # Original development mode
        bot_manager = None
        sys.modules[__name__].bot_manager = None

        # DEVELOPMENT: Single source web dashboard launch from main.py
        logger.info("🛠️ DEVELOPMENT: Starting web dashboard from main.py only")
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