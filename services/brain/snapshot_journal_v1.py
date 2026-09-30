
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping

from services.brain.analyzer_registry_v1 import SUPPORTED_MARKETS
from services.brain.market_snapshot_v1 import MarketSnapshotV1
from services.brain.snapshot_persistence_v1 import (
    SnapshotPersistenceError,
    SnapshotReplayError,
    load_snapshot_record_v1,
    persist_snapshot_record_v1,
)


SNAPSHOT_JOURNAL_ENTRY_SCHEMA_V1 = (
    "BRAIN_SNAPSHOT_JOURNAL_ENTRY_V1"
)

SNAPSHOT_JOURNAL_SLOT_SCHEMA_V1 = (
    "BRAIN_SNAPSHOT_JOURNAL_SLOT_V1"
)

SNAPSHOT_JOURNAL_VERIFICATION_SCHEMA_V1 = (
    "BRAIN_SNAPSHOT_JOURNAL_VERIFICATION_V1"
)


class SnapshotJournalError(RuntimeError):
    pass


class SnapshotJournalConflictError(SnapshotJournalError):
    pass


class SnapshotJournalIntegrityError(SnapshotJournalError):
    pass


class SnapshotJournalDecodeError(SnapshotJournalIntegrityError):
    pass


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
        raise SnapshotJournalIntegrityError(
            "journal payload is not canonical-JSON compatible."
        ) from exc


def _digest(value: object) -> str:
    return sha256(
        _canonical_json(value).encode("utf-8")
    ).hexdigest()


def _reject_duplicate_pairs(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}

    for key, value in pairs:
        if key in result:
            raise SnapshotJournalDecodeError(
                f"duplicate JSON object key: {key}"
            )

        result[key] = value

    return result


def _reject_nonfinite(value: str) -> None:
    raise SnapshotJournalDecodeError(
        f"non-finite JSON constant is forbidden: {value}"
    )


def _strict_json(text: str) -> Any:
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_nonfinite,
        )
    except SnapshotJournalIntegrityError:
        raise
    except (json.JSONDecodeError, TypeError) as exc:
        raise SnapshotJournalDecodeError(
            "journal record is not valid JSON."
        ) from exc


def _mapping(
    name: str,
    value: object,
) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise SnapshotJournalDecodeError(
            f"{name} must be a JSON object."
        )

    return value


def _exact_keys(
    name: str,
    value: Mapping[str, Any],
    expected: set[str],
) -> None:
    actual = set(value)

    if actual != expected:
        raise SnapshotJournalIntegrityError(
            f"{name} keys mismatch; "
            f"missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )


def _false(
    name: str,
    value: object,
) -> None:
    if value is not False:
        raise SnapshotJournalIntegrityError(
            f"{name} must be false."
        )


def _aware(
    name: str,
    value: object,
) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(
            f"{name} must be timezone-aware."
        )

    return value


def _parse_datetime(
    name: str,
    value: object,
) -> datetime:
    if not isinstance(value, str):
        raise SnapshotJournalDecodeError(
            f"{name} must be ISO-8601 text."
        )

    normalized = (
        value[:-1] + "+00:00"
        if value.endswith("Z")
        else value
    )

    try:
        parsed = datetime.fromisoformat(
            normalized
        )
    except ValueError as exc:
        raise SnapshotJournalDecodeError(
            f"{name} is invalid ISO-8601."
        ) from exc

    if (
        parsed.tzinfo is None
        or parsed.utcoffset() is None
    ):
        raise SnapshotJournalDecodeError(
            f"{name} must be timezone-aware."
        )

    return parsed


def _session_id(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError(
            "session_id must use YYYY-MM-DD."
        )

    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            "session_id must be a valid YYYY-MM-DD date."
        ) from exc

    if parsed.isoformat() != value:
        raise ValueError(
            "session_id must use canonical YYYY-MM-DD."
        )

    return value


def _sha256(
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value != value.lower()
    ):
        raise SnapshotJournalIntegrityError(
            f"{name} must be 64 lowercase hex characters."
        )

    try:
        int(value, 16)
    except ValueError as exc:
        raise SnapshotJournalIntegrityError(
            f"{name} must be hexadecimal."
        ) from exc

    return value


def _slot_key(snapshot_at: datetime) -> str:
    return _aware(
        "snapshot_at",
        snapshot_at,
    ).astimezone(
        timezone.utc
    ).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )


def _record_relpath(
    snapshot_sha256: str,
) -> str:
    return (
        f"records/"
        f"{snapshot_sha256}.json"
    )


