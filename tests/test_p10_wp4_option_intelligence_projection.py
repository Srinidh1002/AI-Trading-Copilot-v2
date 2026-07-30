from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

from services.contracts.option_chain_intelligence_result_v1 import (
    OptionChainIntelligenceResultV1,
)
from services.dashboard_read_models.dashboard_option_intelligence_projection import (
    project_option_intelligence,
)


NOW = datetime(2026, 7, 30, 14, 0, tzinfo=timezone.utc)


def exact_option_source():
    source = object.__new__(OptionChainIntelligenceResultV1)
    values = {
        "option_chain_intelligence_result_id": "option-intel-1",
        "created_at": NOW,
        "option_chain_snapshot_id": "option-snapshot-1",
        "option_chain_quality_result_id": "quality-1",
        "underlying_symbol": "NIFTY",
        "exchange": "NSE",
        "expiry": date(2026, 8, 6),
        "metrics": (),
        "intelligence_status": "READY",
        "aggregate_bias": "BULLISH",
        "aggregate_strength": 0.75,
        "bullish_metrics": (),
        "bearish_metrics": (),
        "neutral_metrics": (),
        "unavailable_metrics": (),
        "valid_metric_count": 0,
        "unavailable_metric_count": 0,
        "support_strikes": (24800.0, 24900.0),
        "resistance_strikes": (25100.0, 25200.0),
        "max_pain_strike": 25000.0,
        "blockers": (),
        "warnings": ("LIMITED_METRICS",),
        "execution_mode": "PAPER",
        "live_execution_eligible": False,
    }
    for name, value in values.items():
        object.__setattr__(source, name, value)
    return source


def test_projection_preserves_certified_option_evidence():
    result = project_option_intelligence(exact_option_source())

    assert result.source_id == "option-intel-1"
    assert result.directional_bias == "BULLISH"
    assert result.confidence == 0.75
    assert result.support == 24900.0
    assert result.resistance == 25100.0
    assert result.max_pain == 25000.0
    assert result.warnings == ("LIMITED_METRICS",)


def test_projection_leaves_unsupported_fields_unavailable():
    result = project_option_intelligence(exact_option_source())

    assert result.call_open_interest is None
    assert result.put_open_interest is None
    assert result.atm_delta is None
    assert result.aggregate_greeks_summary is None


def test_projection_rejects_untyped_source():
    with pytest.raises(TypeError, match="exact"):
        project_option_intelligence(SimpleNamespace())
