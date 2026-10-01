from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from services.x1.observation_journal_v1 import (
    ObservationJournalCapacityError,
    ObservationJournalCorruptError,
    ObservationJournalIntegrityError,
    ObservationJournalV1,
    ObservationRecordError,
    ObservationRecordV1,
    build_observation_record_v1,
)
from services.x1.observation_tracker_v1 import (
    ObservationQualityV1,
    ObservationTrackerV1,
)

BASE = datetime(2026, 9, 17, 10, 0, tzinfo=UTC)
SESSION = "2026-09-17"


def rec(
    *,
    ltp=100.0,
    ts=None,
    received_at=None,
    canonical_id="NIFTY|UNDERLYING|NSE:NIFTY50-INDEX",
    generation=1,
    timestamp_source="PROVIDER",
    market="NIFTY",
    instrument_type="UNDERLYING",
    symbol="NSE:NIFTY50-INDEX",
):
    return {
        "provider": "FYERS",
        "provider_symbol": symbol,
        "ltp": ltp,
        "ts": ts or BASE,
        "received_at": received_at or BASE,
        "timestamp_source": timestamp_source,
        "canonical_instrument_id": canonical_id,
        "market_symbol": market,
        "instrument_type": instrument_type,
        "connection_generation": generation,
    }


def classify(record, tracker):
    return tracker.classify(
        record,
        connection_generation=record["connection_generation"],
        current_generation=record["connection_generation"],
    )


def make_record(*, tracker, record, receipt_index=1, session=SESSION):
    classification = classify(record, tracker)
    return build_observation_record_v1(
        record=record,
        classification=classification,
        receipt_order_index=receipt_index,
        session_id=session,
    )


def test_record_round_trips_through_canonical_json(tmp_path):
    tracker = ObservationTrackerV1(clock=lambda: BASE)
    record = make_record(tracker=tracker, record=rec())
    text = record.canonical_json()
    assert text == record.canonical_json()
    assert record.observation_id == record._compute_observation_id()


def test_build_record_rejects_missing_fields():
    tracker = ObservationTrackerV1(clock=lambda: BASE)
    bad = rec()
    del bad["provider_symbol"]
    with pytest.raises(ObservationRecordError):
        make_record(tracker=tracker, record=bad)


def test_build_record_rejects_nonpositive_ltp():
    tracker = ObservationTrackerV1(clock=lambda: BASE)
    bad = rec()
    bad["ltp"] = 0
    with pytest.raises(ObservationRecordError):
        make_record(tracker=tracker, record=bad)


def test_build_record_rejects_bad_session_id():
    tracker = ObservationTrackerV1(clock=lambda: BASE)
    with pytest.raises(ObservationRecordError):
        make_record(
            tracker=tracker,
            record=rec(),
            session="2026/09/17",
        )


def test_append_then_load_is_deterministic(tmp_path):
    tracker = ObservationTrackerV1(clock=lambda: BASE)
    journal = ObservationJournalV1(tmp_path, session_id=SESSION)
    for i in range(3):
        record = make_record(
            tracker=tracker,
            record=rec(ltp=100.0 + i),
            receipt_index=i + 1,
        )
        journal.append(record)
    loaded = journal.load()
    assert len(loaded) == 3
    assert [r.receipt_order_index for r in loaded] == [1, 2, 3]


def test_load_missing_file_is_empty(tmp_path):
    journal = ObservationJournalV1(tmp_path, session_id=SESSION)
    assert journal.load() == ()


def test_load_rejects_non_canonical_line(tmp_path):
    tracker = ObservationTrackerV1(clock=lambda: BASE)
    journal = ObservationJournalV1(tmp_path, session_id=SESSION)
    record = make_record(tracker=tracker, record=rec())
    journal.append(record)
    path = journal.path
    text = path.read_text(encoding="utf-8")
    # Add a space after the first key — no longer canonical.
    text = text.replace("{", "{ ", 1)
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ObservationJournalIntegrityError):
        journal.load()


def test_load_rejects_hash_mismatch(tmp_path):
    tracker = ObservationTrackerV1(clock=lambda: BASE)
    journal = ObservationJournalV1(tmp_path, session_id=SESSION)
    record = make_record(tracker=tracker, record=rec())
    journal.append(record)
    path = journal.path
    payload = path.read_text(encoding="utf-8").strip()
    # Flip a digit in observation_id.
    tampered = payload.replace(
        record.observation_id, "0" * 64
    )
    path.write_text(tampered + "\n", encoding="utf-8")
    with pytest.raises(ObservationJournalIntegrityError):
        journal.load()


def test_load_rejects_invalid_json(tmp_path):
    journal = ObservationJournalV1(tmp_path, session_id=SESSION)
    journal.path.parent.mkdir(parents=True, exist_ok=True)
    journal.path.write_text("not json\n", encoding="utf-8")
    with pytest.raises(ObservationJournalCorruptError):
        journal.load()


