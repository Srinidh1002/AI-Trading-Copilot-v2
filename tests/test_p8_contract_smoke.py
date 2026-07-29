from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.contracts.paper_capital_reservation_v1 import PaperCapitalReservationV1
from services.contracts.paper_portfolio_exposure_v1 import PaperPortfolioExposureV1
from services.contracts.paper_portfolio_lock_state_v1 import PaperPortfolioLockStateV1
from services.contracts.paper_portfolio_policy_v1 import PaperPortfolioPolicyV1
from services.contracts.paper_portfolio_recovery_result_v1 import PaperPortfolioRecoveryResultV1


NOW = datetime(2026, 7, 30, 1, 0, tzinfo=timezone.utc)


def make_policy(**overrides):
    values = dict(
        portfolio_policy_id="policy-1",
        policy_timestamp=NOW,
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
    values.update(overrides)
    return PaperPortfolioPolicyV1(**values)


def test_policy_is_deterministic_and_paper_only():
    policy = make_policy(metadata={"z": 1, "a": [2, 3]})
    assert policy.execution_mode == "PAPER"
    assert policy.live_execution_eligible is False
    assert policy.to_json() == policy.to_json()
    assert list(policy.to_dict()["metadata"]) == ["a", "z"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("maximum_concurrent_trades", True),
        ("maximum_total_deployed_capital", float("nan")),
        ("maximum_instrument_risk_fraction", 1.1),
    ],
)
def test_policy_rejects_invalid_values(field, value):
    with pytest.raises((TypeError, ValueError)):
        make_policy(**{field: value})


def test_profit_lock_requires_threshold():
    with pytest.raises(ValueError):
        make_policy(profit_lock_enabled=True)


def test_pending_reservation_invariants():
    reservation = PaperCapitalReservationV1(
        reservation_id="reservation-1",
        portfolio_id="portfolio-1",
        admission_request_id="admission-1",
        admission_idempotency_key="key-1",
        integrated_trade_plan_result_id="integration-1",
        trade_plan_id="plan-1",
        reservation_status="PENDING_HOLD",
        original_capital_amount=20_000.0,
        remaining_capital_amount=20_000.0,
        released_capital_amount=0.0,
        original_risk_amount=2_000.0,
        remaining_risk_amount=2_000.0,
        initial_quantity=75,
        remaining_quantity=75,
        created_at=NOW,
        updated_at=NOW,
    )
    assert reservation.remaining_capital_amount == 20_000.0
    assert reservation.position_id is None


def test_reservation_rejects_unbalanced_capital():
    with pytest.raises(ValueError):
        PaperCapitalReservationV1(
            reservation_id="reservation-1",
            portfolio_id="portfolio-1",
            admission_request_id="admission-1",
            admission_idempotency_key="key-1",
            integrated_trade_plan_result_id="integration-1",
            trade_plan_id="plan-1",
            reservation_status="PENDING_HOLD",
            original_capital_amount=20_000.0,
            remaining_capital_amount=19_000.0,
            released_capital_amount=0.0,
            original_risk_amount=2_000.0,
            remaining_risk_amount=2_000.0,
            initial_quantity=75,
            remaining_quantity=75,
            created_at=NOW,
            updated_at=NOW,
        )


def test_empty_exposure_is_canonical():
    exposure = PaperPortfolioExposureV1.empty()
    assert exposure.total_instrument_risk == 0.0
    assert exposure.to_json() == exposure.to_json()


def test_exposure_rejects_wrong_total():
    with pytest.raises(ValueError):
        PaperPortfolioExposureV1(
            instrument_risk={"NIFTY|NSE": 100.0},
            direction_risk={},
            expiry_risk={},
            correlated_index_direction_risk={},
            total_instrument_risk=99.0,
            total_direction_risk=0.0,
            total_expiry_risk=0.0,
            total_correlated_index_direction_risk=0.0,
        )


def test_unlocked_lock_state():
    state = PaperPortfolioLockStateV1(
        trading_day_id="2026-07-30",
        loss_locked=False,
        profit_locked=False,
        lock_reason_codes=(),
        daily_total_pnl=0.0,
        daily_realized_net_pnl=0.0,
        daily_loss_amount=0.0,
        intraday_peak_equity=100_000.0,
        daily_drawdown_amount=0.0,
        evaluated_at=NOW,
    )
    assert state.admission_locked is False


def test_corrupt_recovery_never_exposes_snapshot():
    result = PaperPortfolioRecoveryResultV1(
        portfolio_id="portfolio-1",
        status="CORRUPT",
        recovered_at=NOW,
        reconciliation_codes=("INTEGRITY_MISMATCH",),
    )
    assert result.persistence_snapshot is None
