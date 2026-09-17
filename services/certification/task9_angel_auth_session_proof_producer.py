"""Task 9 Angel auth-session proof from established client state.

This module performs no login, refresh, profile request, or provider call.

AngelMarketDataClient.login() already validates the required JWT,
refresh, and feed credential references before setting its authenticated
state. This producer therefore projects only that established,
same-trading-date state into the non-secret Task 9 proof contract.

No credential value is read, copied, persisted, or logged.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from services.broker.angel_client import (
    AngelMarketDataClient,
)
from services.contracts.task9_angel_auth_session_proof_v1 import (
    Task9AngelAuthProbeStatus,
    Task9AngelAuthSessionProofV1,
)
from services.contracts.task9_angel_capability_session_v1 import (
    Task9AngelSessionCredentialKind,
)


_CONFIRMED_CREDENTIAL_KINDS = (
    Task9AngelSessionCredentialKind.JWT,
    Task9AngelSessionCredentialKind.REFRESH,
    Task9AngelSessionCredentialKind.FEED,
)


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


def produce_task9_angel_auth_session_proof(
    *,
    client: AngelMarketDataClient,
    observed_at: datetime,
) -> Task9AngelAuthSessionProofV1:
    """Project the already-established Angel auth state into Task 9 proof."""

    if type(client) is not AngelMarketDataClient:
        raise TypeError("client")

    observed_at = _aware(
        observed_at,
        "observed_at",
    )

    authenticated = (
        client.authenticated is True
    )

    session_present = isinstance(
        client.session,
        Mapping,
    )

    authenticated_on = getattr(
        client,
        "_authenticated_on",
        None,
    )

    current_date_reader = getattr(
        client,
        "_current_date",
        None,
    )

    same_trading_date = False

    if (
        authenticated
        and session_present
        and authenticated_on is not None
        and callable(current_date_reader)
    ):
        try:
            same_trading_date = (
                authenticated_on
                == current_date_reader()
            )
        except Exception:
            same_trading_date = False

    ready = (
        authenticated
        and session_present
        and same_trading_date
    )

    if ready:
        return Task9AngelAuthSessionProofV1(
            proof_id=(
                "task9-angel-auth-session:"
                f"{observed_at.isoformat()}"
            ),
            observed_at=observed_at,
            status=Task9AngelAuthProbeStatus.READY,
            credential_references_present=True,
            credential_kinds_confirmed=(
                _CONFIRMED_CREDENTIAL_KINDS
            ),
            provider_code=None,
            sanitized_reason=None,
            incident_ref=None,
            execution_mode="PAPER",
            broker_order_submission=False,
            live_execution_eligible=False,
        )

    if not authenticated:
        reason = (
            "ANGEL_SESSION_NOT_AUTHENTICATED"
        )
    elif not session_present:
        reason = (
            "ANGEL_AUTHENTICATED_SESSION_REFERENCE_MISSING"
        )
    elif authenticated_on is None:
        reason = (
            "ANGEL_AUTHENTICATED_DATE_MISSING"
        )
    elif not callable(current_date_reader):
        reason = (
            "ANGEL_TRADING_DATE_AUTHORITY_MISSING"
        )
    else:
        reason = (
            "ANGEL_AUTHENTICATED_SESSION_DATE_MISMATCH"
        )

    return Task9AngelAuthSessionProofV1(
        proof_id=(
            "task9-angel-auth-session:"
            f"failed:"
            f"{observed_at.isoformat()}"
        ),
        observed_at=observed_at,
        status=Task9AngelAuthProbeStatus.FAILED,
        credential_references_present=False,
        credential_kinds_confirmed=(),
        provider_code=None,
        sanitized_reason=reason,
        incident_ref=None,
        execution_mode="PAPER",
        broker_order_submission=False,
        live_execution_eligible=False,
    )


__all__ = (
    "produce_task9_angel_auth_session_proof",
)
