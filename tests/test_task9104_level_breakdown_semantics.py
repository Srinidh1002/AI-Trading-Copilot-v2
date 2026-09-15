from datetime import (
    datetime,
    timedelta,
    timezone,
)

from services.contracts import (
    MarketCandleSeriesV1,
    MarketCandleV1,
    MarketDataProvenanceV1,
)

from services.technical_intelligence import (
    evaluate_level_intelligence,
)


NOW = datetime(
    2026,
    8,
    22,
    tzinfo=timezone.utc,
)

PROVENANCE = MarketDataProvenanceV1(
    "TASK9104_LEVEL_TEST",
    None,
    None,
    "TEST",
    NOW,
    NOW,
    False,
    None,
    None,
)


def _candle(
    index,
    *,
    open_price,
    high_price,
    low_price,
    close_price,
):
    opened_at = (
        NOW
        + timedelta(
            minutes=5 * index
        )
    )

    closed_at = (
        opened_at
        + timedelta(minutes=5)
    )

    return MarketCandleV1(
        str(index),
        "NIFTY",
        "NSE",
        "5m",
        opened_at,
        closed_at,
        float(open_price),
        float(high_price),
        float(low_price),
        float(close_price),
        100.0,
        True,
        PROVENANCE,
    )


def _series(
    *,
    final_open,
    final_high,
    final_low,
    final_close,
):
    # Twenty prior completed candles.
    #
    # Prior support = 99
    # Prior resistance = 120
    prior = tuple(
        _candle(
            i,
            open_price=100 + i,
            high_price=101 + i,
            low_price=99 + i,
            close_price=100.5 + i,
        )
        for i in range(20)
    )

    final = _candle(
        20,
        open_price=final_open,
        high_price=final_high,
        low_price=final_low,
        close_price=final_close,
    )

    return MarketCandleSeriesV1(
        "task9104-level-series",
        "NIFTY",
        "NSE",
        "5m",
        prior + (final,),
        None,
        None,
        NOW,
    )


def _indicators(result):
    return {
        item.indicator_name: item
        for item in result["indicators"]
    }


def test_true_breakdown_is_bearish_not_near_support():
    value = evaluate_level_intelligence(
        _series(
            final_open=100,
            final_high=101,
            final_low=89,
            final_close=90,
        )
    )

    indicators = _indicators(value)

    assert value["bias"] == "BEARISH"
    assert value["strength"] == 1.0

    assert (
        indicators["SUPPORT"].signal
        == "NONE"
    )


def test_true_breakout_is_bullish_not_near_resistance():
    value = evaluate_level_intelligence(
        _series(
            final_open=119,
            final_high=126,
            final_low=118,
            final_close=125,
        )
    )

    indicators = _indicators(value)

    assert value["bias"] == "BULLISH"
    assert value["strength"] == 1.0

    assert (
        indicators["RESISTANCE"].signal
        == "NONE"
    )


def test_price_just_above_support_remains_near_support():
    value = evaluate_level_intelligence(
        _series(
            final_open=101,
            final_high=102,
            final_low=99,
            final_close=100,
        )
    )

    indicators = _indicators(value)

    assert value["bias"] == "BULLISH"
    assert value["strength"] == 0.5

    assert (
        indicators["SUPPORT"].signal
        == "LOW"
    )


def test_price_just_below_resistance_remains_near_resistance():
    value = evaluate_level_intelligence(
        _series(
            final_open=118,
            final_high=120,
            final_low=117,
            final_close=119,
        )
    )

    indicators = _indicators(value)

    assert value["bias"] == "BEARISH"
    assert value["strength"] == 0.5

    assert (
        indicators["RESISTANCE"].signal
        == "HIGH"
    )


def test_inside_range_away_from_boundaries_remains_neutral():
    value = evaluate_level_intelligence(
        _series(
            final_open=109,
            final_high=111,
            final_low=108,
            final_close=110,
        )
    )

    assert value["bias"] == "NEUTRAL"
    assert value["strength"] == 0.0
