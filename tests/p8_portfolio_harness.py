"""Reusable real-contract P8 harness built on certified P7 fixtures."""
from __future__ import annotations

from dataclasses import replace

from services.contracts.paper_portfolio_persistence_snapshot_v1 import (
    PaperPortfolioPersistenceSnapshotV1,
)
from services.contracts.paper_portfolio_policy_v1 import PaperPortfolioPolicyV1
from services.contracts.paper_trade_persistence_snapshot_v1 import (
    PaperTradePersistenceSnapshotV1,
)
from services.paper_portfolio import aggregate_paper_portfolio
from services.paper_portfolio.paper_capital_reservation_manager import (
    reserve_pending_paper_capital,
)
from services.paper_portfolio.paper_portfolio_persistence_service import (
    PaperPortfolioPersistenceService,
)
from services.paper_portfolio_repository import PaperPortfolioRepository
from tests.p7_fixture_helpers import (
    NOW,
    make_integrated,
    make_observation,
    make_open_position,
    make_open_state,
    make_policy as make_p7_policy,
)

PORTFOLIO_ID = "portfolio-1"
TRADING_DAY_ID = "2026-01-08"
P8_NOW = NOW


def make_cost_complete_integrated():
    """Upgrade the legacy P7 fixture with explicit P6 total-capital evidence."""
    plan = make_integrated()
    capital = plan.capital_quantity_result
    total_cost = (
        0.0
        if capital.estimated_total_trading_cost is None
        else capital.estimated_total_trading_cost
    )
    total_requirement = (
        capital.estimated_premium_outlay + total_cost
        if capital.estimated_total_capital_requirement is None
        else capital.estimated_total_capital_requirement
    )
    capital = replace(
        capital,
        trading_cost_policy_id=(
            capital.trading_cost_policy_id or "fixture-cost-policy-1"
        ),
        trading_cost_evidence_id=(
            capital.trading_cost_evidence_id or "fixture-cost-evidence-1"
        ),
        trading_cost_calculation_mode=(
            capital.trading_cost_calculation_mode or "FIXTURE_ZERO_COST"
        ),
        estimated_brokerage=capital.estimated_brokerage or 0.0,
        estimated_exchange_transaction_charges=(
            capital.estimated_exchange_transaction_charges or 0.0
        ),
        estimated_clearing_charges=capital.estimated_clearing_charges or 0.0,
        estimated_stt=capital.estimated_stt or 0.0,
        estimated_sebi_charges=capital.estimated_sebi_charges or 0.0,
        estimated_stamp_duty=capital.estimated_stamp_duty or 0.0,
        estimated_gst=capital.estimated_gst or 0.0,
        estimated_slippage=capital.estimated_slippage or 0.0,
        estimated_total_trading_cost=total_cost,
        estimated_total_capital_requirement=total_requirement,
        cost_adjusted_capital_feasible=True,
    )
    return replace(plan, capital_quantity_result=capital)


def make_p8_policy(**changes):
    values = dict(
        portfolio_policy_id="p8-policy-1",
        policy_timestamp=P8_NOW,
        maximum_concurrent_trades=3,
        maximum_total_deployed_capital=100_000.0,
        maximum_total_portfolio_risk_amount=10_000.0,
        maximum_daily_loss_amount=2_000.0,
        maximum_daily_drawdown_amount=3_000.0,
        maximum_instrument_risk_fraction=0.75,
        maximum_direction_risk_fraction=0.75,
        maximum_correlated_index_risk_fraction=0.60,
        maximum_expiry_risk_fraction=0.60,
        minimum_available_cash_reserve=10_000.0,
    )
    values.update(changes)
    return PaperPortfolioPolicyV1(**values)


def make_pending_reservation():
    plan = make_cost_complete_integrated()
    capital = plan.capital_quantity_result
    return reserve_pending_paper_capital(
        reservation_id="reservation-1",
        portfolio_id=PORTFOLIO_ID,
        admission_request_id="admission-1",
        admission_idempotency_key="admission-key-1",
        integrated_trade_plan_result_id=plan.integration_id,
        trade_plan_id=capital.trade_plan_id,
        capital_amount=capital.estimated_total_capital_requirement,
        risk_amount=capital.estimated_risk_amount,
        initial_quantity=capital.planned_quantity,
        created_at=P8_NOW,
    )


