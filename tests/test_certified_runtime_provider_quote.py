from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from services.paper_orchestration import (
    certified_runtime_composition as runtime,
)


NOW = datetime(
    2026,
    8,
    3,
    10,
    0,
    tzinfo=timezone.utc,
)


def install_client(
    monkeypatch,
    *,
    timestamp,
    field="exchFeedTime",
):
    row = {
        "ltp": 25000.0,
        "tradingsymbol": "NIFTY",
        "exchange": "NSE",
        "symboltoken": "99926000",
        field: timestamp,
    }

    client = MagicMock()

    client.get_ltp.return_value = {
        "status": True,
        "data": row,
    }

    monkeypatch.setattr(
        runtime,
        "get_certification_market_client",
        lambda: client,
    )

    monkeypatch.setattr(
        runtime,
        "_aware_now",
        lambda: NOW,
    )

    return client


def read_quote():
    return runtime._provider_ltp_reader(
        "NSE",
        "99926000",
        "NIFTY",
    )


def test_provider_ltp_reader_uses_exchange_timestamp(
    monkeypatch,
):
    client = install_client(
        monkeypatch,
        timestamp="03-Aug-2026 15:29:30",
    )

    result = read_quote()

    assert result["spot_price"] == 25000.0
    assert result["ltp"] == 25000.0
    assert result["received_at"] == NOW
    assert (
        result["market_timestamp"]
        == datetime(
            2026,
            8,
            3,
            15,
            29,
            30,
            tzinfo=runtime.IST,
        )
    )
    assert (
        result["timestamp_source"]
        == "ANGEL_PROVIDER_EXCHFEEDTIME"
    )
    assert (
        result["provider_timestamp_field"]
        == "exchFeedTime"
    )
    assert result["quote_age_seconds"] == 30.0

    client.get_ltp.assert_called_once_with(
        exchange="NSE",
        tradingsymbol="NIFTY",
        symboltoken="99926000",
    )


@pytest.mark.parametrize(
    "field",
    [
        "exchFeedTime",
        "exchangeTimestamp",
        "timestamp",
    ],
)
def test_supported_provider_timestamp_fields(
    monkeypatch,
    field,
):
    install_client(
        monkeypatch,
        timestamp=(
            NOW
            - timedelta(seconds=1)
        ).isoformat(),
        field=field,
    )

    result = read_quote()

    assert (
        result["provider_timestamp_field"]
        == field
    )
    assert result["quote_age_seconds"] == 1.0


def test_epoch_milliseconds_are_supported(
    monkeypatch,
):
    timestamp = int(
        (
            NOW
            - timedelta(seconds=2)
        ).timestamp()
        * 1000
    )

    install_client(
        monkeypatch,
        timestamp=timestamp,
    )

    result = read_quote()

    assert result["quote_age_seconds"] == 2.0


def test_missing_provider_timestamp_fails_closed(
    monkeypatch,
):
    client = MagicMock()

    client.get_ltp.return_value = {
        "status": True,
        "data": {
            "ltp": 25000.0,
            "tradingsymbol": "NIFTY",
            "exchange": "NSE",
            "symboltoken": "99926000",
        },
    }

    monkeypatch.setattr(
        runtime,
        "get_certification_market_client",
        lambda: client,
    )

    monkeypatch.setattr(
        runtime,
        "_aware_now",
        lambda: NOW,
    )

    with pytest.raises(
        ValueError,
        match="timestamp is missing",
    ):
        read_quote()


@pytest.mark.parametrize(
    "timestamp",
    [
        "bad",
        "",
        None,
        True,
        float("nan"),
    ],
)
def test_invalid_provider_timestamp_fails_closed(
    monkeypatch,
    timestamp,
):
    install_client(
        monkeypatch,
        timestamp=timestamp,
    )

    with pytest.raises(
        ValueError,
        match="timestamp",
    ):
        read_quote()


