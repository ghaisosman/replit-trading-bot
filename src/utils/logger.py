"""
Logging utilities for the trading bot
"""

import logging
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
from collections import deque
import threading

class ColoredFormatter(logging.Formatter):
    """Colorful formatter with Telegram-style vertical layout"""

    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green  
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
        'RESET': '\033[0m'      # Reset
    }

    BACKGROUND_COLORS = {
        'DEBUG': '\033[46m',    # Cyan background
        'INFO': '\033[42m',     # Green background
        'WARNING': '\033[43m',  # Yellow background
        'ERROR': '\033[41m',    # Red background
        'CRITICAL': '\033[45m', # Magenta background
        'RESET': '\033[0m'      # Reset
    }

    # Extended color palette for strategies
    AVAILABLE_STRATEGY_COLORS = [
        '\033[95m',   # Purple/Magenta
        '\033[93m',   # Yellow
        '\033[96m',   # Cyan
        '\033[91m',   # Light Red
        '\033[92m',   # Light Green
        '\033[94m',   # Light Blue
        '\033[97m',   # White
        '\033[90m',   # Dark Gray
        '\033[35m',   # Magenta
        '\033[36m',   # Dark Cyan
        '\033[33m',   # Dark Yellow
        '\033[31m',   # Dark Red
        '\033[32m',   # Dark Green
        '\033[34m',   # Dark Blue
        '\033[37m',   # Light Gray
        '\033[1;35m', # Bold Magenta
        '\033[1;36m', # Bold Cyan
        '\033[1;33m', # Bold Yellow
        '\033[1;31m', # Bold Red
        '\033[1;32m', # Bold Green
        '\033[1;34m', # Bold Blue
        '\033[1;37m', # Bold White
    ]

    # Dynamic strategy color assignment
    STRATEGY_COLORS = {}
    ACTIVE_POSITION_COLORS = {}

    @classmethod
    def _load_strategy_colors(cls):
        """Load strategy colors from persistent storage"""
        import os
        import json

        color_file = 'trading_data/strategy_colors.json'

        # Ensure trading_data directory exists
        os.makedirs('trading_data', exist_ok=True)

        if os.path.exists(color_file):
            try:
                with open(color_file, 'r') as f:
                    data = json.load(f)
                    cls.STRATEGY_COLORS = data.get('strategy_colors', {})
                    cls.ACTIVE_POSITION_COLORS = data.get('active_position_colors', {})
            except Exception:
                # If file is corrupted, start fresh
                cls.STRATEGY_COLORS = {}
                cls.ACTIVE_POSITION_COLORS = {}

    @classmethod
    def _save_strategy_colors(cls):
        """Save strategy colors to persistent storage"""
        import os
        import json

        color_file = 'trading_data/strategy_colors.json'

        # Ensure trading_data directory exists
        os.makedirs('trading_data', exist_ok=True)

        data = {
            'strategy_colors': cls.STRATEGY_COLORS,
            'active_position_colors': cls.ACTIVE_POSITION_COLORS
        }

        try:
            with open(color_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass  # Fail silently to not break logging

    @classmethod
    def _assign_strategy_color(cls, strategy_name):
        """Assign a unique color to a strategy"""
        # Normalize strategy name for consistent lookup
        normalized_name = strategy_name.upper()

        # If already assigned, return existing color
        if normalized_name in cls.STRATEGY_COLORS:
            return cls.STRATEGY_COLORS[normalized_name]

        # Find next available color
        used_colors = set(cls.STRATEGY_COLORS.values())
        available_colors = [color for color in cls.AVAILABLE_STRATEGY_COLORS if color not in used_colors]

        if not available_colors:
            # If all colors are used, cycle back to the beginning
            available_colors = cls.AVAILABLE_STRATEGY_COLORS

        # Assign the first available color
        selected_color = available_colors[0]
        cls.STRATEGY_COLORS[normalized_name] = selected_color

        # Create bold version for active positions
        if selected_color.startswith('\033[1;'):
            # Already bold, use as is
            cls.ACTIVE_POSITION_COLORS[normalized_name] = selected_color
        else:
            # Make bold version
            color_code = selected_color.replace('\033[', '\033[1;')
            cls.ACTIVE_POSITION_COLORS[normalized_name] = color_code

        # Save the updated colors
        cls._save_strategy_colors()

        return selected_color

    def __init__(self):
        super().__init__()
        self.last_log_time = None
        # Load existing strategy colors on initialization
        self._load_strategy_colors()

    def format(self, record):
        # Format timestamp in Dubai time (UTC+4)
        from src.config.global_config import global_config
        utc_time = datetime.fromtimestamp(record.created)
        if global_config.USE_LOCAL_TIMEZONE:
            local_time = utc_time + timedelta(hours=global_config.TIMEZONE_OFFSET_HOURS)
            timestamp = local_time.strftime('%H:%M:%S')
            current_time = local_time
        else:
            timestamp = utc_time.strftime('%H:%M:%S')
            current_time = utc_time

        # Get message
        message = record.getMessage()

        # Detect strategy and position status from message
        strategy_color = None
        is_active_position = False
        detected_strategy = None

        # Extract strategy name from common message patterns
        import re

        # Pattern 1: "STRATEGY_NAME | SYMBOL" or "Strategy: STRATEGY_NAME"
        strategy_patterns = [
            r'🎯\s*(?:Strategy:\s*)?([A-Z_]+)',
            r'([A-Z_]+)\s*\|',
            r'SCANNING\s+[A-Z]+\s*\|\s*([A-Z_]+)',
            r'POSITION\s+(?:OPENED|CLOSED)\s*\|\s*([A-Z_]+)',
            r'SIGNAL\s+(?:DETECTED|TRIGGERED)\s*\|\s*([A-Z_]+)',
            r'EXIT\s+TRIGGERED\s*\|\s*([A-Z_]+)',
            r'STRATEGY\s+BLOCKED\s*\|\s*([A-Z_]+)',
        ]

        for pattern in strategy_patterns:
            match = re.search(pattern, message)
            if match:
                detected_strategy = match.group(1).upper()
                break

        # If we detected a strategy, assign color if needed
        if detected_strategy:
            # Assign color dynamically if not already assigned
            strategy_color = self._assign_strategy_color(detected_strategy)

            # Check if this is an active position
            if "TRADE IN PROGRESS" in message or "ACTIVE POSITION" in message:
                strategy_color = self.ACTIVE_POSITION_COLORS.get(detected_strategy, strategy_color)
                is_active_position = True
            elif any(keyword in message for keyword in ["MARKET ASSESSMENT", "ENTRY SIGNAL", "POSITION OPENED", "POSITION CLOSED", "SCANNING", "EXIT TRIGGERED", "STRATEGY BLOCKED"]):
                strategy_color = self.STRATEGY_COLORS.get(detected_strategy, strategy_color)

        # Get colors
        if strategy_color:
            text_color = strategy_color
        else:
            text_color = self.COLORS.get(record.levelname, self.COLORS['RESET'])

        reset = self.COLORS['RESET']

        # Add time separator if new minute
        separator = ""
        if self.last_log_time is None or current_time.minute != self.last_log_time.minute:
            separator = f"\n{text_color}{'─' * 60}{reset}\n"

        self.last_log_time = current_time

        # Parse structured messages for better formatting
        def format_structured_message(msg):
            """Format structured messages with each component on separate lines"""
            lines = []

            # Handle different message types
            if "TRADE IN PROGRESS" in msg:
                parts = msg.split(" | ")
                if len(parts) >= 5:
                    lines.append("📊 TRADE IN PROGRESS")
                    lines.append(f"🎯 Strategy: {parts[1]}")
                    lines.append(f"💱 Symbol: {parts[2]}")
                    lines.append(f"💵 {parts[3]}")
                    lines.append(f"📊 {parts[4]}")
                else:
                    lines.append(msg)
            elif "MARKET ASSESSMENT" in msg:
                # Handle market assessment messages - group related info
                if " | " in msg:
                    parts = msg.split(" | ")
                    if len(parts) >= 6:
                        lines.append("📈 MARKET ASSESSMENT")
                        lines.append(f"🎯 Strategy: {parts[1]}")
                        lines.append(f"💱 Symbol: {parts[2]}")
                        lines.append(f"💵 {parts[3]}")
                        lines.append(f"📊 {parts[4]}")
                        lines.append(f"📈 {parts[5]}")
                    elif len(parts) >= 4:
                        lines.append("📈 MARKET ASSESSMENT")
                        lines.append(f"🎯 Strategy: {parts[1]}")
                        lines.append(f"💱 Symbol: {parts[2]}")
                        lines.append(f"💵 {parts[3]}")
                        if len(parts) > 4:
                            lines.append(f"📊 {parts[4]}")
                    else:
                        lines.append("📈 MARKET ASSESSMENT")
                        for part in parts[1:]:  # Skip first part which is "MARKET ASSESSMENT"
                            if part.strip():
                                lines.append(f"📊 {part.strip()}")
                else:
                    lines.append(msg)
            elif "POSITION OPENED" in msg:
                parts = msg.split(" | ")
                if len(parts) >= 8:
                    lines.append("🟢 POSITION OPENED")
                    lines.append(f"🎯 Strategy: {parts[1]}")
                    lines.append(f"💱 Symbol: {parts[2]}")
                    lines.append(f"📊 Side: {parts[3]}")
                    lines.append(f"📈 {parts[4]}")
                    lines.append(f"📦 {parts[5]}")
                    lines.append(f"🛡️ {parts[6]}")
                    lines.append(f"🎯 {parts[7]}")
                else:
                    lines.append(msg)
            elif "POSITION CLOSED" in msg:
                parts = msg.split(" | ")
                if len(parts) >= 6:
                    lines.append("🔴 POSITION CLOSED")
                    lines.append(f"🎯 Strategy: {parts[1]}")
                    lines.append(f"💱 Symbol: {parts[2]}")
                    lines.append(f"💰 {parts[3]}")
                    lines.append(f"📊 {parts[4]}")
                    lines.append(f"⏱️ {parts[5]}")
                else:
                    lines.append(msg)
            elif "SCANNING" in msg:
                # Format SCANNING messages vertically
                parts = msg.split(" | ")
                if len(parts) >= 5:
                    lines.append("🔍 SCANNING")
                    lines.append(f"💱 Symbol: {parts[0].split()[-1]}")
                    lines.append(f"🎯 Strategy: {parts[1]}")
                    lines.append(f"⏱️ Timeframe: {parts[2]}")
                    lines.append(f"💵 {parts[3]}")
                    lines.append(f"⚡ {parts[4]}")
                else:
                    lines.append(msg)
            elif "WEB INTERFACE:" in msg:
                # Handle WEB INTERFACE messages with vertical formatting
                if "Updated" in msg and "config in shared bot:" in msg:
                    # Extract strategy name and config details
                    parts = msg.split("Updated ")
                    if len(parts) > 1:
                        strategy_part = parts[1].split(" config in shared bot: ")
                        if len(strategy_part) == 2:
                            strategy_name = strategy_part[0]
                            config_str = strategy_part[1]

                            lines.append("📝 WEB INTERFACE:")
                            lines.append(f"Updated {strategy_name}")
                            lines.append("config in shared bot:")

                            # Parse the config dictionary string
                            try:
                                # Remove outer braces and split by commas
                                config_clean = config_str.strip("{}")
                                config_items = [item.strip() for item in config_clean.split(",")]
                                for item in config_items:
                                    if ":" in item:
                                        key, value = item.split(":", 1)
                                        key = key.strip().strip("'\"")
                                        value = value.strip().strip("'\"")
                                        lines.append(f"{key}: {value}")
                            except:
                                # Fallback if parsing fails
                                lines.append(config_str)
                        else:
                            lines.append(msg)
                    else:
                        lines.append(msg)
                else:
                    lines.append(msg)
            else:
                lines.append(msg)

            return lines

        # Create Telegram-style vertical message
        if is_active_position:
            # Active position - special formatting
            msg_lines = format_structured_message(message)
            formatted_lines = "║\n".join([f"║ {line}" for line in msg_lines])
            formatted_message = f"""{separator}{text_color}╔═══════════════════════════════════════════════════╗
║ 📊 ACTIVE POSITION                                ║
║ ⏰ {timestamp}                                        ║
║                                                   ║
{formatted_lines}
║                                                   ║
╚═══════════════════════════════════════════════════╝{reset}
"""
        elif "MARKET ASSESSMENT" in message:
            # Check if this is the start of a consolidated market assessment
            if message.strip() == "📈 MARKET ASSESSMENT":
                # This is the start of a market assessment block - start collecting
                formatted_message = f"{separator}{text_color}┌─────────────────────────────────────────────────┐\n│ 📈 MARKET ASSESSMENT                           │\n│ ⏰ {timestamp}                                      │\n│                                                 │\n│ {message}                                       │{reset}\n"
            elif any(keyword in message for keyword in ["Interval", "Symbol:", "🎯", "💵 Price:", "📈 MACD:", "📈 RSI:", "🔍 SCANNING"]):
                # This is part of a market assessment - continue the block
                formatted_message = f"{text_color}│ {message}                                       │{reset}\n"
                # If this is the last line (SCANNING FOR ENTRY), close the block
                if "🔍 SCANNING FOR ENTRY" in message:
                    formatted_message += f"{text_color}│                                                 │\n└─────────────────────────────────────────────────┘{reset}\n"
            else:
                # Fallback for other market assessment formats
                msg_lines = format_structured_message(message)
                formatted_lines = "│\n".join([f"│ {line}" for line in msg_lines])
                formatted_message = f"""{separator}{text_color}┌─────────────────────────────────────────────────┐
│ 📈 MARKET ASSESSMENT                           │
│ ⏰ {timestamp}                                      │\n│                                                 │\n{formatted_lines}\n│                                                 │\n└─────────────────────────────────────────────────┘{reset}
"""
        elif "TRADE ENTRY" in message or "POSITION OPENED" in message:
            # Trade entry - highlighted
            msg_lines = format_structured_message(message)
            formatted_lines = "║\n".join([f"║ {line}" for line in msg_lines])
            formatted_message = f"""{separator}{text_color}╔═══════════════════════════════════════════════════╗
║ 🟢 TRADE ENTRY                                   ║
║ ⏰ {timestamp}                                        ║
║                                                   ║
{formatted_lines}
║                                                   ║
╚═══════════════════════════════════════════════════╝{reset}
"""
        elif "TRADE CLOSED" in message or "POSITION CLOSED" in message:
            # Trade closed - highlighted
            msg_lines = format_structured_message(message)
            formatted_lines = "║\n".join([f"║ {line}" for line in msg_lines])
            formatted_message = f"""{separator}{text_color}╔═══════════════════════════════════════════════════╗
║ 🔴 TRADE CLOSED                                  ║
║ ⏰ {timestamp}                                        ║
║                                                   ║
{formatted_lines}
║                                                   ║
╚═══════════════════════════════════════════════════╝{reset}
"""
        elif record.levelname == 'ERROR':
            # Error - double border
            msg_lines = [message]
            formatted_lines = "║\n".join([f"║ {line}" for line in msg_lines])
            formatted_message = f"""{separator}{text_color}╔═══════════════════════════════════════════════════╗
║ ❌ ERROR                                         ║
║ ⏰ {timestamp}                                        ║
║                                                   ║
{formatted_lines}
║                                                   ║
╚═══════════════════════════════════════════════════╝{reset}
"""
        elif record.levelname == 'WARNING':
            # Warning - rounded border
            msg_lines = [message]
            formatted_lines = "│\n".join([f"│ {line}" for line in msg_lines])
            formatted_message = f"""{separator}{text_color}╭─────────────────────────────────────────────────╮
│ ⚠️  WARNING                                       │
│ ⏰ {timestamp}                                      │
│                                                 │
{formatted_lines}
│                                                 │
╰─────────────────────────────────────────────────╯{reset}
"""
        else:
            # Regular info - simple border
            msg_lines = [message]
            formatted_lines = "│\n".join([f"│ {line}" for line in msg_lines])
            formatted_message = f"""{separator}{text_color}┌─────────────────────────────────────────────────┐
│ ℹ️  INFO                                          │
│ ⏰ {timestamp}                                      │
│                                                 │
{formatted_lines}
│                                                 │
└─────────────────────────────────────────────────┘{reset}
"""

        return formatted_message

class SimpleFileFormatter(logging.Formatter):
    """Simple formatter for file logging without colors"""

    def format(self, record):
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        message = record.getMessage()
        return f"[{timestamp}] [{record.levelname}] {message}"

def setup_logger():
    """Setup logging configuration with Telegram-style vertical output"""

    # Console handler with Telegram-style blocks
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ColoredFormatter())
    console_handler.setLevel(logging.INFO)

    # File handler with simple format - ensure directory exists
    os.makedirs('trading_data', exist_ok=True)
    file_handler = logging.FileHandler('trading_bot.log')
    file_handler.setFormatter(SimpleFileFormatter())
    file_handler.setLevel(logging.DEBUG)

    # Also create a copy in trading_data for web interface
    file_handler_web = logging.FileHandler('trading_data/bot.log')
    file_handler_web.setFormatter(SimpleFileFormatter())
    file_handler_web.setLevel(logging.INFO)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Clear existing handlers
    root_logger.handlers.clear()

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(file_handler_web)


    # Add web log handler - capture DEBUG level to mirror development console
    web_log_handler = WebLogHandler()
    web_log_handler.setFormatter(ColoredFormatter())
    web_log_handler.setLevel(logging.DEBUG)  # Changed from INFO to DEBUG to capture all messages
    root_logger.addHandler(web_log_handler)



    # Suppress noisy loggers
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    print(">>> [logger.py] Step 22")
    logging.getLogger('requests').setLevel(logging.WARNING)
    print(">>> [logger.py] Step 23")

    # Test the new format
    logger = logging.getLogger(__name__)
    print(">>> [logger.py] Step 24")
    logger.info("📱 Telegram-style vertical logging format initialized")
    print(">>> [logger.py] Step 25")

    # Force flush to ensure logs are written immediately
    for handler in logger.handlers:
        print(">>> [logger.py] Step 26")
        handler.flush()
        print(">>> [logger.py] Step 27")


