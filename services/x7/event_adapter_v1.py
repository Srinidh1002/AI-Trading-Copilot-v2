"""X7-B3 pure adaptation of supplied scheduled-calendar records.

Records plus typed caller attestations are not independent publisher authentication.
The canonical session calendar retains exchange-open/closed authority; none of
these records can block entry, select an option, size risk or place an order.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone

from services.x7.contracts_v1 import (
    EVENT_CATEGORIES,
    MARKETS,
    SEVERITIES,
    X7ScheduledEventV1,
    _authority,
    _aware,
    _markets,
    _text,
    canonical_sha256,
)

IST = timezone(timedelta(hours=5, minutes=30))
STATES = frozenset({"CONFIRMED", "TENTATIVE", "CANCELLED", "POSTPONED", "UNAVAILABLE"})
SESSION_EVENTS = frozenset({"EXCHANGE_HOLIDAY", "SPECIAL_SESSION"})
EXPIRY_EVENTS = frozenset({"WEEKLY_EXPIRY", "MONTHLY_EXPIRY"})
CONTRACT_EVENTS = EXPIRY_EVENTS | {"ROLLOVER"}
_RAW_KEYS = frozenset(
    {
        "event_id",
        "category",
        "scheduled_at",
        "affected_markets",
        "severity",
        "source_id",
        "source_record_id",
        "observed_at",
        "published_at",
        "available_at",
        "schedule_state",
        "bound_contract_id",
        "bound_contract_expiry",
    }
)


def _sha(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


def _budget(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value > 0


@dataclass(frozen=True, slots=True)
class X7EventSourceProofV1:
    """Caller-supplied, independently audited *assertions* about one calendar fact."""

    event_id: str
    category: str
    scheduled_at: datetime
    affected_markets: tuple[str, ...]
    severity: str
    source_id: str
    source_record_id: str
    observed_at: datetime
    published_at: datetime | None
    available_at: datetime | None
    schedule_state: str
    bound_contract_id: str | None
    bound_contract_expiry: date | None
    source_verified: bool
    timestamp_semantics_verified: bool
    schedule_verified: bool
    calendar_reference_verified: bool = False
    contract_binding_verified: bool = False
    schema_version: str = "X7_EVENT_SOURCE_PROOF_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if (
            not _text(self.event_id)
            or self.category not in EVENT_CATEGORIES
            or not _aware(self.scheduled_at)
            or not _markets(self.affected_markets)
            or self.severity not in SEVERITIES
            or self.schedule_state not in STATES
            or not _text(self.source_id)
            or not _text(self.source_record_id)
            or not _aware(self.observed_at)
        ):
            raise ValueError("Exact event identity, source, schedule and markets are required")
        if self.published_at is not None and (
            not _aware(self.published_at) or self.published_at < self.observed_at
        ):
            raise ValueError("Publication cannot precede the observed record")
        if self.available_at is not None and (
            not _aware(self.available_at)
            or self.published_at is None
            or self.available_at < self.published_at
        ):
            raise ValueError("Availability cannot precede verified publication")
        for flag in (
            self.source_verified,
            self.timestamp_semantics_verified,
            self.schedule_verified,
            self.calendar_reference_verified,
            self.contract_binding_verified,
        ):
            if type(flag) is not bool:
                raise ValueError("Verification flags must be exact booleans")
        if self.source_verified and (
            not self.timestamp_semantics_verified
            or self.published_at is None
            or self.available_at is None
        ):
            raise ValueError("Verified source requires verified temporal provenance")
        if self.schedule_verified and not self.source_verified:
            raise ValueError("Schedule cannot be verified without a verified source")
        if self.calendar_reference_verified and (
            self.category not in SESSION_EVENTS or not self.schedule_verified
        ):
            raise ValueError("Only verified session facts may have calendar attestation")
        if self.contract_binding_verified and (
            self.category not in CONTRACT_EVENTS or not self.schedule_verified
        ):
            raise ValueError("Only verified contract events may claim contract binding")
        if self.bound_contract_id is not None and not _text(self.bound_contract_id):
            raise ValueError("Contract identity must not be blank")
        if self.bound_contract_expiry is not None and type(self.bound_contract_expiry) is not date:
            raise ValueError("Contract expiry must be a calendar date")
        if self.category not in CONTRACT_EVENTS and (
            self.bound_contract_id is not None
            or self.bound_contract_expiry is not None
            or self.contract_binding_verified
        ):
            raise ValueError("Non-contract events must not carry contract binding")
        if self.category in CONTRACT_EVENTS and (
            self.bound_contract_id is None
            or self.bound_contract_expiry is None
            or len(self.affected_markets) != 1
        ):
            raise ValueError("Contract events need one market and an explicit binding")
        if self.category in EXPIRY_EVENTS and (
            self.scheduled_at.astimezone(IST).date() != self.bound_contract_expiry
        ):
            raise ValueError("Expiry event must match the bound expiry in IST")
        if self.category == "ROLLOVER" and (
            self.scheduled_at.astimezone(IST).date() > self.bound_contract_expiry
        ):
            raise ValueError("Rollover event cannot follow its bound contract expiry")
        if (
            self.schedule_state == "CONFIRMED"
            and self.severity == "UNKNOWN"
            and self.schedule_verified
        ):
            raise ValueError("Verified confirmed event cannot invent its severity")
        if self.schedule_state != "CONFIRMED" and self.schedule_verified:
            raise ValueError("Cancelled, postponed or tentative schedule is not confirmed")
        _authority(self, "X7_EVENT_SOURCE_PROOF_V1")

    def sha256(self) -> str:
        return canonical_sha256(asdict(self))


@dataclass(frozen=True, slots=True)
class X7AdaptedEventV1:
    event: X7ScheduledEventV1
    source_record_id: str
    raw_record_sha256: str
    proof_sha256: str
    as_of: datetime
    max_age_seconds: float
    schedule_state: str
    temporal_relation: str
    reasons: tuple[str, ...]
    schema_version: str = "X7_ADAPTED_EVENT_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if (
            not isinstance(self.event, X7ScheduledEventV1)
            or not _text(self.source_record_id)
            or not _sha(self.raw_record_sha256)
            or not _sha(self.proof_sha256)
            or not _aware(self.as_of)
            or not _budget(self.max_age_seconds)
            or self.schedule_state not in STATES
            or self.temporal_relation not in {"UPCOMING", "AT_SCHEDULED_INSTANT", "PAST"}
            or type(self.reasons) is not tuple
            or any(not _text(reason) for reason in self.reasons)
            or len(set(self.reasons)) != len(self.reasons)
        ):
            raise ValueError("Invalid adapted event provenance")
        relation = (
            "UPCOMING"
            if self.event.scheduled_at > self.as_of
            else "PAST"
            if self.event.scheduled_at < self.as_of
            else "AT_SCHEDULED_INSTANT"
        )
        if self.temporal_relation != relation or self.event.observed_at > self.as_of:
            raise ValueError("Event chronology is inconsistent")
        if self.event.available_at is not None and self.event.available_at > self.as_of:
            raise ValueError("Future event publication is prohibited")
        if self.event.status == "AVAILABLE" and (
            self.schedule_state != "CONFIRMED" or self.reasons
        ):
            raise ValueError("Available event must be confirmed without caveats")
        if self.schedule_state != "CONFIRMED" and self.event.confirmed:
            raise ValueError("Non-final schedules cannot become confirmed")
        _authority(self, "X7_ADAPTED_EVENT_V1")

    def sha256(self) -> str:
        return canonical_sha256(asdict(self))


@dataclass(frozen=True, slots=True)
class X7EventBatchV1:
    market: str
    session_id: str
    capture_id: str
    as_of: datetime
    events: tuple[X7AdaptedEventV1, ...]
    input_sha256: str
    schema_version: str = "X7_EVENT_BATCH_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if (
            self.market not in MARKETS
            or not _text(self.session_id)
            or not _text(self.capture_id)
            or not _aware(self.as_of)
            or not _sha(self.input_sha256)
            or type(self.events) is not tuple
            or any(not isinstance(event, X7AdaptedEventV1) for event in self.events)
        ):
            raise ValueError("Invalid event batch")
        ordered = tuple(sorted(self.events, key=lambda x: (x.event.scheduled_at, x.event.event_id)))
        if self.events != ordered:
            raise ValueError("Events must be ordered by scheduled instant and event ID")
        if len({event.event.event_id for event in self.events}) != len(self.events):
            raise ValueError("Duplicate scheduled-event IDs")
        if len({event.source_record_id for event in self.events}) != len(self.events):
            raise ValueError("Duplicate source-record identity")
        if any(
            event.as_of != self.as_of or self.market not in event.event.affected_markets
            for event in self.events
        ):
            raise ValueError("Event does not apply to target market/capture")
        if self.events:
            budget = self.events[0].max_age_seconds
            if any(event.max_age_seconds != budget for event in self.events):
                raise ValueError("Batch must use the same freshness budget")
            expected = canonical_sha256(
                {
                    "market": self.market,
                    "session_id": self.session_id,
                    "capture_id": self.capture_id,
                    "as_of": self.as_of,
                    "raw_hashes": [event.raw_record_sha256 for event in self.events],
                    "proof_hashes": [event.proof_sha256 for event in self.events],
                    "max_age_seconds": budget,
                }
            )
            if self.input_sha256 != expected:
                raise ValueError("Batch input hash does not match retained evidence")
        _authority(self, "X7_EVENT_BATCH_V1")

    def sha256(self) -> str:
        return canonical_sha256(asdict(self))


def adapt_x7_scheduled_event_v1(
    *,
    raw_record: Mapping[str, object],
    proof: X7EventSourceProofV1,
    as_of: datetime,
    max_age_seconds: float,
) -> X7AdaptedEventV1:
    """Normalize exactly one supplied event; return unavailable rather than infer."""
    if not isinstance(raw_record, Mapping) or set(raw_record) != _RAW_KEYS:
        raise ValueError("Scheduled-event record must contain exact normalized fields")
    if not isinstance(proof, X7EventSourceProofV1) or not _aware(as_of):
        raise TypeError("Typed source proof and aware capture time are required")
    if not _budget(max_age_seconds):
        raise ValueError("Positive finite freshness budget is required")
    for field in _RAW_KEYS:
        if raw_record[field] != getattr(proof, field):
            raise ValueError(f"Event record conflicts with {field} proof")
    if (
        proof.observed_at > as_of
        or (proof.published_at is not None and proof.published_at > as_of)
        or (proof.available_at is not None and proof.available_at > as_of)
    ):
        raise ValueError("Future or not-yet-published scheduled events are prohibited")
    age = (as_of - proof.observed_at).total_seconds()
    reasons: list[str] = []
    if age > max_age_seconds:
        reasons.append("STALE_CALENDAR_RECORD")
    if proof.schedule_state != "CONFIRMED":
        reasons.append(f"SCHEDULE_{proof.schedule_state}")
    if not (
        proof.source_verified and proof.timestamp_semantics_verified and proof.schedule_verified
    ):
        reasons.append("SOURCE_OR_SCHEDULE_UNVERIFIED")
    if proof.category in SESSION_EVENTS and not proof.calendar_reference_verified:
        reasons.append("CANONICAL_SESSION_REFERENCE_UNVERIFIED")
    if proof.category in CONTRACT_EVENTS and not proof.contract_binding_verified:
        reasons.append("CONTRACT_EXPIRY_OR_ROLLOVER_BINDING_UNVERIFIED")
    if proof.severity == "UNKNOWN":
        reasons.append("SEVERITY_UNAVAILABLE")
    eligible = not reasons
    confirmed = (
        proof.schedule_state == "CONFIRMED"
        and proof.schedule_verified
        and proof.source_verified
        and proof.severity != "UNKNOWN"
        and (proof.category not in SESSION_EVENTS or proof.calendar_reference_verified)
        and (proof.category not in CONTRACT_EVENTS or proof.contract_binding_verified)
    )
    status = (
        "AVAILABLE"
        if eligible
        else "STALE"
        if confirmed and age > max_age_seconds
        else "UNAVAILABLE"
        if proof.schedule_state == "UNAVAILABLE"
        else "UNVERIFIED"
    )
    event = X7ScheduledEventV1(
        event_id=proof.event_id,
        category=proof.category,
        scheduled_at=proof.scheduled_at,
        affected_markets=proof.affected_markets,
        severity=proof.severity,
        source_id=proof.source_id,
        observed_at=proof.observed_at,
        published_at=proof.published_at,
        available_at=proof.available_at,
        source_verified=proof.source_verified,
        confirmed=confirmed,
        status=status,
    )
    return X7AdaptedEventV1(
        event=event,
        source_record_id=proof.source_record_id,
        raw_record_sha256=canonical_sha256(dict(raw_record)),
        proof_sha256=proof.sha256(),
        as_of=as_of,
        max_age_seconds=float(max_age_seconds),
        schedule_state=proof.schedule_state,
        temporal_relation=(
            "UPCOMING"
            if proof.scheduled_at > as_of
            else "PAST"
            if proof.scheduled_at < as_of
            else "AT_SCHEDULED_INSTANT"
        ),
        reasons=tuple(reasons),
    )


def adapt_x7_scheduled_event_batch_v1(
    *,
    market: str,
    session_id: str,
    capture_id: str,
    as_of: datetime,
    raw_records: tuple[Mapping[str, object], ...],
    proofs: tuple[X7EventSourceProofV1, ...],
    max_age_seconds: float,
) -> X7EventBatchV1:
    """Batch is point-in-time, market-scoped and deterministic, never a decision."""
    if market not in MARKETS or not _text(session_id) or not _text(capture_id):
        raise ValueError("Exact five-market, session and capture identity required")
    if not _aware(as_of) or not _budget(max_age_seconds):
        raise ValueError("Aware capture time and explicit freshness budget required")
    if (
        type(raw_records) is not tuple
        or type(proofs) is not tuple
        or len(raw_records) != len(proofs)
    ):
        raise ValueError("Exact one-to-one record/proof tuples are required")
    adapted = tuple(
        adapt_x7_scheduled_event_v1(
            raw_record=raw,
            proof=proof,
            as_of=as_of,
            max_age_seconds=max_age_seconds,
        )
        for raw, proof in zip(raw_records, proofs)
    )
    if any(market not in row.event.affected_markets for row in adapted):
        raise ValueError("Calendar event does not apply to target market")
    ordered = tuple(sorted(adapted, key=lambda x: (x.event.scheduled_at, x.event.event_id)))
    return X7EventBatchV1(
        market=market,
        session_id=session_id,
        capture_id=capture_id,
        as_of=as_of,
        events=ordered,
        input_sha256=canonical_sha256(
            {
                "market": market,
                "session_id": session_id,
                "capture_id": capture_id,
                "as_of": as_of,
                "raw_hashes": [x.raw_record_sha256 for x in ordered],
                "proof_hashes": [x.proof_sha256 for x in ordered],
                "max_age_seconds": float(max_age_seconds),
            }
        ),
    )
