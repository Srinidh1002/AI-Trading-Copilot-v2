from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

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
from services.paper_portfolio.paper_portfolio_lifecycle_coordinator import (
    PaperPortfolioLifecycleCoordinator,
)
from services.paper_trading.paper_trade_replay_coordinator import (
    PaperTradeReplayCoordinator,
)


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


@dataclass(frozen=True, slots=True)
class ExistingPositionMonitoringInputV1:
    portfolio_id: str
    result_snapshot_id: str
    portfolio_event_id: str
    update_idempotency_key: str
    updated_at: datetime
    portfolio_policy: PaperPortfolioPolicyV1
    p7_snapshot: PaperTradePersistenceSnapshotV1
    evaluation_input: PaperTradePositionEvaluationInputV1
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "existing_position_monitoring_input.v1"

    def __post_init__(self) -> None:
        for name in (
            "portfolio_id",
            "result_snapshot_id",
            "portfolio_event_id",
            "update_idempotency_key",
        ):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name),
            )

        object.__setattr__(
            self,
            "updated_at",
            _aware(self.updated_at, "updated_at"),
        )

        if type(self.portfolio_policy) is not PaperPortfolioPolicyV1:
            raise TypeError(
                "portfolio_policy must be exact PaperPortfolioPolicyV1"
            )
        if type(self.p7_snapshot) is not PaperTradePersistenceSnapshotV1:
            raise TypeError(
                "p7_snapshot must be exact "
                "PaperTradePersistenceSnapshotV1"
            )
        if (
            type(self.evaluation_input)
            is not PaperTradePositionEvaluationInputV1
        ):
            raise TypeError(
                "evaluation_input must be exact "
                "PaperTradePositionEvaluationInputV1"
            )
        if self.p7_snapshot.position is None:
            raise ValueError("p7_snapshot must contain a position")
        if (
            self.evaluation_input.position.position_id
            != self.p7_snapshot.position.position_id
        ):
            raise ValueError("P7 position identity mismatch")
        if self.updated_at != self.evaluation_input.evaluation_timestamp:
            raise ValueError(
                "updated_at must equal evaluation timestamp"
            )
        if self.execution_mode != "PAPER":
            raise ValueError("execution_mode must be PAPER")
        if self.live_execution_eligible:
            raise ValueError("live execution is not eligible")
        if self.schema_version != "existing_position_monitoring_input.v1":
            raise ValueError("unsupported schema_version")


