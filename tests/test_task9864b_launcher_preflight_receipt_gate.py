"""Task 9 launcher must require the durable approved startup receipt."""
from datetime import datetime, timezone

import pytest

from services.certification.task9_live_paper_certification_launcher import (
    Task9LivePaperCertificationLauncher,
)
from services.certification.task9_startup_preflight_store import (
    Task9StartupPreflightStore,
)
from services.contracts.task9_startup_preflight_v1 import (
    Task9StartupPreflightPhase,
    Task9StartupPreflightPhaseResultV1,
    Task9StartupPreflightPhaseStatus,
    Task9StartupPreflightResultV1,
)


NOW = datetime(
    2026,
    8,
    17,
    10,
    0,
    tzinfo=timezone.utc,
)

RUN_ID = "task9864b-run"
PREFLIGHT_ID = "task9864b-preflight"
SNAPSHOT_SHA = "b" * 64
SNAPSHOT_ID = (
    "task9-runtime-config-"
    + SNAPSHOT_SHA
)
CAMPAIGN_ID = "task9864b-campaign"
MARKET_DATE = NOW.date()


def _receipt(
    *,
    approved=True,
    official_run_id=RUN_ID,
    run_classification="OFFICIAL_CERTIFICATION",
    snapshot_id=SNAPSHOT_ID,
    snapshot_sha=SNAPSHOT_SHA,
    campaign_id=CAMPAIGN_ID,
    market_date=MARKET_DATE,
):
    phases = []

    for phase in Task9StartupPreflightPhase:
        status = (
            Task9StartupPreflightPhaseStatus.PASS
        )

        reason = "TASK9864B_TEST_PASS"

        if (
            not approved
            and phase
            is tuple(Task9StartupPreflightPhase)[-1]
        ):
            status = (
                Task9StartupPreflightPhaseStatus.NOT_RUN
            )
            reason = "PREVIOUS_PHASE_BLOCKED"

        phases.append(
            Task9StartupPreflightPhaseResultV1(
                phase,
                status,
                False,
                reason,
                None,
                NOW,
            )
        )

    return Task9StartupPreflightResultV1(
        preflight_id=PREFLIGHT_ID,
        runtime_config_snapshot_id=snapshot_id,
        runtime_config_sha256=snapshot_sha,
        campaign_id=campaign_id,
        market_date=market_date,
        official_run_id=official_run_id,
        run_classification=run_classification,
        started_at=NOW,
        completed_at=NOW,
        phase_results=tuple(phases),
    )


def _launcher(root, **overrides):
    kwargs = {
        "persistence_root": root,
        "official_run_id": RUN_ID,
        "startup_preflight_id": PREFLIGHT_ID,
        "runtime_config_snapshot_id": SNAPSHOT_ID,
        "runtime_config_sha256": SNAPSHOT_SHA,
        "campaign_id": CAMPAIGN_ID,
        "market_date": MARKET_DATE,
        "task9_evidence_dependencies_factory": (
            lambda **_: pytest.fail(
                "provider acquisition must not start"
            )
        ),
        "runtime_factory": (
            lambda **_: pytest.fail(
                "runtime must not be built"
            )
        ),
        "session_state_resolver": (
            lambda **_: pytest.fail(
                "session resolver must not be invoked "
                "before startup safety"
            )
        ),
        "clock": lambda: NOW,
        "sleep": lambda _: None,
    }

    kwargs.update(overrides)

    return Task9LivePaperCertificationLauncher(
        **kwargs
    )


def test_missing_receipt_blocks_before_live_acquisition(
    tmp_path,
):
    root = tmp_path / "task9"

    value = _launcher(root)

    with pytest.raises(
        ValueError,
        match=(
            "TASK9_STARTUP_PREFLIGHT_RECEIPT_MISSING"
        ),
    ):
        value.run(max_cycles=1)

    assert not (
        root / "task9-live-paper.lock"
    ).exists()


def test_unapproved_receipt_blocks_before_live_acquisition(
    tmp_path,
):
    root = tmp_path / "task9"

    Task9StartupPreflightStore(
        root
    ).save(
        _receipt(
            approved=False
        )
    )

    value = _launcher(root)

    with pytest.raises(
        ValueError,
        match="TASK9_STARTUP_PREFLIGHT_NOT_APPROVED",
    ):
        value.run(max_cycles=1)

    assert not (
        root / "task9-live-paper.lock"
    ).exists()


@pytest.mark.parametrize(
    "receipt_kwargs,launcher_kwargs,error",
    (
        (
            {"official_run_id": "wrong-run"},
            {},
            "TASK9_STARTUP_PREFLIGHT_RUN_ID_MISMATCH",
        ),
        (
            {
                "run_classification":
                "DIAGNOSTIC_NON_COUNTING"
            },
            {},
            "TASK9_STARTUP_PREFLIGHT_CLASSIFICATION_MISMATCH",
        ),
        (
            {
                "snapshot_id": (
                    "task9-runtime-config-"
                    + ("c" * 64)
                ),
                "snapshot_sha": "c" * 64,
            },
            {},
            "TASK9_STARTUP_PREFLIGHT_SNAPSHOT_REFERENCE_MISMATCH",
        ),
        (
            {
                "campaign_id":
                "task9864b-other-campaign"
            },
            {},
            "TASK9_STARTUP_PREFLIGHT_CAMPAIGN_MISMATCH",
        ),
        (
            {
                "market_date":
                NOW.date().replace(day=18)
            },
            {},
            "TASK9_STARTUP_PREFLIGHT_MARKET_DATE_MISMATCH",
        ),
    ),
)
def test_receipt_identity_mismatch_fails_closed(
    tmp_path,
    receipt_kwargs,
    launcher_kwargs,
    error,
):
    root = tmp_path / "task9"

    Task9StartupPreflightStore(
        root
    ).save(
        _receipt(
            **receipt_kwargs
        )
    )

    value = _launcher(
        root,
        **launcher_kwargs,
    )

    with pytest.raises(
        ValueError,
        match=error,
    ):
        value.run(max_cycles=1)

    assert not (
        root / "task9-live-paper.lock"
    ).exists()


def test_valid_receipt_reaches_existing_startup_safety(
    tmp_path,
):
    root = tmp_path / "task9"

    Task9StartupPreflightStore(
        root
    ).save(
        _receipt()
    )

    value = _launcher(root)

    reached = []

    def stop_after_receipt():
        reached.append("startup_safety")
        raise RuntimeError(
            "TASK9864B_RECEIPT_GATE_PASSED"
        )

    value._startup_safety = stop_after_receipt

    with pytest.raises(
        RuntimeError,
        match="TASK9864B_RECEIPT_GATE_PASSED",
    ):
        value.run(max_cycles=1)

    assert reached == [
        "startup_safety"
    ]

    assert not (
        root / "task9-live-paper.lock"
    ).exists()
