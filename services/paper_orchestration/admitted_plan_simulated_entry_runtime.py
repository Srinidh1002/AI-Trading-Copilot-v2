"""R4.2 persisted P8 admission to simulated P7 entry runtime."""

from __future__ import annotations

from dataclasses import dataclass

from services.contracts.integrated_three_target_trade_plan_result_v1 import (
    IntegratedThreeTargetTradePlanResultV1,
)
from services.contracts.paper_capital_reservation_v1 import (
    PaperCapitalReservationV1,
)
from services.contracts.paper_market_observation_v1 import (
    PaperMarketObservationV1,
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
    build_initial_paper_trade_lifecycle_state,
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


_ALLOWED_STATUSES = frozenset(
    {
        "OPEN",
        "WAITING_FOR_ENTRY",
        "BLOCKED",
        "ENTRY_CLOSED",
    }
)


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be a nonblank string")
    return value.strip()


@dataclass(frozen=True, slots=True)
class AdmittedPlanSimulatedEntryResultV1:
    """R4.2 entry result with exact durable P7/P8 state."""

    status: str
    entry_result: PaperTradeEntryEvaluationResultV1
    p7_snapshot: PaperTradePersistenceSnapshotV1 | None
    p8_snapshot: PaperPortfolioPersistenceSnapshotV1
    paper_action_occurred: bool
    idempotent_replay: bool = False
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False

    def __post_init__(self) -> None:
        if self.status not in _ALLOWED_STATUSES:
            raise ValueError("unsupported R4.2 entry status")

        if (
            type(self.entry_result)
            is not PaperTradeEntryEvaluationResultV1
        ):
            raise TypeError(
                "entry_result must be exact "
                "PaperTradeEntryEvaluationResultV1"
            )

        if (
            self.p7_snapshot is not None
            and type(self.p7_snapshot)
            is not PaperTradePersistenceSnapshotV1
        ):
            raise TypeError(
                "p7_snapshot must be exact "
                "PaperTradePersistenceSnapshotV1"
            )

        if (
            type(self.p8_snapshot)
            is not PaperPortfolioPersistenceSnapshotV1
        ):
            raise TypeError(
                "p8_snapshot must be exact "
                "PaperPortfolioPersistenceSnapshotV1"
            )

        if type(self.paper_action_occurred) is not bool:
            raise TypeError("paper_action_occurred must be bool")

        if type(self.idempotent_replay) is not bool:
            raise TypeError("idempotent_replay must be bool")

        if self.status == "OPEN":
            if self.entry_result.status != "OPEN":
                raise ValueError("OPEN requires exact OPEN entry result")

            if self.p7_snapshot is None:
                raise ValueError("OPEN requires durable P7 snapshot")

            if self.p7_snapshot.position is None:
                raise ValueError("OPEN requires durable position")

            if (
                self.p7_snapshot.lifecycle_state.current_state
                != "OPEN"
            ):
                raise ValueError("OPEN requires OPEN lifecycle state")

            if not self.paper_action_occurred:
                raise ValueError("OPEN requires simulated paper action")
        else:
            if self.p7_snapshot is not None:
                raise ValueError(
                    "non-OPEN result cannot persist P7 entry state"
                )

            if self.paper_action_occurred:
                raise ValueError(
                    "non-OPEN result cannot report paper action"
                )

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
        ):
            raise ValueError("R4.2 must remain PAPER-only")


def _find_persisted_reservation(
    *,
    admission_result: PaperPortfolioAdmissionResultV1,
    persisted: PaperPortfolioPersistenceSnapshotV1,
) -> PaperCapitalReservationV1:
    matches = tuple(
        item
        for item in persisted.portfolio_snapshot.reservations
        if item.reservation_id
        == admission_result.requested_reservation_id
    )

    if len(matches) != 1:
        raise ValueError("persisted admission reservation missing")

    return matches[0]


