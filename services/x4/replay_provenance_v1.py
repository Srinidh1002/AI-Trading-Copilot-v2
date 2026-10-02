"""Offline, read-only, point-in-time X4 replay with provenance sidecars.

This module validates supplied provenance identifiers and capture integrity;
it does NOT independently authenticate FYERS documentation or certify that
historical volume/OI were observable at a particular historical checkpoint.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta, timezone
from types import MappingProxyType

from services.x4.contracts_v1 import (
    X4BasisReferenceV1,
    X4ContractV1,
    _aware,
    _encode,
    canonical_sha256,
)
from services.x4.fyers_adapter_v1 import (
    _INTERVALS,
    _PRICE_UNITS,
    ResolvedFuturesIdentityV1,
    adapt_fyers_futures_candles_v1,
)
from services.x4.multi_timeframe_v1 import compose_x4_multi_timeframe_v1
from services.x4.research_view_v1 import build_x4_research_view_v1

_IST = timezone(timedelta(hours=5, minutes=30))
_REQUIRED_PROOFS = frozenset({"capture", "session", "candle_time", "price_unit"})
_OPTIONAL_PROOFS = frozenset({"volume_unit", "oi_unit", "oi_timestamp"})


@dataclass(frozen=True, slots=True)
class X4ReplayArchiveV1:
    """Capture identity plus caller-supplied, separately reviewable proof IDs.

    Proof IDs are references, not proof of independent provider verification.
    The caller must separately substantiate each claimed provider data property.
    """

    timeframe: str
    session_id: str
    capture_id: str
    archive_id: str
    archived_at: datetime
    rows: tuple[Mapping[str, object], ...]
    rows_sha256: str
    proof_ids: tuple[tuple[str, str], ...]
    schema_version: str = "X4_REPLAY_ARCHIVE_V1"
    data_only: bool = True
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if (
            self.timeframe not in _INTERVALS
            or not all(
                isinstance(s, str) and bool(s) and s == s.strip()
                for s in (self.session_id, self.capture_id, self.archive_id)
            )
            or not _aware(self.archived_at)
            or type(self.rows) is not tuple
            or not self.rows
            or self.schema_version != "X4_REPLAY_ARCHIVE_V1"
            or self.data_only is not True
            or self.live_execution_eligible is not False
        ):
            raise ValueError("Invalid replay archive identity or authority")
        if not isinstance(self.proof_ids, tuple) or any(
            type(item) is not tuple
            or len(item) != 2
            or not all(type(x) is str and bool(x.strip()) and x == x.strip() for x in item)
            for item in self.proof_ids
        ):
            raise ValueError("Proof IDs must be nonempty (property, evidence reference) pairs")
        proofs = dict(self.proof_ids)
        if (
            len(proofs) != len(self.proof_ids)
            or not _REQUIRED_PROOFS <= proofs.keys()
            or not proofs.keys() <= _REQUIRED_PROOFS | _OPTIONAL_PROOFS
        ):
            raise ValueError("Missing or unexpected data-provenance references")
        # A frozen dataclass is not enough if nested dictionaries can be mutated.
        normalized: list[Mapping[str, object]] = []
        for row in self.rows:
            if not isinstance(row, Mapping) or any(
                type(k) is not str or type(v) not in (str, int, float, type(None))
                for k, v in row.items()
            ):
                raise ValueError("Replay requires flat, JSON-compatible normalized FYERS candles")
            normalized.append(MappingProxyType(dict(row)))
        object.__setattr__(self, "rows", tuple(normalized))
        if self.rows_sha256 != x4_replay_rows_sha256_v1(self.rows):
            raise ValueError("Archived capture SHA256 does not match normalized candle content")

    def proof(self, name: str) -> bool:
        return name in dict(self.proof_ids)


def x4_replay_rows_sha256_v1(rows: tuple[Mapping[str, object], ...]) -> str:
    if type(rows) is not tuple or not rows or any(not isinstance(r, Mapping) for r in rows):
        raise ValueError("Hash an ordered, nonempty immutable candle sequence")
    return canonical_sha256([dict(row) for row in rows])


@dataclass(frozen=True, slots=True)
class X4ReplayCheckpointV1:
    """Hash-linked research output; never an operational trade or PAPER record."""

    as_of: datetime
    market: str
    instrument_id: str
    session_id: str
    source_result_sha256: str
    research_view_sha256: str
    capture_sha256_by_timeframe: tuple[tuple[str, str], ...]
    basis_reference_sha256: str | None
    basis_proof_id: str | None
    alignment: str
    status: str
    missing_timeframes: tuple[str, ...]
    blockers: tuple[str, ...]
    schema_version: str = "X4_REPLAY_CHECKPOINT_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False
    certification_eligible: bool = False
    real_provider_semantics_proven: bool = False

    def __post_init__(self) -> None:
        if (
            not _aware(self.as_of)
            or not all((self.market, self.instrument_id, self.session_id))
            or len({tf for tf, _ in self.capture_sha256_by_timeframe})
            != len(self.capture_sha256_by_timeframe)
            or self.schema_version != "X4_REPLAY_CHECKPOINT_V1"
            or self.data_only is not True
            or self.independent_vote is not False
            or any(
                (
                    self.execution_authority,
                    self.risk_authority,
                    self.position_authority,
                    self.certification_authority,
                    self.live_execution_eligible,
                    self.certification_eligible,
                    self.real_provider_semantics_proven,
                )
            )
        ):
            raise ValueError("Invalid or authority-bearing replay checkpoint")

    def to_dict(self) -> dict[str, object]:
        return _encode(asdict(self))

    def sha256(self) -> str:
        return canonical_sha256(self.to_dict())


def replay_x4_historical_v1(
    *,
    resolved: ResolvedFuturesIdentityV1,
    archives: Mapping[str, X4ReplayArchiveV1],
    checkpoints: tuple[datetime, ...],
    required_timeframes: tuple[str, ...],
    freshness_seconds: Mapping[str, float],
    basis_reference: X4BasisReferenceV1 | None = None,
    basis_proof_id: str | None = None,
) -> tuple[X4ReplayCheckpointV1, ...]:
    """Replay with closed-bar prefixes only; never substitute current LTP.

    The archive may have been downloaded after a historical checkpoint. That
    is retrospective research, not proof of point-in-time provider availability.
    Caller-supplied proof references require external review before real-data
    verification; this output always remains non-certifying research.
    """
    if (
        type(checkpoints) is not tuple
        or not checkpoints
        or any(not _aware(t) for t in checkpoints)
        or any(b <= a for a, b in zip(checkpoints, checkpoints[1:]))
    ):
        raise ValueError("Replay checkpoints must be strictly increasing, aware datetimes")
    if (
        type(required_timeframes) is not tuple
        or len(required_timeframes) < 2
        or len(set(required_timeframes)) != len(required_timeframes)
        or any(tf not in _INTERVALS for tf in required_timeframes)
        or not isinstance(archives, Mapping)
        or not set(archives) <= set(required_timeframes)
        or not isinstance(freshness_seconds, Mapping)
        or set(freshness_seconds) != set(required_timeframes)
        or any(
            type(x) not in (int, float) or not math.isfinite(x) or x <= 0
            for x in freshness_seconds.values()
        )
    ):
        raise ValueError("Invalid replay timeframes, archives or freshness policy")
    if (
        getattr(resolved, "market_symbol", None) not in _PRICE_UNITS
        or getattr(resolved, "provider", None) != "FYERS"
        or getattr(resolved, "instrument_type", None) != "FUTURE"
        or getattr(resolved, "data_only", None) is not True
        or getattr(resolved, "live_execution_eligible", None) is not False
    ):
        raise ValueError("Replay requires FYERS data-only canonical FUTURE identity")
    resolution_time = getattr(resolved, "resolved_at", None)
    if resolution_time is not None and (
        not _aware(resolution_time) or resolution_time > checkpoints[0]
    ):
        raise ValueError("Instrument resolution unavailable at earliest checkpoint")
    if (basis_reference is None) != (basis_proof_id is None):
        raise ValueError("A basis reference and its separate proof ID must be supplied together")
    if basis_proof_id is not None and (
        type(basis_proof_id) is not str or not basis_proof_id.strip()
    ):
        raise ValueError("Basis proof ID must be nonempty")
    if basis_reference is not None and (
        not isinstance(basis_reference, X4BasisReferenceV1) or not basis_reference.verified
    ):
        raise ValueError("Unverified basis references cannot enter replay")

    # Audit every archive, including frames that will be missing at early checkpoints.
    session_id: str | None = None
    unique_captures: set[str] = set()
    verified_archives: dict[str, X4ReplayArchiveV1] = {}
    for tf in required_timeframes:
        if tf not in archives:
            continue
        archive = archives[tf]
        if not isinstance(archive, X4ReplayArchiveV1) or archive.timeframe != tf:
            raise ValueError("Archive/timeframe identity mismatch")
        if archive.capture_id in unique_captures:
            raise ValueError("Capture identifier reused across timeframes")
        unique_captures.add(archive.capture_id)
        if session_id is None:
            session_id = archive.session_id
        if archive.session_id != session_id:
            raise ValueError("Mixed futures sessions in a replay")
        interval = _INTERVALS[tf][0]
        prior_start: datetime | None = None
        for row in archive.rows:
            start_raw = row.get("timestamp")
            if type(start_raw) is not int or not 1_000_000_000 <= start_raw < 10_000_000_000:
                raise ValueError("Expected Unix-second FYERS candle start")
            start = datetime.fromtimestamp(start_raw, tz=UTC)
            if prior_start is not None and (start - prior_start).total_seconds() != interval:
                raise ValueError("Overlapping, duplicate, out-of-order or gapped replay candles")
            if start.astimezone(_IST).date().isoformat() != archive.session_id[:10]:
                raise ValueError("Candle does not belong to declared IST session date")
            if start + timedelta(seconds=interval) > archive.archived_at:
                raise ValueError("Archive claims to contain a bar not completed at archive time")
            prior_start = start
        verified_archives[tf] = archive

    results: list[X4ReplayCheckpointV1] = []
    for as_of in checkpoints:
        captures = {}
        for tf in required_timeframes:
            if tf not in verified_archives:
                continue
            archive = verified_archives[tf]
            interval = _INTERVALS[tf][0]
            prefix = tuple(
                row
                for row in archive.rows
                if datetime.fromtimestamp(row["timestamp"], tz=UTC) + timedelta(seconds=interval)
                <= as_of
            )
            if not prefix:
                continue
            adapted = adapt_fyers_futures_candles_v1(
                resolved=resolved,
                rows=prefix,
                timeframe=tf,
                session_id=archive.session_id,
                as_of=as_of,
                capture_id=archive.capture_id,
                capture_verified=archive.proof("capture"),
                session_verified=archive.proof("session"),
                timestamp_semantics_verified=archive.proof("candle_time"),
                price_unit=_PRICE_UNITS[getattr(resolved, "market_symbol", None)],
                price_unit_verified=archive.proof("price_unit"),
                volume_unit_verified=archive.proof("volume_unit"),
                oi_unit_verified=archive.proof("oi_unit"),
                oi_timestamp_verified=archive.proof("oi_timestamp"),
            )
            captures[tf] = adapted
        contract = (
            next(iter(captures.values())).contract
            if captures
            else X4ContractV1(
                market=resolved.market_symbol,
                canonical_instrument_id=resolved.canonical_instrument_id,
                provider="FYERS",
                provider_symbol=resolved.provider_symbol,
                expiry=resolved.expiry,
                price_unit=_PRICE_UNITS[resolved.market_symbol],
                metadata_status=resolved.contract_metadata_status,
                metadata_source=resolved.metadata_source,
            )
        )
        reference = basis_reference
        if reference is not None and reference.observed_at > as_of:
            reference = None  # Historical replay cannot borrow a future benchmark.
        composed = compose_x4_multi_timeframe_v1(
            contract=contract,
            captures=captures,
            required_timeframes=required_timeframes,
            max_age_seconds_by_timeframe=freshness_seconds,
            as_of=as_of,
            basis_reference=reference,
        )
        view = build_x4_research_view_v1(composed)
        blockers = list(view.blockers)
        blockers.append("HISTORICAL_PROVIDER_SEMANTICS_NOT_INDEPENDENTLY_PROVEN")
        if any(a.archived_at > as_of for a in verified_archives.values()):
            blockers.append("RETROSPECTIVE_ARCHIVE_CAPTURE")
        if basis_reference is not None and reference is None:
            blockers.append("FUTURE_BENCHMARK_EXCLUDED")
        results.append(
            X4ReplayCheckpointV1(
                as_of=as_of,
                market=composed.market,
                instrument_id=composed.instrument_id,
                session_id=composed.session_id,
                source_result_sha256=composed.sha256(),
                research_view_sha256=view.sha256(),
                capture_sha256_by_timeframe=tuple(
                    (tf, verified_archives[tf].rows_sha256)
                    for tf in required_timeframes
                    if tf in verified_archives
                ),
                basis_reference_sha256=(
                    canonical_sha256(asdict(reference)) if reference is not None else None
                ),
                basis_proof_id=basis_proof_id if reference is not None else None,
                alignment=composed.alignment,
                status=composed.status,
                missing_timeframes=composed.missing_timeframes,
                blockers=tuple(dict.fromkeys(blockers)),
            )
        )
    return tuple(results)
