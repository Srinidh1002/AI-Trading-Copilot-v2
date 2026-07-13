import pandas as pd

from unittest.mock import (
    MagicMock,
    patch,
)

from services.live_analysis_pipeline import (
    LiveAnalysisPipeline,
)


def market_data():

    rows = 250

    return pd.DataFrame({
        "timestamp": pd.date_range(
            "2026-01-01",
            periods=rows,
            freq="5min",
        ),
        "Open": range(
            100,
            100 + rows,
        ),
        "High": range(
            105,
            105 + rows,
        ),
        "Low": range(
            95,
            95 + rows,
        ),
        "Close": range(
            102,
            102 + rows,
        ),
        "Volume": [
            1000
            for _ in range(rows)
        ],
    })


@patch(
    "services.live_analysis_pipeline."
    "evaluate_regime_aware_evidence"
)
@patch(
    "services.live_analysis_pipeline."
    "select_strategy"
)
@patch(
    "services.live_analysis_pipeline."
    "analyse_chart_patterns"
)
@patch(
    "services.live_analysis_pipeline."
    "analyse_volume_intelligence"
)
@patch(
    "services.live_analysis_pipeline."
    "analyse_patterns"
)
@patch(
    "services.live_analysis_pipeline."
    "analyse_market_regime"
)
@patch(
    "services.live_analysis_pipeline."
    "analyse_multi_timeframe"
)
@patch(
    "services.live_analysis_pipeline."
    "analyse_technical"
)
def test_live_analysis_pipeline(
    mock_technical,
    mock_timeframe,
    mock_regime,
    mock_patterns,
    mock_volume,
    mock_chart,
    mock_strategy,
    mock_regime_evidence,
):

    mock_service = MagicMock()

    df = market_data()

    mock_service.fetch_all.return_value = {
        "5m": df.copy(),
        "15m": df.copy(),
        "1h": df.copy(),
        "1d": df.copy(),
    }

    mock_technical.return_value = {
        "trend": "BULLISH"
    }

    mock_timeframe.return_value = {
        "overall_trend": "BULLISH",
        "alignment": "FULL",
    }

    mock_regime.return_value = {
        "primary_regime": (
            "TRENDING_BULLISH"
        ),
        "trend": "BULLISH",
    }

    mock_patterns.return_value = {
        "patterns": [
            "BULLISH_ENGULFING"
        ],
        "signal": "BULLISH",
        "support": 100.0,
        "resistance": 400.0,
    }

    mock_volume.return_value = {
        "bias": "BULLISH",
        "relative_volume": 1.8,
        "volume_spike": True,
        "signals": [
            "VOLUME_SPIKE"
        ],
    }

    mock_chart.return_value = {
        "patterns": [
            "UPTREND_STRUCTURE"
        ],
        "signal": "BULLISH",
        "volume_confirmation": True,
    }

    mock_regime_evidence.return_value = {
        "regime": "TRENDING_BULLISH",
        "contextual_bias": "BULLISH",
        "bullish_evidence": [
            "Multi-timeframe trend is bullish."
        ],
        "bearish_evidence": [],
        "confirmations": [],
        "warnings": [],
        "relevant_signals": [
            "MULTI_TIMEFRAME_TREND"
        ],
    }

    mock_strategy.return_value = {
        "strategy": (
            "TREND_CONTINUATION"
        ),
        "direction": "BULLISH",
        "confidence": 90,
        "decision": "TRADE",
    }

    pipeline = LiveAnalysisPipeline(
        data_service=mock_service
    )

    result = pipeline.analyse(
        exchange="NSE",
        symboltoken="99926000",
    )

    assert (
        result["strategy"]["decision"]
        == "TRADE"
    )

    assert (
        result["regime"]["primary_regime"]
        == "TRENDING_BULLISH"
    )

    assert (
        result["timeframe"]["alignment"]
        == "FULL"
    )

    assert (
        result["volume"]["bias"]
        == "BULLISH"
    )

    assert (
        result[
            "regime_aware_evidence"
        ][
            "contextual_bias"
        ]
        == "BULLISH"
    )

    mock_volume.assert_called_once()

    volume_call = (
        mock_volume.call_args.kwargs
    )

    assert (
        volume_call["support"]
        == 100.0
    )

    assert (
        volume_call["resistance"]
        == 400.0
    )

    mock_regime_evidence.assert_called_once()

    evidence_call = (
        mock_regime_evidence.call_args.kwargs
    )

    assert (
        evidence_call["regime"]
        == mock_regime.return_value
    )

    assert (
        evidence_call["volume"]
        == mock_volume.return_value
    )

    mock_service.fetch_all.assert_called_once()