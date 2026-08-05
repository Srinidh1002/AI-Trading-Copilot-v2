from dataclasses import replace
from datetime import datetime, timezone

import pytest

from services.contracts.paper_trade_position_evaluation_input_v1 import (
    PaperTradePositionEvaluationInputV1,
)
from services.paper_orchestration.certified_live_option_quote_reader import (
    CertifiedLiveOptionQuoteV1,
    derivative_exchange_for,
)
from services.paper_orchestration.certified_position_evaluation_input_factory import (
    CertifiedPositionEvaluationInputFactory,
)
from tests.test_r42_admitted_plan_simulated_entry_runtime import (
    _admitted_runtime_args,
)


NOW = datetime(
    2026,
    8,
    5,
    9,
    30,
    tzinfo=timezone.utc,
)


def open_snapshot(tmp_path):
    from services.paper_orchestration.admitted_plan_simulated_entry_runtime import (
        execute_admitted_plan_simulated_entry,
    )

    args, _, trade_service = _admitted_runtime_args(
        tmp_path
    )

    result = execute_admitted_plan_simulated_entry(
        **args
    )

    assert result.status == "OPEN"

    snapshot = trade_service.get(
        args["paper_trade_id"]
    )

    assert snapshot is not None
    assert snapshot.position is not None
    assert snapshot.latest_observation is not None

    return snapshot


def exact_cycle(snapshot):
    from services.contracts.paper_orchestration_cycle_input_v1 import (
        PaperOrchestrationCycleInputV1,
    )

    prior = snapshot.latest_observation
    position = snapshot.position

    assert prior is not None
    assert position is not None

    value = object.__new__(
        PaperOrchestrationCycleInputV1
    )

    fields = {
        "cycle_id": "monitor-cycle-1",
        "cycle_idempotency_key": "monitor-cycle-key-1",
        "underlying_symbol": position.underlying_symbol,
        "market_timestamp": NOW,
        "received_at": NOW,
        "cycle_requested_at": NOW,
        "metadata": {
            "spot_price": (
                prior.underlying_last_price + 5.0
            ),
        },
    }

    for name, item in fields.items():
        object.__setattr__(
            value,
            name,
            item,
        )

    return value


def quote(snapshot, **changes):
    position = snapshot.position
    assert position is not None

    value = CertifiedLiveOptionQuoteV1(
        paper_trade_id=snapshot.paper_trade_id,
        position_id=position.position_id,
        underlying_symbol=position.underlying_symbol,
        option_symbol=position.option_symbol,
        option_exchange=derivative_exchange_for(
            position.underlying_symbol,
            position.exchange,
        ),
        symboltoken="123456",
        option_last_price=position.entry_price + 2.0,
        provider_timestamp=NOW,
    )

    return replace(
        value,
        **changes,
    )


def test_builds_exact_position_evaluation_input(tmp_path):
    snapshot = open_snapshot(tmp_path)
    cycle = exact_cycle(snapshot)

    result = CertifiedPositionEvaluationInputFactory()(
        cycle_input=cycle,
        snapshot=snapshot,
        quote=quote(snapshot),
    )

    assert type(result) is (
        PaperTradePositionEvaluationInputV1
    )

    assert (
        result.position.position_id
        == snapshot.position.position_id
    )
    assert result.lifecycle_policy == (
        snapshot.lifecycle_policy
    )
    assert result.lifecycle_state == (
        snapshot.lifecycle_state
    )
    assert result.evaluation_timestamp == NOW
    assert result.observation.observed_at == NOW
    assert result.observation.received_at == NOW
    assert result.observation.option_last_price == (
        snapshot.position.entry_price + 2.0
    )
    assert result.observation.underlying_last_price == (
        snapshot.latest_observation.underlying_last_price
        + 5.0
    )
    assert len(result.exit_fill_ids) == 8
    assert len(set(result.exit_fill_ids)) == 8
    assert result.execution_mode == "PAPER"
    assert result.live_execution_eligible is False


def test_ids_are_deterministic(tmp_path):
    snapshot = open_snapshot(tmp_path)
    cycle = exact_cycle(snapshot)
    factory = CertifiedPositionEvaluationInputFactory()

    first = factory(
        cycle_input=cycle,
        snapshot=snapshot,
        quote=quote(snapshot),
    )

    second = factory(
        cycle_input=cycle,
        snapshot=snapshot,
        quote=quote(snapshot),
    )

    assert (
        first.requested_transition_id
        == second.requested_transition_id
    )
    assert (
        first.resulting_lifecycle_state_id
        == second.resulting_lifecycle_state_id
    )
    assert (
        first.evaluation_result_id
        == second.evaluation_result_id
    )
    assert first.exit_fill_ids == second.exit_fill_ids
    assert (
        first.pnl_evidence_id
        == second.pnl_evidence_id
    )


def test_quote_identity_mismatch_fails_closed(tmp_path):
    snapshot = open_snapshot(tmp_path)

    with pytest.raises(
        ValueError,
        match="quote identity",
    ):
        CertifiedPositionEvaluationInputFactory()(
            cycle_input=exact_cycle(snapshot),
            snapshot=snapshot,
            quote=quote(
                snapshot,
                paper_trade_id="wrong-trade",
            ),
        )


def test_other_market_position_uses_its_prior_underlying_price(
    tmp_path,
):
    snapshot = open_snapshot(tmp_path)
    cycle = exact_cycle(snapshot)

    object.__setattr__(
        cycle,
        "underlying_symbol",
        "SENSEX"
        if snapshot.position.underlying_symbol == "NIFTY"
        else "NIFTY",
    )

    result = CertifiedPositionEvaluationInputFactory()(
        cycle_input=cycle,
        snapshot=snapshot,
        quote=quote(snapshot),
    )

    assert (
        result.observation.underlying_last_price
        == snapshot.latest_observation.underlying_last_price
    )


def test_future_quote_timestamp_fails_closed(tmp_path):
    snapshot = open_snapshot(tmp_path)

    future = datetime(
        2026,
        8,
        5,
        9,
        31,
        tzinfo=timezone.utc,
    )

    with pytest.raises(
        ValueError,
        match="cannot follow",
    ):
        CertifiedPositionEvaluationInputFactory()(
            cycle_input=exact_cycle(snapshot),
            snapshot=snapshot,
            quote=quote(
                snapshot,
                provider_timestamp=future,
            ),
        )


def test_factory_does_not_mutate_snapshot(tmp_path):
    snapshot = open_snapshot(tmp_path)
    before = snapshot.to_json()

    CertifiedPositionEvaluationInputFactory()(
        cycle_input=exact_cycle(snapshot),
        snapshot=snapshot,
        quote=quote(snapshot),
    )

    assert snapshot.to_json() == before