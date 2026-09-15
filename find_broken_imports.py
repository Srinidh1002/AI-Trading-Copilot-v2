import ast, os
broken = []
for fn in sorted(os.listdir("src")):
    if not fn.endswith(".py"): continue
    p = os.path.join("src", fn)
    try:
        with open(p, encoding="utf-8") as f:
            tree = ast.parse(f.read())
    except Exception:
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("src."):
                target = node.module[4:].replace(".", os.sep) + ".py"
                full = os.path.join("src", target)
                if not os.path.exists(full):
                    broken.append((fn, node.module, full))
        elif isinstance(node, ast.Import):
            for n in node.names:
                if n.name.startswith("src."):
                    target = n.name[4:].replace(".", os.sep) + ".py"
                    full = os.path.join("src", target)
                    if not os.path.exists(full):
                        broken.append((fn, n.name, full))

print("BROKEN src.* IMPORTS:")
for src_file, mod, missing in broken:
    print(f"  {src_file}: from {mod} -> MISSING {missing}")
if not broken:
    print("  (none)")
