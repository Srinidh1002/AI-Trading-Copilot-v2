from dataclasses import replace
from datetime import datetime,timezone
from services.certification.task9_provider_capability_report_builder import build_task9_provider_capability_report,build_task9_provider_capability_preflight_phases
from services.contracts.task9_provider_capability_report_v1 import *
from tests.test_task9_runtime_config_snapshot_v1 import _config

def test_documented_default_report_is_market_specific_and_non_secret():
 report=build_task9_provider_capability_report(_config())
 find=lambda f,c,m=None:next(x for x in report.capability_states if (x.provider_family,x.capability,x.market)==(f,c,m))
 assert find(Task9ProviderFamily.ANGEL_SPOT,Task9ProviderCapability.SPOT_QUOTES,"NIFTY").required
 assert find(Task9ProviderFamily.ANGEL_OPTION_FULL,Task9ProviderCapability.OPTION_FULL_QUOTES,"SENSEX").required
 nfo=find(Task9ProviderFamily.ANGEL_OPTION_GREEKS,Task9ProviderCapability.OPTION_GREEKS,"NIFTY");bfo=find(Task9ProviderFamily.ANGEL_OPTION_GREEKS,Task9ProviderCapability.OPTION_GREEKS,"SENSEX")
 assert nfo.readiness_status is Task9ProviderReadinessStatus.READY_PENDING_LIVE_PROOF
 assert bfo.readiness_status is Task9ProviderReadinessStatus.UNSUPPORTED and bfo.startup_semantic is Task9StartupSemantic.OPTIONAL_UNAVAILABLE
 vix=find(Task9ProviderFamily.INDIA_VIX,Task9ProviderCapability.INDIA_VIX);assert vix.readiness_status is Task9ProviderReadinessStatus.READY_PENDING_LIVE_PROOF and not vix.required
 for f in (Task9ProviderFamily.MARKET_BREADTH,Task9ProviderFamily.INSTITUTIONAL_FLOW,Task9ProviderFamily.ECONOMIC_EVENT_CALENDAR,Task9ProviderFamily.GLOBAL_MARKET_DATA,Task9ProviderFamily.STRUCTURED_NEWS):assert find(f,Task9ProviderCapability.EXTERNAL_CONTEXT).readiness_status is Task9ProviderReadinessStatus.PROVIDER_NOT_SELECTED
 assert find(Task9ProviderFamily.LLM_CLASSIFIER,Task9ProviderCapability.CLASSIFICATION).readiness_status is Task9ProviderReadinessStatus.DISABLED
 ws=find(Task9ProviderFamily.ANGEL_MARKET_WEBSOCKET,Task9ProviderCapability.MARKET_DATA_WEBSOCKET);assert ws.metadata["index_sequence_reliable"] is False and ws.metadata["heartbeat_seconds"]==30
 native=find(Task9ProviderFamily.ANGEL_MARKET_WEBSOCKET,Task9ProviderCapability.PROVIDER_NATIVE_OI_CHANGE);assert native.documentation_status is Task9ProviderSupportStatus.UNSUPPORTED
 full=find(Task9ProviderFamily.ANGEL_OPTION_FULL,Task9ProviderCapability.OPTION_FULL_QUOTES,"NIFTY");assert full.rate_limit_policy_ref and full.metadata["documentation_rate_discrepancy"]=="1_per_second_vs_10_per_second"
 assert "secret" not in report.to_dict().__repr__().lower()

def test_bridge_is_deterministic_and_required_pending_blocks_optional_does_not():
 report=build_task9_provider_capability_report(_config());required,optional=build_task9_provider_capability_preflight_phases(report,observed_at=datetime(2026,8,15,tzinfo=timezone.utc))
 assert required.blocking and required.status.value=="BLOCKED_RETRYABLE"
 assert not optional.blocking and optional.status.value=="WARNING"

def test_required_capability_block_preserves_exact_non_ready_row_diagnostics():
    report = build_task9_provider_capability_report(
        _config()
    )

    rows = [
        (
            replace(
                state,
                live_proof_status=Task9LiveProofStatus.PROVEN,
                readiness_status=Task9ProviderReadinessStatus.READY,
                startup_semantic=None,
            )
            if state.required
            else state
        )
        for state in report.capability_states
    ]

    target_index = next(
        index
        for index, state in enumerate(rows)
        if (
            state.provider_family
            is Task9ProviderFamily.ANGEL_OPTION_FULL
            and state.capability
            is Task9ProviderCapability.OPTION_FULL_QUOTES
            and state.market == "SENSEX"
            and state.exchange == "BFO"
        )
    )

    rows[target_index] = replace(
        rows[target_index],
        live_proof_status=Task9LiveProofStatus.PENDING,
        readiness_status=(
            Task9ProviderReadinessStatus.BLOCKED_RETRYABLE
        ),
        startup_semantic=(
            Task9StartupSemantic.STARTUP_BLOCKED_RETRYABLE
        ),
        incident_refs=("incident:task9104-gate7s",),
    )

    projected = Task9ProviderCapabilityReportV1(
        runtime_config_id=report.runtime_config_id,
        runtime_config_version=report.runtime_config_version,
        capability_states=tuple(rows),
    )

    required, _ = (
        build_task9_provider_capability_preflight_phases(
            projected,
            observed_at=datetime(
                2026,
                8,
                20,
                tzinfo=timezone.utc,
            ),
        )
    )

    assert required.blocking is True
    assert (
        required.status.value
        == "BLOCKED_RETRYABLE"
    )
    assert (
        required.reason_code
        == "REQUIRED_CAPABILITY_TEMPORARILY_UNAVAILABLE"
    )

    assert (
        "ANGEL_OPTION_FULL/"
        "OPTION_FULL_QUOTES/"
        "SENSEX/"
        "BFO=BLOCKED_RETRYABLE"
        in required.detail
    )

    assert (
        "incident:task9104-gate7s"
        in required.incident_refs
    )

    assert (
        "task9-provider-capability-evidence.v1"
        in required.evidence_refs
    )

