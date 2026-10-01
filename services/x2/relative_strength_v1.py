"""Relative strength engine for X2.

Compares aligned returns between two identities:

* constituent vs its index
* constituent vs its sector benchmark (sector-weighted return)
* sector vs index
* NIFTY vs SENSEX

Discipline:

* Both sides of a comparison must be observed at the same timestamp and
  carry the same horizon label. Misaligned or mismatched pairs are
  reported as ``UNALIGNED`` and are not admitted into the result.
* Relative outperformance is not an absolute bullish signal. The result
  carries only the arithmetic difference and its classification.
* NIFTY and SENSEX are compared only on aligned returns, never on raw
  index levels.
* Missing data for either side yields ``INSUFFICIENT_HISTORY`` for that
  pair. Other pairs are unaffected.
"""
from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256

from services.x2.constituent_universe_v1 import X2ConstituentError

RELATIVE_STRENGTH_SCHEMA_V1 = "X2_RELATIVE_STRENGTH_V1"

DEFAULT_NEUTRAL_BAND = 0.0005  # 0.05% as a fraction


class RelativeStrengthStatusV1:
    OK = "OK"
    UNALIGNED = "UNALIGNED"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"


class RelativeStrengthClassV1:
    OUTPERFORMING = "OUTPERFORMING"
    UNDERPERFORMING = "UNDERPERFORMING"
    NEUTRAL = "NEUTRAL"


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
class ReturnObservationV1:
    identity: str
    return_fraction: float
    observed_at: datetime
    horizon: str

    def __post_init__(self) -> None:
        if not isinstance(self.identity, str) or not self.identity.strip():
            raise X2ConstituentError(
                "identity must be a non-empty string."
            )
        if not _finite(self.return_fraction):
            raise X2ConstituentError(
                "return_fraction must be numeric."
            )
        object.__setattr__(
            self, "observed_at", _aware("observed_at", self.observed_at)
        )
        if (
            not isinstance(self.horizon, str)
            or not self.horizon.strip()
        ):
            raise X2ConstituentError(
                "horizon must be a non-empty string."
            )


@dataclass(frozen=True, slots=True)
class RelativeStrengthPairV1:
    subject: str
    benchmark: str
    relationship: str
    status: str
    subject_return: float | None
    benchmark_return: float | None
    relative_return: float | None
    classification: str | None
    observed_at: datetime | None
    horizon: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "subject": self.subject,
            "benchmark": self.benchmark,
            "relationship": self.relationship,
            "status": self.status,
            "subject_return": self.subject_return,
            "benchmark_return": self.benchmark_return,
            "relative_return": self.relative_return,
            "classification": self.classification,
            "observed_at": (
                self.observed_at.isoformat()
                if self.observed_at is not None
                else None
            ),
            "horizon": self.horizon,
        }


@dataclass(frozen=True, slots=True)
class RelativeStrengthResultV1:
    calculated_at: datetime
    horizon: str
    neutral_band: float
    pairs: tuple[RelativeStrengthPairV1, ...]
    nifty_vs_sensex: RelativeStrengthPairV1 | None
    evidence_status: str
    warnings: tuple[str, ...] = ()
    schema_version: str = RELATIVE_STRENGTH_SCHEMA_V1

    def __post_init__(self) -> None:
        _aware("calculated_at", self.calculated_at)
        if self.schema_version != RELATIVE_STRENGTH_SCHEMA_V1:
            raise X2ConstituentError(
                "unsupported relative strength schema."
            )
        if self.evidence_status not in (
            "READY",
            "PARTIAL",
            "UNAVAILABLE",
        ):
            raise X2ConstituentError(
                "unsupported relative strength evidence_status."
            )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "calculated_at": self.calculated_at.isoformat(),
            "horizon": self.horizon,
            "neutral_band": float(self.neutral_band),
            "pairs": [p.to_dict() for p in self.pairs],
            "nifty_vs_sensex": (
                self.nifty_vs_sensex.to_dict()
                if self.nifty_vs_sensex is not None
                else None
            ),
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


def _classify(
    relative_return: float, neutral_band: float
) -> str:
    if relative_return > neutral_band:
        return RelativeStrengthClassV1.OUTPERFORMING
    if relative_return < -neutral_band:
        return RelativeStrengthClassV1.UNDERPERFORMING
    return RelativeStrengthClassV1.NEUTRAL


