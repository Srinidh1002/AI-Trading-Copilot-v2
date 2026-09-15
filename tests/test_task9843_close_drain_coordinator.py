from dataclasses import replace
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from services.certification.task9_close_drain_coordinator import (
    coordinate_task9_close_drain,
)
from services.certification.task9_close_drain_state_store import (
    Task9CloseDrainStateStore,
)
from services.contracts.prediction_lifecycle_outcome_policy_v1 import (
    PredictionLifecycleOutcomePolicyV1,
)
from services.contracts.task9_close_drain_state_v1 import (
    Task9CloseDrainStatus,
)
from services.contracts.task9_market_session_policy_v1 import (
    Task9MarketSegment,
    Task9SessionPhase,
)
from services.contracts.task9_market_session_state_v1 import (
    Task9SegmentSessionStateV1,
)
from services.paper_orchestration.prediction_ledger import (
    PredictionLedger,
)
from services.paper_trade_repository import (
    PaperTradeRepository,
)
from services.paper_trading.paper_trade_persistence_service import (
    PaperTradePersistenceService,
)
from tests.test_task916_production_child_evidence_authority import (
    _quote,
    _runtime,
)


IST = ZoneInfo("Asia/Kolkata")


def _policy():
    return PredictionLifecycleOutcomePolicyV1(
        policy_id="task9843-close-drain",
        policy_version="1.0",
    )


def _state(
    segment,
    phase,
    day,
    evaluated_at,
):
    active = phase in {
        Task9SessionPhase.OPEN,
        Task9SessionPhase.ENTRY_RESTRICTED,
    }

    return Task9SegmentSessionStateV1(
        segment=segment,
        market_date=day,
        evaluated_at=evaluated_at,
        timezone="Asia/Kolkata",
        phase=phase,
        market_open=active,
        new_entries_allowed=(
            phase is Task9SessionPhase.OPEN
        ),
        position_monitoring_allowed=active,
        close_drain_required=False,
        session_open_time=time(9, 15),
        new_entry_cutoff=time(15, 30),
        position_monitoring_until=time(15, 40),
        session_close_time=time(15, 40),
        calendar_status="TRADING_DAY",
        policy_id="task9843",
        policy_version="1",
    )


def _states(day, evaluated_at, phase):
    return (
        _state(
            Task9MarketSegment.NFO_OPTIONS,
            phase,
            day,
            evaluated_at,
        ),
        _state(
            Task9MarketSegment.BFO_OPTIONS,
            phase,
            day,
            evaluated_at,
        ),
    )


def _coordinate(
    tmp_path,
    runtime,
    *,
    evaluated_at,
    phase,
):
    prediction = runtime["predictions"][0]
    day = prediction.completed_at.astimezone(
        IST
    ).date()

    return coordinate_task9_close_drain(
        official_run_id="task9843-run",
        market_date=day,
        evaluated_at=evaluated_at,
        session_states=_states(
            day,
            evaluated_at,
            phase,
        ),
        prediction_ledger=runtime["ledger"],
        binding_store=runtime["binding_store"],
        lifecycle_context_store=(
            runtime["context_store"]
        ),
        observation_store=(
            runtime["observation_store"]
        ),
        outcome_store=runtime["outcome_store"],
        reconciliation_store=(
            runtime["reconciliation_store"]
        ),
        trade_persistence_service=(
            runtime["trade_service"]
        ),
        outcome_policy=_policy(),
        state_store=Task9CloseDrainStateStore(
            tmp_path
        ),
    )


@pytest.mark.parametrize(
    "phase",
    (
        Task9SessionPhase.OPEN,
        Task9SessionPhase.ENTRY_RESTRICTED,
    ),
)
def test_active_session_does_not_run_close_drain(
    tmp_path,
    phase,
):
    runtime = _runtime(
        tmp_path / "runtime",
        nifty_action="WAIT",
        sensex_action="NO_TRADE",
    )
    prediction = runtime["predictions"][0]

    result = _coordinate(
        tmp_path / "state",
        runtime,
        evaluated_at=prediction.completed_at,
        phase=phase,
    )

    assert (
        result.status
        is Task9CloseDrainStatus.NOT_REQUIRED
    )
    assert (
        runtime["outcome_store"].recover(
            prediction.prediction_id
        )
        is None
    )


