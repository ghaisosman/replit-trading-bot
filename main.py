import asyncio
import logging
import os
import signal
import sys
import threading
import time
import psutil
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
    global web_server_running, flask_server
    print("\n🛑 Shutdown signal received...")

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

def cleanup_all_locks():
    """Clean up all lock files safely with enhanced validation"""
    lock_files = [
        "/tmp/bot_restart_lock",
        "/tmp/web_dashboard.lock", 
        "/tmp/bot_restart_count",
        "/tmp/bot_cleanup_in_progress"  # Additional cleanup tracking
    ]

    for lock_file in lock_files:
        try:
            if os.path.exists(lock_file):
                # Validate lock file before removal
                try:
                    with open(lock_file, 'r') as f:
                        content = f.read().strip()
                    if content:  # Only remove if file has content (valid lock)
                        os.remove(lock_file)
                        print(f"🧹 Cleaned up: {os.path.basename(lock_file)} (content: {content[:50]})")
                    else:
                        os.remove(lock_file)  # Remove empty files too
                        print(f"🧹 Removed empty lock: {os.path.basename(lock_file)}")
                except:
                    # If we can't read it, remove it anyway
                    os.remove(lock_file)
                    print(f"🧹 Force removed: {os.path.basename(lock_file)}")
        except Exception as e:
            print(f"⚠️ Could not remove {lock_file}: {e}")

def force_cleanup_processes():
    """Force cleanup of any remaining bot processes"""
    current_pid = os.getpid()
    killed_count = 0

    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.pid == current_pid:
                    continue

                cmdline = ' '.join(proc.info['cmdline'] or [])

                # Kill processes that might be conflicting
                if any(pattern in cmdline.lower() for pattern in [
                    'main.py', 'web_dashboard', 'flask', 'python main'
                ]):
                    proc.terminate()
                    try:
                        proc.wait(timeout=3)
                    except psutil.TimeoutExpired:
                        proc.kill()
                    killed_count += 1
                    print(f"🔄 Terminated process {proc.pid}: {proc.info['name']}")

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

    except Exception as e:
        print(f"⚠️ Error during process cleanup: {e}")

    if killed_count > 0:
        print(f"🔄 Terminated {killed_count} conflicting processes")
        time.sleep(2)  # Give time for cleanup

    return killed_count

