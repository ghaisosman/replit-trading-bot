import logging
import sys
import os
from datetime import datetime

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
        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
        current_time = datetime.fromtimestamp(record.created)

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
│ ⏰ {timestamp}                                      │
│                                                 │
{formatted_lines}
│                                                 │
└─────────────────────────────────────────────────┘{reset}
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

    # Suppress noisy loggers
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)

    # Test the new format
    logger = logging.getLogger(__name__)
    logger.info("📱 Telegram-style vertical logging format initialized")