"""Immutable X1 observation journal and deterministic offline replay.

Schema version: ``X1_OBSERVATION_RECORD_V1``.
File layout: ``<root>/<session_id>.jsonl`` (one canonical JSON per line).

Fail-closed principles:

* Every line must be canonical JSON. Any deviation in whitespace, key
  order, or non-finite value fails the load.
* Every record carries ``observation_id`` = SHA-256 of its canonical
  payload excluding ``observation_id`` itself. A mismatch fails the load.
* Duplicate ``observation_id`` values within one session file fail the
  load.
* A missing session file is treated as an empty journal, not as an error.
* Corrupt JSON in any line fails the load with an explicit error class.

Bounded storage:

* ``max_records_per_file`` refuses further appends past the cap.
* ``max_file_bytes`` refuses further appends past the cap.
* One file per ``session_id``. No rotation, no compaction, no truncation.

Deterministic replay:

* Replay reads only from disk. It never touches the live streaming adapter
  and never depends on the current wall clock.
* Replay returns records ordered by ``receipt_order_index``.
* An optional ``replay_at`` argument validates that no record's
  ``received_at`` is later than ``replay_at``. This provides an explicit
  replay clock without regenerating any timestamp.

Not claimed:

* No power-loss durability. ``append`` does not fsync.
* No atomic multi-file transactions.
* No compression, no encryption.
"""
from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from services.x1.observation_tracker_v1 import (
    ObservationClassificationV1,
    ObservationQualityV1,
)

OBSERVATION_RECORD_SCHEMA_V1 = "X1_OBSERVATION_RECORD_V1"

_VALID_TIMESTAMP_SOURCES = frozenset({"PROVIDER", "LOCAL_RECEIPT"})
_VALID_QUALITIES = frozenset(q.value for q in ObservationQualityV1)
_SESSION_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ObservationJournalError(RuntimeError):
    """Base class for journal failures."""


class ObservationJournalCorruptError(ObservationJournalError):
    """Journal file is unreadable or contains invalid JSON."""


class ObservationJournalIntegrityError(ObservationJournalError):
    """Journal content fails canonical, hash, or identity checks."""


class ObservationJournalCapacityError(ObservationJournalError):
    """Journal has reached its bounded capacity."""


class ObservationRecordError(ValueError):
    """Input cannot be turned into a valid observation record."""


def _canonical_json(value: object) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise ObservationJournalIntegrityError(
            "journal payload is not canonical-JSON compatible."
        ) from exc


def _require_text(name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or value != value.strip()
    ):
        raise ObservationRecordError(
            f"{name} must be a non-empty trimmed string."
        )
    return value


def _require_optional_text(name: str, value: object) -> str | None:
    if value is None:
        return None
    return _require_text(name, value)


def _require_aware_iso(name: str, value: object) -> str:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ObservationRecordError(
            f"{name} must be a timezone-aware datetime."
        )
    return value.isoformat()


def _require_positive_finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ObservationRecordError(f"{name} must be numeric.")
    f = float(value)
    if f != f or f in (float("inf"), float("-inf")) or f <= 0:
        raise ObservationRecordError(
            f"{name} must be finite and positive."
        )
    return f


def _require_nonneg_int(name: str, value: object) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 0
    ):
        raise ObservationRecordError(
            f"{name} must be a non-negative integer."
        )
    return value


