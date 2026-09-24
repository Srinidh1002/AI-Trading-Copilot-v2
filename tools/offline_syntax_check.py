"""Offline syntax check for CI. Portable across OSes and shells.

Walks src/, services/, tools/, tests/ and asserts every .py parses.
No imports, no network, no .env. Exits 0 on success, 1 on any failure.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOTS = ("src", "services", "tools", "tests")


def main() -> int:
    bad = []
    for root_name in ROOTS:
        root = Path(root_name)
        if not root.exists():
            continue
        for p in root.rglob("*.py"):
            if "__pycache__" in p.parts:
                continue
            try:
                ast.parse(p.read_text(encoding="utf-8"))
            except SyntaxError as e:
                bad.append((str(p), e.lineno or 0, e.msg or ""))
            except UnicodeDecodeError as e:
                bad.append((str(p), 0, f"decode: {e}"))
    if bad:
        for path, lineno, msg in bad:
            print(f"SYNTAX {path}:{lineno}: {msg}")
        print(f"SYNTAX_FAIL count={len(bad)}")
        return 1
    print("syntax OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
