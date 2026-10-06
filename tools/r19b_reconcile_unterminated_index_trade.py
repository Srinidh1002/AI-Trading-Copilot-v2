"""R19-B explicit reconciliation for an unterminated index PAPER trade.

This tool never invents an exit price or P&L.  It removes one explicitly
identified, frozen unresolved trade from active authority and archives it as
an operational incident excluded from certification and operational P&L.

Default mode is dry-run.  --apply requires an exact pre-state SHA256 and an
explicit backup path.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest().upper()


def _trade_id(row) -> str | None:
    if not isinstance(row, dict):
        return None
    return row.get("trade_id") or row.get("id")


def reconcile_state(state: dict, trade_id: str, *, reconciled_at: str) -> tuple[dict, dict]:
    """Return (new_state, incident) without mutating input.

    The unresolved trade is archived, not closed.  Economic P&L and all
    certification counters remain bit-for-bit equivalent values.
    """
    if not isinstance(state, dict):
        raise ValueError("STATE_NOT_OBJECT")

    market = str(state.get("market") or "").upper()
    if market not in {"NIFTY", "SENSEX"}:
        raise ValueError("INDEX_MARKET_REQUIRED")

    active = state.get("active_trades") or []
    if isinstance(active, dict):
        active = [active]
    if not isinstance(active, list):
        raise ValueError("ACTIVE_TRADES_INVALID")

    matches = [row for row in active if _trade_id(row) == trade_id]
    if len(matches) != 1:
        raise ValueError(f"ACTIVE_MATCH_COUNT_{len(matches)}")

    completed = state.get("completed_trades") or []
    if not isinstance(completed, list):
        raise ValueError("COMPLETED_TRADES_INVALID")
    if any(_trade_id(row) == trade_id for row in completed):
        raise ValueError("TERMINAL_COMPLETED_RECORD_EXISTS")

    counted = state.get("counted_trade_ids") or []
    if trade_id in set(counted):
        raise ValueError("TRADE_ALREADY_CERTIFICATION_COUNTED")

    before_authority = {
        "total_pnl": state.get("total_pnl"),
        "certification_counter": state.get("certification_counter"),
        "certification_wins": state.get("certification_wins"),
        "certification_losses": state.get("certification_losses"),
        "counted_trade_ids": list(counted),
        "completed_trades_count": len(completed),
    }

    unresolved = copy.deepcopy(matches[0])
    unresolved["status"] = "UNRESOLVED_PRIOR_SESSION"
    unresolved["reconciliation_status"] = "UNRESOLVED_EXCLUDED"
    unresolved["reconciliation_reason"] = "NO_TERMINAL_EXECUTABLE_EVIDENCE"
    unresolved["reconciled_at"] = reconciled_at
    unresolved["certification_countable"] = False
    unresolved["certification_countability_reason"] = (
        "UNTERMINATED_PRIOR_SESSION_NO_TERMINAL_EVIDENCE"
    )
    unresolved["operational_pnl_included"] = False
    unresolved["terminal_exit_invented"] = False

    new_state = copy.deepcopy(state)
    new_state["active_trades"] = [
        copy.deepcopy(row)
        for row in active
        if _trade_id(row) != trade_id
    ]

    orphaned = new_state.get("orphaned_trades") or []
    if not isinstance(orphaned, list):
        raise ValueError("ORPHANED_TRADES_INVALID")
    orphaned = list(orphaned)
    orphaned.append(unresolved)
    new_state["orphaned_trades"] = orphaned

    after_authority = {
        "total_pnl": new_state.get("total_pnl"),
        "certification_counter": new_state.get("certification_counter"),
        "certification_wins": new_state.get("certification_wins"),
        "certification_losses": new_state.get("certification_losses"),
        "counted_trade_ids": list(new_state.get("counted_trade_ids") or []),
        "completed_trades_count": len(new_state.get("completed_trades") or []),
    }

    if before_authority != after_authority:
        raise RuntimeError("ACCOUNTING_AUTHORITY_CHANGED")

    incident = {
        "schema_version": "r19b.unterminated_index_incident.v1",
        "market": market,
        "trade_id": trade_id,
        "classification": "UNTERMINATED_ACTIVE_REQUIRES_RECOVERY",
        "resolution": "ARCHIVED_UNRESOLVED_EXCLUDED",
        "reason": "NO_TERMINAL_EXECUTABLE_EVIDENCE",
        "reconciled_at": reconciled_at,
        "economic_pnl_added": 0,
        "certification_count_added": 0,
        "terminal_exit_invented": False,
        "first_touch_result": unresolved.get("first_touch_result"),
        "entry": unresolved.get("entry"),
        "entry_time": str(unresolved.get("entry_time") or ""),
        "last_valid_bid": (
            (unresolved.get("first_touch_state") or {}).get("last_valid_bid")
            if isinstance(unresolved.get("first_touch_state"), dict)
            else None
        ),
        "peak_bid": unresolved.get("peak_bid"),
        "t1_price": unresolved.get("t1_price"),
        "sl_price": unresolved.get("sl_price"),
    }
    return new_state, incident


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)
            f.write("\n")
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True)
    ap.add_argument("--trade-id", required=True)
    ap.add_argument("--expected-sha256", required=True)
    ap.add_argument("--backup", required=True)
    ap.add_argument("--incident-log", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    state_path = Path(args.state).resolve()
    backup_path = Path(args.backup).resolve()
    incident_path = Path(args.incident_log).resolve()

    raw = state_path.read_bytes()
    before_sha = _sha256_bytes(raw)
    expected = args.expected_sha256.strip().upper()

    print(f"STATE_PATH={state_path}")
    print(f"STATE_SHA256_BEFORE={before_sha}")
    print(f"EXPECTED_SHA256={expected}")

    if before_sha != expected:
        print("R19B_RECONCILE=REFUSED_HASH_MISMATCH")
        return 2

    state = json.loads(raw.decode("utf-8"))
    reconciled_at = datetime.now(timezone.utc).isoformat()
    new_state, incident = reconcile_state(
        state,
        args.trade_id,
        reconciled_at=reconciled_at,
    )

    print(f"MARKET={incident['market']}")
    print(f"TRADE_ID={incident['trade_id']}")
    print(f"CLASSIFICATION={incident['classification']}")
    print(f"RESOLUTION={incident['resolution']}")
    print(f"TERMINAL_EXIT_INVENTED={incident['terminal_exit_invented']}")
    print(f"ECONOMIC_PNL_ADDED={incident['economic_pnl_added']}")
    print(f"CERTIFICATION_COUNT_ADDED={incident['certification_count_added']}")

    if not args.apply:
        print("R19B_RECONCILE=DRY_RUN_PASS")
        return 0

    if backup_path.exists():
        print("R19B_RECONCILE=REFUSED_BACKUP_EXISTS")
        return 3

    backup_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path.write_bytes(raw)

    if _sha256_bytes(backup_path.read_bytes()) != before_sha:
        raise RuntimeError("BACKUP_HASH_MISMATCH")

    _atomic_write_json(state_path, new_state)

    after_raw = state_path.read_bytes()
    after_sha = _sha256_bytes(after_raw)

    incident["state_sha256_before"] = before_sha
    incident["state_sha256_after"] = after_sha
    incident["backup_path"] = str(backup_path)

    incident_path.parent.mkdir(parents=True, exist_ok=True)
    with incident_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(incident, sort_keys=True, default=str) + "\n")

    verify = json.loads(state_path.read_text(encoding="utf-8"))
    remaining = [
        row
        for row in (verify.get("active_trades") or [])
        if _trade_id(row) == args.trade_id
    ]
    archived = [
        row
        for row in (verify.get("orphaned_trades") or [])
        if _trade_id(row) == args.trade_id
        and row.get("reconciliation_status") == "UNRESOLVED_EXCLUDED"
    ]
    if remaining or len(archived) != 1:
        raise RuntimeError("POST_WRITE_RECONCILIATION_VERIFY_FAILED")

    print(f"BACKUP_PATH={backup_path}")
    print(f"INCIDENT_LOG={incident_path}")
    print(f"STATE_SHA256_AFTER={after_sha}")
    print("ACTIVE_TRADE_REMOVED=TRUE")
    print("UNRESOLVED_ARCHIVE_ADDED=TRUE")
    print("ACCOUNTING_AUTHORITY_CHANGED=FALSE")
    print("R19B_RECONCILE=APPLY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