def _pair(
    *,
    subject_id: str,
    benchmark_id: str,
    relationship: str,
    observations: Mapping[str, ReturnObservationV1],
    neutral_band: float,
) -> RelativeStrengthPairV1:
    subj = observations.get(subject_id)
    bench = observations.get(benchmark_id)
    if subj is None or bench is None:
        return RelativeStrengthPairV1(
            subject=subject_id,
            benchmark=benchmark_id,
            relationship=relationship,
            status=RelativeStrengthStatusV1.INSUFFICIENT_HISTORY,
            subject_return=subj.return_fraction if subj else None,
            benchmark_return=(
                bench.return_fraction if bench else None
            ),
            relative_return=None,
            classification=None,
            observed_at=None,
            horizon=None,
        )
    if (
        subj.observed_at != bench.observed_at
        or subj.horizon != bench.horizon
    ):
        return RelativeStrengthPairV1(
            subject=subject_id,
            benchmark=benchmark_id,
            relationship=relationship,
            status=RelativeStrengthStatusV1.UNALIGNED,
            subject_return=subj.return_fraction,
            benchmark_return=bench.return_fraction,
            relative_return=None,
            classification=None,
            observed_at=None,
            horizon=None,
        )
    relative = subj.return_fraction - bench.return_fraction
    return RelativeStrengthPairV1(
        subject=subject_id,
        benchmark=benchmark_id,
        relationship=relationship,
        status=RelativeStrengthStatusV1.OK,
        subject_return=subj.return_fraction,
        benchmark_return=bench.return_fraction,
        relative_return=relative,
        classification=_classify(relative, neutral_band),
        observed_at=subj.observed_at,
        horizon=subj.horizon,
    )


def compute_relative_strength_v1(
    *,
    observations: Mapping[str, ReturnObservationV1],
    calculated_at: datetime,
    horizon: str,
    pairs_to_compute: tuple[
        tuple[str, str, str],
        ...,
    ],
    neutral_band: float = DEFAULT_NEUTRAL_BAND,
) -> RelativeStrengthResultV1:
    """Compute a deterministic set of relative-strength pairs.

    ``pairs_to_compute`` is a tuple of ``(subject_id, benchmark_id,
    relationship)``. Each relationship label is copied verbatim into
    the result; callers can use labels such as
    ``"CONSTITUENT_VS_INDEX"``, ``"CONSTITUENT_VS_SECTOR"``,
    ``"SECTOR_VS_INDEX"``, ``"INDEX_VS_INDEX"``.
    """
    if not isinstance(observations, Mapping):
        raise X2ConstituentError("observations must be a mapping.")
    if not isinstance(horizon, str) or not horizon.strip():
        raise X2ConstituentError("horizon must be non-empty.")
    if (
        not _finite(neutral_band)
        or float(neutral_band) < 0
    ):
        raise X2ConstituentError(
            "neutral_band must be finite and non-negative."
        )
    if not isinstance(pairs_to_compute, tuple):
        raise X2ConstituentError(
            "pairs_to_compute must be a tuple."
        )
    if not pairs_to_compute:
        raise X2ConstituentError(
            "at least one pair must be supplied."
        )
    calculated = _aware("calculated_at", calculated_at)

    normalised_pairs: list[
        tuple[str, str, str]
    ] = []
    for item in pairs_to_compute:
        if (
            not isinstance(item, tuple)
            or len(item) != 3
            or not all(
                isinstance(x, str) and x.strip()
                for x in item
            )
        ):
            raise X2ConstituentError(
                "each pair must be a 3-tuple of non-empty strings."
            )
        normalised_pairs.append((item[0], item[1], item[2]))
    normalised_pairs.sort(
        key=lambda x: (x[2], x[0], x[1])
    )

    results: list[RelativeStrengthPairV1] = []
    for subject_id, benchmark_id, relationship in normalised_pairs:
        results.append(
            _pair(
                subject_id=subject_id,
                benchmark_id=benchmark_id,
                relationship=relationship,
                observations=observations,
                neutral_band=float(neutral_band),
            )
        )

    nifty_vs_sensex: RelativeStrengthPairV1 | None = None
    for pair in results:
        if (
            pair.relationship == "INDEX_VS_INDEX"
            and pair.subject == "NIFTY"
            and pair.benchmark == "SENSEX"
        ):
            nifty_vs_sensex = pair
            break

    ok_count = sum(
        1 for p in results if p.status == RelativeStrengthStatusV1.OK
    )
    if ok_count == 0:
        evidence_status = "UNAVAILABLE"
    elif ok_count < len(results):
        evidence_status = "PARTIAL"
    else:
        evidence_status = "READY"

    warnings: list[str] = []
    unaligned = sum(
        1 for p in results
        if p.status == RelativeStrengthStatusV1.UNALIGNED
    )
    if unaligned:
        warnings.append(
            f"{unaligned} pair(s) had misaligned returns"
        )
    insufficient = sum(
        1 for p in results
        if p.status == RelativeStrengthStatusV1.INSUFFICIENT_HISTORY
    )
    if insufficient:
        warnings.append(
            f"{insufficient} pair(s) had insufficient data"
        )

    return RelativeStrengthResultV1(
        calculated_at=calculated,
        horizon=horizon,
        neutral_band=float(neutral_band),
        pairs=tuple(results),
        nifty_vs_sensex=nifty_vs_sensex,
        evidence_status=evidence_status,
        warnings=tuple(warnings),
    )


__all__ = [
    "DEFAULT_NEUTRAL_BAND",
    "RELATIVE_STRENGTH_SCHEMA_V1",
    "RelativeStrengthClassV1",
    "RelativeStrengthPairV1",
    "RelativeStrengthResultV1",
    "RelativeStrengthStatusV1",
    "ReturnObservationV1",
    "compute_relative_strength_v1",
]