def _manifest_filename(
    snapshot_at: datetime,
    snapshot_sha256: str,
) -> str:
    return (
        f"{_slot_key(snapshot_at)}_"
        f"{snapshot_sha256}.json"
    )


def _slot_filename(
    snapshot_at: datetime,
) -> str:
    return (
        f"{_slot_key(snapshot_at)}.json"
    )


def _read_utf8(path: Path) -> str:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise SnapshotJournalIntegrityError(
            f"unable to read journal file: {path}"
        ) from exc

    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SnapshotJournalDecodeError(
            f"journal file is not UTF-8: {path}"
        ) from exc


def _publish_immutable(
    target: Path,
    data: bytes,
) -> Path:
    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)

            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())

        try:
            os.link(
                temporary,
                target,
            )

        except FileExistsError:
            try:
                existing = target.read_bytes()
            except OSError as exc:
                raise SnapshotJournalError(
                    f"unable to inspect concurrent journal target: {target}"
                ) from exc

            if existing == data:
                return target

            raise SnapshotJournalConflictError(
                f"immutable journal target already differs: {target}"
            )

        except OSError as exc:
            raise SnapshotJournalError(
                f"unable to publish immutable journal file: {target}"
            ) from exc

        return target

    finally:
        if (
            temporary is not None
            and temporary.exists()
        ):
            temporary.unlink()


@dataclass(
    frozen=True,
    slots=True,
)
class SnapshotJournalEntryV1:
    session_id: str
    market: str
    snapshot_at: datetime
    snapshot_sha256: str
    record_relpath: str

    source_strategy_version: str | None = None
    source_policy_epoch: str | None = None
    source_runtime_ref: str | None = None

    execution_authority: bool = False
    decision_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False

    schema_version: str = (
        SNAPSHOT_JOURNAL_ENTRY_SCHEMA_V1
    )

    def __post_init__(self) -> None:
        _session_id(self.session_id)

        if self.market not in SUPPORTED_MARKETS:
            raise ValueError(
                f"unsupported market: {self.market}"
            )

        _aware(
            "snapshot_at",
            self.snapshot_at,
        )

        _sha256(
            "snapshot_sha256",
            self.snapshot_sha256,
        )

        if self.record_relpath != _record_relpath(
            self.snapshot_sha256
        ):
            raise ValueError(
                "record_relpath must match deterministic snapshot path."
            )

        if self.schema_version != (
            SNAPSHOT_JOURNAL_ENTRY_SCHEMA_V1
        ):
            raise ValueError(
                "unsupported journal entry schema."
            )

        for name in (
            "source_strategy_version",
            "source_policy_epoch",
            "source_runtime_ref",
        ):
            value = getattr(self, name)

            if value is not None and (
                not isinstance(value, str)
                or not value.strip()
                or value != value.strip()
            ):
                raise ValueError(
                    f"{name} must be non-empty trimmed text when supplied."
                )

        for name in (
            "execution_authority",
            "decision_authority",
            "risk_authority",
            "position_authority",
            "certification_authority",
        ):
            if getattr(self, name) is not False:
                raise ValueError(
                    f"{name} is permanently False "
                    "in SnapshotJournalEntryV1."
                )

    def canonical_payload(
        self,
    ) -> dict[str, object]:
        return {
            "schema_version":
                self.schema_version,

            "session_id":
                self.session_id,

            "market":
                self.market,

            "snapshot_at":
                self.snapshot_at.isoformat(),

            "snapshot_sha256":
                self.snapshot_sha256,

            "record_relpath":
                self.record_relpath,

            "source_strategy_version":
                self.source_strategy_version,

            "source_policy_epoch":
                self.source_policy_epoch,

            "source_runtime_ref":
                self.source_runtime_ref,

            "execution_authority":
                False,

            "decision_authority":
                False,

            "risk_authority":
                False,

            "position_authority":
                False,

            "certification_authority":
                False,
        }

    @property
    def entry_sha256(self) -> str:
        return _digest(
            self.canonical_payload()
        )

    def to_dict(
        self,
    ) -> dict[str, object]:
        payload = self.canonical_payload()

        payload[
            "entry_sha256"
        ] = self.entry_sha256

        return payload


