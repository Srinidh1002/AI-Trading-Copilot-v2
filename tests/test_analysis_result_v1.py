from __future__ import annotations

from datetime import datetime
import json
import math
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from services.contracts.analysis_result_v1 import (
    AlignmentStatus,
    AnalysisResultV1,
    AnalysisValidationError,
    DirectionalBias,
    EvidenceSection,
    EvidenceSignal,
    EvidenceStatus,
    MarketRegime,
    MultiTimeframeSummary,
    TimeframeState,
)


NOW = datetime(2026, 7, 25, 10, 0, tzinfo=ZoneInfo("Asia/Kolkata"))


def make_result(**overrides):
    payload = {
        "snapshot_id": "snapshot-1",
        "symbol": "NIFTY",
        "created_at": NOW,
        "market_timestamp": NOW,
        "market_regime": MarketRegime.TRENDING,
        "directional_bias": DirectionalBias.BULLISH,
        "direction_resolved": True,
        "multi_timeframe": MultiTimeframeSummary(
            alignment=AlignmentStatus.ALIGNED_BULLISH,
            primary_timeframe="5m",
            confirmation_timeframe="15m",
            higher_timeframe="1h",
            states={
                "5m": TimeframeState(
                    timeframe="5m",
                    direction=DirectionalBias.BULLISH,
                    trend_strength=70,
                    status=EvidenceStatus.VALID,
                )
            },
        ),
        "technical": EvidenceSection(
            status=EvidenceStatus.VALID,
            signal=EvidenceSignal.BULLISH,
            score=75,
            confidence=80,
            reasons=("Trend aligned",),
        ),
    }
    payload.update(overrides)
    return AnalysisResultV1(**payload)


def test_minimal_valid_result():
    result = AnalysisResultV1(
        snapshot_id="s1",
        symbol="NIFTY",
        created_at=NOW,
        market_timestamp=NOW,
    )
    assert result.analysis_valid is True
    assert result.directional_bias == "UNKNOWN"


def test_full_valid_bullish_result():
    result = make_result()
    assert result.analysis_valid is True
    assert result.direction_resolved is True
    assert result.technical.score == 75


@pytest.mark.parametrize(
    "bias",
    [
        DirectionalBias.BULLISH,
        DirectionalBias.BEARISH,
        DirectionalBias.NEUTRAL,
        DirectionalBias.UNKNOWN,
    ],
)
def test_valid_directional_bias_values(bias):
    result = make_result(
        directional_bias=bias,
        direction_resolved=bias != DirectionalBias.UNKNOWN,
    )
    assert result.directional_bias == bias.value


def test_conflicted_direction_cannot_be_resolved():
    result = make_result(
        directional_bias=DirectionalBias.CONFLICTED,
        direction_resolved=True,
    )
    assert result.analysis_valid is False
    assert any("Conflicted direction" in e for e in result.validation_errors)


def test_unknown_direction_cannot_be_resolved():
    result = make_result(
        directional_bias=DirectionalBias.UNKNOWN,
        direction_resolved=True,
    )
    assert result.analysis_valid is False


def test_conflicted_timeframes_block_resolved_direction():
    result = make_result(
        multi_timeframe=MultiTimeframeSummary(
            alignment=AlignmentStatus.CONFLICTED
        )
    )
    assert result.analysis_valid is False


@pytest.mark.parametrize(
    "status",
    [
        EvidenceStatus.UNAVAILABLE,
        EvidenceStatus.EMPTY,
        EvidenceStatus.INVALID,
        EvidenceStatus.ERROR,
    ],
)
def test_invalid_evidence_cannot_be_directional(status):
    with pytest.raises(AnalysisValidationError):
        EvidenceSection(
            status=status,
            signal=EvidenceSignal.BULLISH,
        )


def test_error_evidence_gets_default_error():
    section = EvidenceSection(
        status=EvidenceStatus.ERROR,
        signal=EvidenceSignal.UNAVAILABLE,
    )
    assert section.errors


def test_partial_evidence_can_be_mixed():
    section = EvidenceSection(
        status=EvidenceStatus.PARTIAL,
        signal=EvidenceSignal.MIXED,
    )
    assert section.status == "PARTIAL"


def test_unavailable_timeframe_cannot_be_bullish():
    with pytest.raises(AnalysisValidationError):
        TimeframeState(
            timeframe="5m",
            direction=DirectionalBias.BULLISH,
            status=EvidenceStatus.UNAVAILABLE,
        )


def test_missing_timeframes_are_preserved():
    result = make_result(
        multi_timeframe=MultiTimeframeSummary(
            alignment=AlignmentStatus.INSUFFICIENT_DATA,
            missing_timeframes=("15m", "1h"),
        ),
        directional_bias=DirectionalBias.UNKNOWN,
        direction_resolved=False,
    )
    assert result.multi_timeframe.missing_timeframes == ("15m", "1h")


def test_engine_error_for_critical_engine_invalidates_analysis():
    result = make_result(
        engine_errors={"technical": ("failed",)}
    )
    assert result.analysis_valid is False


def test_noncritical_engine_error_is_recorded_without_forcing_invalid():
    result = make_result(
        engine_errors={"context": ("news unavailable",)}
    )
    assert result.analysis_valid is True


