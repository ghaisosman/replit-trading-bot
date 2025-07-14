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

    def report_bot_startup(self, pairs: list, strategies: list, balance: float, open_trades: int):
        """1. Bot starting message"""
        message = f"""
🟢 <b>BOT STARTED</b>
⏰ <b>Time:</b> {datetime.now().strftime("%Y-%m-%d %H:%M")}
🔋 <b>Bot Health:</b> Online
📊 <b>Pairs Watching:</b> {', '.join(pairs)}
🎯 <b>Strategy Names:</b> {', '.join(strategies)}
💰 <b>Available Balance:</b> ${balance:.2f} USDT
📈 <b>Currently Open Trades:</b> {open_trades}
        """
        self.send_message(message)

    def report_trade_entry(self, strategy_name: str, pair: str, direction: str, entry_price: float, 
                          margin: float, leverage: int, balance_after: float, open_trades: int):
        """2. Trade Entry"""
        message = f"""
🟢 <b>TRADE ENTRY</b>
⏰ <b>Time:</b> {datetime.now().strftime("%Y-%m-%d %H:%M")}
🎯 <b>Strategy Name:</b> {strategy_name}
💰 <b>Pair:</b> {pair}
📊 <b>Direction:</b> {direction}
💵 <b>Entry Price:</b> ${entry_price:.4f}
💸 <b>Margin:</b> ${margin:.2f} USDT
⚡ <b>Leverage:</b> {leverage}x
💰 <b>Current Balance:</b> ${balance_after:.2f} USDT
📈 <b>Current Open Trades:</b> {open_trades}
        """
        self.send_message(message)

    def report_trade_closing(self, strategy_name: str, pair: str, direction: str, entry_price: float,
                           exit_price: float, margin: float, pnl_usdt: float, pnl_percent: float,
                           exit_reason: str, balance_after: float, open_trades: int):
        """3. Trade Closing"""
        pnl_emoji = "🟢" if pnl_usdt >= 0 else "🔴"

        message = f"""
{pnl_emoji} <b>TRADE CLOSED</b>
⏰ <b>Time:</b> {datetime.now().strftime("%Y-%m-%d %H:%M")}
🎯 <b>Strategy Name:</b> {strategy_name}
💰 <b>Pair:</b> {pair}
📊 <b>Direction:</b> {direction}
💵 <b>Entry Price:</b> ${entry_price:.4f}
🚪 <b>Exit Price:</b> ${exit_price:.4f}
💸 <b>Margin:</b> ${margin:.2f} USDT
💰 <b>Realized PNL:</b> ${pnl_usdt:.2f} USDT ({pnl_percent:+.2f}%)
🎯 <b>Exit Reason:</b> {exit_reason}
💰 <b>Current Balance:</b> ${balance_after:.2f} USDT
📈 <b>Current Open Trades:</b> {open_trades}
        """
        self.send_message(message)

    def report_bot_stopped(self, reason: str):
        """4. Bot stopped"""
        message = f"""
🔴 <b>BOT STOPPED</b>
⏰ <b>Time:</b> {datetime.now().strftime("%Y-%m-%d %H:%M")}
📝 <b>Reason:</b> {reason}
        """
        self.send_message(message)

    def report_critical_error(self, error_type: str, diagnosis: str, suggested_action: str):
        """5. Critical error messages"""
        message = f"""
🚨 <b>CRITICAL ERROR</b>
⏰ <b>Time:</b> {datetime.now().strftime("%Y-%m-%d %H:%M")}
⚠️ <b>Error Type:</b> {error_type}
🔍 <b>Diagnosis:</b> {diagnosis}
🛠️ <b>Suggested Action:</b> {suggested_action}
        """
        self.send_message(message)

    def report_orphan_trade_detected(self, strategy_name: str, symbol: str, side: str, entry_price: float):
        """Report orphan trade detection"""
        message = f"""
🔍 <b>ORPHAN TRADE DETECTED</b>
⏰ <b>Time:</b> {datetime.now().strftime("%Y-%m-%d %H:%M")}
🎯 <b>Strategy:</b> {strategy_name}
💰 <b>Pair:</b> {symbol}
📊 <b>Direction:</b> {side}
💵 <b>Entry Price:</b> ${entry_price:.4f}
⚠️ <b>Status:</b> Bot opened trade, manually closed
🔄 <b>Action:</b> Will clear in 2 market cycles
        """
        self.send_message(message)

    def report_orphan_trade_cleared(self, strategy_name: str, symbol: str):
        """Report orphan trade cleared"""
        message = f"""
🧹 <b>ORPHAN TRADE CLEARED</b>
⏰ <b>Time:</b> {datetime.now().strftime("%Y-%m-%d %H:%M")}
🎯 <b>Strategy:</b> {strategy_name}
💰 <b>Pair:</b> {symbol}
✅ <b>Status:</b> Strategy can trade again
        """
        self.send_message(message)

    def report_ghost_trade_detected(self, strategy_name: str, symbol: str, side: str, quantity: float):
        """Report ghost trade detection"""
        message = f"""
👻 <b>GHOST TRADE DETECTED</b>
⏰ <b>Time:</b> {datetime.now().strftime("%Y-%m-%d %H:%M")}
🎯 <b>Strategy:</b> {strategy_name}
💰 <b>Pair:</b> {symbol}
📊 <b>Direction:</b> {side}
📏 <b>Quantity:</b> {quantity:.6f}
⚠️ <b>Status:</b> Manual trade found, not opened by bot
🔄 <b>Action:</b> Will clear in 2 market cycles
        """
        self.send_message(message)

    def report_ghost_trade_cleared(self, strategy_name: str, symbol: str):
        """Report ghost trade cleared"""
        message = f"""
🧹 <b>GHOST TRADE CLEARED</b>
⏰ <b>Time:</b> {datetime.now().strftime("%Y-%m-%d %H:%M")}
🎯 <b>Strategy:</b> {strategy_name}
💰 <b>Pair:</b> {symbol}
✅ <b>Status:</b> Strategy can trade again
        """
        self.send_message(message)

    # Remove all the old methods we don't need anymore
    def report_entry_signal(self, *args, **kwargs):
        pass

    def report_position_opened(self, *args, **kwargs):
        pass

    def report_position_closed(self, *args, **kwargs):
        pass

    def report_error(self, error_type: str, error_message: str, strategy_name: str = None):
        """Report an error to Telegram"""
        try:
            message = f"❌ **{error_type}**\n"
            if strategy_name:
                message += f"Strategy: {strategy_name}\n"
            message += f"Error: {error_message}"

            self.send_message(message)
        except Exception as e:
            self.logger.error(f"Failed to send error report: {e}")

    def report_orphan_trade_detected(self, strategy_name: str, symbol: str, side: str, entry_price: float):
        """Report orphan trade detection to Telegram"""
        try:
            message = f"🔍 **ORPHAN TRADE DETECTED**\n"
            message += f"Strategy: {strategy_name.upper()}\n"
            message += f"Symbol: {symbol}\n"
            message += f"Side: {side}\n"
            message += f"Entry Price: ${entry_price:.4f}\n"
            message += f"⚠️ Position was closed manually outside the bot"

            self.send_message(message)
        except Exception as e:
            self.logger.error(f"Failed to send orphan trade detection report: {e}")

    def report_orphan_trade_cleared(self, strategy_name: str, symbol: str):
        """Report orphan trade clearance to Telegram"""
        try:
            message = f"🧹 **ORPHAN TRADE CLEARED**\n"
            message += f"Strategy: {strategy_name.upper()}\n"
            message += f"Symbol: {symbol}\n"
            message += f"✅ Strategy can now trade again"

            self.send_message(message)
        except Exception as e:
            self.logger.error(f"Failed to send orphan trade clearance report: {e}")

    def report_ghost_trade_detected(self, strategy_name: str, symbol: str, side: str, quantity: float):
        """Report ghost trade detection to Telegram"""
        try:
            message = f"👻 **GHOST TRADE DETECTED**\n"
            message += f"Strategy: {strategy_name.upper()}\n"
            message += f"Symbol: {symbol}\n"
            message += f"Side: {side}\n"
            message += f"Quantity: {quantity}\n"
            message += f"⚠️ Position was opened manually outside the bot"

            self.send_message(message)
        except Exception as e:
            self.logger.error(f"Failed to send ghost trade detection report: {e}")

    def report_ghost_trade_cleared(self, strategy_name: str, symbol: str):
        """Report ghost trade clearance to Telegram"""
        try:
            message = f"🧹 **GHOST TRADE CLEARED**\n"
            message += f"Strategy: {strategy_name.upper()}\n"
            message += f"Symbol: {symbol}\n"
            message += f"✅ Strategy can now trade again"

            self.send_message(message)
        except Exception as e:
            self.logger.error(f"Failed to send ghost trade clearance report: {e}")