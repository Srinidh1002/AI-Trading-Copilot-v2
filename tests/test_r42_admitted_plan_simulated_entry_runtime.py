"""R4.2 admitted-plan simulated entry and persistence certification."""

from dataclasses import replace
from datetime import timedelta

import pytest

from services.paper_orchestration.admitted_plan_simulated_entry_runtime import (
    AdmittedPlanSimulatedEntryResultV1,
    execute_admitted_plan_simulated_entry,
)
from services.paper_orchestration.plan_to_portfolio_admission_runtime import (
    execute_plan_to_portfolio_admission,
)
from services.paper_portfolio.paper_portfolio_persistence_service import (
    PaperPortfolioPersistenceService,
)
from services.paper_portfolio_repository import PaperPortfolioRepository
from services.paper_trade_repository import PaperTradeRepository
from services.paper_trading.paper_trade_persistence_service import (
    PaperTradePersistenceService,
)
from test_certified_two_market_parent_runtime import cycles
from tests.p7_fixture_helpers import (
    make_observation,
    make_policy,
)
from tests.p8_portfolio_harness import (
    PORTFOLIO_ID,
    make_cost_complete_integrated,
    make_p8_policy,
)


def _services(tmp_path):
    portfolio_service = PaperPortfolioPersistenceService(
        PaperPortfolioRepository(tmp_path / "portfolio.json")
    )
    trade_service = PaperTradePersistenceService(
        PaperTradeRepository(tmp_path / "trades.json")
    )
    return portfolio_service, trade_service


def _plan_with_future_expiry(plan, evaluated_at):
    selection = plan.option_contract_selection_result
    selected_candidate = selection.selected_contract
    selected_contract = selected_candidate.contract

    future_contract = replace(
        selected_contract,
        expiry_date=evaluated_at.date() + timedelta(days=30),
    )
    future_candidate = replace(
        selected_candidate,
        contract=future_contract,
    )
    future_selection = replace(
        selection,
        selected_contract=future_candidate,
    )

    return replace(
        plan,
        option_contract_selection_result=future_selection,
    )


def _admitted_runtime_args(tmp_path):
    plan = make_cost_complete_integrated()
    policy = make_p8_policy()
    lifecycle_policy = make_policy(
        entry_timeout_seconds=300,
        maximum_observation_age_seconds=300,
        maximum_holding_seconds=3600,
    )

    nifty, _ = cycles()
    evaluated_at = nifty.cycle_requested_at

    plan = _plan_with_future_expiry(
        plan,
        evaluated_at,
    )

    cycle = replace(
        nifty,
        p6_integration_id=plan.integration_id,
    )

    selected_contract = (
        plan.option_contract_selection_result
        .selected_contract
        .contract
    )

    entry_price = plan.entry_zone_result.entry_reference_price

    observation = make_observation(
        observation_id="r42-entry-observation",
        trade_plan_id=plan.capital_quantity_result.trade_plan_id,
        integrated_trade_plan_result_id=plan.integration_id,
        selected_option_contract_id=selected_contract.contract_id,
        underlying_symbol=selected_contract.underlying_symbol,
        option_symbol=selected_contract.trading_symbol,
        exchange=selected_contract.exchange,
        market=selected_contract.underlying_symbol,
        observed_at=evaluated_at,
        received_at=evaluated_at,
        market_session_date=evaluated_at.date(),
        option_last_price=entry_price,
        option_open=entry_price,
        option_low=entry_price - 1.0,
        option_high=entry_price + 1.0,
        option_close=entry_price,
    )

    portfolio_service, trade_service = _services(tmp_path)

    admission = execute_plan_to_portfolio_admission(
        cycle_input=cycle,
        integrated_trade_plan_result=plan,
        portfolio_policy=policy,
        portfolio_id=PORTFOLIO_ID,
        starting_capital=100_000.0,
        persistence_service=portfolio_service,
        admission_result_id="r42-admission",
        requested_reservation_id="r42-reservation",
        initial_portfolio_snapshot_id="r42-initial",
    )

    assert admission.status == "APPROVED"

    args = {
        "admission_result": admission.admission_result,
        "integrated_trade_plan_result": plan,
        "portfolio_policy": policy,
        "lifecycle_policy": lifecycle_policy,
        "observation": observation,
        "portfolio_id": PORTFOLIO_ID,
        "paper_trade_id": "r42-paper-trade",
        "paper_trade_adapter_idempotency_key": "r42-entry-key",
        "initial_lifecycle_state_id": "r42-state-initial",
        "resulting_lifecycle_state_id": "r42-state-open",
        "requested_transition_id": "r42-transition",
        "position_id": "r42-position",
        "entry_fill_id": "r42-entry-fill",
        "activation_result_snapshot_id": "r42-portfolio-open",
        "activation_portfolio_event_id": "r42-activation-event",
        "activation_update_idempotency_key": "r42-activation-key",
        "evaluated_at": evaluated_at,
        "portfolio_persistence_service": portfolio_service,
        "trade_persistence_service": trade_service,
    }

    return args, portfolio_service, trade_service