def run_web_dashboard():
    """Run web dashboard in separate thread - keeps running even if bot stops"""
    global web_server_running, flask_server
    logger = logging.getLogger(__name__)

    # Singleton check - prevent multiple instances
    if web_server_running:
        logger.info("🌐 Web dashboard already running - skipping duplicate start")
        return

    # Simple restart prevention with current PID check
    restart_lock_file = "/tmp/bot_restart_lock"
    current_pid = os.getpid()

    if os.path.exists(restart_lock_file):
        try:
            with open(restart_lock_file, 'r') as f:
                data = f.read().strip()

            # Simple validation - check if it's recent and from different process
            try:
                if ',' in data:
                    parts = data.split(',', 1)
                    if len(parts) == 2:
                        timestamp_str = parts[0].strip()
                        pid_str = parts[1].strip()

                        # Extract only digits
                        clean_timestamp = ''.join(c for c in timestamp_str if c.isdigit())
                        clean_pid = ''.join(c for c in pid_str if c.isdigit())

                        if clean_timestamp and clean_pid:
                            lock_timestamp = int(clean_timestamp)
                            lock_pid = int(clean_pid)

                            # Check if recent (within 15 seconds) and different process
                            if (time.time() - lock_timestamp < 15 and lock_pid != current_pid):
                                try:
                                    os.kill(lock_pid, 0)  # Check if process exists
                                    logger.info(f"🔄 Recent lock detected - another instance running (PID: {lock_pid})")
                                    return
                                except OSError:
                                    # Process doesn't exist, continue
                                    pass

                # Remove stale or invalid lock
                os.remove(restart_lock_file)
                logger.info("🔄 Removed stale restart lock file")

            except (ValueError, IndexError) as e:
                logger.warning(f"Invalid lock format: {data} - removing")
                os.remove(restart_lock_file)

        except Exception as e:
            logger.warning(f"Error reading restart lock: {e}")
            try:
                os.remove(restart_lock_file)
            except:
                pass

    # Create restart lock with simple format
    try:
        with open(restart_lock_file, 'w') as f:
            f.write(f"{int(time.time())},{current_pid}")
        logger.debug(f"🔒 Created restart lock: {int(time.time())},{current_pid}")
    except Exception as e:
        logger.warning(f"Could not create restart lock: {e}")

    # Check if running in deployment environment
    is_deployment = os.environ.get('REPLIT_DEPLOYMENT') == '1'
    if is_deployment:
        logger.info("🚀 RUNNING IN REPLIT DEPLOYMENT MODE")

    try:
        # Import and run web dashboard
        from web_dashboard import app

        # Simple web dashboard lock
        lock_file = "/tmp/web_dashboard.lock"

        if os.path.exists(lock_file):
            try:
                with open(lock_file, 'r') as f:
                    data = f.read().strip()

                # Simple validation
                try:
                    if ',' in data:
                        parts = data.split(',', 1)
                        if len(parts) == 2:
                            pid_str = parts[0].strip()
                            timestamp_str = parts[1].strip()

                            clean_pid = ''.join(c for c in pid_str if c.isdigit())
                            clean_timestamp = ''.join(c for c in timestamp_str if c.isdigit())

                            if clean_pid and clean_timestamp:
                                lock_pid = int(clean_pid)
                                lock_timestamp = int(clean_timestamp)

                                # Check if recent and process exists
                                if (time.time() - lock_timestamp < 30):
                                    try:
                                        os.kill(lock_pid, 0)
                                        logger.info(f"🔄 Web dashboard already running (PID: {lock_pid})")
                                        return
                                    except OSError:
                                        pass

                    # Remove stale lock
                    os.remove(lock_file)
                    logger.info("🔄 Removed stale web dashboard lock")

                except (ValueError, IndexError):
                    os.remove(lock_file)

            except Exception:
                try:
                    os.remove(lock_file)
                except:
                    pass

        # Create web dashboard lock
        try:
            with open(lock_file, 'w') as f:
                f.write(f"{current_pid},{int(time.time())}")
            logger.info(f"🔒 Created web dashboard lock (PID: {current_pid})")
        except Exception as e:
            logger.warning(f"Could not create web dashboard lock: {e}")

        # Check and cleanup port conflicts
        if not check_port_available(5000):
            logger.error("🚨 PORT 5000 UNAVAILABLE: Cleaning up...")

            # Force cleanup processes using port 5000
            try:
                for proc in psutil.process_iter(['pid', 'name', 'connections']):
                    try:
                        if proc.info['connections']:
                            for conn in proc.info['connections']:
                                if hasattr(conn, 'laddr') and conn.laddr and conn.laddr.port == 5000:
                                    if proc.pid != os.getpid():
                                        proc.terminate()
                                        logger.info(f"🔄 Killed process {proc.pid} using port 5000")
                                        try:
                                            proc.wait(timeout=3)
                                        except psutil.TimeoutExpired:
                                            proc.kill()
                                        break
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        continue

                time.sleep(3)

                if check_port_available(5000):
                    logger.info("✅ Port 5000 successfully freed")
                else:
                    logger.error("❌ Port 5000 still unavailable after cleanup")
                    return

            except Exception as e:
                logger.error(f"Error during port cleanup: {e}")
                return

        web_server_running = True
        logger.info("🌐 Starting web dashboard on 0.0.0.0:5000")

        # Get port from environment for deployment compatibility
        port = int(os.environ.get('PORT', 5000))

        # Store Flask server reference for shutdown
        from werkzeug.serving import make_server

        flask_server = make_server('0.0.0.0', port, app, threaded=True)
        logger.info(f"🌐 Flask server created on port {port}")

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
            # Try alternative cleanup
            try:
                killed_count = 0
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        if proc.info['cmdline']:
                            cmdline_str = ' '.join(proc.info['cmdline'])
                            if ('python' in proc.info['name'].lower() and 
                                ('web_dashboard' in cmdline_str or 'flask' in cmdline_str or 'main.py' in cmdline_str)):
                                if proc.pid != os.getpid():
                                    proc.terminate()
                                    logger.info(f"🔄 Terminated process {proc.pid}: {proc.info['name']}")
                                    killed_count += 1
                                    try:
                                        proc.wait(timeout=3)
                                    except psutil.TimeoutExpired:
                                        proc.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        continue

                if killed_count > 0:
                    logger.info(f"🔄 Terminated {killed_count} processes")
                    time.sleep(5)

                if check_port_available(5000):
                    logger.info("✅ Port 5000 cleared successfully")
                    # Try to start again
                    web_server_running = True
                    port = int(os.environ.get('PORT', 5000))
                    logger.info(f"🌐 Restarting web dashboard on 0.0.0.0:{port}")
                    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)
                else:
                    logger.error("💡 Please restart the entire Repl to clear port conflicts")
                    return

            except Exception as cleanup_error:
                logger.error(f"Error during port cleanup: {cleanup_error}")
                return

        web_server_running = True
        logger.info("🌐 WEB DASHBOARD: Starting persistent web interface on http://0.0.0.0:5000")

        # Run Flask with minimal logging
        import logging as flask_logging
        flask_log = flask_logging.getLogger('werkzeug')
        flask_log.setLevel(flask_logging.WARNING)

        app.config['TESTING'] = False
        app.config['DEBUG'] = False

        port = int(os.environ.get('PORT', 5000))
        logger.info(f"🌐 Starting web dashboard on 0.0.0.0:{port}")
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)

    except Exception as e:
        logger.error(f"Web dashboard error: {e}")
    finally:
        web_server_running = False

        # Cleanup on exit
        logger.info("🧹 Starting web dashboard cleanup...")

        if flask_server:
            try:
                flask_server.shutdown()
                logger.info("✅ Flask server shut down")
            except Exception as e:
                logger.warning(f"Error shutting down Flask server: {e}")
            finally:
                flask_server = None

        # Clean up lock files
        lock_files = ["/tmp/web_dashboard.lock", "/tmp/bot_restart_lock"]
        current_pid = os.getpid()

        for lock_file in lock_files:
            try:
                if os.path.exists(lock_file):
                    # Simple ownership check
                    try:
                        with open(lock_file, 'r') as f:
                            data = f.read().strip()

                        if str(current_pid) in data:
                            os.remove(lock_file)
                            logger.info(f"🔓 Removed our lock file: {os.path.basename(lock_file)}")
                        else:
                            logger.info(f"🔍 Lock file belongs to another process: {os.path.basename(lock_file)}")
                    except:
                        # If we can't read it, try to remove it anyway
                        os.remove(lock_file)
                        logger.info(f"🔓 Force removed lock file: {os.path.basename(lock_file)}")

            except Exception as e:
                logger.warning(f"Error cleaning up lock file {lock_file}: {e}")

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

    await asyncio.sleep(1)
    logger.info("🌐 Using existing Web Dashboard instance")

    try:
        # Initialize the bot manager with enhanced error handling and validation
        logger.info("🔧 INITIALIZING BOT MANAGER...")

        try:
            # FIXED: Add pre-initialization checks to catch issues early
            logger.info("🔍 Pre-initialization validation...")

            # Validate imports first
            try:
                from src.config.global_config import global_config
                from src.binance_client.client import BinanceClientWrapper
                logger.info("✅ Core imports validated")
            except ImportError as import_error:
                logger.error(f"❌ IMPORT ERROR: {import_error}")
                raise

            # Validate configuration
            if not global_config.validate_config():
                logger.error("❌ CONFIGURATION VALIDATION FAILED")
                raise ValueError("Invalid configuration")

            logger.info("🚀 Creating bot manager instance...")
            # Import BotManager here to avoid circular imports
            from src.bot_manager import BotManager
            bot_manager = BotManager()

            # FIXED: Validate bot manager was created properly
            if not hasattr(bot_manager, 'logger') or not hasattr(bot_manager, 'binance_client'):
                raise RuntimeError("Bot manager initialization incomplete")

            logger.info("✅ Bot manager created successfully")
            logger.info(f"🔍 Bot manager validation: logger={hasattr(bot_manager, 'logger')}, client={hasattr(bot_manager, 'binance_client')}")

        except Exception as e:
            logger.error(f"❌ CRITICAL: Bot manager initialization failed: {e}")
            logger.error(f"🔍 Error type: {type(e).__name__}")
            logger.error("💡 Common causes:")
            logger.error("   - Invalid API keys or network issues")
            logger.error("   - Missing environment variables")
            logger.error("   - Configuration file errors")

            # FIXED: Add more detailed error information for debugging
            import traceback
            logger.error(f"🔍 Full traceback: {traceback.format_exc()}")
            raise

        # Enhanced bot manager reference sharing with error handling
        try:
            sys.modules['__main__'].bot_manager = bot_manager
            logger.info("✅ Bot manager registered in main module")
        except Exception as e:
            logger.warning(f"Could not register in main module: {e}")

        try:
            web_dashboard.bot_manager = bot_manager
            web_dashboard.shared_bot_manager = bot_manager
            logger.info("✅ Bot manager registered in web dashboard module")
        except Exception as e:
            logger.warning(f"Could not register in web dashboard: {e}")

        try:
            setattr(sys.modules[__name__], 'current_bot_manager', bot_manager)
            logger.info("✅ Bot manager registered with additional reference")
        except Exception as e:
            logger.warning(f"Could not create additional reference: {e}")

        # Start the trading bot
        logger.info("🚀 Starting trading bot main loop...")
        logger.info("🌐 BOT STARTUP INITIATED FROM: Console")

        # Ensure web dashboard is running
        if not web_server_running:
            logger.info("🌐 Starting web dashboard alongside bot...")
            web_thread = threading.Thread(target=run_web_dashboard, daemon=False)
            web_thread.start()
            await asyncio.sleep(2)

        # Start the bot
        bot_task = asyncio.create_task(bot_manager.start())
        shutdown_task = asyncio.create_task(shutdown_event.wait())

        done, pending = await asyncio.wait(
            [bot_task, shutdown_task],
            return_when=asyncio.FIRST_COMPLETED
        )

        if shutdown_task in done:
            logger.info("🛑 Shutdown signal received, stopping bot...")
            await bot_manager.stop("Manual shutdown via Ctrl+C or SIGTERM")

        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        logger.info("🔴 Bot stopped but web interface remains active for control")
        logger.info("💡 You can restart the bot using the web interface")

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
    global bot_manager, web_server_running, web_thread

    setup_logger()
    logger = logging.getLogger(__name__)

    def enhanced_signal_handler(signum, frame):
        logger.info(f"🛑 Received signal {signum}, starting graceful shutdown...")
        signal_handler(signum, frame)

        global web_thread
        if web_thread and web_thread.is_alive():
            logger.info("🔄 Waiting for web thread to finish...")
            web_thread.join(timeout=5)
            if web_thread.is_alive():
                logger.warning("⚠️ Web thread did not finish gracefully")

        os._exit(0)

    signal.signal(signal.SIGINT, enhanced_signal_handler)
    signal.signal(signal.SIGTERM, enhanced_signal_handler)

    logger.info("Starting Multi-Strategy Trading Bot with Persistent Web Interface")
    logger.info("🌐 MAIN.PY: Starting web dashboard (single source control)")

    global web_thread
    web_thread = threading.Thread(target=run_web_dashboard, daemon=False)
    web_thread.daemon = False
    web_thread.start()

    time.sleep(1)
    if not web_thread.is_alive():
        logger.error("❌ Web dashboard thread failed to start")
        return
    else:
        logger.info("✅ Web dashboard thread started successfully")

    await asyncio.sleep(3)
    logger.info("🌐 Web Dashboard accessible and will remain active")

    try:
        # Initialize the bot manager with enhanced error handling and validation
        logger.info("🔧 INITIALIZING BOT MANAGER...")

        try:
            # FIXED: Add pre-initialization checks to catch issues early
            logger.info("🔍 Pre-initialization validation...")

            # Validate imports first
            try:
                from src.config.global_config import global_config
                from src.binance_client.client import BinanceClientWrapper
                logger.info("✅ Core imports validated")
            except ImportError as import_error:
                logger.error(f"❌ IMPORT ERROR: {import_error}")
                raise

            # Validate configuration
            if not global_config.validate_config():
                logger.error("❌ CONFIGURATION VALIDATION FAILED")
                raise ValueError("Invalid configuration")

            logger.info("🚀 Creating bot manager instance...")
            # Import BotManager here to avoid circular imports
            from src.bot_manager import BotManager
            bot_manager = BotManager()

            # FIXED: Validate bot manager was created properly
            if not hasattr(bot_manager, 'logger') or not hasattr(bot_manager, 'binance_client'):
                raise RuntimeError("Bot manager initialization incomplete")

            logger.info("✅ Bot manager created successfully")
            logger.info(f"🔍 Bot manager validation: logger={hasattr(bot_manager, 'logger')}, client={hasattr(bot_manager, 'binance_client')}")

        except Exception as e:
            logger.error(f"❌ CRITICAL: Bot manager initialization failed: {e}")
            logger.error(f"🔍 Error type: {type(e).__name__}")
            logger.error("💡 Common causes:")
            logger.error("   - Invalid API keys or network issues")
            logger.error("   - Missing environment variables")
            logger.error("   - Configuration file errors")

            # FIXED: Add more detailed error information for debugging
            import traceback
            logger.error(f"🔍 Full traceback: {traceback.format_exc()}")
            raise

        # Enhanced bot manager reference sharing with error handling
        try:
            sys.modules['__main__'].bot_manager = bot_manager
            logger.info("✅ Bot manager registered in main module")
        except Exception as e:
            logger.warning(f"Could not register in main module: {e}")

        try:
            web_dashboard.bot_manager = bot_manager
            web_dashboard.shared_bot_manager = bot_manager
            logger.info("✅ Bot manager registered in web dashboard module")
        except Exception as e:
            logger.warning(f"Could not register in web dashboard: {e}")

        try:
            setattr(sys.modules[__name__], 'current_bot_manager', bot_manager)
            logger.info("✅ Bot manager registered with additional reference")
        except Exception as e:
            logger.warning(f"Could not create additional reference: {e}")

        # Start the bot in a task
        logger.info("🚀 Starting trading bot main loop...")
        bot_task = asyncio.create_task(bot_manager.start())
        shutdown_task = asyncio.create_task(shutdown_event.wait())

        done, pending = await asyncio.wait(
            [bot_task, shutdown_task],
            return_when=asyncio.FIRST_COMPLETED
        )

        if shutdown_task in done:
            logger.info("🛑 Shutdown signal received, stopping bot...")
            await bot_manager.stop("Manual shutdown via Ctrl+C or SIGTERM")

        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        logger.info("🔴 Bot stopped but web interface remains active for control")
        logger.info("💡 You can restart the bot using the web interface")

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
    # SAFETY CHECK: Prevent restart loop on critical import errors
    # Check if web_dashboard can be imported without errors
    try:
        import web_dashboard
        logger_test = logging.getLogger(__name__)
        logger_test.info("✅ Import test passed - starting normally")
    except SyntaxError as syntax_error:
        print(f"🚫 CRITICAL SYNTAX ERROR DETECTED: {syntax_error}")
        print("🔧 Please fix the syntax error before starting the bot")
        print("💡 Check web_dashboard.py for syntax issues")
        exit(1)
    except Exception as import_error:
        print(f"🚫 CRITICAL IMPORT ERROR: {import_error}")
        print("🔧 Please fix the import error before starting the bot")
        exit(1)

    # Setup logging first
    setup_logger()
    logger = logging.getLogger(__name__)

    # FORCE CLEANUP AND RESET on startup
    logger.info("🧹 PERFORMING STARTUP CLEANUP...")

    # Clean all lock files
    cleanup_all_locks()

    # Force cleanup any conflicting processes
    killed_count = force_cleanup_processes()

    if killed_count > 0:
        logger.info("🕐 Waiting for cleanup to complete...")
        time.sleep(3)

    # FIXED: Enhanced restart loop protection with better error handling
    restart_count_file = "/tmp/bot_restart_count"
    current_pid = os.getpid()

    try:
        if os.path.exists(restart_count_file):
            with open(restart_count_file, 'r') as f:
                restart_data = f.read().strip()

            # Parse restart data (format: count,timestamp,pid)
            if ',' in restart_data:
                parts = restart_data.split(',')
                if len(parts) >= 3:
                    try:
                        restart_count = int(parts[0])
                        last_restart_time = float(parts[1])
                        last_pid = int(parts[2])

                        # FIXED: More aggressive restart loop prevention
                        if (restart_count >= 3 and 
                            time.time() - last_restart_time < 120 and  # Extended to 2 minutes
                            last_pid == current_pid):
                            logger.error(f"🚫 RESTART LOOP DETECTED: {restart_count} restarts in 2 minutes from PID {current_pid}")
                            logger.error("🔄 Waiting 60 seconds before allowing restart...")
                            time.sleep(60)  # Extended wait time

                        # Reset counter if enough time has passed or different PID
                        if (time.time() - last_restart_time > 600 or last_pid != current_pid):  # Extended to 10 minutes
                            restart_count = 0

                    except ValueError:
                        restart_count = 0
                        logger.warning("Invalid restart count data, resetting")
                else:
                    restart_count = 0
            else:
                restart_count = 0

            # Update restart count
            restart_count += 1
            with open(restart_count_file, 'w') as f:
                f.write(f"{restart_count},{time.time()},{current_pid}")

            logger.info(f"🔄 Restart count: {restart_count} (PID: {current_pid})")

        else:
            # First start
            with open(restart_count_file, 'w') as f:
                f.write(f"1,{time.time()},{current_pid}")
            logger.info(f"🚀 First startup detected (PID: {current_pid})")

    except Exception as e:
        logger.warning(f"Could not manage restart count: {e}")
        # FIXED: Continue without restart protection if file operations fail
        logger.info("🔄 Continuing startup without restart protection")

    # Check if running in deployment
    is_deployment = os.environ.get('REPLIT_DEPLOYMENT') == '1'

    if is_deployment:
        logger.info("🚀 STARTING IN REPLIT DEPLOYMENT MODE")

        bot_manager = None
        sys.modules[__name__].bot_manager = None

        logger.info("🚀 DEPLOYMENT: Starting web dashboard from main.py only")
        web_thread = threading.Thread(target=run_web_dashboard, daemon=False)
        web_thread.start()

        time.sleep(2)
        logger.info("🌐 Deployment web dashboard active")
        logger.info("💡 Access your bot via the web interface at your deployment URL")
        logger.info("🔄 Bot can be started/stopped through the web dashboard")

        try:
            # FIXED: Add process health monitoring to prevent infinite loops
            health_check_count = 0
            while True:
                time.sleep(10)

                # Health check every 10 iterations (100 seconds)
                health_check_count += 1
                if health_check_count % 10 == 0:
                    try:
                        # Check if web thread is still alive
                        if web_thread and not web_thread.is_alive():
                            logger.error("🚨 Web dashboard thread died, restarting...")
                            web_thread = threading.Thread(target=run_web_dashboard, daemon=False)
                            web_thread.start()

                        # Check memory usage
                        try:
                            process = psutil.Process()
                            memory_mb = process.memory_info().rss / 1024 / 1024
                            if memory_mb > 500:  # 500MB threshold
                                logger.warning(f"⚠️ High memory usage: {memory_mb:.1f} MB")
                        except:
                            pass

                        logger.debug(f"✅ Health check {health_check_count} passed")
                    except Exception as health_error:
                        logger.error(f"Health check failed: {health_error}")

        except KeyboardInterrupt:
            logger.info("🔴 Deployment shutdown")
    else:
        logger.info("🛠️ Development mode: Starting bot normally")

        bot_manager = None
        sys.modules[__name__].bot_manager = None

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