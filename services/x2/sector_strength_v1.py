"""Sector strength and rotation engine for X2.

Consumes a :class:`ConstituentUniverseV1` plus per-constituent returns
and produces sector-level return, breadth, participation, contribution,
relative strength and rotation evidence.

Rotation discipline:

* Rotation is never declared from a single observation. It requires
  both a current snapshot and a previous snapshot, at least two sectors,
  and a change in rank that exceeds an explicit threshold.
* Without a previous snapshot, rotation status is
  ``INSUFFICIENT_HISTORY``. The other sector metrics are still
  produced.
* A constituent without a verified sector is excluded from sector
  calculations and recorded under ``unsectored_constituents``.
* Sector return is the weight-weighted return over the sector's own
  constituents. It is not rescaled against the whole index.
* Relative return is ``sector_weighted_return - index_weighted_return``,
  both computed on the same eligible universe so they are comparable.

Horizon discipline:

* The engine labels the analysis with ``horizon`` supplied by the
  caller. It does not construct a daily or weekly return by pretending
  a short intraday sample represents a full day or week.
* When history is required and not supplied, ``INSUFFICIENT_HISTORY``
  is reported for rotation.
"""
from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256

from services.x2.constituent_universe_v1 import (
    ConstituentUniverseV1,
    X2ConstituentError,
)

SECTOR_STRENGTH_SCHEMA_V1 = "X2_SECTOR_STRENGTH_V1"

DEFAULT_STALE_AFTER_SECONDS = 300.0
DEFAULT_ROTATION_RANK_THRESHOLD = 2
DEFAULT_ROTATION_RELATIVE_RETURN_THRESHOLD = 0.005


class RotationStatusV1:
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    STABLE = "STABLE"
    ROTATION = "ROTATION"


def _aware(name: str, value: object) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise X2ConstituentError(
            f"{name} must be a timezone-aware datetime."
        )
    return value


def _finite(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


@dataclass(frozen=True, slots=True)
class SectorReturnInputV1:
    canonical_constituent_id: str
    return_fraction: float
    observed_at: datetime

    def __post_init__(self) -> None:
        if (
            not isinstance(self.canonical_constituent_id, str)
            or not self.canonical_constituent_id.strip()
        ):
            raise X2ConstituentError(
                "canonical_constituent_id must be non-empty."
            )
        if not _finite(self.return_fraction):
            raise X2ConstituentError(
                "return_fraction must be numeric."
            )
        object.__setattr__(
            self, "observed_at", _aware("observed_at", self.observed_at)
        )


@dataclass(frozen=True, slots=True)
class SectorStrengthRowV1:
    sector: str
    constituent_count: int
    total_sector_weight: float
    sector_weighted_return: float
    sector_relative_return: float
    advancing_count: int
    declining_count: int
    unchanged_count: int
    participation_ratio: float
    top_contributor: str | None
    top_detractor: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "sector": self.sector,
            "constituent_count": int(self.constituent_count),
            "total_sector_weight": float(self.total_sector_weight),
            "sector_weighted_return": float(self.sector_weighted_return),
            "sector_relative_return": float(
                self.sector_relative_return
            ),
            "advancing_count": int(self.advancing_count),
            "declining_count": int(self.declining_count),
            "unchanged_count": int(self.unchanged_count),
            "participation_ratio": float(self.participation_ratio),
            "top_contributor": self.top_contributor,
            "top_detractor": self.top_detractor,
        }


@dataclass(frozen=True, slots=True)
class SectorRotationV1:
    sector: str
    current_rank: int
    previous_rank: int | None
    rank_change: int | None
    relative_return_change: float | None
    rotation_status: str

    def to_dict(self) -> dict[str, object]:
        return {
            "sector": self.sector,
            "current_rank": int(self.current_rank),
            "previous_rank": self.previous_rank,
            "rank_change": self.rank_change,
            "relative_return_change": self.relative_return_change,
            "rotation_status": self.rotation_status,
        }


