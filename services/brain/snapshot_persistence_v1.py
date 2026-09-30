"""Deterministic persistence and exact replay for MarketSnapshotV1.

The record is self-verifying:

1. the stored canonical snapshot payload must reproduce its declared
   snapshot SHA-256;
2. replay reconstructs EvidenceV1 / AnalyzerResultV1 / MarketSnapshotV1;
3. the reconstructed MarketSnapshotV1 must reproduce the same SHA-256;
4. the reconstructed canonical JSON must equal the stored canonical payload.

This provides deterministic integrity checking. It is not a digital signature
and does not establish adversarial authenticity.

No provider, broker, execution, risk, position, certification, or policy
authority exists in this module.
"""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping

from services.brain.market_snapshot_v1 import (
    MarketSnapshotV1,
)
from services.contracts.brain_evidence_v1 import (
    AnalyzerResultV1,
    EvidenceV1,
)


SNAPSHOT_RECORD_SCHEMA_V1 = "BRAIN_SNAPSHOT_RECORD_V1"
SNAPSHOT_SCHEMA_V1 = "BRAIN_MARKET_SNAPSHOT_V1"
ANALYZER_RESULT_SCHEMA_V1 = "BRAIN_ANALYZER_RESULT_V1"
EVIDENCE_SCHEMA_V1 = "BRAIN_EVIDENCE_V1"
REGISTRY_SCHEMA_V1 = "BRAIN_ANALYZER_REGISTRY_V1"


class SnapshotPersistenceError(RuntimeError):
    """Base class for persistence failures."""


class SnapshotPersistenceConflictError(
    SnapshotPersistenceError
):
    """Target exists with bytes different from the requested snapshot."""


class SnapshotReplayError(ValueError):
    """Base class for snapshot record replay failures."""


class SnapshotRecordDecodeError(
    SnapshotReplayError
):
    """Record cannot be decoded without ambiguity."""


class SnapshotSchemaError(
    SnapshotReplayError
):
    """Record uses an unsupported or invalid schema."""


class SnapshotIntegrityError(
    SnapshotReplayError
):
    """Stored and recomputed snapshot identities do not match."""


def _require_mapping(
    name: str,
    value: object,
) -> Mapping[str, Any]:
    if not isinstance(
        value,
        dict,
    ):
        raise SnapshotRecordDecodeError(
            f"{name} must be a JSON object."
        )

    return value


def _require_exact_keys(
    name: str,
    value: Mapping[str, Any],
    expected: set[str],
) -> None:
    actual = set(
        value
    )

    if actual != expected:
        missing = sorted(
            expected - actual
        )

        extra = sorted(
            actual - expected
        )

        raise SnapshotSchemaError(
            f"{name} keys mismatch; "
            f"missing={missing}, extra={extra}"
        )


def _require_list(
    name: str,
    value: object,
) -> list[Any]:
    if not isinstance(
        value,
        list,
    ):
        raise SnapshotRecordDecodeError(
            f"{name} must be a JSON array."
        )

    return value


def _require_string_list(
    name: str,
    value: object,
) -> tuple[str, ...]:
    values = _require_list(
        name,
        value,
    )

    if any(
        not isinstance(
            item,
            str,
        )
        for item in values
    ):
        raise SnapshotRecordDecodeError(
            f"{name} must contain only strings."
        )

    return tuple(
        values
    )


def _require_false(
    name: str,
    value: object,
) -> None:
    if value is not False:
        raise SnapshotSchemaError(
            f"{name} must be false."
        )


def _require_schema(
    name: str,
    value: object,
    expected: str,
) -> None:
    if value != expected:
        raise SnapshotSchemaError(
            f"{name} must be {expected!r}; got {value!r}."
        )


