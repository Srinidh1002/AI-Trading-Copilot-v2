"""Weighted breadth engine for X2.

Consumes a :class:`ConstituentUniverseV1` plus per-constituent
observations and per-constituent indicator states (above VWAP / EMA20 /
EMA50), and produces:

* ``WeightedBreadthResultV1`` - the rich X2 evidence payload with
  weighted advancing / declining exposure, weighted percentages above
  indicators, participation and concentration.
* an optional :class:`MarketBreadthSnapshotV1` so the existing
  ``evaluate_market_breadth`` classifier remains the sole authority for
  BULLISH/BEARISH/NEUTRAL.

Discipline:

* A missing VWAP or EMA observation is never treated as "below".
  Percentages use an explicitly defined eligible denominator.
* A constituent without a return observation is never treated as
  unchanged; it is recorded as missing.
* A stale observation is not admitted; it is recorded as stale.
* Partial coverage is preserved; totals are not silently renormalised
  to 100%.
* Thresholds are policy-driven. The defaults are conservative and
  documented, not tuned against PAPER outcomes.
"""
from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256

from services.contracts.market_breadth_snapshot_v1 import (
    MarketBreadthSnapshotV1,
)
from services.x2.constituent_universe_v1 import (
    ConstituentUniverseV1,
    X2ConstituentError,
)

WEIGHTED_BREADTH_SCHEMA_V1 = "X2_WEIGHTED_BREADTH_V1"

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
class BreadthPolicyV1:
    """Policy thresholds for weighted breadth.

    Defaults are intentionally simple and documented. They are not
    derived from PAPER outcomes.
    """

    unchanged_band_pct: float = 0.05
    min_coverage_ratio: float = 0.5
    bullish_advance_decline_ratio: float = 1.5
    bearish_advance_decline_ratio: float = 0.67

    def __post_init__(self) -> None:
        for name, value in (
            ("unchanged_band_pct", self.unchanged_band_pct),
            (
                "bullish_advance_decline_ratio",
                self.bullish_advance_decline_ratio,
            ),
            (
                "bearish_advance_decline_ratio",
                self.bearish_advance_decline_ratio,
            ),
        ):
            if not _finite(value) or float(value) <= 0:
                raise X2ConstituentError(
                    f"{name} must be finite and positive."
                )
        if not _finite(self.min_coverage_ratio):
            raise X2ConstituentError(
                "min_coverage_ratio must be numeric."
            )
        mcr = float(self.min_coverage_ratio)
        if mcr < 0 or mcr > 1:
            raise X2ConstituentError(
                "min_coverage_ratio must be between 0 and 1."
            )
        if (
            self.bearish_advance_decline_ratio
            >= self.bullish_advance_decline_ratio
        ):
            raise X2ConstituentError(
                "bearish_advance_decline_ratio must be less than "
                "bullish_advance_decline_ratio."
            )


DEFAULT_BREADTH_POLICY_V1 = BreadthPolicyV1()


@dataclass(frozen=True, slots=True)
class ConstituentBreadthInputV1:
    """Per-constituent input for weighted breadth.

    ``above_vwap`` / ``above_ema20`` / ``above_ema50`` are ``bool | None``.
    ``None`` means the indicator was not computed for this constituent;
    it is excluded from that indicator's denominator.
    """

    canonical_constituent_id: str
    change_pct: float
    observed_at: datetime
    above_vwap: bool | None = None
    above_ema20: bool | None = None
    above_ema50: bool | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.canonical_constituent_id, str)
            or not self.canonical_constituent_id.strip()
        ):
            raise X2ConstituentError(
                "canonical_constituent_id must be non-empty."
            )
        if not _finite(self.change_pct):
            raise X2ConstituentError("change_pct must be numeric.")
        object.__setattr__(
            self, "observed_at", _aware("observed_at", self.observed_at)
        )
        for name, value in (
            ("above_vwap", self.above_vwap),
            ("above_ema20", self.above_ema20),
            ("above_ema50", self.above_ema50),
        ):
            if value is not None and not isinstance(value, bool):
                raise X2ConstituentError(
                    f"{name} must be bool or None."
                )


