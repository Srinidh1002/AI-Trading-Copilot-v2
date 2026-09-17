from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from services.contracts.paper_portfolio_persistence_snapshot_v1 import (
    PaperPortfolioPersistenceSnapshotV1,
)
from services.contracts.paper_trade_persistence_snapshot_v1 import (
    PaperTradePersistenceSnapshotV1,
)
from services.contracts.paper_trade_position_evaluation_result_v1 import (
    PaperTradePositionEvaluationResultV1,
)
from services.paper_orchestration.existing_position_monitoring_executor import (
    ExistingPositionMonitoringExecutor,
    ExistingPositionMonitoringInputV1,
)
from services.paper_portfolio.paper_portfolio_lifecycle_coordinator import (
    PaperPortfolioLifecycleCoordinator,
)
from services.paper_trading.paper_trade_replay_coordinator import (
    PaperTradeReplayCoordinator,
)


NOW = datetime(
    2026,
    1,
    8,
    9,
    30,
    tzinfo=timezone.utc,
)


def p7_snapshot() -> PaperTradePersistenceSnapshotV1:
    return object.__new__(PaperTradePersistenceSnapshotV1)


def p8_snapshot() -> PaperPortfolioPersistenceSnapshotV1:
    return object.__new__(PaperPortfolioPersistenceSnapshotV1)


def build_input() -> ExistingPositionMonitoringInputV1:
    value = object.__new__(ExistingPositionMonitoringInputV1)

    object.__setattr__(
        value,
        "portfolio_id",
        "portfolio-1",
    )
    object.__setattr__(
        value,
        "result_snapshot_id",
        "portfolio-snapshot-2",
    )
    object.__setattr__(
        value,
        "portfolio_event_id",
        "portfolio-event-2",
    )
    object.__setattr__(
        value,
        "update_idempotency_key",
        "update-key-2",
    )
    object.__setattr__(
        value,
        "updated_at",
        NOW,
    )
    object.__setattr__(
        value,
        "portfolio_policy",
        object(),
    )
    object.__setattr__(
        value,
        "p7_snapshot",
        p7_snapshot(),
    )
    object.__setattr__(
        value,
        "evaluation_input",
        object(),
    )

    return value


def build_executor() -> ExistingPositionMonitoringExecutor:
    replay = object.__new__(
        PaperTradeReplayCoordinator
    )
    portfolio = object.__new__(
        PaperPortfolioLifecycleCoordinator
    )

    return ExistingPositionMonitoringExecutor(
        trade_replay_coordinator=replay,
        portfolio_lifecycle_coordinator=portfolio,
    )


def evaluation_result(
    *,
    status: str = "OPEN",
    decision: str = "HOLD",
    blockers: tuple[str, ...] = (),
    fills: tuple[object, ...] = (),
    remaining_quantity: int = 10,
) -> PaperTradePositionEvaluationResultV1:
    value = object.__new__(
        PaperTradePositionEvaluationResultV1
    )

    object.__setattr__(
        value,
        "status",
        status,
    )
    object.__setattr__(
        value,
        "position_decision",
        decision,
    )
    object.__setattr__(
        value,
        "blockers",
        blockers,
    )
    object.__setattr__(
        value,
        "decision_reasons",
        (),
    )
    object.__setattr__(
        value,
        "warnings",
        (),
    )
    object.__setattr__(
        value,
        "generated_exit_fills",
        fills,
    )
    object.__setattr__(
        value,
        "resulting_position",
        SimpleNamespace(
            remaining_quantity=remaining_quantity,
        ),
    )

    return value


def test_blocked_evaluation_does_not_update_p8():
    executor = build_executor()
    value = build_input()

    result_value = evaluation_result(
        status="BLOCKED",
        decision="BLOCK",
        blockers=("STALE_OBSERVATION",),
    )

    with (
        patch.object(
            executor.trade_replay_coordinator,
            "evaluate",
            return_value=(
                value.p7_snapshot,
                result_value,
            ),
        ),
        patch.object(
            executor.portfolio_lifecycle_coordinator,
            "apply_p7_snapshot",
        ) as apply_p8,
    ):
        result = executor.execute(value)

    assert result.status == "BLOCKED"
    assert result.blockers == (
        "STALE_OBSERVATION",
    )
    assert result.p7_snapshot is value.p7_snapshot
    assert result.p8_snapshot is None
    assert result.p7_state_changed is False
    assert result.p8_state_changed is False
    assert result.paper_action_occurred is False

    apply_p8.assert_not_called()


