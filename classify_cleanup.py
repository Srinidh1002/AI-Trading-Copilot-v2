import ast, os, sys, json

# Roots to analyze (the canonical runners + their entry class)
roots = ["src/target_focused_bot.py"]

# All candidate src/*.py files
src_files = [f for f in os.listdir("src") if f.endswith(".py")]
all_mods = {f[:-3] for f in src_files}

# Build local import graph
import_map = {}  # module_name -> set of local module_names it imports
for fn in src_files:
    p = os.path.join("src", fn)
    mod = fn[:-3]
    imps = set()
    try:
        with open(p, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for n in node.names:
                    base = n.name.split(".")[0]
                    if base in all_mods:
                        imps.add(base)
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.level == 0:
                    base = node.module.split(".")[0]
                    if base in all_mods:
                        imps.add(base)
    except Exception as e:
        imps.add(f"__PARSE_ERR__:{e}")
    import_map[mod] = imps

# Transitive closure from roots
def closure(start):
    seen = set()
    stack = [start]
    while stack:
        m = stack.pop()
        if m in seen: continue
        seen.add(m)
        for dep in import_map.get(m, set()):
            if not dep.startswith("__"): stack.append(dep)
    return seen

reachable = closure("target_focused_bot")

# Classify
classified = {"PRODUCTION_REQUIRED": [], "LEGACY": [], "BACKUP": [], "UNKNOWN": []}
for fn in src_files:
    mod = fn[:-3]
    if ".bak_" in fn or ".backup_" in fn:
        classified["BACKUP"].append(fn)
    elif mod in reachable:
        classified["PRODUCTION_REQUIRED"].append(fn)
    else:
        classified["LEGACY"].append(fn)

# Also check root files
root_files = [f for f in os.listdir(".") if f.endswith(".py")]
root_classified = {"PATCH_SCRATCH": [], "LEGACY_DIAGNOSTIC": [], "OTHER": []}
for fn in root_files:
    if fn in ("run_nifty.py", "run_sensex.py"):
        continue
    low = fn.lower()
    if any(p in low for p in ("patch_", "verify_", "read_", "wire_",
                              "s7_inspect", "s7a_", "s7_stage", "run_s7_")):
        root_classified["PATCH_SCRATCH"].append(fn)
    elif any(p in low for p in ("check_", "test_", "fix_", "show_", "smoke_",
                                 "inspect", "diag", "probe", "monitor_")):
        root_classified["LEGACY_DIAGNOSTIC"].append(fn)
    else:
        root_classified["OTHER"].append(fn)

print("=" * 90)
print("TRANSITIVE IMPORT AUDIT — target_focused_bot.py")
print("=" * 90)
print(f"Reachable modules from target_focused_bot.py: {len(reachable)}")
print(f"Total src/*.py files: {len(src_files)}")
print()
print("--- PRODUCTION_REQUIRED (imported transitively — MUST NOT DELETE) ---")
for f in sorted(classified["PRODUCTION_REQUIRED"]):
    print(f"  {f}")
print()
print(f"--- LEGACY src/*.py (NOT reachable — safe to delete) --- [{len(classified['LEGACY'])}]")
for f in sorted(classified["LEGACY"]):
    print(f"  {f}")
print()
print(f"--- BACKUP files --- [{len(classified['BACKUP'])}]")
for f in sorted(classified["BACKUP"]):
    print(f"  {f}")
print()
print(f"--- ROOT: PATCH/SCRATCH scripts --- [{len(root_classified['PATCH_SCRATCH'])}]")
print(f"--- ROOT: LEGACY DIAGNOSTIC scripts --- [{len(root_classified['LEGACY_DIAGNOSTIC'])}]")
print(f"--- ROOT: OTHER --- [{len(root_classified['OTHER'])}]")
for f in sorted(root_classified["OTHER"]):
    print(f"  {f}")

# Save JSON for the delete step
with open("_cleanup_plan.json", "w", encoding="utf-8") as f:
    json.dump({"src_legacy": sorted(classified["LEGACY"]),
               "src_backup": sorted(classified["BACKUP"]),
               "src_production": sorted(classified["PRODUCTION_REQUIRED"]),
               "root_patch": sorted(root_classified["PATCH_SCRATCH"]),
               "root_diag": sorted(root_classified["LEGACY_DIAGNOSTIC"]),
               "root_other": sorted(root_classified["OTHER"])},
              f, indent=2)
print("\nWrote _cleanup_plan.json")
