"""Immutable journal for snapshot-bound ShadowBrainResultV1 records.

Publication claims the immutable slot before writing its result, then publishes
the manifest last. An interrupted capture is incomplete and fails verification;
an exact retry may finish it, but a different result cannot take over its slot.
Readers require exact slot/manifest/record accounting and may fail closed while
a writer is publishing. Verification should be retried after writers quiesce.
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
from tempfile import NamedTemporaryFile
from typing import Any

from services.brain.market_snapshot_v1 import (
    MarketSnapshotV1,
)
from services.brain.shadow_brain_v1 import (
    ShadowBrainResultV1,
)
from services.brain.shadow_result_persistence_v1 import (
    ShadowResultPersistenceError,
    load_shadow_result_record_v1,
    persist_shadow_result_record_v1,
    serialize_shadow_result_record_v1,
)

SHADOW_RESULT_JOURNAL_SLOT_SCHEMA_V1 = (
    "BRAIN_SHADOW_RESULT_JOURNAL_SLOT_V1"
)

SHADOW_RESULT_JOURNAL_ENTRY_SCHEMA_V1 = (
    "BRAIN_SHADOW_RESULT_JOURNAL_ENTRY_V1"
)

SHADOW_RESULT_JOURNAL_MANIFEST_SCHEMA_V1 = (
    "BRAIN_SHADOW_RESULT_JOURNAL_MANIFEST_ENTRY_V1"
)

SHADOW_RESULT_JOURNAL_VERIFICATION_SCHEMA_V1 = (
    "BRAIN_SHADOW_RESULT_JOURNAL_VERIFICATION_V1"
)


class ShadowResultJournalError(
    RuntimeError
):
    """Base error for Shadow result journal operations."""


class ShadowResultJournalConflictError(
    ShadowResultJournalError
):
    """Immutable journal slot already contains different content."""


class ShadowResultJournalReplayError(
    ValueError
):
    """Base error for journal replay or decoding."""


class ShadowResultJournalSchemaError(
    ShadowResultJournalReplayError
):
    """Journal document does not conform to V1 schema."""


class ShadowResultJournalIntegrityError(
    ShadowResultJournalReplayError
):
    """Journal hashes, paths, or cross-bindings are inconsistent."""


_SAFE_COMPONENT_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*$"
)


_SLOT_KEYS = frozenset(
    {
        "slot_schema_version",
        "entry_schema_version",
        "slot_id",
        "slot_sha256",
        "market",
        "session_id",
        "snapshot_at",
        "snapshot_sha256",
        "shadow_result_sha256",
        "record_relpath",
        "source_strategy_version",
        "source_policy_epoch",
        "source_runtime_ref",
    }
)


_MANIFEST_KEYS = frozenset(
    {
        "manifest_schema_version",
        "manifest_sha256",
        "slot_id",
        "market",
        "session_id",
        "snapshot_at",
        "slot_relpath",
        "slot_sha256",
        "record_relpath",
        "snapshot_sha256",
        "shadow_result_sha256",
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
        raise ShadowResultJournalIntegrityError(
            "journal payload is not canonical-JSON compatible."
        ) from exc


def _sha256_text(
    text: str,
) -> str:
    return sha256(
        text.encode(
            "utf-8"
        )
    ).hexdigest()


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
            raise ShadowResultJournalReplayError(
                f"duplicate JSON object key: {key}"
            )

        result[
            key
        ] = value

    return result


def _reject_nonfinite_constant(
    value: str,
) -> None:
    raise ShadowResultJournalReplayError(
        f"non-finite JSON constant is forbidden: {value}"
    )


def _strict_json_loads(
    text: str,
) -> object:
    if not isinstance(
        text,
        str,
    ):
        raise ShadowResultJournalReplayError(
            "journal document must be text."
        )

    try:
        return json.loads(
            text,
            object_pairs_hook=
                _reject_duplicate_pairs,
            parse_constant=
                _reject_nonfinite_constant,
        )

    except ShadowResultJournalReplayError:
        raise

    except (
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ) as exc:
        raise ShadowResultJournalReplayError(
            "journal document is not valid JSON."
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
        raise ShadowResultJournalSchemaError(
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
        raise ShadowResultJournalSchemaError(
            f"{name} keys differ from schema; "
            f"missing={missing}, unknown={unknown}."
        )


def _require_string(
    name: str,
    value: object,
    *,
    trimmed: bool = False,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise ShadowResultJournalSchemaError(
            f"{name} must be a string."
        )

    if not value:
        raise ShadowResultJournalSchemaError(
            f"{name} must be non-empty."
        )

    if (
        trimmed
        and value != value.strip()
    ):
        raise ShadowResultJournalSchemaError(
            f"{name} must be trimmed."
        )

    return value


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
        raise ShadowResultJournalSchemaError(
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
        raise ShadowResultJournalSchemaError(
            f"{name} must be an ISO-8601 datetime."
        ) from exc

    if (
        parsed.tzinfo is None
        or parsed.utcoffset()
        is None
    ):
        raise ShadowResultJournalSchemaError(
            f"{name} must be timezone-aware."
        )

    return parsed


def _require_aware_datetime(
    name: str,
    value: object,
) -> datetime:
    if not isinstance(
        value,
        datetime,
    ):
        raise ShadowResultJournalSchemaError(
            f"{name} must be datetime."
        )

    if (
        value.tzinfo is None
        or value.utcoffset()
        is None
    ):
        raise ShadowResultJournalSchemaError(
            f"{name} must be timezone-aware."
        )

    return value


def _safe_component(
    name: str,
    value: object,
) -> str:
    text = _require_string(
        name,
        value,
        trimmed=True,
    )

    if (
        text in {
            ".",
            "..",
        }
        or not _SAFE_COMPONENT_RE.fullmatch(
            text
        )
    ):
        raise ShadowResultJournalSchemaError(
            f"{name} is not a safe journal path component."
        )

    return text


def _record_relpath(
    shadow_result_sha256: str,
) -> str:
    return (
        "records/"
        + _require_sha256(
            "shadow_result_sha256",
            shadow_result_sha256,
        )
        + ".json"
    )


def _slot_relpath(
    slot_id: str,
) -> str:
    return (
        "slots/"
        + _require_sha256(
            "slot_id",
            slot_id,
        )
        + ".json"
    )


def _manifest_relpath(
    slot_id: str,
) -> str:
    return (
        "manifest/"
        + _require_sha256(
            "slot_id",
            slot_id,
        )
        + ".json"
    )


def shadow_result_journal_slot_id_v1(
    *,
    market: str,
    session_id: str,
    snapshot_at: datetime,
) -> str:
    market_value = _safe_component(
        "market",
        market,
    )

    session_value = _safe_component(
        "session_id",
        session_id,
    )

    stamp = _require_aware_datetime(
        "snapshot_at",
        snapshot_at,
    )

    identity = {
        "slot_schema_version":
            SHADOW_RESULT_JOURNAL_SLOT_SCHEMA_V1,
        "market":
            market_value,
        "session_id":
            session_value,
        "snapshot_at":
            stamp.isoformat(),
    }

    return _sha256_text(
        _canonical_json(
            identity
        )
    )


@dataclass(
    frozen=True,
    slots=True,
)
class ShadowResultJournalEntryV1:
    market: str
    session_id: str
    snapshot_at: datetime

    snapshot_sha256: str
    shadow_result_sha256: str

    record_relpath: str

    source_strategy_version: str
    source_policy_epoch: str
    source_runtime_ref: str

    slot_id: str
    slot_sha256: str

    schema_version: str = (
        SHADOW_RESULT_JOURNAL_ENTRY_SCHEMA_V1
    )

    def __post_init__(
        self,
    ) -> None:
        market = _safe_component(
            "market",
            self.market,
        )

        session_id = _safe_component(
            "session_id",
            self.session_id,
        )

        stamp = _require_aware_datetime(
            "snapshot_at",
            self.snapshot_at,
        )

        snapshot_sha256 = _require_sha256(
            "snapshot_sha256",
            self.snapshot_sha256,
        )

        result_sha256 = _require_sha256(
            "shadow_result_sha256",
            self.shadow_result_sha256,
        )

        slot_id = _require_sha256(
            "slot_id",
            self.slot_id,
        )

        _require_sha256(
            "slot_sha256",
            self.slot_sha256,
        )

        if (
            self.schema_version
            != SHADOW_RESULT_JOURNAL_ENTRY_SCHEMA_V1
        ):
            raise ShadowResultJournalSchemaError(
                "unsupported Shadow journal entry schema."
            )

        if (
            self.record_relpath
            != _record_relpath(
                result_sha256
            )
        ):
            raise ShadowResultJournalIntegrityError(
                "record_relpath is not deterministic for "
                "shadow_result_sha256."
            )

        expected_slot_id = (
            shadow_result_journal_slot_id_v1(
                market=market,
                session_id=session_id,
                snapshot_at=stamp,
            )
        )

        if slot_id != expected_slot_id:
            raise ShadowResultJournalIntegrityError(
                "slot_id does not match market/session/snapshot_at."
            )

        _require_string(
            "source_strategy_version",
            self.source_strategy_version,
            trimmed=True,
        )

        _require_string(
            "source_policy_epoch",
            self.source_policy_epoch,
            trimmed=True,
        )

        _require_string(
            "source_runtime_ref",
            self.source_runtime_ref,
            trimmed=True,
        )

        # Keep local variables intentionally evaluated so validation is
        # explicit and static analyzers see all required fields.
        _ = (
            snapshot_sha256,
            result_sha256,
        )


@dataclass(
    frozen=True,
    slots=True,
)
class ShadowResultJournalVerificationV1:
    market: str
    session_id: str

    entry_count: int

    chronological: bool
    manifest_hashes_verified: bool
    slot_hashes_verified: bool
    records_verified: bool

    schema_version: str = (
        SHADOW_RESULT_JOURNAL_VERIFICATION_SCHEMA_V1
    )

    def __post_init__(
        self,
    ) -> None:
        _safe_component(
            "market",
            self.market,
        )

        _safe_component(
            "session_id",
            self.session_id,
        )

        if (
            isinstance(
                self.entry_count,
                bool,
            )
            or not isinstance(
                self.entry_count,
                int,
            )
            or self.entry_count < 0
        ):
            raise ShadowResultJournalSchemaError(
                "entry_count must be a non-negative integer."
            )

        for name in (
            "chronological",
            "manifest_hashes_verified",
            "slot_hashes_verified",
            "records_verified",
        ):
            if type(
                getattr(
                    self,
                    name,
                )
            ) is not bool:
                raise ShadowResultJournalSchemaError(
                    f"{name} must be boolean."
                )

        if (
            self.schema_version
            != SHADOW_RESULT_JOURNAL_VERIFICATION_SCHEMA_V1
        ):
            raise ShadowResultJournalSchemaError(
                "unsupported Shadow journal verification schema."
            )


def _entry_body(
    entry: ShadowResultJournalEntryV1,
) -> dict[
    str,
    object,
]:
    return {
        "slot_schema_version":
            SHADOW_RESULT_JOURNAL_SLOT_SCHEMA_V1,
        "entry_schema_version":
            entry.schema_version,
        "slot_id":
            entry.slot_id,
        "market":
            entry.market,
        "session_id":
            entry.session_id,
        "snapshot_at":
            entry.snapshot_at.isoformat(),
        "snapshot_sha256":
            entry.snapshot_sha256,
        "shadow_result_sha256":
            entry.shadow_result_sha256,
        "record_relpath":
            entry.record_relpath,
        "source_strategy_version":
            entry.source_strategy_version,
        "source_policy_epoch":
            entry.source_policy_epoch,
        "source_runtime_ref":
            entry.source_runtime_ref,
    }


def _slot_document(
    entry: ShadowResultJournalEntryV1,
) -> dict[
    str,
    object,
]:
    body = _entry_body(
        entry
    )

    expected = _sha256_text(
        _canonical_json(
            body
        )
    )

    if entry.slot_sha256 != expected:
        raise ShadowResultJournalIntegrityError(
            "entry slot_sha256 does not match canonical slot body."
        )

    return {
        **body,
        "slot_sha256":
            entry.slot_sha256,
    }


def _manifest_body(
    entry: ShadowResultJournalEntryV1,
) -> dict[
    str,
    object,
]:
    return {
        "manifest_schema_version":
            SHADOW_RESULT_JOURNAL_MANIFEST_SCHEMA_V1,
        "slot_id":
            entry.slot_id,
        "market":
            entry.market,
        "session_id":
            entry.session_id,
        "snapshot_at":
            entry.snapshot_at.isoformat(),
        "slot_relpath":
            _slot_relpath(
                entry.slot_id
            ),
        "slot_sha256":
            entry.slot_sha256,
        "record_relpath":
            entry.record_relpath,
        "snapshot_sha256":
            entry.snapshot_sha256,
        "shadow_result_sha256":
            entry.shadow_result_sha256,
    }


def _manifest_document(
    entry: ShadowResultJournalEntryV1,
) -> dict[
    str,
    object,
]:
    body = _manifest_body(
        entry
    )

    return {
        **body,
        "manifest_sha256":
            _sha256_text(
                _canonical_json(
                    body
                )
            ),
    }


def _validate_pair(
    snapshot: MarketSnapshotV1,
    result: ShadowBrainResultV1,
) -> None:
    if not isinstance(
        snapshot,
        MarketSnapshotV1,
    ):
        raise TypeError(
            "snapshot must be MarketSnapshotV1."
        )

    if not isinstance(
        result,
        ShadowBrainResultV1,
    ):
        raise TypeError(
            "result must be ShadowBrainResultV1."
        )

    # Re-run the frozen persistence boundary's constructor and hash
    # validation before journal identity is calculated.
    serialize_shadow_result_record_v1(
        result
    )

    exact_pairs = (
        (
            "market",
            snapshot.market,
            result.market,
        ),
        (
            "snapshot_sha256",
            snapshot.snapshot_sha256,
            result.snapshot_sha256,
        ),
        (
            "snapshot_at",
            snapshot.snapshot_at,
            result.snapshot_at,
        ),
        (
            "generated_at",
            snapshot.generated_at,
            result.generated_at,
        ),
        (
            "source_strategy_version",
            snapshot.source_strategy_version,
            result.source_strategy_version,
        ),
        (
            "source_policy_epoch",
            snapshot.source_policy_epoch,
            result.source_policy_epoch,
        ),
        (
            "source_runtime_ref",
            snapshot.source_runtime_ref,
            result.source_runtime_ref,
        ),
        (
            "production_coverage_pct",
            snapshot.production_coverage_pct,
            result.production_coverage_pct,
        ),
        (
            "production_complete",
            snapshot.production_complete,
            result.production_complete,
        ),
        (
            "missing_production_analyzers",
            snapshot.missing_production_analyzers,
            result.missing_production_analyzers,
        ),
    )

    for (
        name,
        snapshot_value,
        result_value,
    ) in exact_pairs:
        if snapshot_value != result_value:
            raise ShadowResultJournalIntegrityError(
                f"snapshot/result {name} must match exactly."
            )


def _build_entry(
    *,
    snapshot: MarketSnapshotV1,
    result: ShadowBrainResultV1,
    session_id: str,
) -> ShadowResultJournalEntryV1:
    _validate_pair(
        snapshot,
        result,
    )

    market = _safe_component(
        "market",
        snapshot.market,
    )

    session_value = _safe_component(
        "session_id",
        session_id,
    )

    slot_id = (
        shadow_result_journal_slot_id_v1(
            market=market,
            session_id=session_value,
            snapshot_at=snapshot.snapshot_at,
        )
    )

    provisional = ShadowResultJournalEntryV1(
        market=market,
        session_id=session_value,
        snapshot_at=snapshot.snapshot_at,
        snapshot_sha256=
            snapshot.snapshot_sha256,
        shadow_result_sha256=
            result.shadow_result_sha256,
        record_relpath=
            _record_relpath(
                result.shadow_result_sha256
            ),
        source_strategy_version=
            result.source_strategy_version,
        source_policy_epoch=
            result.source_policy_epoch,
        source_runtime_ref=
            result.source_runtime_ref,
        slot_id=slot_id,
        slot_sha256=(
            "0"
            * 64
        ),
    )

    body = _entry_body(
        provisional
    )

    slot_sha256 = _sha256_text(
        _canonical_json(
            body
        )
    )

    return ShadowResultJournalEntryV1(
        market=provisional.market,
        session_id=provisional.session_id,
        snapshot_at=provisional.snapshot_at,
        snapshot_sha256=
            provisional.snapshot_sha256,
        shadow_result_sha256=
            provisional.shadow_result_sha256,
        record_relpath=
            provisional.record_relpath,
        source_strategy_version=
            provisional.source_strategy_version,
        source_policy_epoch=
            provisional.source_policy_epoch,
        source_runtime_ref=
            provisional.source_runtime_ref,
        slot_id=provisional.slot_id,
        slot_sha256=slot_sha256,
    )


def _session_root(
    journal_root: str | Path,
    *,
    market: str,
    session_id: str,
) -> Path:
    market_value = _safe_component(
        "market",
        market,
    )

    session_value = _safe_component(
        "session_id",
        session_id,
    )

    root = (
        Path(
            journal_root
        )
        / market_value
        / session_value
    )

    for directory in (Path(journal_root), root.parent, root):
        _require_plain_path(directory, directory=True)
    return root


def _require_plain_path(path: Path, *, directory: bool = False) -> None:
    # Reject dangling links too: exists() alone would treat them as absent.
    if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
        raise ShadowResultJournalIntegrityError(
            f"linked journal artifact is forbidden: {path}"
        )
    if path.exists() and not (path.is_dir() if directory else path.is_file()):
        raise ShadowResultJournalIntegrityError(
            f"unexpected journal artifact type: {path}"
        )


def _read_utf8(
    path: Path,
) -> str:
    try:
        raw = path.read_bytes()

    except OSError as exc:
        raise ShadowResultJournalError(
            f"unable to read journal document: {path}"
        ) from exc

    try:
        return raw.decode(
            "utf-8"
        )

    except UnicodeDecodeError as exc:
        raise ShadowResultJournalReplayError(
            f"journal document is not UTF-8: {path}"
        ) from exc


def _publish_immutable_text(
    path: Path,
    text: str,
) -> Path:
    _require_plain_path(path.parent, directory=True)
    _require_plain_path(path)
    data = text.encode(
        "utf-8"
    )

    try:
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    except OSError as exc:
        raise ShadowResultJournalError(
            f"unable to prepare journal directory: {path.parent}"
        ) from exc

    if path.exists():
        try:
            existing = path.read_bytes()

        except OSError as exc:
            raise ShadowResultJournalError(
                f"unable to inspect existing journal target: {path}"
            ) from exc

        if existing == data:
            return path

        raise ShadowResultJournalConflictError(
            f"journal target already exists with different bytes: {path}"
        )

    temporary_path: Path | None = None

    try:
        with NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
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
                path,
            )

        except FileExistsError:
            try:
                existing = path.read_bytes()

            except OSError as exc:
                raise ShadowResultJournalError(
                    "unable to inspect concurrently published "
                    f"journal target: {path}"
                ) from exc

            if existing != data:
                raise ShadowResultJournalConflictError(
                    "journal target appeared concurrently with "
                    f"different bytes: {path}"
                )

        except OSError as exc:
            raise ShadowResultJournalError(
                "unable to publish journal document without overwrite; "
                f"target={path}"
            ) from exc

        return path

    finally:
        if (
            temporary_path is not None
            and temporary_path.exists()
        ):
            try:
                temporary_path.unlink()

            except OSError:
                pass


def _decode_slot(
    text: str,
) -> ShadowResultJournalEntryV1:
    raw = _strict_json_loads(
        text
    )

    document = _require_mapping(
        "slot",
        raw,
    )

    _require_exact_keys(
        "slot",
        document,
        _SLOT_KEYS,
    )

    if (
        document[
            "slot_schema_version"
        ]
        != SHADOW_RESULT_JOURNAL_SLOT_SCHEMA_V1
    ):
        raise ShadowResultJournalSchemaError(
            "unsupported Shadow journal slot schema."
        )

    if (
        document[
            "entry_schema_version"
        ]
        != SHADOW_RESULT_JOURNAL_ENTRY_SCHEMA_V1
    ):
        raise ShadowResultJournalSchemaError(
            "unsupported Shadow journal entry schema."
        )

    canonical_document = _canonical_json(
        document
    )

    if canonical_document != text:
        raise ShadowResultJournalIntegrityError(
            "slot JSON is not canonical."
        )

    entry = ShadowResultJournalEntryV1(
        market=_require_string(
            "slot.market",
            document[
                "market"
            ],
        ),
        session_id=_require_string(
            "slot.session_id",
            document[
                "session_id"
            ],
        ),
        snapshot_at=_parse_datetime(
            "slot.snapshot_at",
            document[
                "snapshot_at"
            ],
        ),
        snapshot_sha256=_require_sha256(
            "slot.snapshot_sha256",
            document[
                "snapshot_sha256"
            ],
        ),
        shadow_result_sha256=_require_sha256(
            "slot.shadow_result_sha256",
            document[
                "shadow_result_sha256"
            ],
        ),
        record_relpath=_require_string(
            "slot.record_relpath",
            document[
                "record_relpath"
            ],
        ),
        source_strategy_version=_require_string(
            "slot.source_strategy_version",
            document[
                "source_strategy_version"
            ],
        ),
        source_policy_epoch=_require_string(
            "slot.source_policy_epoch",
            document[
                "source_policy_epoch"
            ],
        ),
        source_runtime_ref=_require_string(
            "slot.source_runtime_ref",
            document[
                "source_runtime_ref"
            ],
        ),
        slot_id=_require_sha256(
            "slot.slot_id",
            document[
                "slot_id"
            ],
        ),
        slot_sha256=_require_sha256(
            "slot.slot_sha256",
            document[
                "slot_sha256"
            ],
        ),
    )

    expected_slot_sha256 = _sha256_text(
        _canonical_json(
            _entry_body(
                entry
            )
        )
    )

    if entry.slot_sha256 != expected_slot_sha256:
        raise ShadowResultJournalIntegrityError(
            "slot SHA-256 does not match canonical slot body."
        )

    return entry


def _decode_manifest(
    text: str,
) -> dict[
    str,
    object,
]:
    raw = _strict_json_loads(
        text
    )

    document = _require_mapping(
        "manifest",
        raw,
    )

    _require_exact_keys(
        "manifest",
        document,
        _MANIFEST_KEYS,
    )

    if (
        document[
            "manifest_schema_version"
        ]
        != SHADOW_RESULT_JOURNAL_MANIFEST_SCHEMA_V1
    ):
        raise ShadowResultJournalSchemaError(
            "unsupported Shadow journal manifest schema."
        )

    canonical_document = _canonical_json(
        document
    )

    if canonical_document != text:
        raise ShadowResultJournalIntegrityError(
            "manifest JSON is not canonical."
        )

    declared_manifest_sha256 = (
        _require_sha256(
            "manifest.manifest_sha256",
            document[
                "manifest_sha256"
            ],
        )
    )

    body = {
        key:
            value
        for key, value
        in document.items()
        if key
        != "manifest_sha256"
    }

    expected_manifest_sha256 = (
        _sha256_text(
            _canonical_json(
                body
            )
        )
    )

    if (
        declared_manifest_sha256
        != expected_manifest_sha256
    ):
        raise ShadowResultJournalIntegrityError(
            "manifest SHA-256 does not match canonical manifest body."
        )

    _safe_component(
        "manifest.market",
        document[
            "market"
        ],
    )

    _safe_component(
        "manifest.session_id",
        document[
            "session_id"
        ],
    )

    _parse_datetime(
        "manifest.snapshot_at",
        document[
            "snapshot_at"
        ],
    )

    _require_sha256(
        "manifest.slot_id",
        document[
            "slot_id"
        ],
    )

    _require_sha256(
        "manifest.slot_sha256",
        document[
            "slot_sha256"
        ],
    )

    _require_sha256(
        "manifest.snapshot_sha256",
        document[
            "snapshot_sha256"
        ],
    )

    _require_sha256(
        "manifest.shadow_result_sha256",
        document[
            "shadow_result_sha256"
        ],
    )

    _require_string(
        "manifest.slot_relpath",
        document[
            "slot_relpath"
        ],
    )

    _require_string(
        "manifest.record_relpath",
        document[
            "record_relpath"
        ],
    )

    return dict(
        document
    )


def _validate_manifest_slot(
    manifest: Mapping[
        str,
        object,
    ],
    entry: ShadowResultJournalEntryV1,
) -> None:
    expected = {
        "slot_id":
            entry.slot_id,
        "market":
            entry.market,
        "session_id":
            entry.session_id,
        "snapshot_at":
            entry.snapshot_at.isoformat(),
        "slot_relpath":
            _slot_relpath(
                entry.slot_id
            ),
        "slot_sha256":
            entry.slot_sha256,
        "record_relpath":
            entry.record_relpath,
        "snapshot_sha256":
            entry.snapshot_sha256,
        "shadow_result_sha256":
            entry.shadow_result_sha256,
    }

    for key, value in expected.items():
        if manifest[
            key
        ] != value:
            raise ShadowResultJournalIntegrityError(
                f"manifest/slot {key} mismatch."
            )


def _validate_result_entry(
    result: ShadowBrainResultV1,
    entry: ShadowResultJournalEntryV1,
) -> None:
    exact = (
        (
            "market",
            result.market,
            entry.market,
        ),
        (
            "snapshot_at",
            result.snapshot_at,
            entry.snapshot_at,
        ),
        (
            "snapshot_sha256",
            result.snapshot_sha256,
            entry.snapshot_sha256,
        ),
        (
            "shadow_result_sha256",
            result.shadow_result_sha256,
            entry.shadow_result_sha256,
        ),
        (
            "source_strategy_version",
            result.source_strategy_version,
            entry.source_strategy_version,
        ),
        (
            "source_policy_epoch",
            result.source_policy_epoch,
            entry.source_policy_epoch,
        ),
        (
            "source_runtime_ref",
            result.source_runtime_ref,
            entry.source_runtime_ref,
        ),
    )

    for (
        name,
        result_value,
        entry_value,
    ) in exact:
        if result_value != entry_value:
            raise ShadowResultJournalIntegrityError(
                f"journal entry/result {name} mismatch."
            )


def _load_slot(
    path: Path,
) -> ShadowResultJournalEntryV1:
    return _decode_slot(
        _read_utf8(
            path
        )
    )


def _load_manifest(
    path: Path,
) -> dict[
    str,
    object,
]:
    return _decode_manifest(
        _read_utf8(
            path
        )
    )


def capture_shadow_result_journal_v1(
    *,
    journal_root: str | Path,
    session_id: str,
    snapshot: MarketSnapshotV1,
    result: ShadowBrainResultV1,
) -> ShadowResultJournalEntryV1:
    entry = _build_entry(
        snapshot=snapshot,
        result=result,
        session_id=session_id,
    )

    session_root = _session_root(
        journal_root,
        market=entry.market,
        session_id=entry.session_id,
    )

    record_path = (
        session_root
        / Path(
            entry.record_relpath
        )
    )

    slot_path = (
        session_root
        / Path(
            _slot_relpath(
                entry.slot_id
            )
        )
    )

    manifest_path = (
        session_root
        / Path(
            _manifest_relpath(
                entry.slot_id
            )
        )
    )

    slot_text = _canonical_json(
        _slot_document(
            entry
        )
    )

    manifest_text = _canonical_json(
        _manifest_document(
            entry
        )
    )

    for path in (slot_path, record_path, manifest_path):
        _require_plain_path(path.parent, directory=True)
        _require_plain_path(path)

    for (
        path,
        expected_text,
        label,
    ) in (
        (
            slot_path,
            slot_text,
            "slot",
        ),
        (
            manifest_path,
            manifest_text,
            "manifest",
        ),
    ):
        if path.exists():
            try:
                existing = path.read_bytes()

            except OSError as exc:
                raise ShadowResultJournalError(
                    f"unable to inspect existing {label}: {path}"
                ) from exc

            if existing != expected_text.encode(
                "utf-8"
            ):
                raise ShadowResultJournalConflictError(
                    f"existing {label} conflicts with requested "
                    "market/session/snapshot_at slot."
                )

    # This no-overwrite publication is the cross-process slot claim. A losing
    # writer must conflict here, before creating its distinct result record.
    _publish_immutable_text(
        slot_path,
        slot_text,
    )

    try:
        persist_shadow_result_record_v1(
            result,
            record_path,
        )

    except ShadowResultPersistenceError as exc:
        raise ShadowResultJournalError(
            "unable to persist Shadow result record for journal."
        ) from exc

    _publish_immutable_text(
        manifest_path,
        manifest_text,
    )

    replayed_entry = _load_slot(
        slot_path
    )

    replayed_manifest = _load_manifest(
        manifest_path
    )

    _validate_manifest_slot(
        replayed_manifest,
        replayed_entry,
    )

    replayed_result = (
        load_shadow_result_record_v1(
            record_path
        )
    )

    _validate_result_entry(
        replayed_result,
        replayed_entry,
    )

    return replayed_entry


def _scan_documents(
    directory: Path,
    *,
    label: str,
) -> dict[
    str,
    Path,
]:
    _require_plain_path(directory, directory=True)
    if not directory.exists():
        return {}

    if not directory.is_dir():
        raise ShadowResultJournalIntegrityError(
            f"{label} path is not a directory: {directory}"
        )

    result: dict[
        str,
        Path,
    ] = {}

    for path in directory.iterdir():

        _require_plain_path(path)

        if (
            not path.is_file()
            or path.suffix != ".json"
        ):
            raise ShadowResultJournalIntegrityError(
                f"unexpected {label} journal artifact: {path}"
            )

        stem = _require_sha256(
            f"{label} filename stem",
            path.stem,
        )

        if stem in result:
            raise ShadowResultJournalIntegrityError(
                f"duplicate {label} identifier: {stem}"
            )

        result[
            stem
        ] = path

    return result


def enumerate_shadow_result_journal_v1(
    *,
    journal_root: str | Path,
    market: str,
    session_id: str,
) -> tuple[
    ShadowResultJournalEntryV1,
    ...,
]:
    market_value = _safe_component(
        "market",
        market,
    )

    session_value = _safe_component(
        "session_id",
        session_id,
    )

    session_root = _session_root(
        journal_root,
        market=market_value,
        session_id=session_value,
    )

    slots = _scan_documents(
        session_root
        / "slots",
        label="slot",
    )

    manifests = _scan_documents(
        session_root
        / "manifest",
        label="manifest",
    )

    if set(
        slots
    ) != set(
        manifests
    ):
        raise ShadowResultJournalIntegrityError(
            "slot and manifest identifier sets differ."
        )

    entries: list[
        ShadowResultJournalEntryV1
    ] = []

    for slot_id in sorted(
        slots
    ):
        entry = _load_slot(
            slots[
                slot_id
            ]
        )

        manifest = _load_manifest(
            manifests[
                slot_id
            ]
        )

        if entry.slot_id != slot_id:
            raise ShadowResultJournalIntegrityError(
                "slot filename does not match slot_id."
            )

        if manifest[
            "slot_id"
        ] != slot_id:
            raise ShadowResultJournalIntegrityError(
                "manifest filename does not match slot_id."
            )

        if entry.market != market_value:
            raise ShadowResultJournalIntegrityError(
                "slot market does not match journal partition."
            )

        if entry.session_id != session_value:
            raise ShadowResultJournalIntegrityError(
                "slot session does not match journal partition."
            )

        _validate_manifest_slot(
            manifest,
            entry,
        )

        entries.append(
            entry
        )

    records = _scan_documents(session_root / "records", label="record")
    expected_records = {entry.shadow_result_sha256 for entry in entries}
    if len(expected_records) != len(entries):
        raise ShadowResultJournalIntegrityError(
            "multiple journal entries reference the same result record."
        )
    actual_records = set(records)
    if actual_records != expected_records:
        raise ShadowResultJournalIntegrityError(
            "journal record set differs from referenced records; "
            f"missing={sorted(expected_records - actual_records)}, "
            f"orphan={sorted(actual_records - expected_records)}."
        )

    entries.sort(
        key=lambda item:
            item.snapshot_at
    )

    stamps = tuple(
        entry.snapshot_at
        for entry
        in entries
    )

    if len(
        stamps
    ) != len(
        set(
            stamps
        )
    ):
        raise ShadowResultJournalIntegrityError(
            "journal contains duplicate snapshot_at slots."
        )

    return tuple(
        entries
    )


def replay_shadow_result_journal_v1(
    *,
    journal_root: str | Path,
    market: str,
    session_id: str,
) -> tuple[
    ShadowBrainResultV1,
    ...,
]:
    entries = (
        enumerate_shadow_result_journal_v1(
            journal_root=journal_root,
            market=market,
            session_id=session_id,
        )
    )

    session_root = _session_root(
        journal_root,
        market=market,
        session_id=session_id,
    )

    replayed: list[
        ShadowBrainResultV1
    ] = []

    for entry in entries:

        expected_relpath = _record_relpath(
            entry.shadow_result_sha256
        )

        if (
            entry.record_relpath
            != expected_relpath
        ):
            raise ShadowResultJournalIntegrityError(
                "journal record path is not deterministic."
            )

        record_path = (
            session_root
            / Path(
                expected_relpath
            )
        )

        if not record_path.is_file():
            raise ShadowResultJournalIntegrityError(
                f"journal record is missing: {record_path}"
            )

        try:
            result = load_shadow_result_record_v1(
                record_path
            )

        except Exception as exc:
            raise ShadowResultJournalIntegrityError(
                f"journal record failed strict replay: {record_path}"
            ) from exc

        _validate_result_entry(
            result,
            entry,
        )

        replayed.append(
            result
        )

    return tuple(
        replayed
    )


def verify_shadow_result_journal_v1(
    *,
    journal_root: str | Path,
    market: str,
    session_id: str,
) -> ShadowResultJournalVerificationV1:
    entries = (
        enumerate_shadow_result_journal_v1(
            journal_root=journal_root,
            market=market,
            session_id=session_id,
        )
    )

    results = (
        replay_shadow_result_journal_v1(
            journal_root=journal_root,
            market=market,
            session_id=session_id,
        )
    )

    if len(
        entries
    ) != len(
        results
    ):
        raise ShadowResultJournalIntegrityError(
            "journal entry/result count mismatch."
        )

    for entry, result in zip(entries, results):
        _validate_result_entry(result, entry)

    stamps = tuple(
        entry.snapshot_at
        for entry
        in entries
    )

    chronological = all(
        left < right
        for left, right
        in zip(
            stamps,
            stamps[
                1:
            ],
        )
    )

    if len(
        stamps
    ) <= 1:
        chronological = True

    return ShadowResultJournalVerificationV1(
        market=_safe_component(
            "market",
            market,
        ),
        session_id=_safe_component(
            "session_id",
            session_id,
        ),
        entry_count=len(
            entries
        ),
        chronological=chronological,
        manifest_hashes_verified=True,
        slot_hashes_verified=True,
        records_verified=True,
    )


__all__ = [
    "SHADOW_RESULT_JOURNAL_SLOT_SCHEMA_V1",
    "SHADOW_RESULT_JOURNAL_ENTRY_SCHEMA_V1",
    "SHADOW_RESULT_JOURNAL_MANIFEST_SCHEMA_V1",
    "SHADOW_RESULT_JOURNAL_VERIFICATION_SCHEMA_V1",
    "ShadowResultJournalError",
    "ShadowResultJournalConflictError",
    "ShadowResultJournalReplayError",
    "ShadowResultJournalSchemaError",
    "ShadowResultJournalIntegrityError",
    "ShadowResultJournalEntryV1",
    "ShadowResultJournalVerificationV1",
    "shadow_result_journal_slot_id_v1",
    "capture_shadow_result_journal_v1",
    "enumerate_shadow_result_journal_v1",
    "replay_shadow_result_journal_v1",
    "verify_shadow_result_journal_v1",
]
