"""Task 9 provider-selection authority for optional external context.

No provider integration is selected in the current Task 9 build.

This contract makes that state explicit and durable instead of representing
missing external evidence as a fabricated neutral score.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Task9ExternalProviderDomain(str, Enum):
    MARKET_BREADTH = "MARKET_BREADTH"
    FII_DII = "FII_DII"
    ECONOMIC_EVENTS = "ECONOMIC_EVENTS"
    GLOBAL_MARKETS = "GLOBAL_MARKETS"
    STRUCTURED_NEWS = "STRUCTURED_NEWS"


class Task9ExternalProviderStatus(str, Enum):
    FEATURE_DISABLED = "FEATURE_DISABLED"
    PROVIDER_NOT_SELECTED = "PROVIDER_NOT_SELECTED"
    UNAVAILABLE = "UNAVAILABLE"
    AVAILABLE = "AVAILABLE"


class Task9ExternalProviderFreshness(str, Enum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"
    FRESH = "FRESH"
    STALE = "STALE"


class Task9ExternalCanonicalRole(str, Enum):
    OPTIONAL_CONFIRMATION = "OPTIONAL_CONFIRMATION"
    OPTIONAL_CONTRADICTION = "OPTIONAL_CONTRADICTION"
    OPTIONAL_ENTRY_RESTRICTION = "OPTIONAL_ENTRY_RESTRICTION"
    OPTIONAL_CONTEXT = "OPTIONAL_CONTEXT"


class Task9ExternalFailureSemantic(str, Enum):
    OPTIONAL_UNAVAILABLE = "OPTIONAL_UNAVAILABLE"
    WARNING = "WARNING"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True, slots=True)
class Task9ExternalProviderStateV1:
    state_id: str
    observed_at: datetime
    domain: Task9ExternalProviderDomain
    status: Task9ExternalProviderStatus
    availability: bool
    freshness: Task9ExternalProviderFreshness
    canonical_role: Task9ExternalCanonicalRole
    failure_semantic: Task9ExternalFailureSemantic
    provider_name: str | None
    provider_selected: bool
    network_calls_allowed: bool
    reason_code: str
    provenance: tuple[str, ...]

    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False
    schema_version: str = "task9_external_provider_state.v1"

    def __post_init__(self):
        if (
            type(self.state_id) is not str
            or not self.state_id.strip()
        ):
            raise ValueError("state_id")

        if (
            not isinstance(self.observed_at, datetime)
            or self.observed_at.tzinfo is None
            or self.observed_at.utcoffset() is None
        ):
            raise ValueError("observed_at")

        object.__setattr__(
            self,
            "domain",
            Task9ExternalProviderDomain(
                self.domain
            ),
        )

        object.__setattr__(
            self,
            "status",
            Task9ExternalProviderStatus(
                self.status
            ),
        )

        object.__setattr__(
            self,
            "freshness",
            Task9ExternalProviderFreshness(
                self.freshness
            ),
        )

        object.__setattr__(
            self,
            "canonical_role",
            Task9ExternalCanonicalRole(
                self.canonical_role
            ),
        )

        object.__setattr__(
            self,
            "failure_semantic",
            Task9ExternalFailureSemantic(
                self.failure_semantic
            ),
        )

        if type(self.availability) is not bool:
            raise ValueError("availability")

        if type(self.provider_selected) is not bool:
            raise ValueError("provider_selected")

        if type(self.network_calls_allowed) is not bool:
            raise ValueError("network_calls_allowed")

        if (
            self.provider_name is not None
            and (
                type(self.provider_name) is not str
                or not self.provider_name.strip()
            )
        ):
            raise ValueError("provider_name")

        if (
            type(self.reason_code) is not str
            or not self.reason_code.strip()
        ):
            raise ValueError("reason_code")

        if (
            not isinstance(self.provenance, tuple)
            or not self.provenance
            or any(
                type(value) is not str
                or not value.strip()
                for value in self.provenance
            )
        ):
            raise ValueError("provenance")

        if self.status in {
            Task9ExternalProviderStatus.FEATURE_DISABLED,
            Task9ExternalProviderStatus.PROVIDER_NOT_SELECTED,
            Task9ExternalProviderStatus.UNAVAILABLE,
        }:
            if self.availability is not False:
                raise ValueError(
                    "unavailable provider state cannot be available"
                )

        if (
            self.status
            is Task9ExternalProviderStatus.PROVIDER_NOT_SELECTED
        ):
            if (
                self.provider_selected is not False
                or self.provider_name is not None
                or self.network_calls_allowed is not False
                or self.freshness
                is not Task9ExternalProviderFreshness.NOT_APPLICABLE
                or self.failure_semantic
                is not Task9ExternalFailureSemantic.OPTIONAL_UNAVAILABLE
            ):
                raise ValueError(
                    "provider-not-selected invariant"
                )

        if (
            self.status
            is Task9ExternalProviderStatus.AVAILABLE
        ):
            if (
                self.availability is not True
                or self.provider_selected is not True
                or self.provider_name is None
            ):
                raise ValueError(
                    "available provider invariant"
                )

        if (
            self.execution_mode != "PAPER"
            or self.broker_order_submission is not False
            or self.live_execution_eligible is not False
        ):
            raise ValueError(
                "Task9 external provider state must remain PAPER-only"
            )

        if (
            self.schema_version
            != "task9_external_provider_state.v1"
        ):
            raise ValueError("schema_version")

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "state_id": self.state_id,
            "observed_at": self.observed_at.isoformat(),
            "domain": self.domain.value,
            "status": self.status.value,
            "availability": self.availability,
            "freshness": self.freshness.value,
            "canonical_role": self.canonical_role.value,
            "failure_semantic": (
                self.failure_semantic.value
            ),
            "provider_name": self.provider_name,
            "provider_selected": (
                self.provider_selected
            ),
            "network_calls_allowed": (
                self.network_calls_allowed
            ),
            "reason_code": self.reason_code,
            "provenance": list(self.provenance),
            "execution_mode": self.execution_mode,
            "broker_order_submission": (
                self.broker_order_submission
            ),
            "live_execution_eligible": (
                self.live_execution_eligible
            ),
        }


@dataclass(frozen=True, slots=True)
class Task9ExternalProviderSnapshotV1:
    snapshot_id: str
    observed_at: datetime
    states: tuple[Task9ExternalProviderStateV1, ...]

    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False
    schema_version: str = (
        "task9_external_provider_snapshot.v1"
    )

    def __post_init__(self):
        if (
            type(self.snapshot_id) is not str
            or not self.snapshot_id.strip()
        ):
            raise ValueError("snapshot_id")

        if (
            not isinstance(self.observed_at, datetime)
            or self.observed_at.tzinfo is None
            or self.observed_at.utcoffset() is None
        ):
            raise ValueError("observed_at")

        if (
            not isinstance(self.states, tuple)
            or len(self.states)
            != len(Task9ExternalProviderDomain)
            or any(
                type(value)
                is not Task9ExternalProviderStateV1
                for value in self.states
            )
        ):
            raise ValueError("states")

        domains = tuple(
            state.domain
            for state in self.states
        )

        if (
            set(domains)
            != set(Task9ExternalProviderDomain)
            or len(domains)
            != len(set(domains))
        ):
            raise ValueError(
                "external provider domains incomplete"
            )

        if domains != tuple(
            sorted(
                domains,
                key=lambda item: item.value,
            )
        ):
            raise ValueError(
                "external provider domains must be ordered"
            )

        if any(
            state.observed_at != self.observed_at
            for state in self.states
        ):
            raise ValueError(
                "external provider snapshot boundary"
            )

        if (
            self.execution_mode != "PAPER"
            or self.broker_order_submission is not False
            or self.live_execution_eligible is not False
        ):
            raise ValueError(
                "Task9 external snapshot must remain PAPER-only"
            )

    def for_domain(
        self,
        domain: Task9ExternalProviderDomain | str,
    ) -> Task9ExternalProviderStateV1:
        expected = Task9ExternalProviderDomain(
            domain
        )

        return next(
            state
            for state in self.states
            if state.domain is expected
        )

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "snapshot_id": self.snapshot_id,
            "observed_at": self.observed_at.isoformat(),
            "states": [
                state.to_dict()
                for state in self.states
            ],
            "execution_mode": self.execution_mode,
            "broker_order_submission": (
                self.broker_order_submission
            ),
            "live_execution_eligible": (
                self.live_execution_eligible
            ),
        }


__all__ = (
    "Task9ExternalCanonicalRole",
    "Task9ExternalFailureSemantic",
    "Task9ExternalProviderDomain",
    "Task9ExternalProviderFreshness",
    "Task9ExternalProviderSnapshotV1",
    "Task9ExternalProviderStateV1",
    "Task9ExternalProviderStatus",
)
