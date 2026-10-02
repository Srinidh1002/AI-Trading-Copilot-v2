"""Deterministic X5 captured-window research projection; no score or execution."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from math import isfinite
from string import hexdigits

from services.x5.analytics_v1 import X5AnalyticsResultV1, X5ResearchMetricV1
from services.x5.chain_validation_v1 import METRICS
from services.x5.contracts_v1 import (
    MARKET_EXCHANGES,
    X5ChainCaptureV1,
    X5ChainValidationV1,
    canonical_sha256,
)
from services.x5.feature_manifest_v1 import (
    X5FeatureManifestV1,
    X5FeatureSpecV1,
    build_x5_feature_manifest_v1,
)


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value) and value.strip() == value


def _sha(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(x in hexdigits for x in value)


def _aware(value: object) -> bool:
    return (
        isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
    )


def _strings(items: object) -> bool:
    return type(items) is tuple and all(_text(x) for x in items)


def _finite(value: object) -> bool:
    return type(value) in (int, float) and isfinite(value)


def _dedup(*groups: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(word for group in groups for word in group))


@dataclass(frozen=True, slots=True)
class X5ResearchFeatureV1:
    metric_name: str
    market: str
    expiry: date
    capture_id: str
    as_of: datetime
    family: str
    dependency_group: str
    status: str
    value: float | None
    unit: str
    supporting_strikes: tuple[float, ...]
    detail: tuple[tuple[str, float], ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    source_metric_sha256: str
    scope: str = "CAPTURED_STRIKE_WINDOW"
    independent_vote: bool = False
    data_only: bool = True
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False
    schema_version: str = "X5_RESEARCH_FEATURE_V1"

    def __post_init__(self) -> None:
        if (
            self.market not in MARKET_EXCHANGES
            or not isinstance(self.expiry, date)
            or isinstance(self.expiry, datetime)
        ):
            raise ValueError("Invalid feature market or expiry")
        if (
            not _aware(self.as_of)
            or not all(
                _text(x)
                for x in (
                    self.metric_name,
                    self.capture_id,
                    self.family,
                    self.dependency_group,
                    self.unit,
                )
            )
            or not _sha(self.source_metric_sha256)
        ):
            raise ValueError("Invalid feature identity or provenance")
        if self.status not in {"AVAILABLE", "UNAVAILABLE"}:
            raise ValueError("Invalid feature status")
        if self.status == "AVAILABLE" and not _finite(self.value):
            raise ValueError("Available feature requires a finite value")
        if self.status == "UNAVAILABLE" and (self.value is not None or not self.blockers):
            raise ValueError("Unavailable feature has no value and requires a blocker")
        if (
            type(self.supporting_strikes) is not tuple
            or any(not _finite(x) or x <= 0 for x in self.supporting_strikes)
            or tuple(sorted(set(self.supporting_strikes))) != self.supporting_strikes
        ):
            raise ValueError("Invalid supporting strike window")
        if (
            type(self.detail) is not tuple
            or any(
                type(item) is not tuple
                or len(item) != 2
                or not _text(item[0])
                or not _finite(item[1])
                for item in self.detail
            )
            or len({item[0] for item in self.detail}) != len(self.detail)
        ):
            raise ValueError("Invalid feature detail")
        if not _strings(self.blockers) or not _strings(self.warnings):
            raise ValueError("Invalid diagnostics")
        if (
            self.scope != "CAPTURED_STRIKE_WINDOW"
            or self.schema_version != "X5_RESEARCH_FEATURE_V1"
        ):
            raise ValueError("Feature cannot claim exchange-wide scope")
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
            raise ValueError("Research feature cannot acquire voting or trading authority")


@dataclass(frozen=True, slots=True)
class X5ResearchViewV1:
    market: str
    expiry: date
    option_exchange: str
    capture_id: str
    session_id: str
    as_of: datetime
    captured_at: datetime
    status: str
    capture_quality_status: str
    total_strike_count: int
    complete_pair_count: int
    call_only_count: int
    put_only_count: int
    features: tuple[X5ResearchFeatureV1, ...]
    dependency_groups: tuple[str, ...]
    group_coverage: tuple[tuple[str, int], ...]
    available_metrics: tuple[str, ...]
    unavailable_metrics: tuple[str, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    source_capture_sha256: str
    source_validation_sha256: str
    source_analytics_sha256: str
    manifest_sha256: str
    point_in_time_verified: bool
    historical_retrieval: bool
    scope: str = "CAPTURED_STRIKE_WINDOW"
    independent_vote: bool = False
    data_only: bool = True
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False
    schema_version: str = "X5_RESEARCH_VIEW_V1"

    def __post_init__(self) -> None:
        if (
            self.market not in MARKET_EXCHANGES
            or self.option_exchange != MARKET_EXCHANGES[self.market][0]
        ):
            raise ValueError("Invalid research market or exchange")
        if (
            not isinstance(self.expiry, date)
            or isinstance(self.expiry, datetime)
            or not all(_text(x) for x in (self.capture_id, self.session_id))
            or not _aware(self.as_of)
            or not _aware(self.captured_at)
        ):
            raise ValueError("Invalid research identity or timestamp")
        if self.status not in {
            "AVAILABLE",
            "PARTIAL",
            "UNAVAILABLE",
        } or self.capture_quality_status not in {"AVAILABLE", "PARTIAL", "UNAVAILABLE"}:
            raise ValueError("Invalid research availability")
        if not all(
            type(x) is int and x >= 0
            for x in (
                self.total_strike_count,
                self.complete_pair_count,
                self.call_only_count,
                self.put_only_count,
            )
        ):
            raise ValueError("Invalid strike/pair count")
        if (
            self.total_strike_count
            != self.complete_pair_count + self.call_only_count + self.put_only_count
        ):
            raise ValueError("Inconsistent strike/pair count")
        if (
            type(self.features) is not tuple
            or tuple(x.metric_name for x in self.features if isinstance(x, X5ResearchFeatureV1))
            != METRICS
            or len(self.features) != len(METRICS)
        ):
            raise ValueError("Exactly nine canonical research features are required")
        if any(
            x.market != self.market
            or x.expiry != self.expiry
            or x.capture_id != self.capture_id
            or x.as_of != self.as_of
            for x in self.features
        ):
            raise ValueError("Mixed feature identities or timestamps")
        if not _strings(self.dependency_groups) or len(set(self.dependency_groups)) != len(
            self.dependency_groups
        ):
            raise ValueError("Duplicate or invalid dependency groups")
        if self.dependency_groups != tuple(sorted({x.dependency_group for x in self.features})):
            raise ValueError("Dependency groups are not canonical")
        if (
            type(self.group_coverage) is not tuple
            or any(type(x) is not tuple or len(x) != 2 for x in self.group_coverage)
            or tuple(x[0] for x in self.group_coverage) != self.dependency_groups
            or any(
                type(g) is not str or type(n) is not int or n < 0 or n > len(self.features)
                for g, n in self.group_coverage
            )
        ):
            raise ValueError("Invalid group coverage")
        if any(
            n != sum(x.status == "AVAILABLE" and x.dependency_group == g for x in self.features)
            for g, n in self.group_coverage
        ):
            raise ValueError("Dependency group coverage is inconsistent")
        if (
            not _strings(self.available_metrics)
            or not _strings(self.unavailable_metrics)
            or (
                self.available_metrics
                != tuple(x.metric_name for x in self.features if x.status == "AVAILABLE")
                or self.unavailable_metrics
                != tuple(x.metric_name for x in self.features if x.status == "UNAVAILABLE")
            )
        ):
            raise ValueError("Metric availability does not match the features")
        expected_status = (
            "UNAVAILABLE"
            if not self.available_metrics
            else "AVAILABLE"
            if not self.unavailable_metrics
            else "PARTIAL"
        )
        if self.status != expected_status or (
            self.capture_quality_status == "UNAVAILABLE" and self.available_metrics
        ):
            raise ValueError("Status cannot upgrade blocked capture evidence")
        if (
            not _strings(self.blockers)
            or not _strings(self.warnings)
            or not all(
                _sha(value)
                for value in (
                    self.source_capture_sha256,
                    self.source_validation_sha256,
                    self.source_analytics_sha256,
                    self.manifest_sha256,
                )
            )
        ):
            raise ValueError("Invalid research provenance/diagnostics")
        if (
            type(self.point_in_time_verified) is not bool
            or type(self.historical_retrieval) is not bool
        ):
            raise ValueError("Invalid replay flags")
        if (
            self.historical_retrieval or not self.point_in_time_verified
        ) and self.available_metrics:
            raise ValueError("Retrospective or unproven capture cannot expose available metrics")
        if self.scope != "CAPTURED_STRIKE_WINDOW" or self.schema_version != "X5_RESEARCH_VIEW_V1":
            raise ValueError("Research view cannot claim exchange-wide scope")
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
            raise ValueError("Research view has no trading or voting authority")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def sha256(self) -> str:
        return canonical_sha256(self.to_dict())


def _project_feature(
    metric: X5ResearchMetricV1, spec: X5FeatureSpecV1, capture: X5ChainCaptureV1
) -> X5ResearchFeatureV1:
    if (
        metric.metric_name != spec.metric_name
        or metric.dependency_group != spec.dependency_group
        or metric.unit != spec.unit
    ):
        raise ValueError("Analytics metric disagrees with the fixed X5 manifest")
    return X5ResearchFeatureV1(
        metric_name=metric.metric_name,
        market=capture.contract.market,
        expiry=capture.contract.expiry,
        capture_id=capture.capture_id,
        as_of=capture.as_of,
        family=spec.family,
        dependency_group=spec.dependency_group,
        status=metric.status,
        value=metric.value,
        unit=metric.unit,
        supporting_strikes=metric.supporting_strikes,
        detail=metric.detail,
        blockers=metric.blockers,
        warnings=metric.warnings,
        source_metric_sha256=canonical_sha256(asdict(metric)),
    )


def build_x5_research_view_v1(
    *,
    capture: X5ChainCaptureV1,
    validation: X5ChainValidationV1,
    analytics: X5AnalyticsResultV1,
    manifest: X5FeatureManifestV1 | None = None,
) -> X5ResearchViewV1:
    """Project one consistent X5 snapshot. Never recompute or aggregate signals."""
    if (
        not isinstance(capture, X5ChainCaptureV1)
        or not isinstance(validation, X5ChainValidationV1)
        or not isinstance(analytics, X5AnalyticsResultV1)
    ):
        raise ValueError("Versioned capture, validation and analytics are required")
    fixed_manifest = build_x5_feature_manifest_v1()
    selected_manifest = fixed_manifest if manifest is None else manifest
    if (
        not isinstance(selected_manifest, X5FeatureManifestV1)
        or selected_manifest.sha256() != fixed_manifest.sha256()
    ):
        raise ValueError("Unknown or modified X5 feature manifest")
    expected_identity = (
        capture.contract.market,
        capture.contract.expiry,
        capture.capture_id,
        capture.as_of,
    )
    if (
        validation.market,
        validation.expiry,
        validation.capture_id,
        validation.as_of,
    ) != expected_identity or (
        analytics.market,
        analytics.expiry,
        analytics.capture_id,
        analytics.as_of,
    ) != expected_identity:
        raise ValueError("Mixed capture/validation/analytics identities")
    capture_hash = capture.sha256()
    validation_hash = validation.sha256()
    if (
        validation.source_capture_sha256 != capture_hash
        or analytics.source_capture_sha256 != capture_hash
        or (analytics.source_validation_sha256 != validation_hash)
    ):
        raise ValueError("Source capture/validation hash mismatch")
    if analytics.blockers != validation.blockers or analytics.warnings != validation.warnings:
        raise ValueError("Analytics diagnostics do not match source validation")
    if len(analytics.metrics) != len(selected_manifest.features):
        raise ValueError("Analytics feature inventory mismatch")
    ready = dict(validation.readiness)
    if tuple(ready) != METRICS:
        raise ValueError("Unknown, missing or reordered validation readiness")
    if any(
        metric.status == "AVAILABLE" and ready[metric.metric_name] != "AVAILABLE"
        for metric in analytics.metrics
    ):
        raise ValueError("Unavailable validation data was promoted")
    features = tuple(
        _project_feature(metric, spec, capture)
        for metric, spec in zip(analytics.metrics, selected_manifest.features, strict=True)
    )
    available = tuple(feature.metric_name for feature in features if feature.status == "AVAILABLE")
    unavailable = tuple(
        feature.metric_name for feature in features if feature.status == "UNAVAILABLE"
    )
    computed_status = (
        "UNAVAILABLE" if not available else "AVAILABLE" if not unavailable else "PARTIAL"
    )
    if analytics.status != computed_status:
        raise ValueError("Analytics result status is inconsistent with its metrics")
    groups = tuple(sorted({feature.dependency_group for feature in features}))
    return X5ResearchViewV1(
        market=capture.contract.market,
        expiry=capture.contract.expiry,
        option_exchange=capture.contract.option_exchange,
        capture_id=capture.capture_id,
        session_id=capture.session_id,
        as_of=capture.as_of,
        captured_at=capture.captured_at,
        status=computed_status,
        capture_quality_status=validation.status,
        total_strike_count=validation.complete_pair_count
        + validation.call_only_count
        + validation.put_only_count,
        complete_pair_count=validation.complete_pair_count,
        call_only_count=validation.call_only_count,
        put_only_count=validation.put_only_count,
        features=features,
        dependency_groups=groups,
        group_coverage=tuple(
            (group, sum(x.status == "AVAILABLE" and x.dependency_group == group for x in features))
            for group in groups
        ),
        available_metrics=available,
        unavailable_metrics=unavailable,
        blockers=_dedup(validation.blockers, analytics.blockers, *(x.blockers for x in features)),
        warnings=_dedup(validation.warnings, analytics.warnings, *(x.warnings for x in features)),
        source_capture_sha256=capture_hash,
        source_validation_sha256=validation_hash,
        source_analytics_sha256=analytics.sha256(),
        manifest_sha256=selected_manifest.sha256(),
        point_in_time_verified=capture.point_in_time_verified,
        historical_retrieval=capture.historical_retrieval,
    )
