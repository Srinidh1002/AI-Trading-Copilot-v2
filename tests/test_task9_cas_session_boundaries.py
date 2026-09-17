from datetime import datetime, time

import pytest
from zoneinfo import ZoneInfo

from services.market_session import (
    validate_session_timestamp,
)
from services.market_session.policies import (
    BSE_SENSEX_POLICY,
    NSE_NIFTY_POLICY,
    MarketSessionPolicy,
)


IST = ZoneInfo("Asia/Kolkata")


@pytest.mark.parametrize(
    "policy",
    (
        NSE_NIFTY_POLICY,
        BSE_SENSEX_POLICY,
    ),
)
def test_derivative_session_policy_uses_cas_era_boundaries(
    policy,
):
    assert policy.regular_open == time(9, 15)
    assert policy.new_entry_cutoff == time(15, 20)
    assert policy.regular_close == time(15, 40)


@pytest.mark.parametrize(
    "symbol,exchange",
    (
        ("NIFTY", "NSE"),
        ("SENSEX", "BSE"),
    ),
)
def test_new_entry_allowed_at_exact_cutoff(
    symbol,
    exchange,
):
    now = datetime(
        2026,
        8,
        10,
        15,
        20,
        tzinfo=IST,
    )

    result = validate_session_timestamp(
        symbol=symbol,
        exchange=exchange,
        market_timestamp=now,
        evaluated_at=now,
    )

    assert result.session_state == "REGULAR"
    assert result.analysis_allowed is True
    assert result.paper_preparation_allowed is True
    assert result.paper_execution_allowed is True
    assert (
        result.metadata[
            "regular_new_entry_window_open"
        ]
        is True
    )


@pytest.mark.parametrize(
    "symbol,exchange",
    (
        ("NIFTY", "NSE"),
        ("SENSEX", "BSE"),
    ),
)
def test_after_cutoff_analysis_continues_but_new_entry_is_blocked(
    symbol,
    exchange,
):
    now = datetime(
        2026,
        8,
        10,
        15,
        20,
        1,
        tzinfo=IST,
    )

    result = validate_session_timestamp(
        symbol=symbol,
        exchange=exchange,
        market_timestamp=now,
        evaluated_at=now,
    )

    assert result.session_state == "REGULAR"
    assert result.analysis_allowed is True
    assert result.paper_preparation_allowed is True
    assert result.paper_execution_allowed is False
    assert (
        "New PAPER entries are closed "
        "after the session entry cutoff."
        in result.warnings
    )


@pytest.mark.parametrize(
    "symbol,exchange",
    (
        ("NIFTY", "NSE"),
        ("SENSEX", "BSE"),
    ),
)
def test_position_monitoring_window_remains_regular_until_1540(
    symbol,
    exchange,
):
    now = datetime(
        2026,
        8,
        10,
        15,
        39,
        59,
        tzinfo=IST,
    )

    result = validate_session_timestamp(
        symbol=symbol,
        exchange=exchange,
        market_timestamp=now,
        evaluated_at=now,
    )

    assert result.session_state == "REGULAR"
    assert result.analysis_allowed is True
    assert result.paper_execution_allowed is False


@pytest.mark.parametrize(
    "symbol,exchange",
    (
        ("NIFTY", "NSE"),
        ("SENSEX", "BSE"),
    ),
)
def test_exact_1540_is_still_session_boundary(
    symbol,
    exchange,
):
    now = datetime(
        2026,
        8,
        10,
        15,
        40,
        tzinfo=IST,
    )

    result = validate_session_timestamp(
        symbol=symbol,
        exchange=exchange,
        market_timestamp=now,
        evaluated_at=now,
    )

    assert result.session_state == "REGULAR"
    assert result.analysis_allowed is True
    assert result.paper_execution_allowed is False


@pytest.mark.parametrize(
    "symbol,exchange",
    (
        ("NIFTY", "NSE"),
        ("SENSEX", "BSE"),
    ),
)
def test_after_1540_session_is_closed(
    symbol,
    exchange,
):
    now = datetime(
        2026,
        8,
        10,
        15,
        40,
        1,
        tzinfo=IST,
    )

    result = validate_session_timestamp(
        symbol=symbol,
        exchange=exchange,
        market_timestamp=now,
        evaluated_at=now,
    )

    assert result.session_state == "POST_CLOSE"
    assert result.analysis_allowed is False
    assert result.paper_execution_allowed is False


def test_policy_rejects_entry_cutoff_after_session_close():
    with pytest.raises(ValueError):
        MarketSessionPolicy(
            new_entry_cutoff=time(15, 41),
            regular_close=time(15, 40),
        )


def test_policy_rejects_entry_cutoff_at_regular_open():
    with pytest.raises(ValueError):
        MarketSessionPolicy(
            regular_open=time(9, 15),
            new_entry_cutoff=time(9, 15),
        )


def test_session_metadata_publishes_entry_and_close_boundaries():
    now = datetime(
        2026,
        8,
        10,
        12,
        0,
        tzinfo=IST,
    )

    result = validate_session_timestamp(
        symbol="NIFTY",
        exchange="NSE",
        market_timestamp=now,
        evaluated_at=now,
    )

    assert (
        result.metadata[
            "new_entry_cutoff"
        ]
        == "15:20"
    )

    assert (
        result.metadata[
            "regular_close"
        ]
        == "15:40"
    )
