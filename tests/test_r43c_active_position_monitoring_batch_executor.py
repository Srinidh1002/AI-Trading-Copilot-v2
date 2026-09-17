from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
)
from services.contracts.paper_orchestration_cycle_result_v1 import (
    PaperOrchestrationCycleResultV1,
)
from services.contracts.paper_portfolio_policy_v1 import (
    PaperPortfolioPolicyV1,
)
from services.paper_orchestration.active_position_monitoring_batch_executor import (
    ActivePositionMonitoringBatchExecutor,
)
from services.paper_orchestration.certified_live_option_quote_reader import (
    CertifiedLiveOptionQuoteReader,
    CertifiedLiveOptionQuoteV1,
)
from services.paper_orchestration.certified_position_evaluation_input_factory import (
    CertifiedPositionEvaluationInputFactory,
)
from services.paper_orchestration.existing_position_monitoring_executor import (
    ExistingPositionMonitoringExecutor,
    ExistingPositionMonitoringResultV1,
)
from services.paper_trading.paper_trade_recovery_service import (
    PaperTradeRecoveryService,
)
from services.contracts.paper_trade_persistence_snapshot_v1 import (
    PaperTradePersistenceSnapshotV1,
)
from services.contracts.paper_trade_position_evaluation_input_v1 import (
    PaperTradePositionEvaluationInputV1,
)

NOW = datetime(
    2026,
    8,
    5,
    9,
    30,
    tzinfo=timezone.utc,
)

HASH = "a" * 64


def exact(contract, **fields):
    value = object.__new__(contract)

    for name, item in fields.items():
        object.__setattr__(
            value,
            name,
            item,
        )

    return value


def cycle():
    return exact(
        PaperOrchestrationCycleInputV1,
        cycle_id="monitoring-cycle-1",
        cycle_idempotency_key="monitoring-cycle-key-1",
        cycle_requested_at=NOW,
        market_timestamp=NOW,
        received_at=NOW,
        underlying_symbol="NIFTY",
        metadata={"spot_price": 25000.0},
    )


def policy():
    return exact(
        PaperPortfolioPolicyV1,
    )


def snapshot(
    trade_id,
    position_id,
    *,
    created_at=NOW,
    terminal=False,
    option_symbol=None,
):
    lifecycle_state = type(
        "LifecycleState",
        (),
        {
            "is_terminal": terminal,
        },
    )()

    position = type(
        "Position",
        (),
        {
            "position_id": position_id,
            "underlying_symbol": "NIFTY",
            "option_symbol": (
                option_symbol
                or f"NIFTY-OPTION-{position_id}"
            ),
            "lifecycle_state": (
                "CLOSED_STOP"
                if terminal
                else "OPEN"
            ),
        },
    )()

    return exact(
        PaperTradePersistenceSnapshotV1,
        paper_trade_id=trade_id,
        adapter_idempotency_key=(
            f"adapter-key-{trade_id}"
        ),
        position=position,
        lifecycle_state=lifecycle_state,
        created_at=created_at,
    )


def quote_for(snapshot_value):
    return exact(
        CertifiedLiveOptionQuoteV1,
        paper_trade_id=snapshot_value.paper_trade_id,
        position_id=snapshot_value.position.position_id,
        underlying_symbol=(
            snapshot_value.position.underlying_symbol
        ),
        option_symbol=(
            snapshot_value.position.option_symbol
        ),
        option_exchange="NFO",
        symboltoken=(
            f"token-{snapshot_value.paper_trade_id}"
        ),
        option_last_price=100.0,
        provider_timestamp=NOW,
    )


def monitoring_input(snapshot_value):
    return exact(
        PaperTradePositionEvaluationInputV1,
        position=snapshot_value.position,
        evaluation_timestamp=NOW,
    )


def monitoring_result(
    status,
    *,
    blockers=(),
    warnings=(),
):
    state_changed = status in {
        "HOLD_UPDATED",
        "PARTIAL_EXIT",
        "CLOSED",
    }

    action_occurred = status in {
        "PARTIAL_EXIT",
        "CLOSED",
    }

    return exact(
        ExistingPositionMonitoringResultV1,
        status=status,
        p7_state_changed=state_changed,
        p8_state_changed=state_changed,
        paper_action_occurred=action_occurred,
        blockers=blockers,
        warnings=warnings,
    )


def dependencies(active_snapshots):
    recovery = object.__new__(
        PaperTradeRecoveryService
    )
    recovery.recover_active = (
        lambda: tuple(active_snapshots)
    )

    quote_reader = object.__new__(
        CertifiedLiveOptionQuoteReader
    )

    evaluation_factory = object.__new__(
        CertifiedPositionEvaluationInputFactory
    )

    monitoring_executor = object.__new__(
        ExistingPositionMonitoringExecutor
    )

    executor = ActivePositionMonitoringBatchExecutor(
        portfolio_id="certified-paper-portfolio",
        trade_recovery_service=recovery,
        quote_reader=quote_reader,
        evaluation_input_factory=(
            evaluation_factory
        ),
        monitoring_executor=monitoring_executor,
        portfolio_policy_provider=lambda _: policy(),
        clock=lambda: NOW,
    )

    return (
        executor,
        quote_reader,
        evaluation_factory,
        monitoring_executor,
    )


