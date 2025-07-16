
#!/usr/bin/env python3
"""
Clear Orphan Trade Script
Immediately clear the orphan trade that's blocking the RSI strategy
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def clear_orphan_trade():
    """Clear the orphan trade manually"""
    try:
        # Import the bot manager
        from main import bot_manager
        
        if not bot_manager:
            print("❌ Bot manager not available")
            return False
            
        # Clear orphan position from order manager
        if hasattr(bot_manager, 'order_manager') and bot_manager.order_manager:
            strategy_name = "rsi_oversold"
            bot_manager.order_manager.clear_orphan_position(strategy_name)
            print(f"✅ Cleared orphan position for {strategy_name}")
            
            # Also clear from anomaly detector
            if hasattr(bot_manager, 'anomaly_detector'):
                anomaly_id = f"orphan_{strategy_name}_SOLUSDT"
                success = bot_manager.anomaly_detector.clear_anomaly_by_id(anomaly_id, "Manual clear via script")
                if success:
                    print(f"✅ Cleared anomaly {anomaly_id} from database")
                else:
                    print(f"⚠️ Could not find anomaly {anomaly_id} in database")
            
            print("🚀 Strategy should now be available for new trades")
            return True
        else:
            print("❌ Order manager not available")
            return False
            
    except Exception as e:
        print(f"❌ Error clearing orphan trade: {e}")
        return False

if __name__ == "__main__":
    print("🧹 CLEARING ORPHAN TRADE")
    print("=" * 30)
    
    success = clear_orphan_trade()
    
    if success:
        print("\n✅ SUCCESS: Orphan trade cleared!")
        print("💡 The web dashboard should now show no active positions")
        print("🎯 The RSI strategy is now available for new trades")
    else:
        print("\n❌ FAILED: Could not clear orphan trade")
        print("💡 The anomaly system will clear it automatically in ~2 minutes")