def test_naive_iso_timestamp_is_rejected(
    monkeypatch,
):
    install_client(
        monkeypatch,
        timestamp="2026-08-03T09:59:30",
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        read_quote()


def test_stale_provider_timestamp_fails_closed(
    monkeypatch,
):
    install_client(
        monkeypatch,
        timestamp=(
            NOW
            - timedelta(seconds=301)
        ).isoformat(),
    )

    with pytest.raises(
        ValueError,
        match="stale",
    ):
        read_quote()


def test_future_provider_timestamp_fails_closed(
    monkeypatch,
):
    install_client(
        monkeypatch,
        timestamp=(
            NOW
            + timedelta(seconds=6)
        ).isoformat(),
    )

    with pytest.raises(
        ValueError,
        match="future skew",
    ):
        read_quote()


def test_freshness_boundaries_are_inclusive(
    monkeypatch,
):
    install_client(
        monkeypatch,
        timestamp=(
            NOW
            - timedelta(seconds=300)
        ).isoformat(),
    )

    stale_boundary = read_quote()

    assert (
        stale_boundary["quote_age_seconds"]
        == 300.0
    )

    install_client(
        monkeypatch,
        timestamp=(
            NOW
            + timedelta(seconds=5)
        ).isoformat(),
    )

    future_boundary = read_quote()

    assert (
        future_boundary["quote_age_seconds"]
        == -5.0
    )


def test_false_provider_status_fails_closed(
    monkeypatch,
):
    client = MagicMock()

    client.get_ltp.return_value = {
        "status": False,
        "data": {
            "ltp": 25000.0,
            "tradingsymbol": "NIFTY",
            "exchange": "NSE",
            "symboltoken": "99926000",
            "exchFeedTime": (
                "03-Aug-2026 15:29:30"
            ),
        },
    }

    monkeypatch.setattr(
        runtime,
        "get_certification_market_client",
        lambda: client,
    )

    with pytest.raises(
        ValueError,
        match="status must be true",
    ):
        read_quote()


@pytest.mark.parametrize(
    "field",
    [
        "exchange",
        "tradingsymbol",
        "symboltoken",
    ],
)
def test_missing_provider_identity_fails_closed(
    monkeypatch,
    field,
):
    install_client(
        monkeypatch,
        timestamp="03-Aug-2026 15:29:30",
    )

    client = runtime.get_certification_market_client()
    del client.get_ltp.return_value[
        "data"
    ][field]

    with pytest.raises(
        ValueError,
        match="missing",
    ):
        read_quote()


@pytest.mark.parametrize(
    "field,value,match",
    [
        (
            "exchange",
            "BSE",
            "exchange does not match",
        ),
        (
            "tradingsymbol",
            "SENSEX",
            "trading symbol does not match",
        ),
        (
            "symboltoken",
            "99919000",
            "symbol token does not match",
        ),
    ],
)
def test_mismatched_provider_identity_fails_closed(
    monkeypatch,
    field,
    value,
    match,
):
    install_client(
        monkeypatch,
        timestamp="03-Aug-2026 15:29:30",
    )

    client = runtime.get_certification_market_client()

    client.get_ltp.return_value[
        "data"
    ][field] = value

    with pytest.raises(
        ValueError,
        match=match,
    ):
        read_quote()


def test_provider_identity_aliases_are_supported(
    monkeypatch,
):
    client = MagicMock()

    client.get_ltp.return_value = {
        "status": True,
        "data": {
            "ltp": 25000.0,
            "tradingSymbol": "NIFTY",
            "exchange": "NSE",
            "symbolToken": "99926000",
            "exchFeedTime": (
                "03-Aug-2026 15:29:30"
            ),
        },
    }

    monkeypatch.setattr(
        runtime,
        "get_certification_market_client",
        lambda: client,
    )

    monkeypatch.setattr(
        runtime,
        "_aware_now",
        lambda: NOW,
    )

    result = read_quote()

    assert result["spot_price"] == 25000.0
    assert result["quote_age_seconds"] == 30.0
