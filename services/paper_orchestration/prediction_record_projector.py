"""Pure deterministic projection of one parent result into two predictions."""
from __future__ import annotations

import math
from collections.abc import Mapping

from services.certification.task9_prediction_lifecycle_timing import (
    resolve_prediction_lifecycle_window,
)
from services.contracts.prediction_lifecycle_timing_v1 import (
    PredictionLifecycleTimingPolicyV1,
    PredictionLifecycleWindowV1,
)
from services.contracts.prediction_record_v1 import PredictionRecordV1
from services.contracts.two_market_decision_result_v1 import (
    TwoMarketDecisionResultV1,
)
from services.market_session.policies import BSE_SENSEX_POLICY, NSE_NIFTY_POLICY


def _predicted_action(direction: str, *, selected: bool) -> str:
    if not selected:
        return "WAIT"
    if direction == "BULLISH":
        return "CALL"
    if direction == "BEARISH":
        return "PUT"
    raise ValueError(
        "selected prediction requires BULLISH or BEARISH direction"
    )


def project_parent_decision_predictions(
    decision: TwoMarketDecisionResultV1,
    *,
    start_underlying_prices: Mapping[tuple[str, str], float],
    lifecycle_window_sink=None,
) -> tuple[PredictionRecordV1, PredictionRecordV1]:
    """Project one parent decision into exact ordered NIFTY/SENSEX records."""

    if type(decision) is not TwoMarketDecisionResultV1:
        raise TypeError("decision")
    if not isinstance(start_underlying_prices, Mapping):
        raise TypeError("start_underlying_prices")
    if lifecycle_window_sink is not None and not callable(lifecycle_window_sink):
        raise TypeError("lifecycle_window_sink")
    expected_identities = (("NIFTY", "NSE"), ("SENSEX", "BSE"))
    if set(start_underlying_prices) != set(expected_identities):
        raise ValueError("exact NIFTY/SENSEX start prices required")
    normalized_prices = {}
    for identity in expected_identities:
        value = start_underlying_prices[identity]
        if type(value) not in (int, float) or isinstance(value, bool) or not math.isfinite(value) or value <= 0.0:
            raise ValueError("start underlying price")
        normalized_prices[identity] = float(value)

    records: list[PredictionRecordV1] = []

    for entry in decision.entries:
        child = entry.child
        candidate = child.candidate
        selected = entry.outcome_reason == "SELECTED"

        if candidate is None:
            candidate_id = None
            market_timestamp = None
            direction = "UNAVAILABLE"
            eligibility = "UNAVAILABLE"
            confidence = 0.0
            score = 0.0
            candidate_blockers = ()
            candidate_warnings = ()
        else:
            candidate_id = candidate.candidate_id
            market_timestamp = candidate.market_timestamp
            direction = candidate.direction
            eligibility = candidate.eligibility
            confidence = candidate.confidence
            score = candidate.score
            candidate_blockers = candidate.blockers
            candidate_warnings = candidate.warnings

        records.append(
            PredictionRecordV1(
                prediction_id=(
                    f"prediction:{decision.parent_cycle_id}:"
                    f"{child.underlying_symbol}:{child.exchange}"
                ),
                parent_cycle_id=decision.parent_cycle_id,
                decision_result_id=decision.decision_result_id,
                child_result_id=child.child_result_id,
                observation_id=child.observation_id,
                underlying_symbol=child.underlying_symbol,
                exchange=child.exchange,
                requested_at=decision.requested_at,
                completed_at=decision.completed_at,
                observed_at=decision.completed_at,
                market_timestamp=market_timestamp,
                received_at=child.received_at,
                start_underlying_price=normalized_prices[(child.underlying_symbol, child.exchange)],
                terminal_status=child.terminal_status,
                candidate_id=candidate_id,
                predicted_direction=direction,
                predicted_action=_predicted_action(
                    direction,
                    selected=selected,
                ),
                eligibility=eligibility,
                confidence=confidence,
                score=score,
                rank_value=entry.rank_value,
                eligible_for_comparison=entry.eligible_for_comparison,
                outcome_reason=entry.outcome_reason,
                parent_decision=decision.decision,
                parent_selected=selected,
                rationale=entry.rationale,
                blockers=tuple(
                    dict.fromkeys(
                        (
                            *decision.blockers,
                            *child.blockers,
                            *candidate_blockers,
                        )
                    )
                ),
                warnings=tuple(
                    dict.fromkeys(
                        (
                            *decision.warnings,
                            *child.warnings,
                            *candidate_warnings,
                        )
                    )
                ),
                errors=child.errors,
            )
        )

    result = tuple(records)

    if len(result) != 2:
        raise ValueError("exactly two prediction records required")
    if tuple(
        (item.underlying_symbol, item.exchange)
        for item in result
    ) != (("NIFTY", "NSE"), ("SENSEX", "BSE")):
        raise ValueError("exact ordered NIFTY/SENSEX pair required")

    if lifecycle_window_sink is not None:
        policies = {("NIFTY", "NSE"): NSE_NIFTY_POLICY, ("SENSEX", "BSE"): BSE_SENSEX_POLICY}
        windows: tuple[PredictionLifecycleWindowV1, PredictionLifecycleWindowV1] = tuple(
            resolve_prediction_lifecycle_window(
                prediction_record=record,
                session_policy=policies[(record.underlying_symbol, record.exchange)],
                timing_policy=PredictionLifecycleTimingPolicyV1(),
            )
            for record in result
        )
        lifecycle_window_sink(windows)

    return result
