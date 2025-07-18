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

def run_web_dashboard():
    """Run web dashboard in separate thread - keeps running even if bot stops"""
    global web_server_running, flask_server
    logger = logging.getLogger(__name__)

    # Singleton check - prevent multiple instances
    if web_server_running:
        logger.info("🌐 Web dashboard already running - skipping duplicate start")
        return

    # Enhanced restart prevention with robust lock file handling
    restart_lock_file = "/tmp/bot_restart_lock"
    current_pid = os.getpid()

    if os.path.exists(restart_lock_file):
        try:
            with open(restart_lock_file, 'r') as f:
                data = f.read().strip()

            # BULLETPROOF PARSING - handles any format corruption
            lock_valid = False
            last_start = 0
            last_pid = 0

            try:
                if ',' in data:
                    parts = data.split(',')
                    if len(parts) >= 2:
                        # ROBUST PARSING: Try both timestamp,pid and pid,timestamp formats
                        part1 = parts[0].strip()
                        part2 = parts[1].strip()
                        
                        # Extract only digits from both parts
                        clean_part1 = ''.join(c for c in part1 if c.isdigit())
                        clean_part2 = ''.join(c for c in part2 if c.isdigit())
                        
                        if clean_part1 and clean_part2:
                            # Convert to integers for comparison
                            val1 = int(clean_part1)
                            val2 = int(clean_part2)
                            
                            # Determine which is timestamp vs PID based on realistic ranges
                            # PIDs are typically < 100000, timestamps are > 1600000000
                            if val1 > 1600000000 and val2 < 100000:
                                # Format: timestamp,pid
                                last_start = val1
                                last_pid = val2
                                lock_valid = True
                            elif val2 > 1600000000 and val1 < 100000:
                                # Format: pid,timestamp
                                last_start = val2
                                last_pid = val1
                                lock_valid = True
                            else:
                                # Invalid format - use current time to expire it
                                logger.warning(f"Ambiguous lock format: {data} - treating as expired")
                                last_start = 0
                                last_pid = 0

                if lock_valid and last_start > 0 and last_pid > 0:
                    # Check if it's too recent AND from a different process
                    time_diff = time.time() - last_start
                    if time_diff < 15 and last_pid != current_pid:
                        try:
                            # Check if the other process is still running
                            os.kill(last_pid, 0)
                            logger.info(f"🔄 Restart prevented - another instance running (PID: {last_pid})")
                            return
                        except OSError:
                            # Process doesn't exist anymore, continue
                            logger.info(f"🔄 Stale lock detected - previous process {last_pid} no longer exists")
                else:
                    # Either invalid format or expired lock
                    if data:
                        logger.warning(f"Invalid/expired lock file format: '{data}' - cleaning up")
                    
            except (ValueError, IndexError, TypeError) as e:
                logger.warning(f"Lock file parsing error: {e} - data: '{data}' - treating as corrupted")
            
            # Always remove invalid, stale, or corrupted locks
            try:
                os.remove(restart_lock_file)
                logger.info(f"🔄 Removed problematic restart lock file")
            except Exception as remove_error:
                logger.warning(f"Could not remove lock file: {remove_error}")

        except Exception as e:
            logger.warning(f"Error reading restart lock: {e}")
            # Force remove any problematic lock file
            try:
                os.remove(restart_lock_file)
                logger.info(f"🔄 Force removed restart lock after read error")
            except:
                pass

    # Create restart lock with CONSISTENT format (timestamp,pid)
    try:
        with open(restart_lock_file, 'w') as f:
            # Always use format: timestamp,pid (no decimals, no ambiguity)
            timestamp = int(time.time())
            f.write(f"{timestamp},{current_pid}")
        logger.debug(f"🔒 Created restart lock: {timestamp},{current_pid}")
    except Exception as e:
        logger.warning(f"Could not create restart lock: {e}")
        pass

    # Check if running in deployment environment
    is_deployment = os.environ.get('REPLIT_DEPLOYMENT') == '1'
    if is_deployment:
        logger.info("🚀 RUNNING IN REPLIT DEPLOYMENT MODE")

    try:
        # Import and run web dashboard
        from web_dashboard import app

        # Enhanced web dashboard lock with timeout
        lock_file = "/tmp/web_dashboard.lock"
        current_pid = os.getpid()

        if os.path.exists(lock_file):
            try:
                with open(lock_file, 'r') as f:
                    data = f.read().strip()

                # BULLETPROOF PARSING - identical to restart lock logic
                lock_valid = False
                existing_pid = 0
                lock_time = 0

                try:
                    if ',' in data:
                        parts = data.split(',')
                        if len(parts) >= 2:
                            # ROBUST PARSING: Try both pid,timestamp and timestamp,pid formats
                            part1 = parts[0].strip()
                            part2 = parts[1].strip()
                            
                            # Extract only digits from both parts
                            clean_part1 = ''.join(c for c in part1 if c.isdigit())
                            clean_part2 = ''.join(c for c in part2 if c.isdigit())
                            
                            if clean_part1 and clean_part2:
                                # Convert to integers for comparison
                                val1 = int(clean_part1)
                                val2 = int(clean_part2)
                                
                                # Determine which is timestamp vs PID based on realistic ranges
                                # PIDs are typically < 100000, timestamps are > 1600000000
                                if val1 < 100000 and val2 > 1600000000:
                                    # Format: pid,timestamp
                                    existing_pid = val1
                                    lock_time = val2
                                    lock_valid = True
                                elif val2 < 100000 and val1 > 1600000000:
                                    # Format: timestamp,pid
                                    existing_pid = val2
                                    lock_time = val1
                                    lock_valid = True
                                else:
                                    # Invalid format - treat as expired
                                    logger.warning(f"Ambiguous web dashboard lock format: {data} - treating as expired")
                                    existing_pid = 0
                                    lock_time = 0

                    if lock_valid and existing_pid > 0 and lock_time > 0:
                        # Check if lock is recent and process still exists
                        time_diff = time.time() - lock_time
                        if time_diff < 30:  # 30 second timeout
                            try:
                                os.kill(existing_pid, 0)
                                logger.info(f"🔄 Web dashboard already running (PID: {existing_pid})")
                                return
                            except OSError:
                                # Process doesn't exist, continue
                                logger.info(f"🔄 Stale web dashboard lock - process {existing_pid} no longer exists")
                    else:
                        # Either invalid format or expired lock
                        if data:
                            logger.warning(f"Invalid/expired web dashboard lock format: '{data}' - cleaning up")
                        
                except (ValueError, IndexError, TypeError) as parse_error:
                    logger.warning(f"Web dashboard lock parsing error: {parse_error} - data: '{data}' - treating as corrupted")

                # Always remove invalid, stale, or corrupted locks
                try:
                    os.remove(lock_file)
                    logger.info("🔄 Removed web dashboard lock file")
                except Exception as remove_error:
                    logger.warning(f"Could not remove web dashboard lock: {remove_error}")

            except Exception as e:
                logger.warning(f"Error reading web dashboard lock file: {e}")
                # Force remove problematic lock
                try:
                    os.remove(lock_file)
                    logger.info("🔄 Force removed web dashboard lock after read error")
                except:
                    pass

        # Create lock file with CONSISTENT format (pid,timestamp)
        try:
            with open(lock_file, 'w') as f:
                # Always use format: pid,timestamp (no decimals, no ambiguity)
                timestamp = int(time.time())
                f.write(f"{current_pid},{timestamp}")
            logger.info(f"🔒 Created web dashboard lock (PID: {current_pid})")
        except Exception as e:
            logger.warning(f"Could not create web dashboard lock: {e}")

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

        # Signal handling is managed by the main thread
        # No signal setup needed in web dashboard thread

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
        if flask_server:
            try:
                flask_server.shutdown()
                logger.info("✅ Flask server shut down")
            except Exception as e:
                logger.warning(f"Error shutting down Flask server: {e}")
            finally:
                flask_server = None

        # 2. Clean up lock files with robust verification
        lock_files = ["/tmp/web_dashboard.lock", "/tmp/bot_restart_lock"]
        current_pid = os.getpid()
        
        for lock_file in lock_files:
            try:
                if os.path.exists(lock_file):
                    # Robust lock file verification
                    lock_belongs_to_us = False
                    try:
                        with open(lock_file, 'r') as f:
                            data = f.read().strip()
                        
                        if ',' in data:
                            parts = data.split(',')
                            if len(parts) >= 2:
                                # Extract PID (handle any format)
                                pid_part = parts[0].strip()
                                clean_pid = ''.join(c for c in pid_part if c.isdigit())
                                if clean_pid and int(clean_pid) == current_pid:
                                    lock_belongs_to_us = True
                        
                        if lock_belongs_to_us:
                            os.remove(lock_file)
                            logger.info(f"🔓 Removed our lock file: {os.path.basename(lock_file)}")
                        else:
                            # Verify if other process still exists
                            try:
                                if clean_pid:
                                    os.kill(int(clean_pid), 0)
                                    logger.warning(f"Lock file belongs to active process ({clean_pid}), not removing")
                                else:
                                    # Invalid format, safe to remove
                                    os.remove(lock_file)
                                    logger.info(f"🔓 Removed invalid lock file: {os.path.basename(lock_file)}")
                            except (OSError, ValueError):
                                # Process doesn't exist or invalid PID, safe to remove
                                os.remove(lock_file)
                                logger.info(f"🔓 Removed stale lock file: {os.path.basename(lock_file)}")
                    
                    except Exception as parse_error:
                        # Cannot parse lock file, force remove
                        logger.warning(f"Cannot parse lock file {lock_file}: {parse_error}")
                        os.remove(lock_file)
                        logger.info(f"🔓 Force removed unparseable lock file: {os.path.basename(lock_file)}")

            except Exception as e:
                logger.warning(f"Error cleaning up lock file {lock_file}: {e}")
                # Final attempt to remove
                try:
                    if os.path.exists(lock_file):
                        os.remove(lock_file)
                        logger.info(f"🔓 Final cleanup of lock file: {os.path.basename(lock_file)}")
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

        # Enhanced bot manager reference sharing with multiple access points
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
            # Additional reference for stability
            setattr(sys.modules[__name__], 'current_bot_manager', bot_manager)
            logger.info("✅ Bot manager registered with additional reference")
        except Exception as e:
            logger.warning(f"Could not create additional reference: {e}")

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

        # Enhanced bot manager reference sharing with multiple access points
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
            # Additional reference for stability
            setattr(sys.modules[__name__], 'current_bot_manager', bot_manager)
            logger.info("✅ Bot manager registered with additional reference")
        except Exception as e:
            logger.warning(f"Could not create additional reference: {e}")

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

    # ENHANCED RESTART LOOP DETECTION with bulletproof validation
    restart_count_file = "/tmp/bot_restart_count"
    max_restarts = 5
    restart_window = 300  # 5 minutes
    
    try:
        current_time = time.time()
        restart_count = 0
        last_restart_time = 0
        
        if os.path.exists(restart_count_file):
            try:
                with open(restart_count_file, 'r') as f:
                    data = f.read().strip()
                    
                # BULLETPROOF PARSING for restart count file
                if ',' in data:
                    parts = data.split(',')
                    if len(parts) >= 2:
                        # Extract only digits from both parts
                        clean_count = ''.join(c for c in parts[0] if c.isdigit())
                        clean_time = ''.join(c for c in parts[1] if c.isdigit())
                        
                        if clean_count and clean_time:
                            restart_count = int(clean_count)
                            last_restart_time = float(clean_time)
                            
                            # Reset counter if outside window
                            if current_time - last_restart_time > restart_window:
                                restart_count = 0
                                logger.info(f"🔄 Restart counter reset - outside {restart_window}s window")
                        else:
                            logger.warning(f"Invalid restart count format: {data} - resetting")
                            restart_count = 0
                    else:
                        logger.warning(f"Malformed restart count data: {data} - resetting")
                        restart_count = 0
                else:
                    logger.warning(f"No comma in restart count data: {data} - resetting")
                    restart_count = 0
                    
            except Exception as parse_error:
                logger.warning(f"Restart count parsing error: {parse_error} - resetting to 0")
                restart_count = 0
        
        # Check for restart loop
        if restart_count >= max_restarts:
            logger.error(f"🚨 RESTART LOOP DETECTED: {restart_count} restarts in {restart_window}s")
            logger.error(f"🛑 EMERGENCY STOP: Preventing infinite restart loop")
            logger.error(f"💡 SOLUTION: Check logs for root cause, manually restart when ready")
            
            # Clean up all lock files to prevent future issues
            for lock_file in ["/tmp/web_dashboard.lock", "/tmp/bot_restart_lock", restart_count_file]:
                try:
                    if os.path.exists(lock_file):
                        os.remove(lock_file)
                        logger.info(f"🧹 Cleaned up: {lock_file}")
                except:
                    pass
            
            # Exit gracefully
            exit(1)
        
        # Update restart counter with consistent format
        restart_count += 1
        with open(restart_count_file, 'w') as f:
            f.write(f"{restart_count},{int(current_time)}")
        
        logger.info(f"🔄 Bot start #{restart_count} (window: {restart_window}s)")
        
    except Exception as e:
        logger.warning(f"Restart detection error: {e}")
        # Continue anyway - don't let restart detection break the bot

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
# Auto-commit permanently removed for stability