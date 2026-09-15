from datetime import datetime
from zoneinfo import ZoneInfo

from services.certification.task9_persistence_writability_probe import (
    produce_task9_persistence_writability_proof,
)
from services.certification.task9_persistence_writability_readiness import (
    build_task9_persistence_writability_preflight_phase,
)
from services.contracts.task9_persistence_writability_proof_v1 import (
    Task9PersistenceProbeStatus,
)
from services.contracts.task9_startup_preflight_v1 import (
    Task9StartupPreflightPhase,
    Task9StartupPreflightPhaseStatus,
)


NOW = datetime(
    2026,
    8,
    17,
    12,
    30,
    tzinfo=ZoneInfo("Asia/Kolkata"),
)


def test_real_three_root_probe_is_ready_and_leaves_no_artifacts(
    tmp_path,
):
    persistence = (
        tmp_path
        / "persistence"
    )

    live_stream = (
        tmp_path
        / "stream"
    )

    proof = (
        produce_task9_persistence_writability_proof(
            persistence_root=persistence,
            live_stream_root=live_stream,
            observed_at=NOW,
        )
    )

    assert (
        proof.status
        is Task9PersistenceProbeStatus.READY
    )

    assert all(
        item.ready
        for item in proof.roots
    )

    assert {
        item.root_kind
        for item in proof.roots
    } == {
        "PERSISTENCE_ROOT",
        "STARTUP_PREFLIGHT_ROOT",
        "LIVE_STREAM_ROOT",
    }

    leftovers = tuple(
        tmp_path.rglob(
            ".task9-writability-*"
        )
    )

    assert leftovers == ()


def test_probe_does_not_modify_existing_files(
    tmp_path,
):
    persistence = (
        tmp_path
        / "persistence"
    )

    persistence.mkdir()

    existing = (
        persistence
        / "official-record.json"
    )

    existing.write_text(
        '{"authority":"existing"}',
        encoding="utf-8",
    )

    before = existing.read_bytes()

    proof = (
        produce_task9_persistence_writability_proof(
            persistence_root=persistence,
            live_stream_root=(
                tmp_path
                / "stream"
            ),
            observed_at=NOW,
        )
    )

    assert (
        proof.status
        is Task9PersistenceProbeStatus.READY
    )

    assert existing.read_bytes() == before


def test_file_instead_of_persistence_directory_blocks(
    tmp_path,
):
    persistence = (
        tmp_path
        / "not-a-directory"
    )

    persistence.write_text(
        "occupied",
        encoding="utf-8",
    )

    proof = (
        produce_task9_persistence_writability_proof(
            persistence_root=persistence,
            live_stream_root=(
                tmp_path
                / "stream"
            ),
            observed_at=NOW,
        )
    )

    assert (
        proof.status
        is Task9PersistenceProbeStatus.BLOCKED_RETRYABLE
    )

    failed = {
        item.root_kind
        for item in proof.roots
        if not item.ready
    }

    assert "PERSISTENCE_ROOT" in failed
    assert "STARTUP_PREFLIGHT_ROOT" in failed


def test_ready_proof_builds_pass_preflight_phase(
    tmp_path,
):
    proof = (
        produce_task9_persistence_writability_proof(
            persistence_root=(
                tmp_path
                / "persistence"
            ),
            live_stream_root=(
                tmp_path
                / "stream"
            ),
            observed_at=NOW,
        )
    )

    phase = (
        build_task9_persistence_writability_preflight_phase(
            proof=proof,
        )
    )

    assert (
        phase.phase
        is Task9StartupPreflightPhase.PERSISTENCE_INTEGRITY_WRITABILITY
    )

    assert (
        phase.status
        is Task9StartupPreflightPhaseStatus.PASS
    )

    assert phase.blocking is False


def test_blocked_proof_builds_retryable_blocking_phase(
    tmp_path,
):
    persistence = (
        tmp_path
        / "occupied"
    )

    persistence.write_text(
        "not-directory",
        encoding="utf-8",
    )

    proof = (
        produce_task9_persistence_writability_proof(
            persistence_root=persistence,
            live_stream_root=(
                tmp_path
                / "stream"
            ),
            observed_at=NOW,
        )
    )

    phase = (
        build_task9_persistence_writability_preflight_phase(
            proof=proof,
        )
    )

    assert (
        phase.status
        is Task9StartupPreflightPhaseStatus.BLOCKED_RETRYABLE
    )

    assert phase.blocking is True


def test_probe_remains_paper_only(
    tmp_path,
):
    proof = (
        produce_task9_persistence_writability_proof(
            persistence_root=(
                tmp_path
                / "persistence"
            ),
            live_stream_root=(
                tmp_path
                / "stream"
            ),
            observed_at=NOW,
        )
    )

    assert proof.execution_mode == "PAPER"
    assert proof.broker_order_submission is False
    assert proof.live_execution_eligible is False