def test_open_entry_persists_one_fill_position_and_active_reservation(
    tmp_path,
):
    args, portfolio_service, trade_service = (
        _admitted_runtime_args(tmp_path)
    )

    result = execute_admitted_plan_simulated_entry(**args)

    assert type(result) is AdmittedPlanSimulatedEntryResultV1
    assert result.status == "OPEN"
    assert result.paper_action_occurred is True
    assert result.idempotent_replay is False
    assert result.entry_result.status == "OPEN"
    assert result.p7_snapshot is not None
    assert result.p7_snapshot.position is not None

    persisted_trade = trade_service.get("r42-paper-trade")
    assert persisted_trade == result.p7_snapshot

    position = persisted_trade.position
    assert position is not None
    assert position.position_id == "r42-position"
    assert position.entry_fill.fill_id == "r42-entry-fill"
    assert position.lifecycle_state == "OPEN"
    assert position.exit_fills == ()

    persisted_portfolio = portfolio_service.get(PORTFOLIO_ID)
    assert persisted_portfolio == result.p8_snapshot
    assert len(
        persisted_portfolio.portfolio_snapshot.reservations
    ) == 1
    assert len(
        persisted_portfolio.portfolio_snapshot.position_references
    ) == 1

    reservation = (
        persisted_portfolio.portfolio_snapshot.reservations[0]
    )
    reference = (
        persisted_portfolio.portfolio_snapshot
        .position_references[0]
    )

    assert reservation.reservation_status == "ACTIVE"
    assert reservation.position_id == "r42-position"
    assert reservation.last_p7_lifecycle_state == "OPEN"
    assert reference.position_id == "r42-position"
    assert reference.lifecycle_state == "OPEN"


def test_exact_replay_creates_no_duplicate_state(tmp_path):
    args, portfolio_service, trade_service = (
        _admitted_runtime_args(tmp_path)
    )

    first = execute_admitted_plan_simulated_entry(**args)
    portfolio_before = portfolio_service.get(PORTFOLIO_ID)
    trade_before = trade_service.get("r42-paper-trade")

    second = execute_admitted_plan_simulated_entry(**args)

    assert second.status == "OPEN"
    assert second.idempotent_replay is True
    assert second.p7_snapshot == first.p7_snapshot
    assert second.p8_snapshot == first.p8_snapshot

    assert trade_service.get("r42-paper-trade") == trade_before
    assert portfolio_service.get(PORTFOLIO_ID) == portfolio_before
    assert len(trade_service.list_all()) == 1
    assert len(
        portfolio_before.portfolio_snapshot.reservations
    ) == 1
    assert len(
        portfolio_before.portfolio_snapshot.position_references
    ) == 1


def test_changed_entry_payload_fails_closed_without_mutation(
    tmp_path,
):
    args, portfolio_service, trade_service = (
        _admitted_runtime_args(tmp_path)
    )

    first = execute_admitted_plan_simulated_entry(**args)
    portfolio_before = portfolio_service.get(PORTFOLIO_ID)
    trade_before = trade_service.get("r42-paper-trade")

    with pytest.raises(
        ValueError,
        match="IDEMPOTENCY_PAYLOAD_CONFLICT",
    ):
        execute_admitted_plan_simulated_entry(
            **(
                args
                | {
                    "position_id": "changed-position",
                }
            )
        )

    assert trade_service.get("r42-paper-trade") == trade_before
    assert portfolio_service.get(PORTFOLIO_ID) == portfolio_before
    assert first.p8_snapshot == portfolio_before


def test_non_open_entry_does_not_persist_trade_or_activate_portfolio(
    tmp_path,
):
    args, portfolio_service, trade_service = (
        _admitted_runtime_args(tmp_path)
    )

    observation = replace(
        args["observation"],
        option_last_price=1.0,
        option_open=1.0,
        option_low=1.0,
        option_high=1.0,
        option_close=1.0,
    )

    before = portfolio_service.get(PORTFOLIO_ID)

    result = execute_admitted_plan_simulated_entry(
        **(
            args
            | {
                "observation": observation,
            }
        )
    )

    assert result.status == "WAITING_FOR_ENTRY"
    assert result.paper_action_occurred is False
    assert result.p7_snapshot is None
    assert trade_service.get("r42-paper-trade") is None
    assert portfolio_service.get(PORTFOLIO_ID) == before


def test_missing_persisted_r41_portfolio_is_rejected(tmp_path):
    args, _, trade_service = _admitted_runtime_args(tmp_path)

    empty_portfolio_service = PaperPortfolioPersistenceService(
        PaperPortfolioRepository(
            tmp_path / "empty-portfolio.json"
        )
    )

    with pytest.raises(
        ValueError,
        match="persisted R4.1 portfolio not found",
    ):
        execute_admitted_plan_simulated_entry(
            **(
                args
                | {
                    "portfolio_persistence_service": (
                        empty_portfolio_service
                    ),
                    "trade_persistence_service": trade_service,
                }
            )
        )


def test_submission_guard_rejects_before_entry(tmp_path):
    args, portfolio_service, trade_service = (
        _admitted_runtime_args(tmp_path)
    )

    before = portfolio_service.get(PORTFOLIO_ID)

    with pytest.raises(
        ValueError,
        match="order submission must remain disabled",
    ):
        execute_admitted_plan_simulated_entry(
            **args,
            broker_order_submission=True,
        )

    assert portfolio_service.get(PORTFOLIO_ID) == before
    assert trade_service.get("r42-paper-trade") is None