def test_load_rejects_duplicate_observation_id(tmp_path):
    tracker = ObservationTrackerV1(clock=lambda: BASE)
    journal = ObservationJournalV1(tmp_path, session_id=SESSION)
    record = make_record(tracker=tracker, record=rec())
    journal.append(record)
    # Append the same record twice via direct file write to bypass
    # the append path (which would recompute identity anyway).
    with journal.path.open("a", encoding="utf-8") as handle:
        handle.write(record.canonical_json() + "\n")
    with pytest.raises(ObservationJournalIntegrityError):
        journal.load()


def test_load_replay_at_rejects_future_records(tmp_path):
    tracker = ObservationTrackerV1(clock=lambda: BASE)
    journal = ObservationJournalV1(tmp_path, session_id=SESSION)
    record = make_record(
        tracker=tracker,
        record=rec(received_at=BASE + timedelta(seconds=60)),
    )
    journal.append(record)
    with pytest.raises(ObservationJournalIntegrityError):
        journal.load(replay_at=BASE)


def test_replay_at_accepts_records_up_to_bound(tmp_path):
    tracker = ObservationTrackerV1(clock=lambda: BASE)
    journal = ObservationJournalV1(tmp_path, session_id=SESSION)
    record = make_record(tracker=tracker, record=rec())
    journal.append(record)
    loaded = journal.load(replay_at=BASE + timedelta(seconds=1))
    assert len(loaded) == 1


def test_record_cap_is_enforced(tmp_path):
    tracker = ObservationTrackerV1(clock=lambda: BASE)
    journal = ObservationJournalV1(
        tmp_path, session_id=SESSION, max_records_per_file=1
    )
    journal.append(make_record(tracker=tracker, record=rec()))
    with pytest.raises(ObservationJournalCapacityError):
        journal.append(
            make_record(
                tracker=tracker,
                record=rec(ltp=101.0),
                receipt_index=2,
            )
        )


def test_byte_cap_is_enforced(tmp_path):
    tracker = ObservationTrackerV1(clock=lambda: BASE)
    journal = ObservationJournalV1(
        tmp_path, session_id=SESSION, max_file_bytes=1
    )
    with pytest.raises(ObservationJournalCapacityError):
        journal.append(make_record(tracker=tracker, record=rec()))


def test_malformed_classification_is_still_recordable(tmp_path):
    # The record builder allows MALFORMED classifications for audit
    # purposes because the raw fields are still present.
    tracker = ObservationTrackerV1(clock=lambda: BASE)
    bad = rec(canonical_id="")
    classification = classify(bad, tracker)
    assert classification.quality is ObservationQualityV1.MALFORMED
    record = build_observation_record_v1(
        record=bad,
        classification=classification,
        receipt_order_index=1,
        session_id=SESSION,
    )
    assert record.quality == ObservationQualityV1.MALFORMED.value
    assert record.canonical_instrument_id == ""


def test_observation_id_ignores_declared_value():
    tracker = ObservationTrackerV1(clock=lambda: BASE)
    record = make_record(tracker=tracker, record=rec())
    # Reconstruct from the same payload with the correct id.
    payload = record.canonical_payload()
    import json as _json
    from hashlib import sha256
    expected = sha256(
        _json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    assert record.observation_id == expected


def test_direct_construction_accepts_matching_observation_id():
    tracker = ObservationTrackerV1(clock=lambda: BASE)
    valid = make_record(tracker=tracker, record=rec())
    reconstructed = ObservationRecordV1(
        record_schema_version=valid.record_schema_version,
        observation_id=valid.observation_id,
        provider=valid.provider,
        provider_symbol=valid.provider_symbol,
        canonical_instrument_id=valid.canonical_instrument_id,
        market_symbol=valid.market_symbol,
        instrument_type=valid.instrument_type,
        connection_generation=valid.connection_generation,
        timestamp_source=valid.timestamp_source,
        anchor_timestamp_iso=valid.anchor_timestamp_iso,
        received_at_iso=valid.received_at_iso,
        ltp=valid.ltp,
        quality=valid.quality,
        reason_code=valid.reason_code,
        receipt_order_index=valid.receipt_order_index,
        processing_order_index=valid.processing_order_index,
        session_id=valid.session_id,
    )
    assert reconstructed.observation_id == valid.observation_id
    assert reconstructed.canonical_json() == valid.canonical_json()


def test_direct_construction_rejects_tampered_observation_id():
    tracker = ObservationTrackerV1(clock=lambda: BASE)
    valid = make_record(tracker=tracker, record=rec())
    with pytest.raises(ObservationRecordError):
        ObservationRecordV1(
            record_schema_version=valid.record_schema_version,
            observation_id="f" * 64,
            provider=valid.provider,
            provider_symbol=valid.provider_symbol,
            canonical_instrument_id=valid.canonical_instrument_id,
            market_symbol=valid.market_symbol,
            instrument_type=valid.instrument_type,
            connection_generation=valid.connection_generation,
            timestamp_source=valid.timestamp_source,
            anchor_timestamp_iso=valid.anchor_timestamp_iso,
            received_at_iso=valid.received_at_iso,
            ltp=valid.ltp,
            quality=valid.quality,
            reason_code=valid.reason_code,
            receipt_order_index=valid.receipt_order_index,
            processing_order_index=valid.processing_order_index,
            session_id=valid.session_id,
        )