def test_duplicate_hold_is_no_change():
    executor = build_executor()
    value = build_input()
    result_value = evaluation_result()

    with (
        patch.object(
            executor.trade_replay_coordinator,
            "evaluate",
            return_value=(
                value.p7_snapshot,
                result_value,
            ),
        ),
        patch.object(
            executor.portfolio_lifecycle_coordinator,
            "apply_p7_snapshot",
        ) as apply_p8,
    ):
        result = executor.execute(value)

    assert result.status == "HOLD_NO_CHANGE"
    assert result.p7_snapshot is value.p7_snapshot
    assert result.p8_snapshot is None
    assert result.p7_state_changed is False
    assert result.p8_state_changed is False
    assert result.paper_action_occurred is False

    apply_p8.assert_not_called()


def test_mark_to_market_hold_updates_p7_then_p8():
    executor = build_executor()
    value = build_input()

    updated_p7 = p7_snapshot()
    updated_p8 = p8_snapshot()
    result_value = evaluation_result()

    with (
        patch.object(
            executor.trade_replay_coordinator,
            "evaluate",
            return_value=(
                updated_p7,
                result_value,
            ),
        ),
        patch.object(
            executor.portfolio_lifecycle_coordinator,
            "apply_p7_snapshot",
            return_value=updated_p8,
        ) as apply_p8,
    ):
        result = executor.execute(value)

    assert result.status == "HOLD_UPDATED"
    assert result.p7_snapshot is updated_p7
    assert result.p8_snapshot is updated_p8
    assert result.p7_state_changed is True
    assert result.p8_state_changed is True
    assert result.paper_action_occurred is False

    apply_p8.assert_called_once_with(
        portfolio_id=value.portfolio_id,
        policy=value.portfolio_policy,
        p7_snapshot=updated_p7,
        result_snapshot_id=value.result_snapshot_id,
        portfolio_event_id=value.portfolio_event_id,
        update_idempotency_key=(
            value.update_idempotency_key
        ),
        updated_at=value.updated_at,
    )


def test_partial_exit_updates_p7_then_p8_and_reports_action():
    executor = build_executor()
    value = build_input()

    updated_p7 = p7_snapshot()
    updated_p8 = p8_snapshot()

    result_value = evaluation_result(
        status="PARTIALLY_EXITED",
        decision="PARTIAL_EXIT",
        fills=(object(),),
        remaining_quantity=5,
    )

    with (
        patch.object(
            executor.trade_replay_coordinator,
            "evaluate",
            return_value=(
                updated_p7,
                result_value,
            ),
        ),
        patch.object(
            executor.portfolio_lifecycle_coordinator,
            "apply_p7_snapshot",
            return_value=updated_p8,
        ) as apply_p8,
    ):
        result = executor.execute(value)

    assert result.status == "PARTIAL_EXIT"
    assert result.p7_snapshot is updated_p7
    assert result.p8_snapshot is updated_p8
    assert result.p7_state_changed is True
    assert result.p8_state_changed is True
    assert result.paper_action_occurred is True

    apply_p8.assert_called_once()


def test_terminal_exit_updates_p7_then_p8_and_reports_closed():
    executor = build_executor()
    value = build_input()

    updated_p7 = p7_snapshot()
    updated_p8 = p8_snapshot()

    result_value = evaluation_result(
        status="CLOSED_STOP",
        decision="CLOSE_STOP",
        fills=(object(),),
        remaining_quantity=0,
    )

    with (
        patch.object(
            executor.trade_replay_coordinator,
            "evaluate",
            return_value=(
                updated_p7,
                result_value,
            ),
        ),
        patch.object(
            executor.portfolio_lifecycle_coordinator,
            "apply_p7_snapshot",
            return_value=updated_p8,
        ) as apply_p8,
    ):
        result = executor.execute(value)

    assert result.status == "CLOSED"
    assert result.p7_snapshot is updated_p7
    assert result.p8_snapshot is updated_p8
    assert result.p7_state_changed is True
    assert result.p8_state_changed is True
    assert result.paper_action_occurred is True

    apply_p8.assert_called_once()