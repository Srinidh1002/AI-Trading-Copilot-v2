from datetime import date, datetime, timezone
import inspect

from services.broker.angel_client import (
    AngelMarketDataClient,
)
from services.certification.task9_angel_auth_session_proof_producer import (
    produce_task9_angel_auth_session_proof,
)
from services.certification.task9_angel_auth_session_readiness import (
    Task9AngelAuthReadinessStatus,
    evaluate_task9_angel_auth_session,
)
from services.certification.task9_angel_capability_session_builder import (
    build_task9_angel_capability_session,
)
from services.contracts.task9_angel_auth_session_proof_v1 import (
    Task9AngelAuthProbeStatus,
)
from services.contracts.task9_angel_capability_session_v1 import (
    Task9AngelSessionCredentialKind,
)


NOW = datetime(
    2026,
    8,
    17,
    6,
    30,
    tzinfo=timezone.utc,
)

TODAY = date(
    2026,
    8,
    17,
)


def _client():
    client = object.__new__(
        AngelMarketDataClient
    )

    client.authenticated = True

    # Deliberately opaque. The producer must never
    # inspect credential/token contents.
    client.session = {
        "opaque": "established-session-reference"
    }

    client._authenticated_on = TODAY
    client._current_date = lambda: TODAY

    return client


def test_established_same_day_session_produces_ready_proof():
    proof = (
        produce_task9_angel_auth_session_proof(
            client=_client(),
            observed_at=NOW,
        )
    )

    assert (
        proof.status
        is Task9AngelAuthProbeStatus.READY
    )

    assert (
        proof.credential_references_present
        is True
    )

    assert proof.credential_kinds_confirmed == (
        Task9AngelSessionCredentialKind.JWT,
        Task9AngelSessionCredentialKind.REFRESH,
        Task9AngelSessionCredentialKind.FEED,
    )

    assert proof.provider_code is None
    assert proof.sanitized_reason is None


def test_ready_proof_passes_existing_auth_readiness():
    proof = (
        produce_task9_angel_auth_session_proof(
            client=_client(),
            observed_at=NOW,
        )
    )

    result = (
        evaluate_task9_angel_auth_session(
            authority=(
                build_task9_angel_capability_session()
            ),
            proof=proof,
        )
    )

    assert (
        result.status
        is Task9AngelAuthReadinessStatus.READY
    )


def test_unauthenticated_client_fails_closed():
    client = _client()
    client.authenticated = False

    proof = (
        produce_task9_angel_auth_session_proof(
            client=client,
            observed_at=NOW,
        )
    )

    assert (
        proof.status
        is Task9AngelAuthProbeStatus.FAILED
    )
    assert (
        proof.credential_references_present
        is False
    )
    assert (
        proof.credential_kinds_confirmed
        == ()
    )
    assert proof.sanitized_reason == (
        "ANGEL_SESSION_NOT_AUTHENTICATED"
    )


def test_missing_session_reference_fails_closed():
    client = _client()
    client.session = None

    proof = (
        produce_task9_angel_auth_session_proof(
            client=client,
            observed_at=NOW,
        )
    )

    assert (
        proof.status
        is Task9AngelAuthProbeStatus.FAILED
    )
    assert proof.sanitized_reason == (
        "ANGEL_AUTHENTICATED_SESSION_REFERENCE_MISSING"
    )


def test_missing_authenticated_date_fails_closed():
    client = _client()
    client._authenticated_on = None

    proof = (
        produce_task9_angel_auth_session_proof(
            client=client,
            observed_at=NOW,
        )
    )

    assert (
        proof.status
        is Task9AngelAuthProbeStatus.FAILED
    )
    assert proof.sanitized_reason == (
        "ANGEL_AUTHENTICATED_DATE_MISSING"
    )


def test_prior_trading_date_session_fails_closed():
    client = _client()

    client._authenticated_on = date(
        2026,
        8,
        16,
    )

    proof = (
        produce_task9_angel_auth_session_proof(
            client=client,
            observed_at=NOW,
        )
    )

    assert (
        proof.status
        is Task9AngelAuthProbeStatus.FAILED
    )

    assert proof.sanitized_reason == (
        "ANGEL_AUTHENTICATED_SESSION_DATE_MISMATCH"
    )


def test_producer_does_not_require_real_token_fields():
    client = _client()

    # If the producer searched jwtToken / refreshToken /
    # feedToken this would fail. Successful proof therefore
    # confirms it relies on the client's established invariant.
    proof = (
        produce_task9_angel_auth_session_proof(
            client=client,
            observed_at=NOW,
        )
    )

    assert (
        proof.status
        is Task9AngelAuthProbeStatus.READY
    )


def test_producer_has_no_login_or_provider_dependencies():
    parameters = inspect.signature(
        produce_task9_angel_auth_session_proof
    ).parameters

    assert tuple(parameters) == (
        "client",
        "observed_at",
    )


def test_auth_proof_remains_paper_only():
    proof = (
        produce_task9_angel_auth_session_proof(
            client=_client(),
            observed_at=NOW,
        )
    )

    assert proof.execution_mode == "PAPER"
    assert (
        proof.broker_order_submission
        is False
    )
    assert (
        proof.live_execution_eligible
        is False
    )


def test_serialized_proof_contains_no_session_material():
    proof = (
        produce_task9_angel_auth_session_proof(
            client=_client(),
            observed_at=NOW,
        )
    )

    serialized = str(
        proof.to_dict()
    )

    assert (
        "established-session-reference"
        not in serialized
    )
    assert "jwtToken" not in serialized
    assert "refreshToken" not in serialized
    assert "feedToken" not in serialized
