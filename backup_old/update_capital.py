# update_capital.py
# Update deployed capital without rerunning full setup

import json
from pathlib import Path

def update_capital():
    print("=" * 60)
    print("💰 UPDATE DEPLOYED CAPITAL")
    print("=" * 60)
    print("")
    print("Current Configuration:")
    
    config_path = Path("config/deployment_config.json")
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = json.load(f)
        print(f"Current Capital: ₹{config.get('deployed_capital', 0):,.2f}")
        print(f"Risk per Trade: {config.get('risk_per_trade', 2)}%")
        print(f"Max Lots: {config.get('max_lots_per_trade', 5)}")
        print("")
    else:
        config = {}
        print("No existing config found")
        print("")
    
    try:
        new_capital = input("Enter new deployed capital (in INR, press Enter to keep current): ₹")
        if new_capital.strip():
            new_capital = float(new_capital)
            if new_capital <= 0:
                print("❌ Capital must be greater than 0")
                return
            config['deployed_capital'] = new_capital
        
        new_risk = input(f"Enter risk per trade % (current: {config.get('risk_per_trade', 2)}%, press Enter to keep): ")
        if new_risk.strip():
            new_risk = float(new_risk)
            if new_risk <= 0 or new_risk > 50:
                print("❌ Risk must be between 0 and 50")
                return
            config['risk_per_trade'] = new_risk
        
        new_lots = input(f"Enter max lots per trade (current: {config.get('max_lots_per_trade', 5)}, press Enter to keep): ")
        if new_lots.strip():
            new_lots = int(new_lots)
            if new_lots <= 0:
                print("❌ Lots must be greater than 0")
                return
            config['max_lots_per_trade'] = new_lots
        
        config['last_updated'] = datetime.now().isoformat()
        
        # Save config
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        print("")
        print("✅ Configuration updated successfully!")
        print(f"💰 Deployed Capital: ₹{config['deployed_capital']:,.2f}")
        print(f"📊 Risk per Trade: {config['risk_per_trade']}%")
        print(f"📊 Max Lots: {config['max_lots_per_trade']}")
        print("")
        print("✅ To start trading, run: start_advanced_system.ps1")
        
    except ValueError as e:
        print(f"❌ Invalid input: {e}")

if __name__ == "__main__":
    from datetime import datetime
    update_capital()
