"""Offline Task 9 Angel capability/session authority builder."""
from __future__ import annotations

from services.contracts.task9_angel_capability_session_v1 import (
    Task9AngelCapability,
    Task9AngelCapabilitySessionV1,
    Task9AngelCapabilityStateV1,
    Task9AngelFailureCodeSetV1,
    Task9AngelRequirement,
    Task9AngelSessionCredentialKind,
)
from services.contracts.task9_provider_capability_report_v1 import (
    Task9LiveProofStatus,
    Task9ProviderReadinessStatus,
    Task9ProviderSupportStatus,
)


_REQUIRED_PENDING = dict(
    requirement=Task9AngelRequirement.REQUIRED,
    documentation_status=(
        Task9ProviderSupportStatus.DOCUMENTED
    ),
    implementation_status=(
        Task9ProviderSupportStatus.IMPLEMENTED
    ),
    live_proof_status=(
        Task9LiveProofStatus.PENDING
    ),
    readiness_status=(
        Task9ProviderReadinessStatus.READY_PENDING_LIVE_PROOF
    ),
)


def build_task9_angel_capability_session(
) -> Task9AngelCapabilitySessionV1:
    states = (
        Task9AngelCapabilityStateV1(
            capability=(
                Task9AngelCapability.AUTH_SESSION
            ),
            market=None,
            exchange=None,
            endpoint_policy_ref=(
                "angel-endpoint-policy:authentication"
            ),
            notes=(
                "Session creation requires JWT, refresh, and feed credentials.",
                "Live authentication proof is deferred to live-market preflight.",
            ),
            **_REQUIRED_PENDING,
        ),
        Task9AngelCapabilityStateV1(
            capability=(
                Task9AngelCapability.BFO_OPTION_FULL
            ),
            market="SENSEX",
            exchange="BFO",
            endpoint_policy_ref=(
                "angel-endpoint-policy:market-data"
            ),
            notes=(
                "FULL quote fetched and unfetched results require per-contract handling.",
            ),
            **_REQUIRED_PENDING,
        ),
        Task9AngelCapabilityStateV1(
            capability=(
                Task9AngelCapability.BFO_OPTION_GREEKS
            ),
            requirement=(
                Task9AngelRequirement.OPTIONAL
            ),
            market="SENSEX",
            exchange="BFO",
            documentation_status=(
                Task9ProviderSupportStatus.UNSUPPORTED
            ),
            implementation_status=(
                Task9ProviderSupportStatus.IMPLEMENTED
            ),
            live_proof_status=(
                Task9LiveProofStatus.NOT_APPLICABLE
            ),
            readiness_status=(
                Task9ProviderReadinessStatus.UNSUPPORTED
            ),
            endpoint_policy_ref=(
                "angel-endpoint-policy:option-greeks"
            ),
            notes=(
                "BFO Greeks are unsupported by provider capability policy.",
                "Unsupported BFO Greeks are optional and must not block SENSEX.",
            ),
        ),
        Task9AngelCapabilityStateV1(
            capability=(
                Task9AngelCapability.INDIA_VIX
            ),
            requirement=(
                Task9AngelRequirement.OPTIONAL
            ),
            market="INDIA_VIX",
            exchange="NSE",
            documentation_status=(
                Task9ProviderSupportStatus.DOCUMENTED
            ),
            implementation_status=(
                Task9ProviderSupportStatus.IMPLEMENTED
            ),
            live_proof_status=(
                Task9LiveProofStatus.PENDING
            ),
            readiness_status=(
                Task9ProviderReadinessStatus.READY_PENDING_LIVE_PROOF
            ),
            endpoint_policy_ref=(
                "angel-endpoint-policy:market-data"
            ),
            freshness_policy_ref=(
                "INDIA_VIX_PREVIOUS_CLOSE_POLICY_2026_08_03"
            ),
            notes=(
                "Expected provider identity is India VIX on NSE with AMXIDX instrument type.",
                "India VIX remains optional for Task9 startup.",
            ),
        ),
        Task9AngelCapabilityStateV1(
            capability=(
                Task9AngelCapability.INSTRUMENT_MASTER
            ),
            market=None,
            exchange=None,
            freshness_policy_ref=(
                "task9-angel-daily-instrument-master-freshness.v1"
            ),
            notes=(
                "Instrument master is identity and contract-discovery authority, not live price authority.",
                "Freshness must be proven before option contract use.",
            ),
            **_REQUIRED_PENDING,
        ),
        Task9AngelCapabilityStateV1(
            capability=(
                Task9AngelCapability.NFO_OPTION_FULL
            ),
            market="NIFTY",
            exchange="NFO",
            endpoint_policy_ref=(
                "angel-endpoint-policy:market-data"
            ),
            notes=(
                "FULL quote fetched and unfetched results require per-contract handling.",
            ),
            **_REQUIRED_PENDING,
        ),
        Task9AngelCapabilityStateV1(
            capability=(
                Task9AngelCapability.NFO_OPTION_GREEKS
            ),
            requirement=(
                Task9AngelRequirement.OPTIONAL
            ),
            market="NIFTY",
            exchange="NFO",
            documentation_status=(
                Task9ProviderSupportStatus.DOCUMENTED
            ),
            implementation_status=(
                Task9ProviderSupportStatus.IMPLEMENTED
            ),
            live_proof_status=(
                Task9LiveProofStatus.PENDING
            ),
            readiness_status=(
                Task9ProviderReadinessStatus.READY_PENDING_LIVE_PROOF
            ),
            endpoint_policy_ref=(
                "angel-endpoint-policy:option-greeks"
            ),
            notes=(
                "NFO Greeks are capability-aware and optional for certification startup.",
            ),
        ),
        Task9AngelCapabilityStateV1(
            capability=(
                Task9AngelCapability.NIFTY_SPOT_FULL
            ),
            market="NIFTY",
            exchange="NSE",
            endpoint_policy_ref=(
                "angel-endpoint-policy:market-data"
            ),
            notes=(
                "NIFTY spot FULL identity and freshness require live proof.",
            ),
            **_REQUIRED_PENDING,
        ),
        Task9AngelCapabilityStateV1(
            capability=(
                Task9AngelCapability.REQUEST_BUDGET
            ),
            market=None,
            exchange=None,
            endpoint_policy_ref=(
                "services.broker.market_data_control.MarketDataRequestController"
            ),
            notes=(
                "One account-wide request-budget authority owns outbound pacing.",
                "Endpoint cooldowns remain endpoint-scoped.",
                "Conservative FULL quote pacing remains required while documentation rates conflict.",
            ),
            **_REQUIRED_PENDING,
        ),
        Task9AngelCapabilityStateV1(
            capability=(
                Task9AngelCapability.SENSEX_SPOT_FULL
            ),
            market="SENSEX",
            exchange="BSE",
            endpoint_policy_ref=(
                "angel-endpoint-policy:market-data"
            ),
            notes=(
                "SENSEX spot FULL identity and freshness require live proof.",
            ),
            **_REQUIRED_PENDING,
        ),
    )

    states = tuple(
        sorted(
            states,
            key=lambda state: (
                state.capability.value,
                state.market or "",
                state.exchange or "",
            ),
        )
    )

    return Task9AngelCapabilitySessionV1(
        capability_states=states,
        required_session_credentials=(
            Task9AngelSessionCredentialKind.JWT,
            Task9AngelSessionCredentialKind.REFRESH,
            Task9AngelSessionCredentialKind.FEED,
        ),
        failure_codes=(
            Task9AngelFailureCodeSetV1(
                fatal_codes=(
                    "AG8001",
                    "AG8003",
                    "AB8050",
                ),
                retryable_codes=(
                    "AG8002",
                    "AB8051",
                    "AB1010",
                    "AB1011",
                    "AB2001",
                ),
            )
        ),
        account_wide_request_budget=True,
    )
