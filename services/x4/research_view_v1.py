"""Deterministic X4 zero-authority research projection for future X9/X10.

No registry writes, provider calls, decisions, policy scores, or PAPER mutations.
The source result is authoritative for computed values and quality; this view
cannot recover absent data or elevate correlated features to separate votes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime

from services.x4.contracts_v1 import _aware, _encode, canonical_sha256
from services.x4.feature_manifest_v1 import (
    X4_FEATURE_IDS_V1,
    get_x4_feature_spec_v1,
    x4_manifest_sha256_v1,
)
from services.x4.multi_timeframe_v1 import X4MultiTimeframeResultV1


@dataclass(frozen=True, slots=True)
class X4ResearchFeatureV1:
    feature_id: str
    market: str
    instrument_id: str
    session_id: str
    timeframe: str
    capture_id: str
    as_of: datetime
    family: str
    dependency_group: str
    status: str
    value: float | None
    unit: str
    metric_direction: str
    dependency_ids: tuple[str, ...]
    blockers: tuple[str, ...]
    independent_vote: bool = False
    data_only: bool = True
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False
    schema_version: str = "X4_RESEARCH_FEATURE_V1"

    def __post_init__(self) -> None:
        spec = get_x4_feature_spec_v1(self.feature_id)
        if (
            not all(
                (self.market, self.instrument_id, self.session_id, self.timeframe, self.capture_id)
            )
            or not _aware(self.as_of)
            or self.family != spec.family
            or self.dependency_group != spec.dependency_group
            or self.status not in {"AVAILABLE", "UNAVAILABLE", "NOT_APPLICABLE"}
            or self.metric_direction not in {"UP", "DOWN", "FLAT", "NON_DIRECTIONAL", "UNKNOWN"}
            or self.independent_vote is not False
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
            or self.schema_version != "X4_RESEARCH_FEATURE_V1"
        ):
            raise ValueError("Invalid or authority-bearing X4 research feature")
        # A zero-valued measurement is valid, but absent measurements cannot carry values.
        if (self.status == "AVAILABLE") != (self.value is not None):
            raise ValueError("X4 research value/status mismatch")
        if self.status != "AVAILABLE" and self.metric_direction != "UNKNOWN":
            raise ValueError("Unavailable evidence must not convey a direction")


@dataclass(frozen=True, slots=True)
class X4ResearchViewV1:
    market: str
    instrument_id: str
    provider_symbol: str
    session_id: str
    as_of: datetime
    required_timeframes: tuple[str, ...]
    missing_timeframes: tuple[str, ...]
    alignment: str
    status: str
    features: tuple[X4ResearchFeatureV1, ...]
    dependency_groups: tuple[str, ...]
    blockers: tuple[str, ...]
    source_result_sha256: str
    manifest_sha256: str
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False
    schema_version: str = "X4_RESEARCH_VIEW_V1"

    def __post_init__(self) -> None:
        keys = [(f.timeframe, f.feature_id) for f in self.features]
        if (
            not all((self.market, self.instrument_id, self.provider_symbol, self.session_id))
            or not _aware(self.as_of)
            or len(set(keys)) != len(keys)
            or any(
                f.market != self.market
                or f.instrument_id != self.instrument_id
                or f.session_id != self.session_id
                or f.as_of != self.as_of
                or f.timeframe not in self.required_timeframes
                for f in self.features
            )
            or self.dependency_groups
            != tuple(dict.fromkeys(f.dependency_group for f in self.features))
            or not self.source_result_sha256
            or self.manifest_sha256 != x4_manifest_sha256_v1()
            or self.data_only is not True
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
            or self.schema_version != "X4_RESEARCH_VIEW_V1"
        ):
            raise ValueError("Invalid or authority-bearing X4 research view")

    def to_dict(self) -> dict[str, object]:
        return _encode(asdict(self))

    def sha256(self) -> str:
        return canonical_sha256(self.to_dict())


def build_x4_research_view_v1(result: X4MultiTimeframeResultV1) -> X4ResearchViewV1:
    """Project the already-composed immutable evidence; never recompute it.

    B2 frame order determines presentation, and the source sha256 binds the
    projection to exactly one input result. X9 owns registry installation.
    """
    if not isinstance(result, X4MultiTimeframeResultV1):
        raise TypeError("Expected verified X4 multi-timeframe output")
    if result.data_only is not True or any(
        (
            result.execution_authority,
            result.risk_authority,
            result.position_authority,
            result.certification_authority,
            result.live_execution_eligible,
        )
    ):
        raise ValueError("Authority-bearing result cannot enter the research view")
    projected: list[X4ResearchFeatureV1] = []
    for frame, evidence in zip(result.timeframe_results, result.evidence, strict=True):
        if (
            frame.timeframe != evidence.timeframe
            or frame.market != result.market
            or frame.instrument_id != result.instrument_id
            or frame.session_id != result.session_id
            or frame.as_of != result.as_of
            or evidence.status != frame.status
            or evidence.positioning_state != frame.positioning_state
        ):
            raise ValueError("Frame/evidence identity or state mismatch")
        observed_available = tuple(f.feature_id for f in frame.features if f.status == "AVAILABLE")
        observed_unavailable = tuple(
            f.feature_id for f in frame.features if f.status == "UNAVAILABLE"
        )
        if (
            evidence.available_feature_ids != observed_available
            or evidence.unavailable_feature_ids != observed_unavailable
            or evidence.blockers != frame.blockers
            or not evidence.capture_id
        ):
            raise ValueError("Frame/evidence feature or capture mismatch")
        seen: set[str] = set()
        for feature in frame.features:
            if feature.feature_id in seen:
                raise ValueError("Duplicate X4 feature")
            seen.add(feature.feature_id)
            spec = get_x4_feature_spec_v1(feature.feature_id)
            if feature.unit != spec.unit_rule and spec.unit_rule != "CONTRACT_PRICE_UNIT":
                raise ValueError("X4 feature unit differs from frozen manifest")
            if feature.data_only is not True or any(
                (
                    feature.execution_authority,
                    feature.risk_authority,
                    feature.position_authority,
                    feature.certification_authority,
                    feature.live_execution_eligible,
                )
            ):
                raise ValueError("Authority-bearing feature")
            if feature.dependency_ids[:3] != (
                result.instrument_id,
                result.session_id,
                frame.timeframe,
            ):
                raise ValueError("Missing canonical X4 dependencies")
            if len(set(feature.dependency_ids)) != len(feature.dependency_ids):
                raise ValueError("Repeated X4 dependencies")
            if not any(
                dep.startswith(evidence.capture_id + ":") for dep in feature.dependency_ids[3:]
            ):
                raise ValueError("Capture ID is not bound to source observations")
            projected.append(
                X4ResearchFeatureV1(
                    feature_id=feature.feature_id,
                    market=result.market,
                    instrument_id=result.instrument_id,
                    session_id=result.session_id,
                    timeframe=frame.timeframe,
                    capture_id=evidence.capture_id,
                    as_of=result.as_of,
                    family=spec.family,
                    dependency_group=spec.dependency_group,
                    status=feature.status,
                    value=feature.value,
                    unit=feature.unit,
                    metric_direction=feature.direction,
                    dependency_ids=feature.dependency_ids,
                    blockers=feature.blockers,
                )
            )
        if frame.features and set(seen) != set(X4_FEATURE_IDS_V1):
            raise ValueError("Partial manifest population inside an available frame")
    features = tuple(projected)
    return X4ResearchViewV1(
        market=result.market,
        instrument_id=result.instrument_id,
        provider_symbol=result.provider_symbol,
        session_id=result.session_id,
        as_of=result.as_of,
        required_timeframes=result.required_timeframes,
        missing_timeframes=result.missing_timeframes,
        alignment=result.alignment,
        status=result.status,
        features=features,
        dependency_groups=tuple(dict.fromkeys(f.dependency_group for f in features)),
        blockers=result.blockers,
        source_result_sha256=result.sha256(),
        manifest_sha256=x4_manifest_sha256_v1(),
    )
