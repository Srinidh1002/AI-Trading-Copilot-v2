"""Fixed X5 options research feature registry; descriptive, never voting/trading."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from services.x5.analytics_v1 import _GROUPS, _UNITS
from services.x5.chain_validation_v1 import METRICS
from services.x5.contracts_v1 import canonical_sha256

# Explicit identities prevent a new or renamed B2 metric from being silently
# incorporated as an independently weighted option-chain signal.
_FEATURES: tuple[tuple[str, str, str, str], ...] = (
    ("PCR_OI", "OPTION_POSITIONING", "OPTION_OI_POSITIONING", "RATIO"),
    ("PCR_VOLUME", "OPTION_VOLUME", "OPTION_FLOW_VOLUME", "RATIO"),
    ("MAX_PAIN", "OPTION_POSITIONING", "OPTION_OI_POSITIONING", "UNDERLYING_PRICE_UNIT"),
    ("OI_CONCENTRATION", "OPTION_POSITIONING", "OPTION_OI_POSITIONING", "RATIO"),
    ("OI_BUILDUP", "OPTION_POSITIONING", "OPTION_OI_POSITIONING", "RATIO"),
    ("OI_SUPPORT_RESISTANCE", "OPTION_POSITIONING", "OPTION_OI_POSITIONING", "BPS"),
    ("IV_SKEW", "OPTION_VOLATILITY", "OPTION_VOLATILITY", "PERCENTAGE_POINTS"),
    ("QUOTE_SPREAD", "OPTION_LIQUIDITY", "OPTION_QUOTE_LIQUIDITY", "BPS"),
    ("GREEKS", "OPTION_SENSITIVITY", "OPTION_GREEKS_SHAPE", "MEAN_ABS_DELTA"),
)


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value) and value.strip() == value


@dataclass(frozen=True, slots=True)
class X5FeatureSpecV1:
    metric_name: str
    family: str
    dependency_group: str
    unit: str
    scope: str = "CAPTURED_STRIKE_WINDOW"
    independent_vote: bool = False
    data_only: bool = True
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False
    schema_version: str = "X5_FEATURE_SPEC_V1"

    def __post_init__(self) -> None:
        if not all(
            _text(x) for x in (self.metric_name, self.family, self.dependency_group, self.unit)
        ):
            raise ValueError("Feature identity, group and unit are required")
        if (self.metric_name, self.family, self.dependency_group, self.unit) not in _FEATURES:
            raise ValueError("Unknown or reclassified X5 feature")
        if self.scope != "CAPTURED_STRIKE_WINDOW" or self.schema_version != "X5_FEATURE_SPEC_V1":
            raise ValueError("Feature scope and version are fixed")
        if (
            self.independent_vote is not False
            or self.data_only is not True
            or any(
                (
                    self.execution_authority,
                    self.risk_authority,
                    self.position_authority,
                    self.certification_authority,
                    self.live_execution_eligible,
                )
            )
        ):
            raise ValueError("X5 feature cannot acquire voting or trading authority")


@dataclass(frozen=True, slots=True)
class X5FeatureManifestV1:
    features: tuple[X5FeatureSpecV1, ...]
    source_analytics_schema: str = "X5_ANALYTICS_RESULT_V1"
    scope: str = "CAPTURED_STRIKE_WINDOW"
    independent_vote: bool = False
    data_only: bool = True
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False
    schema_version: str = "X5_FEATURE_MANIFEST_V1"

    def __post_init__(self) -> None:
        if (
            type(self.features) is not tuple
            or tuple(
                (x.metric_name, x.family, x.dependency_group, x.unit)
                for x in self.features
                if isinstance(x, X5FeatureSpecV1)
            )
            != _FEATURES
            or len(self.features) != len(_FEATURES)
        ):
            raise ValueError("Manifest must contain the exact nine canonical features")
        if self.source_analytics_schema != "X5_ANALYTICS_RESULT_V1":
            raise ValueError("Manifest has the wrong analytics source")
        if (
            self.scope != "CAPTURED_STRIKE_WINDOW"
            or self.schema_version != "X5_FEATURE_MANIFEST_V1"
        ):
            raise ValueError("Manifest scope or version changed")
        if (
            self.independent_vote is not False
            or self.data_only is not True
            or any(
                (
                    self.execution_authority,
                    self.risk_authority,
                    self.position_authority,
                    self.certification_authority,
                    self.live_execution_eligible,
                )
            )
        ):
            raise ValueError("Manifest cannot acquire trading or voting authority")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def sha256(self) -> str:
        return canonical_sha256(self.to_dict())


def build_x5_feature_manifest_v1() -> X5FeatureManifestV1:
    """Validate the B2 interface and return the immutable fixed registry."""
    if tuple(x[0] for x in _FEATURES) != METRICS or any(
        _GROUPS[name] != group or _UNITS[name] != unit for name, _, group, unit in _FEATURES
    ):
        raise ValueError("X5 B2 metric identity, unit or dependency group drift")
    return X5FeatureManifestV1(tuple(X5FeatureSpecV1(*item) for item in _FEATURES))
