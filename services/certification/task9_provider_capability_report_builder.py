"""Pure Task 9 capability report composition; it never contacts a provider."""
from __future__ import annotations
from datetime import datetime
from services.contracts.task9_provider_capability_report_v1 import *
from services.contracts.task9_runtime_config_v1 import Task9RuntimeConfigV1
from services.contracts.task9_startup_failure_semantics_v1 import build_task9_startup_phase_result,Task9StartupReasonCode
from services.contracts.task9_startup_preflight_v1 import Task9StartupPreflightPhase,Task9StartupPreflightPhaseResultV1,Task9StartupPreflightPhaseStatus
def _state(f,c,*,market=None,exchange=None,required=False,intent=ProviderFeatureStateV1.ENABLED_REQUIRED,doc=Task9ProviderSupportStatus.DOCUMENTED,impl=Task9ProviderSupportStatus.IMPLEMENTED,proof=Task9LiveProofStatus.PENDING,readiness=Task9ProviderReadinessStatus.READY_PENDING_LIVE_PROOF,semantic=None,meta=None,rate=None):return Task9ProviderCapabilityStateV1(f,c,market,exchange,required,intent,doc,impl,proof,readiness,semantic,rate_limit_policy_ref=rate,evidence_refs=("task9-provider-capability-evidence.v1",),metadata={} if meta is None else meta)
def build_task9_provider_capability_report(runtime_config:Task9RuntimeConfigV1,*,live_proof_overrides=None):
 if type(runtime_config)is not Task9RuntimeConfigV1:raise TypeError("runtime_config")
 rows=[_state(Task9ProviderFamily.ANGEL_AUTH_SESSION,Task9ProviderCapability.AUTH_SESSION,required=True,semantic=Task9StartupSemantic.STARTUP_BLOCKED_RETRYABLE),_state(Task9ProviderFamily.ANGEL_INSTRUMENT_MASTER,Task9ProviderCapability.INSTRUMENT_MASTER,required=True,semantic=Task9StartupSemantic.STARTUP_BLOCKED_RETRYABLE)]
 for m in runtime_config.markets:
  rows += [_state(Task9ProviderFamily.ANGEL_SPOT,Task9ProviderCapability.SPOT_QUOTES,market=m.market,exchange=m.exchange,required=True,semantic=Task9StartupSemantic.STARTUP_BLOCKED_RETRYABLE),_state(Task9ProviderFamily.ANGEL_OPTION_FULL,Task9ProviderCapability.OPTION_FULL_QUOTES,market=m.market,exchange=m.option_exchange,required=True,semantic=Task9StartupSemantic.STARTUP_BLOCKED_RETRYABLE,rate="task9-conservative-full-quote-rate-policy.v1",meta={"documentation_rate_discrepancy":"1_per_second_vs_10_per_second"})]
  if m.market=="NIFTY":rows.append(_state(Task9ProviderFamily.ANGEL_OPTION_GREEKS,Task9ProviderCapability.OPTION_GREEKS,market=m.market,exchange=m.option_exchange,intent=ProviderFeatureStateV1.CAPABILITY_AWARE,semantic=Task9StartupSemantic.OPTIONAL_UNAVAILABLE))
  else:rows.append(_state(Task9ProviderFamily.ANGEL_OPTION_GREEKS,Task9ProviderCapability.OPTION_GREEKS,market=m.market,exchange=m.option_exchange,intent=ProviderFeatureStateV1.CAPABILITY_AWARE,doc=Task9ProviderSupportStatus.UNSUPPORTED,impl=Task9ProviderSupportStatus.IMPLEMENTED,proof=Task9LiveProofStatus.NOT_APPLICABLE,readiness=Task9ProviderReadinessStatus.UNSUPPORTED,semantic=Task9StartupSemantic.OPTIONAL_UNAVAILABLE))
 rows += [_state(Task9ProviderFamily.ANGEL_MARKET_WEBSOCKET,Task9ProviderCapability.MARKET_DATA_WEBSOCKET,required=True,semantic=Task9StartupSemantic.STARTUP_BLOCKED_RETRYABLE,meta={"heartbeat_seconds":30,"connection_limit":3,"subscription_limit":1000,"index_sequence_reliable":False}),_state(Task9ProviderFamily.ANGEL_MARKET_WEBSOCKET,Task9ProviderCapability.PROVIDER_NATIVE_OI_CHANGE,intent=ProviderFeatureStateV1.CAPABILITY_AWARE,doc=Task9ProviderSupportStatus.UNSUPPORTED,impl=Task9ProviderSupportStatus.UNSUPPORTED,proof=Task9LiveProofStatus.NOT_APPLICABLE,readiness=Task9ProviderReadinessStatus.UNSUPPORTED,semantic=Task9StartupSemantic.OPTIONAL_UNAVAILABLE),_state(Task9ProviderFamily.ANGEL_MARKET_WEBSOCKET,Task9ProviderCapability.TASK9_DERIVED_OI_CHANGE,intent=ProviderFeatureStateV1.CAPABILITY_AWARE,proof=Task9LiveProofStatus.PROVEN,readiness=Task9ProviderReadinessStatus.READY,semantic=None),_state(Task9ProviderFamily.INDIA_VIX,Task9ProviderCapability.INDIA_VIX,intent=ProviderFeatureStateV1.ENABLED_OPTIONAL,semantic=Task9StartupSemantic.OPTIONAL_UNAVAILABLE)]
 for f in (Task9ProviderFamily.MARKET_BREADTH,Task9ProviderFamily.INSTITUTIONAL_FLOW,Task9ProviderFamily.ECONOMIC_EVENT_CALENDAR,Task9ProviderFamily.GLOBAL_MARKET_DATA,Task9ProviderFamily.STRUCTURED_NEWS):rows.append(_state(f,Task9ProviderCapability.EXTERNAL_CONTEXT,intent=ProviderFeatureStateV1.PROVIDER_NOT_SELECTED,doc=Task9ProviderSupportStatus.NOT_SELECTED,impl=Task9ProviderSupportStatus.NOT_SELECTED,proof=Task9LiveProofStatus.NOT_APPLICABLE,readiness=Task9ProviderReadinessStatus.PROVIDER_NOT_SELECTED,semantic=Task9StartupSemantic.NOT_APPLICABLE))
 rows.append(_state(Task9ProviderFamily.LLM_CLASSIFIER,Task9ProviderCapability.CLASSIFICATION,intent=ProviderFeatureStateV1.OPTIONAL_FUTURE,doc=Task9ProviderSupportStatus.NOT_SELECTED,impl=Task9ProviderSupportStatus.NOT_SELECTED,proof=Task9LiveProofStatus.NOT_APPLICABLE,readiness=Task9ProviderReadinessStatus.DISABLED,semantic=Task9StartupSemantic.NOT_APPLICABLE))
 if live_proof_overrides is not None:
  if not isinstance(live_proof_overrides,dict):raise TypeError("live_proof_overrides")
  adjusted=[]
  for row in rows:
   proof=live_proof_overrides.get((row.provider_family.value,row.capability.value,row.market,row.exchange))
   if proof is None:adjusted.append(row);continue
   data=row.to_dict();data["live_proof_status"]=Task9LiveProofStatus(proof).value
   if data["live_proof_status"]==Task9LiveProofStatus.PROVEN.value and row.readiness_status is Task9ProviderReadinessStatus.READY_PENDING_LIVE_PROOF:data["readiness_status"]=Task9ProviderReadinessStatus.READY.value;data["startup_semantic"]=None
   data["evidence_refs"]=tuple(data["evidence_refs"]);data["incident_refs"]=tuple(data["incident_refs"]);adjusted.append(Task9ProviderCapabilityStateV1(**data))
  rows=adjusted
 return Task9ProviderCapabilityReportV1(runtime_config.runtime_config_id,runtime_config.runtime_config_version,tuple(rows))
