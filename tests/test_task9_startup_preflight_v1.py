from dataclasses import FrozenInstanceError
from datetime import date, datetime, timezone

import pytest

from services.contracts.task9_startup_preflight_v1 import (
    Task9StartupPreflightPhase,
    Task9StartupPreflightPhaseResultV1,
    Task9StartupPreflightPhaseStatus,
    Task9StartupPreflightResultV1,
)


NOW = datetime(2026, 8, 15, 9, 15, tzinfo=timezone.utc)
SHA = "a" * 64
SNAPSHOT = f"task9-runtime-config-{SHA}"


def _phase(phase, status=Task9StartupPreflightPhaseStatus.PASS):
    return Task9StartupPreflightPhaseResultV1(
        phase=phase, status=status,
        blocking=status in {Task9StartupPreflightPhaseStatus.FAIL_FATAL, Task9StartupPreflightPhaseStatus.BLOCKED_RETRYABLE},
        reason_code=f"{phase.value}_OK" if status is Task9StartupPreflightPhaseStatus.PASS else f"{phase.value}_{status.value}",
        detail="safe detail", observed_at=NOW, evidence_refs=(f"evidence:{phase.value}",), incident_refs=(), metadata={"source": "test"},
    )


def _result(phases=None, **overrides):
    values = dict(
        preflight_id="preflight-1", runtime_config_snapshot_id=SNAPSHOT, runtime_config_sha256=SHA,
        campaign_id="campaign-1", market_date=date(2026, 8, 15), official_run_id="run-1",
        run_classification="OFFICIAL_CERTIFICATION", started_at=NOW, completed_at=NOW,
        phase_results=tuple(_phase(phase) for phase in Task9StartupPreflightPhase), evidence_refs=("snapshot:1",),
    )
    if phases is not None:
        values["phase_results"] = tuple(phases)
    values.update(overrides)
    return Task9StartupPreflightResultV1(**values)


def test_exact_twelve_phases_and_pass_approval_round_trip():
    result = _result()
    assert len(Task9StartupPreflightPhase) == 12
    assert result.overall_status is Task9StartupPreflightPhaseStatus.PASS
    assert result.launch_approved is True
    assert Task9StartupPreflightResultV1.from_dict(result.to_dict()) == result


def test_warning_does_not_block_but_final_must_pass():
    phases = [_phase(phase) for phase in Task9StartupPreflightPhase]
    phases[1] = _phase(Task9StartupPreflightPhase.PAPER_SAFETY, Task9StartupPreflightPhaseStatus.WARNING)
    assert _result(phases).launch_approved is True
    phases[-1] = _phase(Task9StartupPreflightPhase.FINAL_LAUNCH_APPROVAL, Task9StartupPreflightPhaseStatus.WARNING)
    assert _result(phases).launch_approved is False


@pytest.mark.parametrize("status", [Task9StartupPreflightPhaseStatus.BLOCKED_RETRYABLE, Task9StartupPreflightPhaseStatus.FAIL_FATAL])
def test_blocking_statuses_prevent_approval_and_derive_phase(status):
    phases = [_phase(phase) for phase in Task9StartupPreflightPhase]
    phases[3] = _phase(Task9StartupPreflightPhase.PERSISTENCE_INTEGRITY_WRITABILITY, status)
    phases[4:] = [_phase(phase, Task9StartupPreflightPhaseStatus.NOT_RUN) for phase in list(Task9StartupPreflightPhase)[4:]]
    result = _result(phases)
    assert result.overall_status is status
    assert result.blocking_phase is Task9StartupPreflightPhase.PERSISTENCE_INTEGRITY_WRITABILITY
    assert not result.launch_approved


def test_not_run_order_blocking_and_identity_validation_are_strict():
    phases = [_phase(phase) for phase in Task9StartupPreflightPhase]
    phases[4] = _phase(Task9StartupPreflightPhase.MARKET_SESSION_IDENTITY, Task9StartupPreflightPhaseStatus.NOT_RUN)
    phases[5] = _phase(Task9StartupPreflightPhase.ANGEL_CREDENTIALS_SESSION, Task9StartupPreflightPhaseStatus.NOT_RUN)
    phases[6:] = [_phase(phase, Task9StartupPreflightPhaseStatus.NOT_RUN) for phase in list(Task9StartupPreflightPhase)[6:]]
    assert not _result(phases).launch_approved
    phases[5] = _phase(Task9StartupPreflightPhase.ANGEL_CREDENTIALS_SESSION)
    with pytest.raises(ValueError, match="NOT_RUN"):
        _result(phases)
    with pytest.raises(ValueError):
        _result(runtime_config_sha256="bad")
    with pytest.raises(ValueError):
        _result(runtime_config_snapshot_id="")
    with pytest.raises(ValueError):
        _result(campaign_id="")


def test_invalid_phase_shape_and_secret_content_are_rejected_and_objects_are_frozen():
    phase = _phase(Task9StartupPreflightPhase.STATIC_CONFIG_VALIDATION)
    with pytest.raises(FrozenInstanceError):
        phase.status = Task9StartupPreflightPhaseStatus.WARNING
    with pytest.raises(ValueError):
        Task9StartupPreflightPhaseResultV1(Task9StartupPreflightPhase.PAPER_SAFETY, Task9StartupPreflightPhaseStatus.PASS, True, "BAD", None, NOW)
    with pytest.raises(ValueError):
        Task9StartupPreflightPhaseResultV1(Task9StartupPreflightPhase.PAPER_SAFETY, Task9StartupPreflightPhaseStatus.FAIL_FATAL, False, "BAD", None, NOW)
    with pytest.raises(ValueError):
        Task9StartupPreflightPhaseResultV1(Task9StartupPreflightPhase.PAPER_SAFETY, Task9StartupPreflightPhaseStatus.PASS, False, "BAD", "api_key=secret", NOW)
    phases = [_phase(phase) for phase in Task9StartupPreflightPhase]
    phases[1] = phases[0]
    with pytest.raises(ValueError, match="phase order"):
        _result(phases)
    result = _result()
    with pytest.raises(FrozenInstanceError):
        result.preflight_id = "other"
    inconsistent = result.to_dict()
    inconsistent["launch_approved"] = False
    with pytest.raises(ValueError, match="derived"):
        Task9StartupPreflightResultV1.from_dict(inconsistent)
