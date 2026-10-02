"""Frozen X4 research manifest. X9 owns V2 registry registration.

Related measurements share dependency families; a feature is never an
independent vote, execution instruction, risk limit or certification record.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from services.x4.contracts_v1 import canonical_sha256


@dataclass(frozen=True, slots=True)
class X4FeatureSpecV1:
    feature_id: str
    family: str
    dependency_group: str
    unit_rule: str
    minimum_bars: int
    interpretation: str = "DESCRIPTIVE_RESEARCH_ONLY"
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False
    schema_version: str = "X4_FEATURE_SPEC_V1"

    def __post_init__(self) -> None:
        if (
            not self.feature_id.startswith("FUTURES_")
            or self.family not in {"FUTURES_POSITIONING", "FUTURES_PARTICIPATION", "FUTURES_BASIS"}
            or self.dependency_group not in {"PRICE_OI", "VOLUME_DERIVED", "BASIS_REFERENCE"}
            or not self.unit_rule
            or type(self.minimum_bars) is not int
            or self.minimum_bars < 1
            or self.interpretation != "DESCRIPTIVE_RESEARCH_ONLY"
            or self.independent_vote is not False
            or any(
                (
                    self.execution_authority,
                    self.risk_authority,
                    self.position_authority,
                    self.certification_authority,
                    self.live_execution_eligible,
                )
            )
            or self.schema_version != "X4_FEATURE_SPEC_V1"
        ):
            raise ValueError("Invalid or authority-bearing X4 feature specification")


X4_FEATURE_MANIFEST_V1: tuple[X4FeatureSpecV1, ...] = (
    X4FeatureSpecV1("FUTURES_PRICE_CHANGE_PCT", "FUTURES_POSITIONING", "PRICE_OI", "PERCENT", 2),
    X4FeatureSpecV1(
        "FUTURES_OI_DELTA", "FUTURES_POSITIONING", "PRICE_OI", "OI_PROVIDER_REPORTED_UNIT", 2
    ),
    X4FeatureSpecV1("FUTURES_OI_CHANGE_PCT", "FUTURES_POSITIONING", "PRICE_OI", "PERCENT", 2),
    X4FeatureSpecV1(
        "FUTURES_OI_ACCELERATION",
        "FUTURES_POSITIONING",
        "PRICE_OI",
        "OI_PROVIDER_UNIT_PER_HOUR_SQUARED",
        3,
    ),
    X4FeatureSpecV1(
        "FUTURES_VOLUME_CHANGE_PCT", "FUTURES_PARTICIPATION", "VOLUME_DERIVED", "PERCENT", 2
    ),
    X4FeatureSpecV1(
        "FUTURES_CANDLE_VWAP_ESTIMATE",
        "FUTURES_PARTICIPATION",
        "VOLUME_DERIVED",
        "CONTRACT_PRICE_UNIT",
        1,
    ),
    X4FeatureSpecV1(
        "FUTURES_VWAP_ESTIMATE_DISTANCE_PCT",
        "FUTURES_PARTICIPATION",
        "VOLUME_DERIVED",
        "PERCENT",
        1,
    ),
    X4FeatureSpecV1("FUTURES_BASIS", "FUTURES_BASIS", "BASIS_REFERENCE", "CONTRACT_PRICE_UNIT", 1),
)

X4_FEATURE_IDS_V1 = tuple(spec.feature_id for spec in X4_FEATURE_MANIFEST_V1)

if len(set(X4_FEATURE_IDS_V1)) != len(X4_FEATURE_IDS_V1):
    raise RuntimeError("Duplicated X4 feature ID")

_SPECS = {spec.feature_id: spec for spec in X4_FEATURE_MANIFEST_V1}


def get_x4_feature_spec_v1(feature_id: str) -> X4FeatureSpecV1:
    """Fail closed on unknown or accidentally introduced feature identifiers."""
    if type(feature_id) is not str or feature_id not in _SPECS:
        raise ValueError(f"Unregistered X4 research feature: {feature_id!r}")
    return _SPECS[feature_id]


def x4_manifest_sha256_v1() -> str:
    return canonical_sha256([asdict(spec) for spec in X4_FEATURE_MANIFEST_V1])
