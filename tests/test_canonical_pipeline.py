from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
import math
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest

from services.canonical.analysis_pipeline import CanonicalAnalysisDependencies
from services.canonical.pipeline import (
    CanonicalPipelineDependencies,
    run_canonical_analysis,
    run_canonical_pipeline,
)
from services.contracts.analysis_result_v1 import AnalysisResultV1
from services.contracts.final_decision_v1 import FinalDecisionV1
from services.contracts.market_snapshot_v1 import (
    DataStatus,
    MarketSnapshotV1,
    OHLCVBar,
    OHLCVSeries,
)


NOW = datetime(2026, 7, 10, 10, 0, tzinfo=ZoneInfo("Asia/Kolkata"))


def _snapshot(
    *,
    snapshot_id: str = "canonical-snapshot",
    ltp: float | None = 102,
    stale: bool = False,
    option_chain_status: str = DataStatus.UNAVAILABLE.value,
    option_chain_data=None,
    india_vix_status: str = DataStatus.UNAVAILABLE.value,
    india_vix_value: float | None = None,
    fii_dii_status: str = DataStatus.UNAVAILABLE.value,
    fii_dii_data=None,
) -> MarketSnapshotV1:
    bars = tuple(
        OHLCVBar(
            timestamp=NOW,
            open=100 + index,
            high=102 + index,
            low=99 + index,
            close=101 + index,
            volume=1000,
        )
        for index in range(2)
    )
    return MarketSnapshotV1(
        snapshot_id=snapshot_id,
        symbol="NIFTY",
        exchange="NSE",
        instrument_type="INDEX",
        captured_at=NOW,
        market_timestamp=NOW,
        ltp=ltp,
        is_stale=stale,
        timeframes={"5m": OHLCVSeries("5m", bars)},
        option_chain_status=option_chain_status,
        option_chain_data=option_chain_data,
        india_vix_status=india_vix_status,
        india_vix_value=india_vix_value,
        fii_dii_status=fii_dii_status,
        fii_dii_data=fii_dii_data,
    )


def _analysis_dependencies(
    *,
    technical_trend: str = "BULLISH",
    structure_trend: str = "BULLISH",
    candlestick_signal: str = "BULLISH",
    volume_bias: str = "BULLISH",
) -> CanonicalAnalysisDependencies:
    return CanonicalAnalysisDependencies(
        technical_analyzer=lambda frame: {
            "trend": technical_trend,
            "score": 80,
            "confidence": 75,
            "indicators": {"atr": 2},
            "reasons": ["Technical alignment."],
        },
        multi_timeframe_analyzer=lambda frames: {
            "overall_trend": technical_trend,
            "alignment": "FULL",
            "timeframe_results": {
                "5m": {
                    "trend": technical_trend,
                    "confidence": 75,
                }
            },
        },
        candlestick_analyzer=lambda frame: {
            "signal": candlestick_signal,
            "score": 2,
            "support": 99,
            "resistance": 103,
        },
        chart_analyzer=lambda frame: {
            "signal": structure_trend,
            "patterns": ["UPTREND_STRUCTURE"],
        },
        volume_analyzer=lambda frame, **_: {
            "bias": volume_bias,
            "volume_spike": True,
            "bullish_evidence": ["Volume confirms."]
            if volume_bias == "BULLISH"
            else [],
            "bearish_evidence": ["Volume confirms bearish pressure."]
            if volume_bias == "BEARISH"
            else [],
        },
        market_structure_analyzer=lambda payload: {
            "trend": structure_trend,
            "structure": "HH-HL"
            if structure_trend == "BULLISH"
            else "LH-LL",
            "confidence": 80,
        },
        market_regime_analyzer=lambda technical: {
            "regime": "TRENDING_BULL"
            if technical_trend == "BULLISH"
            else "TRENDING_BEAR",
            "trend_strength": 80,
        },
        option_analyzer=lambda symbol, data: {
            "bull_score": 2,
            "bear_score": 1,
            "score": 60,
            "reasons": ["Option evidence."],
        },
    )


def _dependencies(**kwargs) -> CanonicalPipelineDependencies:
    return CanonicalPipelineDependencies(
        analysis=_analysis_dependencies(**kwargs)
    )


def test_combined_pipeline_returns_final_decision_v1():
    decision = run_canonical_pipeline(
        _snapshot(),
        dependencies=_dependencies(),
    )
    assert isinstance(decision, FinalDecisionV1)


def test_analysis_stage_returns_analysis_result_v1():
    analysis = run_canonical_analysis(
        _snapshot(),
        dependencies=_dependencies(),
    )
    assert isinstance(analysis, AnalysisResultV1)
    assert analysis.snapshot_id == "canonical-snapshot"


def test_bullish_analysis_maps_to_buy_analysis_only():
    decision = run_canonical_pipeline(
        _snapshot(),
        dependencies=_dependencies(),
    )
    assert decision.action == "BUY"
    assert decision.authorization_status == "ANALYSIS_ONLY"
    assert decision.execution_status == "NOT_REQUESTED"
    assert decision.trade_plan is None


def test_bearish_analysis_maps_to_sell_analysis_only():
    decision = run_canonical_pipeline(
        _snapshot(),
        dependencies=_dependencies(
            technical_trend="BEARISH",
            structure_trend="BEARISH",
            candlestick_signal="BEARISH",
            volume_bias="BEARISH",
        ),
    )
    assert decision.action == "SELL"
    assert decision.authorization_status == "ANALYSIS_ONLY"
    assert decision.trade_plan is None


