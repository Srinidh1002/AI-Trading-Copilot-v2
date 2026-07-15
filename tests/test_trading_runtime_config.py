from dataclasses import FrozenInstanceError

import pytest

from services.trading_runtime_config import (
    DEFAULT_CAPITAL,
    DEFAULT_PAPER_TRADING,
    DEFAULT_RISK_PER_TRADE_PERCENT,
    DEFAULT_TRADING_MODE,
    DEFAULT_UNDERLYING,
    TradingRuntimeConfig,
    build_trading_runtime_config,
)


def test_default_configuration_preserves_live_behavior():
    config = TradingRuntimeConfig()

    assert config.capital == DEFAULT_CAPITAL
    assert (
        config.risk_per_trade_percent
        == DEFAULT_RISK_PER_TRADE_PERCENT
    )
    assert config.underlying == DEFAULT_UNDERLYING
    assert config.trading_mode == DEFAULT_TRADING_MODE
    assert (
        config.paper_trading
        is DEFAULT_PAPER_TRADING
    )


def test_default_configuration_matches_current_live_values():
    config = TradingRuntimeConfig()

    assert config.capital == 10_000.0
    assert config.risk_per_trade_percent == 1.0
    assert config.underlying == "NIFTY"


def test_capital_is_normalized_to_float():
    config = TradingRuntimeConfig(
        capital=50_000
    )

    assert config.capital == 50_000.0


def test_numeric_string_capital_is_normalized():
    config = TradingRuntimeConfig(
        capital="50000"
    )

    assert config.capital == 50_000.0


@pytest.mark.parametrize(
    "capital",
    [
        0,
        -1,
        -10_000,
    ],
)
def test_non_positive_capital_is_rejected(capital):
    with pytest.raises(
        ValueError,
        match="capital must be greater than zero",
    ):
        TradingRuntimeConfig(
            capital=capital
        )


@pytest.mark.parametrize(
    "capital",
    [
        None,
        "",
        "invalid",
        [],
        {},
        True,
        False,
    ],
)
def test_invalid_capital_is_rejected(capital):
    with pytest.raises(ValueError):
        TradingRuntimeConfig(
            capital=capital
        )


def test_risk_percent_is_normalized_to_float():
    config = TradingRuntimeConfig(
        risk_per_trade_percent=2
    )

    assert config.risk_per_trade_percent == 2.0


def test_numeric_string_risk_is_normalized():
    config = TradingRuntimeConfig(
        risk_per_trade_percent="1.5"
    )

    assert config.risk_per_trade_percent == 1.5


@pytest.mark.parametrize(
    "risk_percent",
    [
        0,
        -1,
        -10,
    ],
)
def test_non_positive_risk_is_rejected(
    risk_percent,
):
    with pytest.raises(
        ValueError,
        match=(
            "risk_per_trade_percent must be greater "
            "than zero"
        ),
    ):
        TradingRuntimeConfig(
            risk_per_trade_percent=risk_percent
        )


@pytest.mark.parametrize(
    "risk_percent",
    [
        100.1,
        101,
        500,
    ],
)
def test_risk_above_100_is_rejected(
    risk_percent,
):
    with pytest.raises(
        ValueError,
        match=(
            "risk_per_trade_percent must not exceed 100"
        ),
    ):
        TradingRuntimeConfig(
            risk_per_trade_percent=risk_percent
        )


@pytest.mark.parametrize(
    "risk_percent",
    [
        None,
        "",
        "invalid",
        [],
        {},
        True,
        False,
    ],
)
def test_invalid_risk_is_rejected(
    risk_percent,
):
    with pytest.raises(ValueError):
        TradingRuntimeConfig(
            risk_per_trade_percent=risk_percent
        )


def test_underlying_is_normalized():
    config = TradingRuntimeConfig(
        underlying=" nifty "
    )

    assert config.underlying == "NIFTY"


@pytest.mark.parametrize(
    "underlying",
    [
        "",
        " ",
        "\t",
        "\n",
    ],
)
def test_empty_underlying_is_rejected(
    underlying,
):
    with pytest.raises(
        ValueError,
        match="underlying cannot be empty",
    ):
        TradingRuntimeConfig(
            underlying=underlying
        )


