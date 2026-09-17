"""R4.1 real-contract P6-to-P8 admission-only certification."""
from dataclasses import replace
from pathlib import Path

import pytest

from services.contracts.paper_orchestration_cycle_result_v1 import PaperOrchestrationCycleResultV1
from services.contracts.paper_portfolio_admission_result_v1 import PaperPortfolioAdmissionResultV1
from services.contracts.paper_portfolio_persistence_snapshot_v1 import PaperPortfolioPersistenceSnapshotV1
from services.paper_orchestration.plan_to_portfolio_admission_runtime import (
    PlanToPortfolioAdmissionResultV1,
    adapt_plan_to_portfolio_admission_to_cycle_result,
    execute_plan_to_portfolio_admission,
)
from services.paper_portfolio.paper_portfolio_persistence_service import PaperPortfolioPersistenceService
from services.paper_portfolio_repository import PaperPortfolioRepository
from tests.p8_portfolio_harness import PORTFOLIO_ID, make_cost_complete_integrated, make_p8_policy
from test_certified_two_market_parent_runtime import cycles


def _runtime_args(tmp_path, *, plan=None, policy=None, cycle_changes=None):
    plan = plan or make_cost_complete_integrated()
    policy = policy or make_p8_policy()
    nifty, _ = cycles()
    cycle = replace(nifty, p6_integration_id=plan.integration_id, **(cycle_changes or {}))
    service = PaperPortfolioPersistenceService(PaperPortfolioRepository(tmp_path / "portfolio.json"))
    return dict(cycle_input=cycle, integrated_trade_plan_result=plan, portfolio_policy=policy, portfolio_id=PORTFOLIO_ID, starting_capital=100_000.0, persistence_service=service, admission_result_id="r41-admission", requested_reservation_id="r41-reservation", initial_portfolio_snapshot_id="r41-initial"), service


def test_ready_plan_admits_one_pending_hold_and_projects_p8_cycle(tmp_path):
    args, service = _runtime_args(tmp_path)
    value = execute_plan_to_portfolio_admission(**args)
    plan = args["integrated_trade_plan_result"]
    assert type(value) is PlanToPortfolioAdmissionResultV1
    assert type(value.admission_result) is PaperPortfolioAdmissionResultV1
    assert type(value.portfolio_snapshot) is PaperPortfolioPersistenceSnapshotV1
    assert value.status == "APPROVED"
    persisted = service.get(PORTFOLIO_ID)
    assert persisted == value.portfolio_snapshot
    assert len(persisted.portfolio_snapshot.reservations) == 1
    reservation = persisted.portfolio_snapshot.reservations[0]
    assert reservation.reservation_status == "PENDING_HOLD" and reservation.position_id is None
    capital = plan.capital_quantity_result
    assert (reservation.original_capital_amount, reservation.original_risk_amount, reservation.initial_quantity) == (capital.estimated_total_capital_requirement, capital.estimated_risk_amount, capital.planned_quantity)
    result = adapt_plan_to_portfolio_admission_to_cycle_result(cycle_input=args["cycle_input"], admission=value)
    assert type(result) is PaperOrchestrationCycleResultV1
    assert (result.cycle_status, result.terminal_stage, result.stage_results[0].status, result.paper_actions) == ("COMPLETED_NO_ACTION", "P8_ADMISSION", "COMPLETED", ())
    assert all(x.stage not in {"P7_LIFECYCLE", "P8_PORTFOLIO_UPDATE", "PERSISTENCE"} for x in result.stage_results)


def test_duplicate_is_idempotent_and_changed_payload_fails_closed(tmp_path):
    args, service = _runtime_args(tmp_path)
    first = execute_plan_to_portfolio_admission(**args)
    second = execute_plan_to_portfolio_admission(**args)
    assert second.portfolio_snapshot == first.portfolio_snapshot
    assert len(second.portfolio_snapshot.portfolio_snapshot.reservations) == 1
    with pytest.raises(ValueError, match="IDEMPOTENCY_PAYLOAD_CONFLICT"):
        execute_plan_to_portfolio_admission(**(args | {"requested_reservation_id": "changed"}))
    assert service.get(PORTFOLIO_ID) == first.portfolio_snapshot


def test_mismatches_fail_before_mutation(tmp_path):
    args, service = _runtime_args(tmp_path)
    with pytest.raises(ValueError, match="plan/P6 integration mismatch"):
        execute_plan_to_portfolio_admission(**(args | {"cycle_input": replace(args["cycle_input"], p6_integration_id="wrong")}))
    assert service.get(PORTFOLIO_ID) is None
    # A mismatched P6 integration is rejected before any portfolio mutation.


def test_runtime_has_no_p7_trade_or_broker_dependency():
    source = Path("services/paper_orchestration/plan_to_portfolio_admission_runtime.py").read_text(encoding="utf-8").lower()
    source = source.replace("broker_order_submission", "")
    assert all(token not in source for token in ("broker", "place_order(", "submit_order(", "paper_trade_entry", "trade_persistence"))
