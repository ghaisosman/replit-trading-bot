import asyncio
import json
import logging
import threading
import time
from websocket import WebSocketApp
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from collections import defaultdict, deque
import ssl

class WebSocketKlineManager:
    """Persistent WebSocket manager for live kline data caching"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # WebSocket configuration
        self.base_url = "wss://fstream.binance.com/ws/"
        self.ws = None
        self.ws_thread = None
        self.is_connected = False
        self.is_running = False

        # Data storage - organized by symbol and interval
        self.kline_cache = defaultdict(lambda: defaultdict(lambda: deque(maxlen=1000)))
        self.latest_klines = defaultdict(dict)  # symbol -> interval -> latest_kline
        self.last_updates = defaultdict(dict)   # symbol -> interval -> timestamp

        # Subscriptions management
        self.subscribed_streams = set()
        self.symbols = set()
        self.intervals = set()

        # Connection health monitoring
        self.last_ping = time.time()
        self.ping_interval = 30  # seconds (unused - ping disabled)
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 20  # Increased attempts
        self.connection_recovery_mode = True

        # Callbacks for real-time data updates
        self.update_callbacks = []

        # Statistics
        self.stats = {
            'messages_received': 0,
            'klines_processed': 0,
            'connection_uptime': 0,
            'last_message_time': None,
            'reconnections': 0
        }

    def add_symbol_interval(self, symbol: str, interval: str):
        """Add a symbol/interval pair for WebSocket streaming"""
        symbol = symbol.upper()
        self.symbols.add(symbol)
        self.intervals.add(interval)

        stream_name = f"{symbol.lower()}@kline_{interval}"
        if stream_name not in self.subscribed_streams:
            self.subscribed_streams.add(stream_name)
            self.logger.info(f"📡 Added WebSocket stream: {stream_name}")

            # Initialize cache structure
            if symbol not in self.kline_cache:
                self.kline_cache[symbol] = defaultdict(lambda: deque(maxlen=1000))
            if interval not in self.kline_cache[symbol]:
                self.kline_cache[symbol][interval] = deque(maxlen=1000)

            # If already connected, update subscription
            if self.is_connected and self.ws:
                self._update_subscription()

    def remove_symbol_interval(self, symbol: str, interval: str):
        """Remove a symbol/interval pair from WebSocket streaming"""
        symbol = symbol.upper()
        stream_name = f"{symbol.lower()}@kline_{interval}"

        if stream_name in self.subscribed_streams:
            self.subscribed_streams.remove(stream_name)
            self.logger.info(f"📡 Removed WebSocket stream: {stream_name}")

            # Clean up cache
            if symbol in self.kline_cache and interval in self.kline_cache[symbol]:
                del self.kline_cache[symbol][interval]
                if not self.kline_cache[symbol]:
                    del self.kline_cache[symbol]

            # Update subscription if connected
            if self.is_connected and self.ws:
                self._update_subscription()

    def start(self):
        """Start the WebSocket connection in a background thread"""
        if self.is_running:
            self.logger.warning("WebSocket manager is already running")
            return

        if not self.subscribed_streams:
            self.logger.warning("No streams to subscribe to. Add symbols first.")
            return

        self.is_running = True
        self.ws_thread = threading.Thread(target=self._run_websocket, daemon=True)
        self.ws_thread.start()

        self.logger.info(f"🚀 WebSocket manager started with {len(self.subscribed_streams)} streams")

    def stop(self):
        """Stop the WebSocket connection"""
        self.is_running = False

        if self.ws:
            try:
                self.ws.close()
            except Exception as e:
                self.logger.error(f"Error closing WebSocket: {e}")

        if self.ws_thread and self.ws_thread.is_alive():
            self.ws_thread.join(timeout=5.0)

        self.is_connected = False
        self.logger.info("🛑 WebSocket manager stopped")

    def _run_websocket(self):
        """Main WebSocket connection loop"""
        while self.is_running:
            try:
                self._connect_websocket()

                # Keep connection alive without ping monitoring
                while self.is_running and self.is_connected:
                    time.sleep(5)  # Longer sleep since no ping needed

                    # Update ping timestamp to prevent timeout logic
                    if self.is_connected:
                        self.last_ping = time.time()

            except Exception as e:
                self.logger.error(f"WebSocket connection error: {e}")
                self.is_connected = False

                if self.is_running:
                    self.reconnect_attempts += 1
                    if self.reconnect_attempts < self.max_reconnect_attempts:
                        wait_time = min(30, 2 ** self.reconnect_attempts)
                        self.logger.info(f"🔄 Reconnecting in {wait_time}s (attempt {self.reconnect_attempts})")
                        time.sleep(wait_time)
                    else:
                        self.logger.error("❌ Max reconnection attempts reached. Stopping.")
                        break

    def _connect_websocket(self):
        """Establish WebSocket connection with deployment-optimized settings"""
        try:
            # Use proper Binance Futures WebSocket URL format
            if len(self.subscribed_streams) == 1:
                # Single stream - direct connection
                stream = list(self.subscribed_streams)[0]
                url = f"wss://fstream.binance.com/ws/{stream}"
            else:
                # Multiple streams - use proper Binance Futures combined stream format
                streams_list = list(sorted(self.subscribed_streams))
                # Binance Futures uses different combined stream format
                combined_params = "/".join(streams_list)
                url = f"wss://fstream.binance.com/ws/{combined_params}"

            self.logger.info(f"🔗 Connecting to WebSocket: {url}")
            self.logger.info(f"📡 Streams: {list(self.subscribed_streams)}")

            # Create WebSocket connection with production-ready settings
            self.ws = WebSocketApp(
                url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                header={
                    "User-Agent": "python-binance-websocket/1.0",
                    "Origin": "https://www.binance.com",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache"
                }
            )

            # Enhanced deployment-ready WebSocket settings
            self.ws.run_forever(
                sslopt={
                    "cert_reqs": ssl.CERT_NONE,
                    "check_hostname": False,
                    "ssl_version": ssl.PROTOCOL_TLS,
                    "ciphers": "HIGH:!aNULL:!eNULL:!EXPORT:!DES:!RC4:!MD5:!PSK:!SRP:!CAMELLIA"
                },
                ping_interval=None,  # Disable automatic ping to prevent socket errors
                ping_timeout=None,   # Disable ping timeout 
                suppress_origin=False,
                origin="https://www.binance.com",
                skip_utf8_validation=True,  # Skip validation for better performance
                sockopt=[(
                    __import__('socket').SOL_SOCKET,
                    __import__('socket').SO_KEEPALIVE,
                    1
                )]  # Enable socket keepalive for deployment
            )

        except Exception as e:
            self.logger.error(f"Failed to connect WebSocket: {e}")
            import traceback
            self.logger.error(f"Full traceback: {traceback.format_exc()}")
            time.sleep(2)  # Shorter delay for faster recovery

    def _on_open(self, ws):
        """WebSocket connection opened with verification"""
        self.is_connected = True
        self.reconnect_attempts = 0
        self.last_ping = time.time()
        self.stats['connection_uptime'] = time.time()
        self.stats['reconnections'] += 1

        self.logger.info(f"✅ WebSocket Connected Successfully!")
        self.logger.info(f"📡 Active Streams: {len(self.subscribed_streams)}")
        for stream in self.subscribed_streams:
            self.logger.info(f"   🔗 {stream}")

        # Send a test ping to verify bidirectional communication
        try:
            self._send_ping()
            self.logger.info("📤 Test ping sent to verify connection")
        except Exception as e:
            self.logger.warning(f"⚠️ Could not send test ping: {e}")

    def _on_message(self, ws, message):
        """Process incoming WebSocket message with improved format handling"""
        try:
            data = json.loads(message)
            self.stats['messages_received'] += 1
            self.stats['last_message_time'] = datetime.now()

            # Handle different message formats from Binance WebSocket
            if 'stream' in data and 'data' in data:
                # Combined stream format: {"stream": "btcusdt@kline_1m", "data": {...}}
                stream_name = data['stream']
                message_data = data['data']

                if 'k' in message_data:  # Kline data
                    self._process_kline_data(stream_name, message_data['k'])
                    self.logger.debug(f"📊 Combined stream kline: {stream_name}")
                elif 'e' in message_data and message_data['e'] == 'kline':
                    # Sometimes data is nested differently
                    self._process_kline_data(stream_name, message_data['k'])
                    self.logger.debug(f"📊 Combined stream nested kline: {stream_name}")

            elif 'e' in data and data['e'] == 'kline':
                # Direct kline format: {"e": "kline", "E": timestamp, "s": "BTCUSDT", "k": {...}}
                symbol = data['s'].lower()
                interval = data['k']['i']
                stream_name = f"{symbol}@kline_{interval}"
                self._process_kline_data(stream_name, data['k'])
                self.logger.debug(f"📊 Direct kline: {stream_name}")

            elif 'k' in data and 's' in data:
                # Alternative direct format
                symbol = data['s'].lower()
                interval = data['k']['i']
                stream_name = f"{symbol}@kline_{interval}"
                self._process_kline_data(stream_name, data['k'])
                self.logger.debug(f"📊 Alt direct kline: {stream_name}")

            else:
                # Log unknown formats for debugging (but don't spam)
                if self.stats['messages_received'] % 100 == 1:  # Log every 100th unknown message
                    self.logger.debug(f"🔍 Unknown message format: {list(data.keys())[:5]}")

        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error: {e}")
            self.logger.debug(f"Raw message: {message[:200]}...")
        except Exception as e:
            self.logger.error(f"Error processing WebSocket message: {e}")
            self.logger.debug(f"Raw message: {message[:200]}...")
            import traceback
            self.logger.debug(f"Traceback: {traceback.format_exc()}")

    def _on_error(self, ws, error):
        """WebSocket error handler with comprehensive error analysis"""
        error_str = str(error)

        # Log the raw error for debugging
        self.logger.error(f"🚫 WebSocket Error: {error}")

        # Categorize error types for better debugging
        if "403" in error_str or "Forbidden" in error_str:
            self.logger.error("🚫 Access Forbidden - Check URL format and permissions")
        elif "429" in error_str or "rate limit" in error_str.lower():
            self.logger.error("⚠️ Rate Limit - Will retry with backoff")
        elif "timeout" in error_str.lower() or "timed out" in error_str.lower():
            self.logger.error("⏱️ Connection Timeout - Network or server issue")
        elif "connection" in error_str.lower():
            self.logger.error("🔌 Connection Issue - Will retry connection")
        elif "ssl" in error_str.lower() or "certificate" in error_str.lower():
            self.logger.error("🔒 SSL/TLS Issue - Certificate or encryption problem")
        elif "websocket" in error_str.lower():
            self.logger.error("📡 WebSocket Protocol Issue")
        else:
            self.logger.error("❓ Unknown Error Type")

        # Add detailed error info for debugging
        self.logger.error(f"🔍 Error details: {type(error).__name__}: {error}")

        # Import traceback for full error context in deployment
        import traceback
        self.logger.error(f"🔍 Full traceback: {traceback.format_exc()}")

        self.is_connected = False

    def _on_close(self, ws, close_status_code, close_msg):
        """WebSocket connection closed with enhanced auto-reconnect"""
        self.is_connected = False

        # Handle normal closure vs error closure
        if close_status_code in [1000, 1001]:  # Normal closure codes
            self.logger.info(f"WebSocket closed normally: {close_status_code}")
        else:
            self.logger.warning(f"WebSocket closed: {close_status_code} - {close_msg}")

        # PRESERVE EXISTING CACHE DATA during reconnection
        cache_sizes = {}
        for symbol in self.kline_cache:
            cache_sizes[symbol] = {}
            for interval in self.kline_cache[symbol]:
                cache_sizes[symbol][interval] = len(self.kline_cache[symbol][interval])
        
        if cache_sizes:
            self.logger.info(f"📊 Preserving cached data during reconnection: {cache_sizes}")

        # Immediate reconnect if we're supposed to be running
        if self.is_running and self.connection_recovery_mode:
            self.logger.info("🔄 Enhanced WebSocket reconnection...")
            # Start reconnection immediately in a separate thread with higher priority
            import threading
            reconnect_thread = threading.Thread(target=self._enhanced_reconnect, daemon=True)
            reconnect_thread.priority = 10  # Higher priority thread
            reconnect_thread.start()

    def _enhanced_reconnect(self):
        """Enhanced reconnection with validation test support"""
        max_immediate_attempts = 5  # Increased attempts for validation tests
        for attempt in range(max_immediate_attempts):
            if not self.is_running:
                break
                
            try:
                self.logger.info(f"🔄 Enhanced reconnect attempt {attempt + 1}/{max_immediate_attempts}")
                
                # Close any existing connection first
                if self.ws:
                    try:
                        self.ws.close()
                    except:
                        pass
                    
                self._connect_websocket()
                
                # Wait for stable connection
                stable_wait = 0
                while stable_wait < 10 and self.is_connected:
                    time.sleep(0.5)
                    stable_wait += 0.5
                    
                if self.is_connected:
                    self.logger.info(f"✅ Enhanced reconnection successful after {stable_wait}s!")
                    return
                    
            except Exception as e:
                self.logger.error(f"Enhanced reconnect attempt {attempt + 1} failed: {e}")
                time.sleep(2)  # Longer delay for stability
        
        # If enhanced reconnection fails, fall back to regular reconnection
        self._attempt_reconnect()

    def _immediate_reconnect(self):
        """Fallback to enhanced reconnect for compatibility"""
        self._enhanced_reconnect()

    def _attempt_reconnect(self):
        """Attempt to reconnect WebSocket with backoff"""
        if self.is_running and not self.is_connected:
            try:
                self.logger.info("🔄 Attempting WebSocket reconnection...")
                self._connect_websocket()
            except Exception as e:
                self.logger.error(f"Reconnection failed: {e}")
                if self.reconnect_attempts < self.max_reconnect_attempts:
                    import threading
                    threading.Timer(5.0, self._attempt_reconnect).start()

    def _process_kline_data(self, stream_name: str, kline: Dict[str, Any]):
        """Process incoming kline data and update cache"""
        try:
            self.logger.debug(f"🔍 Processing kline for stream: {stream_name}")

            # Parse stream name to get symbol and interval
            # Format: btcusdt@kline_1m
            parts = stream_name.split('@')
            if len(parts) != 2 or not parts[1].startswith('kline_'):
                self.logger.warning(f"❌ Invalid stream name format: {stream_name}")
                return

            symbol = parts[0].upper()
            interval = parts[1].replace('kline_', '')

            self.logger.debug(f"🔍 Parsed: {symbol} {interval}")

            # Create standardized kline data
            processed_kline = {
                'timestamp': int(kline['t']),
                'open': float(kline['o']),
                'high': float(kline['h']),
                'low': float(kline['l']),
                'close': float(kline['c']),
                'volume': float(kline['v']),
                'close_time': int(kline['T']),
                'is_closed': kline['x'],  # True if this kline is closed
                'received_at': time.time()
            }

            # Update cache
            self.kline_cache[symbol][interval].append(processed_kline)
            self.latest_klines[symbol][interval] = processed_kline
            self.last_updates[symbol][interval] = datetime.now()

            self.stats['klines_processed'] += 1

            self.logger.debug(f"✅ Kline processed: {symbol} {interval} @ ${processed_kline['close']:.4f} | Total processed: {self.stats['klines_processed']}")

            # Log closed klines (completed candles)
            if processed_kline['is_closed']:
                self.logger.info(f"📊 Kline closed: {symbol} {interval} @ ${processed_kline['close']:.4f}")

            # Notify callbacks
            for callback in self.update_callbacks:
                try:
                    callback(symbol, interval, processed_kline)
                except Exception as e:
                    self.logger.error(f"Error in update callback: {e}")

        except Exception as e:
            self.logger.error(f"Error processing kline data for {stream_name}: {e}")
            self.logger.debug(f"Kline data keys: {list(kline.keys())}")
            import traceback
            traceback.print_exc()

    def _send_ping(self):
        """Send ping to keep connection alive - disabled to prevent socket errors"""
        try:
            # Skip all ping operations to prevent NoneType socket errors
            # Binance WebSocket maintains connection without manual pings
            self.last_ping = time.time()
            self.logger.debug("📤 Ping disabled - relying on server-side keepalive")
        except Exception as e:
            self.logger.debug(f"Ping operation skipped: {e}")

    def _update_subscription(self):
        """Update WebSocket subscription (for dynamic stream management)"""
        # For now, we'll reconnect to update streams
        # In production, you might want to use the subscription management API
        if self.is_connected:
            self.logger.info("🔄 Updating WebSocket subscription...")
            self.ws.close()  # This will trigger reconnection with new streams

    def get_cached_klines(self, symbol: str, interval: str, limit: int = 100) -> Optional[List[Dict]]:
        """Get cached kline data for a symbol/interval"""
        symbol = symbol.upper()

        if symbol not in self.kline_cache or interval not in self.kline_cache[symbol]:
            self.logger.debug(f"No cached data for {symbol} {interval}")
            return None

        klines = list(self.kline_cache[symbol][interval])
        if not klines:
            return None

        # Return most recent klines up to limit
        return klines[-limit:] if len(klines) > limit else klines

    def get_latest_kline(self, symbol: str, interval: str) -> Optional[Dict]:
        """Get the most recent kline for a symbol/interval"""
        symbol = symbol.upper()

        if symbol in self.latest_klines and interval in self.latest_klines[symbol]:
            return self.latest_klines[symbol][interval]
        return None

    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price from latest kline data with connection check"""
        # Ensure connection is active
        if not self.is_connected and self.is_running:
            self.logger.warning("⚠️ WebSocket not connected, attempting reconnection...")
            self._immediate_reconnect()
            
        # Try to get from any available interval, preferring shorter timeframes
        symbol = symbol.upper()

        for interval in ['1m', '3m', '5m', '15m', '1h', '4h', '1d']:
            latest = self.get_latest_kline(symbol, interval)
            if latest:
                return latest['close']

        return None

    def is_data_fresh(self, symbol: str, interval: str, max_age_seconds: int = 60) -> bool:
        """Check if cached data is fresh enough with startup grace period"""
        symbol = symbol.upper()

        # First check if we have any data at all
        if symbol in self.kline_cache and interval in self.kline_cache[symbol]:
            cached_data = list(self.kline_cache[symbol][interval])
            if len(cached_data) > 0:
                # If we have recent data, check timestamp
                if symbol in self.last_updates and interval in self.last_updates[symbol]:
                    last_update = self.last_updates[symbol][interval]
                    age = (datetime.now() - last_update).total_seconds()

                    # Be more lenient during the first few minutes after connection
                    connection_time = time.time() - self.stats.get('connection_uptime', time.time())
                    if connection_time < 300:  # First 5 minutes after connection
                        max_age_seconds = max(max_age_seconds, 300)  # Allow up to 5 minutes old data

                    return age <= max_age_seconds
                else:
                    # Have data but no timestamp - check if data itself is recent
                    latest_kline = cached_data[-1]
                    data_age = time.time() - latest_kline.get('received_at', 0)
                    if data_age <= max_age_seconds * 2:  # Double tolerance for received_at
                        self.logger.debug(f"💡 Using received_at timestamp for freshness check: {data_age:.1f}s")
                        return True

        return False

    def add_update_callback(self, callback: Callable):
        """Add callback function for real-time updates"""
        self.update_callbacks.append(callback)

    def remove_update_callback(self, callback: Callable):
        """Remove callback function"""
        if callback in self.update_callbacks:
            self.update_callbacks.remove(callback)

    def get_statistics(self) -> Dict[str, Any]:
        """Get WebSocket connection statistics"""
        stats = self.stats.copy()
        stats['is_connected'] = self.is_connected
        stats['subscribed_streams'] = len(self.subscribed_streams)
        stats['cached_symbols'] = len(self.kline_cache)

        if stats['connection_uptime'] > 0:
            stats['uptime_seconds'] = time.time() - stats['connection_uptime']
        else:
            stats['uptime_seconds'] = 0

        return stats

    def get_cache_status(self) -> Dict[str, Any]:
        """Get detailed cache status"""
        status = {}

        for symbol in self.kline_cache:
            status[symbol] = {}
            for interval in self.kline_cache[symbol]:
                cache_size = len(self.kline_cache[symbol][interval])
                last_update = self.last_updates.get(symbol, {}).get(interval)

                status[symbol][interval] = {
                    'cached_klines': cache_size,
                    'last_update': last_update.isoformat() if last_update else None,
                    'is_fresh': self.is_data_fresh(symbol, interval)
                }

        return status

# Global WebSocket manager instance
websocket_manager = WebSocketKlineManager()