@dataclass(
    frozen=True,
    slots=True,
)
class SnapshotJournalVerificationV1:
    market: str
    session_id: str
    entry_count: int
    snapshot_sha256s: tuple[str, ...]
    first_snapshot_at: datetime | None
    last_snapshot_at: datetime | None
    chronological: bool

    execution_authority: bool = False
    decision_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False

    schema_version: str = (
        SNAPSHOT_JOURNAL_VERIFICATION_SCHEMA_V1
    )

    def __post_init__(self) -> None:
        if self.market not in SUPPORTED_MARKETS:
            raise ValueError(
                f"unsupported market: {self.market}"
            )

        _session_id(self.session_id)

        if (
            isinstance(self.entry_count, bool)
            or not isinstance(self.entry_count, int)
            or self.entry_count < 0
        ):
            raise ValueError(
                "entry_count must be a non-negative integer."
            )

        if (
            not isinstance(
                self.snapshot_sha256s,
                tuple,
            )
            or len(
                self.snapshot_sha256s
            )
            != self.entry_count
        ):
            raise ValueError(
                "snapshot_sha256s must match entry_count."
            )

        for value in self.snapshot_sha256s:
            _sha256(
                "snapshot_sha256",
                value,
            )

        for name in (
            "first_snapshot_at",
            "last_snapshot_at",
        ):
            value = getattr(self, name)

            if value is not None:
                _aware(
                    name,
                    value,
                )

        if self.chronological is not True:
            raise ValueError(
                "verified journal must be chronological."
            )

        if self.schema_version != (
            SNAPSHOT_JOURNAL_VERIFICATION_SCHEMA_V1
        ):
            raise ValueError(
                "unsupported verification schema."
            )

        for name in (
            "execution_authority",
            "decision_authority",
            "risk_authority",
            "position_authority",
            "certification_authority",
        ):
            if getattr(self, name) is not False:
                raise ValueError(
                    f"{name} is permanently False."
                )


_ENTRY_KEYS = {
    "schema_version",
    "session_id",
    "market",
    "snapshot_at",
    "snapshot_sha256",
    "record_relpath",
    "source_strategy_version",
    "source_policy_epoch",
    "source_runtime_ref",
    "execution_authority",
    "decision_authority",
    "risk_authority",
    "position_authority",
    "certification_authority",
    "entry_sha256",
}


_SLOT_KEYS = {
    "schema_version",
    "session_id",
    "market",
    "snapshot_at",
    "snapshot_sha256",
    "record_relpath",
    "manifest_filename",
}


