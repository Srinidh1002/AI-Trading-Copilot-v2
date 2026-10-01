"""Provisional X2 feature manifest.

This manifest is **not** registered in the frozen ``AnalyzerRegistryV1``.
Formal V2 registration belongs to X9. It exists so that downstream
consumers (future X9 snapshot, X10 Shadow Brain V2) can reason about
which X2 features exist, what family they belong to, and whether they
share a source with other features.

Discipline:

* No authority fields. Every feature carries the data-only invariants
  used throughout X1 and X2.
* Explicit ``source_family`` and ``dependency_ids`` so that features
  computed from the same underlying observations are visible as a
  group. Downstream reducers must not treat them as independent market
  votes.
* No numeric weights, confidence percentages or profitability-derived
  thresholds.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256

X2_FEATURE_MANIFEST_SCHEMA_V1 = "X2_FEATURE_MANIFEST_V1"

SUPPORTED_MARKETS_V1 = frozenset({"NIFTY", "SENSEX"})
NOT_APPLICABLE_MARKETS_V1 = frozenset(
    {"CRUDEOILM", "GOLDM", "NATGASMINI"}
)

FAMILIES_V1 = frozenset(
    {
        "CONSTITUENT_INFLUENCE",
        "WEIGHTED_BREADTH",
        "HEATMAP",
        "SECTOR_STRENGTH",
        "RELATIVE_STRENGTH",
    }
)

SOURCE_FAMILIES_V1 = frozenset(
    {
        "X2_CONSTITUENT_RETURNS",
        "X2_CONSTITUENT_WEIGHTS",
        "X2_SECTOR_MAPPING",
        "X2_INDEX_RETURNS",
    }
)


class X2FeatureManifestError(ValueError):
    """Feature manifest contract failed closed."""


def _text(name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or value != value.strip()
    ):
        raise X2FeatureManifestError(
            f"{name} must be a non-empty trimmed string."
        )
    return value


def _text_tuple(name: str, values: object) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise X2FeatureManifestError(f"{name} must be a tuple.")
    out = tuple(_text(f"{name} item", v) for v in values)
    if len(set(out)) != len(out):
        raise X2FeatureManifestError(
            f"{name} must not contain duplicates."
        )
    return out


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


@dataclass(frozen=True, slots=True)
class X2FeatureDescriptorV1:
    feature_id: str
    feature_version: str
    family: str
    subject: str
    markets: tuple[str, ...]
    source_families: tuple[str, ...]
    dependency_ids: tuple[str, ...]
    output_contract: str
    notes: tuple[str, ...] = ()

    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    data_only: bool = True
    order_capability_allowed: bool = False
    automatic_fallback_allowed: bool = False

    schema_version: str = "X2_FEATURE_DESCRIPTOR_V1"

    def __post_init__(self) -> None:
        _text("feature_id", self.feature_id)
        _text("feature_version", self.feature_version)
        _text("subject", self.subject)
        _text("output_contract", self.output_contract)

        if self.family not in FAMILIES_V1:
            raise X2FeatureManifestError(
                f"unsupported family: {self.family!r}"
            )
        markets = _text_tuple("markets", self.markets)
        unsupported = set(markets) - SUPPORTED_MARKETS_V1
        if unsupported:
            raise X2FeatureManifestError(
                f"unsupported markets: {sorted(unsupported)}"
            )
        source_families = _text_tuple(
            "source_families", self.source_families
        )
        unknown_sources = set(source_families) - SOURCE_FAMILIES_V1
        if unknown_sources:
            raise X2FeatureManifestError(
                f"unsupported source families: {sorted(unknown_sources)}"
            )
        _text_tuple("dependency_ids", self.dependency_ids)
        _text_tuple("notes", self.notes)

        for name in (
            "execution_authority",
            "risk_authority",
            "position_authority",
            "certification_authority",
            "order_capability_allowed",
            "automatic_fallback_allowed",
        ):
            if getattr(self, name) is not False:
                raise X2FeatureManifestError(
                    f"{name} is permanently False."
                )
        if self.data_only is not True:
            raise X2FeatureManifestError(
                "data_only is permanently True."
            )
        if self.schema_version != "X2_FEATURE_DESCRIPTOR_V1":
            raise X2FeatureManifestError(
                "unsupported feature descriptor schema."
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "feature_id": self.feature_id,
            "feature_version": self.feature_version,
            "family": self.family,
            "subject": self.subject,
            "markets": list(self.markets),
            "source_families": list(self.source_families),
            "dependency_ids": list(self.dependency_ids),
            "output_contract": self.output_contract,
            "notes": list(self.notes),
            "execution_authority": False,
            "risk_authority": False,
            "position_authority": False,
            "certification_authority": False,
            "data_only": True,
            "order_capability_allowed": False,
            "automatic_fallback_allowed": False,
        }


@dataclass(frozen=True, slots=True)
class X2FeatureManifestV1:
    descriptors: tuple[X2FeatureDescriptorV1, ...]
    schema_version: str = X2_FEATURE_MANIFEST_SCHEMA_V1

    def __post_init__(self) -> None:
        if not isinstance(self.descriptors, tuple):
            raise X2FeatureManifestError(
                "descriptors must be a tuple."
            )
        if not self.descriptors:
            raise X2FeatureManifestError(
                "manifest must contain at least one descriptor."
            )
        seen: set[str] = set()
        for d in self.descriptors:
            if not isinstance(d, X2FeatureDescriptorV1):
                raise X2FeatureManifestError(
                    "descriptors must be X2FeatureDescriptorV1."
                )
            if d.feature_id in seen:
                raise X2FeatureManifestError(
                    f"duplicate feature_id: {d.feature_id}"
                )
            seen.add(d.feature_id)
        if self.schema_version != X2_FEATURE_MANIFEST_SCHEMA_V1:
            raise X2FeatureManifestError(
                "unsupported feature manifest schema."
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "descriptors": [
                d.to_dict() for d in self.descriptors
            ],
        }

    def canonical_json(self) -> str:
        return _canonical_json(self.to_dict())

    @property
    def manifest_sha256(self) -> str:
        return sha256(
            self.canonical_json().encode("utf-8")
        ).hexdigest()

    def by_family(self, family: str) -> tuple[X2FeatureDescriptorV1, ...]:
        if family not in FAMILIES_V1:
            raise X2FeatureManifestError(
                f"unsupported family: {family!r}"
            )
        return tuple(
            d for d in self.descriptors if d.family == family
        )

    def dependency_groups(self) -> dict[str, tuple[str, ...]]:
        """Group feature ids by their primary source families.

        Downstream consumers can use this to detect features that share
        the same underlying observations and must not be double-counted.
        """
        groups: dict[str, list[str]] = {}
        for d in self.descriptors:
            key = "|".join(sorted(d.source_families))
            groups.setdefault(key, []).append(d.feature_id)
        return {
            k: tuple(sorted(v)) for k, v in groups.items()
        }


DEFAULT_X2_FEATURE_MANIFEST_V1 = X2FeatureManifestV1(
    descriptors=(
        X2FeatureDescriptorV1(
            feature_id="x2.constituent_influence.v1",
            feature_version="1.0",
            family="CONSTITUENT_INFLUENCE",
            subject="CONSTITUENT",
            markets=("NIFTY", "SENSEX"),
            source_families=(
                "X2_CONSTITUENT_RETURNS",
                "X2_CONSTITUENT_WEIGHTS",
            ),
            dependency_ids=(),
            output_contract="ConstituentInfluenceResultV1",
            notes=(
                "Reports weighted-return contribution only.",
                "Does not claim exact index-point attribution.",
            ),
        ),
        X2FeatureDescriptorV1(
            feature_id="x2.weighted_breadth.v1",
            feature_version="1.0",
            family="WEIGHTED_BREADTH",
            subject="INDEX",
            markets=("NIFTY", "SENSEX"),
            source_families=(
                "X2_CONSTITUENT_RETURNS",
                "X2_CONSTITUENT_WEIGHTS",
            ),
            dependency_ids=("x2.constituent_influence.v1",),
            output_contract="WeightedBreadthResultV1",
            notes=(
                "Shares underlying returns with constituent influence.",
                "Downstream must not treat as an independent market vote.",
                "Snapshot handoff goes through MarketBreadthSnapshotV1.",
            ),
        ),
        X2FeatureDescriptorV1(
            feature_id="x2.heatmap.v1",
            feature_version="1.0",
            family="HEATMAP",
            subject="INDEX",
            markets=("NIFTY", "SENSEX"),
            source_families=(
                "X2_CONSTITUENT_RETURNS",
                "X2_CONSTITUENT_WEIGHTS",
            ),
            dependency_ids=("x2.constituent_influence.v1",),
            output_contract="HeatmapResultV1",
            notes=(
                "Derived from the same returns as constituent influence.",
                "Not an independent directional vote.",
                "Contains no institutional-activity claim.",
            ),
        ),
        X2FeatureDescriptorV1(
            feature_id="x2.sector_strength.v1",
            feature_version="1.0",
            family="SECTOR_STRENGTH",
            subject="SECTOR",
            markets=("NIFTY", "SENSEX"),
            source_families=(
                "X2_CONSTITUENT_RETURNS",
                "X2_CONSTITUENT_WEIGHTS",
                "X2_SECTOR_MAPPING",
            ),
            dependency_ids=("x2.constituent_influence.v1",),
            output_contract="SectorStrengthResultV1",
            notes=(
                "Rotation requires a previous snapshot.",
                "Reports INSUFFICIENT_HISTORY without one.",
            ),
        ),
        X2FeatureDescriptorV1(
            feature_id="x2.relative_strength.v1",
            feature_version="1.0",
            family="RELATIVE_STRENGTH",
            subject="PAIR",
            markets=("NIFTY", "SENSEX"),
            source_families=(
                "X2_CONSTITUENT_RETURNS",
                "X2_INDEX_RETURNS",
            ),
            dependency_ids=(),
            output_contract="RelativeStrengthResultV1",
            notes=(
                "Pairs must be aligned in timestamp and horizon.",
                "Relative outperformance is not an absolute signal.",
            ),
        ),
    )
)


__all__ = [
    "DEFAULT_X2_FEATURE_MANIFEST_V1",
    "FAMILIES_V1",
    "NOT_APPLICABLE_MARKETS_V1",
    "SOURCE_FAMILIES_V1",
    "SUPPORTED_MARKETS_V1",
    "X2_FEATURE_MANIFEST_SCHEMA_V1",
    "X2FeatureDescriptorV1",
    "X2FeatureManifestError",
    "X2FeatureManifestV1",
]
