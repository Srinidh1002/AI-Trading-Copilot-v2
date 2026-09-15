from dataclasses import replace
from datetime import datetime
from zoneinfo import ZoneInfo

from services.certification.task9_angel_capability_session_builder import (
    build_task9_angel_capability_session,
)
from services.certification.task9_angel_live_proof_bundle import (
    Task9AngelLiveProofBundleV1,
    project_task9_angel_live_proof_bundle,
)
from services.contracts.task9_angel_auth_session_proof_v1 import (
    Task9AngelAuthProbeStatus,
    Task9AngelAuthSessionProofV1,
)
from services.contracts.task9_angel_capability_session_v1 import (
    Task9AngelSessionCredentialKind,
)
from services.contracts.task9_angel_greeks_proof_v1 import (
    Task9AngelGreeksProbeStatus,
    Task9AngelGreeksProofV1,
)
from services.contracts.task9_angel_india_vix_proof_v1 import (
    Task9AngelIndiaVixProbeStatus,
    Task9AngelIndiaVixProofV1,
)
from services.contracts.task9_angel_instrument_master_proof_v1 import (
    Task9AngelInstrumentMasterProbeStatus,
    Task9AngelInstrumentMasterProofV1,
)
from services.contracts.task9_angel_option_full_proof_v1 import (
    Task9AngelOptionFullProbeStatus,
    Task9AngelOptionFullProofV1,
)
from services.contracts.task9_angel_request_budget_proof_v1 import (
    Task9AngelRequestBudgetProbeStatus,
    Task9AngelRequestBudgetProofV1,
)
from services.contracts.task9_angel_spot_full_proof_v1 import (
    Task9AngelSpotFullProbeStatus,
    Task9AngelSpotFullProofV1,
)
from services.contracts.task9_provider_capability_report_v1 import (
    Task9ProviderCapability,
    Task9ProviderFamily,
    Task9ProviderReadinessStatus,
)
from tests.test_task9_runtime_config_snapshot_v1 import (
    _config,
)


NOW = datetime(
    2026,
    8,
    17,
    12,
    0,
    tzinfo=ZoneInfo("Asia/Kolkata"),
)


def _auth():
    return Task9AngelAuthSessionProofV1(
        proof_id="task9865a7-auth",
        observed_at=NOW,
        status=Task9AngelAuthProbeStatus.READY,
        credential_references_present=True,
        credential_kinds_confirmed=(
            Task9AngelSessionCredentialKind.JWT,
            Task9AngelSessionCredentialKind.REFRESH,
            Task9AngelSessionCredentialKind.FEED,
        ),
    )


def _master():
    return Task9AngelInstrumentMasterProofV1(
        proof_id="task9865a7-master",
        observed_at=NOW,
        status=(
            Task9AngelInstrumentMasterProbeStatus.AVAILABLE
        ),
        fetched_at=NOW,
        record_count=100,
        nifty_nfo_identity_present=True,
        sensex_bfo_identity_present=True,
        source_ref="angel-openapi-scrip-master",
    )


def _spot(
    market,
    exchange,
    token,
):
    return Task9AngelSpotFullProofV1(
        proof_id=f"task9865a7-spot-{market.lower()}",
        observed_at=NOW,
        market=market,
        exchange=exchange,
        token=token,
        status=Task9AngelSpotFullProbeStatus.AVAILABLE,
        provider_timestamp=NOW,
        ltp=25000.0 if market == "NIFTY" else 80000.0,
        identity_verified=True,
        source_ref="angel-spot-full",
    )


def _option(
    market,
    exchange,
):
    return Task9AngelOptionFullProofV1(
        proof_id=f"task9865a7-option-{market.lower()}",
        observed_at=NOW,
        market=market,
        exchange=exchange,
        status=Task9AngelOptionFullProbeStatus.AVAILABLE,
        requested_contract_count=10,
        fetched_contract_count=10,
        unfetched_contract_count=0,
        malformed_contract_count=0,
        oldest_provider_timestamp=NOW,
        newest_provider_timestamp=NOW,
        exchange_identity_verified=True,
        source_ref="angel-option-full",
    )


def _greeks_nifty():
    return Task9AngelGreeksProofV1(
        proof_id="task9865a7-greeks-nifty",
        observed_at=NOW,
        market="NIFTY",
        exchange="NFO",
        status=Task9AngelGreeksProbeStatus.AVAILABLE,
        requested_contract_count=5,
        enriched_contract_count=5,
        unavailable_contract_count=0,
        delta_present=True,
        gamma_present=True,
        theta_present=True,
        vega_present=True,
        implied_volatility_present=True,
        source_ref="angel-option-greeks",
    )


def _greeks_sensex():
    return Task9AngelGreeksProofV1(
        proof_id="task9865a7-greeks-sensex",
        observed_at=NOW,
        market="SENSEX",
        exchange="BFO",
        status=Task9AngelGreeksProbeStatus.UNSUPPORTED,
        requested_contract_count=0,
        enriched_contract_count=0,
        unavailable_contract_count=0,
        delta_present=False,
        gamma_present=False,
        theta_present=False,
        vega_present=False,
        implied_volatility_present=False,
        sanitized_reason=(
            "BFO_GREEKS_PROVIDER_UNSUPPORTED"
        ),
    )


def _vix():
    return Task9AngelIndiaVixProofV1(
        proof_id="task9865a7-vix",
        observed_at=NOW,
        market="INDIA_VIX",
        exchange="NSE",
        instrument_type="AMXIDX",
        status=Task9AngelIndiaVixProbeStatus.AVAILABLE,
        provider_timestamp=NOW,
        ltp=14.5,
        previous_close=14.1,
        identity_verified=True,
        source_ref="certified-india-vix-live-reader",
    )