def _decode_entry(
    raw: object,
) -> SnapshotJournalEntryV1:
    payload = _mapping(
        "journal_entry",
        raw,
    )

    _exact_keys(
        "journal_entry",
        payload,
        _ENTRY_KEYS,
    )

    if payload[
        "schema_version"
    ] != SNAPSHOT_JOURNAL_ENTRY_SCHEMA_V1:
        raise SnapshotJournalIntegrityError(
            "unsupported journal entry schema."
        )

    for name in (
        "execution_authority",
        "decision_authority",
        "risk_authority",
        "position_authority",
        "certification_authority",
    ):
        _false(
            name,
            payload[name],
        )

    declared = _sha256(
        "entry_sha256",
        payload[
            "entry_sha256"
        ],
    )

    unhashed = {
        key:
            value
        for key, value in payload.items()
        if key != "entry_sha256"
    }

    if _digest(unhashed) != declared:
        raise SnapshotJournalIntegrityError(
            "journal entry SHA-256 mismatch."
        )

    try:
        entry = SnapshotJournalEntryV1(
            session_id=payload[
                "session_id"
            ],
            market=payload[
                "market"
            ],
            snapshot_at=_parse_datetime(
                "snapshot_at",
                payload[
                    "snapshot_at"
                ],
            ),
            snapshot_sha256=payload[
                "snapshot_sha256"
            ],
            record_relpath=payload[
                "record_relpath"
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
        )
    except ValueError as exc:
        raise SnapshotJournalIntegrityError(
            f"invalid journal entry: {exc}"
        ) from exc

    if entry.entry_sha256 != declared:
        raise SnapshotJournalIntegrityError(
            "reconstructed journal entry hash mismatch."
        )

    return entry


def _slot_payload(
    entry: SnapshotJournalEntryV1,
) -> dict[str, object]:
    return {
        "schema_version":
            SNAPSHOT_JOURNAL_SLOT_SCHEMA_V1,

        "session_id":
            entry.session_id,

        "market":
            entry.market,

        "snapshot_at":
            entry.snapshot_at.isoformat(),

        "snapshot_sha256":
            entry.snapshot_sha256,

        "record_relpath":
            entry.record_relpath,

        "manifest_filename":
            _manifest_filename(
                entry.snapshot_at,
                entry.snapshot_sha256,
            ),
    }


def _session_root(
    journal_root: str | Path,
    market: str,
    session_id: str,
) -> Path:
    if market not in SUPPORTED_MARKETS:
        raise ValueError(
            f"unsupported market: {market}"
        )

    _session_id(session_id)

    return (
        Path(journal_root)
        / market
        / session_id
    )


def capture_snapshot_v1(
    *,
    journal_root: str | Path,
    session_id: str,
    snapshot: MarketSnapshotV1,
) -> SnapshotJournalEntryV1:
    if not isinstance(
        snapshot,
        MarketSnapshotV1,
    ):
        raise TypeError(
            "snapshot must be MarketSnapshotV1."
        )

    root = _session_root(
        journal_root,
        snapshot.market,
        session_id,
    )

    record_relpath = _record_relpath(
        snapshot.snapshot_sha256
    )

    record_path = (
        root
        / record_relpath
    )

    try:
        persist_snapshot_record_v1(
            snapshot,
            record_path,
        )
    except SnapshotPersistenceError as exc:
        raise SnapshotJournalError(
            f"unable to persist snapshot record: {exc}"
        ) from exc

    entry = SnapshotJournalEntryV1(
        session_id=session_id,
        market=snapshot.market,
        snapshot_at=snapshot.snapshot_at,
        snapshot_sha256=snapshot.snapshot_sha256,
        record_relpath=record_relpath,
        source_strategy_version=snapshot.source_strategy_version,
        source_policy_epoch=snapshot.source_policy_epoch,
        source_runtime_ref=snapshot.source_runtime_ref,
    )

    slot_path = (
        root
        / "slots"
        / _slot_filename(
            snapshot.snapshot_at
        )
    )

    manifest_path = (
        root
        / "manifest"
        / _manifest_filename(
            snapshot.snapshot_at,
            snapshot.snapshot_sha256,
        )
    )

    slot_bytes = (
        _canonical_json(
            _slot_payload(entry)
        )
        + "\n"
    ).encode(
        "utf-8"
    )

    entry_bytes = (
        _canonical_json(
            entry.to_dict()
        )
        + "\n"
    ).encode(
        "utf-8"
    )

    _publish_immutable(
        slot_path,
        slot_bytes,
    )

    _publish_immutable(
        manifest_path,
        entry_bytes,
    )

    return entry


def enumerate_snapshot_journal_v1(
    *,
    journal_root: str | Path,
    market: str,
    session_id: str,
) -> tuple[
    SnapshotJournalEntryV1,
    ...,
]:
    root = _session_root(
        journal_root,
        market,
        session_id,
    )

    manifest_root = (
        root
        / "manifest"
    )

    if not manifest_root.exists():
        return ()

    if not manifest_root.is_dir():
        raise SnapshotJournalIntegrityError(
            "manifest path is not a directory."
        )

    entries: list[
        SnapshotJournalEntryV1
    ] = []

    seen_slots: set[str] = set()
    seen_hashes: set[str] = set()

    for manifest_path in sorted(
        manifest_root.glob(
            "*.json"
        ),
        key=lambda item: item.name,
    ):
        entry = _decode_entry(
            _strict_json(
                _read_utf8(
                    manifest_path
                )
            )
        )

        if entry.market != market:
            raise SnapshotJournalIntegrityError(
                "manifest market differs from journal path."
            )

        if entry.session_id != session_id:
            raise SnapshotJournalIntegrityError(
                "manifest session differs from journal path."
            )

        expected_manifest_name = _manifest_filename(
            entry.snapshot_at,
            entry.snapshot_sha256,
        )

        if manifest_path.name != expected_manifest_name:
            raise SnapshotJournalIntegrityError(
                "manifest filename is not deterministic."
            )

        slot_name = _slot_filename(
            entry.snapshot_at
        )

        if slot_name in seen_slots:
            raise SnapshotJournalIntegrityError(
                "duplicate capture slot in manifest."
            )

        if entry.snapshot_sha256 in seen_hashes:
            raise SnapshotJournalIntegrityError(
                "duplicate snapshot hash in manifest."
            )

        slot_path = (
            root
            / "slots"
            / slot_name
        )

        if not slot_path.is_file():
            raise SnapshotJournalIntegrityError(
                "manifest entry has no slot claim."
            )

        slot_payload = _mapping(
            "journal_slot",
            _strict_json(
                _read_utf8(
                    slot_path
                )
            ),
        )

        _exact_keys(
            "journal_slot",
            slot_payload,
            _SLOT_KEYS,
        )

        if slot_payload != _slot_payload(
            entry
        ):
            raise SnapshotJournalIntegrityError(
                "journal slot does not match manifest entry."
            )

        record_path = (
            root
            / entry.record_relpath
        )

        if not record_path.is_file():
            raise SnapshotJournalIntegrityError(
                "manifest entry references a missing snapshot record."
            )

        try:
            snapshot = load_snapshot_record_v1(
                record_path
            )
        except (
            SnapshotReplayError,
            SnapshotPersistenceError,
        ) as exc:
            raise SnapshotJournalIntegrityError(
                f"snapshot record failed replay: {exc}"
            ) from exc

        if (
            snapshot.snapshot_sha256
            != entry.snapshot_sha256
        ):
            raise SnapshotJournalIntegrityError(
                "manifest hash differs from replayed snapshot hash."
            )

        if snapshot.market != entry.market:
            raise SnapshotJournalIntegrityError(
                "manifest market differs from replayed snapshot."
            )

        if snapshot.snapshot_at != entry.snapshot_at:
            raise SnapshotJournalIntegrityError(
                "manifest timestamp differs from replayed snapshot."
            )

        if (
            snapshot.source_strategy_version
            != entry.source_strategy_version
        ):
            raise SnapshotJournalIntegrityError(
                "manifest strategy version differs from snapshot."
            )

        if (
            snapshot.source_policy_epoch
            != entry.source_policy_epoch
        ):
            raise SnapshotJournalIntegrityError(
                "manifest policy epoch differs from snapshot."
            )

        if (
            snapshot.source_runtime_ref
            != entry.source_runtime_ref
        ):
            raise SnapshotJournalIntegrityError(
                "manifest runtime reference differs from snapshot."
            )

        seen_slots.add(
            slot_name
        )

        seen_hashes.add(
            entry.snapshot_sha256
        )

        entries.append(
            entry
        )

    entries.sort(
        key=lambda item: (
            item.snapshot_at,
            item.snapshot_sha256,
        )
    )

    return tuple(entries)


def replay_snapshot_journal_v1(
    *,
    journal_root: str | Path,
    market: str,
    session_id: str,
) -> tuple[
    MarketSnapshotV1,
    ...,
]:
    root = _session_root(
        journal_root,
        market,
        session_id,
    )

    entries = enumerate_snapshot_journal_v1(
        journal_root=journal_root,
        market=market,
        session_id=session_id,
    )

    snapshots = []

    for entry in entries:
        snapshot = load_snapshot_record_v1(
            root
            / entry.record_relpath
        )

        if (
            snapshot.snapshot_sha256
            != entry.snapshot_sha256
        ):
            raise SnapshotJournalIntegrityError(
                "replay hash differs from verified journal entry."
            )

        snapshots.append(
            snapshot
        )

    return tuple(
        snapshots
    )


def verify_snapshot_journal_v1(
    *,
    journal_root: str | Path,
    market: str,
    session_id: str,
) -> SnapshotJournalVerificationV1:
    entries = enumerate_snapshot_journal_v1(
        journal_root=journal_root,
        market=market,
        session_id=session_id,
    )

    timestamps = tuple(
        entry.snapshot_at
        for entry in entries
    )

    chronological = (
        timestamps
        == tuple(
            sorted(
                timestamps
            )
        )
    )

    if not chronological:
        raise SnapshotJournalIntegrityError(
            "journal enumeration is not chronological."
        )

    return SnapshotJournalVerificationV1(
        market=market,
        session_id=session_id,
        entry_count=len(entries),
        snapshot_sha256s=tuple(
            entry.snapshot_sha256
            for entry in entries
        ),
        first_snapshot_at=(
            entries[0].snapshot_at
            if entries
            else None
        ),
        last_snapshot_at=(
            entries[-1].snapshot_at
            if entries
            else None
        ),
        chronological=True,
    )


__all__ = [
    "SNAPSHOT_JOURNAL_ENTRY_SCHEMA_V1",
    "SNAPSHOT_JOURNAL_SLOT_SCHEMA_V1",
    "SNAPSHOT_JOURNAL_VERIFICATION_SCHEMA_V1",
    "SnapshotJournalConflictError",
    "SnapshotJournalDecodeError",
    "SnapshotJournalEntryV1",
    "SnapshotJournalError",
    "SnapshotJournalIntegrityError",
    "SnapshotJournalVerificationV1",
    "capture_snapshot_v1",
    "enumerate_snapshot_journal_v1",
    "replay_snapshot_journal_v1",
    "verify_snapshot_journal_v1",
]
