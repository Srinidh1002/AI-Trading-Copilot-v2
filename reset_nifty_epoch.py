"""Clean epoch reset - NIFTY.

Moves old NIFTY experimental state + ledgers to _archived/.
Does NOT touch MCX or SENSEX files.
Does NOT delete anything - pure archive + move.
"""
import os, json, shutil
from datetime import datetime

ARCHIVE_DIR = f"data/paper_trades/_archived_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
os.makedirs(ARCHIVE_DIR, exist_ok=True)

FILES_TO_ARCHIVE = [
    "data/paper_trades/nifty_experimental.json",
    "data/paper_trades/nifty_outcomes.jsonl",
    "data/paper_trades/nifty_predictions.jsonl",
    "data/paper_trades/nifty_state.json",       # in case it exists
    "data/paper_trades/nifty_decisions.jsonl",  # in case it exists
]

moved = []
for f in FILES_TO_ARCHIVE:
    if os.path.exists(f):
        dest = os.path.join(ARCHIVE_DIR, os.path.basename(f))
        shutil.move(f, dest)
        moved.append((f, dest))
        print(f"  archived: {f} -> {dest}")
    else:
        print(f"  skipped (not present): {f}")

# Write a manifest for audit
manifest = {
    "reset_at": datetime.now().isoformat(),
    "reason": "N1 defect patches D1-D3,D5-D11 change strategy behavior (D9 Design B trail). Existing sessions pre-date certification_eligible field. Per RULE 22, new strategy = new epoch.",
    "archived_files": [f for f, _ in moved],
    "archive_dir": ARCHIVE_DIR,
}
with open(os.path.join(ARCHIVE_DIR, "MANIFEST.json"), "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)

print()
print(f"Archive dir: {ARCHIVE_DIR}")
print(f"Files archived: {len(moved)}")
print()
print("NIFTY epoch is now clean. Bot will create fresh state on next save_state().")
