"""Immutable, non-secret Task 9 Angel capability/session authority."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import ClassVar

from services.contracts.task9_provider_capability_report_v1 import (
    Task9LiveProofStatus,
    Task9ProviderReadinessStatus,
    Task9ProviderSupportStatus,
)


_FORBIDDEN = (
    "api_key",
    "apikey",
    "password",
    "secret",
    "authorization",
    "totp",
    "client_id",
    "pin",
)


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(name)
    cleaned = value.strip()
    lowered = cleaned.lower()
    if any(term in lowered for term in _FORBIDDEN):
        raise ValueError(f"{name} contains secret-like material")
    return cleaned


def _codes(
    value: object,
    name: str,
) -> tuple[str, ...]:
    if type(value) is not tuple:
        raise TypeError(name)

    normalized = tuple(
        _text(item, name).upper()
        for item in value
    )
    if len(set(normalized)) != len(normalized):
        raise ValueError(name)
    return normalized


class Task9AngelCapability(str, Enum):
    AUTH_SESSION = "AUTH_SESSION"
    INSTRUMENT_MASTER = "INSTRUMENT_MASTER"

    NIFTY_SPOT_FULL = "NIFTY_SPOT_FULL"
    SENSEX_SPOT_FULL = "SENSEX_SPOT_FULL"

    NFO_OPTION_FULL = "NFO_OPTION_FULL"
    BFO_OPTION_FULL = "BFO_OPTION_FULL"

    NFO_OPTION_GREEKS = "NFO_OPTION_GREEKS"
    BFO_OPTION_GREEKS = "BFO_OPTION_GREEKS"

    INDIA_VIX = "INDIA_VIX"

    REQUEST_BUDGET = "REQUEST_BUDGET"


class Task9AngelRequirement(str, Enum):
    REQUIRED = "REQUIRED"
    OPTIONAL = "OPTIONAL"


class Task9AngelSessionCredentialKind(str, Enum):
    JWT = "JWT"
    REFRESH = "REFRESH"
    FEED = "FEED"


class Task9AngelFailureDisposition(str, Enum):
    FATAL = "FATAL"
    RETRYABLE = "RETRYABLE"


@dataclass(frozen=True, slots=True)
class Task9AngelFailureCodeSetV1:
    fatal_codes: tuple[str, ...]
    retryable_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "fatal_codes",
            _codes(
                self.fatal_codes,
                "fatal_codes",
            ),
        )
        object.__setattr__(
            self,
            "retryable_codes",
            _codes(
                self.retryable_codes,
                "retryable_codes",
            ),
        )

        if set(self.fatal_codes) & set(
            self.retryable_codes
        ):
            raise ValueError(
                "Angel failure code classification overlaps"
            )

    def disposition_for(
        self,
        code: str,
    ) -> Task9AngelFailureDisposition | None:
        normalized = _text(
            code,
            "code",
        ).upper()

        if normalized in self.fatal_codes:
            return Task9AngelFailureDisposition.FATAL

        if normalized in self.retryable_codes:
            return Task9AngelFailureDisposition.RETRYABLE

        return None

    def to_dict(self) -> dict[str, object]:
        return {
            "fatal_codes": list(
                self.fatal_codes
            ),
            "retryable_codes": list(
                self.retryable_codes
            ),
        }


@dataclass(frozen=True, slots=True)
class Task9AngelCapabilityStateV1:
    capability: Task9AngelCapability
    requirement: Task9AngelRequirement

    market: str | None
    exchange: str | None

    documentation_status: Task9ProviderSupportStatus
    implementation_status: Task9ProviderSupportStatus
    live_proof_status: Task9LiveProofStatus
    readiness_status: Task9ProviderReadinessStatus

    endpoint_policy_ref: str | None = None
    freshness_policy_ref: str | None = None

    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        try:
            object.__setattr__(
                self,
                "capability",
                Task9AngelCapability(
                    self.capability
                ),
            )
            object.__setattr__(
                self,
                "requirement",
                Task9AngelRequirement(
                    self.requirement
                ),
            )
            object.__setattr__(
                self,
                "documentation_status",
                Task9ProviderSupportStatus(
                    self.documentation_status
                ),
            )
            object.__setattr__(
                self,
                "implementation_status",
                Task9ProviderSupportStatus(
                    self.implementation_status
                ),
            )
            object.__setattr__(
                self,
                "live_proof_status",
                Task9LiveProofStatus(
                    self.live_proof_status
                ),
            )
            object.__setattr__(
                self,
                "readiness_status",
                Task9ProviderReadinessStatus(
                    self.readiness_status
                ),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Angel capability state"
            ) from exc

        if (
            self.market is None
        ) != (
            self.exchange is None
        ):
            raise ValueError(
                "market/exchange"
            )

        if self.market is not None:
            object.__setattr__(
                self,
                "market",
                _text(
                    self.market,
                    "market",
                ).upper(),
            )
            object.__setattr__(
                self,
                "exchange",
                _text(
                    self.exchange,
                    "exchange",
                ).upper(),
            )

        for name in (
            "endpoint_policy_ref",
            "freshness_policy_ref",
        ):
            value = getattr(
                self,
                name,
            )
            if value is not None:
                object.__setattr__(
                    self,
                    name,
                    _text(
                        value,
                        name,
                    ),
                )

        if type(self.notes) is not tuple:
            raise TypeError("notes")

        notes = tuple(
            _text(
                item,
                "notes",
            )
            for item in self.notes
        )
        if len(set(notes)) != len(notes):
            raise ValueError("notes")
        object.__setattr__(
            self,
            "notes",
            notes,
        )

        if (
            self.readiness_status
            is Task9ProviderReadinessStatus.READY
            and self.live_proof_status
            is not Task9LiveProofStatus.PROVEN
        ):
            raise ValueError(
                "READY requires live proof"
            )

        if (
            self.requirement
            is Task9AngelRequirement.REQUIRED
            and self.readiness_status
            in {
                Task9ProviderReadinessStatus.UNAVAILABLE_OPTIONAL,
                Task9ProviderReadinessStatus.UNSUPPORTED,
                Task9ProviderReadinessStatus.PROVIDER_NOT_SELECTED,
                Task9ProviderReadinessStatus.DISABLED,
                Task9ProviderReadinessStatus.NOT_APPLICABLE,
            }
        ):
            raise ValueError(
                "required Angel capability unavailable"
            )

    @property
    def launch_ready(self) -> bool:
        if (
            self.requirement
            is Task9AngelRequirement.OPTIONAL
        ):
            return True

        return (
            self.readiness_status
            is Task9ProviderReadinessStatus.READY
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "capability": self.capability.value,
            "requirement": self.requirement.value,
            "market": self.market,
            "exchange": self.exchange,
            "documentation_status": (
                self.documentation_status.value
            ),
            "implementation_status": (
                self.implementation_status.value
            ),
            "live_proof_status": (
                self.live_proof_status.value
            ),
            "readiness_status": (
                self.readiness_status.value
            ),
            "endpoint_policy_ref": (
                self.endpoint_policy_ref
            ),
            "freshness_policy_ref": (
                self.freshness_policy_ref
            ),
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class Task9AngelCapabilitySessionV1:
    SCHEMA_VERSION: ClassVar[str] = (
        "task9_angel_capability_session.v1"
    )

    capability_states: tuple[
        Task9AngelCapabilityStateV1,
        ...
    ]

    required_session_credentials: tuple[
        Task9AngelSessionCredentialKind,
        ...
    ]

    failure_codes: Task9AngelFailureCodeSetV1

    account_wide_request_budget: bool

    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False

    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if type(self.capability_states) is not tuple:
            raise TypeError(
                "capability_states"
            )

        if any(
            type(item)
            is not Task9AngelCapabilityStateV1
            for item in self.capability_states
        ):
            raise TypeError(
                "capability_states"
            )

        identities = tuple(
            (
                item.capability,
                item.market,
                item.exchange,
            )
            for item in self.capability_states
        )

        if len(set(identities)) != len(
            identities
        ):
            raise ValueError(
                "duplicate Angel capability"
            )

        ordered = tuple(
            sorted(
                self.capability_states,
                key=lambda item: (
                    item.capability.value,
                    item.market or "",
                    item.exchange or "",
                ),
            )
        )
        if ordered != self.capability_states:
            raise ValueError(
                "Angel capabilities must be deterministic"
            )

        if (
            type(
                self.required_session_credentials
            )
            is not tuple
        ):
            raise TypeError(
                "required_session_credentials"
            )

        credentials = tuple(
            Task9AngelSessionCredentialKind(
                item
            )
            for item
            in self.required_session_credentials
        )

        expected_credentials = (
            Task9AngelSessionCredentialKind.JWT,
            Task9AngelSessionCredentialKind.REFRESH,
            Task9AngelSessionCredentialKind.FEED,
        )

        if credentials != expected_credentials:
            raise ValueError(
                "Angel session credential requirements"
            )

        object.__setattr__(
            self,
            "required_session_credentials",
            credentials,
        )

        if (
            type(self.failure_codes)
            is not Task9AngelFailureCodeSetV1
        ):
            raise TypeError(
                "failure_codes"
            )

        if (
            self.account_wide_request_budget
            is not True
        ):
            raise ValueError(
                "Angel request budget must be account-wide"
            )

        if (
            self.execution_mode != "PAPER"
            or self.broker_order_submission is not False
            or self.live_execution_eligible is not False
        ):
            raise ValueError(
                "Task9 Angel authority must remain PAPER-only"
            )

        if self.schema_version != self.SCHEMA_VERSION:
            raise ValueError(
                "schema_version"
            )

    @property
    def required_capabilities_ready(
        self,
    ) -> bool:
        return all(
            state.launch_ready
            for state in self.capability_states
        )

    @property
    def pending_live_proof_capabilities(
        self,
    ) -> tuple[str, ...]:
        return tuple(
            state.capability.value
            for state in self.capability_states
            if (
                state.live_proof_status
                is Task9LiveProofStatus.PENDING
            )
        )

    def capability(
        self,
        capability: Task9AngelCapability,
    ) -> Task9AngelCapabilityStateV1:
        normalized = Task9AngelCapability(
            capability
        )
        matches = tuple(
            state
            for state in self.capability_states
            if state.capability is normalized
        )

        if len(matches) != 1:
            raise ValueError(
                "Angel capability unavailable"
            )

        return matches[0]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "capability_states": [
                state.to_dict()
                for state
                in self.capability_states
            ],
            "required_session_credentials": [
                item.value
                for item
                in self.required_session_credentials
            ],
            "failure_codes": (
                self.failure_codes.to_dict()
            ),
            "account_wide_request_budget": (
                self.account_wide_request_budget
            ),
            "execution_mode": self.execution_mode,
            "broker_order_submission": (
                self.broker_order_submission
            ),
            "live_execution_eligible": (
                self.live_execution_eligible
            ),
        }
