"""Immutable zero-authority Shadow Brain output contracts.

This module defines analysis-only output structures.

It contains no market-data access, scoring engine, trading action,
broker, execution, risk, position-management, or certification logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
from math import isfinite

from services.brain.analyzer_registry_v1 import (
    SUPPORTED_MARKETS,
)


SHADOW_HYPOTHESIS_SCHEMA_V1 = (
    "BRAIN_SHADOW_HYPOTHESIS_V1"
)

SHADOW_BRAIN_RESULT_SCHEMA_V1 = (
    "BRAIN_SHADOW_RESULT_V1"
)

SHADOW_HYPOTHESES = frozenset(
    {
        "BULLISH",
        "BEARISH",
        "NEUTRAL",
        "INSUFFICIENT_EVIDENCE",
    }
)


def _require_text(
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or value != value.strip()
    ):
        raise ValueError(
            f"{name} must be a non-empty trimmed string."
        )

    return value


def _require_aware_datetime(
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


def _require_sha256(
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value != value.lower()
    ):
        raise ValueError(
            f"{name} must be 64 lowercase hex characters."
        )

    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(
            f"{name} must be hexadecimal."
        ) from exc

    return value


def _require_fraction(
    name: str,
    value: object,
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(float(value))
        or float(value) < 0.0
        or float(value) > 1.0
    ):
        raise ValueError(
            f"{name} must be finite and between 0.0 and 1.0."
        )

    return float(value)


def _require_percentage(
    name: str,
    value: object,
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(float(value))
        or float(value) < 0.0
        or float(value) > 100.0
    ):
        raise ValueError(
            f"{name} must be finite and between 0.0 and 100.0."
        )

    return float(value)


def _require_sorted_unique_text_tuple(
    name: str,
    value: object,
) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise TypeError(
            f"{name} must be a tuple."
        )

    for item in value:
        _require_text(
            f"{name} item",
            item,
        )

    if len(set(value)) != len(value):
        raise ValueError(
            f"{name} must not contain duplicates."
        )

    if value != tuple(sorted(value)):
        raise ValueError(
            f"{name} must be sorted."
        )

    return value


def _canonical_json(
    payload: dict[str, object],
) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


@dataclass(
    frozen=True,
    slots=True,
)
class ShadowHypothesisV1:
    """Non-authoritative market hypothesis derived from snapshot evidence."""

    market: str
    hypothesis: str
    confidence: float

    supporting_evidence_ids: tuple[str, ...]
    opposing_evidence_ids: tuple[str, ...]
    unknown_evidence_ids: tuple[str, ...]
    rationale_codes: tuple[str, ...]

    schema_version: str = (
        SHADOW_HYPOTHESIS_SCHEMA_V1
    )

    def __post_init__(self) -> None:
        if self.market not in SUPPORTED_MARKETS:
            raise ValueError(
                f"unsupported shadow market: {self.market!r}."
            )

        if self.hypothesis not in SHADOW_HYPOTHESES:
            raise ValueError(
                f"unsupported shadow hypothesis: {self.hypothesis!r}."
            )

        _require_fraction(
            "confidence",
            self.confidence,
        )

        for name in (
            "supporting_evidence_ids",
            "opposing_evidence_ids",
            "unknown_evidence_ids",
            "rationale_codes",
        ):
            _require_sorted_unique_text_tuple(
                name,
                getattr(self, name),
            )

        supporting = set(
            self.supporting_evidence_ids
        )

        opposing = set(
            self.opposing_evidence_ids
        )

        unknown = set(
            self.unknown_evidence_ids
        )

        if supporting & opposing:
            raise ValueError(
                "supporting and opposing evidence IDs must be disjoint."
            )

        if supporting & unknown:
            raise ValueError(
                "supporting and unknown evidence IDs must be disjoint."
            )

        if opposing & unknown:
            raise ValueError(
                "opposing and unknown evidence IDs must be disjoint."
            )

        if self.schema_version != SHADOW_HYPOTHESIS_SCHEMA_V1:
            raise ValueError(
                "unsupported ShadowHypothesisV1 schema."
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "market": self.market,
            "hypothesis": self.hypothesis,
            "confidence": float(self.confidence),
            "supporting_evidence_ids": list(
                self.supporting_evidence_ids
            ),
            "opposing_evidence_ids": list(
                self.opposing_evidence_ids
            ),
            "unknown_evidence_ids": list(
                self.unknown_evidence_ids
            ),
            "rationale_codes": list(
                self.rationale_codes
            ),
        }


@dataclass(
    frozen=True,
    slots=True,
)
class ShadowBrainResultV1:
    """Deterministic zero-authority Shadow Brain output envelope."""

    market: str
    snapshot_sha256: str
    snapshot_at: datetime
    generated_at: datetime

    source_strategy_version: str
    source_policy_epoch: str
    source_runtime_ref: str

    production_coverage_pct: float
    production_complete: bool

    missing_production_analyzers: tuple[str, ...]
    unverified_evidence_ids: tuple[str, ...]
    stale_evidence_ids: tuple[str, ...]

    hypothesis: ShadowHypothesisV1

    execution_authority: bool = False
    decision_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False

    schema_version: str = (
        SHADOW_BRAIN_RESULT_SCHEMA_V1
    )

    def __post_init__(self) -> None:
        if self.market not in SUPPORTED_MARKETS:
            raise ValueError(
                f"unsupported shadow market: {self.market!r}."
            )

        _require_sha256(
            "snapshot_sha256",
            self.snapshot_sha256,
        )

        _require_aware_datetime(
            "snapshot_at",
            self.snapshot_at,
        )

        _require_aware_datetime(
            "generated_at",
            self.generated_at,
        )

        if self.generated_at < self.snapshot_at:
            raise ValueError(
                "generated_at must not precede snapshot_at."
            )

        for name in (
            "source_strategy_version",
            "source_policy_epoch",
            "source_runtime_ref",
        ):
            _require_text(
                name,
                getattr(self, name),
            )

        coverage = _require_percentage(
            "production_coverage_pct",
            self.production_coverage_pct,
        )

        if not isinstance(
            self.production_complete,
            bool,
        ):
            raise TypeError(
                "production_complete must be bool."
            )

        for name in (
            "missing_production_analyzers",
            "unverified_evidence_ids",
            "stale_evidence_ids",
        ):
            _require_sorted_unique_text_tuple(
                name,
                getattr(self, name),
            )

        if self.production_complete:
            if coverage != 100.0:
                raise ValueError(
                    "complete production coverage must equal 100.0."
                )

            if self.missing_production_analyzers:
                raise ValueError(
                    "complete production coverage cannot have missing analyzers."
                )

        else:
            if coverage >= 100.0:
                raise ValueError(
                    "incomplete production coverage must be below 100.0."
                )

            if not self.missing_production_analyzers:
                raise ValueError(
                    "incomplete production coverage requires missing analyzers."
                )

        if not isinstance(
            self.hypothesis,
            ShadowHypothesisV1,
        ):
            raise TypeError(
                "hypothesis must be ShadowHypothesisV1."
            )

        if self.hypothesis.market != self.market:
            raise ValueError(
                "hypothesis market must equal result market."
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
                    f"{name} is permanently False in ShadowBrainResultV1."
                )

        if self.schema_version != SHADOW_BRAIN_RESULT_SCHEMA_V1:
            raise ValueError(
                "unsupported ShadowBrainResultV1 schema."
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "market": self.market,
            "snapshot_sha256": self.snapshot_sha256,
            "snapshot_at": self.snapshot_at.isoformat(),
            "generated_at": self.generated_at.isoformat(),
            "source_strategy_version": (
                self.source_strategy_version
            ),
            "source_policy_epoch": (
                self.source_policy_epoch
            ),
            "source_runtime_ref": (
                self.source_runtime_ref
            ),
            "production_coverage_pct": float(
                self.production_coverage_pct
            ),
            "production_complete": self.production_complete,
            "missing_production_analyzers": list(
                self.missing_production_analyzers
            ),
            "unverified_evidence_ids": list(
                self.unverified_evidence_ids
            ),
            "stale_evidence_ids": list(
                self.stale_evidence_ids
            ),
            "hypothesis": self.hypothesis.to_dict(),
            "execution_authority": False,
            "decision_authority": False,
            "risk_authority": False,
            "position_authority": False,
            "certification_authority": False,
        }

    def canonical_payload(self) -> dict[str, object]:
        return self.to_dict()

    def canonical_json(self) -> str:
        return _canonical_json(
            self.canonical_payload()
        )

    @property
    def shadow_result_sha256(self) -> str:
        return sha256(
            self.canonical_json().encode("utf-8")
        ).hexdigest()


__all__ = [
    "SHADOW_HYPOTHESIS_SCHEMA_V1",
    "SHADOW_BRAIN_RESULT_SCHEMA_V1",
    "SHADOW_HYPOTHESES",
    "ShadowHypothesisV1",
    "ShadowBrainResultV1",
]
