
#!/usr/bin/env python3
"""
Trading Configuration Manager
Use this script to easily adjust trading parameters for all strategies
"""

from src.config.trading_config import trading_config_manager

def display_current_config():
    """Display current configuration for all strategies"""
    print("\n🔧 CURRENT TRADING CONFIGURATION")
    print("=" * 50)

    print(f"\n📊 DEFAULT PARAMETERS:")
    defaults = trading_config_manager.default_params
    print(f"Symbol: {defaults.symbol}")
    print(f"Margin: ${defaults.margin}")
    print(f"Leverage: {defaults.leverage}x")
    print(f"Timeframe: {defaults.timeframe}")
    print(f"Stop Loss: {defaults.max_loss_pct}% of margin")

    print(f"\n🎯 STRATEGY OVERRIDES:")
    for strategy, overrides in trading_config_manager.strategy_overrides.items():
        print(f"\n{strategy.upper()}:")
        for param, value in overrides.items():
            if param == 'leverage':
                print(f"  {param}: {value}x")
            elif param == 'margin':
                print(f"  {param}: ${value}")
            else:
                print(f"  {param}: {value}")

def update_strategy_config():
    """Interactive strategy configuration update"""
    print("\n🔧 STRATEGY CONFIGURATION UPDATE")
    print("Available strategies:", list(trading_config_manager.strategy_overrides.keys()))

    strategy = input("Enter strategy name (or 'default' for default params): ")

    if strategy == 'default':
        print("\nUpdating default parameters...")
        symbol = input(f"Symbol [{trading_config_manager.default_params.symbol}]: ") or None
        margin = input(f"Margin [{trading_config_manager.default_params.margin}]: ") or None
        leverage = input(f"Leverage [{trading_config_manager.default_params.leverage}]: ") or None
        timeframe = input(f"Timeframe [{trading_config_manager.default_params.timeframe}]: ") or None

        updates = {}
        if symbol: updates['symbol'] = symbol
        if margin: updates['margin'] = float(margin)
        if leverage: updates['leverage'] = int(leverage)
        if timeframe: updates['timeframe'] = timeframe

        trading_config_manager.update_default_params(updates)
        print("✅ Default parameters updated!")

    elif strategy in trading_config_manager.strategy_overrides:
        print(f"\nUpdating {strategy} configuration...")
        current = trading_config_manager.strategy_overrides[strategy]

        symbol = input(f"Symbol [{current.get('symbol', 'N/A')}]: ") or None
        margin = input(f"Margin [{current.get('margin', 'N/A')}]: ") or None
        leverage = input(f"Leverage [{current.get('leverage', 'N/A')}]: ") or None
        timeframe = input(f"Timeframe [{current.get('timeframe', 'N/A')}]: ") or None

        updates = {}
        if symbol: updates['symbol'] = symbol
        if margin: updates['margin'] = float(margin)
        if leverage: updates['leverage'] = int(leverage)
        if timeframe: updates['timeframe'] = timeframe

        trading_config_manager.update_strategy_params(strategy, updates)
        print(f"✅ {strategy} configuration updated!")
    else:
        print("❌ Invalid strategy name")

def main():
    print("🤖 TRADING BOT CONFIGURATION MANAGER")
    print("=" * 40)

    while True:
        print("\nOptions:")
        print("1. Display current configuration")
        print("2. Update strategy configuration") 
        print("3. Quick setup examples")
        print("4. Exit")

        choice = input("\nSelect option (1-4): ")

        if choice == "1":
            display_current_config()
        elif choice == "2":
            update_strategy_config()
        elif choice == "3":
            show_examples()
        elif choice == "4":
            break
        else:
            print("Invalid option")

def show_examples():
    """Show configuration examples"""
    print("\n💡 QUICK SETUP EXAMPLES")
    print("=" * 30)
    print("\n📈 Conservative Setup:")
    print("- ETHUSDT, $25 margin, 3x leverage, 15m timeframe")
    print("\n🚀 Aggressive Setup:")  
    print("- BTCUSDT, $100 margin, 10x leverage, 5m timeframe")
    print("\n🎯 Scalping Setup:")
    print("- Multiple pairs, $50 margin, 5x leverage, 1m timeframe")

    apply = input("\nApply a setup? (conservative/aggressive/scalping/no): ")

    if apply == "conservative":
        trading_config_manager.update_default_params({
            'symbol': 'ETHUSDT',
            'margin': 25.0,
            'leverage': 3,
            'timeframe': '15m'
        })
        print("✅ Conservative setup applied!")
    elif apply == "aggressive":
        trading_config_manager.update_default_params({
            'symbol': 'BTCUSDT', 
            'margin': 100.0,
            'leverage': 10,
            'timeframe': '5m'
        })
        print("✅ Aggressive setup applied!")
    elif apply == "scalping":
        trading_config_manager.update_default_params({
            'margin': 50.0,
            'leverage': 5,
            'timeframe': '1m'
        })
        print("✅ Scalping setup applied!")

if __name__ == "__main__":
    main()
