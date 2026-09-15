from dataclasses import replace
from datetime import datetime
from zoneinfo import ZoneInfo

from services.certification.task9_runtime_safety_proof_producer import (
    produce_task9_runtime_safety_proof,
)
from services.certification.task9_runtime_safety_readiness import (
    build_task9_runtime_safety_preflight_phase,
)
from services.contracts.task9_runtime_safety_proof_v1 import (
    Task9RuntimeSafetyStatus,
)
from services.contracts.task9_startup_preflight_v1 import (
    Task9StartupPreflightPhase,
    Task9StartupPreflightPhaseStatus,
)


NOW = datetime(
    2026,
    8,
    17,
    14,
    30,
    tzinfo=ZoneInfo("Asia/Kolkata"),
)


def _runtime():
    from tests.test_task9_runtime_config_v1 import (
        _config,
    )

    return _config()


def _proof(runtime):
    return produce_task9_runtime_safety_proof(
        runtime_config=runtime,
        repository_broker="PAPER",
        repository_enable_paper_trading=True,
        repository_enable_live_trading=False,
        observed_at=NOW,
    )


def test_clear_runtime_safety_is_ready():
    proof = _proof(
        _runtime()
    )

    assert (
        proof.status
        is Task9RuntimeSafetyStatus.READY
    )

    assert (
        proof.repository_paper_safety_passed
        is True
    )

    assert (
        proof.no_broker_submission_guard_passed
        is True
    )

    assert (
        proof.new_entries_permitted
        is True
    )

    assert (
        proof.monitoring_permitted
        is True
    )


def test_emergency_halt_blocks_entries_but_preserves_monitoring():
    runtime = replace(
        _runtime(),
        emergency_halt_enabled=True,
        emergency_halt_reason=(
            "operator requested halt"
        ),
    )

    proof = _proof(
        runtime
    )

    assert (
        proof.status
        is Task9RuntimeSafetyStatus.EMERGENCY_HALTED
    )

    assert (
        proof.new_entries_permitted
        is False
    )

    assert (
        proof.monitoring_permitted
        is True
    )


def test_repository_nonpaper_broker_is_invalid():
    proof = produce_task9_runtime_safety_proof(
        runtime_config=_runtime(),
        repository_broker="ANGEL",
        repository_enable_paper_trading=True,
        repository_enable_live_trading=False,
        observed_at=NOW,
    )

    assert (
        proof.status
        is Task9RuntimeSafetyStatus.INVALID
    )

    assert (
        proof.new_entries_permitted
        is False
    )


def test_repository_live_trading_enabled_is_invalid():
    proof = produce_task9_runtime_safety_proof(
        runtime_config=_runtime(),
        repository_broker="PAPER",
        repository_enable_paper_trading=True,
        repository_enable_live_trading=True,
        observed_at=NOW,
    )

    assert (
        proof.status
        is Task9RuntimeSafetyStatus.INVALID
    )


def test_clear_runtime_builds_pass_paper_safety_phase():
    phase = (
        build_task9_runtime_safety_preflight_phase(
            proof=_proof(
                _runtime()
            )
        )
    )

    assert (
        phase.phase
        is Task9StartupPreflightPhase.PAPER_SAFETY
    )

    assert (
        phase.status
        is Task9StartupPreflightPhaseStatus.PASS
    )

    assert phase.blocking is False


def test_emergency_halt_builds_retryable_block():
    runtime = replace(
        _runtime(),
        emergency_halt_enabled=True,
        emergency_halt_reason="manual halt",
    )

    phase = (
        build_task9_runtime_safety_preflight_phase(
            proof=_proof(runtime)
        )
    )

    assert (
        phase.status
        is Task9StartupPreflightPhaseStatus.BLOCKED_RETRYABLE
    )

    assert phase.blocking is True
    assert (
        phase.metadata[
            "monitoring_permitted"
        ]
        is True
    )


def test_invalid_repository_safety_builds_fatal_block():
    proof = produce_task9_runtime_safety_proof(
        runtime_config=_runtime(),
        repository_broker="PAPER",
        repository_enable_paper_trading=False,
        repository_enable_live_trading=False,
        observed_at=NOW,
    )

    phase = (
        build_task9_runtime_safety_preflight_phase(
            proof=proof
        )
    )

    assert (
        phase.status
        is Task9StartupPreflightPhaseStatus.FAIL_FATAL
    )

    assert phase.blocking is True


def test_task9_safety_proof_remains_no_broker_and_live_ineligible():
    proof = _proof(
        _runtime()
    )

    assert (
        proof.execution_mode
        == "PAPER"
    )

    assert (
        proof.broker_order_submission
        is False
    )

    assert (
        proof.live_execution_eligible
        is False
    )
