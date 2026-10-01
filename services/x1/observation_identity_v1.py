"""Deterministic observation identity for the X1 data plane.

Observation identity is the minimal tuple of fields the pipeline uses to
decide whether two incoming records describe the same provider market
event.

Design constraints (per X1 review correction B):

* We never fabricate a provider sequence number. The FYERS DataSocket we
  consume does not expose one in the fields we read.
* We never assume provider timestamps are unique. FYERS exposes second
  resolution on the fields we consume, so two legitimate events may share
  a provider timestamp.
* We never use local receipt timestamps to claim that a repeated provider
  observation is new. Local receipt time is used as the identity anchor
  only when the provider timestamp is missing.
* We prefer conservative over-flagging (classifying a legitimate second
  event as ``SUSPECTED_DUPLICATE``) over under-flagging (treating a
  repeated provider observation as new evidence).

When the provider later exposes a stable per-event identity or sequence
field, the identity schema version will be incremented and this module
extended. Version 1 does not claim unique-event identity.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

OBSERVATION_IDENTITY_SCHEMA_V1 = "X1_OBSERVATION_IDENTITY_V1"

_VALID_TIMESTAMP_SOURCES = frozenset({"PROVIDER", "LOCAL_RECEIPT"})

_REQUIRED_RECORD_FIELDS = (
    "provider",
    "provider_symbol",
    "ltp",
    "received_at",
    "timestamp_source",
    "ts",
)


class ObservationIdentityError(ValueError):
    """Observation record cannot produce a canonical identity."""


def _require_text(name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or value != value.strip()
    ):
        raise ObservationIdentityError(
            f"{name} must be a non-empty trimmed string."
        )
    return value


def _require_aware_utc(name: str, value: object) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ObservationIdentityError(
            f"{name} must be a timezone-aware datetime."
        )
    return value.astimezone(UTC)


def _require_positive_finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ObservationIdentityError(f"{name} must be numeric.")
    f = float(value)
    if f != f or f in (float("inf"), float("-inf")) or f <= 0:
        raise ObservationIdentityError(
            f"{name} must be finite and positive."
        )
    return f


def _canonical_float_token(value: float) -> str:
    # repr() of a Python float is deterministic across 3.11/3.12 and
    # avoids locale or platform issues.
    return repr(float(value))


@dataclass(frozen=True, slots=True)
class ObservationIdentityV1:
    """Canonical identity of one observation.

    All fields are stored as strings so the identity is canonical-JSON
    friendly. The identity does not, by itself, claim the observation is
    new. It is used by the tracker to detect exact structural duplicates.
    """

    provider: str
    provider_symbol: str
    canonical_instrument_id: str
    connection_generation: str
    timestamp_source: str
    anchor_timestamp_iso: str
    ltp_token: str

    schema_version: str = OBSERVATION_IDENTITY_SCHEMA_V1

    def __post_init__(self) -> None:
        _require_text("provider", self.provider)
        _require_text("provider_symbol", self.provider_symbol)
        if not isinstance(self.canonical_instrument_id, str):
            raise ObservationIdentityError(
                "canonical_instrument_id must be a string (may be empty)."
            )
        _require_text("connection_generation", self.connection_generation)
        if self.timestamp_source not in _VALID_TIMESTAMP_SOURCES:
            raise ObservationIdentityError(
                f"unsupported timestamp_source: {self.timestamp_source!r}"
            )
        _require_text("anchor_timestamp_iso", self.anchor_timestamp_iso)
        _require_text("ltp_token", self.ltp_token)
        if self.schema_version != OBSERVATION_IDENTITY_SCHEMA_V1:
            raise ObservationIdentityError(
                "unsupported observation identity schema."
            )

    def canonical_payload(self) -> dict[str, str]:
        return {
            "schema_version": self.schema_version,
            "provider": self.provider,
            "provider_symbol": self.provider_symbol,
            "canonical_instrument_id": self.canonical_instrument_id,
            "connection_generation": self.connection_generation,
            "timestamp_source": self.timestamp_source,
            "anchor_timestamp_iso": self.anchor_timestamp_iso,
            "ltp_token": self.ltp_token,
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.canonical_payload(),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @property
    def identity_sha256(self) -> str:
        return sha256(self.canonical_json().encode("utf-8")).hexdigest()


def build_observation_identity_v1(
    record: Mapping[str, Any],
    *,
    connection_generation: int,
) -> ObservationIdentityV1:
    """Construct an observation identity from a normalized record.

    The record is the shape produced by
    ``FyersStreamingDataProviderV2._normalize_message`` with a
    ``canonical_instrument_id`` injected by the X1 bridge.
    """
    if not isinstance(record, Mapping):
        raise ObservationIdentityError("record must be a mapping.")
    for name in _REQUIRED_RECORD_FIELDS:
        if name not in record:
            raise ObservationIdentityError(
                f"record is missing required field: {name}"
            )

    provider = _require_text("provider", record["provider"])
    provider_symbol = _require_text(
        "provider_symbol", record["provider_symbol"]
    )
    ltp = _require_positive_finite("ltp", record["ltp"])
    _require_aware_utc("received_at", record["received_at"])
    anchor_ts = _require_aware_utc("ts", record["ts"])
    timestamp_source = _require_text(
        "timestamp_source", record["timestamp_source"]
    )
    if timestamp_source not in _VALID_TIMESTAMP_SOURCES:
        raise ObservationIdentityError(
            f"unsupported timestamp_source: {timestamp_source!r}"
        )

    canonical_id = record.get("canonical_instrument_id")
    if canonical_id is None:
        canonical_id = ""
    elif not isinstance(canonical_id, str):
        raise ObservationIdentityError(
            "canonical_instrument_id must be a string or absent."
        )

    if (
        not isinstance(connection_generation, int)
        or isinstance(connection_generation, bool)
        or connection_generation < 0
    ):
        raise ObservationIdentityError(
            "connection_generation must be a non-negative integer."
        )

    return ObservationIdentityV1(
        provider=provider,
        provider_symbol=provider_symbol,
        canonical_instrument_id=canonical_id,
        connection_generation=str(connection_generation),
        timestamp_source=timestamp_source,
        anchor_timestamp_iso=anchor_ts.isoformat(),
        ltp_token=_canonical_float_token(ltp),
    )


__all__ = [
    "OBSERVATION_IDENTITY_SCHEMA_V1",
    "ObservationIdentityError",
    "ObservationIdentityV1",
    "build_observation_identity_v1",
]
