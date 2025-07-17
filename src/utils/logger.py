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

    # Strategy-specific colors
    STRATEGY_COLORS = {
        'RSI_OVERSOLD': '\033[95m',      # Purple/Magenta
        'SMA_CROSSOVER': '\033[93m',     # Yellow
        'rsi_oversold': '\033[95m',      # Purple/Magenta
        'sma_crossover': '\033[93m',     # Yellow
    }

    # Active position colors (brighter/bold versions)
    ACTIVE_POSITION_COLORS = {
        'RSI_OVERSOLD': '\033[1;95m',    # Bold Purple/Magenta
        'SMA_CROSSOVER': '\033[1;93m',   # Bold Yellow
        'rsi_oversold': '\033[1;95m',    # Bold Purple/Magenta
        'sma_crossover': '\033[1;93m',   # Bold Yellow
    }

    def __init__(self):
        super().__init__()
        self.last_log_time = None

    def format(self, record):
        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
        current_time = datetime.fromtimestamp(record.created)

        # Get message
        message = record.getMessage()

        # Detect strategy and position status from message
        strategy_color = None
        is_active_position = False

        # Check for strategy mentions and active positions
        for strategy_name in self.STRATEGY_COLORS.keys():
            if strategy_name.upper() in message.upper():
                if "TRADE IN PROGRESS" in message:
                    strategy_color = self.ACTIVE_POSITION_COLORS.get(strategy_name)
                    is_active_position = True
                elif any(keyword in message for keyword in ["MARKET ASSESSMENT", "ENTRY SIGNAL", "POSITION OPENED", "POSITION CLOSED", "SCANNING"]):
                    strategy_color = self.STRATEGY_COLORS.get(strategy_name)
                break

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
            # Active position display with clean formatting to prevent nesting
            formatted_message = f"""{separator}{text_color}┌─────────────────────────────────────────────────┐
│ 📊 ACTIVE POSITION                                │
│ ⏰ {timestamp}                                        │
│                                                   │
│ {message}                                         │
│                                                   │
└─────────────────────────────────────────────────┘{reset}
"""
        elif "TRADE IN PROGRESS" in message:
            # Trade in progress - simplified formatting to prevent nesting
            formatted_message = f"""{separator}{text_color}┌─────────────────────────────────────────────────┐
│ 📊 TRADE IN PROGRESS                             │
│ ⏰ {timestamp}                                        │
│                                                   │
│ {message}                                         │
│                                                   │
└─────────────────────────────────────────────────┘{reset}
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