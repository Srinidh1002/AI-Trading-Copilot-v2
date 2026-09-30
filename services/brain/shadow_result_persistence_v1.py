"""Deterministic persistence and exact replay for ShadowBrainResultV1."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from hashlib import sha256
import json
import math
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Mapping

from services.brain.shadow_brain_v1 import (
    ShadowBrainResultV1,
    ShadowHypothesisV1,
)


SHADOW_RESULT_RECORD_SCHEMA_V1 = (
    "BRAIN_SHADOW_RESULT_RECORD_V1"
)

SHADOW_RESULT_SCHEMA_V1 = (
    "BRAIN_SHADOW_RESULT_V1"
)

SHADOW_HYPOTHESIS_SCHEMA_V1 = (
    "BRAIN_SHADOW_HYPOTHESIS_V1"
)


class ShadowResultPersistenceError(
    RuntimeError
):
    """Base error for immutable Shadow result persistence."""


class ShadowResultPersistenceConflictError(
    ShadowResultPersistenceError
):
    """Existing immutable target differs from requested bytes."""


class ShadowResultReplayError(
    ValueError
):
    """Base error for Shadow result record replay."""


class ShadowResultRecordDecodeError(
    ShadowResultReplayError
):
    """Shadow result record cannot be decoded without ambiguity."""


class ShadowResultSchemaError(
    ShadowResultReplayError
):
    """Shadow result record uses an unsupported or malformed schema."""


class ShadowResultIntegrityError(
    ShadowResultReplayError
):
    """Stored and reconstructed Shadow result identities differ."""


_RESULT_AUTHORITY_FIELDS = (
    "execution_authority",
    "decision_authority",
    "risk_authority",
    "position_authority",
    "certification_authority",
)


_RECORD_KEYS = frozenset(
    {
        "record_schema_version",
        "shadow_result_schema_version",
        "shadow_result_sha256",
        "snapshot_sha256",
        "shadow_result_payload",
    }
)


_RESULT_PAYLOAD_KEYS = frozenset(
    {
        "schema_version",
        "market",
        "snapshot_sha256",
        "snapshot_at",
        "generated_at",
        "source_strategy_version",
        "source_policy_epoch",
        "source_runtime_ref",
        "production_coverage_pct",
        "production_complete",
        "missing_production_analyzers",
        "unverified_evidence_ids",
        "stale_evidence_ids",
        "hypothesis",
        "execution_authority",
        "decision_authority",
        "risk_authority",
        "position_authority",
        "certification_authority",
    }
)


_HYPOTHESIS_PAYLOAD_KEYS = frozenset(
    {
        "schema_version",
        "market",
        "hypothesis",
        "confidence",
        "supporting_evidence_ids",
        "opposing_evidence_ids",
        "unknown_evidence_ids",
        "rationale_codes",
    }
)


def _canonical_json(
    value: object,
) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
            ensure_ascii=False,
            allow_nan=False,
        )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ShadowResultIntegrityError(
            "Shadow result payload is not canonical-JSON compatible."
        ) from exc


def _reject_duplicate_pairs(
    pairs: list[
        tuple[
            str,
            Any,
        ]
    ],
) -> dict[
    str,
    Any,
]:
    result: dict[
        str,
        Any,
    ] = {}

    for key, value in pairs:

        if key in result:
            raise ShadowResultRecordDecodeError(
                f"duplicate JSON object key: {key}"
            )

        result[
            key
        ] = value

    return result


def _reject_nonfinite_constant(
    value: str,
) -> None:
    raise ShadowResultRecordDecodeError(
        f"non-finite JSON constant is forbidden: {value}"
    )


def _strict_json_loads(
    text: str,
) -> object:
    if not isinstance(
        text,
        str,
    ):
        raise ShadowResultRecordDecodeError(
            "Shadow result record must be text."
        )

    try:
        return json.loads(
            text,
            object_pairs_hook=
                _reject_duplicate_pairs,
            parse_constant=
                _reject_nonfinite_constant,
        )

    except ShadowResultReplayError:
        raise

    except (
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ) as exc:
        raise ShadowResultRecordDecodeError(
            "Shadow result record is not valid JSON."
        ) from exc


def _require_mapping(
    name: str,
    value: object,
) -> Mapping[
    str,
    object,
]:
    if not isinstance(
        value,
        Mapping,
    ):
        raise ShadowResultRecordDecodeError(
            f"{name} must be a JSON object."
        )

    return value


def _require_exact_keys(
    name: str,
    value: Mapping[
        str,
        object,
    ],
    expected: frozenset[
        str
    ],
) -> None:
    actual = set(
        value
    )

    missing = sorted(
        expected
        - actual
    )

    unknown = sorted(
        actual
        - expected
    )

    if (
        missing
        or unknown
    ):
        raise ShadowResultSchemaError(
            f"{name} keys differ from schema; "
            f"missing={missing}, unknown={unknown}."
        )


def _require_schema(
    name: str,
    value: object,
    expected: str,
) -> str:
    if value != expected:
        raise ShadowResultSchemaError(
            f"{name} must equal {expected!r}."
        )

    return expected


def _require_string(
    name: str,
    value: object,
    *,
    nonempty: bool = True,
    trimmed: bool = False,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise ShadowResultSchemaError(
            f"{name} must be a string."
        )

    if (
        nonempty
        and not value
    ):
        raise ShadowResultSchemaError(
            f"{name} must be non-empty."
        )

    if (
        trimmed
        and value != value.strip()
    ):
        raise ShadowResultSchemaError(
            f"{name} must be trimmed."
        )

    return value


def _require_bool(
    name: str,
    value: object,
) -> bool:
    if type(
        value
    ) is not bool:
        raise ShadowResultSchemaError(
            f"{name} must be boolean."
        )

    return value


def _require_number(
    name: str,
    value: object,
) -> float:
    if (
        isinstance(
            value,
            bool,
        )
        or not isinstance(
            value,
            (
                int,
                float,
            ),
        )
    ):
        raise ShadowResultSchemaError(
            f"{name} must be numeric."
        )

    numeric = float(
        value
    )

    if not math.isfinite(
        numeric
    ):
        raise ShadowResultSchemaError(
            f"{name} must be finite."
        )

    return numeric


def _require_string_tuple(
    name: str,
    value: object,
) -> tuple[
    str,
    ...,
]:
    if not isinstance(
        value,
        list,
    ):
        raise ShadowResultSchemaError(
            f"{name} must be a JSON array."
        )

    converted: list[
        str
    ] = []

    for index, item in enumerate(
        value
    ):
        if not isinstance(
            item,
            str,
        ):
            raise ShadowResultSchemaError(
                f"{name}[{index}] must be a string."
            )

        converted.append(
            item
        )

    return tuple(
        converted
    )


def _require_sha256(
    name: str,
    value: object,
) -> str:
    text = _require_string(
        name,
        value,
    )

    if (
        len(
            text
        ) != 64
        or text != text.lower()
        or any(
            character
            not in "0123456789abcdef"
            for character
            in text
        )
    ):
        raise ShadowResultSchemaError(
            f"{name} must be 64 lowercase hexadecimal characters."
        )

    return text


def _parse_datetime(
    name: str,
    value: object,
) -> datetime:
    text = _require_string(
        name,
        value,
    )

    try:
        parsed = datetime.fromisoformat(
            text
        )

    except ValueError as exc:
        raise ShadowResultSchemaError(
            f"{name} must be an ISO-8601 datetime."
        ) from exc

    if (
        parsed.tzinfo is None
        or parsed.utcoffset()
        is None
    ):
        raise ShadowResultSchemaError(
            f"{name} must be timezone-aware."
        )

    return parsed


def _sha256_text(
    text: str,
) -> str:
    return sha256(
        text.encode(
            "utf-8"
        )
    ).hexdigest()


def _validate_zero_authority_result(
    result: ShadowBrainResultV1,
) -> None:
    for field_name in (
        _RESULT_AUTHORITY_FIELDS
    ):
        if getattr(
            result,
            field_name,
        ) is not False:
            raise ShadowResultIntegrityError(
                f"{field_name} must remain False."
            )


def _revalidate_shadow_result_object(
    result: ShadowBrainResultV1,
) -> ShadowBrainResultV1:
    try:
        validated_hypothesis = replace(
            result.hypothesis
        )

        validated_result = replace(
            result,
            hypothesis=validated_hypothesis,
        )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ShadowResultSchemaError(
            f"invalid ShadowBrainResultV1 object: {exc}"
        ) from exc

    if validated_result != result:
        raise ShadowResultIntegrityError(
            "Shadow result object changes during constructor revalidation."
        )

    if (
        validated_result.canonical_json()
        != result.canonical_json()
    ):
        raise ShadowResultIntegrityError(
            "Shadow result canonical JSON changes during "
            "constructor revalidation."
        )

    return validated_result


def _decode_hypothesis(
    value: object,
) -> ShadowHypothesisV1:
    payload = _require_mapping(
        "shadow_result_payload.hypothesis",
        value,
    )

    _require_exact_keys(
        "shadow_result_payload.hypothesis",
        payload,
        _HYPOTHESIS_PAYLOAD_KEYS,
    )

    _require_schema(
        "shadow_result_payload.hypothesis.schema_version",
        payload[
            "schema_version"
        ],
        SHADOW_HYPOTHESIS_SCHEMA_V1,
    )

    try:
        return ShadowHypothesisV1(
            market=_require_string(
                "hypothesis.market",
                payload[
                    "market"
                ],
            ),
            hypothesis=_require_string(
                "hypothesis.hypothesis",
                payload[
                    "hypothesis"
                ],
            ),
            confidence=_require_number(
                "hypothesis.confidence",
                payload[
                    "confidence"
                ],
            ),
            supporting_evidence_ids=
                _require_string_tuple(
                    "hypothesis.supporting_evidence_ids",
                    payload[
                        "supporting_evidence_ids"
                    ],
                ),
            opposing_evidence_ids=
                _require_string_tuple(
                    "hypothesis.opposing_evidence_ids",
                    payload[
                        "opposing_evidence_ids"
                    ],
                ),
            unknown_evidence_ids=
                _require_string_tuple(
                    "hypothesis.unknown_evidence_ids",
                    payload[
                        "unknown_evidence_ids"
                    ],
                ),
            rationale_codes=
                _require_string_tuple(
                    "hypothesis.rationale_codes",
                    payload[
                        "rationale_codes"
                    ],
                ),
            schema_version=
                SHADOW_HYPOTHESIS_SCHEMA_V1,
        )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ShadowResultSchemaError(
            f"invalid ShadowHypothesisV1 payload: {exc}"
        ) from exc


def _decode_result_payload(
    value: object,
) -> ShadowBrainResultV1:
    payload = _require_mapping(
        "shadow_result_payload",
        value,
    )

    _require_exact_keys(
        "shadow_result_payload",
        payload,
        _RESULT_PAYLOAD_KEYS,
    )

    _require_schema(
        "shadow_result_payload.schema_version",
        payload[
            "schema_version"
        ],
        SHADOW_RESULT_SCHEMA_V1,
    )

    hypothesis = _decode_hypothesis(
        payload[
            "hypothesis"
        ]
    )

    market = _require_string(
        "shadow_result_payload.market",
        payload[
            "market"
        ],
    )

    if hypothesis.market != market:
        raise ShadowResultSchemaError(
            "hypothesis market must match Shadow result market."
        )

    authority_values = {
        field_name:
            _require_bool(
                f"shadow_result_payload.{field_name}",
                payload[
                    field_name
                ],
            )
        for field_name
        in _RESULT_AUTHORITY_FIELDS
    }

    if any(
        authority_values.values()
    ):
        raise ShadowResultSchemaError(
            "Shadow result authorities must all remain False."
        )

    try:
        result = ShadowBrainResultV1(
            market=market,
            snapshot_sha256=
                _require_sha256(
                    "shadow_result_payload.snapshot_sha256",
                    payload[
                        "snapshot_sha256"
                    ],
                ),
            snapshot_at=
                _parse_datetime(
                    "shadow_result_payload.snapshot_at",
                    payload[
                        "snapshot_at"
                    ],
                ),
            generated_at=
                _parse_datetime(
                    "shadow_result_payload.generated_at",
                    payload[
                        "generated_at"
                    ],
                ),
            source_strategy_version=
                _require_string(
                    "shadow_result_payload.source_strategy_version",
                    payload[
                        "source_strategy_version"
                    ],
                    trimmed=True,
                ),
            source_policy_epoch=
                _require_string(
                    "shadow_result_payload.source_policy_epoch",
                    payload[
                        "source_policy_epoch"
                    ],
                    trimmed=True,
                ),
            source_runtime_ref=
                _require_string(
                    "shadow_result_payload.source_runtime_ref",
                    payload[
                        "source_runtime_ref"
                    ],
                    trimmed=True,
                ),
            production_coverage_pct=
                _require_number(
                    "shadow_result_payload.production_coverage_pct",
                    payload[
                        "production_coverage_pct"
                    ],
                ),
            production_complete=
                _require_bool(
                    "shadow_result_payload.production_complete",
                    payload[
                        "production_complete"
                    ],
                ),
            missing_production_analyzers=
                _require_string_tuple(
                    "shadow_result_payload.missing_production_analyzers",
                    payload[
                        "missing_production_analyzers"
                    ],
                ),
            unverified_evidence_ids=
                _require_string_tuple(
                    "shadow_result_payload.unverified_evidence_ids",
                    payload[
                        "unverified_evidence_ids"
                    ],
                ),
            stale_evidence_ids=
                _require_string_tuple(
                    "shadow_result_payload.stale_evidence_ids",
                    payload[
                        "stale_evidence_ids"
                    ],
                ),
            hypothesis=hypothesis,
            execution_authority=False,
            decision_authority=False,
            risk_authority=False,
            position_authority=False,
            certification_authority=False,
            schema_version=
                SHADOW_RESULT_SCHEMA_V1,
        )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ShadowResultSchemaError(
            f"invalid ShadowBrainResultV1 payload: {exc}"
        ) from exc

    _validate_zero_authority_result(
        result
    )

    return result


def shadow_result_record_v1(
    result: ShadowBrainResultV1,
) -> dict[
    str,
    object,
]:
    if not isinstance(
        result,
        ShadowBrainResultV1,
    ):
        raise TypeError(
            "result must be ShadowBrainResultV1."
        )

    _validate_zero_authority_result(
        result
    )

    result = _revalidate_shadow_result_object(
        result
    )

    if (
        result.schema_version
        != SHADOW_RESULT_SCHEMA_V1
    ):
        raise ShadowResultSchemaError(
            "unsupported Shadow result schema."
        )

    if (
        result.hypothesis.schema_version
        != SHADOW_HYPOTHESIS_SCHEMA_V1
    ):
        raise ShadowResultSchemaError(
            "unsupported Shadow hypothesis schema."
        )

    snapshot_sha256 = _require_sha256(
        "result.snapshot_sha256",
        result.snapshot_sha256,
    )

    declared = _require_sha256(
        "result.shadow_result_sha256",
        result.shadow_result_sha256,
    )

    canonical_result = (
        result.canonical_json()
    )

    recomputed = _sha256_text(
        canonical_result
    )

    if recomputed != declared:
        raise ShadowResultIntegrityError(
            "Shadow result object failed its own canonical SHA-256 check."
        )

    payload = result.canonical_payload()

    _require_exact_keys(
        "shadow_result_payload",
        payload,
        _RESULT_PAYLOAD_KEYS,
    )

    if (
        payload[
            "snapshot_sha256"
        ]
        != snapshot_sha256
    ):
        raise ShadowResultIntegrityError(
            "Shadow result payload snapshot SHA-256 does not match "
            "the result snapshot SHA-256."
        )

    return {
        "record_schema_version":
            SHADOW_RESULT_RECORD_SCHEMA_V1,
        "shadow_result_schema_version":
            result.schema_version,
        "shadow_result_sha256":
            declared,
        "snapshot_sha256":
            snapshot_sha256,
        "shadow_result_payload":
            payload,
    }


def serialize_shadow_result_record_v1(
    result: ShadowBrainResultV1,
) -> str:
    return _canonical_json(
        shadow_result_record_v1(
            result
        )
    )


def replay_shadow_result_record_v1(
    record_text: str,
) -> ShadowBrainResultV1:
    record = _require_mapping(
        "shadow_result_record",
        _strict_json_loads(
            record_text
        ),
    )

    _require_exact_keys(
        "shadow_result_record",
        record,
        _RECORD_KEYS,
    )

    _require_schema(
        "record_schema_version",
        record[
            "record_schema_version"
        ],
        SHADOW_RESULT_RECORD_SCHEMA_V1,
    )

    _require_schema(
        "shadow_result_schema_version",
        record[
            "shadow_result_schema_version"
        ],
        SHADOW_RESULT_SCHEMA_V1,
    )

    declared_result_sha256 = (
        _require_sha256(
            "shadow_result_sha256",
            record[
                "shadow_result_sha256"
            ],
        )
    )

    declared_snapshot_sha256 = (
        _require_sha256(
            "snapshot_sha256",
            record[
                "snapshot_sha256"
            ],
        )
    )

    payload = _require_mapping(
        "shadow_result_payload",
        record[
            "shadow_result_payload"
        ],
    )

    _require_exact_keys(
        "shadow_result_payload",
        payload,
        _RESULT_PAYLOAD_KEYS,
    )

    if (
        payload[
            "schema_version"
        ]
        != record[
            "shadow_result_schema_version"
        ]
    ):
        raise ShadowResultSchemaError(
            "record and payload Shadow result schema versions differ."
        )

    payload_snapshot_sha256 = (
        _require_sha256(
            "shadow_result_payload.snapshot_sha256",
            payload[
                "snapshot_sha256"
            ],
        )
    )

    if (
        payload_snapshot_sha256
        != declared_snapshot_sha256
    ):
        raise ShadowResultIntegrityError(
            "record snapshot SHA-256 does not match "
            "Shadow result payload snapshot SHA-256."
        )

    replayed = _decode_result_payload(
        payload
    )

    replayed_result_sha256 = (
        replayed.shadow_result_sha256
    )

    if (
        replayed_result_sha256
        != declared_result_sha256
    ):
        raise ShadowResultIntegrityError(
            "reconstructed ShadowBrainResultV1 SHA-256 does not match "
            "declared shadow_result_sha256."
        )

    if (
        replayed.snapshot_sha256
        != declared_snapshot_sha256
    ):
        raise ShadowResultIntegrityError(
            "reconstructed ShadowBrainResultV1 snapshot SHA-256 "
            "does not match record snapshot SHA-256."
        )

    stored_canonical = _canonical_json(
        payload
    )

    replayed_canonical = (
        replayed.canonical_json()
    )

    if (
        replayed_canonical
        != stored_canonical
    ):
        raise ShadowResultIntegrityError(
            "reconstructed canonical Shadow result JSON differs "
            "from stored canonical payload."
        )

    return replayed


def persist_shadow_result_record_v1(
    result: ShadowBrainResultV1,
    path: str | Path,
) -> Path:
    target = Path(
        path
    )

    data = (
        serialize_shadow_result_record_v1(
            result
        ).encode(
            "utf-8"
        )
    )

    try:
        target.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    except OSError as exc:
        raise ShadowResultPersistenceError(
            f"unable to prepare Shadow result parent directory: "
            f"{target.parent}"
        ) from exc

    if target.exists():

        try:
            existing = target.read_bytes()

        except OSError as exc:
            raise ShadowResultPersistenceError(
                f"unable to read existing Shadow result target: {target}"
            ) from exc

        if existing == data:
            return target

        raise ShadowResultPersistenceConflictError(
            f"Shadow result target already exists with different bytes: "
            f"{target}"
        )

    temporary_path: Path | None = None

    try:
        with NamedTemporaryFile(
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
            os.link(
                temporary_path,
                target,
            )

        except FileExistsError:

            try:
                existing = target.read_bytes()

            except OSError as exc:
                raise ShadowResultPersistenceError(
                    "unable to inspect concurrently published "
                    f"Shadow result target: {target}"
                ) from exc

            if existing != data:
                raise ShadowResultPersistenceConflictError(
                    "Shadow result target appeared concurrently "
                    f"with different bytes: {target}"
                )

        except OSError as exc:
            raise ShadowResultPersistenceError(
                "unable to publish Shadow result without overwrite; "
                f"target={target}"
            ) from exc

        return target

    finally:
        if (
            temporary_path is not None
            and temporary_path.exists()
        ):
            try:
                temporary_path.unlink()

            except OSError:
                pass


def load_shadow_result_record_v1(
    path: str | Path,
) -> ShadowBrainResultV1:
    target = Path(
        path
    )

    try:
        raw = target.read_bytes()

    except OSError as exc:
        raise ShadowResultPersistenceError(
            f"unable to read Shadow result record: {target}"
        ) from exc

    try:
        text = raw.decode(
            "utf-8"
        )

    except UnicodeDecodeError as exc:
        raise ShadowResultRecordDecodeError(
            "Shadow result record is not UTF-8."
        ) from exc

    return replay_shadow_result_record_v1(
        text
    )


__all__ = [
    "SHADOW_RESULT_RECORD_SCHEMA_V1",
    "ShadowResultPersistenceError",
    "ShadowResultPersistenceConflictError",
    "ShadowResultReplayError",
    "ShadowResultRecordDecodeError",
    "ShadowResultSchemaError",
    "ShadowResultIntegrityError",
    "shadow_result_record_v1",
    "serialize_shadow_result_record_v1",
    "replay_shadow_result_record_v1",
    "persist_shadow_result_record_v1",
    "load_shadow_result_record_v1",
]
