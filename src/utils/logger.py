
import logging
import sys
from datetime import datetime

class ColoredFormatter(logging.Formatter):
    """Colorful formatter with block separators for console logging"""

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

    def __init__(self):
        super().__init__()
        self.last_log_time = None

    def format(self, record):
        # Format timestamp without seconds and milliseconds
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M')
        current_time = datetime.fromtimestamp(record.created)

        # Get message
        message = record.getMessage()

        # Get colors
        text_color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        bg_color = self.BACKGROUND_COLORS.get(record.levelname, self.BACKGROUND_COLORS['RESET'])
        reset = self.COLORS['RESET']

        # Add separator line if this is a new time block (different minute)
        separator = ""
        if self.last_log_time is None or current_time.minute != self.last_log_time.minute:
            separator = f"\n{text_color}{'─' * 80}{reset}\n"
        
        self.last_log_time = current_time

        # Create different block styles for each log level
        if record.levelname == 'INFO':
            block_start = f"{text_color}┌─"
            block_end = f"─┐{reset}"
            block_body = f"{text_color}│ {bg_color} INFO {reset} {text_color}[{timestamp}] {message} │{reset}"
            block_bottom = f"{text_color}└{'─' * (len(f'[{timestamp}] {message}') + 8)}┘{reset}"
        elif record.levelname == 'ERROR':
            block_start = f"{text_color}╔═"
            block_end = f"═╗{reset}"
            block_body = f"{text_color}║ {bg_color} ERROR {reset} {text_color}[{timestamp}] {message} ║{reset}"
            block_bottom = f"{text_color}╚{'═' * (len(f'[{timestamp}] {message}') + 9)}╝{reset}"
        elif record.levelname == 'WARNING':
            block_start = f"{text_color}╭─"
            block_end = f"─╮{reset}"
            block_body = f"{text_color}│ {bg_color} WARN {reset} {text_color}[{timestamp}] {message} │{reset}"
            block_bottom = f"{text_color}╰{'─' * (len(f'[{timestamp}] {message}') + 8)}╯{reset}"
        else:
            # DEBUG, CRITICAL, etc.
            block_start = f"{text_color}┏━"
            block_end = f"━┓{reset}"
            level_short = record.levelname[:5]
            block_body = f"{text_color}┃ {bg_color} {level_short} {reset} {text_color}[{timestamp}] {message} ┃{reset}"
            block_bottom = f"{text_color}┗{'━' * (len(f'[{timestamp}] {message}') + len(level_short) + 4)}┛{reset}"

        # Calculate the width for the top and bottom borders
        content_width = len(f'[{timestamp}] {message}') + 10
        
        # Format the complete message with visual block
        formatted_message = (
            f"{separator}"
            f"{block_start}{'─' * (content_width - 2)}{block_end}\n"
            f"{block_body}\n"
            f"{block_bottom}\n"
        )
        
        return formatted_message

class SimpleFileFormatter(logging.Formatter):
    """Simple formatter for file logging without colors"""

    def format(self, record):
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M')
        message = record.getMessage()
        return f"[{timestamp}] [{record.levelname}] {message}"

def setup_logger():
    """Setup logging configuration with colorful block console output"""

    # Console handler with colored blocks
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ColoredFormatter())
    console_handler.setLevel(logging.INFO)

    # File handler with simple format
    file_handler = logging.FileHandler('trading_bot.log')
    file_handler.setFormatter(SimpleFileFormatter())
    file_handler.setLevel(logging.DEBUG)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Clear existing handlers
    root_logger.handlers.clear()

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Suppress noisy loggers
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)

    # Test the new format
    logger = logging.getLogger(__name__)
    logger.info("🎨 Enhanced block logging format initialized")