@dataclass(frozen=True, slots=True)
class WeightedBreadthResultV1:
    universe_id: str
    universe_version: str
    universe_sha256: str
    index_symbol: str
    index_exchange: str
    calculated_at: datetime
    policy: BreadthPolicyV1

    advancing_count: int
    declining_count: int
    unchanged_count: int
    missing_count: int
    stale_count: int
    eligible_count: int

    advance_decline_ratio: float | None
    advance_decline_difference: int

    weighted_advancing_exposure: float
    weighted_declining_exposure: float
    weighted_advancing_pct: float | None
    weighted_declining_pct: float | None

    above_vwap_count: int
    above_vwap_eligible_count: int
    above_vwap_pct: float | None
    weighted_above_vwap_pct: float | None

    above_ema20_count: int
    above_ema20_eligible_count: int
    above_ema20_pct: float | None
    weighted_above_ema20_pct: float | None

    above_ema50_count: int
    above_ema50_eligible_count: int
    above_ema50_pct: float | None
    weighted_above_ema50_pct: float | None

    coverage_ratio: float
    is_partial: bool
    evidence_status: str
    warnings: tuple[str, ...] = ()
    schema_version: str = WEIGHTED_BREADTH_SCHEMA_V1

    def __post_init__(self) -> None:
        _aware("calculated_at", self.calculated_at)
        if self.schema_version != WEIGHTED_BREADTH_SCHEMA_V1:
            raise X2ConstituentError(
                "unsupported weighted breadth schema."
            )
        if self.evidence_status not in (
            "READY",
            "READY_WITH_WARNINGS",
            "PARTIAL",
            "UNAVAILABLE",
        ):
            raise X2ConstituentError(
                "unsupported evidence_status."
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
            "policy": {
                "unchanged_band_pct": float(
                    self.policy.unchanged_band_pct
                ),
                "min_coverage_ratio": float(
                    self.policy.min_coverage_ratio
                ),
                "bullish_advance_decline_ratio": float(
                    self.policy.bullish_advance_decline_ratio
                ),
                "bearish_advance_decline_ratio": float(
                    self.policy.bearish_advance_decline_ratio
                ),
            },
            "advancing_count": int(self.advancing_count),
            "declining_count": int(self.declining_count),
            "unchanged_count": int(self.unchanged_count),
            "missing_count": int(self.missing_count),
            "stale_count": int(self.stale_count),
            "eligible_count": int(self.eligible_count),
            "advance_decline_ratio": self.advance_decline_ratio,
            "advance_decline_difference": int(
                self.advance_decline_difference
            ),
            "weighted_advancing_exposure": float(
                self.weighted_advancing_exposure
            ),
            "weighted_declining_exposure": float(
                self.weighted_declining_exposure
            ),
            "weighted_advancing_pct": self.weighted_advancing_pct,
            "weighted_declining_pct": self.weighted_declining_pct,
            "above_vwap_count": int(self.above_vwap_count),
            "above_vwap_eligible_count": int(
                self.above_vwap_eligible_count
            ),
            "above_vwap_pct": self.above_vwap_pct,
            "weighted_above_vwap_pct": self.weighted_above_vwap_pct,
            "above_ema20_count": int(self.above_ema20_count),
            "above_ema20_eligible_count": int(
                self.above_ema20_eligible_count
            ),
            "above_ema20_pct": self.above_ema20_pct,
            "weighted_above_ema20_pct": self.weighted_above_ema20_pct,
            "above_ema50_count": int(self.above_ema50_count),
            "above_ema50_eligible_count": int(
                self.above_ema50_eligible_count
            ),
            "above_ema50_pct": self.above_ema50_pct,
            "weighted_above_ema50_pct": self.weighted_above_ema50_pct,
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


def _pct(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    return 100.0 * numerator / denominator


def compute_weighted_breadth_v1(
    *,
    universe: ConstituentUniverseV1,
    inputs: Mapping[str, ConstituentBreadthInputV1],
    calculated_at: datetime,
    policy: BreadthPolicyV1 = DEFAULT_BREADTH_POLICY_V1,
    stale_after_seconds: float = DEFAULT_STALE_AFTER_SECONDS,
) -> WeightedBreadthResultV1:
    if not isinstance(universe, ConstituentUniverseV1):
        raise X2ConstituentError(
            "universe must be ConstituentUniverseV1."
        )
    if not isinstance(inputs, Mapping):
        raise X2ConstituentError("inputs must be a mapping.")
    if not isinstance(policy, BreadthPolicyV1):
        raise X2ConstituentError(
            "policy must be BreadthPolicyV1."
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
    calculated = _aware("calculated_at", calculated_at)
    stale_cutoff = calculated - timedelta(
        seconds=float(stale_after_seconds)
    )
    band = float(policy.unchanged_band_pct)

    advancing: list[tuple[str, float]] = []
    declining: list[tuple[str, float]] = []
    unchanged: list[tuple[str, float]] = []
    missing = 0
    stale = 0

    vwap_above = 0
    vwap_eligible = 0
    vwap_weight_above = 0.0
    vwap_weight_eligible = 0.0

    ema20_above = 0
    ema20_eligible = 0
    ema20_weight_above = 0.0
    ema20_weight_eligible = 0.0

    ema50_above = 0
    ema50_eligible = 0
    ema50_weight_above = 0.0
    ema50_weight_eligible = 0.0

    for entry in universe.constituents:
        raw = inputs.get(entry.canonical_constituent_id)
        if raw is None:
            missing += 1
            continue
        if not isinstance(raw, ConstituentBreadthInputV1):
            raise X2ConstituentError(
                "input must be ConstituentBreadthInputV1."
            )
        if raw.observed_at < stale_cutoff:
            stale += 1
            continue
        if raw.observed_at > calculated:
            raise X2ConstituentError(
                f"input for {entry.canonical_constituent_id} "
                "is in the future relative to calculated_at."
            )

        weight = float(entry.weight)
        change = float(raw.change_pct)

        if change > band:
            advancing.append((entry.canonical_constituent_id, weight))
        elif change < -band:
            declining.append((entry.canonical_constituent_id, weight))
        else:
            unchanged.append((entry.canonical_constituent_id, weight))

        if raw.above_vwap is not None:
            vwap_eligible += 1
            vwap_weight_eligible += weight
            if raw.above_vwap:
                vwap_above += 1
                vwap_weight_above += weight
        if raw.above_ema20 is not None:
            ema20_eligible += 1
            ema20_weight_eligible += weight
            if raw.above_ema20:
                ema20_above += 1
                ema20_weight_above += weight
        if raw.above_ema50 is not None:
            ema50_eligible += 1
            ema50_weight_eligible += weight
            if raw.above_ema50:
                ema50_above += 1
                ema50_weight_above += weight

    adv_count = len(advancing)
    dec_count = len(declining)
    unc_count = len(unchanged)
    eligible = adv_count + dec_count + unc_count

    if dec_count == 0:
        ad_ratio = None
    else:
        ad_ratio = adv_count / dec_count

    weighted_adv = sum(w for _, w in advancing)
    weighted_dec = sum(w for _, w in declining)
    weighted_side_total = weighted_adv + weighted_dec

    weighted_adv_pct = (
        100.0 * weighted_adv / weighted_side_total
        if weighted_side_total > 0
        else None
    )
    weighted_dec_pct = (
        100.0 * weighted_dec / weighted_side_total
        if weighted_side_total > 0
        else None
    )

    coverage_ratio = (
        eligible / universe.expected_constituent_count
        if universe.expected_constituent_count > 0
        else 0.0
    )

    if eligible == 0:
        evidence_status = "UNAVAILABLE"
    elif coverage_ratio < policy.min_coverage_ratio:
        evidence_status = "PARTIAL"
    elif missing or stale or universe.is_partial:
        evidence_status = "READY_WITH_WARNINGS"
    else:
        evidence_status = "READY"

    warnings: list[str] = list(universe.warnings)
    if missing:
        warnings.append(
            f"{missing} constituent(s) had no observation"
        )
    if stale:
        warnings.append(
            f"{stale} constituent(s) were stale"
        )
    if coverage_ratio < policy.min_coverage_ratio:
        warnings.append(
            "coverage below policy minimum"
        )
    if universe.is_partial:
        warnings.append(
            f"universe is partial: {universe.missing_reason}"
        )

    return WeightedBreadthResultV1(
        universe_id=universe.universe_id,
        universe_version=universe.universe_version,
        universe_sha256=universe.universe_sha256,
        index_symbol=universe.index_symbol,
        index_exchange=universe.index_exchange,
        calculated_at=calculated,
        policy=policy,
        advancing_count=adv_count,
        declining_count=dec_count,
        unchanged_count=unc_count,
        missing_count=missing,
        stale_count=stale,
        eligible_count=eligible,
        advance_decline_ratio=ad_ratio,
        advance_decline_difference=adv_count - dec_count,
        weighted_advancing_exposure=weighted_adv,
        weighted_declining_exposure=weighted_dec,
        weighted_advancing_pct=weighted_adv_pct,
        weighted_declining_pct=weighted_dec_pct,
        above_vwap_count=vwap_above,
        above_vwap_eligible_count=vwap_eligible,
        above_vwap_pct=_pct(vwap_above, vwap_eligible),
        weighted_above_vwap_pct=(
            100.0 * vwap_weight_above / vwap_weight_eligible
            if vwap_weight_eligible > 0
            else None
        ),
        above_ema20_count=ema20_above,
        above_ema20_eligible_count=ema20_eligible,
        above_ema20_pct=_pct(ema20_above, ema20_eligible),
        weighted_above_ema20_pct=(
            100.0 * ema20_weight_above / ema20_weight_eligible
            if ema20_weight_eligible > 0
            else None
        ),
        above_ema50_count=ema50_above,
        above_ema50_eligible_count=ema50_eligible,
        above_ema50_pct=_pct(ema50_above, ema50_eligible),
        weighted_above_ema50_pct=(
            100.0 * ema50_weight_above / ema50_weight_eligible
            if ema50_weight_eligible > 0
            else None
        ),
        coverage_ratio=coverage_ratio,
        is_partial=(
            universe.is_partial or bool(missing) or bool(stale)
        ),
        evidence_status=evidence_status,
        warnings=tuple(warnings),
    )


def to_market_breadth_snapshot_v1(
    *,
    result: WeightedBreadthResultV1,
    snapshot_id: str,
    source_id: str = "X2_WEIGHTED_BREADTH",
) -> MarketBreadthSnapshotV1:
    """Handoff to the existing ``evaluate_market_breadth`` classifier.

    Produces a ``MarketBreadthSnapshotV1`` carrying the counts and the
    coverage that X2 computed. The heavyweight contribution state is
    left as ``UNAVAILABLE`` because X2 does not compute it here.
    """
    if not isinstance(result, WeightedBreadthResultV1):
        raise X2ConstituentError(
            "result must be WeightedBreadthResultV1."
        )
    eligible = result.eligible_count
    observed = eligible
    return MarketBreadthSnapshotV1(
        market_breadth_snapshot_id=snapshot_id,
        created_at=result.calculated_at,
        underlying_symbol=result.index_symbol,
        exchange=result.index_exchange,
        source_id=source_id,
        source_timestamp=result.calculated_at,
        advance_count=result.advancing_count,
        decline_count=result.declining_count,
        unchanged_count=result.unchanged_count,
        total_count=eligible,
        covered_count=observed,
        heavyweight_contribution_state="UNAVAILABLE",
        is_partial=result.is_partial,
        warnings=tuple(result.warnings),
        metadata={
            "x2_universe_id": result.universe_id,
            "x2_universe_version": result.universe_version,
            "x2_universe_sha256": result.universe_sha256,
            "x2_result_sha256": result.result_sha256,
            "x2_evidence_status": result.evidence_status,
        },
    )


__all__ = [
    "DEFAULT_BREADTH_POLICY_V1",
    "DEFAULT_STALE_AFTER_SECONDS",
    "WEIGHTED_BREADTH_SCHEMA_V1",
    "BreadthPolicyV1",
    "ConstituentBreadthInputV1",
    "WeightedBreadthResultV1",
    "compute_weighted_breadth_v1",
    "to_market_breadth_snapshot_v1",
]
