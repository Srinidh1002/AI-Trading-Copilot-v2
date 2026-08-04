from datetime import datetime, timedelta, timezone

import pytest

from services.analysis.global_market_evidence_adapter import (
    GlobalMarketEvidenceAdapter,
)


NOW = datetime(
    2026,
    8,
    4,
    7,
    0,
    tzinfo=timezone.utc,
)


def record():
    return {
        "external_market_observation_id": "sp500-close",
        "canonical_name": "SP500",
        "observation_type": "INDEX_CLOSE",
        "market_region": "UNITED_STATES",
        "asset_class": "EQUITY_INDEX",
        "source_timestamp": NOW,
        "session_reference": "PREVIOUS_SESSION_CLOSE",
        "current_value": 101.0,
        "previous_value": 100.0,
        "change_value": 1.0,
        "change_percent": 1.0,
        "direction": "POSITIVE",
        "observation_status": "READY",
        "affected_market_identities": [
            ["NIFTY", "NSE"],
            ["SENSEX", "BSE"],
        ],
    }


def test_adapter_builds_exact_typed_observation():
    adapter = GlobalMarketEvidenceAdapter(
        source_id="CERTIFIED_GLOBAL_PROVIDER",
    )

    result = adapter.normalize(
        records=[record()],
        evaluated_at=NOW,
    )

    assert len(result) == 1
    observation = result[0]

    assert observation.source_id == (
        "CERTIFIED_GLOBAL_PROVIDER"
    )
    assert observation.canonical_name == "SP500"
    assert observation.source_timestamp == NOW
    assert observation.change_percent == 1.0
    assert observation.affected_market_identities == (
        ("NIFTY", "NSE"),
        ("SENSEX", "BSE"),
    )
    assert adapter.normalization_count == 1


def test_empty_provider_result_remains_empty():
    adapter = GlobalMarketEvidenceAdapter(
        source_id="CERTIFIED_GLOBAL_PROVIDER",
    )

    assert adapter.normalize(
        records=[],
        evaluated_at=NOW,
    ) == ()

    assert adapter.normalization_count == 1


def test_future_source_timestamp_is_rejected():
    adapter = GlobalMarketEvidenceAdapter(
        source_id="CERTIFIED_GLOBAL_PROVIDER",
    )
    value = record()
    value["source_timestamp"] = (
        NOW + timedelta(seconds=1)
    )

    with pytest.raises(
        ValueError,
        match="source_timestamp cannot follow",
    ):
        adapter.normalize(
            records=[value],
            evaluated_at=NOW,
        )


def test_inconsistent_change_values_fail_closed():
    adapter = GlobalMarketEvidenceAdapter(
        source_id="CERTIFIED_GLOBAL_PROVIDER",
    )
    value = record()
    value["change_percent"] = 9.0

    with pytest.raises(ValueError):
        adapter.normalize(
            records=[value],
            evaluated_at=NOW,
        )


def test_duplicate_canonical_names_are_rejected():
    adapter = GlobalMarketEvidenceAdapter(
        source_id="CERTIFIED_GLOBAL_PROVIDER",
    )

    with pytest.raises(
        ValueError,
        match="duplicate canonical observations",
    ):
        adapter.normalize(
            records=[record(), dict(record())],
            evaluated_at=NOW,
        )


def test_missing_values_are_not_converted_to_zero():
    adapter = GlobalMarketEvidenceAdapter(
        source_id="CERTIFIED_GLOBAL_PROVIDER",
    )
    value = record()
    value.update(
        {
            "current_value": None,
            "previous_value": None,
            "change_value": None,
            "change_percent": None,
            "direction": "UNAVAILABLE",
            "observation_status": "UNAVAILABLE",
        }
    )

    result = adapter.normalize(
        records=[value],
        evaluated_at=NOW,
    )

    assert result[0].current_value is None
    assert result[0].previous_value is None
    assert result[0].change_percent is None


def test_no_unapproved_network_or_price_source_is_used():
    source = __import__("pathlib").Path(
        "services/analysis/"
        "global_market_evidence_adapter.py"
    ).read_text(encoding="utf-8")

    assert "yfinance" not in source
    assert "requests" not in source
    assert "urlopen" not in source
    assert "date.today()" not in source
