import requests
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime
from src.config.global_config import global_config
from typing import List


class TelegramReporter:
    """Handles Telegram notifications for trading bot"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Get Telegram config from environment
        self.bot_token = global_config.TELEGRAM_BOT_TOKEN
        self.chat_id = global_config.TELEGRAM_CHAT_ID

        # Validate configuration
        if not self.bot_token or not self.chat_id:
            self.logger.warning("⚠️ Telegram configuration incomplete - notifications disabled")
            self.enabled = False
        else:
            self.enabled = True
            self.logger.info("✅ Telegram reporter initialized successfully")

        # Rate limiting
        self.last_message_time = {}
        self.min_interval = 5  # Minimum 5 seconds between similar messages

        # Track startup notifications to prevent duplicates
        self.startup_notification_sent = False

        # Set up Telegram API base URL
        if self.bot_token:
            self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        """Send a message to Telegram"""
        try:
            self.logger.info(f"🔍 TELEGRAM DEBUG: send_message() called with message length: {len(message)}")

            # Filter out market assessment messages - they should only appear in console logs
            if ("MARKET ASSESSMENT" in message or 
                "SCANNING" in message or 
                "MARKET SCAN" in message or
                "📈 MARKET" in message):
                self.logger.info(f"🔍 TELEGRAM DEBUG: Message filtered out (market assessment)")
                return True  # Skip sending but return success

            self.logger.info(f"🔍 TELEGRAM DEBUG: bot_token exists: {bool(self.bot_token)}")
            self.logger.info(f"🔍 TELEGRAM DEBUG: chat_id exists: {bool(self.chat_id)}")

            url = f"{self.base_url}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode
            }

            self.logger.info(f"🔍 TELEGRAM DEBUG: Making POST request to Telegram API...")
            response = requests.post(url, json=payload, timeout=10)
            self.logger.info(f"🔍 TELEGRAM DEBUG: Response status: {response.status_code}")

            response.raise_for_status()
            self.logger.info(f"🔍 TELEGRAM DEBUG: Message sent successfully!")

            return True

        except Exception as e:
            self.logger.error(f"❌ TELEGRAM ERROR: Failed to send message: {e}")
            self.logger.error(f"❌ TELEGRAM ERROR: Error type: {type(e).__name__}")
            import traceback
            self.logger.error(f"❌ TELEGRAM ERROR: Full traceback: {traceback.format_exc()}")
            return False

    def reset_startup_notification(self):
        """Reset startup notification flag - used when bot is restarted"""
        self.startup_notification_sent = False
        self.logger.info("🔍 TELEGRAM DEBUG: Startup notification flag reset")

    def report_bot_startup(self, pairs: List[str], strategies: List[str], balance: float, open_trades: int, source: str = "Unknown"):
        """Report bot startup to Telegram"""
        try:
            # Prevent duplicate startup notifications - use a more robust check
            current_time = datetime.now()
            if hasattr(self, 'last_startup_time'):
                time_since_last = (current_time - self.last_startup_time).total_seconds()
                if time_since_last < 300:  # Prevent duplicates within 5 minutes
                    self.logger.info(f"🔍 TELEGRAM DEBUG: Startup notification sent {time_since_last:.0f}s ago, skipping duplicate")
                    return True

            self.logger.info(f"🔍 TELEGRAM DEBUG: report_bot_startup() called")
            self.logger.info(f"🔍 TELEGRAM DEBUG: pairs={pairs}, strategies={strategies}, balance={balance}, open_trades={open_trades}")

            pairs_text = ", ".join(pairs)
            strategies_text = ", ".join(strategies)

            message = f"""
