"""Immutable offline X7 research view with exact source/adapter provenance.

This is NOT a decision, source authenticator, independent-vote calculator,
calendar authority, execution gate, market ranking or FYERS data fetcher.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime

from services.x7.contracts_v1 import (
    INDEX_MARKETS,
    MARKETS,
    X7ContextCaptureV1,
    X7ContextValidationV1,
    _authority,
    _aware,
    _sha,
    _text,
    canonical_sha256,
)
from services.x7.event_adapter_v1 import X7EventBatchV1
from services.x7.global_adapter_v1 import X7GlobalBatchV1
from services.x7.input_validation_v1 import validate_x7_context_v1
from services.x7.institutional_adapter_v1 import X7InstitutionalBatchV1

_FAMILIES = ("GLOBAL", "INSTITUTIONAL", "EVENT")


def _budget(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value > 0


@dataclass(frozen=True, slots=True)
class X7SourceTraceV1:
    family: str
    fact_id: str
    source_id: str
    source_record_id: str
    raw_record_sha256: str
    proof_sha256: str
    status: str
    observed_at: datetime
    published_at: datetime | None
    available_at: datetime | None
    schema_version: str = "X7_SOURCE_TRACE_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if (
            self.family not in _FAMILIES
            or not all(_text(x) for x in (self.fact_id, self.source_id, self.source_record_id))
            or not _sha(self.raw_record_sha256)
            or not _sha(self.proof_sha256)
            or self.status not in {"AVAILABLE", "UNVERIFIED", "UNAVAILABLE", "STALE"}
            or not _aware(self.observed_at)
        ):
            raise ValueError("Invalid X7 source trace identity/status/hashes")
        if self.published_at is not None and (
            not _aware(self.published_at) or self.published_at < self.observed_at
        ):
            raise ValueError("Trace publication cannot precede its observation")
        if self.available_at is not None and (
            not _aware(self.available_at)
            or self.published_at is None
            or self.available_at < self.published_at
        ):
            raise ValueError("Trace availability must follow publication")
        _authority(self, "X7_SOURCE_TRACE_V1")


def _source_traces(
    *,
    global_batch: X7GlobalBatchV1,
    institutional_batch: X7InstitutionalBatchV1 | None,
    event_batch: X7EventBatchV1 | None,
) -> tuple[X7SourceTraceV1, ...]:
    rows: list[X7SourceTraceV1] = []
    for item in global_batch.observations:
        fact = item.observation
        rows.append(
            X7SourceTraceV1(
                "GLOBAL",
                fact.name,
                fact.source_id,
                fact.source_record_id,
                item.raw_record_sha256,
                item.proof_sha256,
                fact.status,
                fact.observed_at,
                fact.published_at,
                fact.available_at,
            )
        )
    if institutional_batch is not None:
        for item in institutional_batch.flows:
            fact = item.flow
            rows.append(
                X7SourceTraceV1(
                    "INSTITUTIONAL",
                    fact.trading_date.isoformat(),
                    fact.source_id,
                    item.source_record_id,
                    item.raw_record_sha256,
                    item.proof_sha256,
                    fact.status,
                    fact.observed_at,
                    fact.published_at,
                    fact.available_at,
                )
            )
    if event_batch is not None:
        for item in event_batch.events:
            fact = item.event
            rows.append(
                X7SourceTraceV1(
                    "EVENT",
                    fact.event_id,
                    fact.source_id,
                    item.source_record_id,
                    item.raw_record_sha256,
                    item.proof_sha256,
                    fact.status,
                    fact.observed_at,
                    fact.published_at,
                    fact.available_at,
                )
            )
    return tuple(
        sorted(
            rows,
            key=lambda row: (
                _FAMILIES.index(row.family),
                row.fact_id,
            ),
        )
    )


def _dependencies(
    *,
    global_batch: X7GlobalBatchV1,
    institutional_batch: X7InstitutionalBatchV1 | None,
    event_batch: X7EventBatchV1 | None,
    traces: tuple[X7SourceTraceV1, ...],
) -> tuple[
    tuple[tuple[str, tuple[str, ...]], ...],
    tuple[tuple[str, tuple[str, ...]], ...],
]:
    # Global groups identify correlated economic themes, NOT additive votes.
    groups = tuple(
        (f"GLOBAL:{label}", tuple(f"GLOBAL:{name}" for name in names))
        for label, names in global_batch.dependency_groups
    )
    if institutional_batch is not None and institutional_batch.flows:
        groups += (
            (
                "INSTITUTIONAL:CASH_EQUITY",
                tuple(
                    f"INSTITUTIONAL:{item.flow.trading_date.isoformat()}"
                    for item in institutional_batch.flows
                ),
            ),
        )
    if event_batch is not None:
        for category in sorted({row.event.category for row in event_batch.events}):
            groups += (
                (
                    f"EVENT:{category}",
                    tuple(
                        f"EVENT:{row.event.event_id}"
                        for row in event_batch.events
                        if row.event.category == category
                    ),
                ),
            )
    sources: dict[str, list[str]] = defaultdict(list)
    for trace in traces:
        sources[trace.source_id].append(f"{trace.family}:{trace.fact_id}")
    shared = tuple(
        (source, tuple(sorted(ids))) for source, ids in sorted(sources.items()) if len(ids) > 1
    )
    return groups, shared


@dataclass(frozen=True, slots=True)
class X7ResearchViewV1:
    capture: X7ContextCaptureV1
    validation: X7ContextValidationV1
    global_batch_sha256: str
    institutional_batch_sha256: str | None
    event_batch_sha256: str | None
    global_max_age_seconds: float
    institutional_max_age_seconds: float
    event_max_age_seconds: float
    source_traces: tuple[X7SourceTraceV1, ...]
    dependency_groups: tuple[tuple[str, tuple[str, ...]], ...]
    shared_source_groups: tuple[tuple[str, tuple[str, ...]], ...]
    provenance_sha256: str
    status: str
    schema_version: str = "X7_RESEARCH_VIEW_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.capture, X7ContextCaptureV1) or not isinstance(
            self.validation, X7ContextValidationV1
        ):
            raise TypeError("Research view requires exact X7 capture and validation")
        if (
            self.validation.source_capture_sha256 != self.capture.sha256()
            or self.validation.market != self.capture.market
            or self.validation.capture_id != self.capture.capture_id
            or self.validation.as_of != self.capture.as_of
            or self.status != self.validation.status
            or not _sha(self.global_batch_sha256)
            or (
                self.institutional_batch_sha256 is not None
                and not _sha(self.institutional_batch_sha256)
            )
            or (self.event_batch_sha256 is not None and not _sha(self.event_batch_sha256))
            or not all(
                _budget(x)
                for x in (
                    self.global_max_age_seconds,
                    self.institutional_max_age_seconds,
                    self.event_max_age_seconds,
                )
            )
            or type(self.source_traces) is not tuple
            or any(not isinstance(row, X7SourceTraceV1) for row in self.source_traces)
            or not _sha(self.provenance_sha256)
        ):
            raise ValueError("Inconsistent X7 research-view identity/provenance")
        if (
            tuple(
                sorted(
                    self.source_traces,
                    key=lambda row: (
                        _FAMILIES.index(row.family),
                        row.fact_id,
                    ),
                )
            )
            != self.source_traces
        ):
            raise ValueError("Source traces must be in deterministic family/fact order")
        if len({(row.family, row.fact_id) for row in self.source_traces}) != len(
            self.source_traces
        ):
            raise ValueError("Source facts must not be repeated")
        if len({(row.source_id, row.source_record_id) for row in self.source_traces}) != len(
            self.source_traces
        ):
            raise ValueError("A publisher record must not be reused across evidence families")
        if any(
            row.observed_at > self.capture.as_of
            or (row.published_at is not None and row.published_at > self.capture.as_of)
            or (row.available_at is not None and row.available_at > self.capture.as_of)
            for row in self.source_traces
        ):
            raise ValueError("Future/published-after-capture evidence is forbidden")
        if self.capture.market not in INDEX_MARKETS and self.institutional_batch_sha256 is not None:
            raise ValueError("MCX cannot inherit index cash-equity evidence")
        if self.provenance_sha256 != canonical_sha256(
            {
                "market": self.capture.market,
                "session_id": self.capture.session_id,
                "capture_id": self.capture.capture_id,
                "as_of": self.capture.as_of,
                "capture_sha256": self.capture.sha256(),
                "validation_sha256": self.validation.sha256(),
                "global_batch_sha256": self.global_batch_sha256,
                "institutional_batch_sha256": self.institutional_batch_sha256,
                "event_batch_sha256": self.event_batch_sha256,
                "global_max_age_seconds": self.global_max_age_seconds,
                "institutional_max_age_seconds": self.institutional_max_age_seconds,
                "event_max_age_seconds": self.event_max_age_seconds,
                "source_traces": [asdict(row) for row in self.source_traces],
                "dependency_groups": self.dependency_groups,
                "shared_source_groups": self.shared_source_groups,
            }
        ):
            raise ValueError("Research-view provenance manifest hash mismatch")
        _authority(self, "X7_RESEARCH_VIEW_V1")

    def sha256(self) -> str:
        return canonical_sha256(asdict(self))


def build_x7_research_view_v1(
    *,
    global_batch: X7GlobalBatchV1,
    institutional_batch: X7InstitutionalBatchV1 | None,
    event_batch: X7EventBatchV1 | None,
    capture_verified: bool,
    point_in_time_verified: bool,
    historical_retrieval: bool,
    global_max_age_seconds: float,
    institutional_max_age_seconds: float,
    event_max_age_seconds: float,
) -> X7ResearchViewV1:
    """Compose supplied exact matching X7 batches; do not create missing facts."""
    if not isinstance(global_batch, X7GlobalBatchV1):
        raise TypeError("A typed global batch is required, even when empty")
    for batch, cls in (
        (institutional_batch, X7InstitutionalBatchV1),
        (event_batch, X7EventBatchV1),
    ):
        if batch is not None and not isinstance(batch, cls):
            raise TypeError("Optional batches must have their exact X7 types")
        if batch is not None and any(
            getattr(batch, key) != getattr(global_batch, key)
            for key in ("market", "session_id", "capture_id", "as_of")
        ):
            raise ValueError("All context batches must match one market/session/capture/time")
    if global_batch.market not in MARKETS or (
        global_batch.market not in INDEX_MARKETS and institutional_batch is not None
    ):
        raise ValueError("Institutional cash-equity context is index-only")
    for flag in (capture_verified, point_in_time_verified, historical_retrieval):
        if type(flag) is not bool:
            raise ValueError("Capture authority/time flags must be exact booleans")
    for value in (global_max_age_seconds, institutional_max_age_seconds, event_max_age_seconds):
        if not _budget(value):
            raise ValueError("All validation freshness budgets must be finite and positive")
    if institutional_batch is not None and any(
        row.max_age_seconds != institutional_max_age_seconds for row in institutional_batch.flows
    ):
        raise ValueError("Institutional batch and validation freshness budgets conflict")
    if event_batch is not None and any(
        row.max_age_seconds != event_max_age_seconds for row in event_batch.events
    ):
        raise ValueError("Event batch and validation freshness budgets conflict")
    capture = X7ContextCaptureV1(
        market=global_batch.market,
        session_id=global_batch.session_id,
        capture_id=global_batch.capture_id,
        as_of=global_batch.as_of,
        global_observations=tuple(x.observation for x in global_batch.observations),
        institutional_flows=(
            tuple(x.flow for x in institutional_batch.flows)
            if institutional_batch is not None
            else ()
        ),
        scheduled_events=(
            tuple(x.event for x in event_batch.events) if event_batch is not None else ()
        ),
        capture_verified=capture_verified,
        point_in_time_verified=point_in_time_verified,
        historical_retrieval=historical_retrieval,
    )
    validation = validate_x7_context_v1(
        capture,
        global_max_age_seconds=global_max_age_seconds,
        institutional_max_age_seconds=institutional_max_age_seconds,
        event_max_age_seconds=event_max_age_seconds,
    )
    traces = _source_traces(
        global_batch=global_batch,
        institutional_batch=institutional_batch,
        event_batch=event_batch,
    )
    dependencies, shared = _dependencies(
        global_batch=global_batch,
        institutional_batch=institutional_batch,
        event_batch=event_batch,
        traces=traces,
    )
    params = dict(
        capture=capture,
        validation=validation,
        global_batch_sha256=global_batch.sha256(),
        institutional_batch_sha256=(
            institutional_batch.sha256() if institutional_batch is not None else None
        ),
        event_batch_sha256=event_batch.sha256() if event_batch is not None else None,
        global_max_age_seconds=float(global_max_age_seconds),
        institutional_max_age_seconds=float(institutional_max_age_seconds),
        event_max_age_seconds=float(event_max_age_seconds),
        source_traces=traces,
        dependency_groups=dependencies,
        shared_source_groups=shared,
    )
    view = X7ResearchViewV1(
        **params,
        provenance_sha256=canonical_sha256(
            {
                "market": capture.market,
                "session_id": capture.session_id,
                "capture_id": capture.capture_id,
                "as_of": capture.as_of,
                "capture_sha256": capture.sha256(),
                "validation_sha256": validation.sha256(),
                **{
                    key: params[key]
                    for key in (
                        "global_batch_sha256",
                        "institutional_batch_sha256",
                        "event_batch_sha256",
                        "global_max_age_seconds",
                        "institutional_max_age_seconds",
                        "event_max_age_seconds",
                        "dependency_groups",
                        "shared_source_groups",
                    )
                },
                "source_traces": [asdict(row) for row in traces],
            }
        ),
        status=validation.status,
    )
    return view


__all__ = [
    "X7SourceTraceV1",
    "X7ResearchViewV1",
    "build_x7_research_view_v1",
]
