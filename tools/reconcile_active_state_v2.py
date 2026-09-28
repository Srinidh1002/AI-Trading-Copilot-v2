"""Read-only active-state reconciliation CLI — Phase 10 of F15-R1.

Default: dry-run. Writes nothing.

--apply : move proven stale orphans into orphaned_trades atomically.
          Counters and counted_trade_ids never change.

PAPER only. No broker calls. No strategy changes.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from services.paper_orchestration.active_state_reconciler_v2 import (  # noqa: E402
    classify_market,
    reconcile_market_state,
)

MARKETS = ("NIFTY", "SENSEX")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Reconcile same-day stale active trades (Phase 10, PAPER only)"
    )
    ap.add_argument("--repo-root", default=str(REPO_ROOT))
    ap.add_argument(
        "--market",
        choices=list(MARKETS) + ["ALL"],
        default="ALL",
    )
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Move proven orphans. Default is dry-run.",
    )
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    targets = list(MARKETS) if args.market == "ALL" else [args.market]

    reports = []
    for m in targets:
        if args.apply:
            rpt = reconcile_market_state(args.repo_root, m, apply=True)
        else:
            rows = classify_market(args.repo_root, m)
            rpt = {
                "market": m,
                "applied": False,
                "classifications": rows,
                "moved": [r for r in rows if r["classification"].endswith("ORPHAN_PROVEN")],
                "retained": [r for r in rows if r["classification"] == "TERMINAL_ALREADY_RECORDED"],
                "held": [r for r in rows if r["classification"] == "UNRESOLVED_HOLD"],
                "skipped": None if rows else "NO_ACTIVE_RECORDS",
            }
        reports.append(rpt)

    if args.json:
        print(json.dumps(reports, indent=2))
        return 0

    for rpt in reports:
        print(f"=== {rpt['market']} (applied={rpt['applied']}) ===")
        if rpt.get("skipped"):
            print(f"  skipped: {rpt['skipped']}")
            continue
        rows = rpt.get("classifications")
        if rows is None:
            # apply path
            for k in ("moved", "retained", "held"):
                for x in rpt.get(k, []):
                    print(f"  {k[:-1]:<10} {x}")
            continue
        for r in rows:
            print(f"  {r['classification']:<28} {r['trade_id']:<28} {r['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