def _budget():
    return Task9AngelRequestBudgetProofV1(
        proof_id="task9865a7-budget",
        observed_at=NOW,
        status=Task9AngelRequestBudgetProbeStatus.READY,
        controller_thread_safe=True,
        account_wide_budget_owner=True,
        endpoint_scoped_cooldowns=True,
        historical_isolated_from_market_data=True,
        historical_isolated_from_greeks=True,
        angel_client_transport_retry_owner=True,
        launcher_next_cycle_retry_only=True,
        launcher_request_burst_owner=False,
        cache_owned_by_controller=True,
        source_ref="task9-request-budget-structural-verifier",
    )


def _bundle():
    return Task9AngelLiveProofBundleV1(
        auth=_auth(),
        instrument_master=_master(),
        spots=(
            _spot(
                "NIFTY",
                "NSE",
                "99926000",
            ),
            _spot(
                "SENSEX",
                "BSE",
                "99919000",
            ),
        ),
        option_full=(
            _option(
                "NIFTY",
                "NFO",
            ),
            _option(
                "SENSEX",
                "BFO",
            ),
        ),
        greeks=(
            _greeks_nifty(),
            _greeks_sensex(),
        ),
        india_vix=_vix(),
        request_budget=_budget(),
    )


def _project(bundle=None):
    return project_task9_angel_live_proof_bundle(
        runtime_config=_config(),
        authority=(
            build_task9_angel_capability_session()
        ),
        bundle=(
            _bundle()
            if bundle is None
            else bundle
        ),
    )


def _row(
    result,
    family,
    capability,
    market=None,
):
    return next(
        item
        for item in result.report.capability_states
        if (
            item.provider_family is family
            and item.capability is capability
            and item.market == market
        )
    )


def test_complete_a1_to_a6_bundle_passes_angel_live_proof_gate():
    result = _project()

    assert (
        result.required_angel_live_proofs_ready
        is True
    )

    assert (
        result.request_budget_readiness.readiness_status
        is Task9ProviderReadinessStatus.READY
    )

    assert result.execution_mode == "PAPER"
    assert result.broker_order_submission is False
    assert result.live_execution_eligible is False


def test_required_projected_generic_rows_are_ready():
    result = _project()

    required = (
        (
            Task9ProviderFamily.ANGEL_AUTH_SESSION,
            Task9ProviderCapability.AUTH_SESSION,
            None,
        ),
        (
            Task9ProviderFamily.ANGEL_INSTRUMENT_MASTER,
            Task9ProviderCapability.INSTRUMENT_MASTER,
            None,
        ),
        (
            Task9ProviderFamily.ANGEL_SPOT,
            Task9ProviderCapability.SPOT_QUOTES,
            "NIFTY",
        ),
        (
            Task9ProviderFamily.ANGEL_SPOT,
            Task9ProviderCapability.SPOT_QUOTES,
            "SENSEX",
        ),
        (
            Task9ProviderFamily.ANGEL_OPTION_FULL,
            Task9ProviderCapability.OPTION_FULL_QUOTES,
            "NIFTY",
        ),
        (
            Task9ProviderFamily.ANGEL_OPTION_FULL,
            Task9ProviderCapability.OPTION_FULL_QUOTES,
            "SENSEX",
        ),
    )

    for family, capability, market in required:
        assert (
            _row(
                result,
                family,
                capability,
                market,
            ).readiness_status
            is Task9ProviderReadinessStatus.READY
        )


def test_bfo_greeks_unsupported_does_not_block_a7():
    result = _project()

    bfo = _row(
        result,
        Task9ProviderFamily.ANGEL_OPTION_GREEKS,
        Task9ProviderCapability.OPTION_GREEKS,
        "SENSEX",
    )

    assert (
        bfo.readiness_status
        is Task9ProviderReadinessStatus.UNSUPPORTED
    )

    assert (
        result.required_angel_live_proofs_ready
        is True
    )


def test_websocket_remains_pending_for_9865b():
    result = _project()

    websocket = _row(
        result,
        Task9ProviderFamily.ANGEL_MARKET_WEBSOCKET,
        Task9ProviderCapability.MARKET_DATA_WEBSOCKET,
        None,
    )

    assert (
        result.websocket_live_proof_pending
        is True
    )

    assert (
        websocket.readiness_status
        is Task9ProviderReadinessStatus.READY_PENDING_LIVE_PROOF
    )


def test_failed_required_auth_fails_a7_gate_without_fabrication():
    bundle = _bundle()

    failed_auth = Task9AngelAuthSessionProofV1(
        proof_id="task9865a7-auth-failed",
        observed_at=NOW,
        status=Task9AngelAuthProbeStatus.FAILED,
        credential_references_present=False,
        credential_kinds_confirmed=(),
        sanitized_reason=(
            "MISSING_REQUIRED_CREDENTIAL_REFERENCE"
        ),
    )

    result = _project(
        replace(
            bundle,
            auth=failed_auth,
        )
    )

    assert (
        result.required_angel_live_proofs_ready
        is False
    )

    auth = _row(
        result,
        Task9ProviderFamily.ANGEL_AUTH_SESSION,
        Task9ProviderCapability.AUTH_SESSION,
        None,
    )

    assert auth.readiness_status is not (
        Task9ProviderReadinessStatus.READY
    )


def test_bundle_requires_exact_two_market_proofs():
    bundle = _bundle()

    try:
        replace(
            bundle,
            spots=(bundle.spots[0],),
        )
    except ValueError as exc:
        assert str(exc) == "spots"
    else:
        raise AssertionError(
            "single-market A7 bundle was accepted"
        )
