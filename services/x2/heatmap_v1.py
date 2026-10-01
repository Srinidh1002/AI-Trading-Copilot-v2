"""Numeric heatmap data engine for X2.

Produces structured numeric records for a per-constituent heatmap. This
is not an image renderer and does not attempt to recreate any provider
UI.

Design constraints:

* The heatmap is derived from the same underlying constituent returns
  and weights used by the influence and weighted-breadth engines. It is
  therefore **not** an independent market vote. Downstream consumers
  must not treat a heatmap's colour-bucket assignment as a separate
  directional signal.
* A large price change or a volume spike is not evidence of
  institutional activity. This module labels nothing as such.
* Deterministic ordering: records are sorted by ``(return_fraction desc,
  weight_value desc, canonical_id asc)``.
* Concentration: top-K share of absolute return value, K configurable.
* Outlier classification uses an explicit, documented z-score threshold
  against the observed returns in the same snapshot. It does not
  compare across snapshots.
"""
from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from hashlib import sha256

from services.x2.constituent_universe_v1 import (
    ConstituentUniverseV1,
    X2ConstituentError,
)

HEATMAP_SCHEMA_V1 = "X2_HEATMAP_V1"

DEFAULT_TOP_K = 5
DEFAULT_OUTLIER_Z_THRESHOLD = 2.0


class ReturnBucketV1(StrEnum):
    STRONG_NEGATIVE = "STRONG_NEGATIVE"
    NEGATIVE = "NEGATIVE"
    NEUTRAL = "NEUTRAL"
    POSITIVE = "POSITIVE"
    STRONG_POSITIVE = "STRONG_POSITIVE"


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
class HeatmapEntryV1:
    canonical_constituent_id: str
    provider_symbol: str
    exchange: str
    weight_value: float
    weight_unit: str
    return_fraction: float
    contribution: float
    sector: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "canonical_constituent_id": self.canonical_constituent_id,
            "provider_symbol": self.provider_symbol,
            "exchange": self.exchange,
            "weight_value": float(self.weight_value),
            "weight_unit": self.weight_unit,
            "return_fraction": float(self.return_fraction),
            "contribution": float(self.contribution),
            "sector": self.sector,
        }


@dataclass(frozen=True, slots=True)
class HeatmapRecordV1:
    entry: HeatmapEntryV1
    return_bucket: ReturnBucketV1
    is_outlier: bool
    z_score: float | None

    def to_dict(self) -> dict[str, object]:
        return {
            **self.entry.to_dict(),
            "return_bucket": self.return_bucket.value,
            "is_outlier": self.is_outlier,
            "z_score": self.z_score,
        }


