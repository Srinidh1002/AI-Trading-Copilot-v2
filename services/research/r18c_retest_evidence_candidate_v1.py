"""R18C explicit BREAKOUT_RETEST evidence candidate.

Research-only contract.  It does not call FYERS, place PAPER trades, mutate
certification state, or change the production MCX setup classifier.
"""

from __future__ import annotations

import collections.abc as cabc
import datetime as dt


_REQUIRED_EVENTS = (
    "breakout_observed",
    "extension_observed",
    "retest_observed",
    "rejection_observed",
)

_REQUIRED_TIMES = (
    "breakout_at",
    "extension_at",
    "retest_at",
    "rejection_at",
)


def _parse_timestamp(value: object) -> dt.datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError("timestamp is required")
    return dt.datetime.fromisoformat(text)


def validate_explicit_retest_evidence(evidence: cabc.Mapping[str, object] | None) -> dict:
    """Validate breakout -> extension -> retest -> rejection event ordering."""
    if not isinstance(evidence, cabc.Mapping):
        return {
            "confirmed": False,
            "reason": "RETEST_EVIDENCE_MISSING",
        }

    missing_events = [name for name in _REQUIRED_EVENTS if not bool(evidence.get(name))]
    if missing_events:
        return {
            "confirmed": False,
            "reason": "RETEST_EVENT_MISSING",
            "missing_events": missing_events,
        }

    missing_times = [name for name in _REQUIRED_TIMES if not evidence.get(name)]
    if missing_times:
        return {
            "confirmed": False,
            "reason": "RETEST_TIMESTAMP_MISSING",
            "missing_timestamps": missing_times,
        }

    try:
        times = [_parse_timestamp(evidence[name]) for name in _REQUIRED_TIMES]
    except (TypeError, ValueError):
        return {
            "confirmed": False,
            "reason": "RETEST_TIMESTAMP_INVALID",
        }

    if times != sorted(times) or len(set(times)) != len(times):
        return {
            "confirmed": False,
            "reason": "RETEST_EVENT_ORDER_INVALID",
        }

    return {
        "confirmed": True,
        "reason": "EXPLICIT_BREAKOUT_RETEST_CONFIRMED",
        "breakout_at": str(evidence["breakout_at"]),
        "extension_at": str(evidence["extension_at"]),
        "retest_at": str(evidence["retest_at"]),
        "rejection_at": str(evidence["rejection_at"]),
    }


def evaluate_breakout_retest_candidate(
    *,
    regime: str,
    mtf_aligned: bool,
    evidence: cabc.Mapping[str, object] | None,
) -> dict:
    """Fail closed unless the named BREAKOUT_RETEST sequence is explicit."""
    if regime not in {"BREAKOUT_UP", "BREAKOUT_DOWN"}:
        return {
            "allow": False,
            "reason": "NOT_BREAKOUT_REGIME",
        }

    if not mtf_aligned:
        return {
            "allow": False,
            "reason": "MTF_NOT_ALIGNED",
        }

    validation = validate_explicit_retest_evidence(evidence)
    if not validation["confirmed"]:
        return {
            "allow": False,
            "reason": validation["reason"],
            "evidence_validation": validation,
        }

    return {
        "allow": True,
        "reason": "BREAKOUT_RETEST_CONFIRMED",
        "evidence_validation": validation,
    }


def audit_bearish_snapshot_episode(
    cycles: cabc.Sequence[cabc.Mapping[str, object]],
    *,
    breakout_level_reference: float,
    entry_timestamp: str,
) -> dict:
    """Ordering-only audit of cycle snapshots for a bearish breakout episode.

    This intentionally does not infer intracycle highs/lows.  It only asks
    whether the recorded cycle prices visibly extended below the breakout and
    then returned toward the frozen pre-breakout level before the entry cycle.
    """
    rows = list(cycles or ())
    if len(rows) < 3:
        return {
            "status": "INSUFFICIENT_SNAPSHOTS",
            "causal_counterfactual_valid": False,
        }

    entry_time = _parse_timestamp(entry_timestamp)
    usable = [row for row in rows if _parse_timestamp(row.get("timestamp")) <= entry_time]

    breakout_index = None
    for index, row in enumerate(usable):
        if str(row.get("regime")) == "BREAKOUT_DOWN":
            breakout_index = index
            break

    if breakout_index is None:
        return {
            "status": "BREAKOUT_NOT_VISIBLE",
            "causal_counterfactual_valid": False,
        }

    breakout_price = float(usable[breakout_index].get("future_ltp") or 0.0)
    after = usable[breakout_index + 1 :]
    if not after:
        return {
            "status": "NO_POST_BREAKOUT_SNAPSHOTS",
            "causal_counterfactual_valid": False,
        }

    prices = [float(row.get("future_ltp") or 0.0) for row in after]
    extension_price = breakout_price
    extension_index = None
    for index, price in enumerate(prices):
        if price < extension_price:
            extension_price = price
            extension_index = index
            break

    if extension_index is None:
        return {
            "status": "EXTENSION_NOT_VISIBLE",
            "breakout_price": breakout_price,
            "causal_counterfactual_valid": False,
        }

    returned_toward_level = False
    return_timestamp = None
    running_low = extension_price
    for offset, price in enumerate(prices[extension_index + 1 :], start=extension_index + 1):
        if price < running_low:
            running_low = price
            continue

        prior_distance = abs(float(breakout_level_reference) - running_low)
        current_distance = abs(float(breakout_level_reference) - price)
        if price > running_low and current_distance < prior_distance:
            returned_toward_level = True
            return_timestamp = str(after[offset].get("timestamp"))
            break

    return {
        "status": (
            "RETEST_RETURN_VISIBLE_IN_SNAPSHOTS"
            if returned_toward_level
            else "NO_RETEST_RETURN_VISIBLE_IN_SNAPSHOTS"
        ),
        "breakout_level_reference": float(breakout_level_reference),
        "breakout_timestamp": str(usable[breakout_index].get("timestamp")),
        "breakout_price": breakout_price,
        "lowest_post_breakout_price": min(prices),
        "returned_toward_level": returned_toward_level,
        "return_timestamp": return_timestamp,
        "causal_counterfactual_valid": False,
        "caution": (
            "Cycle snapshots do not contain the complete intracycle executable "
            "price path, so absence of a visible return is not proof that no "
            "intracycle retest occurred."
        ),
    }


def audit_oct05_candidate_blocks(trades: cabc.Sequence[cabc.Mapping[str, object]]) -> dict:
    """Apply the candidate contract to captured Oct-5 CRUDE trade summaries."""
    results = []
    for row in trades or ():
        evidence = row.get("explicit_retest_evidence_detail")
        result = evaluate_breakout_retest_candidate(
            regime=str(row.get("regime") or ""),
            mtf_aligned=True,
            evidence=evidence if isinstance(evidence, cabc.Mapping) else None,
        )
        results.append(
            {
                "trade_id": str(row.get("trade_id")),
                "allow": result["allow"],
                "reason": result["reason"],
            }
        )

    return {
        "trade_count": len(results),
        "allowed_count": sum(bool(row["allow"]) for row in results),
        "blocked_count": sum(not bool(row["allow"]) for row in results),
        "results": results,
        "causal_counterfactual_valid": False,
    }
