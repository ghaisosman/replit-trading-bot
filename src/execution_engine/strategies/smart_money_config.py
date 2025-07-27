
from typing import Dict, Any, List, Optional
from src.strategy_processor.signal_processor import TradingSignal, SignalType
import numpy as np
import logging
from datetime import datetime, time
import pytz

class SmartMoneyStrategy:
    """
    Smart Money Liquidity Hunt Strategy
    
    This strategy identifies and trades liquidity sweeps where market makers hunt for retail stop losses
    at obvious support/resistance levels, then reverse the price direction.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.name = config.get('name', 'smart_money')
        
        # Core parameters
        self.symbol = config.get('symbol', 'BTCUSDT')
        self.timeframe = config.get('timeframe', '5m')
        
        # Smart Money specific parameters with defaults
        self.swing_lookback_period = config.get('swing_lookback_period', 25)
        self.sweep_threshold_pct = config.get('sweep_threshold_pct', 0.1)
        self.reversion_candles = config.get('reversion_candles', 3)
        self.volume_spike_multiplier = config.get('volume_spike_multiplier', 2.0)
        self.min_swing_distance_pct = config.get('min_swing_distance_pct', 1.0)
        
        # Session filtering
        self.session_filter_enabled = config.get('session_filter_enabled', True)
        self.allowed_sessions = config.get('allowed_sessions', ['LONDON', 'NEW_YORK'])
        
        # Risk management
        self.max_daily_trades = config.get('max_daily_trades', 3)
        self.trend_filter_enabled = config.get('trend_filter_enabled', True)
        
        # Internal tracking
        self.daily_trade_count = 0
        self.last_trade_date = None
        self.recent_sweeps = []  # Track recent sweeps to avoid false signals
        
        self.logger.info(f"🧠 SMART MONEY STRATEGY INITIALIZED | {self.symbol} | {self.timeframe}")
        self.logger.info(f"   📊 Swing Lookback: {self.swing_lookback_period} candles")
        self.logger.info(f"   🎯 Sweep Threshold: {self.sweep_threshold_pct}%")
        self.logger.info(f"   ⏱️ Reversion Window: {self.reversion_candles} candles")
        self.logger.info(f"   📈 Volume Spike: {self.volume_spike_multiplier}x")
        self.logger.info(f"   📏 Min Swing Distance: {self.min_swing_distance_pct}%")
        
    def analyze_market(self, klines: List[List], current_price: float) -> Optional[TradingSignal]:
        """
        Main analysis method for Smart Money strategy
        """
        try:
            if not klines or len(klines) < self.swing_lookback_period + 10:
                self.logger.warning(f"🧠 SMART MONEY | {self.symbol} | Insufficient data: {len(klines) if klines else 0} candles")
                return None

            # Reset daily trade count if new day
            self._reset_daily_count_if_needed()

            # Check daily trade limit
            if self.daily_trade_count >= self.max_daily_trades:
                self.logger.info(f"🧠 SMART MONEY | {self.symbol} | ❌ DAILY LIMIT REACHED | Trades today: {self.daily_trade_count}/{self.max_daily_trades}")
                return None

            # Check session filter
            if not self._is_trading_session_active():
                current_session = self._get_current_session()
                self.logger.info(f"🧠 SMART MONEY | {self.symbol} | ⏰ SESSION FILTER | Current: {current_session} | Allowed: {self.allowed_sessions} | Status: INACTIVE")
                return None

            # Extract price and volume data
            highs = [float(kline[2]) for kline in klines]
            lows = [float(kline[3]) for kline in klines]
            closes = [float(kline[4]) for kline in klines]
            volumes = [float(kline[5]) for kline in klines]

            self.logger.info(f"🧠 SMART MONEY | {self.symbol} | 🔍 SCANNING FOR LIQUIDITY SWEEPS | Price: ${current_price:.4f}")

            # Step 1: Identify liquidity zones (swing highs/lows)
            swing_highs, swing_lows = self._identify_liquidity_zones(highs, lows)
            
            if not swing_highs and not swing_lows:
                self.logger.info(f"🧠 SMART MONEY | {self.symbol} | 📊 NO SIGNIFICANT LIQUIDITY ZONES | Lookback: {self.swing_lookback_period} candles")
                return None

            self.logger.info(f"🧠 SMART MONEY | {self.symbol} | 🎯 LIQUIDITY ZONES FOUND | Swing Highs: {len(swing_highs)} | Swing Lows: {len(swing_lows)}")

            # Step 2: Check for recent liquidity sweeps
            sweep_signal = self._detect_liquidity_sweep(
                highs, lows, closes, volumes, swing_highs, swing_lows, current_price
            )

            if not sweep_signal:
                self.logger.info(f"🧠 SMART MONEY | {self.symbol} | 🔍 NO LIQUIDITY SWEEP DETECTED | Continuing to monitor...")
                return None

            # Step 3: Confirm with volume spike
            if not self._confirm_volume_spike(volumes):
                self.logger.info(f"🧠 SMART MONEY | {self.symbol} | 📊 VOLUME CONFIRMATION FAILED | Recent volume too low for liquidity hunt")
                return None

            # Step 4: Check trend filter if enabled
            if self.trend_filter_enabled:
                trend_direction = self._get_trend_direction(closes)
                if not self._is_signal_aligned_with_trend(sweep_signal, trend_direction):
                    self.logger.info(f"🧠 SMART MONEY | {self.symbol} | 📈 TREND FILTER | Signal: {sweep_signal} | Trend: {trend_direction} | ❌ NOT ALIGNED")
                    return None
                else:
                    self.logger.info(f"🧠 SMART MONEY | {self.symbol} | 📈 TREND FILTER | Signal: {sweep_signal} | Trend: {trend_direction} | ✅ ALIGNED")

            # Step 5: Generate trading signal
            signal = self._generate_trading_signal(sweep_signal, current_price, highs, lows)
            
            if signal:
                self.daily_trade_count += 1
                self.logger.info(f"🧠 SMART MONEY | {self.symbol} | ✅ LIQUIDITY SWEEP SIGNAL GENERATED | Direction: {sweep_signal} | Entry: ${signal.entry_price:.4f}")
                self.logger.info(f"🧠 SMART MONEY | {self.symbol} | 📊 TRADE COUNT | Today: {self.daily_trade_count}/{self.max_daily_trades}")
                
            return signal

        except Exception as e:
            self.logger.error(f"🧠 SMART MONEY | {self.symbol} | ❌ ERROR in market analysis: {e}")
            return None

    def _identify_liquidity_zones(self, highs: List[float], lows: List[float]) -> tuple:
        """Identify swing highs and lows where liquidity is likely to be hunted"""
        try:
            swing_highs = []
            swing_lows = []
            
            # More sensitive swing detection - only need 1 candle on each side
            for i in range(1, len(highs) - 1):
                if highs[i] > highs[i-1] and highs[i] > highs[i+1]:
                    swing_highs.append({'price': highs[i], 'index': i})

            for i in range(1, len(lows) - 1):
                if lows[i] < lows[i-1] and lows[i] < lows[i+1]:
                    swing_lows.append({'price': lows[i], 'index': i})

            # Filter by minimum distance to avoid noise
            swing_highs = self._filter_swing_points_by_distance(swing_highs, highs[-1])
            swing_lows = self._filter_swing_points_by_distance(swing_lows, highs[-1])

            # Keep only recent swings within lookback period
            recent_start = max(0, len(highs) - self.swing_lookback_period)
            swing_highs = [s for s in swing_highs if s['index'] >= recent_start]
            swing_lows = [s for s in swing_lows if s['index'] >= recent_start]

            return swing_highs, swing_lows

        except Exception as e:
            self.logger.error(f"Error identifying liquidity zones: {e}")
            return [], []

    def _filter_swing_points_by_distance(self, swing_points: List[Dict], current_price: float) -> List[Dict]:
        """Filter swing points that are too close to current price"""
        try:
            filtered_points = []
            min_distance = current_price * (self.min_swing_distance_pct / 100)
            
            for point in swing_points:
                if abs(point['price'] - current_price) >= min_distance:
                    filtered_points.append(point)
                    
            return filtered_points
        except Exception:
            return swing_points

    def _detect_liquidity_sweep(self, highs: List[float], lows: List[float], closes: List[float], 
                              volumes: List[float], swing_highs: List[Dict], swing_lows: List[Dict], 
                              current_price: float) -> Optional[str]:
        """Detect if a liquidity sweep has occurred"""
        try:
            recent_candles = min(self.reversion_candles, len(closes) - 1)
            
            # Check for sweep of swing lows (hunt for long stop losses)
            for swing_low in swing_lows[-3:]:  # Check last 3 swing lows
                sweep_level = swing_low['price']
                sweep_threshold = sweep_level * (1 - self.sweep_threshold_pct / 100)
                
                # Check if price pierced below swing low in recent candles
                for i in range(len(lows) - recent_candles, len(lows)):
                    if i >= 0 and lows[i] <= sweep_threshold:
                        # Check if price recovered (closed back above swing low)
                        recovery_candles = 0
                        for j in range(i + 1, min(i + self.reversion_candles + 1, len(closes))):
                            if j < len(closes) and closes[j] > sweep_level:
                                recovery_candles += 1
                                
                        if recovery_candles >= 1:  # At least 1 candle closed back above
                            self.logger.info(f"🧠 SMART MONEY | {self.symbol} | 🎯 LOW SWEEP DETECTED | Level: ${sweep_level:.4f} | Pierce: ${lows[i]:.4f} | Recovery: {recovery_candles} candles")
                            return "LONG"  # Sweep low suggests bullish reversal

            # Check for sweep of swing highs (hunt for short stop losses)
            for swing_high in swing_highs[-3:]:  # Check last 3 swing highs
                sweep_level = swing_high['price']
                sweep_threshold = sweep_level * (1 + self.sweep_threshold_pct / 100)
                
                # Check if price pierced above swing high in recent candles
                for i in range(len(highs) - recent_candles, len(highs)):
                    if i >= 0 and highs[i] >= sweep_threshold:
                        # Check if price recovered (closed back below swing high)
                        recovery_candles = 0
                        for j in range(i + 1, min(i + self.reversion_candles + 1, len(closes))):
                            if j < len(closes) and closes[j] < sweep_level:
                                recovery_candles += 1
                                
                        if recovery_candles >= 1:  # At least 1 candle closed back below
                            self.logger.info(f"🧠 SMART MONEY | {self.symbol} | 🎯 HIGH SWEEP DETECTED | Level: ${sweep_level:.4f} | Pierce: ${highs[i]:.4f} | Recovery: {recovery_candles} candles")
                            return "SHORT"  # Sweep high suggests bearish reversal

            return None

        except Exception as e:
            self.logger.error(f"Error detecting liquidity sweep: {e}")
            return None

    def _confirm_volume_spike(self, volumes: List[float]) -> bool:
        """Confirm liquidity sweep with volume spike"""
        try:
            if len(volumes) < 20:
                return False
                
            recent_volume = volumes[-1]
            avg_volume = sum(volumes[-20:-1]) / 19  # Average of previous 19 candles
            
            volume_multiplier = recent_volume / avg_volume if avg_volume > 0 else 0
            
            is_spike = volume_multiplier >= self.volume_spike_multiplier
            
            self.logger.info(f"🧠 SMART MONEY | {self.symbol} | 📊 VOLUME ANALYSIS | Recent: {recent_volume:.0f} | Avg: {avg_volume:.0f} | Multiplier: {volume_multiplier:.1f}x | Required: {self.volume_spike_multiplier}x | {'✅ CONFIRMED' if is_spike else '❌ INSUFFICIENT'}")
            
            return is_spike

        except Exception as e:
            self.logger.error(f"Error confirming volume spike: {e}")
            return False

    def _get_trend_direction(self, closes: List[float]) -> str:
        """Determine higher timeframe trend direction"""
        try:
            if len(closes) < 50:
                return "NEUTRAL"
                
            sma_20 = sum(closes[-20:]) / 20
            sma_50 = sum(closes[-50:]) / 50
            
            if sma_20 > sma_50 * 1.01:  # 1% buffer
                return "BULLISH"
            elif sma_20 < sma_50 * 0.99:  # 1% buffer
                return "BEARISH"
            else:
                return "NEUTRAL"
                
        except Exception:
            return "NEUTRAL"

    def _is_signal_aligned_with_trend(self, signal: str, trend: str) -> bool:
        """Check if signal aligns with higher timeframe trend"""
        if trend == "NEUTRAL":
            return True
        return (signal == "LONG" and trend == "BULLISH") or (signal == "SHORT" and trend == "BEARISH")

    def _generate_trading_signal(self, direction: str, current_price: float, 
                               highs: List[float], lows: List[float]) -> Optional[TradingSignal]:
        """Generate trading signal with stop loss and take profit"""
        try:
            if direction == "LONG":
                # Long signal after low sweep
                entry_price = current_price
                
                # Stop loss just below recent low
                recent_low = min(lows[-5:])
                stop_loss = recent_low * 0.999  # 0.1% buffer below recent low
                
                # Take profit at 2:1 risk/reward
                risk = entry_price - stop_loss
                take_profit = entry_price + (risk * 2)
                
                self.logger.info(f"🧠 SMART MONEY | {self.symbol} | 📈 LONG SIGNAL | Entry: ${entry_price:.4f} | SL: ${stop_loss:.4f} | TP: ${take_profit:.4f} | Risk: ${risk:.4f}")
                
                return TradingSignal(
                    signal_type=SignalType.BUY,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    symbol=self.symbol,
                    strategy_name=self.name,
                    confidence=0.8
                )
                
            elif direction == "SHORT":
                # Short signal after high sweep
                entry_price = current_price
                
                # Stop loss just above recent high
                recent_high = max(highs[-5:])
                stop_loss = recent_high * 1.001  # 0.1% buffer above recent high
                
                # Take profit at 2:1 risk/reward
                risk = stop_loss - entry_price
                take_profit = entry_price - (risk * 2)
                
                self.logger.info(f"🧠 SMART MONEY | {self.symbol} | 📉 SHORT SIGNAL | Entry: ${entry_price:.4f} | SL: ${stop_loss:.4f} | TP: ${take_profit:.4f} | Risk: ${risk:.4f}")
                
                return TradingSignal(
                    signal_type=SignalType.SELL,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    symbol=self.symbol,
                    strategy_name=self.name,
                    confidence=0.8
                )
                
            return None

        except Exception as e:
            self.logger.error(f"Error generating trading signal: {e}")
            return None

    def _is_trading_session_active(self) -> bool:
        """Check if current time is within allowed trading sessions"""
        if not self.session_filter_enabled:
            return True
            
        current_session = self._get_current_session()
        return current_session in self.allowed_sessions

    def _get_current_session(self) -> str:
        """Get current trading session based on UTC time"""
        try:
            utc_now = datetime.now(pytz.UTC)
            hour = utc_now.hour
            
            # Define session times (UTC)
            if 7 <= hour < 16:  # 7 AM - 4 PM UTC
                return "LONDON"
            elif 13 <= hour < 22:  # 1 PM - 10 PM UTC  
                return "NEW_YORK"
            elif 21 <= hour < 6:  # 9 PM - 6 AM UTC (next day)
                return "ASIAN"
            else:
                return "OVERLAP"
                
        except Exception:
            return "UNKNOWN"

    def _reset_daily_count_if_needed(self):
        """Reset daily trade count if it's a new day"""
        try:
            today = datetime.now().date()
            if self.last_trade_date != today:
                self.daily_trade_count = 0
                self.last_trade_date = today
                self.logger.info(f"🧠 SMART MONEY | {self.symbol} | 🆕 NEW TRADING DAY | Trade count reset")
        except Exception as e:
            self.logger.error(f"Error resetting daily count: {e}")

    def should_exit_position(self, position, current_price: float, klines: List[List]) -> tuple:
        """
        Check if position should be exited based on Smart Money logic
        Returns (should_exit, reason)
        """
        try:
            # Let normal stop loss and take profit handle exits
            # Smart Money strategy relies on precise entry timing rather than complex exit logic
            return False, None
            
        except Exception as e:
            self.logger.error(f"Error in exit logic: {e}")
            return False, None

    def get_strategy_status(self) -> Dict[str, Any]:
        """Get current strategy status for monitoring"""
        return {
            'name': self.name,
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'daily_trades': f"{self.daily_trade_count}/{self.max_daily_trades}",
            'session_filter': 'Enabled' if self.session_filter_enabled else 'Disabled',
            'allowed_sessions': self.allowed_sessions,
            'current_session': self._get_current_session(),
            'trend_filter': 'Enabled' if self.trend_filter_enabled else 'Disabled',
            'parameters': {
                'swing_lookback': self.swing_lookback_period,
                'sweep_threshold': f"{self.sweep_threshold_pct}%",
                'reversion_candles': self.reversion_candles,
                'volume_multiplier': f"{self.volume_spike_multiplier}x",
                'min_swing_distance': f"{self.min_swing_distance_pct}%"
            }
        }
