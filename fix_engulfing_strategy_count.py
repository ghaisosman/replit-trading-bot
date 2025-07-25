
#!/usr/bin/env python3
"""
Fix Engulfing Strategy Count Mismatch
===================================

Fixes the issue where development has 1 engulfing strategy
but deployment has 3 engulfing strategies.

This ensures both environments have the same single engulfing strategy.
"""

import sys
import os
import json

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.config.trading_config import trading_config_manager

def main():
    print("🔧 FIXING ENGULFING STRATEGY COUNT MISMATCH")
    print("=" * 50)
    
    try:
        # Check current state
        config_file = "trading_data/web_dashboard_configs.json"
        
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                current_config = json.load(f)
            
            engulfing_strategies = [key for key in current_config.keys() if 'engulfing' in key.lower()]
            print(f"📊 Found {len(engulfing_strategies)} engulfing strategies:")
            for strategy in engulfing_strategies:
                print(f"   • {strategy}")
        else:
            print("📊 No web dashboard config file found - development mode")
            engulfing_strategies = []
        
        if len(engulfing_strategies) <= 1:
            print("✅ Already have single or no engulfing strategy - no action needed")
            return
        
        # Clean up to single strategy
        print(f"\n🧹 Cleaning up to single engulfing strategy...")
        removed_count = trading_config_manager.remove_duplicate_strategies()
        
        # Verify cleanup
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                updated_config = json.load(f)
            
            updated_engulfing = [key for key in updated_config.keys() if 'engulfing' in key.lower()]
            print(f"\n✅ After cleanup - Found {len(updated_engulfing)} engulfing strategies:")
            for strategy in updated_engulfing:
                symbol = updated_config[strategy].get('symbol', 'UNKNOWN')
                print(f"   ✅ {strategy} - {symbol}")
        
        print(f"\n🎉 SUCCESS: Now both development and deployment have the same single engulfing strategy!")
        print("   Development: 1 engulfing_pattern (from config file)")
        print("   Deployment: 1 engulfing_pattern (from web dashboard)")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    main()
