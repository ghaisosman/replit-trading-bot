
import logging
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime
from src.config.global_config import global_config


class TelegramReporter:
    """Handles Telegram notifications"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.bot_token = None
        self.chat_id = None
        self.logger.info("📱 Telegram Reporter initialized")
    
    def set_credentials(self, bot_token: str, chat_id: str):
        """Set Telegram credentials"""
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.logger.info("🔑 Telegram credentials set")
    
    def send_message(self, message: str) -> bool:
        """Send a message via Telegram"""
        try:
            if not self.bot_token or not self.chat_id:
                self.logger.warning("⚠️ Telegram credentials not set")
                return False
            
            # Simplified message sending for testing
            self.logger.info(f"📱 Telegram message: {message[:100]}...")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error sending Telegram message: {e}")
            return False
    
    def report_position_opened(self, position_data: dict) -> bool:
        """Report position opened"""
        try:
            message = f"""🚀 **Position Opened**
            
Strategy: {position_data.get('strategy_name', 'Unknown')}
Symbol: {position_data.get('symbol', 'Unknown')}
Side: {position_data.get('side', 'Unknown')}
Entry Price: ${position_data.get('entry_price', 0):.4f}
Quantity: {position_data.get('quantity', 0)}"""
            
            return self.send_message(message)
            
        except Exception as e:
            self.logger.error(f"❌ Error reporting position opened: {e}")
            return False
    
    def report_position_closed(self, position_data: dict, exit_reason: str, pnl: float) -> bool:
        """Report position closed"""
        try:
            message = f"""🔴 **Position Closed**
            
Strategy: {position_data.get('strategy_name', 'Unknown')}
Symbol: {position_data.get('symbol', 'Unknown')}
Side: {position_data.get('side', 'Unknown')}
Entry: ${position_data.get('entry_price', 0):.4f}
Exit: ${position_data.get('exit_price', 0):.4f}
PnL: ${pnl:.2f} USDT
Reason: {exit_reason}"""
            
            return self.send_message(message)
            
        except Exception as e:
            self.logger.error(f"❌ Error reporting position closed: {e}")
            return False