@pytest.mark.parametrize(
    "underlying",
    [
        None,
        123,
        True,
        [],
        {},
    ],
)
def test_non_string_underlying_is_rejected(
    underlying,
):
    with pytest.raises(
        ValueError,
        match="underlying must be a string",
    ):
        TradingRuntimeConfig(
            underlying=underlying
        )


def test_trading_mode_is_normalized():
    config = TradingRuntimeConfig(
        trading_mode=" paper "
    )

    assert config.trading_mode == "PAPER"


def test_research_mode_is_supported():
    config = TradingRuntimeConfig(
        trading_mode="research"
    )

    assert config.trading_mode == "RESEARCH"


@pytest.mark.parametrize(
    "trading_mode",
    [
        "",
        "LIVE",
        "REAL",
        "BROKER",
        "EXECUTION",
    ],
)
def test_unsupported_trading_mode_is_rejected(
    trading_mode,
):
    with pytest.raises(
        ValueError,
        match="unsupported trading_mode",
    ):
        TradingRuntimeConfig(
            trading_mode=trading_mode
        )


@pytest.mark.parametrize(
    "paper_trading",
    [
        None,
        0,
        1,
        "true",
        "false",
        [],
        {},
    ],
)
def test_non_boolean_paper_trading_is_rejected(
    paper_trading,
):
    with pytest.raises(
        ValueError,
        match="paper_trading must be a boolean",
    ):
        TradingRuntimeConfig(
            paper_trading=paper_trading
        )


def test_risk_budget_uses_capital_and_risk_percent():
    config = TradingRuntimeConfig(
        capital=50_000,
        risk_per_trade_percent=2.0,
    )

    assert config.risk_budget == 1_000.0


def test_default_risk_budget_matches_current_live_behavior():
    config = TradingRuntimeConfig()

    assert config.risk_budget == 100.0


def test_real_orders_are_never_allowed():
    config = TradingRuntimeConfig()

    assert config.real_orders_allowed is False


def test_configuration_is_immutable():
    config = TradingRuntimeConfig()

    with pytest.raises(FrozenInstanceError):
        config.capital = 50_000


def test_to_dict_returns_runtime_snapshot():
    config = TradingRuntimeConfig(
        capital=50_000,
        risk_per_trade_percent=2.0,
        underlying="nifty",
        trading_mode="paper",
        paper_trading=True,
    )

    result = config.to_dict()

    assert result == {
        "capital": 50_000.0,
        "risk_per_trade_percent": 2.0,
        "risk_budget": 1_000.0,
        "underlying": "NIFTY",
        "trading_mode": "PAPER",
        "paper_trading": True,
        "real_orders_allowed": False,
    }


def test_to_dict_result_is_independent():
    config = TradingRuntimeConfig()

    first = config.to_dict()
    first["capital"] = 999_999

    second = config.to_dict()

    assert second["capital"] == 10_000.0


def test_builder_returns_validated_configuration():
    config = build_trading_runtime_config(
        capital=75_000,
        risk_per_trade_percent=1.5,
        underlying=" nifty ",
        trading_mode=" paper ",
        paper_trading=True,
    )

    assert isinstance(
        config,
        TradingRuntimeConfig,
    )

    assert config.capital == 75_000.0
    assert config.risk_per_trade_percent == 1.5
    assert config.risk_budget == 1_125.0
    assert config.underlying == "NIFTY"
    assert config.trading_mode == "PAPER"
    assert config.paper_trading is True


def test_different_capital_changes_risk_budget():
    small = TradingRuntimeConfig(
        capital=10_000,
        risk_per_trade_percent=1.0,
    )

    large = TradingRuntimeConfig(
        capital=50_000,
        risk_per_trade_percent=1.0,
    )

    assert small.risk_budget == 100.0
    assert large.risk_budget == 500.0


def test_different_risk_percent_changes_risk_budget():
    conservative = TradingRuntimeConfig(
        capital=50_000,
        risk_per_trade_percent=1.0,
    )

    aggressive = TradingRuntimeConfig(
        capital=50_000,
        risk_per_trade_percent=2.0,
    )

    assert conservative.risk_budget == 500.0
    assert aggressive.risk_budget == 1_000.0