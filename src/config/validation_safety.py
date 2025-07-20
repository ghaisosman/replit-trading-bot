
"""
Validation Safety System
Prevents critical configuration errors that could cause bot failures
"""

import logging
from typing import Dict, Any, Optional, Tuple

class ValidationSafety:
    """Safety controls for parameter validation"""
    
    def __init__(self):
        self.lock_mechanism_enabled = True
        self.emergency_fallback = True
        self.validation_rules = self._initialize_validation_rules()
        self.logger = logging.getLogger(__name__)
    
    def _initialize_validation_rules(self) -> Dict[str, Dict[str, Any]]:
        """Initialize validation rules for all parameters"""
        return {
            # Critical parameters that CANNOT be zero
            'margin': {
                'min_value': 1.0,
                'max_value': 10000.0,
                'default': 50.0,
                'zero_allowed': False,
                'error_message': 'Margin cannot be zero - this would prevent any trading',
                'suggestion': 'Standard margin is 50 USDT'
            },
            'leverage': {
                'min_value': 1,
                'max_value': 125,
                'default': 5,
                'zero_allowed': False,
                'error_message': 'Leverage cannot be zero - this would make position size zero',
                'suggestion': 'Safe leverage is 5x'
            },
            'rsi_period': {
                'min_value': 2,
                'max_value': 50,
                'default': 14,
                'zero_allowed': False,
                'error_message': 'RSI period cannot be zero - this would break RSI calculation',
                'suggestion': 'Standard RSI period is 14'
            },
            'macd_fast': {
                'min_value': 1,
                'max_value': 20,
                'default': 12,
                'zero_allowed': False,
                'error_message': 'MACD fast period cannot be zero - this would break MACD calculation',
                'suggestion': 'Standard MACD fast period is 12'
            },
            'macd_slow': {
                'min_value': 2,
                'max_value': 50,
                'default': 26,
                'zero_allowed': False,
                'error_message': 'MACD slow period cannot be zero - this would break MACD calculation',
                'suggestion': 'Standard MACD slow period is 26'
            },
            'macd_signal': {
                'min_value': 1,
                'max_value': 15,
                'default': 9,
                'zero_allowed': False,
                'error_message': 'MACD signal period cannot be zero - this would break signal calculation',
                'suggestion': 'Standard MACD signal period is 9'
            },
            'assessment_interval': {
                'min_value': 5,
                'max_value': 300,
                'default': 60,
                'zero_allowed': False,
                'error_message': 'Assessment interval cannot be zero - bot would never check markets',
                'suggestion': 'Standard assessment interval is 60 seconds'
            },
            'confirmation_candles': {
                'min_value': 1,
                'max_value': 5,
                'default': 2,
                'zero_allowed': False,
                'error_message': 'Confirmation candles cannot be zero - no signal confirmation would occur',
                'suggestion': 'Standard confirmation is 2 candles'
            },
            'cooldown_period': {
                'min_value': 30,
                'max_value': 3600,
                'default': 300,
                'zero_allowed': False,
                'error_message': 'Cooldown period cannot be zero - could cause rapid fire trading',
                'suggestion': 'Safe cooldown is 300 seconds (5 minutes)'
            },
            
            # Parameters where zero IS allowed (to disable features)
            'partial_tp_pnl_threshold': {
                'min_value': 0.0,
                'max_value': 1000.0,
                'default': 0.0,
                'zero_allowed': True,
                'zero_meaning': 'Partial take profit disabled'
            },
            'partial_tp_position_percentage': {
                'min_value': 0.0,
                'max_value': 99.0,
                'default': 0.0,
                'zero_allowed': True,
                'zero_meaning': 'Partial take profit disabled'
            },
            'min_volume': {
                'min_value': 0.0,
                'max_value': 1000000000.0,
                'default': 1000000.0,
                'zero_allowed': True,
                'zero_meaning': 'Volume filter disabled'
            }
        }
    
    def validate_parameter(self, param_name: str, value: Any) -> Tuple[bool, Any, Optional[str]]:
        """
        Validate a single parameter value
        Returns: (is_valid, corrected_value, error_message)
        """
        if not self.lock_mechanism_enabled:
            return True, value, None
        
        if param_name not in self.validation_rules:
            # Parameter not in validation rules - allow it
            return True, value, None
        
        rule = self.validation_rules[param_name]
        
        try:
            # Convert to appropriate type
            if isinstance(rule['default'], int):
                value = int(value)
            else:
                value = float(value)
        except (ValueError, TypeError):
            error_msg = f"Invalid value type for {param_name}"
            return False, rule['default'], error_msg
        
        # Check for zero
        if value == 0 and not rule['zero_allowed']:
            error_msg = f"🚫 {rule['error_message']}. {rule['suggestion']}"
            self.logger.warning(f"VALIDATION BLOCKED: {param_name} = 0 not allowed")
            return False, rule['default'], error_msg
        
        # Check range
        if value < rule['min_value'] or value > rule['max_value']:
            if rule['zero_allowed'] and value == 0:
                # Zero is explicitly allowed for this parameter
                return True, value, None
            
            error_msg = f"🚫 {param_name} must be between {rule['min_value']} and {rule['max_value']}"
            corrected_value = max(rule['min_value'], min(rule['max_value'], value))
            return False, corrected_value, error_msg
        
        return True, value, None
    
    def validate_multiple_parameters(self, updates: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, str]]:
        """
        Validate multiple parameters at once
        Returns: (validated_updates, error_messages)
        """
        validated_updates = {}
        error_messages = {}
        
        for param_name, value in updates.items():
            is_valid, corrected_value, error_msg = self.validate_parameter(param_name, value)
            
            if is_valid:
                validated_updates[param_name] = corrected_value
            else:
                validated_updates[param_name] = corrected_value
                error_messages[param_name] = error_msg
                
                # Log the correction
                self.logger.warning(f"🔧 VALIDATION CORRECTION: {param_name} = {value} → {corrected_value}")
        
        return validated_updates, error_messages
    
    def get_parameter_info(self, param_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a parameter's validation rules"""
        return self.validation_rules.get(param_name)
    
    def emergency_disable_locks(self):
        """Emergency disable all lock mechanisms"""
        self.lock_mechanism_enabled = False
        self.logger.warning("🚨 EMERGENCY: Validation locks disabled - using auto-correction")
    
    def enable_locks(self, enabled: bool = True):
        """Enable/disable validation locks"""
        self.lock_mechanism_enabled = enabled
        status = "enabled" if enabled else "disabled"
        self.logger.info(f"🔒 Validation locks {status}")

# Global validation safety instance
validation_safety = ValidationSafety()
