
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
            # Filter out market assessment messages - they should only appear in console logs
            if ("MARKET ASSESSMENT" in message or 
                "SCANNING" in message or 
                "MARKET SCAN" in message or
                "📈 MARKET" in message):
                return True  # Skip sending but return success
            
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
        # Determine if this is an error or manual shutdown
        is_error = any(keyword in reason.lower() for keyword in ['error', 'failed', 'exception', 'critical'])
        
        # Choose appropriate emoji and status
        status_emoji = "🚨" if is_error else "🔴"
        status_text = "ERROR SHUTDOWN" if is_error else "BOT STOPPED"
        
        # Suggest fixes for common errors
        suggested_fixes = ""
        if is_error:
            if "api" in reason.lower():
                suggested_fixes = "\n🛠️ <b>Suggested Fix:</b> Check API keys and permissions"
            elif "connection" in reason.lower():
                suggested_fixes = "\n🛠️ <b>Suggested Fix:</b> Check internet connection and Binance status"
            elif "auth" in reason.lower():
                suggested_fixes = "\n🛠️ <b>Suggested Fix:</b> Verify API credentials and IP whitelist"
            elif "balance" in reason.lower():
                suggested_fixes = "\n🛠️ <b>Suggested Fix:</b> Check account balance and margin requirements"
            else:
                suggested_fixes = "\n🛠️ <b>Suggested Fix:</b> Check logs and restart bot if needed"
        
        message = f"""
{status_emoji} <b>{status_text}</b>
⏰ <b>Time:</b> {datetime.now().strftime("%Y-%m-%d %H:%M")}
📝 <b>Reason:</b> {reason}{suggested_fixes}
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

    def report_entry_signal(self, strategy_name: str, signal_data: dict):
        """Report entry signal detection to Telegram"""
        try:
            message = f"""
🚨 <b>ENTRY SIGNAL DETECTED</b>
⏰ <b>Time:</b> {datetime.now().strftime("%Y-%m-%d %H:%M")}
🎯 <b>Strategy:</b> {strategy_name.upper()}
💰 <b>Pair:</b> {signal_data['symbol']}
📊 <b>Signal:</b> {signal_data['signal_type']}
💵 <b>Entry Price:</b> ${signal_data['entry_price']:.4f}
🛡️ <b>Stop Loss:</b> ${signal_data['stop_loss']:.4f}
🎯 <b>Take Profit:</b> ${signal_data['take_profit']:.4f}
📝 <b>Reason:</b> {signal_data['reason']}
            """
            self.send_message(message)
        except Exception as e:
            self.logger.error(f"Failed to send entry signal report: {e}")

    def report_position_opened(self, position_data: dict):
        """Report position opened to Telegram"""
        try:
            # Get balance and trade count info
            from src.data_fetcher.balance_fetcher import BalanceFetcher
            from src.binance_client.client import BinanceClientWrapper
            
            binance_client = BinanceClientWrapper()
            balance_fetcher = BalanceFetcher(binance_client)
            current_balance = balance_fetcher.get_usdt_balance() or 0
            
            # Calculate margin used (simplified)
            margin_used = position_data['entry_price'] * position_data['quantity'] / 5  # Assuming 5x leverage
            
            message = f"""
