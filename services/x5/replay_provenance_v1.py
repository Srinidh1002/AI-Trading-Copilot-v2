"""Deterministic X5 source-hash replay auditor; pure, bounded and without orders.

An externally retained witness can reveal modifications made after capture. Hash
consistency is not cryptographic authentication, independent provider proof, or
proof that retrospectively retrieved data was available at a historical time.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from math import isfinite
from string import hexdigits

from services.x5.analytics_v1 import X5AnalyticsResultV1, analyze_x5_chain_v1
from services.x5.chain_validation_v1 import METRICS, validate_x5_chain_v1
from services.x5.contracts_v1 import (
    IST,
    MARKET_EXCHANGES,
    X5ChainCaptureV1,
    X5ChainValidationV1,
    canonical_sha256,
)
from services.x5.research_view_v1 import X5ResearchViewV1, build_x5_research_view_v1


def _sha(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(x in hexdigits for x in value)


def _text(value: object) -> bool:
    return isinstance(value, str) and value.strip() == value and bool(value)


def _aware(value: object) -> bool:
    return (
        isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
    )


def _row_seals(capture: X5ChainCaptureV1) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(
            (row.source_record_id, canonical_sha256(asdict(row))) for row in capture.observations
        )
    )


def _window(capture: X5ChainCaptureV1) -> tuple[tuple[float, str], ...]:
    return tuple(sorted((float(row.strike), row.option_type) for row in capture.observations))


@dataclass(frozen=True, slots=True)
class X5ReplayFrameV1:
    """Captured objects with digests retained independently of later replay."""

    capture: X5ChainCaptureV1
    validation: X5ChainValidationV1
    analytics: X5AnalyticsResultV1
    view: X5ResearchViewV1
    expected_capture_sha256: str
    expected_validation_sha256: str
    expected_analytics_sha256: str
    expected_view_sha256: str
    expected_row_seals: tuple[tuple[str, str], ...]
    schema_version: str = "X5_REPLAY_FRAME_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if (
            not isinstance(self.capture, X5ChainCaptureV1)
            or not isinstance(self.validation, X5ChainValidationV1)
            or not isinstance(self.analytics, X5AnalyticsResultV1)
            or not isinstance(self.view, X5ResearchViewV1)
        ):
            raise ValueError("Four versioned X5 source objects are required")
        if not all(
            _sha(value)
            for value in (
                self.expected_capture_sha256,
                self.expected_validation_sha256,
                self.expected_analytics_sha256,
                self.expected_view_sha256,
            )
        ):
            raise ValueError("Four SHA-256 witness digests are required")
        if (
            type(self.expected_row_seals) is not tuple
            or any(
                type(row) is not tuple or len(row) != 2 or not _text(row[0]) or not _sha(row[1])
                for row in self.expected_row_seals
            )
            or tuple(sorted(self.expected_row_seals)) != self.expected_row_seals
            or len({row[0] for row in self.expected_row_seals}) != len(self.expected_row_seals)
        ):
            raise ValueError("Canonical independent per-row witnesses are required")
        flags = (
            self.data_only,
            self.independent_vote,
            self.execution_authority,
            self.risk_authority,
            self.position_authority,
            self.certification_authority,
            self.live_execution_eligible,
        )
        if any(type(flag) is not bool for flag in flags):
            raise ValueError("Replay authority flags must be exact booleans")
        if (
            self.schema_version != "X5_REPLAY_FRAME_V1"
            or self.data_only is not True
            or (self.independent_vote is not False)
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
            raise ValueError("X5 replay frame has no trading or voting authority")


def seal_x5_replay_frame_v1(
    *, capture: X5ChainCaptureV1, max_age_seconds: float
) -> X5ReplayFrameV1:
    """Create a witness from given in-memory data; store it separately afterward.

    The caller, not this helper, is responsible for source authenticity and
    independent retention of the witness. Never re-seal a suspect capture.
    """
    validation = validate_x5_chain_v1(capture, max_age_seconds=max_age_seconds)
    analytics = analyze_x5_chain_v1(capture=capture, max_age_seconds=max_age_seconds)
    view = build_x5_research_view_v1(capture=capture, validation=validation, analytics=analytics)
    return X5ReplayFrameV1(
        capture=capture,
        validation=validation,
        analytics=analytics,
        view=view,
        expected_capture_sha256=capture.sha256(),
        expected_validation_sha256=validation.sha256(),
        expected_analytics_sha256=analytics.sha256(),
        expected_view_sha256=view.sha256(),
        expected_row_seals=_row_seals(capture),
    )


@dataclass(frozen=True, slots=True)
class X5ReplayRecordV1:
    market: str
    expiry: date
    session_id: str
    capture_id: str
    as_of: datetime
    captured_at: datetime
    source_capture_sha256: str
    source_validation_sha256: str
    source_analytics_sha256: str
    source_view_sha256: str
    row_seals_sha256: str
    captured_window_sha256: str
    coverage_transition: str
    observation_provenance: str
    research_status: str
    available_metrics: tuple[str, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    previous_record_sha256: str | None
    scope: str = "CAPTURED_STRIKE_WINDOW"
    data_only: bool = True
    independent_vote: bool = False
    cross_frame_metric_comparison_allowed: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False
    schema_version: str = "X5_REPLAY_RECORD_V1"

    def __post_init__(self) -> None:
        if (
            self.market not in MARKET_EXCHANGES
            or not isinstance(self.expiry, date)
            or isinstance(self.expiry, datetime)
            or not _text(self.session_id)
            or not _text(self.capture_id)
        ):
            raise ValueError("Invalid replay record identity")
        if not _aware(self.as_of) or not _aware(self.captured_at):
            raise ValueError("Replay record requires aware timestamps")
        if any(
            not _sha(x)
            for x in (
                self.source_capture_sha256,
                self.source_validation_sha256,
                self.source_analytics_sha256,
                self.source_view_sha256,
                self.row_seals_sha256,
                self.captured_window_sha256,
            )
        ) or (self.previous_record_sha256 is not None and not _sha(self.previous_record_sha256)):
            raise ValueError("Replay record requires SHA-256 provenance")
        if self.coverage_transition not in {"FIRST_FRAME", "SAME_WINDOW", "WINDOW_CHANGED"}:
            raise ValueError("Unknown strike-window transition")
        if self.observation_provenance not in {
            "CONTEMPORANEOUS_ATTESTED",
            "RETROSPECTIVE_UNPROVEN",
            "POINT_IN_TIME_UNPROVEN",
        } or self.research_status not in {"AVAILABLE", "PARTIAL", "UNAVAILABLE"}:
            raise ValueError("Unknown historical provenance or research status")
        if (
            type(self.available_metrics) is not tuple
            or any(x not in METRICS for x in self.available_metrics)
            or tuple(x for x in METRICS if x in self.available_metrics) != self.available_metrics
        ):
            raise ValueError("Invalid or noncanonical available metrics")
        expected_status = (
            "UNAVAILABLE"
            if not self.available_metrics
            else "AVAILABLE"
            if len(self.available_metrics) == len(METRICS)
            else "PARTIAL"
        )
        if self.research_status != expected_status:
            raise ValueError("Replay research status disagrees with available metrics")
        if any(not _text(x) for x in self.blockers + self.warnings):
            raise ValueError("Invalid replay diagnostics")
        if self.observation_provenance != "CONTEMPORANEOUS_ATTESTED" and self.available_metrics:
            raise ValueError("Unproven replay cannot promote research metrics")
        flags = (
            self.data_only,
            self.independent_vote,
            self.cross_frame_metric_comparison_allowed,
            self.execution_authority,
            self.risk_authority,
            self.position_authority,
            self.certification_authority,
            self.live_execution_eligible,
        )
        if any(type(flag) is not bool for flag in flags):
            raise ValueError("Replay authority flags must be exact booleans")
        if (
            self.scope != "CAPTURED_STRIKE_WINDOW"
            or self.schema_version != "X5_REPLAY_RECORD_V1"
            or (
                self.data_only is not True
                or self.independent_vote is not False
                or self.cross_frame_metric_comparison_allowed is not False
            )
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
            raise ValueError("Replay record has no trading, comparison or voting authority")

    def sha256(self) -> str:
        return canonical_sha256(asdict(self))


@dataclass(frozen=True, slots=True)
class X5ReplayResultV1:
    market: str
    expiry: date
    session_id: str
    records: tuple[X5ReplayRecordV1, ...]
    source_frame_count: int
    last_record_sha256: str
    window_transition_count: int
    retrospective_count: int
    scope: str = "CAPTURED_STRIKE_WINDOW"
    data_only: bool = True
    independent_vote: bool = False
    cross_frame_metric_comparison_allowed: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False
    schema_version: str = "X5_REPLAY_RESULT_V1"

    def __post_init__(self) -> None:
        if (
            self.market not in MARKET_EXCHANGES
            or not isinstance(self.expiry, date)
            or isinstance(self.expiry, datetime)
            or not _text(self.session_id)
            or type(self.records) is not tuple
            or not self.records
        ):
            raise ValueError("Invalid replay sequence identity")
        if (
            type(self.source_frame_count) is not int
            or self.source_frame_count != len(self.records)
            or any(not isinstance(record, X5ReplayRecordV1) for record in self.records)
        ):
            raise ValueError("Replay record count or type mismatch")
        if (
            not _sha(self.last_record_sha256)
            or self.last_record_sha256 != self.records[-1].sha256()
        ):
            raise ValueError("Replay last-record witness mismatch")
        if (
            type(self.window_transition_count) is not int
            or self.window_transition_count
            != sum(x.coverage_transition == "WINDOW_CHANGED" for x in self.records)
            or type(self.retrospective_count) is not int
            or self.retrospective_count
            != sum(x.observation_provenance == "RETROSPECTIVE_UNPROVEN" for x in self.records)
        ):
            raise ValueError("Replay count mismatch")
        if any(
            x.market != self.market or x.expiry != self.expiry or x.session_id != self.session_id
            for x in self.records
        ):
            raise ValueError("Mixed replay record identities")
        for idx, record in enumerate(self.records):
            prior = self.records[idx - 1] if idx else None
            expected_previous = prior.sha256() if prior is not None else None
            if record.previous_record_sha256 != expected_previous:
                raise ValueError("Invalid replay record hash-chain link")
            if prior is not None and record.as_of <= prior.as_of:
                raise ValueError("Replay records must have strictly increasing checkpoints")
        if len({record.capture_id for record in self.records}) != len(self.records):
            raise ValueError("Duplicate replay record capture identity")
        flags = (
            self.data_only,
            self.independent_vote,
            self.cross_frame_metric_comparison_allowed,
            self.execution_authority,
            self.risk_authority,
            self.position_authority,
            self.certification_authority,
            self.live_execution_eligible,
        )
        if any(type(flag) is not bool for flag in flags):
            raise ValueError("Replay authority flags must be exact booleans")
        if (
            self.scope != "CAPTURED_STRIKE_WINDOW"
            or self.schema_version != "X5_REPLAY_RESULT_V1"
            or (
                self.data_only is not True
                or self.independent_vote is not False
                or self.cross_frame_metric_comparison_allowed is not False
            )
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
            raise ValueError("Replay result has no trading, comparison or voting authority")

    def sha256(self) -> str:
        return canonical_sha256(asdict(self))


def replay_x5_history_v1(
    *, frames: tuple[X5ReplayFrameV1, ...], max_age_seconds: float, max_step_seconds: float
) -> X5ReplayResultV1:
    """Audit chronological, same-session captures without fetching or synthesizing data.

    Intentionally returns no inter-frame signal or metric deltas. Changed
    strike windows and retrospective captures remain descriptive diagnostics.
    """
    if (
        type(frames) is not tuple
        or not frames
        or any(not isinstance(frame, X5ReplayFrameV1) for frame in frames)
    ):
        raise ValueError("A nonempty immutable tuple of replay frames is required")
    if any(
        type(x) not in (float, int) or not isfinite(x) or x <= 0
        for x in (max_age_seconds, max_step_seconds)
    ):
        raise ValueError("Finite positive freshness and checkpoint budgets are required")
    first = frames[0].capture
    key = (
        first.contract.market,
        first.contract.option_exchange,
        first.contract.expiry,
        first.session_id,
        first.contract.underlying_provider_symbol,
    )
    records: list[X5ReplayRecordV1] = []
    seen_captures: set[str] = set()
    seen_sources: set[str] = set()
    seen_rows: dict[str, str] = {}
    previous: X5ChainCaptureV1 | None = None
    previous_window: tuple[tuple[float, str], ...] | None = None
    previous_identity: dict[tuple[float, str], tuple[str, str]] | None = None
    previous_hash: str | None = None
    for frame in frames:
        capture = frame.capture
        current_key = (
            capture.contract.market,
            capture.contract.option_exchange,
            capture.contract.expiry,
            capture.session_id,
            capture.contract.underlying_provider_symbol,
        )
        if current_key != key or capture.contract != first.contract:
            raise ValueError("Mixed market, contract, expiry or session in one replay")
        if capture.capture_id in seen_captures or capture.source_id in seen_sources:
            raise ValueError("Duplicate capture or source identity in replay")
        seen_captures.add(capture.capture_id)
        seen_sources.add(capture.source_id)
        if previous is not None:
            interval = (capture.as_of - previous.as_of).total_seconds()
            if interval <= 0 or interval > max_step_seconds:
                raise ValueError(
                    "Replay checkpoint is duplicate, out of order or beyond gap budget"
                )
        if capture.as_of.astimezone(IST).date() != first.as_of.astimezone(IST).date():
            raise ValueError("Cross-session replay requires a separately identified session")
        for stored, current in (
            (frame.expected_capture_sha256, capture.sha256()),
            (frame.expected_validation_sha256, frame.validation.sha256()),
            (frame.expected_analytics_sha256, frame.analytics.sha256()),
            (frame.expected_view_sha256, frame.view.sha256()),
        ):
            if stored != current:
                raise ValueError("Replay witness hash mismatch")
        row_seals = _row_seals(capture)
        if row_seals != frame.expected_row_seals:
            raise ValueError("Per-row witness mismatch")
        for row_id, row_hash in row_seals:
            if row_id in seen_rows and seen_rows[row_id] != row_hash:
                raise ValueError("Reused source record identity has conflicting content")
            seen_rows[row_id] = row_hash
        expected_validation = validate_x5_chain_v1(capture, max_age_seconds=max_age_seconds)
        expected_analytics = analyze_x5_chain_v1(capture=capture, max_age_seconds=max_age_seconds)
        expected_view = build_x5_research_view_v1(
            capture=capture, validation=expected_validation, analytics=expected_analytics
        )
        if (
            frame.validation != expected_validation
            or frame.analytics != expected_analytics
            or frame.view != expected_view
        ):
            raise ValueError(
                "Stored validation, analytics or view disagrees with replay calculation"
            )
        current_window = _window(capture)
        current_identity = {
            (float(row.strike), row.option_type): (row.canonical_option_id, row.provider_symbol)
            for row in capture.observations
        }
        if previous_identity is not None and any(
            current_identity[key] != prior
            for key, prior in previous_identity.items()
            if key in current_identity
        ):
            raise ValueError("Canonical option contract changed inside a replay window")
        transition = (
            "FIRST_FRAME"
            if previous_window is None
            else "SAME_WINDOW"
            if previous_window == current_window
            else "WINDOW_CHANGED"
        )
        if capture.historical_retrieval:
            provenance = "RETROSPECTIVE_UNPROVEN"
        elif capture.point_in_time_verified:
            provenance = "CONTEMPORANEOUS_ATTESTED"
        else:
            provenance = "POINT_IN_TIME_UNPROVEN"
        if provenance != "CONTEMPORANEOUS_ATTESTED" and frame.view.available_metrics:
            raise ValueError("Unproven capture cannot expose metrics in replay")
        notes = frame.view.warnings + (
            ("NON_COMPARABLE_STRIKE_WINDOW",) if transition == "WINDOW_CHANGED" else ()
        )
        record = X5ReplayRecordV1(
            market=capture.contract.market,
            expiry=capture.contract.expiry,
            session_id=capture.session_id,
            capture_id=capture.capture_id,
            as_of=capture.as_of,
            captured_at=capture.captured_at,
            source_capture_sha256=capture.sha256(),
            source_validation_sha256=frame.validation.sha256(),
            source_analytics_sha256=frame.analytics.sha256(),
            source_view_sha256=frame.view.sha256(),
            row_seals_sha256=canonical_sha256(row_seals),
            captured_window_sha256=canonical_sha256(current_window),
            coverage_transition=transition,
            observation_provenance=provenance,
            research_status=frame.view.status,
            available_metrics=frame.view.available_metrics,
            blockers=frame.view.blockers,
            warnings=notes,
            previous_record_sha256=previous_hash,
        )
        records.append(record)
        previous, previous_window, previous_identity, previous_hash = (
            capture,
            current_window,
            current_identity,
            record.sha256(),
        )
    return X5ReplayResultV1(
        market=first.contract.market,
        expiry=first.contract.expiry,
        session_id=first.session_id,
        records=tuple(records),
        source_frame_count=len(frames),
        last_record_sha256=records[-1].sha256(),
        window_transition_count=sum(x.coverage_transition == "WINDOW_CHANGED" for x in records),
        retrospective_count=sum(
            x.observation_provenance == "RETROSPECTIVE_UNPROVEN" for x in records
        ),
    )
