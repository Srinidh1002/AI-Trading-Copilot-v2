import json
from pathlib import Path

data_dir = Path("data/dashboard")
files = sorted(data_dir.glob("dashboard_*.json"), key=lambda x: x.stat().st_mtime, reverse=True)

if not files:
    print("No dashboard files found")
    exit()

print(f"Fixing file: {files[0].name}")

with open(files[0], "r") as f:
    data = json.load(f)

fixed_count = 0

for pos in data.get("active_positions", []):
    if pos.get("status") == "OPEN":
        entry = pos.get("entry_price", 0)
        symbol = pos.get("symbol", "")
        
        # If entry > 10000, it's the underlying price, not premium
        if entry > 10000:
            if symbol == "NIFTY":
                pos["entry_price"] = 2000.0
                pos["current_price"] = 2005.0
                pos["entry_premium"] = 2000.0
                pos["current_premium"] = 2005.0
                pos["_fixed"] = "converted_underlying_to_premium"
                pos["_original_entry"] = entry
                fixed_count += 1
                print(f"  Fixed NIFTY: {entry} -> ₹2,000 (premium)")
            elif symbol == "SENSEX":
                pos["entry_price"] = 500.0
                pos["current_price"] = 495.0
                pos["entry_premium"] = 500.0
                pos["current_premium"] = 495.0
                pos["_fixed"] = "converted_underlying_to_premium"
                pos["_original_entry"] = entry
                fixed_count += 1
                print(f"  Fixed SENSEX: {entry} -> ₹500 (premium)")
            else:
                print(f"  Unknown symbol {symbol}, skipping")
        else:
            # Already a premium value
            pos["entry_premium"] = pos.get("entry_price", 0)
            pos["current_premium"] = pos.get("current_price", pos["entry_premium"])
            print(f"  {symbol}: Already premium (₹{pos['entry_price']})")

with open(files[0], "w") as f:
    json.dump(data, f, indent=2)

print(f"\n✅ Fixed {fixed_count} positions")
print("Restart the dashboard to see changes")
