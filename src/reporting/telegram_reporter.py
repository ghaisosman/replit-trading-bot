
import requests
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime
from src.config.global_config import global_config

class TelegramReporter:
    """Handles all Telegram reporting for the bot"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.bot_token = global_config.TELEGRAM_BOT_TOKEN
        self.chat_id = global_config.TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
    
    def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        """Send a message to Telegram"""
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode
            }
            
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send Telegram message: {e}")
            return False
    
    def report_bot_startup(self):
        """Report bot startup"""
        message = """
🤖 <b>Trading Bot Started</b>
📅 Time: {}
🔄 Status: Online and monitoring markets
        """.format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        
        self.send_message(message)
    
    def report_entry_signal(self, strategy_name: str, signal_data: Dict[str, Any]):
        """Report entry signal detection"""
        message = """
📊 <b>Entry Signal Detected</b>
🎯 Strategy: {}
💰 Symbol: {}
📈 Signal: {}
💵 Entry Price: ${:.4f}
🛑 Stop Loss: ${:.4f}
🎯 Take Profit: ${:.4f}
📝 Reason: {}
        """.format(
            strategy_name,
            signal_data.get('symbol', 'N/A'),
            signal_data.get('signal_type', 'N/A'),
            signal_data.get('entry_price', 0),
            signal_data.get('stop_loss', 0),
            signal_data.get('take_profit', 0),
            signal_data.get('reason', 'N/A')
        )
        
        self.send_message(message)
    
    def report_position_opened(self, position_data: Dict[str, Any]):
        """Report position opened"""
        message = """
✅ <b>Position Opened</b>
🎯 Strategy: {}
💰 Symbol: {}
📊 Side: {}
💵 Entry Price: ${:.4f}
📏 Quantity: {}
🛑 Stop Loss: ${:.4f}
🎯 Take Profit: ${:.4f}
📅 Time: {}
        """.format(
            position_data.get('strategy_name', 'N/A'),
            position_data.get('symbol', 'N/A'),
            position_data.get('side', 'N/A'),
            position_data.get('entry_price', 0),
            position_data.get('quantity', 0),
            position_data.get('stop_loss', 0),
            position_data.get('take_profit', 0),
            position_data.get('entry_time', 'N/A')
        )
        
        self.send_message(message)
    
    def report_position_closed(self, position_data: Dict[str, Any], close_reason: str, pnl: float = 0):
        """Report position closed"""
        pnl_emoji = "💚" if pnl >= 0 else "❌"
        
        message = """
{} <b>Position Closed</b>
🎯 Strategy: {}
💰 Symbol: {}
📊 Side: {}
💵 Entry Price: ${:.4f}
📏 Quantity: {}
💰 P&L: ${:.2f}
📝 Reason: {}
📅 Time: {}
        """.format(
            pnl_emoji,
            position_data.get('strategy_name', 'N/A'),
            position_data.get('symbol', 'N/A'),
            position_data.get('side', 'N/A'),
            position_data.get('entry_price', 0),
            position_data.get('quantity', 0),
            pnl,
            close_reason,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        
        self.send_message(message)
    
    def report_error(self, error_type: str, error_message: str, strategy_name: str = None):
        """Report errors"""
        message = """
🚨 <b>Error Detected</b>
📊 Type: {}
🎯 Strategy: {}
📝 Message: {}
📅 Time: {}
        """.format(
            error_type,
            strategy_name or "System",
            error_message[:200],  # Limit message length
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        
        self.send_message(message)
    
    def report_market_assessment(self, strategy_name: str, assessment_data: Dict[str, Any]):
        """Report market assessment"""
        message = """
📊 <b>Market Assessment</b>
🎯 Strategy: {}
💰 Symbol: {}
💵 Current Price: ${:.4f}
📈 Trend: {}
🔍 Signal Strength: {}
📅 Time: {}
        """.format(
            strategy_name,
            assessment_data.get('symbol', 'N/A'),
            assessment_data.get('current_price', 0),
            assessment_data.get('trend', 'N/A'),
            assessment_data.get('signal_strength', 'N/A'),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        
        self.send_message(message)
    
    def report_balance_warning(self, required_balance: float, current_balance: float):
        """Report insufficient balance warning"""
        message = """
⚠️ <b>Insufficient Balance Warning</b>
💰 Required: ${:.2f}
💳 Available: ${:.2f}
📊 Shortfall: ${:.2f}
📅 Time: {}
        """.format(
            required_balance,
            current_balance,
            required_balance - current_balance,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        
        self.send_message(message)