def _parse_datetime(
    name: str,
    value: object,
) -> datetime:
    if not isinstance(
        value,
        str,
    ):
        raise SnapshotRecordDecodeError(
            f"{name} must be an ISO-8601 string."
        )

    normalized = (
        value[:-1] + "+00:00"
        if value.endswith(
            "Z"
        )
        else value
    )

    try:
        parsed = datetime.fromisoformat(
            normalized
        )

    except ValueError as exc:
        raise SnapshotRecordDecodeError(
            f"{name} is not valid ISO-8601."
        ) from exc

    if (
        parsed.tzinfo is None
        or parsed.utcoffset() is None
    ):
        raise SnapshotRecordDecodeError(
            f"{name} must be timezone-aware."
        )

    return parsed


def _reject_duplicate_pairs(
    pairs: list[
        tuple[
            str,
            Any,
        ]
    ],
) -> dict[str, Any]:
    result: dict[str, Any] = {}

    for key, value in pairs:
        if key in result:
            raise SnapshotRecordDecodeError(
                f"duplicate JSON object key: {key}"
            )

        result[
            key
        ] = value

    return result


def _reject_nonfinite_constant(
    value: str,
) -> None:
    raise SnapshotRecordDecodeError(
        f"non-finite JSON constant is forbidden: {value}"
    )


def _strict_json_loads(
    text: str,
) -> Any:
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_nonfinite_constant,
        )

    except SnapshotReplayError:
        raise

    except (
        json.JSONDecodeError,
        TypeError,
    ) as exc:
        raise SnapshotRecordDecodeError(
            "snapshot record is not valid JSON."
        ) from exc


def _canonical_json(
    value: object,
) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(
                ",",
                ":",
            ),
            sort_keys=True,
        )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise SnapshotRecordDecodeError(
            "snapshot payload is not canonical-JSON compatible."
        ) from exc


