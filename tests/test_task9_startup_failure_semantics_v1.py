from datetime import datetime, timezone

import pytest

from services.contracts.task9_runtime_config_v1 import ProviderFeatureStateV1
from services.contracts.task9_startup_failure_semantics_v1 import (
    Task9StartupReasonCode, Task9StartupSemantic,
    build_task9_startup_phase_result, classify_task9_startup_condition,
)
from services.contracts.task9_startup_preflight_v1 import (
    Task9StartupPreflightPhase, Task9StartupPreflightPhaseStatus,
)


NOW = datetime(2026, 8, 15, 9, 15, tzinfo=timezone.utc)


def _result(reason, **kwargs):
    return build_task9_startup_phase_result(
        phase=Task9StartupPreflightPhase.ANGEL_CREDENTIALS_SESSION,
        reason_code=reason, observed_at=NOW, **kwargs,
    )


@pytest.mark.parametrize("reason,status,blocking", [
    (Task9StartupReasonCode.NON_PAPER_MODE, Task9StartupPreflightPhaseStatus.FAIL_FATAL, True),
    (Task9StartupReasonCode.PERSISTENCE_TEMPORARY_CONTENTION, Task9StartupPreflightPhaseStatus.BLOCKED_RETRYABLE, True),
    (Task9StartupReasonCode.OPTIONAL_PROVIDER_NOT_SELECTED, Task9StartupPreflightPhaseStatus.NOT_APPLICABLE, False),
])
def test_core_semantics_map_to_exact_phase_status(reason, status, blocking):
    result = _result(reason)
    assert (result.status, result.blocking) == (status, blocking)


@pytest.mark.parametrize("reason", [
    Task9StartupReasonCode.BROKER_SUBMISSION_ENABLED, Task9StartupReasonCode.LIVE_EXECUTION_ELIGIBLE,
    Task9StartupReasonCode.AMBIGUOUS_CAPITAL_RISK, Task9StartupReasonCode.WRONG_NIFTY_IDENTITY,
    Task9StartupReasonCode.WRONG_SENSEX_IDENTITY, Task9StartupReasonCode.WRONG_OPTION_EXCHANGE,
    Task9StartupReasonCode.CORRUPT_AUTHORITATIVE_STATE,
])
def test_known_unsafe_configuration_and_identity_conditions_are_fatal(reason):
    assert _result(reason).status is Task9StartupPreflightPhaseStatus.FAIL_FATAL


def test_instrument_master_context_and_optional_features_do_not_silently_pass():
    assert _result(Task9StartupReasonCode.INSTRUMENT_MASTER_STALE, option_entry_required=True).status is Task9StartupPreflightPhaseStatus.BLOCKED_RETRYABLE
    assert _result(Task9StartupReasonCode.INSTRUMENT_MASTER_STALE, option_entry_required=False).status is Task9StartupPreflightPhaseStatus.WARNING
    bfo = _result(Task9StartupReasonCode.REQUIRED_CAPABILITY_UNSUPPORTED, provider_feature_intent=ProviderFeatureStateV1.CAPABILITY_AWARE)
    assert bfo.status is Task9StartupPreflightPhaseStatus.WARNING and not bfo.blocking
    vix = _result(Task9StartupReasonCode.CAPABILITY_UNKNOWN_PENDING_LIVE_PROOF, provider_feature_intent=ProviderFeatureStateV1.ENABLED_OPTIONAL)
    assert vix.status is Task9StartupPreflightPhaseStatus.WARNING
    for intent in (ProviderFeatureStateV1.PROVIDER_NOT_SELECTED, ProviderFeatureStateV1.OPTIONAL_FUTURE, ProviderFeatureStateV1.DISABLED):
        assert _result(Task9StartupReasonCode.OPTIONAL_PROVIDER_TEMPORARILY_UNAVAILABLE, provider_feature_intent=intent).status is Task9StartupPreflightPhaseStatus.NOT_APPLICABLE


@pytest.mark.parametrize("code,status", [
    (Task9StartupReasonCode.AG8001, Task9StartupPreflightPhaseStatus.FAIL_FATAL),
    (Task9StartupReasonCode.AG8002, Task9StartupPreflightPhaseStatus.BLOCKED_RETRYABLE),
    (Task9StartupReasonCode.AG8003, Task9StartupPreflightPhaseStatus.FAIL_FATAL),
    (Task9StartupReasonCode.AB8050, Task9StartupPreflightPhaseStatus.FAIL_FATAL),
    (Task9StartupReasonCode.AB8051, Task9StartupPreflightPhaseStatus.BLOCKED_RETRYABLE),
    (Task9StartupReasonCode.AB1010, Task9StartupPreflightPhaseStatus.BLOCKED_RETRYABLE),
    (Task9StartupReasonCode.AB1011, Task9StartupPreflightPhaseStatus.BLOCKED_RETRYABLE),
    (Task9StartupReasonCode.AB2001, Task9StartupPreflightPhaseStatus.BLOCKED_RETRYABLE),
])
def test_documented_angel_codes_have_stable_semantics(code, status):
    assert _result(code).status is status


def test_secret_safe_deterministic_output_and_references():
    result = _result(Task9StartupReasonCode.AB2001, detail="temporary provider fault", evidence_refs=("provider:angel",), incident_refs=("incident:1",), metadata={"attempt": 1})
    assert _result(Task9StartupReasonCode.AB2001).to_dict() == _result(Task9StartupReasonCode.AB2001).to_dict()
    assert result.evidence_refs == ("provider:angel",)
    assert result.incident_refs == ("incident:1",)
    with pytest.raises(ValueError, match="secret"):
        _result(Task9StartupReasonCode.AB2001, detail="Authorization: Bearer secret")


def test_semantic_type_is_exposed_and_unknown_reason_fails_closed():
    assert classify_task9_startup_condition(Task9StartupReasonCode.NON_PAPER_MODE) is Task9StartupSemantic.STARTUP_FATAL
    with pytest.raises(ValueError, match="reason_code"):
        classify_task9_startup_condition("UNKNOWN")
