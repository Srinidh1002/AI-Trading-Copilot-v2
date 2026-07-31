from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from services.contracts.integrated_three_target_trade_plan_result_v1 import (
    IntegratedThreeTargetTradePlanResultV1,
)
from services.contracts.paper_market_observation_v1 import (
    PaperMarketObservationV1,
)
from services.contracts.paper_portfolio_admission_input_v1 import (
    PaperPortfolioAdmissionInputV1,
)
from services.contracts.paper_portfolio_admission_result_v1 import (
    PaperPortfolioAdmissionResultV1,
)
from services.contracts.paper_portfolio_persistence_snapshot_v1 import (
    PaperPortfolioPersistenceSnapshotV1,
)
from services.contracts.paper_portfolio_policy_v1 import (
    PaperPortfolioPolicyV1,
)
from services.contracts.paper_trade_entry_evaluation_input_v1 import (
    PaperTradeEntryEvaluationInputV1,
)
from services.contracts.paper_trade_entry_evaluation_result_v1 import (
    PaperTradeEntryEvaluationResultV1,
)
from services.contracts.paper_trade_lifecycle_policy_v1 import (
    PaperTradeLifecyclePolicyV1,
)
from services.contracts.paper_trade_persistence_snapshot_v1 import (
    PaperTradePersistenceSnapshotV1,
)
from services.paper_orchestration.paper_state_factories import (
    build_entry_paper_trade_persistence_snapshot,
    build_initial_paper_portfolio_snapshot,
    build_initial_paper_trade_lifecycle_state,
)
from services.paper_portfolio.paper_portfolio_admission_evaluator import (
    evaluate_paper_portfolio_admission,
)
from services.paper_portfolio.paper_portfolio_lifecycle_coordinator import (
    PaperPortfolioLifecycleCoordinator,
)
from services.paper_portfolio.paper_portfolio_persistence_service import (
    PaperPortfolioPersistenceService,
)
from services.paper_trading.paper_trade_entry_evaluator import (
    evaluate_paper_trade_entry,
)
from services.paper_trading.paper_trade_persistence_service import (
    PaperTradePersistenceService,
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
class NewEntryPaperLifecycleInputV1:
    portfolio_id: str
    initial_portfolio_snapshot_id: str
    admission_result_id: str
    admission_request_id: str
    admission_idempotency_key: str
    admission_portfolio_event_id: str
    requested_reservation_id: str
    paper_trade_id: str
    paper_trade_adapter_idempotency_key: str
    initial_lifecycle_state_id: str
    resulting_lifecycle_state_id: str
    requested_transition_id: str
    position_id: str
    entry_fill_id: str
    activation_result_snapshot_id: str
    activation_portfolio_event_id: str
    activation_update_idempotency_key: str
    trading_day_id: str
    starting_capital: float
    evaluated_at: datetime
    integrated_trade_plan_result: IntegratedThreeTargetTradePlanResultV1
    portfolio_policy: PaperPortfolioPolicyV1
    lifecycle_policy: PaperTradeLifecyclePolicyV1
    observation: PaperMarketObservationV1
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    schema_version: str = "new_entry_paper_lifecycle_input.v1"

    def __post_init__(self) -> None:
        for name in (
            "portfolio_id",
            "initial_portfolio_snapshot_id",
            "admission_result_id",
            "admission_request_id",
            "admission_idempotency_key",
            "admission_portfolio_event_id",
            "requested_reservation_id",
            "paper_trade_id",
            "paper_trade_adapter_idempotency_key",
            "initial_lifecycle_state_id",
            "resulting_lifecycle_state_id",
            "requested_transition_id",
            "position_id",
            "entry_fill_id",
            "activation_result_snapshot_id",
            "activation_portfolio_event_id",
            "activation_update_idempotency_key",
            "trading_day_id",
        ):
            object.__setattr__(
                self,
                name,
                _text(getattr(self, name), name),
            )

        if type(self.integrated_trade_plan_result) is not IntegratedThreeTargetTradePlanResultV1:
            raise TypeError(
                "integrated_trade_plan_result must be exact "
                "IntegratedThreeTargetTradePlanResultV1"
            )
        if type(self.portfolio_policy) is not PaperPortfolioPolicyV1:
            raise TypeError(
                "portfolio_policy must be exact PaperPortfolioPolicyV1"
            )
        if type(self.lifecycle_policy) is not PaperTradeLifecyclePolicyV1:
            raise TypeError(
                "lifecycle_policy must be exact PaperTradeLifecyclePolicyV1"
            )
        if type(self.observation) is not PaperMarketObservationV1:
            raise TypeError(
                "observation must be exact PaperMarketObservationV1"
            )
        if self.integrated_trade_plan_result.status != "READY":
            raise ValueError("integrated trade plan must be READY")
        if self.integrated_trade_plan_result.execution_mode != "PAPER":
            raise ValueError("integrated trade plan must be PAPER-only")
        if self.integrated_trade_plan_result.live_execution_eligible is not False:
            raise ValueError("integrated trade plan cannot be live eligible")

        object.__setattr__(
            self,
            "evaluated_at",
            _aware(self.evaluated_at, "evaluated_at"),
        )
        if (
            type(self.starting_capital) not in (int, float)
            or isinstance(self.starting_capital, bool)
            or self.starting_capital <= 0
        ):
            raise ValueError("starting_capital must be positive")
        object.__setattr__(
            self,
            "starting_capital",
            float(self.starting_capital),
        )

        if self.execution_mode != "PAPER":
            raise ValueError("execution_mode must be PAPER")
        if self.live_execution_eligible:
            raise ValueError("live execution is not eligible")
        if self.schema_version != "new_entry_paper_lifecycle_input.v1":
            raise ValueError("unsupported schema_version")


@dataclass(frozen=True, slots=True)
class NewEntryPaperLifecycleResultV1:
    status: str
    admission_result: PaperPortfolioAdmissionResultV1
    entry_result: PaperTradeEntryEvaluationResultV1 | None
    p7_snapshot: PaperTradePersistenceSnapshotV1 | None
    p8_snapshot: PaperPortfolioPersistenceSnapshotV1 | None
    paper_action_occurred: bool
    blockers: tuple[str, ...] = ()
    decision_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        allowed = {
            "ADMISSION_BLOCKED",
            "NO_CAPACITY",
            "ENTRY_BLOCKED",
            "WAITING_FOR_ENTRY",
            "ENTRY_CLOSED",
            "OPEN",
        }
        if self.status not in allowed:
            raise ValueError("unsupported lifecycle result status")
        if type(self.admission_result) is not PaperPortfolioAdmissionResultV1:
            raise TypeError("admission_result")
        if self.entry_result is not None and type(
            self.entry_result
        ) is not PaperTradeEntryEvaluationResultV1:
            raise TypeError("entry_result")
        if self.p7_snapshot is not None and type(
            self.p7_snapshot
        ) is not PaperTradePersistenceSnapshotV1:
            raise TypeError("p7_snapshot")
        if self.p8_snapshot is not None and type(
            self.p8_snapshot
        ) is not PaperPortfolioPersistenceSnapshotV1:
            raise TypeError("p8_snapshot")
        if type(self.paper_action_occurred) is not bool:
            raise TypeError("paper_action_occurred")
        if self.status == "OPEN":
            if (
                self.entry_result is None
                or self.p7_snapshot is None
                or self.p8_snapshot is None
                or not self.paper_action_occurred
            ):
                raise ValueError("OPEN requires persisted P7/P8 state")
        elif self.paper_action_occurred:
            raise ValueError(
                "non-OPEN result cannot report a paper action"
            )
        if self.execution_mode != "PAPER":
            raise ValueError("execution_mode must be PAPER")
        if self.live_execution_eligible:
            raise ValueError("live execution is not eligible")


class NewEntryPaperLifecycleExecutor:
    """Certified P6→P8 admission→P7 entry→P8 activation sequence."""

    def __init__(
        self,
        *,
        portfolio_persistence_service: PaperPortfolioPersistenceService,
        trade_persistence_service: PaperTradePersistenceService,
        broker_order_submission: bool = False,
    ) -> None:
        if type(portfolio_persistence_service) is not PaperPortfolioPersistenceService:
            raise TypeError("portfolio_persistence_service")
        if type(trade_persistence_service) is not PaperTradePersistenceService:
            raise TypeError("trade_persistence_service")
        if broker_order_submission is not False:
            raise ValueError("broker order submission must remain disabled")

        self.portfolio_persistence_service = (
            portfolio_persistence_service
        )
        self.trade_persistence_service = trade_persistence_service
        self.broker_order_submission = broker_order_submission
        self.portfolio_lifecycle_coordinator = (
            PaperPortfolioLifecycleCoordinator(
                portfolio_persistence_service
            )
        )

    def _get_or_create_portfolio(
        self,
        value: NewEntryPaperLifecycleInputV1,
    ) -> PaperPortfolioPersistenceSnapshotV1:
        existing = self.portfolio_persistence_service.get(
            value.portfolio_id
        )
        if existing is not None:
            if (
                existing.portfolio_snapshot.trading_day_id
                != value.trading_day_id
            ):
                raise ValueError("portfolio trading day mismatch")
            if (
                existing.portfolio_snapshot.portfolio_policy_id
                != value.portfolio_policy.portfolio_policy_id
            ):
                raise ValueError("portfolio policy mismatch")
            return existing

        snapshot = build_initial_paper_portfolio_snapshot(
            portfolio_snapshot_id=(
                value.initial_portfolio_snapshot_id
            ),
            portfolio_id=value.portfolio_id,
            policy=value.portfolio_policy,
            trading_day_id=value.trading_day_id,
            starting_capital=value.starting_capital,
            created_at=value.evaluated_at,
        )
        envelope = PaperPortfolioPersistenceSnapshotV1(
            portfolio_id=value.portfolio_id,
            portfolio_snapshot=snapshot,
            admission_idempotency_records={},
            update_idempotency_records={},
            processed_portfolio_event_hashes={},
            processed_p7_transition_hashes={},
            processed_p7_fill_hashes={},
            created_at=value.evaluated_at,
            updated_at=value.evaluated_at,
            event_sequence=0,
        )
        return self.portfolio_persistence_service.save(envelope)

    def execute(
        self,
        value: NewEntryPaperLifecycleInputV1,
    ) -> NewEntryPaperLifecycleResultV1:
        if type(value) is not NewEntryPaperLifecycleInputV1:
            raise TypeError(
                "value must be exact NewEntryPaperLifecycleInputV1"
            )

        current_portfolio = self._get_or_create_portfolio(value)
        admission_input = PaperPortfolioAdmissionInputV1(
            admission_request_id=value.admission_request_id,
            admission_idempotency_key=value.admission_idempotency_key,
            portfolio_event_id=value.admission_portfolio_event_id,
            portfolio_id=value.portfolio_id,
            requested_reservation_id=value.requested_reservation_id,
            evaluated_at=value.evaluated_at,
            trading_day_id=value.trading_day_id,
            integrated_trade_plan_result=(
                value.integrated_trade_plan_result
            ),
            current_portfolio_snapshot=(
                current_portfolio.portfolio_snapshot
            ),
            portfolio_policy=value.portfolio_policy,
        )
        admission_result = evaluate_paper_portfolio_admission(
            admission_result_id=value.admission_result_id,
            input_value=admission_input,
            resulting_snapshot_id=(
                f"{value.admission_result_id}:snapshot"
            ),
        )

        if admission_result.status == "BLOCKED":
            return NewEntryPaperLifecycleResultV1(
                status="ADMISSION_BLOCKED",
                admission_result=admission_result,
                entry_result=None,
                p7_snapshot=None,
                p8_snapshot=current_portfolio,
                paper_action_occurred=False,
                blockers=admission_result.blockers,
                warnings=admission_result.warnings,
            )
        if admission_result.status == "NO_CAPACITY":
            return NewEntryPaperLifecycleResultV1(
                status="NO_CAPACITY",
                admission_result=admission_result,
                entry_result=None,
                p7_snapshot=None,
                p8_snapshot=current_portfolio,
                paper_action_occurred=False,
                decision_reasons=(
                    admission_result.decision_reasons
                ),
                warnings=admission_result.warnings,
            )

        admitted_portfolio = (
            self.portfolio_lifecycle_coordinator
            .persist_approved_admission(admission_result)
        )

        plan = value.integrated_trade_plan_result
        initial_state = build_initial_paper_trade_lifecycle_state(
            lifecycle_state_id=value.initial_lifecycle_state_id,
            trade_plan_id=plan.capital_quantity_result.trade_plan_id,
            integrated_trade_plan_result_id=plan.integration_id,
            lifecycle_policy=value.lifecycle_policy,
            created_at=value.evaluated_at,
        )
        entry_input = PaperTradeEntryEvaluationInputV1(
            integrated_trade_plan_result=plan,
            lifecycle_policy=value.lifecycle_policy,
            lifecycle_state=initial_state,
            observation=value.observation,
            evaluation_timestamp=value.evaluated_at,
            requested_transition_id=value.requested_transition_id,
            position_id=value.position_id,
            entry_fill_id=value.entry_fill_id,
        )
        entry_result = evaluate_paper_trade_entry(entry_input)

        if entry_result.status == "BLOCKED":
            return NewEntryPaperLifecycleResultV1(
                status="ENTRY_BLOCKED",
                admission_result=admission_result,
                entry_result=entry_result,
                p7_snapshot=None,
                p8_snapshot=admitted_portfolio,
                paper_action_occurred=False,
                blockers=entry_result.blockers,
                warnings=entry_result.warnings,
            )

        if entry_result.status == "WAITING_FOR_ENTRY":
            return NewEntryPaperLifecycleResultV1(
                status="WAITING_FOR_ENTRY",
                admission_result=admission_result,
                entry_result=entry_result,
                p7_snapshot=None,
                p8_snapshot=admitted_portfolio,
                paper_action_occurred=False,
                decision_reasons=entry_result.decision_reasons,
                warnings=entry_result.warnings,
            )

        if entry_result.status != "OPEN":
            return NewEntryPaperLifecycleResultV1(
                status="ENTRY_CLOSED",
                admission_result=admission_result,
                entry_result=entry_result,
                p7_snapshot=None,
                p8_snapshot=admitted_portfolio,
                paper_action_occurred=False,
                decision_reasons=entry_result.decision_reasons,
                warnings=entry_result.warnings,
            )

        p7_snapshot = build_entry_paper_trade_persistence_snapshot(
            paper_trade_id=value.paper_trade_id,
            adapter_idempotency_key=(
                value.paper_trade_adapter_idempotency_key
            ),
            entry_input=entry_input,
            entry_result=entry_result,
            resulting_lifecycle_state_id=(
                value.resulting_lifecycle_state_id
            ),
            persisted_at=value.evaluated_at,
        )
        self.trade_persistence_service.save(p7_snapshot)

        activated_portfolio = (
            self.portfolio_lifecycle_coordinator.apply_p7_snapshot(
                portfolio_id=value.portfolio_id,
                policy=value.portfolio_policy,
                p7_snapshot=p7_snapshot,
                result_snapshot_id=(
                    value.activation_result_snapshot_id
                ),
                portfolio_event_id=(
                    value.activation_portfolio_event_id
                ),
                update_idempotency_key=(
                    value.activation_update_idempotency_key
                ),
                updated_at=value.evaluated_at,
            )
        )

        return NewEntryPaperLifecycleResultV1(
            status="OPEN",
            admission_result=admission_result,
            entry_result=entry_result,
            p7_snapshot=p7_snapshot,
            p8_snapshot=activated_portfolio,
            paper_action_occurred=True,
            decision_reasons=entry_result.decision_reasons,
            warnings=entry_result.warnings,
        )