def _payload_sha256(
    payload: object,
) -> str:
    return sha256(
        _canonical_json(
            payload
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def _require_sha256(
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or len(
            value
        )
        != 64
        or value
        != value.lower()
    ):
        raise SnapshotSchemaError(
            "snapshot_sha256 must be 64 lowercase hex characters."
        )

    try:
        int(
            value,
            16,
        )

    except ValueError as exc:
        raise SnapshotSchemaError(
            "snapshot_sha256 must be hexadecimal."
        ) from exc

    return value


_EVIDENCE_KEYS = {
    "schema_version",
    "evidence_id",
    "market",
    "analyzer",
    "analyzer_version",
    "category",
    "feature",
    "observed_at",
    "generated_at",
    "status",
    "freshness",
    "source",
    "value",
    "unit",
    "direction",
    "strength",
    "confidence",
    "quality_score",
    "source_authoritative",
    "missing_reason",
    "blockers",
    "warnings",
    "metadata",
}


_ANALYZER_RESULT_KEYS = {
    "schema_version",
    "result_id",
    "market",
    "analyzer",
    "analyzer_version",
    "generated_at",
    "status",
    "evidence",
    "blockers",
    "warnings",
    "execution_authority",
}


_SNAPSHOT_PAYLOAD_KEYS = {
    "schema_version",
    "market",
    "snapshot_at",
    "generated_at",
    "registry_schema_version",
    "expected_production_analyzers",
    "source_strategy_version",
    "source_policy_epoch",
    "source_runtime_ref",
    "analyzer_results",
    "execution_authority",
    "decision_authority",
    "risk_authority",
    "position_authority",
    "certification_authority",
}


_RECORD_KEYS = {
    "record_schema_version",
    "snapshot_schema_version",
    "snapshot_sha256",
    "snapshot_payload",
}


def _decode_evidence(
    raw: object,
) -> EvidenceV1:
    payload = _require_mapping(
        "evidence",
        raw,
    )

    _require_exact_keys(
        "evidence",
        payload,
        _EVIDENCE_KEYS,
    )

    _require_schema(
        "evidence.schema_version",
        payload[
            "schema_version"
        ],
        EVIDENCE_SCHEMA_V1,
    )

    metadata = _require_mapping(
        "evidence.metadata",
        payload[
            "metadata"
        ],
    )

    blockers = _require_string_list(
        "evidence.blockers",
        payload[
            "blockers"
        ],
    )

    warnings = _require_string_list(
        "evidence.warnings",
        payload[
            "warnings"
        ],
    )

    try:
        return EvidenceV1(
            evidence_id=payload[
                "evidence_id"
            ],
            market=payload[
                "market"
            ],
            analyzer=payload[
                "analyzer"
            ],
            analyzer_version=payload[
                "analyzer_version"
            ],
            category=payload[
                "category"
            ],
            feature=payload[
                "feature"
            ],
            observed_at=_parse_datetime(
                "evidence.observed_at",
                payload[
                    "observed_at"
                ],
            ),
            generated_at=_parse_datetime(
                "evidence.generated_at",
                payload[
                    "generated_at"
                ],
            ),
            status=payload[
                "status"
            ],
            freshness=payload[
                "freshness"
            ],
            source=payload[
                "source"
            ],
            value=payload[
                "value"
            ],
            unit=payload[
                "unit"
            ],
            direction=payload[
                "direction"
            ],
            strength=payload[
                "strength"
            ],
            confidence=payload[
                "confidence"
            ],
            quality_score=payload[
                "quality_score"
            ],
            source_authoritative=payload[
                "source_authoritative"
            ],
            missing_reason=payload[
                "missing_reason"
            ],
            blockers=blockers,
            warnings=warnings,
            metadata=tuple(
                sorted(
                    metadata.items(),
                    key=lambda item: item[
                        0
                    ],
                )
            ),
            schema_version=payload[
                "schema_version"
            ],
        )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise SnapshotSchemaError(
            f"invalid EvidenceV1 payload: {exc}"
        ) from exc


def _decode_analyzer_result(
    raw: object,
) -> AnalyzerResultV1:
    payload = _require_mapping(
        "analyzer_result",
        raw,
    )

    _require_exact_keys(
        "analyzer_result",
        payload,
        _ANALYZER_RESULT_KEYS,
    )

    _require_schema(
        "analyzer_result.schema_version",
        payload[
            "schema_version"
        ],
        ANALYZER_RESULT_SCHEMA_V1,
    )

    _require_false(
        "analyzer_result.execution_authority",
        payload[
            "execution_authority"
        ],
    )

    evidence_payloads = _require_list(
        "analyzer_result.evidence",
        payload[
            "evidence"
        ],
    )

    evidence = tuple(
        _decode_evidence(
            item
        )
        for item in evidence_payloads
    )

    blockers = _require_string_list(
        "analyzer_result.blockers",
        payload[
            "blockers"
        ],
    )

    warnings = _require_string_list(
        "analyzer_result.warnings",
        payload[
            "warnings"
        ],
    )

    try:
        return AnalyzerResultV1(
            result_id=payload[
                "result_id"
            ],
            market=payload[
                "market"
            ],
            analyzer=payload[
                "analyzer"
            ],
            analyzer_version=payload[
                "analyzer_version"
            ],
            generated_at=_parse_datetime(
                "analyzer_result.generated_at",
                payload[
                    "generated_at"
                ],
            ),
            status=payload[
                "status"
            ],
            evidence=evidence,
            blockers=blockers,
            warnings=warnings,
            execution_authority=False,
            schema_version=payload[
                "schema_version"
            ],
        )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise SnapshotSchemaError(
            f"invalid AnalyzerResultV1 payload: {exc}"
        ) from exc


def _decode_snapshot_payload(
    raw: object,
) -> MarketSnapshotV1:
    payload = _require_mapping(
        "snapshot_payload",
        raw,
    )

    _require_exact_keys(
        "snapshot_payload",
        payload,
        _SNAPSHOT_PAYLOAD_KEYS,
    )

    _require_schema(
        "snapshot_payload.schema_version",
        payload[
            "schema_version"
        ],
        SNAPSHOT_SCHEMA_V1,
    )

    _require_schema(
        "snapshot_payload.registry_schema_version",
        payload[
            "registry_schema_version"
        ],
        REGISTRY_SCHEMA_V1,
    )

    for authority in (
        "execution_authority",
        "decision_authority",
        "risk_authority",
        "position_authority",
        "certification_authority",
    ):
        _require_false(
            f"snapshot_payload.{authority}",
            payload[
                authority
            ],
        )

    analyzer_payloads = _require_list(
        "snapshot_payload.analyzer_results",
        payload[
            "analyzer_results"
        ],
    )

    analyzer_results = tuple(
        _decode_analyzer_result(
            item
        )
        for item in analyzer_payloads
    )

    expected = _require_string_list(
        "snapshot_payload.expected_production_analyzers",
        payload[
            "expected_production_analyzers"
        ],
    )

    try:
        return MarketSnapshotV1(
            market=payload[
                "market"
            ],
            snapshot_at=_parse_datetime(
                "snapshot_payload.snapshot_at",
                payload[
                    "snapshot_at"
                ],
            ),
            generated_at=_parse_datetime(
                "snapshot_payload.generated_at",
                payload[
                    "generated_at"
                ],
            ),
            analyzer_results=analyzer_results,
            expected_production_analyzers=expected,
            registry_schema_version=payload[
                "registry_schema_version"
            ],
            source_strategy_version=payload[
                "source_strategy_version"
            ],
            source_policy_epoch=payload[
                "source_policy_epoch"
            ],
            source_runtime_ref=payload[
                "source_runtime_ref"
            ],
            execution_authority=False,
            decision_authority=False,
            risk_authority=False,
            position_authority=False,
            certification_authority=False,
            schema_version=payload[
                "schema_version"
            ],
        )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise SnapshotSchemaError(
            f"invalid MarketSnapshotV1 payload: {exc}"
        ) from exc


def snapshot_record_v1(
    snapshot: MarketSnapshotV1,
) -> dict[str, object]:
    if not isinstance(
        snapshot,
        MarketSnapshotV1,
    ):
        raise TypeError(
            "snapshot must be MarketSnapshotV1."
        )

    payload = snapshot.canonical_payload()

    declared = snapshot.snapshot_sha256

    recomputed = _payload_sha256(
        payload
    )

    if recomputed != declared:
        raise SnapshotIntegrityError(
            "snapshot object failed its own canonical SHA-256 check."
        )

    return {
        "record_schema_version":
            SNAPSHOT_RECORD_SCHEMA_V1,

        "snapshot_schema_version":
            snapshot.schema_version,

        "snapshot_sha256":
            declared,

        "snapshot_payload":
            payload,
    }


def serialize_snapshot_record_v1(
    snapshot: MarketSnapshotV1,
) -> str:
    return (
        _canonical_json(
            snapshot_record_v1(
                snapshot
            )
        )
        + "\n"
    )


def replay_snapshot_record_v1(
    record_text: str,
) -> MarketSnapshotV1:
    if not isinstance(
        record_text,
        str,
    ):
        raise SnapshotRecordDecodeError(
            "snapshot record must be text."
        )

    record = _require_mapping(
        "snapshot_record",
        _strict_json_loads(
            record_text
        ),
    )

    _require_exact_keys(
        "snapshot_record",
        record,
        _RECORD_KEYS,
    )

    _require_schema(
        "record_schema_version",
        record[
            "record_schema_version"
        ],
        SNAPSHOT_RECORD_SCHEMA_V1,
    )

    _require_schema(
        "snapshot_schema_version",
        record[
            "snapshot_schema_version"
        ],
        SNAPSHOT_SCHEMA_V1,
    )

    declared_hash = _require_sha256(
        record[
            "snapshot_sha256"
        ]
    )

    payload = _require_mapping(
        "snapshot_payload",
        record[
            "snapshot_payload"
        ],
    )

    if (
        payload.get(
            "schema_version"
        )
        != record[
            "snapshot_schema_version"
        ]
    ):
        raise SnapshotSchemaError(
            "record and payload snapshot schema versions differ."
        )

    stored_payload_hash = _payload_sha256(
        payload
    )

    if stored_payload_hash != declared_hash:
        raise SnapshotIntegrityError(
            "stored canonical payload SHA-256 does not match "
            "snapshot_sha256."
        )

    replayed = _decode_snapshot_payload(
        payload
    )

    replayed_hash = replayed.snapshot_sha256

    if replayed_hash != declared_hash:
        raise SnapshotIntegrityError(
            "reconstructed MarketSnapshotV1 SHA-256 does not match "
            "snapshot_sha256."
        )

    stored_canonical = _canonical_json(
        payload
    )

    replayed_canonical = replayed.canonical_json()

    if replayed_canonical != stored_canonical:
        raise SnapshotIntegrityError(
            "reconstructed canonical snapshot JSON differs from "
            "stored canonical payload."
        )

    return replayed


def persist_snapshot_record_v1(
    snapshot: MarketSnapshotV1,
    path: str | Path,
) -> Path:
    """Persist one deterministic snapshot record.

    Existing identical content is idempotent.

    Existing different content is rejected rather than silently overwritten.
    """

    target = Path(
        path
    )

    data = serialize_snapshot_record_v1(
        snapshot
    ).encode(
        "utf-8"
    )

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if target.exists():
        existing = target.read_bytes()

        if existing == data:
            return target

        raise SnapshotPersistenceConflictError(
            f"snapshot target already exists with different bytes: {target}"
        )

    temporary_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(
                handle.name
            )

            handle.write(
                data
            )

            handle.flush()

            os.fsync(
                handle.fileno()
            )

        try:
            # Publish without overwrite.
            #
            # The temporary file is created in the target directory, so the
            # hard-link operation stays on the same filesystem.  Creating the
            # target link is atomic with respect to target-name existence:
            # another writer that wins the name first causes FileExistsError
            # rather than allowing us to overwrite its record.
            os.link(
                temporary_path,
                target,
            )

        except FileExistsError:
            existing = target.read_bytes()

            if existing == data:
                return target

            raise SnapshotPersistenceConflictError(
                f"snapshot target appeared with different bytes: {target}"
            )

        except OSError as exc:
            raise SnapshotPersistenceError(
                "unable to publish snapshot without overwrite; "
                f"target={target}"
            ) from exc

        return target

    finally:
        if (
            temporary_path is not None
            and temporary_path.exists()
        ):
            temporary_path.unlink()


def load_snapshot_record_v1(
    path: str | Path,
) -> MarketSnapshotV1:
    target = Path(
        path
    )

    try:
        raw = target.read_bytes()

    except OSError as exc:
        raise SnapshotPersistenceError(
            f"unable to read snapshot record: {target}"
        ) from exc

    try:
        text = raw.decode(
            "utf-8"
        )

    except UnicodeDecodeError as exc:
        raise SnapshotRecordDecodeError(
            "snapshot record is not valid UTF-8."
        ) from exc

    return replay_snapshot_record_v1(
        text
    )


__all__ = [
    "ANALYZER_RESULT_SCHEMA_V1",
    "EVIDENCE_SCHEMA_V1",
    "REGISTRY_SCHEMA_V1",
    "SNAPSHOT_RECORD_SCHEMA_V1",
    "SNAPSHOT_SCHEMA_V1",
    "SnapshotIntegrityError",
    "SnapshotPersistenceConflictError",
    "SnapshotPersistenceError",
    "SnapshotRecordDecodeError",
    "SnapshotReplayError",
    "SnapshotSchemaError",
    "load_snapshot_record_v1",
    "persist_snapshot_record_v1",
    "replay_snapshot_record_v1",
    "serialize_snapshot_record_v1",
    "snapshot_record_v1",
]