@dataclass(frozen=True, slots=True)
class SectorStrengthResultV1:
    universe_id: str
    universe_version: str
    universe_sha256: str
    index_symbol: str
    index_exchange: str
    calculated_at: datetime
    horizon: str
    stale_after_seconds: float
    rotation_rank_threshold: int
    rotation_relative_return_threshold: float
    index_weighted_return: float
    rows: tuple[SectorStrengthRowV1, ...]
    rotations: tuple[SectorRotationV1, ...]
    unsectored_constituents: tuple[str, ...]
    missing_constituents: tuple[str, ...]
    stale_constituents: tuple[str, ...]
    rotation_overall_status: str
    coverage_ratio: float
    is_partial: bool
    evidence_status: str
    warnings: tuple[str, ...] = ()
    schema_version: str = SECTOR_STRENGTH_SCHEMA_V1

    def __post_init__(self) -> None:
        _aware("calculated_at", self.calculated_at)
        if not isinstance(self.horizon, str) or not self.horizon.strip():
            raise X2ConstituentError(
                "horizon must be a non-empty string."
            )
        if self.schema_version != SECTOR_STRENGTH_SCHEMA_V1:
            raise X2ConstituentError(
                "unsupported sector strength schema."
            )
        if self.rotation_overall_status not in (
            RotationStatusV1.INSUFFICIENT_HISTORY,
            RotationStatusV1.STABLE,
            RotationStatusV1.ROTATION,
        ):
            raise X2ConstituentError(
                "unsupported rotation_overall_status."
            )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "universe_id": self.universe_id,
            "universe_version": self.universe_version,
            "universe_sha256": self.universe_sha256,
            "index_symbol": self.index_symbol,
            "index_exchange": self.index_exchange,
            "calculated_at": self.calculated_at.isoformat(),
            "horizon": self.horizon,
            "stale_after_seconds": float(self.stale_after_seconds),
            "rotation_rank_threshold": int(
                self.rotation_rank_threshold
            ),
            "rotation_relative_return_threshold": float(
                self.rotation_relative_return_threshold
            ),
            "index_weighted_return": float(self.index_weighted_return),
            "rows": [r.to_dict() for r in self.rows],
            "rotations": [r.to_dict() for r in self.rotations],
            "unsectored_constituents": list(
                self.unsectored_constituents
            ),
            "missing_constituents": list(self.missing_constituents),
            "stale_constituents": list(self.stale_constituents),
            "rotation_overall_status": self.rotation_overall_status,
            "coverage_ratio": float(self.coverage_ratio),
            "is_partial": bool(self.is_partial),
            "evidence_status": self.evidence_status,
            "warnings": list(self.warnings),
        }

    def canonical_json(self) -> str:
        return _canonical_json(self.canonical_payload())

    @property
    def result_sha256(self) -> str:
        return sha256(
            self.canonical_json().encode("utf-8")
        ).hexdigest()


@dataclass(frozen=True, slots=True)
class PreviousSectorSnapshotV1:
    """Snapshot of a previous sector ranking for rotation detection."""

    captured_at: datetime
    horizon: str
    sector_ranks: tuple[tuple[str, int], ...]
    sector_relative_returns: tuple[tuple[str, float], ...]

    def __post_init__(self) -> None:
        _aware("captured_at", self.captured_at)
        if (
            not isinstance(self.horizon, str)
            or not self.horizon.strip()
        ):
            raise X2ConstituentError(
                "horizon must be a non-empty string."
            )
        for name, value in (
            ("sector_ranks", self.sector_ranks),
            ("sector_relative_returns", self.sector_relative_returns),
        ):
            if not isinstance(value, tuple):
                raise X2ConstituentError(
                    f"{name} must be a tuple."
                )


