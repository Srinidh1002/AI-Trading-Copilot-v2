"""Pure deterministic projection of one parent result into two predictions."""
from __future__ import annotations

from services.contracts.prediction_record_v1 import PredictionRecordV1
from services.contracts.two_market_decision_result_v1 import (
    TwoMarketDecisionResultV1,
)


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
) -> tuple[PredictionRecordV1, PredictionRecordV1]:
    """Project one parent decision into exact ordered NIFTY/SENSEX records."""

    if type(decision) is not TwoMarketDecisionResultV1:
        raise TypeError("decision")

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
                market_timestamp=market_timestamp,
                received_at=child.received_at,
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

    return result
