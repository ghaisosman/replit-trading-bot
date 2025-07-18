
#!/usr/bin/env python3
"""
Strategy Color Viewer
View current strategy color assignments
"""

import json
import os

def display_strategy_colors():
    """Display current strategy color assignments"""
    color_file = 'trading_data/strategy_colors.json'
    
    print("\n🎨 STRATEGY COLOR ASSIGNMENTS")
    print("=" * 50)
    
    if os.path.exists(color_file):
        try:
            with open(color_file, 'r') as f:
                data = json.load(f)
                strategy_colors = data.get('strategy_colors', {})
                active_position_colors = data.get('active_position_colors', {})
            
            if strategy_colors:
                print("\n📊 Current Strategy Colors:")
                for strategy, color_code in strategy_colors.items():
                    # Display the strategy name with its assigned color
                    reset = '\033[0m'
                    print(f"{color_code}  {strategy}{reset} - {color_code}")
                
                print(f"\n✅ Total strategies with colors: {len(strategy_colors)}")
            else:
                print("\n📝 No strategies have been assigned colors yet.")
                print("💡 Colors will be automatically assigned when strategies appear in logs.")
        
        except Exception as e:
            print(f"\n❌ Error reading color file: {e}")
    else:
        print("\n📝 No color assignments file found.")
        print("💡 Colors will be automatically assigned when strategies appear in logs.")

def reset_strategy_colors():
    """Reset all strategy color assignments"""
    color_file = 'trading_data/strategy_colors.json'
    
    if os.path.exists(color_file):
        try:
            os.remove(color_file)
            print("✅ Strategy color assignments reset successfully!")
            print("💡 New colors will be assigned when strategies appear in logs.")
        except Exception as e:
            print(f"❌ Error resetting colors: {e}")
    else:
        print("📝 No color assignments to reset.")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--reset":
        reset_strategy_colors()
    else:
        display_strategy_colors()
        print("\n💡 To reset color assignments, run: python check_strategy_colors.py --reset")
