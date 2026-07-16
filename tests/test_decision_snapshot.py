import json
from copy import deepcopy
from datetime import datetime

import pytest

from services.decision_snapshot import (
    build_decision_snapshot,
    build_live_decision_snapshot,
    persist_live_decision_snapshot,
    save_live_decision_snapshot,
)


def full_pipeline_result():
    return {
        "decision": "TRADE_ALLOWED",
        "market_decision": "TRADE",
        "direction": "BULLISH",
        "market_analysis": {
            "strategy": {
                "strategy": "TREND_CONTINUATION",
                "decision": "TRADE",
                "confidence": 88,
                "risk_flags": [],
            },
            "regime": {
                "primary_regime": "TRENDING_BULLISH",
                "trend": "BULLISH",
                "confidence": 80,
            },
            "timeframe": {
                "overall_trend": "BULLISH",
                "alignment": "FULL",
                "confidence": 90,
            },
            "technical": {
                "trend": "BULLISH",
                "score": 82,
                "confidence": 85,
            },
            "candlestick": {
                "signal": "BULLISH",
                "patterns": ["BULLISH_ENGULFING"],
                "support": 24100.0,
                "resistance": 24300.0,
            },
            "chart": {
                "signal": "BULLISH",
                "patterns": ["UPTREND_STRUCTURE"],
            },
            "volume": {
                "bias": "BULLISH",
                "relative_volume": 1.8,
                "volume_spike": True,
                "signals": ["VOLUME_SPIKE"],
            },
            "regime_aware_evidence": {
                "contextual_bias": "BULLISH",
                "relevant_signals": [
                    "MULTI_TIMEFRAME_TREND",
                    "VOLUME_SPIKE",
                ],
                "confirmations": [
                    "Volume confirms bullish setup."
                ],
                "warnings": [],
            },
        },
        "setup_trigger": {
            "status": "TRIGGERED",
            "direction": "BULLISH",
            "trigger_type": "BREAKOUT",
            "trigger_price": 24250.0,
        },
        "contract": {
            "symbol": "NIFTY_TEST_CE",
            "option_type": "CE",
            "strike": 24300.0,
            "expiry": "2026-07-30",
        },
    }


def test_builds_complete_snapshot():

    result = build_decision_snapshot(
        full_pipeline_result()
    )

    assert result["decision"] == "TRADE_ALLOWED"
    assert result["direction"] == "BULLISH"

    assert (
        result["strategy"]
        == "TREND_CONTINUATION"
    )

    assert (
        result["market_regime"]
        == "TRENDING_BULLISH"
    )

    assert (
        result["timeframe_alignment"]
        == "FULL"
    )

    assert (
        result["technical_trend"]
        == "BULLISH"
    )

    assert result["volume_bias"] == "BULLISH"
    assert result["relative_volume"] == 1.8
    assert result["volume_spike"] is True

    assert result["setup_status"] == "TRIGGERED"
    assert result["trigger_type"] == "BREAKOUT"

    assert (
        result["option_symbol"]
        == "NIFTY_TEST_CE"
    )

    assert result["option_type"] == "CE"


def test_missing_optional_sections_are_safe():

    result = build_decision_snapshot({
        "decision": "TRADE_ALLOWED",
        "direction": "BULLISH",
    })

    assert result["strategy"] is None
    assert result["market_regime"] is None
    assert result["volume_bias"] is None
    assert result["relative_volume"] is None

    assert result["risk_flags"] == []
    assert result["volume_signals"] == []
    assert result["confirmations"] == []
    assert result["warnings"] == []


def test_input_is_not_mutated():

    pipeline_result = (
        full_pipeline_result()
    )

    original = deepcopy(
        pipeline_result
    )

    build_decision_snapshot(
        pipeline_result
    )

    assert pipeline_result == original


def test_snapshot_lists_are_independent_copies():

    pipeline_result = (
        full_pipeline_result()
    )

    snapshot = build_decision_snapshot(
        pipeline_result
    )

    snapshot[
        "volume_signals"
    ].append(
        "EXTERNAL_MUTATION"
    )

    assert (
        "EXTERNAL_MUTATION"
        not in pipeline_result[
            "market_analysis"
        ][
            "volume"
        ][
            "signals"
        ]
    )


def test_invalid_input_fails_closed():

    with pytest.raises(
        ValueError,
        match=(
            "pipeline_result must be a dictionary"
        ),
    ):
        build_decision_snapshot(
            None
        )

def test_snapshot_prefers_direction_confidence_and_persists_evidence_strength():

    pipeline_result = full_pipeline_result()

    strategy = (
        pipeline_result[
            "market_analysis"
        ][
            "strategy"
        ]
    )

    strategy[
        "confidence"
    ] = 100

    strategy[
        "direction_confidence"
    ] = 64

    strategy[
        "evidence_strength_score"
    ] = 47

    strategy[
        "evidence_strength_label"
    ] = "MEDIUM"

    result = build_decision_snapshot(
        pipeline_result
    )

    assert (
        result["strategy_confidence"]
        == 64
    )

    assert (
        result[
            "strategy_direction_confidence"
        ]
        == 64
    )

    assert (
        result[
            "strategy_evidence_strength_score"
        ]
        == 47
    )

    assert (
        result[
            "strategy_evidence_strength_label"
        ]
        == "MEDIUM"
    )


def test_snapshot_legacy_confidence_remains_supported():

    pipeline_result = full_pipeline_result()

    strategy = (
        pipeline_result[
            "market_analysis"
        ][
            "strategy"
        ]
    )

    strategy.pop(
        "direction_confidence",
        None,
    )

    strategy[
        "confidence"
    ] = 80

    result = build_decision_snapshot(
        pipeline_result
    )

    assert (
        result["strategy_confidence"]
        == 80
    )

    assert (
        result[
            "strategy_direction_confidence"
        ]
        == 80
    )