def test_closed_expired_durable_wait_is_finalized_then_complete(
    tmp_path,
):
    runtime = _runtime(
        tmp_path / "runtime",
        nifty_action="WAIT",
        sensex_action="NO_TRADE",
    )
    prediction = runtime["predictions"][0]

    context = runtime["context_store"].recover(
        prediction.prediction_id
    )

    runtime["observation_store"].initialize(
        prediction=prediction,
        entry_window_ends_at=(
            context.entry_window_ends_at
        ),
        validity_window_ends_at=(
            context.validity_window_ends_at
        ),
    )

    quote, quality = _quote(prediction)

    from services.certification.task9_abstention_later_observation_recovery import (
        recover_task9_later_abstention_observations,
    )

    recover_task9_later_abstention_observations(
        market=prediction.underlying_symbol,
        exchange=prediction.exchange,
        quote=quote,
        data_quality=quality,
        prediction_ledger=runtime["ledger"],
        lifecycle_context_store=(
            runtime["context_store"]
        ),
        observation_store=(
            runtime["observation_store"]
        ),
        outcome_store=runtime["outcome_store"],
        outcome_policy=_policy(),
        evaluated_at=quote.observed_at,
    )

    boundary = (
        context.validity_window_ends_at
    )

    result = _coordinate(
        tmp_path / "state",
        runtime,
        evaluated_at=boundary,
        phase=Task9SessionPhase.CLOSED,
    )

    assert (
        runtime["outcome_store"].recover(
            prediction.prediction_id
        )
        is not None
    )

    # Other session predictions may still be pending,
    # so the coordinator must never claim COMPLETE
    # merely because this WAIT was finalized.
    assert result.status in {
        Task9CloseDrainStatus.PENDING,
        Task9CloseDrainStatus.BLOCKED,
        Task9CloseDrainStatus.COMPLETE,
    }

    item = next(
        item
        for item in result.items
        if item.prediction_id
        == prediction.prediction_id
    )
    assert item.status.value == "COMPLETE"


def test_closed_unexpired_abstention_remains_pending(
    tmp_path,
):
    runtime = _runtime(
        tmp_path / "runtime",
        nifty_action="WAIT",
        sensex_action="NO_TRADE",
    )
    prediction = runtime["predictions"][0]
    context = runtime["context_store"].recover(
        prediction.prediction_id
    )

    runtime["observation_store"].initialize(
        prediction=prediction,
        entry_window_ends_at=(
            context.entry_window_ends_at
        ),
        validity_window_ends_at=(
            context.validity_window_ends_at
        ),
    )

    boundary = prediction.completed_at

    result = _coordinate(
        tmp_path / "state",
        runtime,
        evaluated_at=boundary,
        phase=Task9SessionPhase.CLOSED,
    )

    item = next(
        item
        for item in result.items
        if item.prediction_id
        == prediction.prediction_id
    )

    assert item.status.value == "PENDING"
    assert item.reason_codes == (
        "ABSTENTION_VALIDITY_PENDING",
    )
    assert result.finalization_allowed is False


def test_state_store_restart_recovers_latest_state(
    tmp_path,
):
    runtime = _runtime(
        tmp_path / "runtime",
        nifty_action="WAIT",
        sensex_action="NO_TRADE",
    )
    prediction = runtime["predictions"][0]

    first = _coordinate(
        tmp_path / "state",
        runtime,
        evaluated_at=prediction.completed_at,
        phase=Task9SessionPhase.OPEN,
    )

    restarted = Task9CloseDrainStateStore(
        tmp_path / "state"
    ).get(
        official_run_id="task9843-run",
        market_date=(
            prediction.completed_at
            .astimezone(IST)
            .date()
        ),
    )

    assert restarted is not None
    assert restarted.to_dict() == first.to_dict()


def test_complete_receipt_is_sealed(tmp_path):
    store = Task9CloseDrainStateStore(
        tmp_path
    )
    day = date(2026, 8, 17)
    at = datetime(
        2026,
        8,
        17,
        15,
        40,
        tzinfo=IST,
    )

    from services.certification.task9_close_drain_evaluator import (
        evaluate_task9_close_drain,
    )

    complete = evaluate_task9_close_drain(
        official_run_id="run",
        market_date=day,
        evaluated_at=at,
        session_states=_states(
            day,
            at,
            Task9SessionPhase.CLOSED,
        ),
        items=(),
    )

    first = store.save(complete)
    second = store.save(
        replace(
            complete,
            evaluated_at=(
                at.replace(second=1)
            ),
        )
    )

    assert second.to_dict() == first.to_dict()


def test_complete_receipt_rejects_semantic_regression(
    tmp_path,
):
    store = Task9CloseDrainStateStore(
        tmp_path
    )
    day = date(2026, 8, 17)
    at = datetime(
        2026,
        8,
        17,
        15,
        40,
        tzinfo=IST,
    )

    from services.certification.task9_close_drain_evaluator import (
        evaluate_task9_close_drain,
    )
    from services.contracts.task9_close_drain_state_v1 import (
        Task9CloseDrainItemKind,
        Task9CloseDrainItemStatus,
        Task9CloseDrainItemV1,
    )

    complete = evaluate_task9_close_drain(
        official_run_id="run",
        market_date=day,
        evaluated_at=at,
        session_states=_states(
            day,
            at,
            Task9SessionPhase.CLOSED,
        ),
        items=(),
    )
    store.save(complete)

    changed = evaluate_task9_close_drain(
        official_run_id="run",
        market_date=day,
        evaluated_at=at,
        session_states=_states(
            day,
            at,
            Task9SessionPhase.CLOSED,
        ),
        items=(
            Task9CloseDrainItemV1(
                prediction_id="late",
                market="NIFTY",
                kind=(
                    Task9CloseDrainItemKind.PAPER_TRADE
                ),
                status=(
                    Task9CloseDrainItemStatus.PENDING
                ),
                reason_codes=(
                    "PAPER_POSITION_OPEN",
                ),
            ),
        ),
    )

    with pytest.raises(
        ValueError,
        match="sealed Task9 close-drain conflict",
    ):
        store.save(changed)
