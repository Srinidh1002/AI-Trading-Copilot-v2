import pytest

from tests.task916_real_runtime_harness import (
    build_task916_real_runtime_harness,
)


@pytest.mark.parametrize(
    "market,expected_underlying,expected_cash_exchange,expected_derivative_exchange",
    (
        ("NIFTY", "NIFTY", "NSE", "NFO"),
        ("SENSEX", "SENSEX", "BSE", "BFO"),
    ),
)
def test_task916_real_runtime_harness_is_naturally_aligned(
    tmp_path,
    market,
    expected_underlying,
    expected_cash_exchange,
    expected_derivative_exchange,
):
    harness = build_task916_real_runtime_harness(
        tmp_path,
        market=market,
    )

    decision = harness.decision
    prediction = harness.selected_prediction
    cycle = harness.selected_cycle
    planning = harness.selected_planning
    context = harness.lifecycle_context_store.recover(
        prediction.prediction_id
    )

    assert decision.parent_cycle_id == (
        harness.seed.parent_cycle_id
    )

    assert prediction.parent_cycle_id == (
        decision.parent_cycle_id
    )

    assert prediction.observed_at == (
        decision.completed_at
    )

    assert (
        prediction.underlying_symbol,
        prediction.exchange,
    ) == (
        expected_underlying,
        expected_cash_exchange,
    )

    assert decision.selected_market == (
        expected_underlying,
        expected_cash_exchange,
    )

    assert planning.status == "READY"
    assert planning.execution_mode == "PAPER"
    assert planning.live_execution_eligible is False
    assert planning.broker_order_submission is False

    assert planning.bridge.parent_cycle_id == (
        decision.parent_cycle_id
    )

    assert planning.bridge.selected_market == (
        expected_underlying,
        expected_cash_exchange,
    )

    assert cycle.underlying_symbol == (
        expected_underlying
    )

    assert cycle.exchange == expected_cash_exchange

    assert planning.bridge.observation_id == (
        cycle.observation_id
    )

    assert context is not None
    assert context.prediction_id == (
        prediction.prediction_id
    )

    assert (
        context.window_starts_at
        <= harness.entry_observation.observed_at
        <= context.entry_window_ends_at
    )

    assert harness.entry_observation.market == (
        expected_underlying
    )

    assert harness.entry_observation.exchange == (
        expected_derivative_exchange
    )

    assert harness.entry_observation.observed_at == (
        decision.completed_at
    )

    restored = harness.prediction_ledger.recover(
        prediction.prediction_id
    )

    assert restored == prediction