def test_snapshot_persists_setup_formation_intelligence():

    pipeline_result = full_pipeline_result()

    pipeline_result[
        "setup_trigger"
    ].update({
        "formation_status": "NEAR_TRIGGER",
        "setup_maturity_score": 85,
        "distance_to_trigger": 8.5,
        "distance_to_trigger_percent": 0.0351,
    })

    result = build_decision_snapshot(
        pipeline_result
    )

    assert (
        result["formation_status"]
        == "NEAR_TRIGGER"
    )

    assert (
        result["setup_maturity_score"]
        == 85
    )

    assert (
        result["distance_to_trigger"]
        == 8.5
    )

    assert (
        result["distance_to_trigger_percent"]
        == 0.0351
    )

def test_snapshot_persists_trade_candidate_research():

    pipeline_result = full_pipeline_result()

    pipeline_result[
        "trade_candidate_research"
    ] = {
        "research_only": True,
        "trade_authorized": False,
        "trade_candidate_score": 85,
        "candidate_label": "CLOSE",
        "passed_conditions": [
            "Directional bias established",
            "Direction confidence",
            "Evidence strength",
        ],
        "missing_conditions": [
            "Full timeframe alignment",
            "Resolve risk flags",
        ],
    }

    result = build_decision_snapshot(
        pipeline_result
    )

    assert (
        result["trade_candidate_score"]
        == 85
    )

    assert (
        result["candidate_label"]
        == "CLOSE"
    )

    assert (
        result["candidate_passed_conditions"]
        == [
            "Directional bias established",
            "Direction confidence",
            "Evidence strength",
        ]
    )

    assert (
        result["candidate_missing_conditions"]
        == [
            "Full timeframe alignment",
            "Resolve risk flags",
        ]
    )


def test_snapshot_candidate_conditions_are_deep_copied():

    pipeline_result = full_pipeline_result()

    pipeline_result[
        "trade_candidate_research"
    ] = {
        "trade_candidate_score": 85,
        "candidate_label": "CLOSE",
        "passed_conditions": [
            "Direction confidence",
        ],
        "missing_conditions": [
            "Full timeframe alignment",
        ],
    }

    result = build_decision_snapshot(
        pipeline_result
    )

    pipeline_result[
        "trade_candidate_research"
    ][
        "passed_conditions"
    ].append(
        "MUTATED"
    )

    pipeline_result[
        "trade_candidate_research"
    ][
        "missing_conditions"
    ].append(
        "MUTATED"
    )

    assert (
        result["candidate_passed_conditions"]
        == [
            "Direction confidence",
        ]
    )

    assert (
        result["candidate_missing_conditions"]
        == [
            "Full timeframe alignment",
        ]
    )


def test_build_live_snapshot_contains_required_runtime_fields():

    pipeline_result = full_pipeline_result()
    pipeline_result["session_status"] = {
        "status": "SESSION_VALID",
        "candle_timestamp": "2026-07-16T10:25:00+05:30",
        "candle_age_minutes": 6.0,
        "candle_fresh": True,
    }
    pipeline_result["completed_candle"] = {
        "timestamp": "2026-07-16T10:25:00+05:30",
        "open": 24100.0,
        "high": 24130.0,
        "low": 24090.0,
        "close": 24120.0,
        "volume": 0.0,
    }
    pipeline_result["market_analysis"]["regime"]["volatility"] = "LOW"

    snapshot = build_live_decision_snapshot(
        pipeline_result,
        underlying="NIFTY",
        spot_price=24120.0,
        paper_trading_result={"status": "SKIPPED"},
        timestamp=datetime.fromisoformat("2026-07-16T10:31:00+05:30"),
    )

    required_fields = {
        "timestamp", "underlying", "spot_price", "market_session",
        "candle_timestamp", "candle_age_minutes", "candle_fresh",
        "decision", "direction", "confidence", "evidence_strength",
        "evidence_strength_label", "strategy", "primary_regime", "trend",
        "volatility", "regime_confidence", "support", "resistance",
        "volume_bias", "relative_volume", "volume_spike", "setup_status",
        "trigger_type", "risk_flags", "relevant_signals",
        "paper_trade_status", "selected_option_contract", "completed_candle",
    }

    assert required_fields <= set(snapshot)
    assert snapshot["paper_trade_status"] == "SKIPPED"
    assert snapshot["completed_candle"]["close"] == 24120.0
    assert snapshot["selected_option_contract"]["symbol"] == "NIFTY_TEST_CE"


def test_save_live_snapshot_uses_date_and_time_path(tmp_path):

    snapshot = build_live_decision_snapshot(
        full_pipeline_result(),
        underlying="NIFTY",
        spot_price=24120.0,
        timestamp=datetime.fromisoformat("2026-07-16T10:31:00+05:30"),
    )

    result = save_live_decision_snapshot(snapshot, base_path=tmp_path)

    destination = tmp_path / "2026-07-16" / "10-31.json"
    assert result == {
        "saved": True,
        "path": str(destination),
        "error": None,
    }
    assert json.loads(destination.read_text(encoding="utf-8")) == snapshot


def test_snapshot_persistence_failure_is_non_blocking(tmp_path):

    blocked_path = tmp_path / "not-a-directory"
    blocked_path.write_text("blocked", encoding="utf-8")

    result = persist_live_decision_snapshot(
        full_pipeline_result(),
        underlying="NIFTY",
        spot_price=24120.0,
        base_path=blocked_path,
    )

    assert result["saved"] is False
    assert result["path"] is None
    assert "FileExistsError" in result["error"]