def test_empty_active_set_returns_completed_no_action():
    (
        executor,
        _,
        _,
        _,
    ) = dependencies(())

    with patch.object(
        PaperOrchestrationCycleInputV1,
        "semantic_hash",
        return_value=HASH,
    ):
        result = executor(cycle())

    assert type(result) is PaperOrchestrationCycleResultV1
    assert result.cycle_status == "COMPLETED_NO_ACTION"
    assert result.terminal_stage == "P7_LIFECYCLE"
    assert result.paper_actions == ()
    assert result.metadata["active_trade_count"] == 0
    assert result.metadata["processed_trade_count"] == 0
    assert result.execution_mode == "PAPER"
    assert result.live_execution_eligible is False


def test_multiple_active_trades_run_in_stable_order():
    later = snapshot(
        "trade-b",
        "position-b",
        created_at=NOW + timedelta(seconds=1),
    )
    earlier = snapshot(
        "trade-a",
        "position-a",
        created_at=NOW,
    )

    (
        executor,
        quote_reader,
        evaluation_factory,
        monitoring_executor,
    ) = dependencies((later, earlier))

    order = []

    def read_quote(snapshot_value):
        order.append(
            (
                "QUOTE",
                snapshot_value.paper_trade_id,
            )
        )
        return quote_for(snapshot_value)

    def build_evaluation(
        *,
        cycle_input,
        snapshot,
        quote,
    ):
        order.append(
            (
                "EVALUATION",
                snapshot.paper_trade_id,
            )
        )
        return monitoring_input(snapshot)

    def execute_monitoring(value):
        index = len(
            [
                item
                for item in order
                if item[0] == "MONITOR"
            ]
        )

        trade_id = (
            "trade-a"
            if index == 0
            else "trade-b"
        )

        order.append(
            (
                "MONITOR",
                trade_id,
            )
        )

        return monitoring_result(
            "HOLD_NO_CHANGE"
        )

    with (
        patch.object(
            CertifiedLiveOptionQuoteReader,
            "__call__",
            side_effect=read_quote,
        ),
        patch.object(
            CertifiedPositionEvaluationInputFactory,
            "__call__",
            side_effect=build_evaluation,
        ),
        patch.object(
            monitoring_executor,
            "execute",
            side_effect=execute_monitoring,
        ),
        patch.object(
            PaperOrchestrationCycleInputV1,
            "semantic_hash",
            return_value=HASH,
        ),
    ):
        result = executor(cycle())

    assert result.cycle_status == "COMPLETED_NO_ACTION"
    assert result.metadata["active_trade_count"] == 2
    assert result.metadata["processed_trade_count"] == 2

    outcomes = result.metadata["trade_outcomes"]

    assert tuple(
        item["paper_trade_id"]
        for item in outcomes
    ) == (
        "trade-a",
        "trade-b",
    )

    assert order == [
        ("QUOTE", "trade-a"),
        ("EVALUATION", "trade-a"),
        ("MONITOR", "trade-a"),
        ("QUOTE", "trade-b"),
        ("EVALUATION", "trade-b"),
        ("MONITOR", "trade-b"),
    ]


def test_one_failed_trade_does_not_prevent_next_trade():
    first = snapshot(
        "trade-a",
        "position-a",
        created_at=NOW,
    )
    second = snapshot(
        "trade-b",
        "position-b",
        created_at=NOW + timedelta(seconds=1),
    )

    (
        executor,
        quote_reader,
        evaluation_factory,
        monitoring_executor,
    ) = dependencies((first, second))

    quote_calls = []

    def read_quote(snapshot_value):
        quote_calls.append(
            snapshot_value.paper_trade_id
        )

        if snapshot_value.paper_trade_id == "trade-a":
            raise RuntimeError(
                "option quote unavailable"
            )

        return quote_for(snapshot_value)

    with (
        patch.object(
            CertifiedLiveOptionQuoteReader,
            "__call__",
            side_effect=read_quote,
        ),
        patch.object(
            CertifiedPositionEvaluationInputFactory,
            "__call__",
            side_effect=lambda **kwargs: monitoring_input(
                kwargs["snapshot"]
            ),
        ),
        patch.object(
            monitoring_executor,
            "execute",
            return_value=monitoring_result(
                "HOLD_NO_CHANGE"
            ),
        ),
        patch.object(
            PaperOrchestrationCycleInputV1,
            "semantic_hash",
            return_value=HASH,
        ),
    ):
        result = executor(cycle())

    assert quote_calls == [
        "trade-a",
        "trade-b",
    ]

    assert result.cycle_status == "COMPLETED_NO_ACTION"
    assert result.errors == (
        "ACTIVE_POSITION_MONITORING_RUNTIMEERROR",
    )

    outcomes = result.metadata["trade_outcomes"]

    assert outcomes[0]["status"] == "FAILED"
    assert outcomes[1]["status"] == "HOLD_NO_CHANGE"


