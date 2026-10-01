"""Constituent influence engine for X2.

Given a :class:`ConstituentUniverseV1` and a set of per-constituent
observations, compute the weighted-return contribution of each observed
constituent.

Scope and limits:

* We report **weighted-return contribution**, not exact index-point
  attribution. Exact index-point attribution requires the index divisor
  and methodology, which are not authoritative evidence here.
* Contribution unit: ``weight_value * return_fraction``. For PERCENT
  weight units, contribution is in "index percent points"; for
  FRACTION weight units, contribution is dimensionless.
* A missing observation for a constituent in the universe is recorded as
  missing, not as zero contribution.
* A stale observation is not admitted into the total; it is recorded as
  stale with its own reason.
* Concentration is measured as the top-K share of the absolute
  contributions, K configurable; the default is 3.
* Deterministic: identical inputs produce identical canonical JSON and
  SHA-256, regardless of caller iteration order.
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
    WeightUnitV1,
    X2ConstituentError,
)

CONSTITUENT_INFLUENCE_SCHEMA_V1 = "X2_CONSTITUENT_INFLUENCE_V1"

DEFAULT_TOP_K = 3
DEFAULT_STALE_AFTER_SECONDS = 60.0


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
class ConstituentObservationV1:
    canonical_constituent_id: str
    reference_price: float
    current_price: float
    observed_at: datetime

    def __post_init__(self) -> None:
        if (
            not isinstance(self.canonical_constituent_id, str)
            or not self.canonical_constituent_id.strip()
        ):
            raise X2ConstituentError(
                "canonical_constituent_id must be a non-empty string."
            )
        for name, value in (
            ("reference_price", self.reference_price),
            ("current_price", self.current_price),
        ):
            if not _finite(value) or float(value) <= 0:
                raise X2ConstituentError(
                    f"{name} must be finite and positive."
                )
        object.__setattr__(
            self,
            "observed_at",
            _aware("observed_at", self.observed_at),
        )

    @property
    def return_fraction(self) -> float:
        return (
            float(self.current_price) / float(self.reference_price)
        ) - 1.0


@dataclass(frozen=True, slots=True)
class ConstituentContributionV1:
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
class MissingConstituentV1:
    canonical_constituent_id: str
    reason_code: str

    def to_dict(self) -> dict[str, object]:
        return {
            "canonical_constituent_id": self.canonical_constituent_id,
            "reason_code": self.reason_code,
        }


@dataclass(frozen=True, slots=True)
class ConstituentInfluenceResultV1:
    universe_id: str
    universe_version: str
    universe_sha256: str
    index_symbol: str
    index_exchange: str
    weight_unit: str
    calculated_at: datetime
    observations_considered_at: datetime
    contributions: tuple[ConstituentContributionV1, ...]
    top_positive_contributors: tuple[ConstituentContributionV1, ...]
    top_negative_contributors: tuple[ConstituentContributionV1, ...]
    missing_constituents: tuple[MissingConstituentV1, ...]
    stale_constituents: tuple[MissingConstituentV1, ...]
    total_observed_weight: float
    total_contribution: float
    concentration_top_k: int
    concentration_top_k_share: float
    coverage_ratio: float
    is_partial: bool
    warnings: tuple[str, ...] = ()
    schema_version: str = CONSTITUENT_INFLUENCE_SCHEMA_V1

    def __post_init__(self) -> None:
        _aware("calculated_at", self.calculated_at)
        _aware("observations_considered_at", self.observations_considered_at)
        if self.weight_unit not in (
            WeightUnitV1.PERCENT.value,
            WeightUnitV1.FRACTION.value,
        ):
            raise X2ConstituentError(
                "unsupported weight_unit in influence result."
            )
        if self.schema_version != CONSTITUENT_INFLUENCE_SCHEMA_V1:
            raise X2ConstituentError(
                "unsupported constituent influence schema."
            )
        if self.coverage_ratio < 0 or self.coverage_ratio > 1:
            raise X2ConstituentError(
                "coverage_ratio must be between 0 and 1."
            )
        if (
            self.concentration_top_k_share < 0
            or self.concentration_top_k_share > 1
        ):
            raise X2ConstituentError(
                "concentration_top_k_share must be between 0 and 1."
            )
        if not isinstance(self.is_partial, bool):
            raise X2ConstituentError("is_partial must be a boolean.")
        object.__setattr__(
            self, "warnings", tuple(self.warnings)
        )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "universe_id": self.universe_id,
            "universe_version": self.universe_version,
            "universe_sha256": self.universe_sha256,
            "index_symbol": self.index_symbol,
            "index_exchange": self.index_exchange,
            "weight_unit": self.weight_unit,
            "calculated_at": self.calculated_at.isoformat(),
            "observations_considered_at": (
                self.observations_considered_at.isoformat()
            ),
            "contributions": [
                c.to_dict() for c in self.contributions
            ],
            "top_positive_contributors": [
                c.to_dict() for c in self.top_positive_contributors
            ],
            "top_negative_contributors": [
                c.to_dict() for c in self.top_negative_contributors
            ],
            "missing_constituents": [
                m.to_dict() for m in self.missing_constituents
            ],
            "stale_constituents": [
                s.to_dict() for s in self.stale_constituents
            ],
            "total_observed_weight": float(self.total_observed_weight),
            "total_contribution": float(self.total_contribution),
            "concentration_top_k": int(self.concentration_top_k),
            "concentration_top_k_share": float(
                self.concentration_top_k_share
            ),
            "coverage_ratio": float(self.coverage_ratio),
            "is_partial": bool(self.is_partial),
            "warnings": list(self.warnings),
        }

    def canonical_json(self) -> str:
        return _canonical_json(self.canonical_payload())

    @property
    def result_sha256(self) -> str:
        return sha256(
            self.canonical_json().encode("utf-8")
        ).hexdigest()


def compute_constituent_influence_v1(
    *,
    universe: ConstituentUniverseV1,
    observations: Mapping[str, ConstituentObservationV1],
    calculated_at: datetime,
    top_k: int = DEFAULT_TOP_K,
    stale_after_seconds: float = DEFAULT_STALE_AFTER_SECONDS,
) -> ConstituentInfluenceResultV1:
    """Compute weighted-return contribution for observed constituents.

    ``observations`` is keyed by ``canonical_constituent_id``. Any
    constituent in the universe that does not have a matching
    observation is recorded as missing. Any observation whose
    ``observed_at`` is older than ``calculated_at - stale_after_seconds``
    is recorded as stale.
    """
    if not isinstance(universe, ConstituentUniverseV1):
        raise X2ConstituentError(
            "universe must be ConstituentUniverseV1."
        )
    if not isinstance(observations, Mapping):
        raise X2ConstituentError("observations must be a mapping.")
    if (
        not isinstance(top_k, int)
        or isinstance(top_k, bool)
        or top_k < 1
    ):
        raise X2ConstituentError("top_k must be a positive integer.")
    if (
        isinstance(stale_after_seconds, bool)
        or not isinstance(stale_after_seconds, (int, float))
        or not math.isfinite(float(stale_after_seconds))
        or stale_after_seconds < 0
    ):
        raise X2ConstituentError(
            "stale_after_seconds must be a non-negative number."
        )
    calculated = _aware("calculated_at", calculated_at)
    stale_cutoff = calculated - timedelta(
        seconds=float(stale_after_seconds)
    )

    contributions: list[ConstituentContributionV1] = []
    missing: list[MissingConstituentV1] = []
    stale: list[MissingConstituentV1] = []

    for entry in universe.constituents:
        obs = observations.get(entry.canonical_constituent_id)
        if obs is None:
            missing.append(
                MissingConstituentV1(
                    canonical_constituent_id=entry.canonical_constituent_id,
                    reason_code="NO_OBSERVATION",
                )
            )
            continue
        if not isinstance(obs, ConstituentObservationV1):
            raise X2ConstituentError(
                "observation must be ConstituentObservationV1."
            )
        if obs.observed_at < stale_cutoff:
            stale.append(
                MissingConstituentV1(
                    canonical_constituent_id=(
                        entry.canonical_constituent_id
                    ),
                    reason_code="STALE_OBSERVATION",
                )
            )
            continue
        if obs.observed_at > calculated:
            raise X2ConstituentError(
                f"observation for {entry.canonical_constituent_id} "
                "is in the future relative to calculated_at."
            )
        contribution_value = (
            float(entry.weight) * obs.return_fraction
        )
        contributions.append(
            ConstituentContributionV1(
                canonical_constituent_id=(
                    entry.canonical_constituent_id
                ),
                provider_symbol=entry.provider_symbol,
                exchange=entry.exchange,
                weight_value=float(entry.weight),
                weight_unit=universe.weight_unit.value,
                return_fraction=obs.return_fraction,
                contribution=contribution_value,
                sector=entry.sector,
            )
        )

    contributions.sort(
        key=lambda c: (
            -c.contribution,
            c.canonical_constituent_id,
        )
    )
    positives = tuple(c for c in contributions if c.contribution > 0)
    negatives = tuple(c for c in contributions if c.contribution < 0)
    top_positive = positives[:top_k]
    top_negative = tuple(
        sorted(negatives, key=lambda c: (c.contribution, c.canonical_constituent_id))[
            :top_k
        ]
    )

    total_observed_weight = sum(
        c.weight_value for c in contributions
    )
    total_contribution = sum(
        c.contribution for c in contributions
    )

    abs_sorted = sorted(
        (abs(c.contribution) for c in contributions),
        reverse=True,
    )
    abs_total = sum(abs_sorted)
    if abs_total <= 0:
        concentration_share = 0.0
    else:
        effective_k = min(top_k, len(abs_sorted))
        concentration_share = (
            sum(abs_sorted[:effective_k]) / abs_total
        )

    observed_count = len(contributions)
    expected_count = universe.expected_constituent_count
    if expected_count > 0:
        coverage_ratio = observed_count / expected_count
    else:
        coverage_ratio = 0.0

    is_partial = (
        universe.is_partial
        or bool(missing)
        or bool(stale)
    )

    warnings: list[str] = list(universe.warnings)
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

    return ConstituentInfluenceResultV1(
        universe_id=universe.universe_id,
        universe_version=universe.universe_version,
        universe_sha256=universe.universe_sha256,
        index_symbol=universe.index_symbol,
        index_exchange=universe.index_exchange,
        weight_unit=universe.weight_unit.value,
        calculated_at=calculated,
        observations_considered_at=calculated,
        contributions=tuple(contributions),
        top_positive_contributors=top_positive,
        top_negative_contributors=top_negative,
        missing_constituents=tuple(missing),
        stale_constituents=tuple(stale),
        total_observed_weight=total_observed_weight,
        total_contribution=total_contribution,
        concentration_top_k=top_k,
        concentration_top_k_share=concentration_share,
        coverage_ratio=coverage_ratio,
        is_partial=is_partial,
        warnings=tuple(warnings),
    )


__all__ = [
    "CONSTITUENT_INFLUENCE_SCHEMA_V1",
    "DEFAULT_STALE_AFTER_SECONDS",
    "DEFAULT_TOP_K",
    "ConstituentContributionV1",
    "ConstituentInfluenceResultV1",
    "ConstituentObservationV1",
    "MissingConstituentV1",
    "compute_constituent_influence_v1",
]
