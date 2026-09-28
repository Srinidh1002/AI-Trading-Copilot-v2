"""Same-day stale-active trade reconciler — Phase 10 of F15-R1.

PAPER-only. Read-only classification plus a single safe-apply path
that moves a proven stale active record into orphaned_trades with
audit metadata. Never modifies certification counters or counted IDs.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

IST = timezone(timedelta(hours=5, minutes=30))

INDEX_MARKETS = ("NIFTY", "SENSEX")

ACTIVE_VALID = "ACTIVE_VALID"
TERMINAL_ALREADY_RECORDED = "TERMINAL_ALREADY_RECORDED"
STALE_RESTART_ORPHAN_PROVEN = "STALE_RESTART_ORPHAN_PROVEN"
UNRESOLVED_HOLD = "UNRESOLVED_HOLD"

STALE_QUOTE_THRESHOLD_S = 4 * 3600

# Fields that must never change during reconciliation.
_IMMUTABLE_STATE_FIELDS = (
    "certification_counter",
    "certification_wins",
    "certification_losses",
    "counted_trade_ids",
    "completed_trades",
)


def _state_path(repo_root, market):
    return (
        Path(repo_root)
        / "data"
        / "paper_trades"
        / f"{market.lower()}_experimental.json"
    )


def _outcomes_path(repo_root, market):
    return (
        Path(repo_root)
        / "data"
        / "paper_trades"
        / f"{market.lower()}_outcomes.jsonl"
    )


def _load_state(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _load_outcome_ids(path):
    ids = set()
    try:
        with Path(path).open("r", encoding="utf-8") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    row = json.loads(raw)
                except ValueError:
                    continue
                tid = row.get("trade_id")
                if tid:
                    ids.add(tid)
    except OSError:
        pass
    return ids


def _parse_iso_ist(ts):
    if not isinstance(ts, str) or not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    return dt


def classify_active_record(
    rec,
    *,
    outcome_ids,
    counted_ids,
    orphaned_ids,
    now,
    stale_quote_threshold_s=STALE_QUOTE_THRESHOLD_S,
):
    """Return (classification, reason_string)."""
    if not isinstance(rec, dict):
        return UNRESOLVED_HOLD, "NOT_A_DICT"
    tid = rec.get("trade_id")
    if not tid:
        return UNRESOLVED_HOLD, "NO_TRADE_ID"
    if tid in outcome_ids:
        return TERMINAL_ALREADY_RECORDED, f"FOUND_IN_OUTCOMES:{tid}"
    if tid in counted_ids:
        return TERMINAL_ALREADY_RECORDED, f"IN_COUNTED_TRADE_IDS:{tid}"
    if tid in orphaned_ids:
        return STALE_RESTART_ORPHAN_PROVEN, f"ALREADY_ORPHANED:{tid}"

    ftr = rec.get("first_touch_result")
    if ftr in (None, ""):
        return STALE_RESTART_ORPHAN_PROVEN, "FIRST_TOUCH_UNINITIALIZED"

    fts = rec.get("first_touch_state") or {}
    last_quote = _parse_iso_ist(fts.get("last_valid_quote_time"))
    if last_quote is not None:
        age_s = (now - last_quote).total_seconds()
        if age_s > stale_quote_threshold_s:
            return (
                STALE_RESTART_ORPHAN_PROVEN,
                f"LAST_QUOTE_STALE:{int(age_s)}s",
            )

    return UNRESOLVED_HOLD, f"FIRST_TOUCH_PRESENT:{ftr}"


def classify_market(repo_root, market, *, now=None):
    """Return list of dicts: {trade_id, classification, reason}."""
    if now is None:
        now = datetime.now(IST)
    if market not in INDEX_MARKETS:
        return []
    st = _load_state(_state_path(repo_root, market))
    if not isinstance(st, dict):
        return []
    active = st.get("active_trades")
    if not isinstance(active, list):
        return []
    outcome_ids = _load_outcome_ids(_outcomes_path(repo_root, market))
    counted_ids = set(st.get("counted_trade_ids") or [])
    orphaned = st.get("orphaned_trades") or []
    orphaned_ids = {
        o.get("trade_id") for o in orphaned if isinstance(o, dict) and o.get("trade_id")
    }
    out = []
    for rec in active:
        cls, reason = classify_active_record(
            rec,
            outcome_ids=outcome_ids,
            counted_ids=counted_ids,
            orphaned_ids=orphaned_ids,
            now=now,
        )
        out.append(
            {
                "trade_id": (rec or {}).get("trade_id"),
                "classification": cls,
                "reason": reason,
            }
        )
    return out


def _atomic_write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def reconcile_market_state(repo_root, market, *, apply=False, now=None):
    """Classify and (if apply=True) move proven orphans to orphaned_trades.

    Only STALE_RESTART_ORPHAN_PROVEN records are moved. Returns a report
    dict. In apply mode, raises if any immutable field differs from the
    pre-apply snapshot before persisting.
    """
    if now is None:
        now = datetime.now(IST)

    if market not in INDEX_MARKETS:
        return {
            "market": market,
            "applied": False,
            "skipped": "NON_INDEX_MARKET",
            "moved": [],
            "retained": [],
            "held": [],
        }

    path = _state_path(repo_root, market)
    st = _load_state(path)
    if not isinstance(st, dict):
        return {
            "market": market,
            "applied": False,
            "skipped": "NO_STATE",
            "moved": [],
            "retained": [],
            "held": [],
        }

    active = st.get("active_trades")
    if not isinstance(active, list):
        active = []

    outcome_ids = _load_outcome_ids(_outcomes_path(repo_root, market))
    counted_ids = set(st.get("counted_trade_ids") or [])
    orphaned = st.get("orphaned_trades")
    if not isinstance(orphaned, list):
        orphaned = []
    orphaned_ids = {
        o.get("trade_id") for o in orphaned if isinstance(o, dict) and o.get("trade_id")
    }

    keep = []
    moved = []
    retained = []
    held = []
    now_iso = now.isoformat(timespec="seconds")

    for rec in active:
        if not isinstance(rec, dict):
            keep.append(rec)
            continue
        cls, reason = classify_active_record(
            rec,
            outcome_ids=outcome_ids,
            counted_ids=counted_ids,
            orphaned_ids=orphaned_ids,
            now=now,
        )
        tid = rec.get("trade_id")
        if cls == STALE_RESTART_ORPHAN_PROVEN:
            archived = dict(rec)
            archived["orphan_reason"] = reason
            archived["source_state"] = "active_trades"
            archived["proof_reference"] = reason
            archived["reconciled_at"] = now_iso
            orphaned.append(archived)
            moved.append({"trade_id": tid, "reason": reason})
        elif cls == TERMINAL_ALREADY_RECORDED:
            keep.append(rec)
            retained.append({"trade_id": tid, "reason": reason})
        else:
            keep.append(rec)
            held.append({"trade_id": tid, "reason": reason})

    report = {
        "market": market,
        "applied": bool(apply),
        "moved": moved,
        "retained": retained,
        "held": held,
        "skipped": None,
    }

    if not apply or not moved:
        return report

    # Pre-apply invariant snapshot
    snapshot = {f: st.get(f) for f in _IMMUTABLE_STATE_FIELDS}

    new_state = dict(st)
    new_state["active_trades"] = keep
    new_state["orphaned_trades"] = orphaned

    # Post-build invariant check
    for f, before in snapshot.items():
        if new_state.get(f) != before:
            raise RuntimeError(f"IMMUTABLE_FIELD_CHANGED:{f}")

    _atomic_write_json(path, new_state)
    return report
