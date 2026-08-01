"""Bridge Task 3's exact two-market decision into planning authorization."""
from __future__ import annotations

from datetime import datetime
from math import isfinite

from services.contracts.selected_market_planning_bridge_result_v1 import (
    SelectedMarketPlanningBridgeResultV1,
)
from services.contracts.two_market_decision_result_v1 import (
    TwoMarketDecisionEntryV1,
    TwoMarketDecisionResultV1,
)


def _aware(value: object, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)
    return value


def _positive_finite(value: object, name: str) -> float:
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not isfinite(value)
        or value <= 0.0
    ):
        raise ValueError(name)
    return float(value)


def _losing_entry(
    decision: TwoMarketDecisionResultV1,
) -> TwoMarketDecisionEntryV1 | None:
    if decision.decision != "SELECTED":
        return None
    losing = tuple(
        entry
        for entry in decision.entries
        if entry.outcome_reason != "SELECTED"
    )
    if len(losing) != 1:
        raise ValueError(
            "selected decision must contain exactly one losing entry"
        )
    return losing[0]


def bridge_selected_market_to_planning(
    *,
    bridge_result_id: str,
    decision: TwoMarketDecisionResultV1,
    evaluated_at: datetime,
    maximum_candidate_age_seconds: float,
) -> SelectedMarketPlanningBridgeResultV1:
    """Authorize only Task 3's selected market for later P6 planning."""

    if type(decision) is not TwoMarketDecisionResultV1:
        raise TypeError("decision")

    now = _aware(evaluated_at, "evaluated_at")
    max_age = _positive_finite(
        maximum_candidate_age_seconds,
        "maximum_candidate_age_seconds",
    )
    if now < decision.completed_at:
        raise ValueError(
            "evaluated_at must not precede parent completion"
        )

    if decision.decision == "NO_TRADE":
        reasons = tuple(
            dict.fromkeys(
                decision.blockers
                + tuple(
                    reason
                    for entry in decision.entries
                    for reason in (
                        entry.outcome_reason,
                        *entry.rationale,
                    )
                )
            )
        )
        return SelectedMarketPlanningBridgeResultV1(
            bridge_result_id=bridge_result_id,
            parent_cycle_id=decision.parent_cycle_id,
            evaluated_at=now,
            action="NO_TRADE",
            planning_allowed=False,
            selected_market=None,
            selected_candidate=None,
            losing_market=None,
            losing_outcome_reason=None,
            reasons=reasons or ("NO_ELIGIBLE_MARKET",),
            blockers=decision.blockers or (
                "NO_ELIGIBLE_MARKET",
            ),
            warnings=decision.warnings,
        )

    selected_entries = tuple(
        entry
        for entry in decision.entries
        if entry.outcome_reason == "SELECTED"
    )
    if len(selected_entries) != 1:
        raise ValueError(
            "selected decision must contain one selected entry"
        )

    selected_entry = selected_entries[0]
    candidate = selected_entry.child.candidate
    losing = _losing_entry(decision)
    selected_market = (
        candidate.underlying_symbol,
        candidate.exchange,
    )
    losing_market = (
        losing.child.underlying_symbol,
        losing.child.exchange,
    )

    blockers: list[str] = []
    warnings = list(decision.warnings)
    reasons = list(candidate.reasons)
    invalidation = list(candidate.invalidation_conditions)

    age_seconds = (
        now - candidate.market_timestamp
    ).total_seconds()
    if age_seconds < 0.0:
        blockers.append("FUTURE_CANDIDATE_TIMESTAMP")
    elif age_seconds > max_age:
        blockers.append("SELECTED_CANDIDATE_STALE")

    if candidate.eligibility != "ELIGIBLE":
        blockers.append("SELECTED_CANDIDATE_INELIGIBLE")
    if candidate.blockers:
        blockers.extend(candidate.blockers)
    if candidate.contradictions:
        blockers.append("SELECTED_CANDIDATE_CONFLICTING")
        blockers.extend(candidate.contradictions)
    if candidate.direction not in {"BULLISH", "BEARISH"}:
        blockers.append("SELECTED_DIRECTION_NOT_ACTIONABLE")

    blockers = list(dict.fromkeys(blockers))
    warnings = list(
        dict.fromkeys(warnings + list(candidate.warnings))
    )
    reasons = list(
        dict.fromkeys(
            reasons
            + [
                f"SELECTED_MARKET={candidate.underlying_symbol}",
                f"SELECTED_SCORE={candidate.score:.6f}",
                f"SELECTED_CONFIDENCE={candidate.confidence:.6f}",
            ]
        )
    )

    common = dict(
        bridge_result_id=bridge_result_id,
        parent_cycle_id=decision.parent_cycle_id,
        evaluated_at=now,
        selected_market=selected_market,
        selected_candidate=candidate,
        losing_market=losing_market,
        losing_outcome_reason=losing.outcome_reason,
        losing_rationale=losing.rationale,
        reasons=tuple(reasons),
        invalidation_conditions=tuple(invalidation),
        warnings=tuple(warnings),
    )

    if blockers:
        return SelectedMarketPlanningBridgeResultV1(
            **common,
            action="WAIT",
            planning_allowed=False,
            blockers=tuple(blockers),
        )

    action = (
        "CALL"
        if candidate.direction == "BULLISH"
        else "PUT"
    )
    return SelectedMarketPlanningBridgeResultV1(
        **common,
        action=action,
        planning_allowed=True,
    )
