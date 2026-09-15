"""Task 9 external-provider blocker and fallback launcher coverage."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from services.certification.task9_external_provider_blocker import (
    Task9ExternalProviderBlockerStore,
)
from services.certification.task9_live_paper_certification_launcher import (
    Task9ExternalProviderBlockedError,
    Task9LivePaperCertificationLauncher,
    Task9ParentEvidenceSessionClosedError,
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
    10,
    13,
    5,
    tzinfo=timezone.utc,
)

OPEN = datetime(
    2026,
    8,
    10,
    5,
    0,
    tzinfo=timezone.utc,
)

RUN_ID = "run"
PREFLIGHT_ID = "task924-preflight"

SNAPSHOT_SHA = "9" * 64
SNAPSHOT_ID = (
    "task9-runtime-config-"
    + SNAPSHOT_SHA
)

CAMPAIGN_ID = "task924-campaign"
MARKET_DATE = NOW.date()


def _save_approved_preflight(
    root,
    *,
    now,
):
    phase_results = tuple(
        Task9StartupPreflightPhaseResultV1(
            phase,
            Task9StartupPreflightPhaseStatus.PASS,
            False,
            "TASK924_TEST_PREFLIGHT_PASS",
            None,
            now,
        )
        for phase in Task9StartupPreflightPhase
    )

    receipt = Task9StartupPreflightResultV1(
        preflight_id=PREFLIGHT_ID,
        runtime_config_snapshot_id=SNAPSHOT_ID,
        runtime_config_sha256=SNAPSHOT_SHA,
        campaign_id=CAMPAIGN_ID,
        market_date=MARKET_DATE,
        official_run_id=RUN_ID,
        run_classification=(
            "OFFICIAL_CERTIFICATION"
        ),
        started_at=now,
        completed_at=now,
        phase_results=phase_results,
    )

    store = Task9StartupPreflightStore(
        root
    )

    if store.get(PREFLIGHT_ID) is None:
        store.save(receipt)


def _launcher(
    root,
    *,
    clock,
    sleep=lambda _: None,
    task9_evidence_dependencies_factory=None,
    runtime_factory=None,
    session_state_resolver=lambda **_: object(),
):
    _save_approved_preflight(
        root,
        now=clock(),
    )

    kwargs = {
        "persistence_root": root,
        "official_run_id": RUN_ID,
        "startup_preflight_id": PREFLIGHT_ID,
        "runtime_config_snapshot_id": (
            SNAPSHOT_ID
        ),
        "runtime_config_sha256": (
            SNAPSHOT_SHA
        ),
        "campaign_id": CAMPAIGN_ID,
        "market_date": MARKET_DATE,
        "clock": clock,
        "sleep": sleep,
        "session_state_resolver": session_state_resolver,
    }

    if task9_evidence_dependencies_factory is not None:
        kwargs[
            "task9_evidence_dependencies_factory"
        ] = task9_evidence_dependencies_factory

    if runtime_factory is not None:
        kwargs[
            "runtime_factory"
        ] = runtime_factory

    return Task9LivePaperCertificationLauncher(
        **kwargs
    )


def _record_non_fallback_blocker(
    store,
    *,
    observed_at,
):
    store.record(
        RUN_ID,
        observed_at=observed_at,
        probe_result="FAILED",
        failure_reason=(
            "HISTORICAL-DATA_UNAVAILABLE"
        ),
    )


@pytest.mark.parametrize(
    "offset,code",
    (
        (
            0,
            "TASK9_EXTERNAL_PROVIDER_BLOCKER_ACTIVE",
        ),
        (
            2,
            "RECOVERY_PROBE_REQUIRED",
        ),
    ),
)
def test_active_blocker_stops_launcher_before_dependencies(
    tmp_path,
    offset,
    code,
):
    store = Task9ExternalProviderBlockerStore(
        tmp_path
    )

    _record_non_fallback_blocker(
        store,
        observed_at=(
            NOW
            if offset == 0
            else NOW - timedelta(hours=2)
        ),
    )

    calls = []

    launcher = _launcher(
        tmp_path,
        clock=lambda: (
            NOW
            + timedelta(minutes=offset)
        ),
        task9_evidence_dependencies_factory=(
            lambda **_: calls.append(1)
        ),
        runtime_factory=(
            lambda **_: calls.append(2)
        ),
    )

    with pytest.raises(
        Task9ExternalProviderBlockedError,
        match=code,
    ):
        launcher.run(
            max_cycles=1
        )

    assert calls == []

    assert not (
        tmp_path
        / "task9-live-paper.lock"
    ).exists()

    assert not list(
        tmp_path.glob(
            "task9-cycle-results/*"
        )
    )


def test_corrupt_and_wrong_run_blocker_fail_closed(
    tmp_path,
):
    store = Task9ExternalProviderBlockerStore(
        tmp_path
    )

    store.path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    store.path.write_text(
        "{}",
        encoding="utf-8",
    )

    launcher = _launcher(
        tmp_path,
        clock=lambda: NOW,
    )

    with pytest.raises(Exception):
        launcher.run(
            max_cycles=1
        )


def test_active_external_blocker_remains_higher_priority_than_closed_parent_evidence_window(
    tmp_path,
):
    store = Task9ExternalProviderBlockerStore(
        tmp_path
    )

    _record_non_fallback_blocker(
        store,
        observed_at=(
            NOW
            - timedelta(hours=2)
        ),
    )

    calls = []

    launcher = _launcher(
        tmp_path,
        clock=lambda: (
            NOW
            + timedelta(hours=9)
        ),
        task9_evidence_dependencies_factory=(
            lambda **_: calls.append(1)
        ),
        runtime_factory=(
            lambda **_: calls.append(2)
        ),
    )

    with pytest.raises(
        Task9ExternalProviderBlockedError,
        match="RECOVERY_PROBE_REQUIRED",
    ):
        launcher.run(
            max_cycles=1
        )

    assert calls == []

    assert not (
        tmp_path
        / "task9-live-paper.lock"
    ).exists()


def test_active_typed_rate_limit_selects_local_fallback_at_open_session_without_blocker_mutation(
    tmp_path,
):
    store = Task9ExternalProviderBlockerStore(
        tmp_path
    )

    before = store.record(
        RUN_ID,
        observed_at=OPEN,
    )

    selected = []

    launcher = _launcher(
        tmp_path,
        clock=lambda: OPEN,
        task9_evidence_dependencies_factory=(
            lambda **_: None
        ),
        runtime_factory=(
            lambda **_: None
        ),
    )

    launcher._startup_safety = (
        lambda: None
    )

    launcher._run_one_cycle = (
        lambda _manifest, **kwargs:
        selected.append(
            kwargs[
                "precomposed_timeframe_provider_factory"
            ]
        )
    )

    launcher.run(
        max_cycles=1
    )

    assert len(selected) == 1
    assert callable(selected[0])

    assert store.load(
        RUN_ID
    ) == before


@pytest.mark.parametrize(
    "state",
    (
        "ABSENT",
        "CLEARED",
    ),
)
def test_normal_task9_cycle_always_selects_local_provider_without_historical_rest(
    tmp_path,
    state,
):
    store = Task9ExternalProviderBlockerStore(
        tmp_path
    )

    if state == "CLEARED":
        store.record(
            RUN_ID,
            observed_at=OPEN,
        )

        before = store.clear(
            RUN_ID,
            observed_at=(
                OPEN
                + timedelta(seconds=1)
            ),
        )

    else:
        before = None

    selected = []

    launcher = _launcher(
        tmp_path,
        clock=lambda: OPEN,
        task9_evidence_dependencies_factory=(
            lambda **_: None
        ),
        runtime_factory=(
            lambda **_: None
        ),
    )

    launcher._startup_safety = (
        lambda: None
    )

    launcher._run_one_cycle = (
        lambda _manifest, **kwargs:
        selected.append(
            kwargs[
                "precomposed_timeframe_provider_factory"
            ]
        )
    )

    launcher.run(
        max_cycles=1
    )

    assert len(selected) == 1
    assert callable(selected[0])

    assert store.load(
        RUN_ID
    ) == before


def test_launcher_has_no_direct_legacy_historical_bypass():
    import services.certification.task9_live_paper_certification_launcher as launcher_module

    source = Path(
        launcher_module.__file__
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "historical_market"
        not in source
    )

    assert (
        "CompletedCandleService"
        not in source
    )


def test_active_typed_rate_limit_fallback_still_respects_closed_parent_evidence_session(
    tmp_path,
):
    store = Task9ExternalProviderBlockerStore(
        tmp_path
    )

    store.record(
        RUN_ID,
        observed_at=NOW,
    )

    calls = []

    launcher = _launcher(
        tmp_path,
        clock=lambda: NOW,
        task9_evidence_dependencies_factory=(
            lambda **_: calls.append(1)
        ),
        runtime_factory=(
            lambda **_: calls.append(2)
        ),
    )

    launcher._startup_safety = (
        lambda: None
    )

    with pytest.raises(
        Task9ParentEvidenceSessionClosedError,
        match=(
            "TASK9_PARENT_EVIDENCE_SESSION_CLOSED"
        ),
    ):
        launcher.run(
            max_cycles=1
        )

    assert calls == []