def compute_sector_strength_v1(
    *,
    universe: ConstituentUniverseV1,
    inputs: Mapping[str, SectorReturnInputV1],
    calculated_at: datetime,
    horizon: str,
    previous_snapshot: PreviousSectorSnapshotV1 | None = None,
    stale_after_seconds: float = DEFAULT_STALE_AFTER_SECONDS,
    rotation_rank_threshold: int = DEFAULT_ROTATION_RANK_THRESHOLD,
    rotation_relative_return_threshold: float = (
        DEFAULT_ROTATION_RELATIVE_RETURN_THRESHOLD
    ),
    unchanged_band_pct: float = 0.05,
) -> SectorStrengthResultV1:
    if not isinstance(universe, ConstituentUniverseV1):
        raise X2ConstituentError(
            "universe must be ConstituentUniverseV1."
        )
    if not isinstance(inputs, Mapping):
        raise X2ConstituentError("inputs must be a mapping.")
    if not isinstance(horizon, str) or not horizon.strip():
        raise X2ConstituentError("horizon must be non-empty.")
    if (
        previous_snapshot is not None
        and not isinstance(previous_snapshot, PreviousSectorSnapshotV1)
    ):
        raise X2ConstituentError(
            "previous_snapshot must be PreviousSectorSnapshotV1 or None."
        )
    if (
        isinstance(stale_after_seconds, bool)
        or not isinstance(stale_after_seconds, (int, float))
        or not math.isfinite(float(stale_after_seconds))
        or stale_after_seconds < 0
    ):
        raise X2ConstituentError(
            "stale_after_seconds must be a non-negative number."
        )
    if (
        not isinstance(rotation_rank_threshold, int)
        or isinstance(rotation_rank_threshold, bool)
        or rotation_rank_threshold < 1
    ):
        raise X2ConstituentError(
            "rotation_rank_threshold must be a positive integer."
        )
    if (
        not _finite(rotation_relative_return_threshold)
        or rotation_relative_return_threshold < 0
    ):
        raise X2ConstituentError(
            "rotation_relative_return_threshold must be "
            "finite and non-negative."
        )
    if (
        not _finite(unchanged_band_pct)
        or float(unchanged_band_pct) < 0
    ):
        raise X2ConstituentError(
            "unchanged_band_pct must be a non-negative number."
        )

    calculated = _aware("calculated_at", calculated_at)
    stale_cutoff = calculated - timedelta(
        seconds=float(stale_after_seconds)
    )

    # Accumulators
    per_sector_returns: dict[str, list[tuple[str, float, float]]] = {}
    # sector -> list of (cid, weight, return)
    unsectored: list[str] = []
    missing: list[str] = []
    stale: list[str] = []

    total_weight_used = 0.0
    total_weighted_return_sum = 0.0

    for entry in universe.constituents:
        raw = inputs.get(entry.canonical_constituent_id)
        if raw is None:
            missing.append(entry.canonical_constituent_id)
            continue
        if not isinstance(raw, SectorReturnInputV1):
            raise X2ConstituentError(
                "input must be SectorReturnInputV1."
            )
        if raw.observed_at < stale_cutoff:
            stale.append(entry.canonical_constituent_id)
            continue
        if raw.observed_at > calculated:
            raise X2ConstituentError(
                f"input for {entry.canonical_constituent_id} "
                "is in the future relative to calculated_at."
            )
        if entry.sector is None:
            unsectored.append(entry.canonical_constituent_id)
            continue

        per_sector_returns.setdefault(entry.sector, []).append(
            (
                entry.canonical_constituent_id,
                float(entry.weight),
                float(raw.return_fraction),
            )
        )
        total_weight_used += float(entry.weight)
        total_weighted_return_sum += (
            float(entry.weight) * float(raw.return_fraction)
        )

    if total_weight_used > 0:
        index_weighted_return = (
            total_weighted_return_sum / total_weight_used
        )
    else:
        index_weighted_return = 0.0

    band = float(unchanged_band_pct)
    rows: list[SectorStrengthRowV1] = []
    for sector, members in per_sector_returns.items():
        sector_weight = sum(w for _, w, _ in members)
        if sector_weight > 0:
            sector_weighted_return = (
                sum(w * r for _, w, r in members) / sector_weight
            )
        else:
            sector_weighted_return = 0.0
        sector_relative_return = (
            sector_weighted_return - index_weighted_return
        )
        adv = sum(1 for _, _, r in members if r > band)
        dec = sum(1 for _, _, r in members if r < -band)
        unc = len(members) - adv - dec
        participation_ratio = (
            len(members) / universe.observed_constituent_count
            if universe.observed_constituent_count > 0
            else 0.0
        )
        sorted_by_contrib = sorted(
            members,
            key=lambda m: (-(m[1] * m[2]), m[0]),
        )
        top_contributor = (
            sorted_by_contrib[0][0]
            if sorted_by_contrib and sorted_by_contrib[0][1] * sorted_by_contrib[0][2] > 0
            else None
        )
        sorted_asc = sorted(
            members,
            key=lambda m: (m[1] * m[2], m[0]),
        )
        top_detractor = (
            sorted_asc[0][0]
            if sorted_asc and sorted_asc[0][1] * sorted_asc[0][2] < 0
            else None
        )
        rows.append(
            SectorStrengthRowV1(
                sector=sector,
                constituent_count=len(members),
                total_sector_weight=sector_weight,
                sector_weighted_return=sector_weighted_return,
                sector_relative_return=sector_relative_return,
                advancing_count=adv,
                declining_count=dec,
                unchanged_count=unc,
                participation_ratio=participation_ratio,
                top_contributor=top_contributor,
                top_detractor=top_detractor,
            )
        )

    rows.sort(
        key=lambda r: (-r.sector_weighted_return, r.sector)
    )

    current_ranks = {
        row.sector: idx + 1 for idx, row in enumerate(rows)
    }
    current_relative_returns = {
        row.sector: row.sector_relative_return for row in rows
    }

    rotations: list[SectorRotationV1] = []
    if previous_snapshot is None or len(rows) < 2:
        for row in rows:
            rotations.append(
                SectorRotationV1(
                    sector=row.sector,
                    current_rank=current_ranks[row.sector],
                    previous_rank=None,
                    rank_change=None,
                    relative_return_change=None,
                    rotation_status=(
                        RotationStatusV1.INSUFFICIENT_HISTORY
                    ),
                )
            )
        rotation_overall = (
            RotationStatusV1.INSUFFICIENT_HISTORY
        )
    else:
        prev_ranks = dict(previous_snapshot.sector_ranks)
        prev_rel = dict(previous_snapshot.sector_relative_returns)
        any_rotation = False
        for row in rows:
            sector = row.sector
            current_rank = current_ranks[sector]
            previous_rank = prev_ranks.get(sector)
            if previous_rank is None:
                status = RotationStatusV1.INSUFFICIENT_HISTORY
                rank_change = None
                rel_change = None
            else:
                rank_change = previous_rank - current_rank
                prev_rr = prev_rel.get(sector)
                if prev_rr is None:
                    rel_change = None
                else:
                    rel_change = (
                        current_relative_returns[sector] - prev_rr
                    )
                rank_trigger = (
                    abs(rank_change) >= rotation_rank_threshold
                )
                rel_trigger = (
                    rel_change is not None
                    and abs(rel_change)
                    >= rotation_relative_return_threshold
                )
                if rank_trigger and rel_trigger:
                    status = RotationStatusV1.ROTATION
                    any_rotation = True
                else:
                    status = RotationStatusV1.STABLE
            rotations.append(
                SectorRotationV1(
                    sector=sector,
                    current_rank=current_rank,
                    previous_rank=previous_rank,
                    rank_change=rank_change,
                    relative_return_change=rel_change,
                    rotation_status=status,
                )
            )
        if any_rotation:
            rotation_overall = RotationStatusV1.ROTATION
        elif any(
            r.rotation_status == RotationStatusV1.STABLE
            for r in rotations
        ):
            rotation_overall = RotationStatusV1.STABLE
        else:
            rotation_overall = (
                RotationStatusV1.INSUFFICIENT_HISTORY
            )

    coverage_ratio = (
        len(rows) / universe.expected_constituent_count
        if universe.expected_constituent_count > 0
        else 0.0
    )
    is_partial = (
        universe.is_partial
        or bool(missing)
        or bool(stale)
        or bool(unsectored)
    )
    if not rows:
        evidence_status = "UNAVAILABLE"
    elif is_partial:
        evidence_status = "PARTIAL"
    else:
        evidence_status = "READY"

    warnings: list[str] = list(universe.warnings)
    if unsectored:
        warnings.append(
            f"{len(unsectored)} constituent(s) had no sector mapping"
        )
    if missing:
        warnings.append(
            f"{len(missing)} constituent(s) had no observation"
        )
    if stale:
        warnings.append(
            f"{len(stale)} constituent(s) were stale"
        )
    if universe.is_partial:
        warnings.append(
            f"universe is partial: {universe.missing_reason}"
        )
    if previous_snapshot is None:
        warnings.append(
            "rotation requires a previous snapshot; "
            "reported INSUFFICIENT_HISTORY"
        )

    return SectorStrengthResultV1(
        universe_id=universe.universe_id,
        universe_version=universe.universe_version,
        universe_sha256=universe.universe_sha256,
        index_symbol=universe.index_symbol,
        index_exchange=universe.index_exchange,
        calculated_at=calculated,
        horizon=horizon,
        stale_after_seconds=float(stale_after_seconds),
        rotation_rank_threshold=int(rotation_rank_threshold),
        rotation_relative_return_threshold=float(
            rotation_relative_return_threshold
        ),
        index_weighted_return=index_weighted_return,
        rows=tuple(rows),
        rotations=tuple(rotations),
        unsectored_constituents=tuple(unsectored),
        missing_constituents=tuple(missing),
        stale_constituents=tuple(stale),
        rotation_overall_status=rotation_overall,
        coverage_ratio=coverage_ratio,
        is_partial=is_partial,
        evidence_status=evidence_status,
        warnings=tuple(warnings),
    )


__all__ = [
    "DEFAULT_ROTATION_RANK_THRESHOLD",
    "DEFAULT_ROTATION_RELATIVE_RETURN_THRESHOLD",
    "DEFAULT_STALE_AFTER_SECONDS",
    "SECTOR_STRENGTH_SCHEMA_V1",
    "PreviousSectorSnapshotV1",
    "RotationStatusV1",
    "SectorReturnInputV1",
    "SectorRotationV1",
    "SectorStrengthResultV1",
    "SectorStrengthRowV1",
    "compute_sector_strength_v1",
]
