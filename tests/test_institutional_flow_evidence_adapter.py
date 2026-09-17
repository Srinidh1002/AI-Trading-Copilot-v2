from datetime import date, datetime, timedelta, timezone

import pytest

from services.analysis.institutional_flow_evidence_adapter import (
    InstitutionalFlowEvidenceAdapter,
)


NOW = datetime(
    2026,
    8,
    4,
    6,
    0,
    tzinfo=timezone.utc,
)


def record():
    return {
        "institutional_flow_snapshot_id": "flows-2026-08-04",
        "trading_date": date(2026, 8, 4),
        "source_timestamp": NOW,
        "publication_state": "FINAL",
        "session_reference": "CURRENT_SESSION",
        "currency": "INR",
        "cash_flow_unit": "CRORE_INR",
        "derivatives_position_unit": "CONTRACTS",
        "fii_cash_net": 1200.0,
        "dii_cash_net": -400.0,
        "fii_index_futures_net": 1800.0,
        "fii_index_options_net": 2400.0,
        "flow_status": "READY",
        "affected_market_identities": [
            ["NIFTY", "NSE"],
            ["SENSEX", "BSE"],
        ],
    }


def test_adapter_builds_exact_typed_snapshot():
    adapter = InstitutionalFlowEvidenceAdapter(
        source_id="CERTIFIED_INSTITUTIONAL_PROVIDER",
    )

    result = adapter.normalize(
        record=record(),
        evaluated_at=NOW,
    )

    assert result.source_id == (
        "CERTIFIED_INSTITUTIONAL_PROVIDER"
    )
    assert result.source_timestamp == NOW
    assert result.fii_cash_net == 1200.0
    assert result.dii_cash_net == -400.0
    assert result.affected_market_identities == (
        ("NIFTY", "NSE"),
        ("SENSEX", "BSE"),
    )
    assert adapter.normalization_count == 1


def test_future_source_timestamp_is_rejected():
    adapter = InstitutionalFlowEvidenceAdapter(
        source_id="CERTIFIED_INSTITUTIONAL_PROVIDER",
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
            record=value,
            evaluated_at=NOW,
        )


def test_naive_source_timestamp_is_rejected():
    adapter = InstitutionalFlowEvidenceAdapter(
        source_id="CERTIFIED_INSTITUTIONAL_PROVIDER",
    )
    value = record()
    value["source_timestamp"] = NOW.replace(
        tzinfo=None
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        adapter.normalize(
            record=value,
            evaluated_at=NOW,
        )


def test_invalid_units_fail_closed():
    adapter = InstitutionalFlowEvidenceAdapter(
        source_id="CERTIFIED_INSTITUTIONAL_PROVIDER",
    )
    value = record()
    value["cash_flow_unit"] = "POINTS"

    with pytest.raises(ValueError):
        adapter.normalize(
            record=value,
            evaluated_at=NOW,
        )


def test_missing_values_are_not_converted_to_zero():
    adapter = InstitutionalFlowEvidenceAdapter(
        source_id="CERTIFIED_INSTITUTIONAL_PROVIDER",
    )
    value = record()
    value.update(
        {
            "fii_cash_net": None,
            "dii_cash_net": None,
            "fii_index_futures_net": None,
            "fii_index_options_net": None,
            "publication_state": "UNAVAILABLE",
            "session_reference": "UNAVAILABLE",
            "cash_flow_unit": "UNAVAILABLE",
            "derivatives_position_unit": "UNAVAILABLE",
            "flow_status": "UNAVAILABLE",
        }
    )

    result = adapter.normalize(
        record=value,
        evaluated_at=NOW,
    )

    assert result.fii_cash_net is None
    assert result.dii_cash_net is None
    assert result.fii_index_futures_net is None
    assert result.fii_index_options_net is None


def test_legacy_zero_default_engine_is_not_used():
    source = __import__("pathlib").Path(
        "services/analysis/"
        "institutional_flow_evidence_adapter.py"
    ).read_text(encoding="utf-8")

    assert "fii_dii_engine" not in source
    assert "analyze_fii_dii" not in source
    assert "date.today()" not in source
