
import asyncio
import json
import logging
import threading
import time
import websocket
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
        self.ping_interval = 30  # seconds
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        
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
                
                # Keep connection alive
                while self.is_running and self.is_connected:
                    time.sleep(1)
                    
                    # Send ping if needed
                    current_time = time.time()
                    if current_time - self.last_ping > self.ping_interval:
                        self._send_ping()
                        
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
        """Establish WebSocket connection"""
        try:
            # Create combined stream URL - Binance supports combined streams
            if len(self.subscribed_streams) == 1:
                # Single stream
                stream = list(self.subscribed_streams)[0]
                url = f"wss://fstream.binance.com/ws/{stream}"
            else:
                # Multiple streams combined
                streams = "/".join(sorted(self.subscribed_streams))  # Sort for consistency
                url = f"wss://fstream.binance.com/ws/{streams}"
            
            self.logger.info(f"🔗 Connecting to WebSocket: {url}")
            
            # Create WebSocket connection
            self.ws = websocket.WebSocketApp(
                url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            
            # Run WebSocket with SSL context
            self.ws.run_forever(
                sslopt={"cert_reqs": ssl.CERT_NONE},
                ping_interval=self.ping_interval,
                ping_timeout=10
            )
            
        except Exception as e:
            self.logger.error(f"Failed to connect WebSocket: {e}")
            raise
            
    def _on_open(self, ws):
        """WebSocket connection opened"""
        self.is_connected = True
        self.reconnect_attempts = 0
        self.last_ping = time.time()
        self.stats['connection_uptime'] = time.time()
        self.stats['reconnections'] += 1
        
        self.logger.info(f"✅ WebSocket connected with {len(self.subscribed_streams)} streams")
        for stream in self.subscribed_streams:
            self.logger.info(f"   📡 {stream}")
            
    def _on_message(self, ws, message):
        """Process incoming WebSocket message"""
        try:
            data = json.loads(message)
            self.stats['messages_received'] += 1
            self.stats['last_message_time'] = datetime.now()
            
            # Handle stream data - check multiple possible formats
            if 'stream' in data and 'data' in data:
                # Combined stream format: {"stream": "btcusdt@kline_1m", "data": {...}}
                stream_name = data['stream']
                kline_data = data['data']
                
                if 'k' in kline_data:  # Kline data
                    self._process_kline_data(stream_name, kline_data['k'])
                    self.logger.debug(f"📊 Processed kline from combined stream: {stream_name}")
                    
            elif 'k' in data:
                # Direct kline format: {"e": "kline", "E": timestamp, "s": "BTCUSDT", "k": {...}}
                if 'e' in data and data['e'] == 'kline':
                    symbol = data['s'].lower()
                    # Extract interval from kline data
                    interval = data['k']['i']
                    stream_name = f"{symbol}@kline_{interval}"
                    self._process_kline_data(stream_name, data['k'])
                    self.logger.debug(f"📊 Processed kline from direct format: {stream_name}")
                    
            else:
                # Log unrecognized message format for debugging
                self.logger.debug(f"🔍 Unrecognized message format: {list(data.keys())}")
                
        except Exception as e:
            self.logger.error(f"Error processing WebSocket message: {e}")
            self.logger.debug(f"Raw message: {message[:200]}...")  # First 200 chars for debugging
            
    def _on_error(self, ws, error):
        """WebSocket error handler"""
        self.logger.error(f"WebSocket error: {error}")
        self.is_connected = False
        
    def _on_close(self, ws, close_status_code, close_msg):
        """WebSocket connection closed"""
        self.is_connected = False
        self.logger.warning(f"WebSocket closed: {close_status_code} - {close_msg}")
        
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
        """Send ping to keep connection alive"""
        try:
            if self.ws and self.is_connected:
                self.ws.send('{"method": "ping"}')
                self.last_ping = time.time()
        except Exception as e:
            self.logger.error(f"Error sending ping: {e}")
            
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
        """Get current price from latest kline data"""
        # Try to get from any available interval, preferring shorter timeframes
        symbol = symbol.upper()
        
        for interval in ['1m', '3m', '5m', '15m', '1h', '4h', '1d']:
            latest = self.get_latest_kline(symbol, interval)
            if latest:
                return latest['close']
                
        return None
        
    def is_data_fresh(self, symbol: str, interval: str, max_age_seconds: int = 60) -> bool:
        """Check if cached data is fresh enough"""
        symbol = symbol.upper()
        
        if symbol not in self.last_updates or interval not in self.last_updates[symbol]:
            return False
            
        last_update = self.last_updates[symbol][interval]
        age = (datetime.now() - last_update).total_seconds()
        return age <= max_age_seconds
        
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
