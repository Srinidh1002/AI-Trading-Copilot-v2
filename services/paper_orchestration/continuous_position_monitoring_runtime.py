"""R4.3 continuous PAPER position monitoring runtime."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from services.contracts.paper_market_observation_v1 import (
    PaperMarketObservationV1,
)
from services.contracts.paper_portfolio_persistence_snapshot_v1 import (
    PaperPortfolioPersistenceSnapshotV1,
)
from services.contracts.paper_portfolio_policy_v1 import (
    PaperPortfolioPolicyV1,
)
from services.contracts.paper_trade_persistence_snapshot_v1 import (
    PaperTradePersistenceSnapshotV1,
)
from services.contracts.paper_trade_position_evaluation_input_v1 import (
    PaperTradePositionEvaluationInputV1,
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
from services.paper_portfolio.paper_portfolio_persistence_service import (
    PaperPortfolioPersistenceService,
)
from services.paper_trading.paper_trade_persistence_service import (
    PaperTradePersistenceService,
)
from services.paper_trading.paper_trade_replay_coordinator import (
    PaperTradeReplayCoordinator,
)


_ALLOWED_STATUSES = frozenset(
    {
        "BLOCKED",
        "HOLD_NO_CHANGE",
        "HOLD_UPDATED",
        "PARTIAL_EXIT",
        "CLOSED",
    }
)


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be a nonblank string")
    return value.strip()


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


@dataclass(frozen=True, slots=True)
class ContinuousPositionMonitoringResultV1:
    status: str
    evaluation_result: PaperTradePositionEvaluationResultV1
    p7_snapshot: PaperTradePersistenceSnapshotV1
    p8_snapshot: PaperPortfolioPersistenceSnapshotV1 | None
    p7_state_changed: bool
    p8_state_changed: bool
    paper_action_occurred: bool
    idempotent_replay: bool = False
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False

    def __post_init__(self) -> None:
        if self.status not in _ALLOWED_STATUSES:
            raise ValueError("unsupported R4.3 monitoring status")

        if (
            type(self.evaluation_result)
            is not PaperTradePositionEvaluationResultV1
        ):
            raise TypeError(
                "evaluation_result must be exact "
                "PaperTradePositionEvaluationResultV1"
            )

        if type(self.p7_snapshot) is not PaperTradePersistenceSnapshotV1:
            raise TypeError(
                "p7_snapshot must be exact "
                "PaperTradePersistenceSnapshotV1"
            )

        if (
            self.p8_snapshot is not None
            and type(self.p8_snapshot)
            is not PaperPortfolioPersistenceSnapshotV1
        ):
            raise TypeError(
                "p8_snapshot must be exact "
                "PaperPortfolioPersistenceSnapshotV1"
            )

        for name in (
            "p7_state_changed",
            "p8_state_changed",
            "paper_action_occurred",
            "idempotent_replay",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be bool")

        if self.status in {"BLOCKED", "HOLD_NO_CHANGE"}:
            if (
                self.p7_state_changed
                or self.p8_state_changed
                or self.paper_action_occurred
            ):
                raise ValueError(
                    "blocked/no-change monitoring cannot mutate state"
                )

        if self.status == "HOLD_UPDATED":
            if (
                not self.p7_state_changed
                or not self.p8_state_changed
                or self.paper_action_occurred
                or self.p8_snapshot is None
            ):
                raise ValueError(
                    "HOLD_UPDATED requires persisted non-economic state"
                )

        if self.status in {"PARTIAL_EXIT", "CLOSED"}:
            if (
                not self.p7_state_changed
                or not self.p8_state_changed
                or not self.paper_action_occurred
                or self.p8_snapshot is None
            ):
                raise ValueError(
                    "exit monitoring requires persisted P7/P8 state"
                )

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
        ):
            raise ValueError("R4.3 must remain PAPER-only")


def _validate_persisted_state(
    *,
    portfolio_id: str,
    paper_trade_id: str,
    portfolio_policy: PaperPortfolioPolicyV1,
    trade_snapshot: PaperTradePersistenceSnapshotV1,
    portfolio_snapshot: PaperPortfolioPersistenceSnapshotV1,
) -> None:
    if trade_snapshot.position is None:
        raise ValueError("persisted P7 position missing")

    if trade_snapshot.lifecycle_state.is_terminal:
        raise ValueError("terminal P7 snapshot cannot be monitored")

    if trade_snapshot.lifecycle_state.current_state not in {
        "OPEN",
        "PARTIALLY_EXITED",
    }:
        raise ValueError("persisted P7 state is not monitorable")

    if trade_snapshot.paper_trade_id != paper_trade_id:
        raise ValueError("paper trade identity mismatch")

    if portfolio_snapshot.portfolio_id != portfolio_id:
        raise ValueError("portfolio identity mismatch")

    if (
        portfolio_snapshot.portfolio_snapshot.portfolio_policy_id
        != portfolio_policy.portfolio_policy_id
    ):
        raise ValueError("portfolio policy mismatch")

    position = trade_snapshot.position

    references = tuple(
        item
        for item in portfolio_snapshot.portfolio_snapshot.position_references
        if item.position_id == position.position_id
    )

    if len(references) != 1:
        raise ValueError("persisted portfolio position reference missing")

    reservations = tuple(
        item
        for item in portfolio_snapshot.portfolio_snapshot.reservations
        if item.position_id == position.position_id
    )

    if len(reservations) != 1:
        raise ValueError("persisted active reservation missing")

    reservation = reservations[0]

    if reservation.reservation_status != "ACTIVE":
        raise ValueError("monitoring requires ACTIVE reservation")

    if (
        reservation.trade_plan_id != position.trade_plan_id
        or reservation.integrated_trade_plan_result_id
        != position.integrated_trade_plan_result_id
    ):
        raise ValueError("reservation/position lineage mismatch")


def _validate_observation(
    *,
    snapshot: PaperTradePersistenceSnapshotV1,
    observation: PaperMarketObservationV1,
) -> None:
    position = snapshot.position
    if position is None:
        raise ValueError("persisted P7 position missing")

    actual = (
        observation.trade_plan_id,
        observation.integrated_trade_plan_result_id,
        observation.selected_option_contract_id,
        observation.underlying_symbol,
        observation.option_symbol,
    )
    expected = (
        position.trade_plan_id,
        position.integrated_trade_plan_result_id,
        position.selected_option_contract_id,
        position.underlying_symbol,
        position.option_symbol,
    )

    if actual != expected:
        raise ValueError("observation/position identity mismatch")


def execute_continuous_position_monitoring(
    *,
    portfolio_id: str,
    paper_trade_id: str,
    portfolio_policy: PaperPortfolioPolicyV1,
    observation: PaperMarketObservationV1,
    evaluation_timestamp: datetime,
    requested_transition_id: str,
    resulting_lifecycle_state_id: str,
    evaluation_result_id: str,
    exit_fill_ids: tuple[str, ...],
    pnl_evidence_id: str,
    result_snapshot_id: str,
    portfolio_event_id: str,
    update_idempotency_key: str,
    portfolio_persistence_service: PaperPortfolioPersistenceService,
    trade_persistence_service: PaperTradePersistenceService,
    target_1_exit_cost: float = 0.0,
    target_2_exit_cost: float = 0.0,
    target_3_exit_cost: float = 0.0,
    stop_exit_cost: float = 0.0,
    session_exit_cost: float = 0.0,
    expiry_exit_cost: float = 0.0,
    invalidation_exit_cost: float = 0.0,
    runner_exit_cost: float = 0.0,
    cancellation_exit_cost: float = 0.0,
    invalidation_status: str = "ABSENT",
    invalidation_reason_code: str | None = None,
    cancellation_status: str = "ABSENT",
    cancellation_reason_code: str | None = None,
    broker_order_submission: bool = False,
) -> ContinuousPositionMonitoringResultV1:
    """Evaluate one observation and persist exact P7/P8 monitoring state."""

    if type(portfolio_policy) is not PaperPortfolioPolicyV1:
        raise TypeError(
            "portfolio_policy must be exact PaperPortfolioPolicyV1"
        )

    if type(observation) is not PaperMarketObservationV1:
        raise TypeError(
            "observation must be exact PaperMarketObservationV1"
        )

    if (
        type(portfolio_persistence_service)
        is not PaperPortfolioPersistenceService
    ):
        raise TypeError(
            "portfolio_persistence_service must be exact "
            "PaperPortfolioPersistenceService"
        )

    if (
        type(trade_persistence_service)
        is not PaperTradePersistenceService
    ):
        raise TypeError(
            "trade_persistence_service must be exact "
            "PaperTradePersistenceService"
        )

    portfolio_id = _text(portfolio_id, "portfolio_id")
    paper_trade_id = _text(paper_trade_id, "paper_trade_id")
    requested_transition_id = _text(
        requested_transition_id,
        "requested_transition_id",
    )
    resulting_lifecycle_state_id = _text(
        resulting_lifecycle_state_id,
        "resulting_lifecycle_state_id",
    )
    evaluation_result_id = _text(
        evaluation_result_id,
        "evaluation_result_id",
    )
    pnl_evidence_id = _text(pnl_evidence_id, "pnl_evidence_id")
    result_snapshot_id = _text(
        result_snapshot_id,
        "result_snapshot_id",
    )
    portfolio_event_id = _text(
        portfolio_event_id,
        "portfolio_event_id",
    )
    update_idempotency_key = _text(
        update_idempotency_key,
        "update_idempotency_key",
    )
    evaluation_timestamp = _aware(
        evaluation_timestamp,
        "evaluation_timestamp",
    )

    if broker_order_submission is not False:
        raise ValueError("order submission must remain disabled")

    persisted_p7 = trade_persistence_service.get(paper_trade_id)
    if persisted_p7 is None:
        raise ValueError("persisted R4.2 trade not found")

    persisted_p8 = portfolio_persistence_service.get(portfolio_id)
    if persisted_p8 is None:
        raise ValueError("persisted R4.2 portfolio not found")

    _validate_persisted_state(
        portfolio_id=portfolio_id,
        paper_trade_id=paper_trade_id,
        portfolio_policy=portfolio_policy,
        trade_snapshot=persisted_p7,
        portfolio_snapshot=persisted_p8,
    )

    _validate_observation(
        snapshot=persisted_p7,
        observation=observation,
    )

    position = persisted_p7.position
    assert position is not None

    evaluation_input = PaperTradePositionEvaluationInputV1(
        position=position,
        lifecycle_policy=persisted_p7.lifecycle_policy,
        lifecycle_state=persisted_p7.lifecycle_state,
        observation=observation,
        evaluation_timestamp=evaluation_timestamp,
        requested_transition_id=requested_transition_id,
        resulting_lifecycle_state_id=resulting_lifecycle_state_id,
        evaluation_result_id=evaluation_result_id,
        exit_fill_ids=exit_fill_ids,
        pnl_evidence_id=pnl_evidence_id,
        target_1_exit_cost=target_1_exit_cost,
        target_2_exit_cost=target_2_exit_cost,
        target_3_exit_cost=target_3_exit_cost,
        stop_exit_cost=stop_exit_cost,
        session_exit_cost=session_exit_cost,
        expiry_exit_cost=expiry_exit_cost,
        invalidation_exit_cost=invalidation_exit_cost,
        runner_exit_cost=runner_exit_cost,
        cancellation_exit_cost=cancellation_exit_cost,
        invalidation_status=invalidation_status,
        invalidation_reason_code=invalidation_reason_code,
        cancellation_status=cancellation_status,
        cancellation_reason_code=cancellation_reason_code,
        metadata={"scope": "R4.3_CONTINUOUS_MONITORING"},
    )

    monitoring_input = ExistingPositionMonitoringInputV1(
        portfolio_id=portfolio_id,
        result_snapshot_id=result_snapshot_id,
        portfolio_event_id=portfolio_event_id,
        update_idempotency_key=update_idempotency_key,
        updated_at=evaluation_timestamp,
        portfolio_policy=portfolio_policy,
        p7_snapshot=persisted_p7,
        evaluation_input=evaluation_input,
    )

    authority = ExistingPositionMonitoringExecutor(
        trade_replay_coordinator=PaperTradeReplayCoordinator(
            trade_persistence_service
        ),
        portfolio_lifecycle_coordinator=(
            PaperPortfolioLifecycleCoordinator(
                portfolio_persistence_service
            )
        ),
    )

    before_p7_hash = persisted_p7.integrity_hash
    before_p8_hash = persisted_p8.integrity_hash

    result = authority.execute(monitoring_input)

    current_p7 = trade_persistence_service.get(paper_trade_id)
    if current_p7 is None:
        raise ValueError("persisted P7 state disappeared")

    current_p8 = portfolio_persistence_service.get(portfolio_id)
    if current_p8 is None:
        raise ValueError("persisted P8 state disappeared")

    idempotent_replay = (
        result.status != "BLOCKED"
        and current_p7.integrity_hash == before_p7_hash
        and current_p8.integrity_hash == before_p8_hash
    )

    return ContinuousPositionMonitoringResultV1(
        status=result.status,
        evaluation_result=result.evaluation_result,
        p7_snapshot=result.p7_snapshot,
        p8_snapshot=result.p8_snapshot,
        p7_state_changed=result.p7_state_changed,
        p8_state_changed=result.p8_state_changed,
        paper_action_occurred=result.paper_action_occurred,
        idempotent_replay=idempotent_replay,
    )