def _validate_reservation_lineage(
    *,
    admission_result: PaperPortfolioAdmissionResultV1,
    plan: IntegratedThreeTargetTradePlanResultV1,
    admission_reservation: PaperCapitalReservationV1,
    persisted_reservation: PaperCapitalReservationV1,
) -> None:
    expected = (
        admission_reservation.reservation_id,
        admission_reservation.portfolio_id,
        admission_reservation.admission_request_id,
        admission_reservation.admission_idempotency_key,
        admission_reservation.integrated_trade_plan_result_id,
        admission_reservation.trade_plan_id,
        admission_reservation.original_capital_amount,
        admission_reservation.original_risk_amount,
        admission_reservation.initial_quantity,
    )

    actual = (
        persisted_reservation.reservation_id,
        persisted_reservation.portfolio_id,
        persisted_reservation.admission_request_id,
        persisted_reservation.admission_idempotency_key,
        persisted_reservation.integrated_trade_plan_result_id,
        persisted_reservation.trade_plan_id,
        persisted_reservation.original_capital_amount,
        persisted_reservation.original_risk_amount,
        persisted_reservation.initial_quantity,
    )

    if actual != expected:
        raise ValueError("persisted admission reservation mismatch")

    if (
        persisted_reservation.integrated_trade_plan_result_id
        != plan.integration_id
    ):
        raise ValueError("persisted reservation integration mismatch")

    if (
        persisted_reservation.trade_plan_id
        != plan.capital_quantity_result.trade_plan_id
    ):
        raise ValueError("persisted reservation trade identity mismatch")

    if persisted_reservation.reservation_status not in {
        "PENDING_HOLD",
        "ACTIVE",
    }:
        raise ValueError("persisted reservation is not entry eligible")

    if persisted_reservation.reservation_status == "PENDING_HOLD":
        if persisted_reservation.position_id is not None:
            raise ValueError(
                "PENDING_HOLD reservation cannot have position"
            )

    if persisted_reservation.reservation_status == "ACTIVE":
        if persisted_reservation.position_id is None:
            raise ValueError(
                "ACTIVE reservation requires persisted position"
            )

        if persisted_reservation.last_p7_lifecycle_state != "OPEN":
            raise ValueError(
                "ACTIVE replay reservation must retain OPEN state"
            )


def _validate_admission(
    *,
    admission_result: PaperPortfolioAdmissionResultV1,
    plan: IntegratedThreeTargetTradePlanResultV1,
    portfolio_id: str,
    portfolio_policy: PaperPortfolioPolicyV1,
    persisted: PaperPortfolioPersistenceSnapshotV1,
) -> PaperCapitalReservationV1:
    if admission_result.status != "APPROVED":
        raise ValueError("R4.2 requires APPROVED admission")

    if admission_result.approved is not True:
        raise ValueError("R4.2 requires approved admission")

    admission_reservation = admission_result.resulting_reservation

    if admission_reservation is None:
        raise ValueError("approved admission reservation missing")

    if admission_reservation.reservation_status != "PENDING_HOLD":
        raise ValueError("R4.2 requires PENDING_HOLD admission")

    if admission_reservation.position_id is not None:
        raise ValueError("PENDING_HOLD cannot already have position")

    if admission_result.portfolio_id != portfolio_id:
        raise ValueError("admission portfolio mismatch")

    if (
        admission_result.portfolio_policy_id
        != portfolio_policy.portfolio_policy_id
    ):
        raise ValueError("admission policy mismatch")

    if admission_result.integration_id != plan.integration_id:
        raise ValueError("admission/plan integration mismatch")

    if (
        admission_result.trade_plan_id
        != plan.capital_quantity_result.trade_plan_id
    ):
        raise ValueError("admission/plan trade identity mismatch")

    if persisted.portfolio_id != portfolio_id:
        raise ValueError("persisted portfolio mismatch")

    if (
        persisted.portfolio_snapshot.portfolio_policy_id
        != portfolio_policy.portfolio_policy_id
    ):
        raise ValueError("persisted portfolio policy mismatch")

    admission_hash = dict(
        persisted.admission_idempotency_records
    ).get(admission_result.admission_idempotency_key)

    if admission_hash != admission_result.admission_payload_hash:
        raise ValueError("persisted admission evidence mismatch")

    persisted_reservation = _find_persisted_reservation(
        admission_result=admission_result,
        persisted=persisted,
    )

    _validate_reservation_lineage(
        admission_result=admission_result,
        plan=plan,
        admission_reservation=admission_reservation,
        persisted_reservation=persisted_reservation,
    )

    return persisted_reservation


def _validate_market_identity(
    *,
    plan: IntegratedThreeTargetTradePlanResultV1,
    observation: PaperMarketObservationV1,
) -> None:
    selected = (
        plan.option_contract_selection_result
        .selected_contract
        .contract
    )

    if observation.underlying_symbol != selected.underlying_symbol:
        raise ValueError("observation underlying mismatch")

    if observation.option_symbol != selected.trading_symbol:
        raise ValueError("observation option symbol mismatch")

    if observation.trade_plan_id != (
        plan.capital_quantity_result.trade_plan_id
    ):
        raise ValueError("observation trade-plan mismatch")

    if observation.integrated_trade_plan_result_id != (
        plan.integration_id
    ):
        raise ValueError("observation integration mismatch")

    if observation.selected_option_contract_id != (
        selected.contract_id
    ):
        raise ValueError("observation contract mismatch")


