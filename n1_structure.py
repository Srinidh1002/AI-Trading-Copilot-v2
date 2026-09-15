import ast, os, re

path = "src/target_focused_bot.py"
with open(path, encoding="utf-8") as f:
    src = f.read()
tree = ast.parse(src)

print("=" * 90)
print(f"STRUCTURAL DUMP — {path}")
print(f"Lines: {len(src.splitlines())}    Bytes: {len(src)}")
print("=" * 90)

# 1. Module-level imports
print("\n--- MODULE-LEVEL IMPORTS ---")
for node in tree.body:
    if isinstance(node, ast.Import):
        for n in node.names:
            print(f"  import {n.name}")
    elif isinstance(node, ast.ImportFrom):
        mod = node.module or "."
        names = ", ".join(a.name for a in node.names)
        print(f"  from {mod} import {names}")

# 2. Module-level constants (assignment at top level)
print("\n--- MODULE-LEVEL CONSTANTS ---")
for node in tree.body:
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        t = node.targets[0]
        if isinstance(t, ast.Name):
            val = ast.unparse(node.value)
            if len(val) > 100:
                val = val[:100] + "..."
            print(f"  {t.id} = {val}")

# 3. Classes and their methods
print("\n--- CLASSES ---")
for node in tree.body:
    if isinstance(node, ast.ClassDef):
        print(f"\n  class {node.name}({', '.join(ast.unparse(b) for b in node.bases)}):")
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                args = [a.arg for a in item.args.args]
                print(f"      def {item.name}({', '.join(args)})")