class WebLogHandler(logging.Handler):
    """Log handler that stores recent logs in memory for web dashboard"""

    def __init__(self, max_logs=100):
        super().__init__()
        self.max_logs = max_logs
        self.logs = deque(maxlen=max_logs)
        self.lock = threading.RLock()  # Use reentrant lock

    def emit(self, record):
        try:
            with self.lock:
                if not record or not hasattr(record, 'created'):
                    return

                # Get the original message for processing
                original_msg = record.getMessage()
                timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')

                # Capture ALL messages - no filtering to mirror development console exactly
                if original_msg and original_msg.strip():
                    # Preserve the original message format as much as possible
                    clean_msg = str(original_msg).strip()
                    
                    # Only remove specific box drawing characters that break web display
                    # but preserve structure and content
                    box_chars_to_remove = ['┌', '┐', '└', '┘', '├', '┤', '─', '╔', '╗', '╚', '╝', '═']
                    for char in box_chars_to_remove:
                        clean_msg = clean_msg.replace(char, '')
                    
                    # Replace vertical bars with spaces but preserve structure
                    clean_msg = clean_msg.replace('│', ' ')
                    clean_msg = clean_msg.replace('║', ' ')
                    
                    # Clean up excessive whitespace but preserve intentional spacing
                    lines = clean_msg.split('\n')
                    cleaned_lines = []
                    for line in lines:
                        stripped_line = line.strip()
                        if stripped_line and stripped_line not in ['ℹ️  INFO', 'INFO', 'ERROR', 'WARNING', '']:
                            cleaned_lines.append(stripped_line)
                    
                    if cleaned_lines:
                        # Join multiple lines with proper separation
                        if len(cleaned_lines) == 1:
                            formatted_log = f'[{timestamp}] {cleaned_lines[0]}'
                        else:
                            # Multi-line message - preserve structure
                            main_line = cleaned_lines[0]
                            additional_info = ' | '.join(cleaned_lines[1:]) if len(cleaned_lines) > 1 else ''
                            if additional_info:
                                formatted_log = f'[{timestamp}] {main_line} | {additional_info}'
                            else:
                                formatted_log = f'[{timestamp}] {main_line}'
                        
                        self.logs.append(formatted_log)
        except Exception:
            # DO NOT log here! Just pass
            pass

    def get_recent_logs(self, count=50):
        try:
            with self.lock:
                if not self.logs:
                    return [f'[{datetime.now().strftime("%H:%M:%S")}] [INFO] Bot is starting up...']
                count = max(1, min(count, len(self.logs)))
                recent_logs = list(self.logs)[-count:] if len(self.logs) > count else list(self.logs)
                validated_logs = []
                for log in recent_logs:
                    if isinstance(log, str) and len(log.strip()) > 0:
                        validated_logs.append(log.strip())
                return validated_logs if validated_logs else [f'[{datetime.now().strftime("%H:%M:%S")}] [INFO] Logs initializing...']
        except Exception:
            return [f'[{datetime.now().strftime("%H:%M:%S")}] [ERROR] Could not retrieve logs.']

    def _categorize_message(self, message: str, level: str) -> str:
        """Categorize log message for dashboard display styling"""
        try:
            message_lower = message.lower()

            # Error messages
            if level == 'ERROR' or '❌' in message or 'error' in message_lower or 'failed' in message_lower:
                return 'log-error'

            # Warning messages
            if level == 'WARNING' or '⚠️' in message or 'warning' in message_lower:
                return 'log-warning'

            # Success messages
            if '✅' in message or 'success' in message_lower or 'completed' in message_lower:
                return 'log-success'

            # Trade-related messages
            if any(keyword in message_lower for keyword in ['position', 'trade', 'entry', 'exit', 'pnl', 'signal']):
                return 'log-trade'

            # Strategy messages - ENHANCED to catch all scanning activities
            if any(keyword in message_lower for keyword in [
                'strategy', 'rsi', 'macd', 'scanning', 'assessment', 
                'market assessment', 'interval:', 'symbol:', 'margin:', 'leverage:',
                'scanning for entry', 'btcusdt', 'ethusdt', 'solusdt'
            ]):
                return 'log-strategy'

            # Info messages
            if level == 'INFO' or 'ℹ️' in message or '🔍' in message:
                return 'log-info'

            # Default
            return 'log-default'

        except Exception:
            return 'log-default'