@pytest.mark.parametrize("value", [math.nan, math.inf, -1, 101])
def test_invalid_score_fails_validation(value):
    result = make_result(technical_score=value)
    assert result.analysis_valid is False


@pytest.mark.parametrize("value", [0, 50, 100])
def test_score_boundaries_are_valid(value):
    result = make_result(technical_score=value)
    assert result.analysis_valid is True
    assert result.technical_score == float(value)


def test_invalid_snapshot_id_fails_validation():
    result = make_result(snapshot_id="")
    assert result.analysis_valid is False


def test_invalid_symbol_fails_validation():
    result = make_result(symbol="")
    assert result.analysis_valid is False


def test_invalid_schema_version_fails_validation():
    result = make_result(schema_version="analysis_result.v2")
    assert result.analysis_valid is False


def test_invalid_timestamp_raises():
    with pytest.raises(AnalysisValidationError):
        make_result(created_at="not-a-timestamp")


def test_naive_timestamp_uses_contract_timezone():
    result = make_result(created_at="2026-07-25T10:00:00")
    assert result.created_at.tzinfo is not None


def test_deterministic_serialization():
    result = make_result(
        source_timestamps={"b": "2", "a": "1"},
        engine_errors={"z": ("x",), "a": ("y",)},
    )
    assert result.to_json() == result.to_json()
    payload = json.loads(result.to_json())
    assert list(payload["source_timestamps"]) == ["a", "b"]


def test_round_trip_serialization():
    result = make_result(
        supporting_reasons=("Trend aligned",),
        contradictions=("Resistance nearby",),
        options_score=65,
    )
    restored = AnalysisResultV1.from_dict(result.to_dict())
    assert restored.to_dict() == result.to_dict()


def test_nonserializable_trace_metadata_fails_closed():
    result = make_result(trace_metadata={"bad": object()})
    assert result.analysis_valid is False
    assert result.trace_metadata == {}


def test_nonserializable_evidence_metadata_raises():
    with pytest.raises(AnalysisValidationError):
        EvidenceSection(metadata={"bad": object()})


def test_source_input_mapping_is_not_mutated():
    metadata = {"nested": {"value": 1}}
    section = EvidenceSection(metadata=metadata)
    section.metadata["new"] = 2
    assert "new" not in metadata


def test_reasons_are_normalized_to_tuple():
    result = make_result(supporting_reasons=["A", "", "B"])
    assert result.supporting_reasons == ("A", "B")


def test_engine_errors_are_normalized():
    result = make_result(engine_errors={"volume": ["failed", ""]})
    assert result.engine_errors["volume"] == ("failed",)


def test_evidence_serialization_contains_no_live_objects():
    result = make_result()
    json.dumps(result.to_dict(), sort_keys=True)


def test_contract_has_no_execution_fields():
    result = make_result()
    payload = result.to_dict()
    forbidden = {
        "action",
        "authorization_status",
        "execution_status",
        "trade_plan",
        "paper_trade",
        "broker_order",
    }
    assert forbidden.isdisjoint(payload)


def test_construction_does_not_call_network_or_execution():
    with patch("builtins.open") as opened:
        result = make_result()
    opened.assert_not_called()
    assert result.analysis_valid is True


def test_repeated_construction_is_side_effect_free():
    first = make_result()
    second = make_result()
    assert first.snapshot_id == second.snapshot_id
    assert first.analysis_id != second.analysis_id


def test_market_regime_validation():
    result = make_result(market_regime="NOT_A_REGIME")
    assert result.analysis_valid is False


def test_alignment_validation_raises():
    with pytest.raises(AnalysisValidationError):
        MultiTimeframeSummary(alignment="BAD")


def test_timeframe_requires_name():
    with pytest.raises(AnalysisValidationError):
        TimeframeState(timeframe="")


def test_evidence_score_validation_raises():
    with pytest.raises(AnalysisValidationError):
        EvidenceSection(score=101)


def test_evidence_confidence_validation_raises():
    with pytest.raises(AnalysisValidationError):
        EvidenceSection(confidence=math.nan)


def test_full_evidence_sections_round_trip():
    result = make_result(
        market_structure=EvidenceSection(
            status=EvidenceStatus.VALID,
            signal=EvidenceSignal.BULLISH,
            reasons=("BOS confirmed",),
        ),
        candlestick=EvidenceSection(
            status=EvidenceStatus.VALID,
            signal=EvidenceSignal.NEUTRAL,
        ),
        volume=EvidenceSection(
            status=EvidenceStatus.PARTIAL,
            signal=EvidenceSignal.MIXED,
        ),
        options=EvidenceSection(
            status=EvidenceStatus.VALID,
            signal=EvidenceSignal.BULLISH,
        ),
        institutional=EvidenceSection(
            status=EvidenceStatus.UNAVAILABLE,
            signal=EvidenceSignal.UNAVAILABLE,
        ),
        volatility=EvidenceSection(
            status=EvidenceStatus.STALE,
            signal=EvidenceSignal.NEUTRAL,
        ),
        context=EvidenceSection(
            status=EvidenceStatus.PARTIAL,
            signal=EvidenceSignal.MIXED,
        ),
    )
    restored = AnalysisResultV1.from_dict(result.to_dict())
    assert restored.to_dict() == result.to_dict()