def _parse_iso(name: str, value: object) -> datetime:
    if not isinstance(value, str):
        raise ObservationJournalIntegrityError(
            f"{name} must be ISO-8601 text."
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ObservationJournalIntegrityError(
            f"{name} is not valid ISO-8601."
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ObservationJournalIntegrityError(
            f"{name} must be timezone-aware."
        )
    return parsed


@dataclass(frozen=True, slots=True)
class ObservationRecordV1:
    record_schema_version: str
    observation_id: str
    provider: str
    provider_symbol: str
    canonical_instrument_id: str
    market_symbol: str
    instrument_type: str
    connection_generation: int
    timestamp_source: str
    anchor_timestamp_iso: str
    received_at_iso: str
    ltp: float
    quality: str
    reason_code: str | None
    receipt_order_index: int
    processing_order_index: int
    session_id: str

    def __post_init__(self) -> None:
        if self.record_schema_version != OBSERVATION_RECORD_SCHEMA_V1:
            raise ObservationRecordError(
                "unsupported observation record schema."
            )
        _require_text("provider", self.provider)
        _require_text("provider_symbol", self.provider_symbol)
        _require_text("market_symbol", self.market_symbol)
        _require_text("instrument_type", self.instrument_type)
        _require_nonneg_int(
            "connection_generation", self.connection_generation
        )
        if self.timestamp_source not in _VALID_TIMESTAMP_SOURCES:
            raise ObservationRecordError(
                f"unsupported timestamp_source: "
                f"{self.timestamp_source!r}"
            )
        _parse_iso("anchor_timestamp_iso", self.anchor_timestamp_iso)
        _parse_iso("received_at_iso", self.received_at_iso)
        _require_positive_finite("ltp", self.ltp)
        if self.quality not in _VALID_QUALITIES:
            raise ObservationRecordError(
                f"unsupported quality: {self.quality!r}"
            )
        _require_optional_text("reason_code", self.reason_code)
        _require_nonneg_int(
            "receipt_order_index", self.receipt_order_index
        )
        _require_nonneg_int(
            "processing_order_index", self.processing_order_index
        )
        if not _SESSION_ID_RE.fullmatch(self.session_id):
            raise ObservationRecordError(
                "session_id must use canonical YYYY-MM-DD."
            )
        declared = self.observation_id
        if (
            not isinstance(declared, str)
            or len(declared) != 64
            or declared != declared.lower()
        ):
            raise ObservationRecordError(
                "observation_id must be 64 lowercase hex characters."
            )
        try:
            int(declared, 16)
        except ValueError as exc:
            raise ObservationRecordError(
                "observation_id must be hexadecimal."
            ) from exc
        if declared != self._compute_observation_id():
            raise ObservationRecordError(
                "observation_id does not match canonical payload."
            )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "record_schema_version": self.record_schema_version,
            "provider": self.provider,
            "provider_symbol": self.provider_symbol,
            "canonical_instrument_id": self.canonical_instrument_id,
            "market_symbol": self.market_symbol,
            "instrument_type": self.instrument_type,
            "connection_generation": self.connection_generation,
            "timestamp_source": self.timestamp_source,
            "anchor_timestamp_iso": self.anchor_timestamp_iso,
            "received_at_iso": self.received_at_iso,
            "ltp": float(self.ltp),
            "quality": self.quality,
            "reason_code": self.reason_code,
            "receipt_order_index": self.receipt_order_index,
            "processing_order_index": self.processing_order_index,
            "session_id": self.session_id,
        }

    def to_dict(self) -> dict[str, object]:
        payload = self.canonical_payload()
        payload["observation_id"] = self.observation_id
        return payload

    def canonical_json(self) -> str:
        return _canonical_json(self.to_dict())

    def _compute_observation_id(self) -> str:
        return sha256(
            _canonical_json(self.canonical_payload()).encode("utf-8")
        ).hexdigest()


def build_observation_record_v1(
    *,
    record: Mapping[str, Any],
    classification: ObservationClassificationV1,
    receipt_order_index: int,
    session_id: str,
) -> ObservationRecordV1:
    if not isinstance(record, Mapping):
        raise ObservationRecordError("record must be a mapping.")
    if not isinstance(classification, ObservationClassificationV1):
        raise ObservationRecordError(
            "classification must be ObservationClassificationV1."
        )
    _require_nonneg_int("receipt_order_index", receipt_order_index)
    if not _SESSION_ID_RE.fullmatch(session_id):
        raise ObservationRecordError(
            "session_id must use canonical YYYY-MM-DD."
        )

    provider = _require_text("provider", record.get("provider"))
    provider_symbol = _require_text(
        "provider_symbol", record.get("provider_symbol")
    )
    market_symbol = _require_text(
        "market_symbol", record.get("market_symbol")
    )
    instrument_type = _require_text(
        "instrument_type", record.get("instrument_type")
    )
    canonical_id = record.get("canonical_instrument_id")
    if canonical_id is None:
        canonical_id = ""
    elif not isinstance(canonical_id, str):
        raise ObservationRecordError(
            "canonical_instrument_id must be a string or absent."
        )
    connection_generation = record.get("connection_generation")
    if connection_generation is None:
        connection_generation = 0
    connection_generation = _require_nonneg_int(
        "connection_generation", connection_generation
    )
    timestamp_source = _require_text(
        "timestamp_source", record.get("timestamp_source")
    )
    anchor_iso = _require_aware_iso("ts", record.get("ts"))
    received_iso = _require_aware_iso(
        "received_at", record.get("received_at")
    )
    ltp = _require_positive_finite("ltp", record.get("ltp"))

    quality = classification.quality.value
    reason_code = classification.reason_code
    processing_index = classification.observation_index

    provisional_payload = {
        "record_schema_version": OBSERVATION_RECORD_SCHEMA_V1,
        "provider": provider,
        "provider_symbol": provider_symbol,
        "canonical_instrument_id": canonical_id,
        "market_symbol": market_symbol,
        "instrument_type": instrument_type,
        "connection_generation": int(connection_generation),
        "timestamp_source": timestamp_source,
        "anchor_timestamp_iso": anchor_iso,
        "received_at_iso": received_iso,
        "ltp": float(ltp),
        "quality": quality,
        "reason_code": reason_code,
        "receipt_order_index": receipt_order_index,
        "processing_order_index": processing_index,
        "session_id": session_id,
    }
    observation_id = sha256(
        _canonical_json(provisional_payload).encode("utf-8")
    ).hexdigest()

    return ObservationRecordV1(
        record_schema_version=OBSERVATION_RECORD_SCHEMA_V1,
        observation_id=observation_id,
        provider=provider,
        provider_symbol=provider_symbol,
        canonical_instrument_id=canonical_id,
        market_symbol=market_symbol,
        instrument_type=instrument_type,
        connection_generation=int(connection_generation),
        timestamp_source=timestamp_source,
        anchor_timestamp_iso=anchor_iso,
        received_at_iso=received_iso,
        ltp=float(ltp),
        quality=quality,
        reason_code=reason_code,
        receipt_order_index=receipt_order_index,
        processing_order_index=processing_index,
        session_id=session_id,
    )


class ObservationJournalV1:
    """Append-only on-disk journal of observation records."""

    data_only = True
    order_capability_allowed = False
    automatic_fallback_allowed = False

    def __init__(
        self,
        root: str | Path,
        *,
        session_id: str,
        max_records_per_file: int = 100_000,
        max_file_bytes: int = 256 * 1024 * 1024,
    ) -> None:
        if not _SESSION_ID_RE.fullmatch(session_id or ""):
            raise ValueError(
                "session_id must use canonical YYYY-MM-DD."
            )
        if (
            not isinstance(max_records_per_file, int)
            or isinstance(max_records_per_file, bool)
            or max_records_per_file < 1
        ):
            raise ValueError(
                "max_records_per_file must be a positive integer."
            )
        if (
            not isinstance(max_file_bytes, int)
            or isinstance(max_file_bytes, bool)
            or max_file_bytes < 1
        ):
            raise ValueError(
                "max_file_bytes must be a positive integer."
            )
        self._root = Path(root)
        self._session_id = session_id
        self._max_records = max_records_per_file
        self._max_bytes = max_file_bytes
        self._path = self._root / f"{session_id}.jsonl"

    @property
    def root(self) -> Path:
        return self._root

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def path(self) -> Path:
        return self._path

    def append(self, record: ObservationRecordV1) -> None:
        if not isinstance(record, ObservationRecordV1):
            raise TypeError("record must be ObservationRecordV1.")
        if record.session_id != self._session_id:
            raise ObservationRecordError(
                "record session_id does not match journal session_id."
            )
        self._root.mkdir(parents=True, exist_ok=True)
        existing_bytes = (
            self._path.stat().st_size if self._path.exists() else 0
        )
        existing_records = self._count_records()
        if existing_records >= self._max_records:
            raise ObservationJournalCapacityError(
                "OBSERVATION_JOURNAL_RECORD_CAP_EXCEEDED"
            )
        line = record.canonical_json() + "\n"
        line_bytes = len(line.encode("utf-8"))
        if existing_bytes + line_bytes > self._max_bytes:
            raise ObservationJournalCapacityError(
                "OBSERVATION_JOURNAL_BYTE_CAP_EXCEEDED"
            )
        flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
        fd = os.open(self._path, flags, 0o644)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)

    def load(
        self,
        *,
        replay_at: datetime | None = None,
    ) -> tuple[ObservationRecordV1, ...]:
        if replay_at is not None and (
            not isinstance(replay_at, datetime)
            or replay_at.tzinfo is None
            or replay_at.utcoffset() is None
        ):
            raise ValueError("replay_at must be timezone-aware.")
        if not self._path.exists():
            return ()
        try:
            raw = self._path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ObservationJournalError(
                f"unable to read journal: {self._path}"
            ) from exc
        records: list[ObservationRecordV1] = []
        seen_ids: set[str] = set()
        for lineno, line in enumerate(raw.splitlines(), start=1):
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ObservationJournalCorruptError(
                    f"journal line {lineno} is not valid JSON."
                ) from exc
            if not isinstance(payload, dict):
                raise ObservationJournalIntegrityError(
                    f"journal line {lineno} is not a JSON object."
                )
            if _canonical_json(payload) != line:
                raise ObservationJournalIntegrityError(
                    f"journal line {lineno} is not canonical."
                )
            record = self._record_from_dict(payload)
            if record.observation_id in seen_ids:
                raise ObservationJournalIntegrityError(
                    f"duplicate observation_id at line {lineno}."
                )
            seen_ids.add(record.observation_id)
            if replay_at is not None:
                received = _parse_iso(
                    "received_at_iso", record.received_at_iso
                )
                if received > replay_at:
                    raise ObservationJournalIntegrityError(
                        f"record at line {lineno} was received after "
                        f"replay_at."
                    )
            records.append(record)
        records.sort(
            key=lambda r: (r.receipt_order_index, r.processing_order_index)
        )
        return tuple(records)

    def _count_records(self) -> int:
        if not self._path.exists():
            return 0
        try:
            with self._path.open("r", encoding="utf-8") as handle:
                return sum(1 for line in handle if line.strip())
        except OSError as exc:
            raise ObservationJournalError(
                f"unable to count journal records: {self._path}"
            ) from exc

    @staticmethod
    def _record_from_dict(
        payload: Mapping[str, object],
    ) -> ObservationRecordV1:
        try:
            observation_id = payload["observation_id"]
            record = ObservationRecordV1(
                record_schema_version=payload["record_schema_version"],
                observation_id=observation_id,  # type: ignore[arg-type]
                provider=payload["provider"],  # type: ignore[arg-type]
                provider_symbol=payload["provider_symbol"],  # type: ignore[arg-type]
                canonical_instrument_id=payload[
                    "canonical_instrument_id"
                ],  # type: ignore[arg-type]
                market_symbol=payload["market_symbol"],  # type: ignore[arg-type]
                instrument_type=payload["instrument_type"],  # type: ignore[arg-type]
                connection_generation=payload[
                    "connection_generation"
                ],  # type: ignore[arg-type]
                timestamp_source=payload["timestamp_source"],  # type: ignore[arg-type]
                anchor_timestamp_iso=payload[
                    "anchor_timestamp_iso"
                ],  # type: ignore[arg-type]
                received_at_iso=payload[
                    "received_at_iso"
                ],  # type: ignore[arg-type]
                ltp=payload["ltp"],  # type: ignore[arg-type]
                quality=payload["quality"],  # type: ignore[arg-type]
                reason_code=payload.get("reason_code"),  # type: ignore[arg-type]
                receipt_order_index=payload[
                    "receipt_order_index"
                ],  # type: ignore[arg-type]
                processing_order_index=payload[
                    "processing_order_index"
                ],  # type: ignore[arg-type]
                session_id=payload["session_id"],  # type: ignore[arg-type]
            )
        except KeyError as exc:
            raise ObservationJournalIntegrityError(
                f"journal record missing field: {exc}"
            ) from exc
        except ObservationRecordError as exc:
            raise ObservationJournalIntegrityError(
                f"invalid journal record: {exc}"
            ) from exc
        return record


__all__ = [
    "OBSERVATION_RECORD_SCHEMA_V1",
    "ObservationJournalCapacityError",
    "ObservationJournalCorruptError",
    "ObservationJournalError",
    "ObservationJournalIntegrityError",
    "ObservationJournalV1",
    "ObservationRecordError",
    "ObservationRecordV1",
    "build_observation_record_v1",
]