def test_conflicting_analysis_fails_closed():
    decision = run_canonical_pipeline(
        _snapshot(),
        dependencies=_dependencies(
            technical_trend="BULLISH",
            structure_trend="BEARISH",
            candlestick_signal="BULLISH",
            volume_bias="BEARISH",
        ),
    )
    assert decision.action == "WAIT"
    assert decision.authorization_status == "BLOCKED"


def test_stale_snapshot_fails_closed():
    decision = run_canonical_pipeline(
        _snapshot(stale=True),
        dependencies=_dependencies(),
    )
    assert decision.action == "WAIT"
    assert decision.authorization_status == "BLOCKED"


def test_invalid_snapshot_fails_closed():
    snapshot = _snapshot(ltp=None)
    assert snapshot.validation_passed is False

    decision = run_canonical_pipeline(
        snapshot,
        dependencies=_dependencies(),
    )
    assert decision.action == "WAIT"
    assert decision.authorization_status == "BLOCKED"


def test_missing_primary_timeframe_fails_closed():
    snapshot = _snapshot()
    snapshot.timeframes = {}

    decision = run_canonical_pipeline(
        snapshot,
        dependencies=_dependencies(),
    )
    assert decision.action == "WAIT"
    assert decision.authorization_status == "BLOCKED"


def test_technical_engine_exception_is_isolated():
    dependencies = _analysis_dependencies()

    def fail(_frame):
        raise RuntimeError("technical failed")

    dependencies = replace(
        dependencies,
        technical_analyzer=fail,
    )

    decision = run_canonical_pipeline(
        _snapshot(),
        dependencies=CanonicalPipelineDependencies(
            analysis=dependencies
        ),
    )
    assert decision.action == "WAIT"
    assert decision.authorization_status == "BLOCKED"
    assert any(
        "technical failed" in error
        for error in decision.internal_errors
    )


def test_optional_sources_remain_explicitly_unavailable():
    analysis = run_canonical_analysis(
        _snapshot(),
        dependencies=_dependencies(),
    )
    assert analysis.options.status == "UNAVAILABLE"
    assert analysis.volatility.status == "UNAVAILABLE"
    assert analysis.institutional.status == "UNAVAILABLE"


def test_valid_option_chain_is_analyzed():
    analysis = run_canonical_analysis(
        _snapshot(
            option_chain_status=DataStatus.VALID.value,
            option_chain_data={"pcr": 1.1},
        ),
        dependencies=_dependencies(),
    )
    assert analysis.options.status == "VALID"
    assert analysis.options.signal == "BULLISH"


def test_valid_vix_and_institutional_sources_are_preserved():
    analysis = run_canonical_analysis(
        _snapshot(
            india_vix_status=DataStatus.VALID.value,
            india_vix_value=30,
            fii_dii_status=DataStatus.VALID.value,
            fii_dii_data={"fii_net": -100},
        ),
        dependencies=_dependencies(),
    )
    assert analysis.volatility.status == "VALID"
    assert "India VIX is elevated." in analysis.volatility.warnings
    assert analysis.institutional.status == "PARTIAL"


def test_result_serialization_is_deterministic():
    decision = run_canonical_pipeline(
        _snapshot(),
        dependencies=_dependencies(),
    )
    first = decision.to_json()
    second = decision.to_json()
    assert first == second
    json.loads(first)


def test_repeated_runs_are_semantically_equal_except_generated_ids():
    first = run_canonical_pipeline(
        _snapshot(),
        dependencies=_dependencies(),
    ).to_dict()
    second = run_canonical_pipeline(
        _snapshot(),
        dependencies=_dependencies(),
    ).to_dict()

    first.pop("decision_id")
    second.pop("decision_id")
    first["trace_metadata"].pop("analysis_id")
    second["trace_metadata"].pop("analysis_id")

    assert first == second


def test_injected_engines_are_called_once():
    technical = Mock(
        return_value={
            "trend": "BULLISH",
            "score": 80,
            "confidence": 75,
            "indicators": {"atr": 2},
            "reasons": ["Technical alignment."],
        }
    )
    dependencies = replace(
        _analysis_dependencies(),
        technical_analyzer=technical,
    )

    run_canonical_pipeline(
        _snapshot(),
        dependencies=CanonicalPipelineDependencies(
            analysis=dependencies
        ),
    )
    technical.assert_called_once()


def test_pipeline_does_not_create_execution_authorization():
    decision = run_canonical_pipeline(
        _snapshot(),
        dependencies=_dependencies(),
    )
    assert decision.authorization_status not in {
        "PAPER_READY",
        "MANUAL_APPROVAL_REQUIRED",
        "AUTHORIZED",
    }
    assert decision.trade_plan is None
    assert decision.execution_status == "NOT_REQUESTED"


def test_pipeline_does_not_mutate_snapshot():
    snapshot = _snapshot()
    before = snapshot.to_json()

    run_canonical_pipeline(
        snapshot,
        dependencies=_dependencies(),
    )

    assert snapshot.to_json() == before


def test_non_snapshot_input_is_rejected():
    with pytest.raises(TypeError):
        run_canonical_pipeline(
            {"symbol": "NIFTY"},  # type: ignore[arg-type]
            dependencies=_dependencies(),
        )
