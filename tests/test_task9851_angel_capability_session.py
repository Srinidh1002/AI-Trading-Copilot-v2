import pytest

from services.certification.task9_angel_capability_session_builder import (
    build_task9_angel_capability_session,
)
from services.contracts.task9_angel_capability_session_v1 import (
    Task9AngelCapability,
    Task9AngelCapabilitySessionV1,
    Task9AngelFailureDisposition,
    Task9AngelRequirement,
    Task9AngelSessionCredentialKind,
)
from services.contracts.task9_provider_capability_report_v1 import (
    Task9LiveProofStatus,
    Task9ProviderReadinessStatus,
    Task9ProviderSupportStatus,
)


def _authority():
    return build_task9_angel_capability_session()


def test_builder_is_offline_deterministic_and_paper_only():
    first = _authority()
    second = _authority()

    assert (
        type(first)
        is Task9AngelCapabilitySessionV1
    )
    assert first.to_dict() == second.to_dict()

    assert first.execution_mode == "PAPER"
    assert first.broker_order_submission is False
    assert first.live_execution_eligible is False
    assert first.account_wide_request_budget is True


def test_exact_session_credential_kinds_are_required():
    value = _authority()

    assert value.required_session_credentials == (
        Task9AngelSessionCredentialKind.JWT,
        Task9AngelSessionCredentialKind.REFRESH,
        Task9AngelSessionCredentialKind.FEED,
    )


def test_required_live_capabilities_are_pending_not_falsely_ready():
    value = _authority()

    required = tuple(
        state
        for state in value.capability_states
        if state.requirement
        is Task9AngelRequirement.REQUIRED
    )

    assert required
    assert all(
        state.live_proof_status
        is Task9LiveProofStatus.PENDING
        for state in required
    )
    assert all(
        state.readiness_status
        is Task9ProviderReadinessStatus.READY_PENDING_LIVE_PROOF
        for state in required
    )

    assert value.required_capabilities_ready is False


@pytest.mark.parametrize(
    "capability,market,exchange",
    (
        (
            Task9AngelCapability.NIFTY_SPOT_FULL,
            "NIFTY",
            "NSE",
        ),
        (
            Task9AngelCapability.SENSEX_SPOT_FULL,
            "SENSEX",
            "BSE",
        ),
        (
            Task9AngelCapability.NFO_OPTION_FULL,
            "NIFTY",
            "NFO",
        ),
        (
            Task9AngelCapability.BFO_OPTION_FULL,
            "SENSEX",
            "BFO",
        ),
    ),
)
def test_required_market_data_identity(
    capability,
    market,
    exchange,
):
    state = _authority().capability(
        capability
    )

    assert state.market == market
    assert state.exchange == exchange
    assert (
        state.requirement
        is Task9AngelRequirement.REQUIRED
    )


def test_nfo_greeks_supported_optional_pending_live_proof():
    state = _authority().capability(
        Task9AngelCapability.NFO_OPTION_GREEKS
    )

    assert state.market == "NIFTY"
    assert state.exchange == "NFO"

    assert (
        state.requirement
        is Task9AngelRequirement.OPTIONAL
    )
    assert (
        state.documentation_status
        is Task9ProviderSupportStatus.DOCUMENTED
    )
    assert (
        state.implementation_status
        is Task9ProviderSupportStatus.IMPLEMENTED
    )
    assert (
        state.live_proof_status
        is Task9LiveProofStatus.PENDING
    )


def test_bfo_greeks_explicitly_unsupported_and_nonblocking():
    state = _authority().capability(
        Task9AngelCapability.BFO_OPTION_GREEKS
    )

    assert state.market == "SENSEX"
    assert state.exchange == "BFO"

    assert (
        state.requirement
        is Task9AngelRequirement.OPTIONAL
    )
    assert (
        state.documentation_status
        is Task9ProviderSupportStatus.UNSUPPORTED
    )
    assert (
        state.readiness_status
        is Task9ProviderReadinessStatus.UNSUPPORTED
    )
    assert state.launch_ready is True


def test_india_vix_is_optional_pending_live_proof():
    state = _authority().capability(
        Task9AngelCapability.INDIA_VIX
    )

    assert state.market == "INDIA_VIX"
    assert state.exchange == "NSE"
    assert (
        state.requirement
        is Task9AngelRequirement.OPTIONAL
    )
    assert (
        state.live_proof_status
        is Task9LiveProofStatus.PENDING
    )
    assert state.launch_ready is True


def test_instrument_master_is_not_live_price_authority():
    state = _authority().capability(
        Task9AngelCapability.INSTRUMENT_MASTER
    )

    assert state.freshness_policy_ref == (
        "task9-angel-daily-instrument-master-freshness.v1"
    )
    assert any(
        "not live price authority"
        in note
        for note in state.notes
    )


def test_request_budget_is_single_required_authority():
    state = _authority().capability(
        Task9AngelCapability.REQUEST_BUDGET
    )

    assert (
        state.requirement
        is Task9AngelRequirement.REQUIRED
    )
    assert (
        "MarketDataRequestController"
        in state.endpoint_policy_ref
    )
    assert any(
        "account-wide"
        in note
        for note in state.notes
    )


@pytest.mark.parametrize(
    "code",
    (
        "AG8001",
        "AG8003",
        "AB8050",
    ),
)
def test_fatal_auth_codes(code):
    assert (
        _authority()
        .failure_codes
        .disposition_for(code)
        is Task9AngelFailureDisposition.FATAL
    )


@pytest.mark.parametrize(
    "code",
    (
        "AG8002",
        "AB8051",
        "AB1010",
        "AB1011",
        "AB2001",
    ),
)
def test_retryable_session_or_provider_codes(code):
    assert (
        _authority()
        .failure_codes
        .disposition_for(code)
        is Task9AngelFailureDisposition.RETRYABLE
    )


def test_unknown_provider_code_is_not_silently_classified():
    assert (
        _authority()
        .failure_codes
        .disposition_for("UNKNOWN")
        is None
    )


def test_no_secret_material_is_serialized():
    raw = repr(
        _authority().to_dict()
    ).lower()

    for forbidden in (
        "api_key",
        "apikey",
        "password",
        "authorization",
        "totp",
    ):
        assert forbidden not in raw


def test_capability_identities_are_complete_and_unique():
    value = _authority()

    expected = {
        Task9AngelCapability.AUTH_SESSION,
        Task9AngelCapability.INSTRUMENT_MASTER,
        Task9AngelCapability.NIFTY_SPOT_FULL,
        Task9AngelCapability.SENSEX_SPOT_FULL,
        Task9AngelCapability.NFO_OPTION_FULL,
        Task9AngelCapability.BFO_OPTION_FULL,
        Task9AngelCapability.NFO_OPTION_GREEKS,
        Task9AngelCapability.BFO_OPTION_GREEKS,
        Task9AngelCapability.INDIA_VIX,
        Task9AngelCapability.REQUEST_BUDGET,
    }

    actual = {
        state.capability
        for state in value.capability_states
    }

    assert actual == expected
    assert len(value.capability_states) == len(
        expected
    )
