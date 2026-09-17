"""R4.1 admission outcome and no-mutation certification."""

from dataclasses import replace
import pytest
from services.contracts.paper_portfolio_persistence_snapshot_v1 import (
    PaperPortfolioPersistenceSnapshotV1,
)
from services.paper_orchestration.paper_state_factories import (
    build_initial_paper_portfolio_snapshot,
)
from services.paper_orchestration.plan_to_portfolio_admission_runtime import (
    adapt_plan_to_portfolio_admission_to_cycle_result,
    execute_plan_to_portfolio_admission,
)
from services.paper_portfolio.paper_portfolio_persistence_service import (
    PaperPortfolioPersistenceService,
)
from services.paper_portfolio_repository import PaperPortfolioRepository
from test_certified_two_market_parent_runtime import cycles
from tests.p8_portfolio_harness import (
    PORTFOLIO_ID,
    make_cost_complete_integrated,
    make_p8_policy,
)


def _service(tmp_path):
    return PaperPortfolioPersistenceService(
        PaperPortfolioRepository(tmp_path / "portfolio.json")
    )


def _cycle_for(plan, **changes):
    nifty, _ = cycles()
    return replace(
        nifty,
        p6_integration_id=plan.integration_id,
        **changes,
    )


def _runtime_args(
    tmp_path,
    *,
    plan=None,
    policy=None,
    cycle=None,
    service=None,
):
    plan = plan or make_cost_complete_integrated()
    policy = policy or make_p8_policy()
    cycle = cycle or _cycle_for(plan)
    service = service or _service(tmp_path)

    return {
        "cycle_input": cycle,
        "integrated_trade_plan_result": plan,
        "portfolio_policy": policy,
        "portfolio_id": PORTFOLIO_ID,
        "starting_capital": 100_000.0,
        "persistence_service": service,
        "admission_result_id": "r41-outcome-admission",
        "requested_reservation_id": "r41-outcome-reservation",
        "initial_portfolio_snapshot_id": "r41-outcome-initial",
    }, service


def _initial_envelope(
    *,
    cycle,
    policy,
    blockers=(),
    trading_day_id=None,
):
    snapshot = build_initial_paper_portfolio_snapshot(
        portfolio_snapshot_id="r41-existing-initial",
        portfolio_id=PORTFOLIO_ID,
        policy=policy,
        trading_day_id=(
            cycle.trading_day_id
            if trading_day_id is None
            else trading_day_id
        ),
        starting_capital=100_000.0,
        created_at=cycle.cycle_requested_at,
    )

    if blockers:
        snapshot = replace(snapshot, blockers=blockers)

    return PaperPortfolioPersistenceSnapshotV1(
        portfolio_id=PORTFOLIO_ID,
        portfolio_snapshot=snapshot,
        admission_idempotency_records={},
        update_idempotency_records={},
        processed_portfolio_event_hashes={},
        processed_p7_transition_hashes={},
        processed_p7_fill_hashes={},
        created_at=cycle.cycle_requested_at,
        updated_at=cycle.cycle_requested_at,
        event_sequence=0,
    )


def test_no_capacity_does_not_persist_new_portfolio(tmp_path):
    plan = make_cost_complete_integrated()
    policy = make_p8_policy(
        maximum_total_deployed_capital=1.0,
    )
    cycle = _cycle_for(plan)

    args, service = _runtime_args(
        tmp_path,
        plan=plan,
        policy=policy,
        cycle=cycle,
    )

    result = execute_plan_to_portfolio_admission(**args)

    assert result.status == "NO_CAPACITY"
    assert result.admission_result.approved is False
    assert result.admission_result.resulting_reservation is None
    assert result.admission_result.resulting_snapshot is None
    assert "DEPLOYED_CAPITAL_LIMIT" in (
        result.admission_result.decision_reasons
    )
    assert service.get(PORTFOLIO_ID) is None

    cycle_result = adapt_plan_to_portfolio_admission_to_cycle_result(
        cycle_input=cycle,
        admission=result,
    )

    assert cycle_result.cycle_status == "COMPLETED_NO_ACTION"
    assert cycle_result.terminal_stage == "P8_ADMISSION"
    assert cycle_result.stage_results[0].status == "NO_ACTION"
    assert cycle_result.paper_actions == ()


def test_no_capacity_leaves_existing_portfolio_unchanged(tmp_path):
    plan = make_cost_complete_integrated()
    policy = make_p8_policy(
        maximum_total_deployed_capital=1.0,
    )
    cycle = _cycle_for(plan)
    service = _service(tmp_path)

    before = service.save(
        _initial_envelope(
            cycle=cycle,
            policy=policy,
        )
    )

    args, _ = _runtime_args(
        tmp_path,
        plan=plan,
        policy=policy,
        cycle=cycle,
        service=service,
    )

    result = execute_plan_to_portfolio_admission(**args)

    assert result.status == "NO_CAPACITY"
    assert result.portfolio_snapshot == before
    assert service.get(PORTFOLIO_ID) == before
    assert before.portfolio_snapshot.reservations == ()
    assert before.event_sequence == 0


