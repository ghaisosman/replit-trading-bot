
#!/usr/bin/env python3
"""
Clear Ghost Anomalies Script
Remove all ghost anomalies that are blocking strategies
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.execution_engine.anomaly_detector import AnomalyDatabase, AnomalyType, AnomalyStatus
from datetime import datetime

def clear_ghost_anomalies():
    """Clear all ghost anomalies from the database"""
    print("🧹 CLEARING GHOST ANOMALIES")
    print("=" * 40)
    
    try:
        # Initialize anomaly database
        anomaly_db = AnomalyDatabase()
        
        # Get all active anomalies
        all_anomalies = anomaly_db.anomalies.copy()
        ghost_count = 0
        cleared_count = 0
        
        for anomaly_id, anomaly in all_anomalies.items():
            if anomaly.type == AnomalyType.GHOST and anomaly.status == AnomalyStatus.ACTIVE:
                ghost_count += 1
                print(f"🔍 Found ghost anomaly: {anomaly_id}")
                print(f"   Strategy: {anomaly.strategy_name}")
                print(f"   Symbol: {anomaly.symbol}")
                print(f"   Quantity: {anomaly.quantity}")
                
                # Clear the ghost anomaly
                anomaly_db.update_anomaly(anomaly_id, 
                                        status=AnomalyStatus.CLEARED,
                                        cleared_at=datetime.now())
                cleared_count += 1
                print(f"   ✅ Cleared ghost anomaly")
        
        print(f"\n🎯 SUMMARY:")
        print(f"   👻 Ghost anomalies found: {ghost_count}")
        print(f"   🧹 Ghost anomalies cleared: {cleared_count}")
        
        if cleared_count > 0:
            print(f"\n✅ SUCCESS: All ghost anomalies cleared!")
            print(f"💡 Strategies should no longer be blocked by ghost detection")
        else:
            print(f"\n✅ NO GHOST ANOMALIES: Database is clean")
            
    except Exception as e:
        print(f"❌ Error clearing ghost anomalies: {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    clear_ghost_anomalies()
