from datetime import datetime, timedelta, timezone

import pytest

from services.analysis.scheduled_event_evidence_adapter import (
    ScheduledEventEvidenceAdapter,
)


NOW = datetime(
    2026,
    8,
    4,
    5,
    0,
    tzinfo=timezone.utc,
)


def event_record():
    return {
        "scheduled_market_event_id": "rbi-policy-2026-08",
        "event_name": "RBI Monetary Policy",
        "event_category": "RBI_POLICY",
        "scheduled_start": NOW + timedelta(hours=3),
        "scheduled_end": NOW + timedelta(hours=4),
        "source_timestamp": NOW,
        "confirmation_state": "CONFIRMED",
        "event_status": "UPCOMING",
        "severity": "HIGH",
        "affected_market_identities": [
            ["NIFTY", "NSE"],
            ["SENSEX", "BSE"],
        ],
        "affected_exchanges": ["BSE", "NSE"],
        "analysis_allowed": True,
        "new_entries_allowed": True,
        "session_override_state": "NONE",
    }


def test_adapter_builds_exact_typed_scheduled_event():
    adapter = ScheduledEventEvidenceAdapter(
        source_id="CERTIFIED_EVENT_PROVIDER",
    )

    result = adapter.normalize(
        records=[event_record()],
        evaluated_at=NOW,
    )

    assert len(result) == 1
    event = result[0]

    assert (
        event.scheduled_market_event_id
        == "rbi-policy-2026-08"
    )
    assert event.source_id == "CERTIFIED_EVENT_PROVIDER"
    assert event.source_timestamp == NOW
    assert event.event_category == "RBI_POLICY"
    assert event.severity == "HIGH"
    assert event.affected_market_identities == (
        ("NIFTY", "NSE"),
        ("SENSEX", "BSE"),
    )
    assert adapter.normalization_count == 1


def test_empty_provider_result_remains_empty():
    adapter = ScheduledEventEvidenceAdapter(
        source_id="CERTIFIED_EVENT_PROVIDER",
    )

    assert adapter.normalize(
        records=[],
        evaluated_at=NOW,
    ) == ()

    assert adapter.normalization_count == 1


def test_future_source_timestamp_is_rejected():
    adapter = ScheduledEventEvidenceAdapter(
        source_id="CERTIFIED_EVENT_PROVIDER",
    )
    record = event_record()
    record["source_timestamp"] = (
        NOW + timedelta(seconds=1)
    )

    with pytest.raises(
        ValueError,
        match="source_timestamp cannot follow",
    ):
        adapter.normalize(
            records=[record],
            evaluated_at=NOW,
        )


def test_naive_timestamps_are_rejected():
    adapter = ScheduledEventEvidenceAdapter(
        source_id="CERTIFIED_EVENT_PROVIDER",
    )
    record = event_record()
    record["source_timestamp"] = NOW.replace(
        tzinfo=None
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        adapter.normalize(
            records=[record],
            evaluated_at=NOW,
        )


def test_duplicate_event_identifiers_are_rejected():
    adapter = ScheduledEventEvidenceAdapter(
        source_id="CERTIFIED_EVENT_PROVIDER",
    )
    record = event_record()

    with pytest.raises(
        ValueError,
        match="duplicate event identifiers",
    ):
        adapter.normalize(
            records=[record, dict(record)],
            evaluated_at=NOW,
        )


def test_invalid_provider_records_fail_closed():
    adapter = ScheduledEventEvidenceAdapter(
        source_id="CERTIFIED_EVENT_PROVIDER",
    )

    with pytest.raises(TypeError):
        adapter.normalize(
            records=[object()],
            evaluated_at=NOW,
        )

    record = event_record()
    record["analysis_allowed"] = "yes"

    with pytest.raises(
        TypeError,
        match="analysis_allowed must be boolean",
    ):
        adapter.normalize(
            records=[record],
            evaluated_at=NOW,
        )


def test_adapter_does_not_infer_static_holiday_evidence():
    source = __import__(
        "pathlib"
    ).Path(
        "services/analysis/"
        "scheduled_event_evidence_adapter.py"
    ).read_text(encoding="utf-8")

    assert "NSE_TRADING_HOLIDAYS_2026" not in source
    assert "BSE_TRADING_HOLIDAYS_2026" not in source
    assert "date.today()" not in source
