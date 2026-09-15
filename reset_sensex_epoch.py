import os, shutil
from datetime import datetime

# Find the archive dir created just now
import glob
dirs = sorted(glob.glob("data/paper_trades/_archived_*"))
arch = dirs[-1] if dirs else None
if not arch:
    raise SystemExit("No archive dir found - run reset_nifty_epoch.py first")

for f in ["data/paper_trades/sensex_predictions.jsonl",
          "data/paper_trades/sensex_experimental.json",
          "data/paper_trades/sensex_outcomes.jsonl",
          "data/paper_trades/sensex_state.json"]:
    if os.path.exists(f):
        shutil.move(f, os.path.join(arch, os.path.basename(f)))
        print(f"  archived: {f}")
    else:
        print(f"  skipped (not present): {f}")
print(f"Archive: {arch}")