@dataclass(frozen=True, slots=True)
class HeatmapResultV1:
    universe_id: str
    universe_version: str
    universe_sha256: str
    index_symbol: str
    index_exchange: str
    calculated_at: datetime
    top_k: int
    outlier_z_threshold: float
    strong_return_threshold: float
    records: tuple[HeatmapRecordV1, ...]
    top_k_abs_return_share: float
    outlier_canonical_ids: tuple[str, ...]
    concentration_flag: bool
    coverage_ratio: float
    is_partial: bool
    evidence_status: str
    warnings: tuple[str, ...] = ()
    schema_version: str = HEATMAP_SCHEMA_V1

    def __post_init__(self) -> None:
        _aware("calculated_at", self.calculated_at)
        if self.schema_version != HEATMAP_SCHEMA_V1:
            raise X2ConstituentError("unsupported heatmap schema.")
        if (
            self.top_k_abs_return_share < 0
            or self.top_k_abs_return_share > 1
        ):
            raise X2ConstituentError(
                "top_k_abs_return_share must be between 0 and 1."
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
            "top_k": int(self.top_k),
            "outlier_z_threshold": float(self.outlier_z_threshold),
            "strong_return_threshold": float(
                self.strong_return_threshold
            ),
            "records": [r.to_dict() for r in self.records],
            "top_k_abs_return_share": float(
                self.top_k_abs_return_share
            ),
            "outlier_canonical_ids": list(self.outlier_canonical_ids),
            "concentration_flag": bool(self.concentration_flag),
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
class HeatmapInputV1:
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


def _bucket(
    return_fraction: float, strong_threshold: float
) -> ReturnBucketV1:
    if return_fraction >= strong_threshold:
        return ReturnBucketV1.STRONG_POSITIVE
    if return_fraction > 0:
        return ReturnBucketV1.POSITIVE
    if return_fraction <= -strong_threshold:
        return ReturnBucketV1.STRONG_NEGATIVE
    if return_fraction < 0:
        return ReturnBucketV1.NEGATIVE
    return ReturnBucketV1.NEUTRAL


def compute_heatmap_v1(
    *,
    universe: ConstituentUniverseV1,
    inputs: Mapping[str, HeatmapInputV1],
    calculated_at: datetime,
    top_k: int = DEFAULT_TOP_K,
    outlier_z_threshold: float = DEFAULT_OUTLIER_Z_THRESHOLD,
    strong_return_threshold: float = 0.01,
) -> HeatmapResultV1:
    if not isinstance(universe, ConstituentUniverseV1):
        raise X2ConstituentError(
            "universe must be ConstituentUniverseV1."
        )
    if not isinstance(inputs, Mapping):
        raise X2ConstituentError("inputs must be a mapping.")
    if (
        not isinstance(top_k, int)
        or isinstance(top_k, bool)
        or top_k < 1
    ):
        raise X2ConstituentError("top_k must be a positive integer.")
    if not _finite(outlier_z_threshold) or outlier_z_threshold <= 0:
        raise X2ConstituentError(
            "outlier_z_threshold must be finite and positive."
        )
    if (
        not _finite(strong_return_threshold)
        or strong_return_threshold <= 0
    ):
        raise X2ConstituentError(
            "strong_return_threshold must be finite and positive."
        )
    calculated = _aware("calculated_at", calculated_at)

    entries: list[HeatmapEntryV1] = []
    for entry in universe.constituents:
        raw = inputs.get(entry.canonical_constituent_id)
        if raw is None:
            continue
        if not isinstance(raw, HeatmapInputV1):
            raise X2ConstituentError(
                "input must be HeatmapInputV1."
            )
        if raw.observed_at > calculated:
            raise X2ConstituentError(
                f"input for {entry.canonical_constituent_id} "
                "is in the future relative to calculated_at."
            )
        contribution = float(entry.weight) * raw.return_fraction
        entries.append(
            HeatmapEntryV1(
                canonical_constituent_id=(
                    entry.canonical_constituent_id
                ),
                provider_symbol=entry.provider_symbol,
                exchange=entry.exchange,
                weight_value=float(entry.weight),
                weight_unit=universe.weight_unit.value,
                return_fraction=raw.return_fraction,
                contribution=contribution,
                sector=entry.sector,
            )
        )

    entries.sort(
        key=lambda e: (
            -e.return_fraction,
            -e.weight_value,
            e.canonical_constituent_id,
        )
    )

    returns = [e.return_fraction for e in entries]
    n = len(returns)
    if n >= 2:
        mean = sum(returns) / n
        var = sum((r - mean) ** 2 for r in returns) / n
        std = math.sqrt(var)
    else:
        mean = returns[0] if returns else 0.0
        std = 0.0

    records: list[HeatmapRecordV1] = []
    outliers: list[str] = []
    for e in entries:
        if std > 0:
            z = (e.return_fraction - mean) / std
        else:
            z = 0.0
        is_outlier = abs(z) >= outlier_z_threshold if n >= 3 else False
        if is_outlier:
            outliers.append(e.canonical_constituent_id)
        records.append(
            HeatmapRecordV1(
                entry=e,
                return_bucket=_bucket(
                    e.return_fraction, strong_return_threshold
                ),
                is_outlier=is_outlier,
                z_score=z,
            )
        )

    abs_returns = sorted(
        (abs(e.return_fraction) for e in entries),
        reverse=True,
    )
    abs_total = sum(abs_returns)
    if abs_total <= 0:
        top_k_share = 0.0
    else:
        effective_k = min(top_k, len(abs_returns))
        top_k_share = sum(abs_returns[:effective_k]) / abs_total

    # Concentration flag: top-K share exceeds the proportional
    # expectation by 2x. This is a heuristic, documented and stable.
    if n > 0:
        proportional = min(top_k, n) / n
        concentration_flag = (
            top_k_share >= 2 * proportional
            if proportional > 0
            else False
        )
    else:
        concentration_flag = False

    coverage_ratio = (
        len(entries) / universe.expected_constituent_count
        if universe.expected_constituent_count > 0
        else 0.0
    )

    if len(entries) == 0:
        evidence_status = "UNAVAILABLE"
    elif universe.is_partial or len(entries) < universe.observed_constituent_count:
        evidence_status = "PARTIAL"
    else:
        evidence_status = "READY"

    warnings: list[str] = list(universe.warnings)
    if not entries:
        warnings.append("no observations supplied")
    elif len(entries) < universe.observed_constituent_count:
        warnings.append(
            f"only {len(entries)} of "
            f"{universe.observed_constituent_count} observed "
            "constituents have a heatmap entry"
        )
    if universe.is_partial:
        warnings.append(
            f"universe is partial: {universe.missing_reason}"
        )

    return HeatmapResultV1(
        universe_id=universe.universe_id,
        universe_version=universe.universe_version,
        universe_sha256=universe.universe_sha256,
        index_symbol=universe.index_symbol,
        index_exchange=universe.index_exchange,
        calculated_at=calculated,
        top_k=top_k,
        outlier_z_threshold=float(outlier_z_threshold),
        strong_return_threshold=float(strong_return_threshold),
        records=tuple(records),
        top_k_abs_return_share=top_k_share,
        outlier_canonical_ids=tuple(outliers),
        concentration_flag=concentration_flag,
        coverage_ratio=coverage_ratio,
        is_partial=universe.is_partial
        or len(entries) < universe.observed_constituent_count,
        evidence_status=evidence_status,
        warnings=tuple(warnings),
    )


__all__ = [
    "DEFAULT_OUTLIER_Z_THRESHOLD",
    "DEFAULT_TOP_K",
    "HEATMAP_SCHEMA_V1",
    "HeatmapEntryV1",
    "HeatmapInputV1",
    "HeatmapRecordV1",
    "HeatmapResultV1",
    "ReturnBucketV1",
    "compute_heatmap_v1",
]
