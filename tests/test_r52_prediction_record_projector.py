from services.contracts.pre_entry_market_action_v1 import PreEntryMarketActionV1
from services.paper_orchestration.prediction_record_projector import (
    project_parent_decision_predictions,
)
from services.paper_orchestration.two_market_parent_cycle_coordinator import (
    run_two_market_parent_cycle,
)
from test_two_market_parent_cycle_coordinator import (
    candidate_for,
    parent,
)


START_PRICES = {
    ("NIFTY", "NSE"): 25000.0,
    ("SENSEX", "BSE"): 80000.0,
}


def pre_entry_actions_for(decision):
    """Build canonical pre-entry actions for completed candidate children."""

    actions = {}

    for entry in decision.entries:
        child = entry.child
        candidate = child.candidate

        if child.terminal_status != "COMPLETED" or candidate is None:
            continue

        if (
            candidate.eligibility == "ELIGIBLE"
            and candidate.direction == "BULLISH"
        ):
            action = "CALL"
            reasons = ("ELIGIBLE_BULLISH_CANDIDATE",)

        elif (
            candidate.eligibility == "ELIGIBLE"
            and candidate.direction == "BEARISH"
        ):
            action = "PUT"
            reasons = ("ELIGIBLE_BEARISH_CANDIDATE",)

        elif (
            candidate.eligibility == "INELIGIBLE"
            and candidate.direction == "NEUTRAL"
        ):
            action = "WAIT"
            reasons = ("DIRECTION_NEUTRAL_NO_ENTRY",)

        else:
            action = "NO_TRADE"
            reasons = (
                candidate.blockers
                if candidate.blockers
                else ("REQUIRED_EVIDENCE_UNAVAILABLE",)
            )

        actions[child.observation_id] = PreEntryMarketActionV1(
            action_id=(
                f"pre-entry:{decision.parent_cycle_id}:"
                f"{child.observation_id}"
            ),
            underlying_symbol=child.underlying_symbol,
            exchange=child.exchange,
            cycle_id=decision.parent_cycle_id,
            observation_id=child.observation_id,
            candidate_id=candidate.candidate_id,
            action=action,
            candidate_direction=candidate.direction,
            candidate_eligibility=candidate.eligibility,
            confidence=candidate.confidence,
            score=candidate.score,
            regime_suitability="SUITABLE",
            selected_for_parent_comparison=entry.eligible_for_comparison,
            source_ledger_id=None,
            evaluated_at=decision.completed_at,
            blockers=candidate.blockers,
            reasons=reasons,
        )

    return actions


def project(decision, **kwargs):
    return project_parent_decision_predictions(
        decision,
        start_underlying_prices=START_PRICES,
        pre_entry_actions=pre_entry_actions_for(decision),
        **kwargs,
    )


def test_selected_parent_preserves_independent_call_and_put_actions():
    decision = run_two_market_parent_cycle(
        parent(),
        child_evaluator=(
            lambda symbol, exchange, observation_id: candidate_for(
                symbol,
                observation_id,
                score=80.0 if symbol == "NIFTY" else 60.0,
                direction=(
                    "BULLISH"
                    if symbol == "NIFTY"
                    else "BEARISH"
                ),
            )
        ),
    )

    records = project(decision)

    assert tuple(
        (item.underlying_symbol, item.exchange)
        for item in records
    ) == (("NIFTY", "NSE"), ("SENSEX", "BSE"))

    assert records[0].predicted_action == "CALL"
    assert records[0].parent_selected is True

    assert records[1].predicted_action == "PUT"
    assert records[1].parent_selected is False


def test_failed_child_still_projects_one_prediction_record():
    def evaluator(symbol, exchange, observation_id):
        if symbol == "NIFTY":
            raise RuntimeError("injected failure")

        return candidate_for(
            symbol,
            observation_id,
            score=65.0,
            direction="BEARISH",
        )

    decision = run_two_market_parent_cycle(
        parent(),
        child_evaluator=evaluator,
    )

    records = project(decision)

    assert records[0].terminal_status == "FAILED"
    assert records[0].candidate_id is None
    assert records[0].predicted_action == "NO_TRADE"

    assert records[1].predicted_action == "PUT"
    assert records[1].parent_selected is True


def test_parent_no_trade_preserves_two_independent_wait_actions():
    decision = run_two_market_parent_cycle(
        parent(),
        child_evaluator=(
            lambda symbol, exchange, observation_id: candidate_for(
                symbol,
                observation_id,
                eligibility="INELIGIBLE",
                direction="NEUTRAL",
                score=0.0,
                confidence=0.0,
                contradictions=(f"{symbol}_NEUTRAL_NO_ENTRY",),
            )
        ),
    )

    records = project(decision)

    assert decision.decision == "NO_TRADE"
    assert tuple(
        item.predicted_action
        for item in records
    ) == ("WAIT", "WAIT")

    assert tuple(
        item.parent_selected
        for item in records
    ) == (False, False)


def test_projection_is_deterministic():
    decision = run_two_market_parent_cycle(
        parent(),
        child_evaluator=(
            lambda symbol, exchange, observation_id: candidate_for(
                symbol,
                observation_id,
                score=80.0 if symbol == "NIFTY" else 60.0,
            )
        ),
    )

    first = project(decision)
    second = project(decision)

    assert first == second

    assert tuple(
        item.semantic_hash
        for item in first
    ) == tuple(
        item.semantic_hash
        for item in second
    )


def test_projection_retains_exact_start_prices():
    decision = run_two_market_parent_cycle(
        parent(),
        child_evaluator=(
            lambda symbol, exchange, observation_id: candidate_for(
                symbol,
                observation_id,
                score=80.0 if symbol == "NIFTY" else 60.0,
            )
        ),
    )

    records = project(decision)

    assert tuple(
        item.start_underlying_price
        for item in records
    ) == (25000.0, 80000.0)


def test_projection_creates_independent_lifecycle_windows_for_both_markets():
    decision = run_two_market_parent_cycle(
        parent(),
        child_evaluator=(
            lambda symbol, exchange, observation_id: candidate_for(
                symbol,
                observation_id,
                score=80.0 if symbol == "NIFTY" else 60.0,
                direction=(
                    "BULLISH"
                    if symbol == "NIFTY"
                    else "BEARISH"
                ),
            )
        ),
    )

    captured = []

    records = project(
        decision,
        lifecycle_window_sink=lambda windows: captured.extend(windows),
    )

    assert tuple(
        item.observed_at
        for item in records
    ) == (
        decision.completed_at,
        decision.completed_at,
    )

    assert tuple(
        window.prediction_id
        for window in captured
    ) == tuple(
        record.prediction_id
        for record in records
    )

    assert tuple(
        window.action
        for window in captured
    ) == ("CALL", "PUT")

    assert records[0].parent_selected is True
    assert records[1].parent_selected is False
