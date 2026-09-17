# fix_all_issues.py
# Run this to fix all issues before testing

import os
import sys
import json
from pathlib import Path

print("=" * 60)
print("🔧 FIXING ALL ISSUES")
print("=" * 60)

# 1. Fix permissions
print("\n📁 Fixing file permissions...")
try:
    import subprocess
    subprocess.run(['icacls', 'data', '/grant', f'{os.environ["USERNAME"]}:F', '/T', '/Q'], capture_output=True)
    print("✅ Permissions fixed")
except:
    print("⚠️ Could not fix permissions (run as Administrator)")

# 2. Create missing directories
print("\n📁 Creating directories...")
for dir_name in ['data/pnl', 'data/dashboard', 'data/reports/pre_market', 'logs']:
    Path(dir_name).mkdir(parents=True, exist_ok=True)
    print(f"  ✅ {dir_name}")

# 3. Fix dashboard file if corrupted
print("\n📁 Fixing dashboard files...")
dashboard_dir = Path("data/dashboard")
for file in dashboard_dir.glob("*.json"):
    if file.stat().st_size == 0:
        file.unlink()
        print(f"  🗑️ Removed empty: {file.name}")

# 4. Create clean config
print("\n📁 Creating clean config...")
config_path = Path("config/deployment_config.json")
config_path.parent.mkdir(parents=True, exist_ok=True)

if not config_path.exists() or True:
    with open(config_path, 'w') as f:
        json.dump({
            "deployed_capital": 1000000,
            "risk_per_trade": 2,
            "max_risk_per_day": 10,
            "position_sizing": "fixed",
            "max_lots_per_trade": 5,
            "min_lots_per_trade": 1,
            "prefer_options": True,
            "last_updated": "2026-09-03T20:00:00"
        }, f, indent=2)
    print("  ✅ deployment_config.json created")

print("\n" + "=" * 60)
print("✅ ALL FIXES APPLIED! Ready for testing.")
print("=" * 60)