@dataclass(frozen=True, slots=True)
class ExistingPositionMonitoringResultV1:
    status: str
    evaluation_result: PaperTradePositionEvaluationResultV1
    p7_snapshot: PaperTradePersistenceSnapshotV1
    p8_snapshot: PaperPortfolioPersistenceSnapshotV1 | None
    p7_state_changed: bool
    p8_state_changed: bool
    paper_action_occurred: bool
    blockers: tuple[str, ...] = ()
    decision_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "existing_position_monitoring_result.v1"

    def __post_init__(self) -> None:
        allowed = {
            "BLOCKED",
            "HOLD_NO_CHANGE",
            "HOLD_UPDATED",
            "PARTIAL_EXIT",
            "CLOSED",
        }
        if self.status not in allowed:
            raise ValueError("unsupported monitoring result status")
        if (
            type(self.evaluation_result)
            is not PaperTradePositionEvaluationResultV1
        ):
            raise TypeError("evaluation_result")
        if type(self.p7_snapshot) is not PaperTradePersistenceSnapshotV1:
            raise TypeError("p7_snapshot")
        if self.p8_snapshot is not None and type(
            self.p8_snapshot
        ) is not PaperPortfolioPersistenceSnapshotV1:
            raise TypeError("p8_snapshot")
        for name in (
            "p7_state_changed",
            "p8_state_changed",
            "paper_action_occurred",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(name)

        if self.status == "BLOCKED":
            if (
                self.p7_state_changed
                or self.p8_state_changed
                or self.paper_action_occurred
            ):
                raise ValueError("BLOCKED result cannot mutate state")
        if self.status == "HOLD_NO_CHANGE":
            if (
                self.p7_state_changed
                or self.p8_state_changed
                or self.paper_action_occurred
            ):
                raise ValueError("HOLD_NO_CHANGE cannot mutate state")
        if self.status in {"PARTIAL_EXIT", "CLOSED"}:
            if (
                not self.p7_state_changed
                or not self.p8_state_changed
                or not self.paper_action_occurred
                or self.p8_snapshot is None
            ):
                raise ValueError(
                    "exit result requires persisted P7/P8 changes"
                )
        if self.status == "HOLD_UPDATED":
            if (
                not self.p7_state_changed
                or not self.p8_state_changed
                or self.paper_action_occurred
                or self.p8_snapshot is None
            ):
                raise ValueError(
                    "HOLD_UPDATED requires non-economic P7/P8 update"
                )
        if self.execution_mode != "PAPER":
            raise ValueError("execution_mode must be PAPER")
        if self.live_execution_eligible:
            raise ValueError("live execution is not eligible")
        if self.schema_version != "existing_position_monitoring_result.v1":
            raise ValueError("unsupported schema_version")


class ExistingPositionMonitoringExecutor:
    """Certified P7 evaluation/persistence followed by P8 projection."""

    def __init__(
        self,
        *,
        trade_replay_coordinator: PaperTradeReplayCoordinator,
        portfolio_lifecycle_coordinator: PaperPortfolioLifecycleCoordinator,
    ) -> None:
        if type(trade_replay_coordinator) is not PaperTradeReplayCoordinator:
            raise TypeError("trade_replay_coordinator")
        if (
            type(portfolio_lifecycle_coordinator)
            is not PaperPortfolioLifecycleCoordinator
        ):
            raise TypeError("portfolio_lifecycle_coordinator")

        self.trade_replay_coordinator = trade_replay_coordinator
        self.portfolio_lifecycle_coordinator = (
            portfolio_lifecycle_coordinator
        )

    def execute(
        self,
        value: ExistingPositionMonitoringInputV1,
    ) -> ExistingPositionMonitoringResultV1:
        if type(value) is not ExistingPositionMonitoringInputV1:
            raise TypeError(
                "value must be exact ExistingPositionMonitoringInputV1"
            )

        updated_p7, evaluation = self.trade_replay_coordinator.evaluate(
            value.p7_snapshot,
            value.evaluation_input,
        )

        if (
            evaluation.status == "BLOCKED"
            or evaluation.position_decision == "BLOCK"
        ):
            return ExistingPositionMonitoringResultV1(
                status="BLOCKED",
                evaluation_result=evaluation,
                p7_snapshot=value.p7_snapshot,
                p8_snapshot=None,
                p7_state_changed=False,
                p8_state_changed=False,
                paper_action_occurred=False,
                blockers=evaluation.blockers,
                decision_reasons=evaluation.decision_reasons,
                warnings=evaluation.warnings,
            )

        p7_changed = updated_p7 is not value.p7_snapshot

        if not p7_changed:
            return ExistingPositionMonitoringResultV1(
                status="HOLD_NO_CHANGE",
                evaluation_result=evaluation,
                p7_snapshot=value.p7_snapshot,
                p8_snapshot=None,
                p7_state_changed=False,
                p8_state_changed=False,
                paper_action_occurred=False,
                decision_reasons=evaluation.decision_reasons,
                warnings=evaluation.warnings,
            )

        updated_p8 = self.portfolio_lifecycle_coordinator.apply_p7_snapshot(
            portfolio_id=value.portfolio_id,
            policy=value.portfolio_policy,
            p7_snapshot=updated_p7,
            result_snapshot_id=value.result_snapshot_id,
            portfolio_event_id=value.portfolio_event_id,
            update_idempotency_key=value.update_idempotency_key,
            updated_at=value.updated_at,
        )

        generated_fills = tuple(evaluation.generated_exit_fills)
        action_occurred = bool(generated_fills)
        resulting_position = evaluation.resulting_position

        if action_occurred:
            if (
                resulting_position is not None
                and resulting_position.remaining_quantity == 0
            ):
                status = "CLOSED"
            else:
                status = "PARTIAL_EXIT"
        else:
            status = "HOLD_UPDATED"

        return ExistingPositionMonitoringResultV1(
            status=status,
            evaluation_result=evaluation,
            p7_snapshot=updated_p7,
            p8_snapshot=updated_p8,
            p7_state_changed=True,
            p8_state_changed=True,
            paper_action_occurred=action_occurred,
            blockers=evaluation.blockers,
            decision_reasons=evaluation.decision_reasons,
            warnings=evaluation.warnings,
        )
