from dataclasses import replace
from datetime import datetime, timezone

import pytest

from services.analysis.shared_external_market_context import build_shared_external_market_context


NOW = datetime(2026, 8, 3, tzinfo=timezone.utc)


def test_optional_empty_external_context_is_provider_free_and_reused_as_shared_input():
    result = build_shared_external_market_context(cycle_id="parent", evaluated_at=NOW)
    assert result.build_count == 1
    assert (result.global_provider_call_count, result.institutional_provider_call_count, result.event_provider_call_count, result.breadth_provider_call_count) == (0, 0, 0, 0)
    assert result.nifty.context_status == "UNAVAILABLE"
    assert result.sensex.context_status == "UNAVAILABLE"
    assert not result.nifty.blockers and not result.sensex.blockers
    assert "GLOBAL CONTEXT IS UNAVAILABLE" in result.nifty.warnings
    assert result.for_market("NIFTY", "NSE") is result.nifty
    assert result.for_market("SENSEX", "BSE") is result.sensex
    assert result.nifty.external_market_context_result_id != result.sensex.external_market_context_result_id


def test_shared_context_rejects_cross_market_lookup():
    result = build_shared_external_market_context(cycle_id="parent", evaluated_at=NOW)
    with pytest.raises(ValueError):
        result.for_market("NIFTY", "BSE")