🟢 <b>BOT STARTED</b>
⏰ <b>Time:</b> {datetime.now().strftime("%Y-%m-%d %H:%M")}
🔋 <b>Bot Health:</b> Online
📊 <b>Pairs Watching:</b> {pairs_text}
🎯 <b>Strategy Names:</b> {strategies_text}
💰 <b>Available Balance:</b> ${balance:.2f} USDT
📈 <b>Currently Open Trades:</b> {open_trades}
            """

            self.logger.info(f"🔍 TELEGRAM DEBUG: Prepared message, calling send_message()")
            result = self.send_message(message)
            self.logger.info(f"🔍 TELEGRAM DEBUG: send_message() returned: {result}")

            # Mark startup notification time if successful
            if result:
                self.last_startup_time = current_time
                self.logger.info(f"🔍 TELEGRAM DEBUG: Startup notification time recorded")

            return result
        except Exception as e:
            self.logger.error(f"Failed to send bot startup report: {e}")
            return False

    def report_trade_entry(self, strategy_name: str, pair: str, direction: str, entry_price: float, 
                          margin: float, leverage: int, balance_after: float, open_trades: int, quantity: float = None):
        """2. Trade Entry"""
        # Calculate position value if quantity is provided
        position_value_text = ""
        if quantity:
            position_value = entry_price * quantity
            position_value_text = f"📦 <b>Position Value:</b> ${position_value:.2f} USDT\n"

        message = f"""