def test_blocked_trade_does_not_prevent_valid_trade():
    first = snapshot(
        "trade-a",
        "position-a",
        created_at=NOW,
    )
    second = snapshot(
        "trade-b",
        "position-b",
        created_at=NOW + timedelta(seconds=1),
    )

    (
        executor,
        quote_reader,
        evaluation_factory,
        monitoring_executor,
    ) = dependencies((first, second))

    results = iter(
        (
            monitoring_result(
                "BLOCKED",
                blockers=("STALE_OBSERVATION",),
            ),
            monitoring_result(
                "HOLD_NO_CHANGE"
            ),
        )
    )

    with (
        patch.object(
            CertifiedLiveOptionQuoteReader,
            "__call__",
            side_effect=lambda item: quote_for(item),
        ),
        patch.object(
            CertifiedPositionEvaluationInputFactory,
            "__call__",
            side_effect=lambda **kwargs: monitoring_input(
                kwargs["snapshot"]
            ),
        ),
        patch.object(
            monitoring_executor,
            "execute",
            side_effect=lambda _: next(results),
        ),
        patch.object(
            PaperOrchestrationCycleInputV1,
            "semantic_hash",
            return_value=HASH,
        ),
    ):
        result = executor(cycle())

    assert result.cycle_status == "COMPLETED_NO_ACTION"
    assert result.blockers == (
        "STALE_OBSERVATION",
    )

    outcomes = result.metadata["trade_outcomes"]

    assert outcomes[0]["status"] == "BLOCKED"
    assert outcomes[1]["status"] == "HOLD_NO_CHANGE"


def test_partial_exit_produces_p7_and_p8_stages():
    active = snapshot(
        "trade-a",
        "position-a",
    )

    (
        executor,
        quote_reader,
        evaluation_factory,
        monitoring_executor,
    ) = dependencies((active,))

    with (
        patch.object(
            CertifiedLiveOptionQuoteReader,
            "__call__",
            side_effect=lambda item: quote_for(item),
        ),
        patch.object(
            CertifiedPositionEvaluationInputFactory,
            "__call__",
           side_effect=lambda **kwargs: monitoring_input(
                kwargs["snapshot"]
            ),
        ),
        patch.object(
            monitoring_executor,
            "execute",
            return_value=monitoring_result(
                "PARTIAL_EXIT"
            ),
        ),
        patch.object(
            PaperOrchestrationCycleInputV1,
            "semantic_hash",
            return_value=HASH,
        ),
    ):
        result = executor(cycle())

    assert result.cycle_status == "COMPLETED"
    assert result.terminal_stage == "P8_PORTFOLIO_UPDATE"
    assert result.paper_actions == (
        "PARTIAL_EXIT_POSITION",
    )

    assert tuple(
        stage.stage
        for stage in result.stage_results
    ) == (
        "P7_LIFECYCLE",
        "P8_PORTFOLIO_UPDATE",
    )


def test_all_failures_return_failed_cycle():
    active = snapshot(
        "trade-a",
        "position-a",
    )

    (
        executor,
        quote_reader,
        _,
        _,
    ) = dependencies((active,))

    with (
        patch.object(
            CertifiedLiveOptionQuoteReader,
            "__call__",
            side_effect=RuntimeError(
                "provider unavailable"
            ),
        ),
        patch.object(
            PaperOrchestrationCycleInputV1,
            "semantic_hash",
            return_value=HASH,
        ),
    ):
        result = executor(cycle())

    assert result.cycle_status == "FAILED"
    assert result.terminal_stage == "P7_LIFECYCLE"
    assert result.stage_results[0].status == "FAILED"
    assert result.stage_results[0].failure is not None
    assert (
        result.stage_results[0]
        .failure
        .failure_code
        == "ACTIVE_POSITION_BATCH_FAILURE"
    )


def test_terminal_trade_is_rejected_before_quote():
    terminal = snapshot(
        "trade-terminal",
        "position-terminal",
        terminal=True,
    )

    (
        executor,
        quote_reader,
        _,
        _,
    ) = dependencies((terminal,))

    with patch.object(
        quote_reader,
        "__call__",
    ) as quote_call:
        try:
            executor(cycle())
        except ValueError as exc:
            assert (
                "terminal trade"
                in str(exc)
            )
        else:
            raise AssertionError(
                "terminal recovery result must fail closed"
            )

    quote_call.assert_not_called()


def test_duplicate_position_identity_is_rejected():
    first = snapshot(
        "trade-a",
        "position-shared",
    )
    second = snapshot(
        "trade-b",
        "position-shared",
        created_at=NOW + timedelta(seconds=1),
    )

    (
        executor,
        quote_reader,
        _,
        _,
    ) = dependencies((first, second))

    with patch.object(
        quote_reader,
        "__call__",
    ) as quote_call:
        try:
            executor(cycle())
        except ValueError as exc:
            assert "duplicate position_id" in str(exc)
        else:
            raise AssertionError(
                "duplicate active positions must fail closed"
            )

    quote_call.assert_not_called()
