# DEPRECATED: This file is kept for backwards compatibility only
# RSI strategies now use the web dashboard as the single source of truth

import logging

class RSIOversoldConfig:
    """DEPRECATED: Use web dashboard for configuration"""

    @staticmethod
    def get_config():
        """DEPRECATED: Use web dashboard for configuration"""
        logging.getLogger(__name__).warning(
            "DEPRECATED: RSIOversoldConfig.get_config() is deprecated. "
            "Use web dashboard for strategy configuration."
        )

        return {
            'message': 'USE_WEB_DASHBOARD_ONLY',
            'deprecated': True
        }

    @staticmethod
    def update_config(updates):
        """DEPRECATED: Use web dashboard for configuration updates"""
        logging.getLogger(__name__).warning(
            "DEPRECATED: RSIOversoldConfig.update_config() is deprecated. "
            "Use web dashboard for strategy configuration updates."
        )
        return False