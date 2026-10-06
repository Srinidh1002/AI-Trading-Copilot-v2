"""R18B offline-only strategy shadow analysis.

This module does not place orders, read provider data, mutate PAPER state, or
change certification counters.  It deliberately separates *observed-session
diagnostics* from causal counterfactual claims.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Mapping, Sequence

DEFAULT_PRE_T1_THRESHOLDS = (8.0, 10.0, 12.0, 15.0)
DEFAULT_COOLDOWNS_MINUTES = (5, 10, 15)


def _as_list(rows: Iterable[Mapping[str, object]]) -> list[Mapping[str, object]]:
    return list(rows or ())


def analyze_index_observations(
    trades: Iterable[Mapping[str, object]],
    *,
    thresholds: Sequence[float] = DEFAULT_PRE_T1_THRESHOLDS,
) -> dict:
    """Summarize CHOPPY and pre-T1 observations without simulating exits."""
    rows = _as_list(trades)
    choppy = [row for row in rows if str(row.get("regime")) == "CHOPPY"]
    choppy_losses = [row for row in choppy if str(row.get("outcome")) == "LOSS"]
    choppy_wins = [row for row in choppy if str(row.get("outcome")) == "WIN"]

    arms = []
    for threshold in thresholds:
        threshold = float(threshold)
        armed = [
            row
            for row in rows
            if float(row.get("peak_pnl_pct") or 0.0) >= threshold
        ]
        arms.append(
            {
                "threshold_pct": threshold,
                "armed_count": len(armed),
                "armed_wins": sum(str(row.get("outcome")) == "WIN" for row in armed),
                "armed_losses": sum(
                    str(row.get("outcome")) == "LOSS" for row in armed
                ),
                "trade_ids": [str(row.get("trade_id")) for row in armed],
            }
        )

    return {
        "observed_trade_count": len(rows),
        "observed_wins": sum(str(row.get("outcome")) == "WIN" for row in rows),
        "observed_losses": sum(str(row.get("outcome")) == "LOSS" for row in rows),
        "observed_net_pnl": round(
            sum(float(row.get("net_pnl") or 0.0) for row in rows),
            2,
        ),
        "choppy_trade_count": len(choppy),
        "choppy_loss_count": len(choppy_losses),
        "choppy_win_count": len(choppy_wins),
        "choppy_observed_net_pnl": round(
            sum(float(row.get("net_pnl") or 0.0) for row in choppy),
            2,
        ),
        "choppy_trade_ids": [str(row.get("trade_id")) for row in choppy],
        "pre_t1_threshold_observations": arms,
        "causal_counterfactual_valid": False,
        "caution": (
            "MFE/peak observations can identify which trades would have armed a "
            "candidate rule, but cannot determine the alternate exit price or "
            "P&L without the full ordered executable-bid path."
        ),
    }


def _parse_time(value: object) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError("timestamp is required")
    return datetime.fromisoformat(text)


def analyze_crude_observations(
    trades: Iterable[Mapping[str, object]],
    *,
    cooldowns_minutes: Sequence[int] = DEFAULT_COOLDOWNS_MINUTES,
) -> dict:
    """Analyze observed repeated-thesis intervals and retest evidence."""
    rows = sorted(_as_list(trades), key=lambda row: _parse_time(row.get("entry_time")))

    missing_retest = [
        row
        for row in rows
        if str(row.get("setup")) == "BREAKOUT_RETEST"
        and not bool(row.get("explicit_retest_evidence"))
    ]

    intervals = []
    for previous, current in zip(rows, rows[1:]):
        same_thesis = (
            str(previous.get("setup")) == str(current.get("setup"))
            and str(previous.get("regime")) == str(current.get("regime"))
            and str(previous.get("direction")) == str(current.get("direction"))
        )
        seconds = (
            _parse_time(current.get("entry_time"))
            - _parse_time(previous.get("exit_time"))
        ).total_seconds()
        intervals.append(
            {
                "previous_trade_id": str(previous.get("trade_id")),
                "current_trade_id": str(current.get("trade_id")),
                "same_thesis": same_thesis,
                "minutes_since_previous_exit": round(seconds / 60.0, 3),
            }
        )

    cooldown_observations = []
    for minutes in cooldowns_minutes:
        flagged = [
            row
            for row in intervals
            if row["same_thesis"]
            and float(row["minutes_since_previous_exit"]) < float(minutes)
        ]
        cooldown_observations.append(
            {
                "cooldown_minutes": int(minutes),
                "observed_entries_inside_window": len(flagged),
                "trade_ids": [row["current_trade_id"] for row in flagged],
            }
        )

    return {
        "observed_trade_count": len(rows),
        "observed_losses": sum(str(row.get("outcome")) == "LOSS" for row in rows),
        "observed_net_pnl": round(
            sum(float(row.get("net_pnl") or 0.0) for row in rows),
            2,
        ),
        "breakout_retest_count": sum(
            str(row.get("setup")) == "BREAKOUT_RETEST" for row in rows
        ),
        "breakout_retest_missing_explicit_retest_evidence": len(missing_retest),
        "missing_retest_trade_ids": [
            str(row.get("trade_id")) for row in missing_retest
        ],
        "observed_same_thesis_intervals": intervals,
        "cooldown_observations": cooldown_observations,
        "causal_counterfactual_valid": False,
        "caution": (
            "Cooldown flags use the observed sequence. If an earlier trade were "
            "blocked, later signal timing/state could change, so these counts are "
            "not a causal replay result."
        ),
    }


def shadow_breakout_retest_gate(
    *,
    regime: str,
    mtf_aligned: bool,
    explicit_retest_evidence: bool,
) -> dict:
    """Fail-closed research gate for the semantic BREAKOUT_RETEST requirement."""
    if regime not in {"BREAKOUT_UP", "BREAKOUT_DOWN"}:
        return {"allow": False, "reason": "NOT_BREAKOUT_REGIME"}
    if not mtf_aligned:
        return {"allow": False, "reason": "MTF_NOT_ALIGNED"}
    if not explicit_retest_evidence:
        return {"allow": False, "reason": "EXPLICIT_RETEST_EVIDENCE_MISSING"}
    return {"allow": True, "reason": "BREAKOUT_RETEST_CONFIRMED"}


def analyze_dataset(dataset: Mapping[str, object]) -> dict:
    return {
        "schema_version": "r18b.shadow_analysis.v1",
        "execution_mode": "RESEARCH_ONLY",
        "certification_countable": False,
        "index": analyze_index_observations(dataset.get("index_trades") or ()),
        "crude": analyze_crude_observations(dataset.get("crude_trades") or ()),
        "recommendation": {
            "deploy_index_choppy_veto_now": False,
            "deploy_pre_t1_profit_lock_now": False,
            "deploy_fixed_crude_cooldown_now": False,
            "promote_explicit_breakout_retest_evidence_requirement_to_candidate": True,
            "reason": (
                "One session is insufficient to tune profitability thresholds. "
                "The BREAKOUT_RETEST naming/logic gap is semantic and can be "
                "tested as a fail-closed candidate without changing production."
            ),
        },
    }
