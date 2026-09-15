"""Sanitized Task 9 Angel authentication/session proof contract."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import ClassVar

from services.contracts.task9_angel_capability_session_v1 import (
    Task9AngelSessionCredentialKind,
)


_SECRET_TERMS = (
    "api_key",
    "apikey",
    "password",
    "secret",
    "authorization",
    "totp",
    "jwt",
    "refresh_token",
    "feed_token",
    "access_token",
    "client_id",
    "pin",
    "cookie",
    "raw_payload",
    "raw_exception",
    "exception_text",
)


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(name)

    cleaned = value.strip()

    if any(
        item in cleaned.lower()
        for item in _SECRET_TERMS
    ):
        raise ValueError(
            f"{name} contains secret-like material"
        )

    return cleaned


def _aware(
    value: object,
    name: str,
) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)

    return value


def _messages(
    value: object,
    name: str,
) -> tuple[str, ...]:
    if type(value) is not tuple:
        raise TypeError(name)

    normalized = tuple(
        _text(item, name)
        for item in value
    )

    if len(set(normalized)) != len(
        normalized
    ):
        raise ValueError(name)

    return normalized


class Task9AngelAuthProbeStatus(
    str,
    Enum,
):
    READY = "READY"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class Task9AngelAuthSessionProofV1:
    SCHEMA_VERSION: ClassVar[str] = (
        "task9_angel_auth_session_proof.v1"
    )

    proof_id: str
    observed_at: datetime

    status: Task9AngelAuthProbeStatus

    credential_references_present: bool

    credential_kinds_confirmed: tuple[
        Task9AngelSessionCredentialKind,
        ...
    ]

    provider_code: str | None = None

    sanitized_reason: str | None = None

    incident_ref: str | None = None

    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False

    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "proof_id",
            _text(
                self.proof_id,
                "proof_id",
            ),
        )

        _aware(
            self.observed_at,
            "observed_at",
        )

        try:
            object.__setattr__(
                self,
                "status",
                Task9AngelAuthProbeStatus(
                    self.status
                ),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "status"
            ) from exc

        if type(
            self.credential_references_present
        ) is not bool:
            raise TypeError(
                "credential_references_present"
            )

        if type(
            self.credential_kinds_confirmed
        ) is not tuple:
            raise TypeError(
                "credential_kinds_confirmed"
            )

        try:
            credentials = tuple(
                Task9AngelSessionCredentialKind(
                    item
                )
                for item
                in self.credential_kinds_confirmed
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "credential_kinds_confirmed"
            ) from exc

        if len(set(credentials)) != len(
            credentials
        ):
            raise ValueError(
                "credential_kinds_confirmed"
            )

        object.__setattr__(
            self,
            "credential_kinds_confirmed",
            credentials,
        )

        if self.provider_code is not None:
            code = _text(
                self.provider_code,
                "provider_code",
            ).upper()

            if not (
                code.startswith("AG")
                or code.startswith("AB")
            ):
                raise ValueError(
                    "provider_code"
                )

            object.__setattr__(
                self,
                "provider_code",
                code,
            )

        for name in (
            "sanitized_reason",
            "incident_ref",
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

        if (
            self.execution_mode != "PAPER"
            or self.broker_order_submission is not False
            or self.live_execution_eligible is not False
        ):
            raise ValueError(
                "Task9 Angel auth proof must remain PAPER-only"
            )

        if (
            self.schema_version
            != self.SCHEMA_VERSION
        ):
            raise ValueError(
                "schema_version"
            )

        expected = (
            Task9AngelSessionCredentialKind.JWT,
            Task9AngelSessionCredentialKind.REFRESH,
            Task9AngelSessionCredentialKind.FEED,
        )

        if (
            self.status
            is Task9AngelAuthProbeStatus.READY
        ):
            if (
                self.credential_references_present
                is not True
            ):
                raise ValueError(
                    "READY requires credential references"
                )

            if credentials != expected:
                raise ValueError(
                    "READY requires JWT/REFRESH/FEED proof"
                )

            if (
                self.provider_code is not None
                or self.sanitized_reason
                is not None
            ):
                raise ValueError(
                    "READY cannot contain failure evidence"
                )

        else:
            if (
                self.provider_code is None
                and self.sanitized_reason is None
                and self.credential_references_present
            ):
                raise ValueError(
                    "FAILED requires sanitized failure evidence"
                )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": (
                self.schema_version
            ),
            "proof_id": self.proof_id,
            "observed_at": (
                self.observed_at.isoformat()
            ),
            "status": self.status.value,
            "credential_references_present": (
                self.credential_references_present
            ),
            "credential_kinds_confirmed": [
                item.value
                for item
                in self.credential_kinds_confirmed
            ],
            "provider_code": (
                self.provider_code
            ),
            "sanitized_reason": (
                self.sanitized_reason
            ),
            "incident_ref": (
                self.incident_ref
            ),
            "execution_mode": (
                self.execution_mode
            ),
            "broker_order_submission": (
                self.broker_order_submission
            ),
            "live_execution_eligible": (
                self.live_execution_eligible
            ),
        }
