import sys

import pandas as pd

sys.path.insert(0, "src")

import market_intelligence as market_intelligence_module
from market_intelligence import MarketIntelligence
from decision_composer import DecisionComposer


def _frame(start=100.0, step=1.0, rows=60):
    close = [
        start + (step * i)
        for i in range(rows)
    ]

    return pd.DataFrame(
        {
            "close": close,
            "high": [x + 1.0 for x in close],
            "low": [x - 1.0 for x in close],
        }
    )


def _market_intelligence(monkeypatch, five_minute):
    assert market_intelligence_module.TA_AVAILABLE is True

    obj = object.__new__(MarketIntelligence)

    obj._cache = {}
    obj._cache_time = {}

    obj.cache_ttl = {
        "technicals": 600,
    }

    frames = {
        "ONE_HOUR": _frame(
            start=100.0,
            step=1.0,
        ),
        "FIFTEEN_MINUTE": _frame(
            start=200.0,
            step=1.0,
        ),
        "FIVE_MINUTE": five_minute,
    }

    calls = []

    def fake_get_candles(
        interval,
        days_back=3,
    ):
        calls.append(
            (interval, days_back)
        )

        return frames[interval].copy()

    monkeypatch.setattr(
        obj,
        "get_candles",
        fake_get_candles,
    )

    return obj, frames, calls


def test_partial_required_mtf_is_insufficient_and_not_cached(
    monkeypatch,
):
    obj, _frames, calls = _market_intelligence(
        monkeypatch,
        pd.DataFrame(),
    )

    result = obj.get_multi_timeframe_technicals()

    assert result["1h"]["trend"] in (
        "UP",
        "DOWN",
        "FLAT",
    )

    assert result["15m"]["trend"] in (
        "UP",
        "DOWN",
        "FLAT",
    )

    assert result["5m"]["trend"] == "UNKNOWN"

    assert (
        result["consensus"]
        == "INSUFFICIENT_DATA"
    )

    assert "technicals" not in obj._cache

    assert [
        x[0]
        for x in calls
    ] == [
        "ONE_HOUR",
        "FIFTEEN_MINUTE",
        "FIVE_MINUTE",
    ]


def test_recovered_five_minute_recomputes_and_becomes_cacheable(
    monkeypatch,
):
    obj, frames, calls = _market_intelligence(
        monkeypatch,
        pd.DataFrame(),
    )

    first = obj.get_multi_timeframe_technicals()

    assert (
        first["consensus"]
        == "INSUFFICIENT_DATA"
    )

    assert "technicals" not in obj._cache

    frames["FIVE_MINUTE"] = _frame(
        start=300.0,
        step=1.0,
    )

    calls.clear()

    second = obj.get_multi_timeframe_technicals()

    assert second["5m"]["trend"] in (
        "UP",
        "DOWN",
        "FLAT",
    )

    assert second["consensus"] != "INSUFFICIENT_DATA"

    assert "technicals" in obj._cache

    # Proves the incomplete aggregate was not served from cache.
    assert [
        x[0]
        for x in calls
    ] == [
        "ONE_HOUR",
        "FIFTEEN_MINUTE",
        "FIVE_MINUTE",
    ]


def _decision_context(technical_data_ok):
    return {
        "market_identity_ok": True,
        "session_state": {
            "phase": "CONTINUOUS",
            "can_enter": True,
        },
        "spot_freshness": "FRESH",
        "option_freshness": "FRESH",
        "contract_metadata_ok": True,
        "expiry_validity_ok": True,
        "bull_score": 5.0,
        "bear_score": 0.5,
        "bull_pillars": 5,
        "bear_pillars": 0,
        "technical_data_ok": technical_data_ok,
        "event_block": False,
    }


def test_incomplete_mtf_fails_closed_at_decision_composer():
    result = DecisionComposer().compose(
        _decision_context(
            technical_data_ok=False
        )
    )

    assert result["action"] == "WAIT"
    assert result["readiness"] == "WAIT"

    assert (
        "TECHNICAL_MTF_INSUFFICIENT_DATA"
        in result["blockers"]
    )


def test_complete_mtf_remains_entry_eligible():
    result = DecisionComposer().compose(
        _decision_context(
            technical_data_ok=True
        )
    )

    assert result["action"] == "BUY_CALL"
    assert result["readiness"] == "READY"