def _entry_input(
    *,
    plan: IntegratedThreeTargetTradePlanResultV1,
    lifecycle_policy: PaperTradeLifecyclePolicyV1,
    observation: PaperMarketObservationV1,
    evaluated_at,
    initial_lifecycle_state_id: str,
    requested_transition_id: str,
    position_id: str,
    entry_fill_id: str,
) -> PaperTradeEntryEvaluationInputV1:
    initial_state = build_initial_paper_trade_lifecycle_state(
        lifecycle_state_id=initial_lifecycle_state_id,
        trade_plan_id=plan.capital_quantity_result.trade_plan_id,
        integrated_trade_plan_result_id=plan.integration_id,
        lifecycle_policy=lifecycle_policy,
        created_at=evaluated_at,
    )

    return PaperTradeEntryEvaluationInputV1(
        integrated_trade_plan_result=plan,
        lifecycle_policy=lifecycle_policy,
        lifecycle_state=initial_state,
        observation=observation,
        evaluation_timestamp=evaluated_at,
        requested_transition_id=requested_transition_id,
        position_id=position_id,
        entry_fill_id=entry_fill_id,
        metadata={"scope": "R4.2_SIMULATED_ENTRY"},
    )


def _existing_p7_snapshot(
    *,
    trade_persistence_service: PaperTradePersistenceService,
    paper_trade_id: str,
    paper_trade_adapter_idempotency_key: str,
) -> PaperTradePersistenceSnapshotV1 | None:
    prior_by_key = (
        trade_persistence_service.get_by_idempotency_key(
            paper_trade_adapter_idempotency_key
        )
    )
    prior_by_id = trade_persistence_service.get(paper_trade_id)

    if (
        prior_by_key is not None
        and prior_by_id is not None
        and prior_by_key != prior_by_id
    ):
        raise ValueError("P7_PERSISTED_IDENTITY_CONFLICT")

    return prior_by_key or prior_by_id


