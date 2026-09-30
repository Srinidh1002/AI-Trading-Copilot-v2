"""Zero-authority evidence contracts for the future Brain.

These contracts standardize analyzer evidence only.  They deliberately contain
no trade action, order, position, broker-submission, or risk-override authority.

B2 invariant:
    current production policy remains authoritative.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
from typing import TypeAlias


EvidenceScalar: TypeAlias = str | int | float | bool | None


EVIDENCE_STATUSES = frozenset(
    {
        "AVAILABLE",
        "DEGRADED",
        "UNAVAILABLE",
        "UNVERIFIED",
    }
)

FRESHNESS_STATUSES = frozenset(
    {
        "FRESH",
        "STALE",
        "UNKNOWN",
        "NOT_APPLICABLE",
    }
)

EVIDENCE_DIRECTIONS = frozenset(
    {
        "BULLISH",
        "BEARISH",
        "NEUTRAL",
        "MIXED",
        "UNKNOWN",
    }
)

ANALYZER_STATUSES = frozenset(
    {
        "OK",
        "PARTIAL",
        "UNAVAILABLE",
        "ERROR",
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


def _validate_probability(
    name: str,
    value: object,
) -> None:
    if value is None:
        return

    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or not 0.0 <= float(value) <= 1.0
    ):
        raise ValueError(
            f"{name} must be finite and within [0, 1]."
        )


def _validate_scalar(
    name: str,
    value: EvidenceScalar,
) -> None:
    if value is None:
        return

    if isinstance(
        value,
        (
            str,
            bool,
            int,
        ),
    ):
        return

    if (
        isinstance(value, float)
        and math.isfinite(value)
    ):
        return

    raise ValueError(
        f"{name} must be a JSON-safe scalar."
    )


def _validate_string_tuple(
    name: str,
    values: object,
) -> None:
    if not isinstance(values, tuple):
        raise ValueError(
            f"{name} must be a tuple."
        )

    if any(
        not isinstance(value, str)
        or not value.strip()
        or value != value.strip()
        for value in values
    ):
        raise ValueError(
            f"{name} entries must be non-empty trimmed strings."
        )


def _validate_metadata(
    metadata: object,
) -> None:
    if not isinstance(metadata, tuple):
        raise ValueError(
            "metadata must be a tuple of (key, scalar) pairs."
        )

    keys: set[str] = set()

    for item in metadata:
        if (
            not isinstance(item, tuple)
            or len(item) != 2
        ):
            raise ValueError(
                "metadata entries must be two-item tuples."
            )

        key, value = item

        _require_text(
            "metadata key",
            key,
        )

        if key in keys:
            raise ValueError(
                f"duplicate metadata key: {key}"
            )

        keys.add(key)

        _validate_scalar(
            f"metadata[{key}]",
            value,
        )


@dataclass(
    frozen=True,
    slots=True,
)
class EvidenceV1:
    """One normalized piece of analyzer evidence.

    ``EvidenceV1`` describes observations.  It is intentionally incapable of
    authorizing execution.
    """

    evidence_id: str
    market: str
    analyzer: str
    analyzer_version: str
    category: str
    feature: str

    observed_at: datetime
    generated_at: datetime

    status: str
    freshness: str
    source: str

    value: EvidenceScalar = None
    unit: str | None = None

    direction: str = "UNKNOWN"

    strength: float | None = None
    confidence: float | None = None
    quality_score: float | None = None

    source_authoritative: bool = False
    missing_reason: str | None = None

    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    metadata: tuple[
        tuple[
            str,
            EvidenceScalar,
        ],
        ...,
    ] = ()

    schema_version: str = "BRAIN_EVIDENCE_V1"

    def __post_init__(
        self,
    ) -> None:
        for name in (
            "evidence_id",
            "market",
            "analyzer",
            "analyzer_version",
            "category",
            "feature",
            "source",
            "schema_version",
        ):
            _require_text(
                name,
                getattr(
                    self,
                    name,
                ),
            )

        _require_aware_datetime(
            "observed_at",
            self.observed_at,
        )

        _require_aware_datetime(
            "generated_at",
            self.generated_at,
        )

        if self.status not in EVIDENCE_STATUSES:
            raise ValueError(
                f"unsupported evidence status: {self.status}"
            )

        if self.freshness not in FRESHNESS_STATUSES:
            raise ValueError(
                f"unsupported freshness status: {self.freshness}"
            )

        if self.direction not in EVIDENCE_DIRECTIONS:
            raise ValueError(
                f"unsupported evidence direction: {self.direction}"
            )

        _validate_scalar(
            "value",
            self.value,
        )

        if self.unit is not None:
            _require_text(
                "unit",
                self.unit,
            )

        for name in (
            "strength",
            "confidence",
            "quality_score",
        ):
            _validate_probability(
                name,
                getattr(
                    self,
                    name,
                ),
            )

        if not isinstance(
            self.source_authoritative,
            bool,
        ):
            raise ValueError(
                "source_authoritative must be bool."
            )

        if self.missing_reason is not None:
            _require_text(
                "missing_reason",
                self.missing_reason,
            )

        if (
            self.status == "UNAVAILABLE"
            and self.missing_reason is None
        ):
            raise ValueError(
                "UNAVAILABLE evidence requires missing_reason."
            )

        _validate_string_tuple(
            "blockers",
            self.blockers,
        )

        _validate_string_tuple(
            "warnings",
            self.warnings,
        )

        _validate_metadata(
            self.metadata,
        )

    def to_dict(
        self,
    ) -> dict[str, object]:
        return {
            "schema_version":
                self.schema_version,

            "evidence_id":
                self.evidence_id,

            "market":
                self.market,

            "analyzer":
                self.analyzer,

            "analyzer_version":
                self.analyzer_version,

            "category":
                self.category,

            "feature":
                self.feature,

            "observed_at":
                self.observed_at.isoformat(),

            "generated_at":
                self.generated_at.isoformat(),

            "status":
                self.status,

            "freshness":
                self.freshness,

            "source":
                self.source,

            "value":
                self.value,

            "unit":
                self.unit,

            "direction":
                self.direction,

            "strength":
                self.strength,

            "confidence":
                self.confidence,

            "quality_score":
                self.quality_score,

            "source_authoritative":
                self.source_authoritative,

            "missing_reason":
                self.missing_reason,

            "blockers":
                list(
                    self.blockers
                ),

            "warnings":
                list(
                    self.warnings
                ),

            "metadata":
                dict(
                    self.metadata
                ),
        }


@dataclass(
    frozen=True,
    slots=True,
)
class AnalyzerResultV1:
    """Normalized output from one analyzer.

    Analyzer results are observational.  ``execution_authority`` is locked
    false in V1 so merely wiring an analyzer cannot change PAPER decisions.
    """

    result_id: str
    market: str

    analyzer: str
    analyzer_version: str

    generated_at: datetime

    status: str

    evidence: tuple[
        EvidenceV1,
        ...,
    ]

    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    execution_authority: bool = False

    schema_version: str = "BRAIN_ANALYZER_RESULT_V1"

    def __post_init__(
        self,
    ) -> None:
        for name in (
            "result_id",
            "market",
            "analyzer",
            "analyzer_version",
            "schema_version",
        ):
            _require_text(
                name,
                getattr(
                    self,
                    name,
                ),
            )

        _require_aware_datetime(
            "generated_at",
            self.generated_at,
        )

        if self.status not in ANALYZER_STATUSES:
            raise ValueError(
                f"unsupported analyzer status: {self.status}"
            )

        if not isinstance(
            self.evidence,
            tuple,
        ):
            raise ValueError(
                "evidence must be a tuple."
            )

        if (
            self.status
            in {
                "OK",
                "PARTIAL",
            }
            and not self.evidence
        ):
            raise ValueError(
                f"{self.status} analyzer result requires evidence."
            )

        ids: set[str] = set()

        for item in self.evidence:
            if not isinstance(
                item,
                EvidenceV1,
            ):
                raise ValueError(
                    "evidence entries must be EvidenceV1."
                )

            if item.market != self.market:
                raise ValueError(
                    "evidence market must match analyzer result market."
                )

            if item.analyzer != self.analyzer:
                raise ValueError(
                    "evidence analyzer must match analyzer result analyzer."
                )

            if (
                item.analyzer_version
                != self.analyzer_version
            ):
                raise ValueError(
                    "evidence analyzer version must match analyzer result."
                )

            if item.evidence_id in ids:
                raise ValueError(
                    f"duplicate evidence_id: {item.evidence_id}"
                )

            ids.add(
                item.evidence_id
            )

        _validate_string_tuple(
            "blockers",
            self.blockers,
        )

        _validate_string_tuple(
            "warnings",
            self.warnings,
        )

        if self.execution_authority is not False:
            raise ValueError(
                "AnalyzerResultV1 execution_authority is permanently False."
            )

    def to_dict(
        self,
    ) -> dict[str, object]:
        return {
            "schema_version":
                self.schema_version,

            "result_id":
                self.result_id,

            "market":
                self.market,

            "analyzer":
                self.analyzer,

            "analyzer_version":
                self.analyzer_version,

            "generated_at":
                self.generated_at.isoformat(),

            "status":
                self.status,

            "evidence":
                [
                    item.to_dict()
                    for item in self.evidence
                ],

            "blockers":
                list(
                    self.blockers
                ),

            "warnings":
                list(
                    self.warnings
                ),

            "execution_authority":
                False,
        }


__all__ = [
    "ANALYZER_STATUSES",
    "EVIDENCE_DIRECTIONS",
    "EVIDENCE_STATUSES",
    "FRESHNESS_STATUSES",
    "AnalyzerResultV1",
    "EvidenceScalar",
    "EvidenceV1",
]