🟢 <b>TRADE ENTRY</b>
⏰ <b>Time:</b> {datetime.now().strftime("%Y-%m-%d %H:%M")}
🎯 <b>Strategy Name:</b> {position_data['strategy_name'].upper()}
💰 <b>Pair:</b> {position_data['symbol']}
📊 <b>Direction:</b> {position_data['side']}
💵 <b>Entry Price:</b> ${position_data['entry_price']:.4f}
💸 <b>Margin:</b> ${margin_used:.2f} USDT
⚡ <b>Leverage:</b> 5x
💰 <b>Current Balance:</b> ${current_balance:.2f} USDT
📈 <b>Current Open Trades:</b> 1
            """
            self.send_message(message)
        except Exception as e:
            self.logger.error(f"Failed to send position opened report: {e}")

    def report_position_closed(self, position_data: dict, exit_reason: str, pnl: float):
        """Report position closed to Telegram"""
        try:
            pnl_emoji = "🟢" if pnl >= 0 else "🔴"
            pnl_percent = (pnl / (position_data['entry_price'] * position_data['quantity'])) * 100
            
            # Get current balance
            from src.data_fetcher.balance_fetcher import BalanceFetcher
            from src.binance_client.client import BinanceClientWrapper
            
            binance_client = BinanceClientWrapper()
            balance_fetcher = BalanceFetcher(binance_client)
            current_balance = balance_fetcher.get_usdt_balance() or 0
            
            # Calculate margin used
            margin_used = position_data['entry_price'] * position_data['quantity'] / 5
            
            message = f"""
{pnl_emoji} <b>TRADE CLOSED</b>
⏰ <b>Time:</b> {datetime.now().strftime("%Y-%m-%d %H:%M")}
🎯 <b>Strategy Name:</b> {position_data['strategy_name'].upper()}
💰 <b>Pair:</b> {position_data['symbol']}
📊 <b>Direction:</b> {position_data['side']}
💵 <b>Entry Price:</b> ${position_data['entry_price']:.4f}
🚪 <b>Exit Price:</b> ${position_data.get('exit_price', 0):.4f}
💸 <b>Margin:</b> ${margin_used:.2f} USDT
💰 <b>Realized PNL:</b> ${pnl:.2f} USDT ({pnl_percent:+.2f}%)
🎯 <b>Exit Reason:</b> {exit_reason}
💰 <b>Current Balance:</b> ${current_balance:.2f} USDT
📈 <b>Current Open Trades:</b> 0
            """
            self.send_message(message)
        except Exception as e:
            self.logger.error(f"Failed to send position closed report: {e}")

    def report_orphan_trade_detected(self, strategy_name: str, symbol: str, side: str, entry_price: float):
        """Report orphan trade detection to Telegram"""
        try:
            message = f"""
🔍 <b>ORPHAN TRADE DETECTED</b>
⏰ <b>Time:</b> {datetime.now().strftime("%Y-%m-%d %H:%M")}
🎯 <b>Strategy:</b> {strategy_name.upper()}
💰 <b>Pair:</b> {symbol}
📊 <b>Direction:</b> {side}
💵 <b>Entry Price:</b> ${entry_price:.4f}
⚠️ <b>Status:</b> Bot opened trade, manually closed
🔄 <b>Action:</b> Will clear in 2 market cycles
            """
            self.send_message(message)
        except Exception as e:
            self.logger.error(f"Failed to send orphan trade detection report: {e}")

    def report_orphan_trade_cleared(self, strategy_name: str, symbol: str):
        """Report orphan trade clearance to Telegram"""
        try:
            message = f"""
🧹 <b>ORPHAN TRADE CLEARED</b>
⏰ <b>Time:</b> {datetime.now().strftime("%Y-%m-%d %H:%M")}
🎯 <b>Strategy:</b> {strategy_name.upper()}
💰 <b>Pair:</b> {symbol}
✅ <b>Status:</b> Strategy can now trade again
            """
            self.send_message(message)
        except Exception as e:
            self.logger.error(f"Failed to send orphan trade clearance report: {e}")

    def report_ghost_trade_detected(self, strategy_name: str, symbol: str, side: str, quantity: float):
        """Report ghost trade detection to Telegram"""
        try:
            message = f"""
👻 <b>GHOST TRADE DETECTED</b>
⏰ <b>Time:</b> {datetime.now().strftime("%Y-%m-%d %H:%M")}
🎯 <b>Strategy:</b> {strategy_name.upper()}
💰 <b>Pair:</b> {symbol}
📊 <b>Direction:</b> {side}
📏 <b>Quantity:</b> {quantity:.6f}
⚠️ <b>Status:</b> Manual trade found, not opened by bot
🔄 <b>Action:</b> Will clear in 2 market cycles
            """
            self.send_message(message)
        except Exception as e:
            self.logger.error(f"Failed to send ghost trade detection report: {e}")

    def report_ghost_trade_cleared(self, strategy_name: str, symbol: str):
        """Report ghost trade clearance to Telegram"""
        try:
            message = f"""
🧹 <b>GHOST TRADE CLEARED</b>
⏰ <b>Time:</b> {datetime.now().strftime("%Y-%m-%d %H:%M")}
🎯 <b>Strategy:</b> {strategy_name.upper()}
💰 <b>Pair:</b> {symbol}
⚠️ <b>Note:</b> Position remains open on Binance (manual trade)
✅ <b>Status:</b> Strategy can now trade again
            """
            self.send_message(message)
        except Exception as e:
            self.logger.error(f"Failed to send ghost trade clearance report: {e}")

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
