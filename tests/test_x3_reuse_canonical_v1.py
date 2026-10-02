"""Run this in the complete repository to verify X3 reuses real canonical primitives.

This test intentionally is not executable in a detached X3-only patch checkout;
its normal home is the complete AI-Trading-Copilot-v2 repository.
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from services.x3.pipeline_v1 import build_x3_timeframe_v1


def test_x3_uses_actual_existing_indicator_primitives():
    at = datetime(2026, 9, 18, 9, 0, tzinfo=UTC)
    candles = []
    for i in range(65):
        close = 100.0 + i * 0.07 + (i % 5) * 0.03
        start = at + timedelta(minutes=5 * i)
        candles.append(
            SimpleNamespace(
                candle_id=f"c{i}",
                start_at=start,
                end_at=start + timedelta(minutes=5),
                open_price=close - 0.1,
                high_price=close + 0.5,
                low_price=close - 0.7,
                close_price=close,
                volume=100.0 + i,
                is_complete=True,
                provenance=SimpleNamespace(provider="FYERS"),
            )
        )
    s = SimpleNamespace(
        series_id="canonical-fixture-65",
        timeframe="5m",
        candles=tuple(candles),
        blockers=(),
        warnings=(),
    )
    result = build_x3_timeframe_v1(
        market="NIFTY",
        instrument_id="NIFTY-UNDERLYING",
        series=s,
        as_of=candles[-1].end_at,
        source_quality="READY",
    )
    values = {f.feature_id: f for f in result.features}
    for name in (
        "EMA20",
        "EMA50",
        "RSI",
        "MACD_HISTOGRAM",
        "ADX",
        "ATR",
        "BOLLINGER_WIDTH",
        "VWAP_PROXY",
    ):
        assert values[name].status == "VALID", (name, values[name].blockers)
    assert (
        result.sha256
        == build_x3_timeframe_v1(
            market="NIFTY",
            instrument_id="NIFTY-UNDERLYING",
            series=s,
            as_of=candles[-1].end_at,
            source_quality="READY",
        ).sha256
    )
