
import logging
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime
from src.config.global_config import global_config


class TelegramReporter:
    """Telegram bot for sending trading notifications and reports"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.bot_token = global_config.TELEGRAM_BOT_TOKEN
        self.chat_id = global_config.TELEGRAM_CHAT_ID
        self.enabled = bool(self.bot_token and self.chat_id)

        if not self.enabled:
            self.logger.warning("⚠️ TELEGRAM: Bot token or chat ID not configured - notifications disabled")
        else:
            self.logger.info("✅ TELEGRAM: Reporter initialized successfully")

    def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        """Send a message to Telegram"""
        if not self.enabled:
            self.logger.debug("TELEGRAM: Skipping message (not configured)")
            return False

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode,
                'disable_web_page_preview': True
            }

            response = requests.post(url, json=payload, timeout=10)

            if response.status_code == 200:
                self.logger.debug("✅ TELEGRAM: Message sent successfully")
                return True
            else:
                self.logger.error(f"❌ TELEGRAM: Failed to send message. Status: {response.status_code}, Response: {response.text}")
                return False

        except Exception as e:
            self.logger.error(f"❌ TELEGRAM: Error sending message: {e}")
            return False

    def report_bot_startup(self, pairs: List[str], strategies: List[str], balance: float, open_trades: int = 0) -> bool:
        """Send bot startup notification"""
        try:
            timestamp = datetime.now().strftime('%H:%M:%S')
            mode = "TESTNET" if global_config.BINANCE_TESTNET else "MAINNET"

            message = f"""
🚀 <b>TRADING BOT STARTED</b>
⏰ <b>Time:</b> {timestamp}
🌐 <b>Mode:</b> {mode}

📊 <b>STRATEGIES ACTIVE:</b>
{chr(10).join([f"• {strategy.upper()}" for strategy in strategies])}

💱 <b>TRADING PAIRS:</b>
{chr(10).join([f"• {pair}" for pair in pairs])}

💰 <b>Account Balance:</b> ${balance:,.2f} USDT
📈 <b>Open Positions:</b> {open_trades}

✅ <b>Status:</b> Monitoring markets for entry signals
🔄 <b>Next Update:</b> Real-time alerts enabled
"""

            return self.send_message(message)

        except Exception as e:
            self.logger.error(f"❌ TELEGRAM: Error sending startup notification: {e}")
            return False

    def report_bot_stopped(self, reason: str = "Manual shutdown") -> bool:
        """Send bot shutdown notification"""
        try:
            timestamp = datetime.now().strftime('%H:%M:%S')

            message = f"""
🛑 <b>TRADING BOT STOPPED</b>
⏰ <b>Time:</b> {timestamp}
📝 <b>Reason:</b> {reason}

⚠️ <b>Status:</b> No longer monitoring markets
💡 <b>Note:</b> Restart required to resume trading
"""

            return self.send_message(message)

        except Exception as e:
            self.logger.error(f"❌ TELEGRAM: Error sending shutdown notification: {e}")
            return False

    def report_position_opened(self, position_data: Dict) -> bool:
        """Send position opened notification"""
        try:
            timestamp = datetime.now().strftime('%H:%M:%S')

            # Extract position details
            strategy = position_data.get('strategy_name', 'Unknown').upper()
            symbol = position_data.get('symbol', 'Unknown')
            side = position_data.get('side', 'Unknown')
            entry_price = position_data.get('entry_price', 0)
            quantity = position_data.get('quantity', 0)
            leverage = position_data.get('leverage', 1)

            # Calculate position value
            position_value = entry_price * quantity
            margin_used = position_value / leverage

            message = f"""
🔴 <b>POSITION OPENED</b>
⏰ <b>Time:</b> {timestamp}

🎯 <b>Strategy:</b> {strategy}
💱 <b>Symbol:</b> {symbol}
📊 <b>Side:</b> {side}
💵 <b>Entry Price:</b> ${entry_price:,.4f}
📦 <b>Quantity:</b> {quantity:,.6f}
⚡ <b>Leverage:</b> {leverage}x
💸 <b>Margin Used:</b> ${margin_used:,.2f} USDT
💰 <b>Position Value:</b> ${position_value:,.2f} USDT

✅ <b>Status:</b> Monitoring for exit conditions
"""

            return self.send_message(message)

        except Exception as e:
            self.logger.error(f"❌ TELEGRAM: Error sending position opened notification: {e}")
            return False

    def report_position_closed(self, position_data: Dict, exit_reason: str, pnl: float) -> bool:
        """Send position closed notification"""
        try:
            timestamp = datetime.now().strftime('%H:%M:%S')

            # Extract position details
            strategy = position_data.get('strategy_name', 'Unknown').upper()
            symbol = position_data.get('symbol', 'Unknown')
            side = position_data.get('side', 'Unknown')
            entry_price = position_data.get('entry_price', 0)
            exit_price = position_data.get('exit_price', 0)
            quantity = position_data.get('quantity', 0)

            # Calculate position metrics
            position_value = entry_price * quantity
            pnl_percent = (pnl / position_value) * 100 if position_value > 0 else 0

            # Determine profit/loss status
            status_emoji = "💚" if pnl >= 0 else "❌"
            status_text = "PROFIT" if pnl >= 0 else "LOSS"

            message = f"""
