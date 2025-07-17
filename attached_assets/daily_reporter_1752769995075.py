
import logging
import schedule
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Any
from src.analytics.trade_logger import trade_logger
from src.reporting.telegram_reporter import TelegramReporter

class DailyReporter:
    """Automated daily trading reports"""
    
    def __init__(self, telegram_reporter: TelegramReporter):
        self.logger = logging.getLogger(__name__)
        self.telegram_reporter = telegram_reporter
        self.is_running = False
        self.scheduler_thread = None
        
    def start_scheduler(self):
        """Start the daily report scheduler"""
        if self.is_running:
            self.logger.warning("⚠️ Daily reporter scheduler already running")
            return
            
        # Schedule daily report at 8:00 AM Dubai time (UTC+4)
        # Note: This schedules at 4:00 AM UTC which is 8:00 AM Dubai time
        schedule.every().day.at("04:00").do(self._send_daily_report)
        
        self.is_running = True
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        self.logger.info("📅 Daily report scheduler started - Reports at 8:00 AM Dubai time")
        
    def stop_scheduler(self):
        """Stop the daily report scheduler"""
        self.is_running = False
        schedule.clear()
        self.logger.info("📅 Daily report scheduler stopped")
        
    def _run_scheduler(self):
        """Run the scheduler in a separate thread"""
        while self.is_running:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
            
    def _send_daily_report(self):
        """Generate and send daily trading report"""
        try:
            # Get yesterday's data (previous day)
            yesterday = datetime.now() - timedelta(days=1)
            daily_summary = trade_logger.get_daily_summary(yesterday)
            
            # Generate report
            report = self._format_daily_report(daily_summary)
            
            # Send to Telegram
            success = self.telegram_reporter.send_message(report)
            
            if success:
                self.logger.info(f"📊 Daily report sent successfully for {yesterday.strftime('%Y-%m-%d')}")
            else:
                self.logger.error(f"❌ Failed to send daily report for {yesterday.strftime('%Y-%m-%d')}")
                
        except Exception as e:
            self.logger.error(f"❌ Error generating daily report: {e}")
            
    def _format_daily_report(self, summary: Dict[str, Any]) -> str:
        """Format daily summary into Telegram message"""
        
        # Header
        report = f"""
📊 <b>DAILY TRADING REPORT</b>
📅 <b>Date:</b> {summary['date']}
⏰ <b>Period:</b> 00:00 - 23:59 (Previous Day)

═══════════════════════════════
<b>📈 SUMMARY STATISTICS</b>
"""
        
        # Basic stats
        total_pnl = summary['total_pnl']
        pnl_emoji = "🟢" if total_pnl >= 0 else "🔴"
        
        report += f"""
📊 <b>Total Trades:</b> {summary['total_trades']}
✅ <b>Closed Trades:</b> {summary['closed_trades']}
🔄 <b>Open Trades:</b> {summary['open_trades']}
🏆 <b>Winning Trades:</b> {summary['winning_trades']}
❌ <b>Losing Trades:</b> {summary['losing_trades']}
📊 <b>Win Rate:</b> {summary['win_rate']:.1f}%
{pnl_emoji} <b>Total P&L:</b> ${total_pnl:.2f} USDT
⏱️ <b>Avg Trade Duration:</b> {summary['average_trade_duration']:.0f} minutes
"""
        
        # Strategy breakdown
        if summary['strategy_breakdown']:
            report += f"""
═══════════════════════════════
<b>🎯 STRATEGY BREAKDOWN</b>
"""
            
            for strategy, stats in summary['strategy_breakdown'].items():
                strategy_pnl = stats['pnl']
                strategy_emoji = "🟢" if strategy_pnl >= 0 else "🔴"
                symbols_str = ", ".join(stats['symbols'])
                
                report += f"""
<b>{strategy.upper()}</b>
└ Trades: {stats['trades']}
└ P&L: {strategy_emoji} ${strategy_pnl:.2f} USDT
└ Symbols: {symbols_str}

"""
        
        # Individual trades summary
        if summary['trades']:
            report += f"""═══════════════════════════════
<b>📋 TRADE DETAILS</b>
"""
            
            for i, trade in enumerate(summary['trades'], 1):
                if trade['trade_status'] == 'CLOSED':
                    pnl = trade.get('pnl_usdt', 0)
                    pnl_pct = trade.get('pnl_percentage', 0)
                    pnl_emoji = "🟢" if pnl >= 0 else "🔴"
                    duration = trade.get('duration_minutes', 0)
                    
                    report += f"""
<b>Trade #{i}</b>
🎯 {trade['strategy_name'].upper()} | {trade['symbol']}
📊 {trade['side']} @ ${trade['entry_price']:.4f}
🚪 Exit @ ${trade.get('exit_price', 0):.4f}
{pnl_emoji} P&L: ${pnl:.2f} ({pnl_pct:+.2f}%)
⏱️ Duration: {duration}min
📝 Reason: {trade.get('exit_reason', 'N/A')}

"""
                else:
                    # Open trade
                    report += f"""
<b>Trade #{i} [OPEN]</b>
🎯 {trade['strategy_name'].upper()} | {trade['symbol']}
📊 {trade['side']} @ ${trade['entry_price']:.4f}
💰 Position: ${trade['position_value_usdt']:.2f} USDT

"""
        
        # Footer
        report += f"""═══════════════════════════════
<b>🤖 SYSTEM STATUS</b>
✅ Bot Active | 📊 ML Data Collection: ON
📈 Next Report: Tomorrow 8:00 AM Dubai Time

<i>Report generated automatically by Trading Bot</i>
"""
        
        return report
        
    def send_manual_report(self, date: datetime = None) -> bool:
        """Manually trigger a daily report"""
        try:
            if not date:
                date = datetime.now() - timedelta(days=1)
                
            daily_summary = trade_logger.get_daily_summary(date)
            report = self._format_daily_report(daily_summary)
            
            success = self.telegram_reporter.send_message(report)
            
            if success:
                self.logger.info(f"📊 Manual daily report sent for {date.strftime('%Y-%m-%d')}")
            else:
                self.logger.error(f"❌ Failed to send manual daily report")
                
            return success
            
        except Exception as e:
            self.logger.error(f"❌ Error sending manual daily report: {e}")
            return False

# Global daily reporter instance (will be initialized in bot_manager)
daily_reporter = None
