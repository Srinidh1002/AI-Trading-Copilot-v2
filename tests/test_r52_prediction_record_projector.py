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


def test_selected_parent_projects_call_and_wait_records():
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

    records = project_parent_decision_predictions(decision,
        start_underlying_prices={("NIFTY", "NSE"): 25000.0, ("SENSEX", "BSE"): 80000.0},
    )

    assert tuple(
        (item.underlying_symbol, item.exchange)
        for item in records
    ) == (("NIFTY", "NSE"), ("SENSEX", "BSE"))
    assert records[0].predicted_action == "CALL"
    assert records[0].parent_selected is True
    assert records[1].predicted_action == "WAIT"
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

    records = project_parent_decision_predictions(decision,
        start_underlying_prices={("NIFTY", "NSE"): 25000.0, ("SENSEX", "BSE"): 80000.0},
    )

    assert records[0].terminal_status == "FAILED"
    assert records[0].candidate_id is None
    assert records[0].predicted_action == "WAIT"
    assert records[1].predicted_action == "PUT"
    assert records[1].parent_selected is True


def test_no_trade_projects_two_wait_records():
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
                blockers=(f"{symbol}_BLOCKED",),
            )
        ),
    )

    records = project_parent_decision_predictions(decision,
        start_underlying_prices={("NIFTY", "NSE"): 25000.0, ("SENSEX", "BSE"): 80000.0},
    )

    assert decision.decision == "NO_TRADE"
    assert tuple(
        item.predicted_action for item in records
    ) == ("WAIT", "WAIT")
    assert tuple(
        item.parent_selected for item in records
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

    first = project_parent_decision_predictions(decision,
        start_underlying_prices={("NIFTY", "NSE"): 25000.0, ("SENSEX", "BSE"): 80000.0},
    )
    second = project_parent_decision_predictions(decision,
        start_underlying_prices={("NIFTY", "NSE"): 25000.0, ("SENSEX", "BSE"): 80000.0},
    )

    assert first == second
    assert tuple(item.semantic_hash for item in first) == tuple(
        item.semantic_hash for item in second
    )


def test_projection_retains_exact_start_prices():
    decision = run_two_market_parent_cycle(parent(), child_evaluator=lambda symbol, exchange, observation_id: candidate_for(symbol, observation_id, score=80.0 if symbol == "NIFTY" else 60.0))
    records = project_parent_decision_predictions(decision, start_underlying_prices={("NIFTY", "NSE"): 25000.0, ("SENSEX", "BSE"): 80000.0})
    assert tuple(item.start_underlying_price for item in records) == (25000.0, 80000.0)


def test_projection_creates_independent_lifecycle_windows_for_selected_and_wait():
    decision = run_two_market_parent_cycle(
        parent(),
        child_evaluator=lambda symbol, exchange, observation_id: candidate_for(
            symbol, observation_id, score=80.0 if symbol == "NIFTY" else 60.0,
            direction="BULLISH" if symbol == "NIFTY" else "BEARISH",
        ),
    )
    captured = []
    records = project_parent_decision_predictions(
        decision,
        start_underlying_prices={("NIFTY", "NSE"): 25000.0, ("SENSEX", "BSE"): 80000.0},
        lifecycle_window_sink=lambda windows: captured.extend(windows),
    )

    assert tuple(item.observed_at for item in records) == (decision.completed_at, decision.completed_at)
    assert tuple(window.prediction_id for window in captured) == tuple(record.prediction_id for record in records)
    assert tuple(window.action for window in captured) == ("CALL", "WAIT")
    assert captured[1].entry_window_ends_at == captured[1].window_starts_at
