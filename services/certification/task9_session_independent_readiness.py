"""Offline Task 9 historical-replay readiness command; never contacts Angel."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from services.certification.task9_historical_certification_replay import (
    RECORD_SOURCE,
    Task9HistoricalCertificationReplay,
    Task9HistoricalReplayReceiptStore,
)


IST = ZoneInfo("Asia/Kolkata")


def _fingerprint(path: Path) -> tuple[object, ...]:
    """Read existing state only; missing live paths are never created."""
    if not path.exists():
        return ("MISSING",)
    if path.is_file():
        return ("FILE", hashlib.sha256(path.read_bytes()).hexdigest())
    entries = []
    for item in sorted(path.rglob("*")):
        if item.is_file():
            entries.append((str(item.relative_to(path)), hashlib.sha256(item.read_bytes()).hexdigest()))
    return ("DIRECTORY", tuple(entries))


def _overlaps(left: Path, right: Path) -> bool:
    try:
        left.relative_to(right)
        return True
    except ValueError:
        try:
            right.relative_to(left)
            return True
        except ValueError:
            return False


def run_readiness(*, trading_date: date, completed_session_reader, persistence_root: str | Path, live_state_paths: Mapping[str, str | Path] | None = None, report_publisher=None) -> dict[str, object]:
    if not callable(completed_session_reader):
        raise TypeError("completed_session_reader")
    if report_publisher is not None and not callable(report_publisher):
        raise TypeError("report_publisher")
    root = Path(persistence_root).resolve()
    live_paths = {name: Path(path).resolve() for name, path in (live_state_paths or {}).items()}
    if any(_overlaps(root, path) for path in live_paths.values()):
        return {"status": "FAILED", "network_access_used": False, "reason": "REPLAY_ROOT_OVERLAPS_LIVE_STATE"}
    before = {name: _fingerprint(path) for name, path in live_paths.items()}
    reader_calls = 0

    def reader(**request):
        nonlocal reader_calls
        reader_calls += 1
        return completed_session_reader(**request)

    store = Task9HistoricalReplayReceiptStore(root)
    replay = Task9HistoricalCertificationReplay(
        completed_session_reader=reader,
        receipt_store=store,
        report_publisher=report_publisher,
    )
    receipt = replay.replay(
        trading_date=trading_date,
        cycle_boundary=datetime.combine(trading_date, datetime.strptime("15:30", "%H:%M").time(), IST),
    )
    reloaded = Task9HistoricalCertificationReplay(
        completed_session_reader=reader,
        receipt_store=Task9HistoricalReplayReceiptStore(root),
    ).replay(trading_date=trading_date, cycle_boundary=datetime.combine(trading_date, datetime.strptime("15:30", "%H:%M").time(), IST))
    after = {name: _fingerprint(path) for name, path in live_paths.items()}
    receipt_count = len(store._load()["receipts"])
    passed = (
        receipt == reloaded
        and receipt["record_source"] == RECORD_SOURCE
        and all(market["status"] == "COMPLETED" for market in receipt["markets"].values())
        and receipt["broker_order_submission"] is False
        and receipt["live_execution_eligible"] is False
        and before == after
        and reader_calls == 2
        and receipt_count == 1
    )
    return {"status": "PASSED" if passed else "FAILED", "network_access_used": False, "receipt": receipt, "reader_calls": reader_calls, "receipt_count": receipt_count, "live_state_unchanged": before == after}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Task 9 offline historical replay readiness")
    parser.add_argument("--trading-date", required=True)
    parser.add_argument("--persistence-root", default="data/paper_trading/certified_runtime/task9_historical_replay")
    parser.add_argument("--evidence-file", help="Offline JSON mapping of market name to completed candle timeframes.")
    args = parser.parse_args(argv)
    if not args.evidence_file:
        print("offline readiness requires --evidence-file; no provider mode exists")
        return 2
    try:
        evidence = json.loads(Path(args.evidence_file).read_text(encoding="utf-8"))
        if not isinstance(evidence, dict):
            raise ValueError("evidence root")
        result = run_readiness(
            trading_date=date.fromisoformat(args.trading_date),
            completed_session_reader=lambda **request: evidence[request["market"]],
            persistence_root=args.persistence_root,
        )
    except (OSError, ValueError, KeyError) as exc:
        print(f"offline readiness failed: {type(exc).__name__}")
        return 1
    print(json.dumps({"status": result["status"], "network_access_used": False}, sort_keys=True))
    return 0 if result["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
