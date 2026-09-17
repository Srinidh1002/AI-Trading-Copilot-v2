from datetime import datetime

from services.canonical.analysis_pipeline import (
    CanonicalAnalysisDependencies,
    CanonicalAnalysisPipeline,
)
from services.contracts.market_snapshot_v1 import (
    MarketSnapshotV1,
    OHLCVBar,
    OHLCVSeries,
)


def _snapshot():
    timestamp = datetime.fromisoformat("2026-07-10T10:00:00+05:30")
    bars = tuple(
        OHLCVBar(
            timestamp=timestamp,
            open=100 + index,
            high=102 + index,
            low=99 + index,
            close=101 + index,
            volume=1000,
        )
        for index in range(2)
    )
    return MarketSnapshotV1(
        snapshot_id="canonical-snapshot",
        symbol="NIFTY",
        exchange="NSE",
        instrument_type="INDEX",
        captured_at=timestamp,
        market_timestamp=timestamp,
        ltp=102,
        timeframes={"5m": OHLCVSeries("5m", bars)},
    )


def _dependencies():
    return CanonicalAnalysisDependencies(
        technical_analyzer=lambda frame: {
            "trend": "BULLISH", "score": 80, "confidence": 75,
            "indicators": {"atr": 2}, "reasons": ["Technical alignment."],
        },
        multi_timeframe_analyzer=lambda frames: {
            "overall_trend": "BULLISH", "alignment": "FULL",
            "timeframe_results": {"5m": {"trend": "BULLISH", "confidence": 75}},
        },
        candlestick_analyzer=lambda frame: {
            "signal": "BULLISH", "score": 2, "support": 99, "resistance": 103,
        },
        chart_analyzer=lambda frame: {"signal": "BULLISH", "patterns": ["UPTREND_STRUCTURE"]},
        volume_analyzer=lambda frame, **_: {
            "bias": "BULLISH", "volume_spike": True,
            "bullish_evidence": ["Volume confirms."], "bearish_evidence": [],
        },
        market_structure_analyzer=lambda snapshot: {
            "trend": "BULLISH", "structure": "HH-HL", "confidence": 80,
        },
        market_regime_analyzer=lambda technical: {
            "regime": "TRENDING_BULL", "trend_strength": 80,
        },
    )


def test_canonical_analysis_uses_only_snapshot_and_injected_dependencies():
    result = CanonicalAnalysisPipeline(_dependencies()).analyse(_snapshot())

    assert result.analysis_valid is True
    assert result.directional_bias == "BULLISH"
    assert result.direction_resolved is True
    assert result.snapshot_id == "canonical-snapshot"


def test_missing_primary_timeframe_is_recorded_as_a_critical_analysis_error():
    snapshot = _snapshot()
    snapshot.timeframes = {}

    result = CanonicalAnalysisPipeline(_dependencies()).analyse(snapshot)

    assert result.analysis_valid is False
    assert "market_data" in result.engine_errors
