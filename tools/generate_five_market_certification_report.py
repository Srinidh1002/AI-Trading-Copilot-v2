#!/usr/bin/env python3
"""Generate the canonical read-only five-market PAPER certification report."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    src = root / "src"
    for value in (str(root), str(src)):
        if value not in sys.path:
            sys.path.insert(0, value)

    from services.reporting.five_market_certification_final_report_v1 import (
        build_five_market_certification_final_report,
    )

    report = build_five_market_certification_final_report(root)
    payload = report.to_dict()
    payload["semantic_hash"] = report.semantic_hash

    text = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False)
    if args.output:
        output = Path(args.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
        print(f"REPORT={output}")
    else:
        print(text)

    print(f"REPORT_HASH={report.semantic_hash}")
    print("REPORT_MODE=READ_ONLY")
    print("BROKER_ORDER_SUBMISSION=FALSE")
    print("LIVE_EXECUTION=FALSE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
