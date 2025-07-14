
import logging
import sys
from datetime import datetime

class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors and simplified format"""
    
    # Color codes
    COLORS = {
        'STARTUP': '\033[95m',      # Magenta
        'SUCCESS': '\033[92m',      # Green
        'INFO': '\033[94m',         # Blue
        'WARNING': '\033[93m',      # Yellow
        'ERROR': '\033[91m',        # Red
        'MARKET': '\033[96m',       # Cyan
        'TRADE': '\033[97m',        # White
        'RESET': '\033[0m',         # Reset
        'BOLD': '\033[1m',          # Bold
    }
    
    def __init__(self):
        super().__init__()
    
    def format(self, record):
        # Simplified timestamp (YYYY-MM-DD HH:MM)
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M')
        
        # Extract just the message without module info
        message = record.getMessage()
        
        # Determine color based on message content
        color = self._get_message_color(message, record.levelname)
        
        # Create formatted message with color block
        formatted_msg = f"{color}┌─ {timestamp} ─┐{self.COLORS['RESET']}\n"
        formatted_msg += f"{color}│ {message:<50} │{self.COLORS['RESET']}\n"
        formatted_msg += f"{color}└{'─' * 54}┘{self.COLORS['RESET']}"
        
        return formatted_msg
    
    def _get_message_color(self, message, level):
        """Determine color based on message content"""
        message_lower = message.lower()
        
        if any(keyword in message_lower for keyword in ['starting', 'initialized', 'mode:', 'strategies:']):
            return self.COLORS['STARTUP']
        elif any(keyword in message_lower for keyword in ['✅', 'success', 'complete', 'connected']):
            return self.COLORS['SUCCESS']
        elif any(keyword in message_lower for keyword in ['market', 'price:', 'assessment', 'assessing']):
            return self.COLORS['MARKET']
        elif any(keyword in message_lower for keyword in ['trade', 'order', 'position']):
            return self.COLORS['TRADE']
        elif level == 'WARNING':
            return self.COLORS['WARNING']
        elif level == 'ERROR':
            return self.COLORS['ERROR']
        else:
            return self.COLORS['INFO']

class SimpleFileFormatter(logging.Formatter):
    """Simple formatter for file logging without colors"""
    
    def format(self, record):
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M')
        message = record.getMessage()
        return f"{timestamp} | {message}"

def setup_logger():
    """Setup logging configuration with colorful console output"""
    
    # Console handler with colors
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
    logger.info("🎨 Colorful logging system initialized")
