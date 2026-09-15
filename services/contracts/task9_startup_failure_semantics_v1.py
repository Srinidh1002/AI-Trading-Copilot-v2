"""Pure, secret-safe mapping from known Task 9 startup conditions to phases."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Mapping

from services.contracts.task9_runtime_config_v1 import ProviderFeatureStateV1
from services.contracts.task9_startup_preflight_v1 import (
    Task9StartupPreflightPhase,
    Task9StartupPreflightPhaseResultV1,
    Task9StartupPreflightPhaseStatus,
)


class Task9StartupSemantic(str, Enum):
    STARTUP_FATAL = "STARTUP_FATAL"
    STARTUP_BLOCKED_RETRYABLE = "STARTUP_BLOCKED_RETRYABLE"
    OPTIONAL_UNAVAILABLE = "OPTIONAL_UNAVAILABLE"
    WARNING = "WARNING"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class Task9StartupReasonCode(str, Enum):
    MISSING_REQUIRED_STATIC_REFERENCE = "MISSING_REQUIRED_STATIC_REFERENCE"
    INVALID_NUMERIC_VALUE = "INVALID_NUMERIC_VALUE"
    AMBIGUOUS_CAPITAL_RISK = "AMBIGUOUS_CAPITAL_RISK"
    INVALID_TIMEZONE = "INVALID_TIMEZONE"
    INVALID_MARKET_DATE = "INVALID_MARKET_DATE"
    CONFLICTING_TASK9_LEGACY_CONFIG = "CONFLICTING_TASK9_LEGACY_CONFIG"
    UNSAFE_EXECUTION_MODE_REQUEST = "UNSAFE_EXECUTION_MODE_REQUEST"
    BROKER_SUBMISSION_ENABLED = "BROKER_SUBMISSION_ENABLED"
    LIVE_EXECUTION_ELIGIBLE = "LIVE_EXECUTION_ELIGIBLE"
    NON_PAPER_MODE = "NON_PAPER_MODE"
    CAMPAIGN_ID_BLANK = "CAMPAIGN_ID_BLANK"
    OFFICIAL_RUN_ID_BLANK = "OFFICIAL_RUN_ID_BLANK"
    INVALID_RUN_CLASSIFICATION = "INVALID_RUN_CLASSIFICATION"
    ROOT_MISMATCH = "ROOT_MISMATCH"
    CAMPAIGN_RUN_MISMATCH = "CAMPAIGN_RUN_MISMATCH"
    WRONG_MARKET_DATE = "WRONG_MARKET_DATE"
    CAMPAIGN_COMPLETE = "CAMPAIGN_COMPLETE"
    PATH_BLANK_INVALID = "PATH_BLANK_INVALID"
    PERSISTENCE_UNAVAILABLE = "PERSISTENCE_UNAVAILABLE"
    PERSISTENCE_TEMPORARY_CONTENTION = "PERSISTENCE_TEMPORARY_CONTENTION"
    CORRUPT_AUTHORITATIVE_STATE = "CORRUPT_AUTHORITATIVE_STATE"
    CONFLICTING_DUPLICATE_IDENTITY = "CONFLICTING_DUPLICATE_IDENTITY"
    WRONG_NIFTY_IDENTITY = "WRONG_NIFTY_IDENTITY"
    WRONG_SENSEX_IDENTITY = "WRONG_SENSEX_IDENTITY"
    WRONG_OPTION_EXCHANGE = "WRONG_OPTION_EXCHANGE"
    MARKET_SESSION_IDENTITY_UNAVAILABLE = "MARKET_SESSION_IDENTITY_UNAVAILABLE"
    INVALID_SESSION_POLICY = "INVALID_SESSION_POLICY"
    OUTDATED_SESSION_POLICY_VERSION = "OUTDATED_SESSION_POLICY_VERSION"
    MISSING_CREDENTIAL_REFERENCE = "MISSING_CREDENTIAL_REFERENCE"
    AG8001 = "AG8001"
    AG8002 = "AG8002"
    AG8003 = "AG8003"
    AB8050 = "AB8050"
    AB8051 = "AB8051"
    AB1010 = "AB1010"
    AB1011 = "AB1011"
    AB2001 = "AB2001"
    REQUIRED_CAPABILITY_UNSUPPORTED = "REQUIRED_CAPABILITY_UNSUPPORTED"
    REQUIRED_CAPABILITY_TEMPORARILY_UNAVAILABLE = "REQUIRED_CAPABILITY_TEMPORARILY_UNAVAILABLE"
    OPTIONAL_PROVIDER_NOT_SELECTED = "OPTIONAL_PROVIDER_NOT_SELECTED"
    OPTIONAL_PROVIDER_DISABLED = "OPTIONAL_PROVIDER_DISABLED"
    OPTIONAL_PROVIDER_TEMPORARILY_UNAVAILABLE = "OPTIONAL_PROVIDER_TEMPORARILY_UNAVAILABLE"
    INSTRUMENT_MASTER_STALE = "INSTRUMENT_MASTER_STALE"
    INSTRUMENT_MASTER_CORRUPT = "INSTRUMENT_MASTER_CORRUPT"
    CAPABILITY_UNKNOWN_PENDING_LIVE_PROOF = "CAPABILITY_UNKNOWN_PENDING_LIVE_PROOF"
    COLLECTOR_CONFIG_INVALID = "COLLECTOR_CONFIG_INVALID"
    COLLECTOR_NOT_READY = "COLLECTOR_NOT_READY"
    ONE_MARKET_NOT_READY = "ONE_MARKET_NOT_READY"
    RUNTIME_DEPENDENCY_UNAVAILABLE = "RUNTIME_DEPENDENCY_UNAVAILABLE"
    HARDCODED_INVALID_DASHBOARD_ROOT = "HARDCODED_INVALID_DASHBOARD_ROOT"
    ACTIVE_AUTHORITY_UNAVAILABLE = "ACTIVE_AUTHORITY_UNAVAILABLE"
    PUBLICATION_AUTHORITY_MISMATCH = "PUBLICATION_AUTHORITY_MISMATCH"
    RUNTIME_CONFIG_SNAPSHOT_MISSING = "RUNTIME_CONFIG_SNAPSHOT_MISSING"
    SNAPSHOT_HASH_MISMATCH = "SNAPSHOT_HASH_MISMATCH"
    MALFORMED_PROVENANCE = "MALFORMED_PROVENANCE"
    ROLLOVER_REQUIRED = "ROLLOVER_REQUIRED"
    CAMPAIGN_PAUSED = "CAMPAIGN_PAUSED"
    CAMPAIGN_HALTED = "CAMPAIGN_HALTED"
    CAMPAIGN_NUMERIC_TARGET_MET = "CAMPAIGN_NUMERIC_TARGET_MET"


_FATAL = frozenset({
    Task9StartupReasonCode.MISSING_REQUIRED_STATIC_REFERENCE, Task9StartupReasonCode.INVALID_NUMERIC_VALUE,
    Task9StartupReasonCode.AMBIGUOUS_CAPITAL_RISK, Task9StartupReasonCode.INVALID_TIMEZONE,
    Task9StartupReasonCode.INVALID_MARKET_DATE, Task9StartupReasonCode.CONFLICTING_TASK9_LEGACY_CONFIG,
    Task9StartupReasonCode.UNSAFE_EXECUTION_MODE_REQUEST, Task9StartupReasonCode.BROKER_SUBMISSION_ENABLED,
    Task9StartupReasonCode.LIVE_EXECUTION_ELIGIBLE, Task9StartupReasonCode.NON_PAPER_MODE,
    Task9StartupReasonCode.CAMPAIGN_ID_BLANK, Task9StartupReasonCode.OFFICIAL_RUN_ID_BLANK,
    Task9StartupReasonCode.INVALID_RUN_CLASSIFICATION, Task9StartupReasonCode.ROOT_MISMATCH,
    Task9StartupReasonCode.CAMPAIGN_RUN_MISMATCH, Task9StartupReasonCode.WRONG_MARKET_DATE,
    Task9StartupReasonCode.CAMPAIGN_COMPLETE, Task9StartupReasonCode.PATH_BLANK_INVALID,
    Task9StartupReasonCode.CORRUPT_AUTHORITATIVE_STATE, Task9StartupReasonCode.CONFLICTING_DUPLICATE_IDENTITY,
    Task9StartupReasonCode.WRONG_NIFTY_IDENTITY, Task9StartupReasonCode.WRONG_SENSEX_IDENTITY,
    Task9StartupReasonCode.WRONG_OPTION_EXCHANGE, Task9StartupReasonCode.INVALID_SESSION_POLICY,
    Task9StartupReasonCode.MISSING_CREDENTIAL_REFERENCE, Task9StartupReasonCode.AG8001,
    Task9StartupReasonCode.AG8003, Task9StartupReasonCode.AB8050,
    Task9StartupReasonCode.INSTRUMENT_MASTER_CORRUPT, Task9StartupReasonCode.COLLECTOR_CONFIG_INVALID,
    Task9StartupReasonCode.HARDCODED_INVALID_DASHBOARD_ROOT, Task9StartupReasonCode.PUBLICATION_AUTHORITY_MISMATCH,
    Task9StartupReasonCode.RUNTIME_CONFIG_SNAPSHOT_MISSING, Task9StartupReasonCode.SNAPSHOT_HASH_MISMATCH,
    Task9StartupReasonCode.MALFORMED_PROVENANCE,
})
_RETRYABLE = frozenset({
    Task9StartupReasonCode.PERSISTENCE_UNAVAILABLE, Task9StartupReasonCode.PERSISTENCE_TEMPORARY_CONTENTION,
    Task9StartupReasonCode.MARKET_SESSION_IDENTITY_UNAVAILABLE, Task9StartupReasonCode.OUTDATED_SESSION_POLICY_VERSION,
    Task9StartupReasonCode.AG8002, Task9StartupReasonCode.AB8051, Task9StartupReasonCode.AB1010,
    Task9StartupReasonCode.AB1011, Task9StartupReasonCode.AB2001,
    Task9StartupReasonCode.REQUIRED_CAPABILITY_TEMPORARILY_UNAVAILABLE,
    Task9StartupReasonCode.COLLECTOR_NOT_READY, Task9StartupReasonCode.ONE_MARKET_NOT_READY,
    Task9StartupReasonCode.RUNTIME_DEPENDENCY_UNAVAILABLE, Task9StartupReasonCode.ACTIVE_AUTHORITY_UNAVAILABLE,
    Task9StartupReasonCode.ROLLOVER_REQUIRED,
    Task9StartupReasonCode.CAMPAIGN_PAUSED, Task9StartupReasonCode.CAMPAIGN_HALTED,
    Task9StartupReasonCode.CAMPAIGN_NUMERIC_TARGET_MET,
})


def _reason(value: Task9StartupReasonCode | str) -> Task9StartupReasonCode:
    try:
        return Task9StartupReasonCode(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("reason_code") from exc


def _feature(value: ProviderFeatureStateV1 | str | None) -> ProviderFeatureStateV1 | None:
    if value is None:
        return None
    try:
        return ProviderFeatureStateV1(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("provider_feature_intent") from exc


def classify_task9_startup_condition(
    reason_code: Task9StartupReasonCode | str,
    *,
    provider_feature_intent: ProviderFeatureStateV1 | str | None = None,
    option_entry_required: bool | None = None,
) -> Task9StartupSemantic:
    """Classify one known condition without performing any startup check."""
    reason = _reason(reason_code)
    intent = _feature(provider_feature_intent)
    if option_entry_required is not None and type(option_entry_required) is not bool:
        raise TypeError("option_entry_required")
    if reason is Task9StartupReasonCode.INSTRUMENT_MASTER_STALE:
        return Task9StartupSemantic.STARTUP_BLOCKED_RETRYABLE if option_entry_required else Task9StartupSemantic.WARNING
    if reason in {Task9StartupReasonCode.OPTIONAL_PROVIDER_NOT_SELECTED, Task9StartupReasonCode.OPTIONAL_PROVIDER_DISABLED}:
        return Task9StartupSemantic.NOT_APPLICABLE
    if reason in {Task9StartupReasonCode.OPTIONAL_PROVIDER_TEMPORARILY_UNAVAILABLE, Task9StartupReasonCode.CAPABILITY_UNKNOWN_PENDING_LIVE_PROOF, Task9StartupReasonCode.REQUIRED_CAPABILITY_UNSUPPORTED}:
        if intent in {ProviderFeatureStateV1.PROVIDER_NOT_SELECTED, ProviderFeatureStateV1.DISABLED, ProviderFeatureStateV1.OPTIONAL_FUTURE}:
            return Task9StartupSemantic.NOT_APPLICABLE
        if intent in {ProviderFeatureStateV1.ENABLED_OPTIONAL, ProviderFeatureStateV1.CAPABILITY_AWARE}:
            return Task9StartupSemantic.OPTIONAL_UNAVAILABLE
        if reason is Task9StartupReasonCode.REQUIRED_CAPABILITY_UNSUPPORTED:
            return Task9StartupSemantic.STARTUP_FATAL
        return Task9StartupSemantic.STARTUP_BLOCKED_RETRYABLE
    if reason in _FATAL:
        return Task9StartupSemantic.STARTUP_FATAL
    if reason in _RETRYABLE:
        return Task9StartupSemantic.STARTUP_BLOCKED_RETRYABLE
    raise ValueError("unmapped reason_code")


def _phase_status(semantic: Task9StartupSemantic) -> tuple[Task9StartupPreflightPhaseStatus, bool]:
    mapping = {
        Task9StartupSemantic.STARTUP_FATAL: (Task9StartupPreflightPhaseStatus.FAIL_FATAL, True),
        Task9StartupSemantic.STARTUP_BLOCKED_RETRYABLE: (Task9StartupPreflightPhaseStatus.BLOCKED_RETRYABLE, True),
        Task9StartupSemantic.OPTIONAL_UNAVAILABLE: (Task9StartupPreflightPhaseStatus.WARNING, False),
        Task9StartupSemantic.WARNING: (Task9StartupPreflightPhaseStatus.WARNING, False),
        Task9StartupSemantic.NOT_APPLICABLE: (Task9StartupPreflightPhaseStatus.NOT_APPLICABLE, False),
    }
    return mapping[semantic]


def build_task9_startup_phase_result(
    *,
    phase: Task9StartupPreflightPhase | str,
    reason_code: Task9StartupReasonCode | str,
    observed_at: datetime,
    provider_feature_intent: ProviderFeatureStateV1 | str | None = None,
    option_entry_required: bool | None = None,
    detail: str | None = None,
    evidence_refs: tuple[str, ...] = (),
    incident_refs: tuple[str, ...] = (),
    metadata: Mapping[str, object] | None = None,
) -> Task9StartupPreflightPhaseResultV1:
    """Build one deterministic typed phase result from a classified condition."""
    semantic = classify_task9_startup_condition(
        reason_code, provider_feature_intent=provider_feature_intent,
        option_entry_required=option_entry_required,
    )
    status, blocking = _phase_status(semantic)
    return Task9StartupPreflightPhaseResultV1(
        phase=phase, status=status, blocking=blocking, reason_code=_reason(reason_code).value,
        detail=detail, observed_at=observed_at, evidence_refs=evidence_refs,
        incident_refs=incident_refs, metadata={} if metadata is None else metadata,
    )
