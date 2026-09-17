import os, json, glob

KEEP_ROOT = {
    "run_nifty.py",
    "run_sensex.py",
    "hash_official.py",
    "check_counters.py",
    "write_exec_config.py",
    "stage0a_bypass_audit.py",
    "classify_cleanup.py",
    "cleanup_repository.py",
}
KEEP_PREFIX = ("test_mcx_",)

plan = json.load(open("_cleanup_plan.json", encoding="utf-8"))
to_delete = []

# 1. Root scratch/diagnostic/other
for cat in ("root_patch", "root_diag", "root_other"):
    for f in plan.get(cat, []):
        if f in KEEP_ROOT: continue
        if any(f.startswith(p) for p in KEEP_PREFIX): continue
        to_delete.append(f)

# 2. src legacy modules
for f in plan.get("src_legacy", []):
    to_delete.append(os.path.join("src", f))

# 3. src backup files (.bak_*, .backup_*)
for pat in ("src/*.bak_*", "src/*.backup_*", "src/*.py.bak*"):
    to_delete += glob.glob(pat)

# 4. root backup files
to_delete += glob.glob("*.bak_*")
to_delete += glob.glob("*.backup_*")

# 5. MCX Section-7 probe scripts (user explicit)
for pat in ("run_s7_*.py", "s7a_preflight.py", "s7_inspect*.py", "verify_s7_*.py",
            "ws_minrepro.py", "ws_probe_*.py", "ws_diag_error.py",
            "smoke_test_phase_a.py"):
    to_delete += glob.glob(pat)

# Dedup + only-existing
to_delete = sorted({f for f in to_delete if os.path.exists(f)})

print(f"Will delete {len(to_delete)} files")
print()

# Group by category for display
groups = {}
for f in to_delete:
    d = os.path.dirname(f) or "."
    groups.setdefault(d, []).append(os.path.basename(f))
for d, files in sorted(groups.items()):
    print(f"  {d}/ — {len(files)} files")

# Execute
deleted = 0
failed = []
for f in to_delete:
    try:
        os.remove(f)
        deleted += 1
    except Exception as e:
        failed.append((f, str(e)))

print()
print(f"DELETED: {deleted}")
if failed:
    print(f"FAILED: {len(failed)}")
    for f, e in failed[:10]:
        print(f"  {f}: {e}")
else:
    print("All deletions succeeded.")

# Also remove Day1_Snapshots folder if empty
if os.path.isdir("Day1_Snapshots"):
    try:
        files = os.listdir("Day1_Snapshots")
        if not files:
            os.rmdir("Day1_Snapshots")
            print("Removed empty Day1_Snapshots/")
        else:
            print(f"Day1_Snapshots/ still has {len(files)} items — leaving alone")
    except Exception as e:
        print(f"Day1_Snapshots removal err: {e}")
