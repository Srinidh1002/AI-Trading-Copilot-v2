from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from services.x1.observation_identity_v1 import (
    ObservationIdentityError,
    build_observation_identity_v1,
)

NOW = datetime(2026, 9, 17, 10, 0, tzinfo=UTC)


def record(
    *,
    symbol="NSE:NIFTY50-INDEX",
    ltp=23456.75,
    ts=None,
    timestamp_source="PROVIDER",
    received_at=None,
    canonical_id="NIFTY:UNDERLYING",
    provider="FYERS",
):
    return {
        "provider": provider,
        "provider_symbol": symbol,
        "ltp": ltp,
        "ts": ts or NOW,
        "timestamp_source": timestamp_source,
        "received_at": received_at or NOW,
        "canonical_instrument_id": canonical_id,
    }


def test_identity_is_deterministic_for_identical_records():
    a = build_observation_identity_v1(
        record(), connection_generation=1
    )
    b = build_observation_identity_v1(
        record(), connection_generation=1
    )
    assert a.identity_sha256 == b.identity_sha256
    assert a.canonical_json() == b.canonical_json()


def test_identity_changes_when_ltp_changes():
    a = build_observation_identity_v1(
        record(ltp=100.0), connection_generation=1
    )
    b = build_observation_identity_v1(
        record(ltp=101.0), connection_generation=1
    )
    assert a.identity_sha256 != b.identity_sha256


def test_identity_changes_when_provider_timestamp_changes():
    ts1 = datetime(2026, 9, 17, 10, 0, tzinfo=UTC)
    ts2 = datetime(2026, 9, 17, 10, 0, 1, tzinfo=UTC)
    a = build_observation_identity_v1(
        record(ts=ts1), connection_generation=1
    )
    b = build_observation_identity_v1(
        record(ts=ts2), connection_generation=1
    )
    assert a.identity_sha256 != b.identity_sha256


def test_identity_changes_when_connection_generation_changes():
    a = build_observation_identity_v1(
        record(), connection_generation=1
    )
    b = build_observation_identity_v1(
        record(), connection_generation=2
    )
    assert a.identity_sha256 != b.identity_sha256


def test_local_receipt_identity_uses_ts_as_anchor():
    # When the provider did not supply a timestamp, the streaming
    # adapter sets ts = received_at. A distinct anchor_ts therefore
    # produces a distinct identity, so a caller cannot treat a
    # repeated provider observation as new by only varying received_at.
    r1 = record(
        ts=NOW,
        timestamp_source="LOCAL_RECEIPT",
        received_at=NOW,
    )
    r2 = record(
        ts=NOW + timedelta(seconds=1),
        timestamp_source="LOCAL_RECEIPT",
        received_at=NOW,
    )
    a = build_observation_identity_v1(r1, connection_generation=1)
    b = build_observation_identity_v1(r2, connection_generation=1)
    assert a.identity_sha256 != b.identity_sha256


def test_provider_identity_ignores_receipt_timestamp_changes():
    r1 = record(received_at=NOW)
    r2 = record(received_at=NOW.replace(microsecond=500000))
    a = build_observation_identity_v1(r1, connection_generation=1)
    b = build_observation_identity_v1(r2, connection_generation=1)
    assert a.identity_sha256 == b.identity_sha256


def test_missing_required_field_fails_closed():
    bad = record()
    del bad["ltp"]
    with pytest.raises(ObservationIdentityError):
        build_observation_identity_v1(bad, connection_generation=1)


def test_invalid_ltp_fails_closed():
    with pytest.raises(ObservationIdentityError):
        build_observation_identity_v1(
            record(ltp=0), connection_generation=1
        )
    with pytest.raises(ObservationIdentityError):
        build_observation_identity_v1(
            record(ltp=-1.0), connection_generation=1
        )
    with pytest.raises(ObservationIdentityError):
        build_observation_identity_v1(
            record(ltp=float("nan")), connection_generation=1
        )


def test_naive_timestamp_fails_closed():
    with pytest.raises(ObservationIdentityError):
        build_observation_identity_v1(
            record(ts=datetime(2026, 9, 17, 10, 0)),
            connection_generation=1,
        )


def test_invalid_timestamp_source_fails_closed():
    with pytest.raises(ObservationIdentityError):
        build_observation_identity_v1(
            record(timestamp_source="MOON"),
            connection_generation=1,
        )


def test_invalid_connection_generation_fails_closed():
    with pytest.raises(ObservationIdentityError):
        build_observation_identity_v1(
            record(), connection_generation=-1
        )
    with pytest.raises(ObservationIdentityError):
        build_observation_identity_v1(
            record(), connection_generation=True
        )


def test_missing_canonical_id_is_allowed_but_empty():
    r = record()
    del r["canonical_instrument_id"]
    identity = build_observation_identity_v1(
        r, connection_generation=1
    )
    assert identity.canonical_instrument_id == ""