🔴 <b>POSITION CLOSED</b>
⏰ <b>Time:</b> {timestamp}

🎯 <b>Strategy:</b> {strategy}
💱 <b>Symbol:</b> {symbol}
📊 <b>Side:</b> {side}
💵 <b>Entry:</b> ${entry_price:,.4f}
🚪 <b>Exit:</b> ${exit_price:,.4f}
{status_emoji} <b>PnL:</b> ${pnl:,.2f} USDT ({pnl_percent:+.2f}%)
📝 <b>Exit Reason:</b> {exit_reason}

{status_emoji} <b>Result:</b> {status_text}
"""

            return self.send_message(message)

        except Exception as e:
            self.logger.error(f"❌ TELEGRAM: Error sending position closed notification: {e}")
            return False

    def report_error(self, error_type: str, error_message: str, strategy_name: str = None) -> bool:
        """Send error notification"""
        try:
            timestamp = datetime.now().strftime('%H:%M:%S')

            strategy_info = f"\n🎯 <b>Strategy:</b> {strategy_name.upper()}" if strategy_name else ""

            message = f"""
⚠️ <b>ERROR ALERT</b>
⏰ <b>Time:</b> {timestamp}
🔍 <b>Type:</b> {error_type}{strategy_info}

📝 <b>Details:</b>
{error_message}

🔧 <b>Action:</b> Check logs for more information
"""

            return self.send_message(message)

        except Exception as e:
            self.logger.error(f"❌ TELEGRAM: Error sending error notification: {e}")
            return False

    def report_balance_warning(self, required_balance: float, current_balance: float) -> bool:
        """Send low balance warning"""
        try:
            timestamp = datetime.now().strftime('%H:%M:%S')

            message = f"""
⚠️ <b>LOW BALANCE WARNING</b>
⏰ <b>Time:</b> {timestamp}

💰 <b>Current Balance:</b> ${current_balance:,.2f} USDT
💸 <b>Required Balance:</b> ${required_balance:,.2f} USDT
📉 <b>Shortage:</b> ${required_balance - current_balance:,.2f} USDT

🚫 <b>Status:</b> Trading suspended due to insufficient balance
💡 <b>Action:</b> Add funds to resume trading
"""

            return self.send_message(message)

        except Exception as e:
            self.logger.error(f"❌ TELEGRAM: Error sending balance warning: {e}")
            return False

    def report_anomaly_detected(self, anomaly_type: str, details: Dict) -> bool:
        """Send anomaly detection notification"""
        try:
            timestamp = datetime.now().strftime('%H:%M:%S')

            strategy = details.get('strategy_name', 'Unknown').upper()
            symbol = details.get('symbol', 'Unknown')

            if anomaly_type.lower() == 'orphan':
                emoji = "👻"
                title = "ORPHAN TRADE DETECTED"
                description = "Bot opened position but it was closed manually"
            elif anomaly_type.lower() == 'ghost':
                emoji = "🔍"
                title = "GHOST TRADE DETECTED"
                description = "Manual position detected on bot-managed symbol"
            else:
                emoji = "⚠️"
                title = "TRADE ANOMALY DETECTED"
                description = f"Anomaly type: {anomaly_type}"

            message = f"""
{emoji} <b>{title}</b>
⏰ <b>Time:</b> {timestamp}

🎯 <b>Strategy:</b> {strategy}
💱 <b>Symbol:</b> {symbol}
📝 <b>Description:</b> {description}

🔍 <b>Action:</b> Monitoring for auto-resolution
💡 <b>Note:</b> Use anomaly manager if manual intervention needed
"""

            return self.send_message(message)

        except Exception as e:
            self.logger.error(f"❌ TELEGRAM: Error sending anomaly notification: {e}")
            return False

    def test_connection(self) -> bool:
        """Test Telegram bot connection"""
        if not self.enabled:
            self.logger.warning("TELEGRAM: Cannot test - not configured")
            return False

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getMe"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                bot_info = response.json()
                if bot_info.get('ok'):
                    bot_name = bot_info.get('result', {}).get('username', 'Unknown')
                    self.logger.info(f"✅ TELEGRAM: Connection test successful. Bot: @{bot_name}")
                    return True

            self.logger.error(f"❌ TELEGRAM: Connection test failed. Status: {response.status_code}")
            return False

        except Exception as e:
            self.logger.error(f"❌ TELEGRAM: Connection test error: {e}")
            return False
