import pandas as pd
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

class SignalType(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"

@dataclass
class TradingSignal:
    signal_type: SignalType
    entry_price: float
    stop_loss: float
    take_profit: float
    symbol: str = ""  # Add symbol attribute
    confidence: float = 0.0
    reason: str = ""
    strategy_name: str = ""  # Add strategy_name parameter
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

class SignalProcessor:
    """Processes trading signals"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.info("📊 Signal Processor initialized")
    
    def process_signal(self, signal_data: dict) -> dict:
        """Process a trading signal"""
        try:
            self.logger.info(f"📊 Processing signal: {signal_data.get('type', 'unknown')}")
            # Simplified signal processing for testing
            return {
                'processed': True,
                'signal_type': signal_data.get('type', 'UNKNOWN'),
                'confidence': 0.8,
                'timestamp': '2025-07-28T15:00:00.000Z'
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error processing signal: {e}")
            return {'processed': False, 'error': str(e)}
    
    def validate_signal(self, signal_data: dict) -> bool:
        """Validate a trading signal"""
        try:
            required_fields = ['type', 'symbol', 'price']
            return all(field in signal_data for field in required_fields)
            
        except Exception as e:
            self.logger.error(f"❌ Error validating signal: {e}")
            return False