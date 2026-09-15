import pytest

from services.paper_orchestration.certified_runtime_composition import (
    build_default_automated_paper_authorities,
)
from services.trade_planning import task9_selected_market_p6_bundle as module


@pytest.mark.parametrize(
    ("runtime_risk", "expected"),
    ((0.005, 0.005), (0.01, 0.01), (0.02, 0.01)),
)
def test_runtime_risk_is_consumed_without_weakening_certified_ceiling(
    runtime_risk,
    expected,
):
    assert module._effective_task9_risk_fraction(runtime_risk) == expected
    assert module._MAXIMUM_RISK_FRACTION == 0.01


def test_runtime_maximum_quantity_fails_closed_below_one_lot():
    with pytest.raises(ValueError, match="maximum_quantity"):
        module._task9_quantity_lot_limit(
            maximum_quantity=49,
            lot_size=50,
        )


def test_runtime_maximum_quantity_caps_lots_without_weakening_certified_limit():
    assert module._task9_quantity_lot_limit(
        maximum_quantity=125,
        lot_size=50,
    ) == 2
    assert module._task9_quantity_lot_limit(
        maximum_quantity=500,
        lot_size=50,
    ) == 3
    assert module._MAXIMUM_CAPITAL_UTILIZATION_FRACTION == 0.80


def _portfolio_policy(*, capital, daily_loss_fraction=0.02):
    authorities = build_default_automated_paper_authorities(
        portfolio_id="task9104-test-portfolio",
        available_capital=capital,
        maximum_daily_loss_fraction=daily_loss_fraction,
    )
    return authorities.new_entry_input_factory.portfolio_policy_provider(
        type("Cycle", (), {
            "trading_day_id": "2026-08-17",
            "cycle_requested_at": __import__("datetime").datetime(
                2026, 8, 17, tzinfo=__import__("datetime").timezone.utc,
            ),
        })(),
        object(),
    )


@pytest.mark.parametrize(
    ("capital", "fraction", "expected"),
    ((10_000.0, 0.05, 500.0), (12_345.0, 0.05, 617.25)),
)
def test_task9_daily_loss_authority_sets_exact_entry_policy(
    capital,
    fraction,
    expected,
):
    policy = _portfolio_policy(
        capital=capital,
        daily_loss_fraction=fraction,
    )
    assert policy.maximum_daily_loss_amount == expected
    assert policy.maximum_daily_drawdown_amount == capital * 0.03
    assert policy.maximum_total_portfolio_risk_amount == capital * 0.10


def test_legacy_daily_loss_default_remains_two_percent():
    policy = _portfolio_policy(capital=10_000.0)
    assert policy.maximum_daily_loss_amount == 200.0


@pytest.mark.parametrize("value", (0, -0.01, 1.01, True, float("nan"), float("inf")))
def test_invalid_daily_loss_fraction_fails_closed(value):
    with pytest.raises(ValueError, match="maximum_daily_loss_fraction"):
        build_default_automated_paper_authorities(
            portfolio_id="task9104-invalid-daily-loss",
            available_capital=10_000.0,
            maximum_daily_loss_fraction=value,
        )