def test_blocked_leaves_existing_portfolio_unchanged(tmp_path):
    plan = make_cost_complete_integrated()
    policy = make_p8_policy()
    cycle = _cycle_for(plan)
    service = _service(tmp_path)

    before = service.save(
        _initial_envelope(
            cycle=cycle,
            policy=policy,
            blockers=("TEST_PORTFOLIO_CORRUPT",),
        )
    )

    args, _ = _runtime_args(
        tmp_path,
        plan=plan,
        policy=policy,
        cycle=cycle,
        service=service,
    )

    result = execute_plan_to_portfolio_admission(**args)

    assert result.status == "BLOCKED"
    assert result.admission_result.approved is False
    assert result.admission_result.resulting_reservation is None
    assert result.admission_result.resulting_snapshot is None
    assert result.admission_result.blockers == (
        "PORTFOLIO_CORRUPT",
    )
    assert result.portfolio_snapshot == before
    assert service.get(PORTFOLIO_ID) == before

    cycle_result = adapt_plan_to_portfolio_admission_to_cycle_result(
        cycle_input=cycle,
        admission=result,
    )

    assert cycle_result.cycle_status == "BLOCKED"
    assert cycle_result.terminal_stage == "P8_ADMISSION"
    assert cycle_result.stage_results[0].status == "BLOCKED"
    assert cycle_result.blockers == ("PORTFOLIO_CORRUPT",)
    assert cycle_result.paper_actions == ()


def test_existing_matching_portfolio_is_reused(tmp_path):
    plan = make_cost_complete_integrated()
    policy = make_p8_policy()
    cycle = _cycle_for(plan)
    service = _service(tmp_path)

    before = service.save(
        _initial_envelope(
            cycle=cycle,
            policy=policy,
        )
    )

    args, _ = _runtime_args(
        tmp_path,
        plan=plan,
        policy=policy,
        cycle=cycle,
        service=service,
    )

    result = execute_plan_to_portfolio_admission(**args)
    persisted = service.get(PORTFOLIO_ID)

    assert result.status == "APPROVED"
    assert persisted is not None
    assert persisted.created_at == before.created_at
    assert persisted.portfolio_snapshot.created_at == (
        before.portfolio_snapshot.created_at
    )
    assert persisted.event_sequence == before.event_sequence + 1
    assert len(persisted.portfolio_snapshot.reservations) == 1
def test_trading_day_mismatch_fails_before_mutation(tmp_path):
    plan = make_cost_complete_integrated()
    policy = make_p8_policy()
    cycle = _cycle_for(plan)
    service = _service(tmp_path)

    before = service.save(
        _initial_envelope(
            cycle=cycle,
            policy=policy,
            trading_day_id="different-trading-day",
        )
    )

    args, _ = _runtime_args(
        tmp_path,
        plan=plan,
        policy=policy,
        cycle=cycle,
        service=service,
    )

    with pytest.raises(
        ValueError,
        match="portfolio trading day mismatch",
    ):
        execute_plan_to_portfolio_admission(**args)

    assert service.get(PORTFOLIO_ID) == before


def test_portfolio_policy_mismatch_fails_before_mutation(tmp_path):
    plan = make_cost_complete_integrated()
    existing_policy = make_p8_policy(
        portfolio_policy_id="existing-policy",
    )
    incoming_policy = make_p8_policy(
        portfolio_policy_id="incoming-policy",
    )
    cycle = _cycle_for(plan)
    service = _service(tmp_path)

    before = service.save(
        _initial_envelope(
            cycle=cycle,
            policy=existing_policy,
        )
    )

    args, _ = _runtime_args(
        tmp_path,
        plan=plan,
        policy=incoming_policy,
        cycle=cycle,
        service=service,
    )

    with pytest.raises(
        ValueError,
        match="portfolio policy mismatch",
    ):
        execute_plan_to_portfolio_admission(**args)

    assert service.get(PORTFOLIO_ID) == before


def test_plan_cycle_market_mismatch_fails_before_mutation(tmp_path):
    plan = make_cost_complete_integrated()
    policy = make_p8_policy()

    _, sensex = cycles()
    cycle = replace(
        sensex,
        p6_integration_id=plan.integration_id,
    )

    args, service = _runtime_args(
        tmp_path,
        plan=plan,
        policy=policy,
        cycle=cycle,
    )

    with pytest.raises(
        ValueError,
        match="plan/cycle market mismatch",
    ):
        execute_plan_to_portfolio_admission(**args)

    assert service.get(PORTFOLIO_ID) is None


def test_submission_guard_rejects_before_mutation(tmp_path):
    args, service = _runtime_args(tmp_path)

    with pytest.raises(
        ValueError,
        match="order submission must remain disabled",
    ):
        execute_plan_to_portfolio_admission(
            **args,
            broker_order_submission=True,
        )

    assert service.get(PORTFOLIO_ID) is None


def test_changed_portfolio_event_is_payload_conflict(tmp_path):
    args, service = _runtime_args(tmp_path)

    first = execute_plan_to_portfolio_admission(**args)
    changed_cycle = replace(
        args["cycle_input"],
        p8_portfolio_event_id="changed-event",
    )

    with pytest.raises(
        ValueError,
        match=(
            "IDEMPOTENCY_PORTFOLIO_EVENT_CONFLICT"
            "|IDEMPOTENCY_PAYLOAD_CONFLICT"
        ),
    ):
        execute_plan_to_portfolio_admission(
            **(
                args
                | {
                    "cycle_input": changed_cycle,
                }
            )
        )

    assert service.get(PORTFOLIO_ID) == first.portfolio_snapshot