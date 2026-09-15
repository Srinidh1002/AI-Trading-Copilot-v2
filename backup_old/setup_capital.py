# setup_capital.py
# Run this first to set up deployed capital

import json
from pathlib import Path

print("=" * 60)
print("💰 AI TRADING COPILOT - CAPITAL SETUP")
print("=" * 60)
print("")
print("This will configure your deployed capital for live trading.")
print("")

# Get capital input
try:
    capital = float(input("Enter your deployed capital (in INR): ₹"))
    if capital <= 0:
        print("❌ Capital must be greater than 0")
        exit(1)
    
    # Load existing config
    config_path = Path("config/deployment_config.json")
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = json.load(f)
    else:
        config = {}
    
    # Update capital
    config['deployed_capital'] = capital
    
    # Save config
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print("")
    print("✅ Capital configured successfully!")
    print(f"💰 Deployed Capital: ₹{capital:,.2f}")
    print("")
    print("📊 Position Sizing:")
    print(f"   NIFTY Lot Size: 50")
    print(f"   SENSEX Lot Size: 25")
    print(f"   Risk per Trade: {config.get('risk_per_trade', 2)}%")
    print(f"   Max Lots per Trade: {config.get('max_lots_per_trade', 5)}")
    print("")
    print("✅ To start trading, run: python run_advanced_trading.py")
    
except ValueError:
    print("❌ Please enter a valid number")
    exit(1)
