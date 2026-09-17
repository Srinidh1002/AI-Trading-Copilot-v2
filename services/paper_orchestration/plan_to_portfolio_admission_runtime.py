"""R4.1 P6-plan to P8-admission-only PAPER runtime."""

from __future__ import annotations

import math
from dataclasses import dataclass

from services.contracts.integrated_three_target_trade_plan_result_v1 import (
    IntegratedThreeTargetTradePlanResultV1,
)
from services.contracts.paper_capital_reservation_v1 import (
    PaperCapitalReservationV1,
)
from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
)
from services.contracts.paper_orchestration_cycle_result_v1 import (
    PaperOrchestrationCycleResultV1,
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
from services.paper_orchestration.paper_state_factories import (
    build_initial_paper_portfolio_snapshot,
)
from services.paper_orchestration.stage_result_factory import (
    build_completed_stage_result,
)
from services.paper_portfolio.paper_portfolio_admission_evaluator import (
    evaluate_paper_portfolio_admission,
)
from services.paper_portfolio.paper_portfolio_aggregation import (
    aggregate_paper_portfolio,
)
from services.paper_portfolio.paper_portfolio_lifecycle_coordinator import (
    PaperPortfolioLifecycleCoordinator,
)
from services.paper_portfolio.paper_portfolio_persistence_service import (
    PaperPortfolioPersistenceService,
)


_ALLOWED_STATUSES = frozenset({"APPROVED", "NO_CAPACITY", "BLOCKED"})


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be a nonblank string")
    return value.strip()


def _positive_number(value: object, name: str) -> float:
    if type(value) not in (int, float) or isinstance(value, bool):
        raise TypeError(f"{name} must be numeric")

    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be finite and positive")

    return result


@dataclass(frozen=True, slots=True)
class PlanToPortfolioAdmissionResultV1:
    """Terminal admission-only result. No P7 or paper entry occurs."""

    admission_result: PaperPortfolioAdmissionResultV1
    portfolio_snapshot: PaperPortfolioPersistenceSnapshotV1
    status: str
    paper_action_occurred: bool = False
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    broker_order_submission: bool = False

    def __post_init__(self) -> None:
        if type(self.admission_result) is not PaperPortfolioAdmissionResultV1:
            raise TypeError(
                "admission_result must be exact "
                "PaperPortfolioAdmissionResultV1"
            )

        if (
            type(self.portfolio_snapshot)
            is not PaperPortfolioPersistenceSnapshotV1
        ):
            raise TypeError(
                "portfolio_snapshot must be exact "
                "PaperPortfolioPersistenceSnapshotV1"
            )

        if self.status not in _ALLOWED_STATUSES:
            raise ValueError("unsupported admission-only status")

        if self.status != self.admission_result.status:
            raise ValueError("result/admission status mismatch")

        if (
            self.portfolio_snapshot.portfolio_id
            != self.admission_result.portfolio_id
        ):
            raise ValueError("result portfolio identity mismatch")

        if self.status == "APPROVED":
            if self.admission_result.approved is not True:
                raise ValueError("APPROVED requires approved admission")

            if self.admission_result.resulting_reservation is None:
                raise ValueError("APPROVED requires reservation")

            if self.admission_result.resulting_snapshot is None:
                raise ValueError("APPROVED requires resulting snapshot")

            if (
                self.admission_result.resulting_reservation.reservation_status
                != "PENDING_HOLD"
            ):
                raise ValueError(
                    "APPROVED requires PENDING_HOLD reservation"
                )
        else:
            if self.admission_result.approved is not False:
                raise ValueError(
                    "non-APPROVED result cannot be approved"
                )

            if self.admission_result.resulting_reservation is not None:
                raise ValueError(
                    "non-APPROVED result cannot expose reservation"
                )

            if self.admission_result.resulting_snapshot is not None:
                raise ValueError(
                    "non-APPROVED result cannot expose resulting state"
                )

        if self.paper_action_occurred is not False:
            raise ValueError("admission-only runtime cannot report action")

        if (
            self.execution_mode != "PAPER"
            or self.live_execution_eligible is not False
            or self.broker_order_submission is not False
        ):
            raise ValueError("PAPER-only admission result required")


def _initial_persistence_snapshot(
    *,
    cycle_input: PaperOrchestrationCycleInputV1,
    portfolio_policy: PaperPortfolioPolicyV1,
    portfolio_id: str,
    starting_capital: float,
    initial_portfolio_snapshot_id: str,
) -> PaperPortfolioPersistenceSnapshotV1:
    snapshot = build_initial_paper_portfolio_snapshot(
        portfolio_snapshot_id=initial_portfolio_snapshot_id,
        portfolio_id=portfolio_id,
        policy=portfolio_policy,
        trading_day_id=cycle_input.trading_day_id,
        starting_capital=starting_capital,
        created_at=cycle_input.cycle_requested_at,
    )

    return PaperPortfolioPersistenceSnapshotV1(
        portfolio_id=portfolio_id,
        portfolio_snapshot=snapshot,
        admission_idempotency_records={},
        update_idempotency_records={},
        processed_portfolio_event_hashes={},
        processed_p7_transition_hashes={},
        processed_p7_fill_hashes={},
        created_at=cycle_input.cycle_requested_at,
        updated_at=cycle_input.cycle_requested_at,
        event_sequence=0,
    )


def _plan_market(
    plan: IntegratedThreeTargetTradePlanResultV1,
) -> tuple[str, str]:
    canonical = plan.canonical_trade_plan_input

    if canonical is not None:
        return canonical.underlying_symbol, canonical.exchange

    entry_zone = plan.entry_zone_result
    return entry_zone.underlying_symbol, entry_zone.exchange


def _plan_capital_identity(
    plan: IntegratedThreeTargetTradePlanResultV1,
) -> tuple[str, float, float, int]:
    capital = plan.capital_quantity_result

    return (
        capital.trade_plan_id,
        float(capital.estimated_total_capital_requirement),
        float(capital.estimated_risk_amount),
        capital.planned_quantity,
    )


def _matching_reservation(
    *,
    current: PaperPortfolioPersistenceSnapshotV1,
    admission_idempotency_key: str,
) -> PaperCapitalReservationV1:
    matches = tuple(
        reservation
        for reservation in current.portfolio_snapshot.reservations
        if reservation.admission_idempotency_key
        == admission_idempotency_key
    )

    if len(matches) != 1:
        raise ValueError("IDEMPOTENCY_PERSISTED_STATE_CONFLICT")

    return matches[0]


def _validate_replayed_reservation(
    *,
    reservation: PaperCapitalReservationV1,
    cycle_input: PaperOrchestrationCycleInputV1,
    plan: IntegratedThreeTargetTradePlanResultV1,
    portfolio_id: str,
    requested_reservation_id: str,
) -> None:
    trade_plan_id, capital_amount, risk_amount, quantity = (
        _plan_capital_identity(plan)
    )

    expected = (
        requested_reservation_id,
        portfolio_id,
        cycle_input.p8_admission_request_id,
        cycle_input.p8_admission_idempotency_key,
        plan.integration_id,
        trade_plan_id,
        capital_amount,
        risk_amount,
        quantity,
    )

    actual = (
        reservation.reservation_id,
        reservation.portfolio_id,
        reservation.admission_request_id,
        reservation.admission_idempotency_key,
        reservation.integrated_trade_plan_result_id,
        reservation.trade_plan_id,
        reservation.original_capital_amount,
        reservation.original_risk_amount,
        reservation.initial_quantity,
    )

    if actual != expected:
        raise ValueError("IDEMPOTENCY_PERSISTED_STATE_CONFLICT")

    if reservation.reservation_status != "PENDING_HOLD":
        raise ValueError("IDEMPOTENCY_RESERVATION_STATE_CONFLICT")

    if reservation.position_id is not None:
        raise ValueError("IDEMPOTENCY_RESERVATION_STATE_CONFLICT")


def _reconstruct_pre_admission_snapshot(
    *,
    current: PaperPortfolioPersistenceSnapshotV1,
    reservation: PaperCapitalReservationV1,
    portfolio_policy: PaperPortfolioPolicyV1,
) -> object:
    snapshot = current.portfolio_snapshot

    reservations_before = tuple(
        item
        for item in snapshot.reservations
        if item.reservation_id != reservation.reservation_id
    )

    if len(reservations_before) != len(snapshot.reservations) - 1:
        raise ValueError("IDEMPOTENCY_PERSISTED_STATE_CONFLICT")

    if snapshot.event_sequence <= 0:
        raise ValueError("IDEMPOTENCY_PERSISTED_STATE_CONFLICT")

    return aggregate_paper_portfolio(
        portfolio_snapshot_id=(
            f"{snapshot.portfolio_snapshot_id}:pre-admission-replay"
        ),
        portfolio_id=snapshot.portfolio_id,
        policy=portfolio_policy,
        trading_day_id=snapshot.trading_day_id,
        starting_capital=snapshot.starting_capital,
        reservations=reservations_before,
        position_references=snapshot.position_references,
        event_sequence=snapshot.event_sequence - 1,
        created_at=snapshot.created_at,
        updated_at=reservation.created_at,
        previous_lock_state=snapshot.lock_state,
        blockers=snapshot.blockers,
        decision_reasons=snapshot.decision_reasons,
        warnings=snapshot.warnings,
    )


def _replay_existing_approved_admission(
    *,
    cycle_input: PaperOrchestrationCycleInputV1,
    plan: IntegratedThreeTargetTradePlanResultV1,
    portfolio_policy: PaperPortfolioPolicyV1,
    portfolio_id: str,
    current: PaperPortfolioPersistenceSnapshotV1,
    admission_result_id: str,
    requested_reservation_id: str,
    persisted_payload_hash: str,
) -> PlanToPortfolioAdmissionResultV1:
    reservation = _matching_reservation(
        current=current,
        admission_idempotency_key=(
            cycle_input.p8_admission_idempotency_key
        ),
    )

    event_records = dict(current.processed_portfolio_event_hashes)
    if cycle_input.p8_portfolio_event_id not in event_records:
        raise ValueError("IDEMPOTENCY_PORTFOLIO_EVENT_CONFLICT")

    pre_admission_snapshot = _reconstruct_pre_admission_snapshot(
        current=current,
        reservation=reservation,
        portfolio_policy=portfolio_policy,
    )

    replay_input = PaperPortfolioAdmissionInputV1(
        admission_request_id=cycle_input.p8_admission_request_id,
        admission_idempotency_key=(
            cycle_input.p8_admission_idempotency_key
        ),
        portfolio_event_id=cycle_input.p8_portfolio_event_id,
        portfolio_id=portfolio_id,
        requested_reservation_id=requested_reservation_id,
        evaluated_at=cycle_input.cycle_requested_at,
        trading_day_id=cycle_input.trading_day_id,
        integrated_trade_plan_result=plan,
        current_portfolio_snapshot=pre_admission_snapshot,
        portfolio_policy=portfolio_policy,
    )

    if replay_input.semantic_payload_hash != persisted_payload_hash:
        raise ValueError("IDEMPOTENCY_PAYLOAD_CONFLICT")
    _validate_replayed_reservation(
        reservation=reservation,
        cycle_input=cycle_input,
        plan=plan,
        portfolio_id=portfolio_id,
        requested_reservation_id=requested_reservation_id,
    )
    result = PaperPortfolioAdmissionResultV1(
        admission_result_id=admission_result_id,
        admission_request_id=cycle_input.p8_admission_request_id,
        admission_idempotency_key=(
            cycle_input.p8_admission_idempotency_key
        ),
        admission_payload_hash=persisted_payload_hash,
        portfolio_event_id=cycle_input.p8_portfolio_event_id,
        portfolio_id=portfolio_id,
        portfolio_policy_id=portfolio_policy.portfolio_policy_id,
        trading_day_id=cycle_input.trading_day_id,
        integration_id=plan.integration_id,
        trade_plan_id=reservation.trade_plan_id,
        requested_reservation_id=requested_reservation_id,
        status="APPROVED",
        approved=True,
        reservation_amount=reservation.original_capital_amount,
        reserved_risk_amount=reservation.original_risk_amount,
        projected_available_cash=(
            current.portfolio_snapshot.available_cash
        ),
        projected_reserved_capital=(
            current.portfolio_snapshot.reserved_capital
        ),
        projected_deployed_capital=(
            current.portfolio_snapshot.deployed_capital
        ),
        projected_committed_capital=(
            current.portfolio_snapshot.committed_capital
        ),
        projected_concurrent_trade_count=(
            current.portfolio_snapshot.concurrent_trade_count
        ),
        projected_aggregate_committed_risk=(
            current.portfolio_snapshot.aggregate_committed_risk
        ),
        evaluated_at=cycle_input.cycle_requested_at,
        resulting_reservation=reservation,
        resulting_snapshot=current.portfolio_snapshot,
        metadata={"idempotent_replay": True},
    )

    return PlanToPortfolioAdmissionResultV1(
        admission_result=result,
        portfolio_snapshot=current,
        status="APPROVED",
    )


def execute_plan_to_portfolio_admission(
    *,
    cycle_input: PaperOrchestrationCycleInputV1,
    integrated_trade_plan_result: IntegratedThreeTargetTradePlanResultV1,
    portfolio_policy: PaperPortfolioPolicyV1,
    portfolio_id: str,
    starting_capital: float,
    persistence_service: PaperPortfolioPersistenceService,
    admission_result_id: str,
    requested_reservation_id: str,
    initial_portfolio_snapshot_id: str,
    broker_order_submission: bool = False,
) -> PlanToPortfolioAdmissionResultV1:
    """Admit one exact READY P6 plan and stop before P7."""

    if type(cycle_input) is not PaperOrchestrationCycleInputV1:
        raise TypeError(
            "cycle_input must be exact PaperOrchestrationCycleInputV1"
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

    if type(persistence_service) is not PaperPortfolioPersistenceService:
        raise TypeError(
            "persistence_service must be exact "
            "PaperPortfolioPersistenceService"
        )

    portfolio_id = _text(portfolio_id, "portfolio_id")
    admission_result_id = _text(
        admission_result_id,
        "admission_result_id",
    )
    requested_reservation_id = _text(
        requested_reservation_id,
        "requested_reservation_id",
    )
    initial_portfolio_snapshot_id = _text(
        initial_portfolio_snapshot_id,
        "initial_portfolio_snapshot_id",
    )
    starting_capital = _positive_number(
        starting_capital,
        "starting_capital",
    )

    if broker_order_submission is not False:
        raise ValueError("order submission must remain disabled")

    plan = integrated_trade_plan_result

    if plan.status != "READY":
        raise ValueError("integrated plan must be READY")

    if plan.execution_mode != "PAPER":
        raise ValueError("integrated plan must remain PAPER")

    if plan.live_execution_eligible is not False:
        raise ValueError("integrated plan cannot be live eligible")

    if plan.integration_id != cycle_input.p6_integration_id:
        raise ValueError("plan/P6 integration mismatch")

    if _plan_market(plan) != (
        cycle_input.underlying_symbol,
        cycle_input.exchange,
    ):
        raise ValueError("plan/cycle market mismatch")

    persisted_current = persistence_service.get(portfolio_id)

    if persisted_current is None:
        current = _initial_persistence_snapshot(
            cycle_input=cycle_input,
            portfolio_policy=portfolio_policy,
            portfolio_id=portfolio_id,
            starting_capital=starting_capital,
            initial_portfolio_snapshot_id=(
                initial_portfolio_snapshot_id
            ),
        )
    else:
        current = persisted_current

        if current.portfolio_snapshot.trading_day_id != (
            cycle_input.trading_day_id
        ):
            raise ValueError("portfolio trading day mismatch")

        if current.portfolio_snapshot.portfolio_policy_id != (
            portfolio_policy.portfolio_policy_id
        ):
            raise ValueError("portfolio policy mismatch")

    prior_payload_hash = dict(
        current.admission_idempotency_records
    ).get(cycle_input.p8_admission_idempotency_key)

    if prior_payload_hash is not None:
        return _replay_existing_approved_admission(
            cycle_input=cycle_input,
            plan=plan,
            portfolio_policy=portfolio_policy,
            portfolio_id=portfolio_id,
            current=current,
            admission_result_id=admission_result_id,
            requested_reservation_id=requested_reservation_id,
            persisted_payload_hash=prior_payload_hash,
        )

    admission_input = PaperPortfolioAdmissionInputV1(
        admission_request_id=cycle_input.p8_admission_request_id,
        admission_idempotency_key=(
            cycle_input.p8_admission_idempotency_key
        ),
        portfolio_event_id=cycle_input.p8_portfolio_event_id,
        portfolio_id=portfolio_id,
        requested_reservation_id=requested_reservation_id,
        evaluated_at=cycle_input.cycle_requested_at,
        trading_day_id=cycle_input.trading_day_id,
        integrated_trade_plan_result=plan,
        current_portfolio_snapshot=current.portfolio_snapshot,
        portfolio_policy=portfolio_policy,
    )

    admission_result = evaluate_paper_portfolio_admission(
        admission_result_id=admission_result_id,
        input_value=admission_input,
        resulting_snapshot_id=f"{admission_result_id}:snapshot",
    )

    if admission_result.status == "APPROVED":
        persisted = PaperPortfolioLifecycleCoordinator(
            persistence_service
        ).persist_approved_admission(admission_result)
    else:
        persisted = current

    return PlanToPortfolioAdmissionResultV1(
        admission_result=admission_result,
        portfolio_snapshot=persisted,
        status=admission_result.status,
    )


def adapt_plan_to_portfolio_admission_to_cycle_result(
    *,
    cycle_input: PaperOrchestrationCycleInputV1,
    admission: PlanToPortfolioAdmissionResultV1,
) -> PaperOrchestrationCycleResultV1:
    """Project admission-only outcome to the orchestration cycle contract."""

    if type(cycle_input) is not PaperOrchestrationCycleInputV1:
        raise TypeError(
            "cycle_input must be exact PaperOrchestrationCycleInputV1"
        )

    if type(admission) is not PlanToPortfolioAdmissionResultV1:
        raise TypeError(
            "admission must be exact "
            "PlanToPortfolioAdmissionResultV1"
        )

    cycle_status, stage_status = {
        "APPROVED": ("COMPLETED_NO_ACTION", "COMPLETED"),
        "NO_CAPACITY": ("COMPLETED_NO_ACTION", "NO_ACTION"),
        "BLOCKED": ("BLOCKED", "BLOCKED"),
    }[admission.status]

    result = admission.admission_result
    reservation = result.resulting_reservation

    metadata = {
        "scope": "P8_ADMISSION_ONLY",
        "plan_integration_id": result.integration_id,
        "trade_plan_id": result.trade_plan_id,
        "admission_request_id": result.admission_request_id,
        "admission_idempotency_key": (
            result.admission_idempotency_key
        ),
        "admission_result_id": result.admission_result_id,
        "portfolio_event_id": result.portfolio_event_id,
        "portfolio_id": admission.portfolio_snapshot.portfolio_id,
        "reservation_id": (
            None
            if reservation is None
            else reservation.reservation_id
        ),
    }

    stage = build_completed_stage_result(
        stage_result_id=(
            f"{cycle_input.cycle_id}:p8-admission:r41"
        ),
        cycle_id=cycle_input.cycle_id,
        stage="P8_ADMISSION",
        started_at=cycle_input.cycle_requested_at,
        completed_at=cycle_input.cycle_requested_at,
        source_result=result,
        status=stage_status,
        blockers=result.blockers,
        warnings=result.warnings,
        metadata=metadata,
    )

    return PaperOrchestrationCycleResultV1(
        cycle_result_id=(
            f"{cycle_input.cycle_id}:r41-admission"
        ),
        cycle_id=cycle_input.cycle_id,
        cycle_idempotency_key=cycle_input.cycle_idempotency_key,
        cycle_input_semantic_hash=cycle_input.semantic_hash(),
        cycle_status=cycle_status,
        terminal_stage="P8_ADMISSION",
        started_at=cycle_input.cycle_requested_at,
        completed_at=cycle_input.cycle_requested_at,
        stage_results=(stage,),
        paper_actions=(),
        blockers=result.blockers,
        warnings=result.warnings,
        metadata=metadata,
    )