def build_task9_provider_capability_preflight_phases(
    report: Task9ProviderCapabilityReportV1,
    *,
    observed_at: datetime,
):
    if type(report) is not Task9ProviderCapabilityReportV1:
        raise TypeError("report")

    required = tuple(
        state
        for state in report.capability_states
        if state.required
    )
    optional = tuple(
        state
        for state in report.capability_states
        if not state.required
    )

    non_ready_required = tuple(
        sorted(
            (
                state
                for state in required
                if state.readiness_status
                is not Task9ProviderReadinessStatus.READY
            ),
            key=lambda state: (
                state.provider_family.value,
                state.capability.value,
                state.market or "",
                state.exchange or "",
            ),
        )
    )

    def required_diagnostics():
        detail = (
            "non_ready_required="
            + ",".join(
                (
                    f"{state.provider_family.value}/"
                    f"{state.capability.value}/"
                    f"{state.market or '-'}/"
                    f"{state.exchange or '-'}="
                    f"{state.readiness_status.value}"
                )
                for state in non_ready_required
            )
        )

        if len(detail) > 512:
            raise ValueError(
                "TASK9_REQUIRED_CAPABILITY_DIAGNOSTIC_DETAIL_TOO_LONG"
            )

        evidence_refs = tuple(
            sorted(
                {
                    ref
                    for state in non_ready_required
                    for ref in state.evidence_refs
                }
            )
        )

        incident_refs = tuple(
            sorted(
                {
                    ref
                    for state in non_ready_required
                    for ref in state.incident_refs
                }
            )
        )

        return (
            detail,
            evidence_refs,
            incident_refs,
        )

    unsupported_required = tuple(
        state
        for state in non_ready_required
        if state.readiness_status
        is Task9ProviderReadinessStatus.UNSUPPORTED
    )

    if unsupported_required:
        (
            detail,
            evidence_refs,
            incident_refs,
        ) = required_diagnostics()

        required_phase = build_task9_startup_phase_result(
            phase=(
                Task9StartupPreflightPhase
                .REQUIRED_ANGEL_CAPABILITY_READINESS
            ),
            reason_code=(
                Task9StartupReasonCode
                .REQUIRED_CAPABILITY_UNSUPPORTED
            ),
            observed_at=observed_at,
            detail=detail,
            evidence_refs=evidence_refs,
            incident_refs=incident_refs,
        )

    elif non_ready_required:
        (
            detail,
            evidence_refs,
            incident_refs,
        ) = required_diagnostics()

        required_phase = build_task9_startup_phase_result(
            phase=(
                Task9StartupPreflightPhase
                .REQUIRED_ANGEL_CAPABILITY_READINESS
            ),
            reason_code=(
                Task9StartupReasonCode
                .REQUIRED_CAPABILITY_TEMPORARILY_UNAVAILABLE
            ),
            observed_at=observed_at,
            detail=detail,
            evidence_refs=evidence_refs,
            incident_refs=incident_refs,
        )

    else:
        required_phase = Task9StartupPreflightPhaseResultV1(
            Task9StartupPreflightPhase
            .REQUIRED_ANGEL_CAPABILITY_READINESS,
            Task9StartupPreflightPhaseStatus.PASS,
            False,
            "REQUIRED_CAPABILITIES_READY",
            None,
            observed_at,
        )

    if all(
        state.readiness_status
        in {
            Task9ProviderReadinessStatus.PROVIDER_NOT_SELECTED,
            Task9ProviderReadinessStatus.DISABLED,
            Task9ProviderReadinessStatus.NOT_APPLICABLE,
        }
        for state in optional
    ):
        optional_phase = build_task9_startup_phase_result(
            phase=(
                Task9StartupPreflightPhase
                .OPTIONAL_PROVIDER_CAPABILITY_STATE
            ),
            reason_code=(
                Task9StartupReasonCode
                .OPTIONAL_PROVIDER_NOT_SELECTED
            ),
            observed_at=observed_at,
        )
    else:
        optional_phase = build_task9_startup_phase_result(
            phase=(
                Task9StartupPreflightPhase
                .OPTIONAL_PROVIDER_CAPABILITY_STATE
            ),
            reason_code=(
                Task9StartupReasonCode
                .OPTIONAL_PROVIDER_TEMPORARILY_UNAVAILABLE
            ),
            provider_feature_intent=(
                ProviderFeatureStateV1.ENABLED_OPTIONAL
            ),
            observed_at=observed_at,
        )

    return required_phase, optional_phase