def make_initial_p8_snapshot(*, policy=None):
    policy = policy or make_p8_policy()
    reservation = make_pending_reservation()
    return aggregate_paper_portfolio(
        portfolio_snapshot_id="p8-snapshot-1",
        portfolio_id=PORTFOLIO_ID,
        policy=policy,
        trading_day_id=TRADING_DAY_ID,
        starting_capital=100_000.0,
        reservations=(reservation,),
        position_references=(),
        event_sequence=1,
        created_at=P8_NOW,
        updated_at=P8_NOW,
    )


def make_initial_p8_persistence(*, policy=None):
    snapshot = make_initial_p8_snapshot(policy=policy)
    return PaperPortfolioPersistenceSnapshotV1(
        portfolio_id=PORTFOLIO_ID,
        portfolio_snapshot=snapshot,
        admission_idempotency_records={"admission-key-1": "admission-hash-1"},
        update_idempotency_records={},
        processed_portfolio_event_hashes={
            "admission-event-1": "admission-event-hash-1"
        },
        processed_p7_transition_hashes={},
        processed_p7_fill_hashes={},
        created_at=P8_NOW,
        updated_at=P8_NOW,
        event_sequence=1,
    )


def make_persistence_service(tmp_path):
    repository = PaperPortfolioRepository(tmp_path / "p8-portfolio.json")
    service = PaperPortfolioPersistenceService(repository)
    service.save(make_initial_p8_persistence())
    return service


def make_open_p7_snapshot():
    position = make_open_position()
    state = make_open_state()
    return PaperTradePersistenceSnapshotV1(
        paper_trade_id="paper-trade-1",
        adapter_idempotency_key="p7-entry-key-1",
        idempotency_payload_hash="p7-entry-hash-1",
        lifecycle_policy=make_p7_policy(allow_partial_exits=True),
        lifecycle_state=state,
        position=position,
        latest_observation=make_observation(
            option_open=100.0,
            option_low=99.0,
            option_high=101.0,
            option_close=100.0,
        ),
        pnl_evidence=None,
        created_at=NOW,
        updated_at=NOW,
        event_sequence=1,
    )


def make_position_update_result(
    *,
    option_price: float,
    result_id: str,
    transition_id: str,
):
    from services.contracts.paper_trade_position_evaluation_input_v1 import (
        PaperTradePositionEvaluationInputV1,
    )
    from services.paper_trading import evaluate_open_paper_trade_position

    observation = make_observation(
        observation_id=f"obs-{result_id}",
        option_last_price=option_price,
        option_open=option_price,
        option_low=option_price - 1.0,
        option_high=option_price + 1.0,
        option_close=option_price,
    )
    evaluation_input = PaperTradePositionEvaluationInputV1(
        make_open_position(),
        make_p7_policy(allow_partial_exits=True),
        make_open_state(),
        observation,
        NOW,
        transition_id,
        f"state-{result_id}",
        result_id,
        (
            f"exit-{result_id}-1",
            f"exit-{result_id}-2",
            f"exit-{result_id}-3",
        ),
        f"pnl-{result_id}",
    )
    return evaluation_input, evaluate_open_paper_trade_position(evaluation_input)


def make_p7_snapshot_from_result(
    *,
    result,
    observation,
    paper_trade_id: str,
    key: str,
    payload_hash: str,
    event_sequence: int,
):
    return PaperTradePersistenceSnapshotV1(
        paper_trade_id=paper_trade_id,
        adapter_idempotency_key=key,
        idempotency_payload_hash=payload_hash,
        lifecycle_policy=make_p7_policy(allow_partial_exits=True),
        lifecycle_state=result.resulting_lifecycle_state,
        position=result.resulting_position,
        latest_observation=observation,
        pnl_evidence=result.pnl_evidence,
        created_at=NOW,
        updated_at=NOW,
        event_sequence=event_sequence,
    )