def execute_admitted_plan_simulated_entry(
    *,
    admission_result: PaperPortfolioAdmissionResultV1,
    integrated_trade_plan_result: IntegratedThreeTargetTradePlanResultV1,
    portfolio_policy: PaperPortfolioPolicyV1,
    lifecycle_policy: PaperTradeLifecyclePolicyV1,
    observation: PaperMarketObservationV1,
    portfolio_id: str,
    paper_trade_id: str,
    paper_trade_adapter_idempotency_key: str,
    initial_lifecycle_state_id: str,
    resulting_lifecycle_state_id: str,
    requested_transition_id: str,
    position_id: str,
    entry_fill_id: str,
    activation_result_snapshot_id: str,
    activation_portfolio_event_id: str,
    activation_update_idempotency_key: str,
    evaluated_at,
    portfolio_persistence_service: PaperPortfolioPersistenceService,
    trade_persistence_service: PaperTradePersistenceService,
    broker_order_submission: bool = False,
) -> AdmittedPlanSimulatedEntryResultV1:
    """Evaluate and persist one simulated PAPER entry after R4.1."""

    if type(admission_result) is not PaperPortfolioAdmissionResultV1:
        raise TypeError(
            "admission_result must be exact "
            "PaperPortfolioAdmissionResultV1"
        )

    if (
        type(integrated_trade_plan_result)
        is not IntegratedThreeTargetTradePlanResultV1
    ):
        raise TypeError(
            "integrated_trade_plan_result must be exact "
            "IntegratedThreeTargetTradePlanResultV1"
        )

    if type(portfolio_policy) is not PaperPortfolioPolicyV1:
        raise TypeError(
            "portfolio_policy must be exact PaperPortfolioPolicyV1"
        )

    if type(lifecycle_policy) is not PaperTradeLifecyclePolicyV1:
        raise TypeError(
            "lifecycle_policy must be exact "
            "PaperTradeLifecyclePolicyV1"
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
    paper_trade_adapter_idempotency_key = _text(
        paper_trade_adapter_idempotency_key,
        "paper_trade_adapter_idempotency_key",
    )
    initial_lifecycle_state_id = _text(
        initial_lifecycle_state_id,
        "initial_lifecycle_state_id",
    )
    resulting_lifecycle_state_id = _text(
        resulting_lifecycle_state_id,
        "resulting_lifecycle_state_id",
    )
    requested_transition_id = _text(
        requested_transition_id,
        "requested_transition_id",
    )
    position_id = _text(position_id, "position_id")
    entry_fill_id = _text(entry_fill_id, "entry_fill_id")
    activation_result_snapshot_id = _text(
        activation_result_snapshot_id,
        "activation_result_snapshot_id",
    )
    activation_portfolio_event_id = _text(
        activation_portfolio_event_id,
        "activation_portfolio_event_id",
    )
    activation_update_idempotency_key = _text(
        activation_update_idempotency_key,
        "activation_update_idempotency_key",
    )

    if broker_order_submission is not False:
        raise ValueError("order submission must remain disabled")

    plan = integrated_trade_plan_result

    if plan.status != "READY":
        raise ValueError("R4.2 requires READY plan")

    if plan.execution_mode != "PAPER":
        raise ValueError("R4.2 plan must remain PAPER")

    if plan.live_execution_eligible is not False:
        raise ValueError("R4.2 plan cannot be live eligible")

    persisted_before = portfolio_persistence_service.get(
        portfolio_id
    )

    if persisted_before is None:
        raise ValueError("persisted R4.1 portfolio not found")

    _validate_admission(
        admission_result=admission_result,
        plan=plan,
        portfolio_id=portfolio_id,
        portfolio_policy=portfolio_policy,
        persisted=persisted_before,
    )

    _validate_market_identity(
        plan=plan,
        observation=observation,
    )

    entry_input = _entry_input(
        plan=plan,
        lifecycle_policy=lifecycle_policy,
        observation=observation,
        evaluated_at=evaluated_at,
        initial_lifecycle_state_id=initial_lifecycle_state_id,
        requested_transition_id=requested_transition_id,
        position_id=position_id,
        entry_fill_id=entry_fill_id,
    )

    entry_result = evaluate_paper_trade_entry(entry_input)

    if entry_result.status != "OPEN":
        status = (
            "BLOCKED"
            if entry_result.status == "BLOCKED"
            else (
                "WAITING_FOR_ENTRY"
                if entry_result.status == "WAITING_FOR_ENTRY"
                else "ENTRY_CLOSED"
            )
        )

        return AdmittedPlanSimulatedEntryResultV1(
            status=status,
            entry_result=entry_result,
            p7_snapshot=None,
            p8_snapshot=persisted_before,
            paper_action_occurred=False,
        )

    expected_p7 = build_entry_paper_trade_persistence_snapshot(
        paper_trade_id=paper_trade_id,
        adapter_idempotency_key=(
            paper_trade_adapter_idempotency_key
        ),
        entry_input=entry_input,
        entry_result=entry_result,
        resulting_lifecycle_state_id=(
            resulting_lifecycle_state_id
        ),
        persisted_at=evaluated_at,
    )

    prior = _existing_p7_snapshot(
        trade_persistence_service=trade_persistence_service,
        paper_trade_id=paper_trade_id,
        paper_trade_adapter_idempotency_key=(
            paper_trade_adapter_idempotency_key
        ),
    )

    if prior is not None:
        if (
            prior.paper_trade_id != paper_trade_id
            or prior.adapter_idempotency_key
            != paper_trade_adapter_idempotency_key
        ):
            raise ValueError("P7_PERSISTED_IDENTITY_CONFLICT")

        if (
            prior.idempotency_payload_hash
            != expected_p7.idempotency_payload_hash
        ):
            raise ValueError("IDEMPOTENCY_PAYLOAD_CONFLICT")

        if prior.integrity_hash != expected_p7.integrity_hash:
            raise ValueError("P7_PERSISTED_STATE_CONFLICT")

        persisted_p7 = prior
        idempotent_replay = True
    else:
        persisted_p7 = trade_persistence_service.save(
            expected_p7
        )
        idempotent_replay = False

    activated = PaperPortfolioLifecycleCoordinator(
        portfolio_persistence_service
    ).apply_p7_snapshot(
        portfolio_id=portfolio_id,
        policy=portfolio_policy,
        p7_snapshot=persisted_p7,
        result_snapshot_id=activation_result_snapshot_id,
        portfolio_event_id=activation_portfolio_event_id,
        update_idempotency_key=(
            activation_update_idempotency_key
        ),
        updated_at=evaluated_at,
    )

    return AdmittedPlanSimulatedEntryResultV1(
        status="OPEN",
        entry_result=entry_result,
        p7_snapshot=persisted_p7,
        p8_snapshot=activated,
        paper_action_occurred=True,
        idempotent_replay=idempotent_replay,
    )