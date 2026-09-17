"""Focused Task 9 optional higher-timeframe PAPER gate regressions."""
from datetime import datetime, timedelta, timezone
from dataclasses import replace

import pytest

from services.contracts import (
    MarketCandleSeriesV1,
    MarketCandleV1,
    MarketDataProvenanceV1,
)
from tests.fixtures.p5_4c import bullish_series, incomplete_series
from services.multi_timeframe.pipeline import build_canonical_multi_timeframe_snapshot
from services.multi_timeframe.quality import evaluate_multi_timeframe_quality
from services.technical_intelligence.pipeline import build_canonical_technical_intelligence


_DIRECTIONAL_END = datetime(2026, 8, 24, 9, 15, tzinfo=timezone.utc)
_DIRECTIONAL_PROVENANCE = MarketDataProvenanceV1(
    "TASK929_DIRECTIONAL_FIXTURE",
    None,
    None,
    "TEST",
    _DIRECTIONAL_END,
    _DIRECTIONAL_END,
    False,
    None,
    None,
)
_TIMEFRAME_MINUTES = {"5m": 5, "15m": 15, "1h": 60}


def directional_raw_series(*, direction, timeframe):
    """Sixty valid raw NIFTY candles; 1d is intentionally absent."""
    assert direction in {"BULLISH", "BEARISH"}
    step = _TIMEFRAME_MINUTES[timeframe]
    sign = 1 if direction == "BULLISH" else -1
    start = _DIRECTIONAL_END - timedelta(minutes=step * 60)
    rows = []
    previous_close = 24500.0
    for index in range(60):
        close = 24500.0 + sign * 5.0 * index
        open_price = 24500.0 if index == 0 else previous_close
        opened_at = start + timedelta(minutes=step * index)
        rows.append(
            MarketCandleV1(
                f"task929-{direction.lower()}-{timeframe}-{index}",
                "NIFTY",
                "NSE",
                timeframe,
                opened_at,
                opened_at + timedelta(minutes=step),
                open_price,
                max(open_price, close) + 4.0,
                min(open_price, close) - 4.0,
                close,
                1000.0,
                True,
                _DIRECTIONAL_PROVENANCE,
            )
        )
        previous_close = close
    return MarketCandleSeriesV1(
        f"task929-{direction.lower()}-{timeframe}",
        "NIFTY",
        "NSE",
        timeframe,
        tuple(rows),
        None,
        None,
        _DIRECTIONAL_END,
    )


def build_directional_three_timeframe_technical(direction):
    series = tuple(
        directional_raw_series(direction=direction, timeframe=timeframe)
        for timeframe in ("5m", "15m", "1h")
    )
    snapshot, quality = build_canonical_multi_timeframe_snapshot(
        candle_series_by_timeframe=series,
        clock=lambda: _DIRECTIONAL_END,
    )
    technical = build_canonical_technical_intelligence(
        candle_series_by_timeframe=series,
        multi_timeframe_snapshot=snapshot,
        multi_timeframe_quality_result=quality,
        clock=lambda: _DIRECTIONAL_END,
    )
    return snapshot, quality, technical


def _build(*timeframes, incomplete=False):
    builder = incomplete_series if incomplete else bullish_series
    series = tuple(builder(timeframe=timeframe) for timeframe in timeframes)
    now = series[0].candles[-1].end_at
    snapshot, quality = build_canonical_multi_timeframe_snapshot(
        candle_series_by_timeframe=series, clock=lambda: now,
    )
    technical = build_canonical_technical_intelligence(
        candle_series_by_timeframe=series, multi_timeframe_snapshot=snapshot,
        multi_timeframe_quality_result=quality, clock=lambda: now,
    )
    return quality, technical


def test_5m_only_is_usable_with_exact_optional_warnings_and_zero_weight_contribution():
    quality, technical = _build("5m")

    assert quality.quality_status == technical.status == "READY_WITH_WARNINGS"
    assert quality.missing_timeframes == ("15m", "1h", "1d")
    assert technical.unavailable_timeframes == ("15m", "1h", "1d")
    # 5m's .35 policy weight is deliberately not renormalized to 1.0.
    assert technical.aggregate_strength < 0.35


def test_available_optional_confirmation_and_missing_remaining_optional_are_warnings():
    quality, technical = _build("5m", "15m")

    assert quality.quality_status == technical.status == "READY_WITH_WARNINGS"
    assert quality.warnings == (
        "optional_timeframe_unavailable_1h",
        "optional_timeframe_unavailable_1d",
    )
    assert technical.unavailable_timeframes == ("1h", "1d")


def test_all_four_valid_remains_ready():
    quality, technical = _build("5m", "15m", "1h", "1d")

    assert quality.quality_status == technical.status == "READY"


def test_missing_or_incomplete_mandatory_5m_remains_blocking():
    series = (bullish_series(timeframe="15m"),)
    now = series[0].candles[-1].end_at
    _, missing_quality = build_canonical_multi_timeframe_snapshot(
        candle_series_by_timeframe=series, clock=lambda: now,
    )
    assert missing_quality.quality_status == "MISSING_TIMEFRAMES"

    quality, technical = _build("5m", incomplete=True)
    assert quality.quality_status == technical.status == "INCOMPLETE"


def test_supplied_stale_or_future_optional_and_mandatory_evidence_never_silently_qualifies():
    series = tuple(bullish_series(timeframe=timeframe) for timeframe in ("5m", "15m"))
    now = series[0].candles[-1].end_at
    snapshot, _ = build_canonical_multi_timeframe_snapshot(candle_series_by_timeframe=series, clock=lambda: now)

    stale_optional = replace(snapshot, timeframe_evidence=(snapshot.timeframe_evidence[0], replace(snapshot.timeframe_evidence[1], quality_status="STALE", blockers=("stale",))))
    future_mandatory = replace(snapshot, timeframe_evidence=(replace(snapshot.timeframe_evidence[0], quality_status="FUTURE", blockers=("future",)), snapshot.timeframe_evidence[1]))

    assert evaluate_multi_timeframe_quality(stale_optional, clock=lambda: now).quality_status == "STALE"
    assert evaluate_multi_timeframe_quality(future_mandatory, clock=lambda: now).quality_status == "FUTURE"


@pytest.mark.parametrize(
    ("direction", "expected_bias"),
    (("BULLISH", "BULLISH"), ("BEARISH", "BEARISH")),
)
def test_raw_three_timeframe_directional_fixture_remains_usable_without_1d(
    direction,
    expected_bias,
):
    _, quality, technical = build_directional_three_timeframe_technical(direction)

    assert quality.quality_status == technical.status == "READY_WITH_WARNINGS"
    assert technical.aggregate_bias == expected_bias
    assert technical.aggregate_strength == pytest.approx(0.34)
    assert technical.blockers == ()
    assert tuple(warning.upper() for warning in technical.warnings) == (
        "OPTIONAL_TIMEFRAME_UNAVAILABLE_1D",
        "TECHNICAL_TIMEFRAME_UNAVAILABLE_1D",
    )
