"""Deterministic exact-two-market ranker for NIFTY and SENSEX PAPER candidates."""
from __future__ import annotations

from datetime import datetime
from math import fabs

from services.contracts.two_market_child_terminal_result_v1 import (
    TwoMarketChildTerminalResultV1,
)
from services.contracts.two_market_decision_policy_v1 import (
    TwoMarketDecisionPolicyV1,
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


def _reason_for_ineligible(
    child: TwoMarketChildTerminalResultV1,
    *,
    completed_at: datetime,
    policy: TwoMarketDecisionPolicyV1,
) -> tuple[str, tuple[str, ...]]:
    if child.terminal_status != "COMPLETED":
        return (
            "CHILD_FAILED",
            tuple(child.errors or child.blockers or ("CHILD_NOT_COMPLETED",)),
        )

    candidate = child.candidate
    age_seconds = (completed_at - candidate.market_timestamp).total_seconds()
    if age_seconds < 0:
        return ("STALE", ("FUTURE_MARKET_TIMESTAMP",))
    if age_seconds > policy.max_candidate_age_seconds:
        return (
            "STALE",
            (
                f"CANDIDATE_AGE_SECONDS={age_seconds:.6f}",
                f"MAX_AGE_SECONDS={policy.max_candidate_age_seconds:.6f}",
            ),
        )

    if candidate.eligibility != "ELIGIBLE":
        rationale = (
            candidate.blockers
            or candidate.contradictions
            or candidate.reasons
            or ("CANDIDATE_NOT_ELIGIBLE",)
        )
        return ("INELIGIBLE", tuple(rationale))

    return ("SELECTED", ())


def rank_two_market_candidates(
    *,
    decision_result_id: str,
    parent_cycle_id: str,
    requested_at: datetime,
    completed_at: datetime,
    nifty: TwoMarketChildTerminalResultV1,
    sensex: TwoMarketChildTerminalResultV1,
    policy: TwoMarketDecisionPolicyV1,
) -> TwoMarketDecisionResultV1:
    """Compare only eligible NIFTY/SENSEX candidates and select at most one."""

    if type(policy) is not TwoMarketDecisionPolicyV1:
        raise TypeError("policy")
    if type(nifty) is not TwoMarketChildTerminalResultV1:
        raise TypeError("nifty")
    if type(sensex) is not TwoMarketChildTerminalResultV1:
        raise TypeError("sensex")

    if (nifty.underlying_symbol, nifty.exchange) != ("NIFTY", "NSE"):
        raise ValueError("nifty child identity")
    if (sensex.underlying_symbol, sensex.exchange) != ("SENSEX", "BSE"):
        raise ValueError("sensex child identity")
    if nifty.parent_cycle_id != parent_cycle_id:
        raise ValueError("nifty parent_cycle_id")
    if sensex.parent_cycle_id != parent_cycle_id:
        raise ValueError("sensex parent_cycle_id")

    requested = _aware(requested_at, "requested_at")
    completed = _aware(completed_at, "completed_at")
    if requested > completed:
        raise ValueError("requested_at must not exceed completed_at")

    nifty_reason, nifty_rationale = _reason_for_ineligible(
        nifty,
        completed_at=completed,
        policy=policy,
    )
    sensex_reason, sensex_rationale = _reason_for_ineligible(
        sensex,
        completed_at=completed,
        policy=policy,
    )

    completed_candidates = tuple(
        child.candidate
        for child in (nifty, sensex)
        if child.terminal_status == "COMPLETED"
    )
    timestamp_skew_seconds = 0.0
    if len(completed_candidates) == 2:
        timestamp_skew_seconds = fabs(
            (
                completed_candidates[0].market_timestamp
                - completed_candidates[1].market_timestamp
            ).total_seconds()
        )

    skew_blocked = (
        nifty_reason == "SELECTED"
        and sensex_reason == "SELECTED"
        and timestamp_skew_seconds > policy.max_timestamp_skew_seconds
    )
    if skew_blocked:
        nifty_reason = "SKEW_BLOCKED"
        sensex_reason = "SKEW_BLOCKED"
        detail = (
            f"TIMESTAMP_SKEW_SECONDS={timestamp_skew_seconds:.6f}",
            f"MAX_SKEW_SECONDS={policy.max_timestamp_skew_seconds:.6f}",
        )
        nifty_rationale = detail
        sensex_rationale = detail

    eligible_children = []
    if nifty_reason == "SELECTED":
        eligible_children.append(nifty)
    if sensex_reason == "SELECTED":
        eligible_children.append(sensex)

    selected = None
    loser_reason = None
    loser_rationale = ()

    if len(eligible_children) == 1:
        selected = eligible_children[0]
    elif len(eligible_children) == 2:
        def rank_key(child: TwoMarketChildTerminalResultV1) -> tuple[float, float, int]:
            candidate = child.candidate
            primary = float(getattr(candidate, policy.score_field))
            confidence = (
                float(candidate.confidence)
                if policy.confidence_tie_break
                else 0.0
            )
            order = policy.deterministic_market_order.index(
                (child.underlying_symbol, child.exchange)
            )
            return (primary, confidence, -order)

        selected = max(eligible_children, key=rank_key)
        loser = sensex if selected is nifty else nifty

        selected_primary = float(
            getattr(selected.candidate, policy.score_field)
        )
        loser_primary = float(getattr(loser.candidate, policy.score_field))
        selected_confidence = float(selected.candidate.confidence)
        loser_confidence = float(loser.candidate.confidence)

        if (
            selected_primary == loser_primary
            and (
                not policy.confidence_tie_break
                or selected_confidence == loser_confidence
            )
        ):
            loser_reason = "TIE_BREAK_LOSS"
            loser_rationale = (
                "DETERMINISTIC_MARKET_ORDER",
                f"WINNER={selected.underlying_symbol}",
            )
        else:
            loser_reason = "LOWER_RANK"
            loser_rationale = (
                f"WINNER_{policy.score_field.upper()}={selected_primary:.6f}",
                f"LOSER_{policy.score_field.upper()}={loser_primary:.6f}",
                f"WINNER_CONFIDENCE={selected_confidence:.6f}",
                f"LOSER_CONFIDENCE={loser_confidence:.6f}",
            )

        if loser is nifty:
            nifty_reason, nifty_rationale = loser_reason, loser_rationale
        else:
            sensex_reason, sensex_rationale = loser_reason, loser_rationale

    if selected is nifty:
        nifty_reason = "SELECTED"
        nifty_rationale = (
            f"SELECTED_{policy.score_field.upper()}="
            f"{getattr(nifty.candidate, policy.score_field):.6f}",
        )
    elif selected is sensex:
        sensex_reason = "SELECTED"
        sensex_rationale = (
            f"SELECTED_{policy.score_field.upper()}="
            f"{getattr(sensex.candidate, policy.score_field):.6f}",
        )

    def entry(
        child: TwoMarketChildTerminalResultV1,
        reason: str,
        rationale: tuple[str, ...],
    ) -> TwoMarketDecisionEntryV1:
        eligible = reason in {"SELECTED", "LOWER_RANK", "TIE_BREAK_LOSS"}
        rank_value = (
            float(getattr(child.candidate, policy.score_field))
            if eligible
            else 0.0
        )
        return TwoMarketDecisionEntryV1(
            child=child,
            eligible_for_comparison=eligible,
            rank_value=rank_value,
            outcome_reason=reason,
            rationale=rationale,
        )

    entries = (
        entry(nifty, nifty_reason, nifty_rationale),
        entry(sensex, sensex_reason, sensex_rationale),
    )

    if selected is None:
        blockers = ["NO_ELIGIBLE_MARKET"]
        if skew_blocked:
            blockers.append("CANDIDATE_TIMESTAMP_SKEW_EXCEEDED")
        return TwoMarketDecisionResultV1(
            decision_result_id=decision_result_id,
            parent_cycle_id=parent_cycle_id,
            requested_at=requested,
            completed_at=completed,
            entries=entries,
            decision="NO_TRADE",
            selected_market=None,
            selected_candidate_id=None,
            timestamp_skew_seconds=timestamp_skew_seconds,
            blockers=tuple(blockers),
        )

    return TwoMarketDecisionResultV1(
        decision_result_id=decision_result_id,
        parent_cycle_id=parent_cycle_id,
        requested_at=requested,
        completed_at=completed,
        entries=entries,
        decision="SELECTED",
        selected_market=(
            selected.underlying_symbol,
            selected.exchange,
        ),
        selected_candidate_id=selected.candidate.candidate_id,
        timestamp_skew_seconds=timestamp_skew_seconds,
    )
