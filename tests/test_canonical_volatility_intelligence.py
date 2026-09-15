from datetime import datetime, timedelta, timezone

import pytest

from services.contracts import (
    MarketCandleSeriesV1,
    MarketCandleV1,
    MarketDataProvenanceV1,
)
from services.technical_intelligence import (
    evaluate_volatility_intelligence,
)


N = datetime(2025, 1, 1, tzinfo=timezone.utc)
P = MarketDataProvenanceV1(
    "T",
    None,
    None,
    "TEST",
    N,
    N,
    False,
    None,
    None,
)


def series(
    n=40,
    symbol="NIFTY",
    exchange="NSE",
    incomplete=False,
    *,
    zero_volume=False,
):
    candles = tuple(
        MarketCandleV1(
            str(i),
            symbol,
            exchange,
            "5m",
            N + timedelta(minutes=5 * i),
            N + timedelta(minutes=5 * (i + 1)),
            100 + i,
            102 + i,
            99 + i,
            101 + i,
            0 if zero_volume else 100 + i,
            not (incomplete and i == n - 1),
            P,
        )
        for i in range(n)
    )

    return MarketCandleSeriesV1(
        "s",
        symbol,
        exchange,
        "5m",
        candles,
        None,
        None,
        N,
    )


@pytest.mark.parametrize(
    "symbol,exchange",
    [
        ("NIFTY", "NSE"),
        ("BANKNIFTY", "NSE"),
        ("FINNIFTY", "NSE"),
        ("SENSEX", "BSE"),
    ],
)
@pytest.mark.parametrize("n", range(25, 41))
def test_volatility_completed_series(symbol, exchange, n):
    result = evaluate_volatility_intelligence(
        series(n, symbol, exchange)
    )

    assert result["category"] == "VOLATILITY"
    assert 0 <= result["strength"] <= 1


@pytest.mark.parametrize("n", range(0, 20))
def test_volatility_insufficient_history_blocks(n):
    value = (
        series(n)
        if n
        else MarketCandleSeriesV1(
            "s",
            "NIFTY",
            "NSE",
            "5m",
            (),
            None,
            None,
            N,
            blockers=("empty",),
        )
    )

    result = evaluate_volatility_intelligence(value)

    assert result["bias"] == "UNAVAILABLE"


def test_incomplete_latest_is_excluded():
    assert (
        evaluate_volatility_intelligence(
            series(40, incomplete=True)
        )["bias"]
        ==
        evaluate_volatility_intelligence(
            series(39)
        )["bias"]
    )


def test_zero_volume_does_not_block_price_volatility():
    result = evaluate_volatility_intelligence(
        series(60, zero_volume=True)
    )

    indicators = {
        item.indicator_name: item
        for item in result["indicators"]
    }

    assert result["category"] == "VOLATILITY"
    assert result["bias"] == "NEUTRAL"
    assert result["strength"] > 0
    assert result["blockers"] == ()
    assert "volume_evidence_unavailable" in result["warnings"]

    assert indicators["ATR"].status == "VALID"
    assert indicators["BOLLINGER_WIDTH"].status == "VALID"

    assert indicators["VOLUME_AVERAGE"].status == "UNAVAILABLE"
    assert indicators["VWAP"].status == "UNAVAILABLE"

    assert (
        indicators["VOLUME_AVERAGE"].value
        is None
    )
    assert indicators["VWAP"].value is None


@pytest.mark.parametrize(
    "symbol,exchange",
    [
        ("NIFTY", "NSE"),
        ("SENSEX", "BSE"),
    ],
)
def test_task9_style_zero_volume_rows_preserve_price_evidence(
    symbol,
    exchange,
):
    result = evaluate_volatility_intelligence(
        series(
            80,
            symbol,
            exchange,
            zero_volume=True,
        )
    )

    valid = {
        item.indicator_name
        for item in result["indicators"]
        if item.status == "VALID"
    }
    unavailable = {
        item.indicator_name
        for item in result["indicators"]
        if item.status != "VALID"
    }

    assert {"ATR", "BOLLINGER_WIDTH"} <= valid
    assert unavailable == {
        "VOLUME_AVERAGE",
        "VWAP",
    }
    assert result["blockers"] == ()