🟢 <b>TRADE ENTRY</b>
⏰ <b>Time:</b> {datetime.now().strftime("%Y-%m-%d %H:%M")}
🎯 <b>Strategy Name:</b> {strategy_name}
💰 <b>Pair:</b> {pair}
📊 <b>Direction:</b> {direction}
💵 <b>Entry Price:</b> ${entry_price:.4f}
{position_value_text}💸 <b>Margin Used:</b> ${margin:.2f} USDT
⚡ <b>Leverage:</b> {leverage}x
💰 <b>Current Balance:</b> ${balance_after:.2f} USDT
📈 <b>Current Open Trades:</b> {open_trades}
        """
        self.send_message(message)

    def report_trade_closing(self, strategy_name: str, pair: str, direction: str, entry_price: float,
                           exit_price: float, margin: float, pnl_usdt: float, pnl_percent: float,
                           exit_reason: str, balance_after: float, open_trades: int, quantity: float = None):
        """3. Trade Closing"""
        pnl_emoji = "🟢" if pnl_usdt >= 0 else "🔴"

        # Calculate position value if quantity is provided
        position_value_text = ""
        if quantity:
            position_value = entry_price * quantity
            position_value_text = f"📦 <b>Position Value:</b> ${position_value:.2f} USDT\n"

        message = f"""
{pnl_emoji} <b>TRADE CLOSED</b>
⏰ <b>Time:</b> {datetime.now().strftime("%Y-%m-%d %H:%M")}
🎯 <b>Strategy Name:</b> {strategy_name}
💰 <b>Pair:</b> {pair}
📊 <b>Direction:</b> {direction}
💵 <b>Entry Price:</b> ${entry_price:.4f}
🚪 <b>Exit Price:</b> ${exit_price:.4f}
{position_value_text}💸 <b>Margin Used:</b> ${margin:.2f} USDT
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
            # Create unique signal identifier to prevent duplicates
            signal_id = f"{strategy_name}_{signal_data['symbol']}_{signal_data['signal_type']}"
            current_time = datetime.now()

            # Initialize signal tracking if not exists
            if not hasattr(self, 'last_signal_times'):
                self.last_signal_times = {}

            # Check if we recently sent this signal type for this strategy/symbol
            if signal_id in self.last_signal_times:
                time_since_last = (current_time - self.last_signal_times[signal_id]).total_seconds()
                if time_since_last < 900:  # Prevent duplicate signals within 15 minutes
                    self.logger.info(f"🔍 TELEGRAM DEBUG: Duplicate signal blocked - {signal_id} sent {time_since_last:.0f}s ago, cooldown active")
                    return

            # Mark this signal as sent
            self.last_signal_times[signal_id] = current_time

            # Send the signal notification
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
            
            result = self.send_message(message)
            if result:
                self.logger.info(f"🔍 TELEGRAM DEBUG: Entry signal notification sent for {signal_id}")
            else:
                self.logger.warning(f"🔍 TELEGRAM DEBUG: Failed to send entry signal notification for {signal_id}")

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

            # Calculate position value and margin used
            position_value_usdt = position_data['entry_price'] * position_data['quantity']
            margin_used = position_value_usdt / 5  # Assuming 5x leverage

            message = f"""
🟢 <b>TRADE ENTRY</b>
⏰ <b>Time:</b> {datetime.now().strftime("%Y-%m-%d %H:%M")}
🎯 <b>Strategy Name:</b> {position_data['strategy_name'].upper()}
💰 <b>Pair:</b> {position_data['symbol']}
📊 <b>Direction:</b> {position_data['side']}
💵 <b>Entry Price:</b> ${position_data['entry_price']:.4f}
📦 <b>Position Value:</b> ${position_value_usdt:.2f} USDT
💸 <b>Margin Used:</b> ${margin_used:.2f} USDT
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
            position_value_usdt = position_data['entry_price'] * position_data['quantity']
            pnl_percent = (pnl / position_value_usdt) * 100

            # Get current balance
            from src.data_fetcher.balance_fetcher import BalanceFetcher
            from src.binance_client.client import BinanceClientWrapper

            binance_client = BinanceClientWrapper()
            balance_fetcher = BalanceFetcher(binance_client)
            current_balance = balance_fetcher.get_usdt_balance() or 0

            # Calculate margin used
            margin_used = position_value_usdt / 5  # Assuming 5x leverage

            # Get actual current open trades count from bot manager
            open_trades_count = 0
            try:
                # Import here to avoid circular imports
                import sys
                for module_name, module in sys.modules.items():
                    if hasattr(module, 'shared_bot_instance') and module.shared_bot_instance:
                        open_trades_count = len(module.shared_bot_instance.order_manager.active_positions)
                        break
            except Exception as e:
                self.logger.debug(f"Could not get open trades count: {e}")
                open_trades_count = 0

            message = f"""
{pnl_emoji} <b>TRADE CLOSED</b>
⏰ <b>Time:</b> {datetime.now().strftime("%Y-%m-%d %H:%M")}
🎯 <b>Strategy Name:</b> {position_data['strategy_name'].upper()}
💰 <b>Pair:</b> {position_data['symbol']}
📊 <b>Direction:</b> {position_data['side']}
💵 <b>Entry Price:</b> ${position_data['entry_price']:.4f}
🚪 <b>Exit Price:</b> ${position_data.get('exit_price', 0):.4f}
📦 <b>Position Value:</b> ${position_value_usdt:.2f} USDT
💸 <b>Margin Used:</b> ${margin_used:.2f} USDT
💰 <b>Realized PNL:</b> ${pnl:.2f} USDT ({pnl_percent:+.2f}%)
🎯 <b>Exit Reason:</b> {exit_reason}
💰 <b>Current Balance:</b> ${current_balance:.2f} USDT
📈 <b>Current Open Trades:</b> {open_trades_count}
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

    def report_ghost_trade_detected(self, strategy_name: str, symbol: str, side: str, quantity: float, current_price: float = None):
        """Report ghost trade detection to Telegram"""
        try:
            # Simple position value calculation without additional Binance API calls
            position_value_text = ""
            if current_price:
                position_value = current_price * quantity
                position_value_text = f"📦 <b>Position Value:</b> ${position_value:.2f} USDT\n"

            message = f"""
👻 <b>GHOST TRADE DETECTED</b>
⏰ <b>Time:</b> {datetime.now().strftime("%Y-%m-%d %H:%M")}
🎯 <b>Strategy:</b> {strategy_name.upper()}
💰 <b>Pair:</b> {symbol}
📊 <b>Direction:</b> {side}
📏 <b>Quantity:</b> {quantity:.6f} {symbol.replace('USDT', '')}
{position_value_text}⚠️ <b>Status:</b> Manual trade found, not opened by bot
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