from dataclasses import replace

import pytest

from services.certification.task9_active_campaign_pointer_store import (
    Task9ActiveCampaignPointerStore,
)
from services.certification.task9_angel_capability_session_builder import (
    build_task9_angel_capability_session,
)
from services.certification.task9_campaign_manifest_store import (
    Task9CampaignManifestStore,
)
from services.certification.task9_production_startup_bootstrap import (
    run_task9_production_startup_bootstrap,
)
from services.certification.task9_runtime_config_snapshot_store import (
    Task9RuntimeConfigSnapshotStore,
)
from services.certification.task9_startup_preflight_store import (
    Task9StartupPreflightStore,
)
from services.contracts.provider_capability_registry_v1 import (
    default_provider_capability_registry,
)
from services.contracts.task9_campaign_manifest_v1 import (
    Task9ActiveCampaignPointerStatus,
)
from services.contracts.task9_runtime_config_snapshot_v1 import (
    build_task9_runtime_config_snapshot,
)
from services.contracts.task9_startup_preflight_v1 import (
    Task9StartupPreflightPhase,
)
from tests.test_task9_active_campaign_pointer_store import (
    _manifest,
    _pointer,
)
from tests.test_task9_runtime_config_snapshot_v1 import (
    _config,
)
from tests.test_task9865a7_angel_live_proof_bundle import (
    _bundle,
)
from tests.test_task9865b1_websocket_runtime_readiness import (
    NOW,
    _lock,
    _seed,
)


PREFLIGHT_ID = (
    "task9865c1-production-bootstrap"
)


def _runtime(
    tmp_path,
    **changes,
):
    value = replace(
        _config(),
        authoritative_persistence_root=str(
            tmp_path
        ),
        dashboard_publication_location=str(
            tmp_path
            / "dashboard"
        ),
    )

    if changes:
        value = replace(
            value,
            **changes,
        )

    return value


def _seed_campaign(
    root,
    runtime,
    snapshot,
):
    manifest = replace(
        _manifest(),
        campaign_id=runtime.campaign_id,
        created_market_date=(
            runtime.market_date
        ),
        runtime_config_snapshot_id=(
            snapshot.snapshot_id
        ),
        runtime_config_sha256=(
            snapshot.content_sha256
        ),
    )

    pointer = replace(
        _pointer(),
        campaign_id=runtime.campaign_id,
        active_market_date=(
            runtime.market_date
        ),
        active_official_run_id=(
            runtime.official_run_id
        ),
        runtime_config_snapshot_id=(
            snapshot.snapshot_id
        ),
        runtime_config_sha256=(
            snapshot.content_sha256
        ),
        updated_at=NOW,
        status=(
            Task9ActiveCampaignPointerStatus.ACTIVE
        ),
    )

    # Pointer/manifest root identity must stay canonical and equal.
    pointer = replace(
        pointer,
        registry_root=manifest.registry_root,
        campaign_root=manifest.campaign_root,
    )

    Task9CampaignManifestStore(
        root
    ).save(
        manifest
    )

    Task9ActiveCampaignPointerStore(
        root
    ).set(
        pointer,
        manifest=manifest,
    )

    return manifest, pointer


def _seed_websocket(
    root,
    *,
    market_date,
):
    from datetime import datetime, time, timedelta
    from zoneinfo import ZoneInfo

    from services.market.task9_live_tick_stream import (
        Task9LiveTickJournal,
        normalize_task9_websocket_tick,
    )
    from tests.test_task9865b1_websocket_runtime_readiness import (
        _open_state,
    )

    stream = (
        root
        / "live_stream"
    )

    _lock(
        stream
    )

    zone = ZoneInfo(
        "Asia/Kolkata"
    )

    observed_at = datetime.combine(
        market_date,
        time(12, 0),
        tzinfo=zone,
    )

    journal = Task9LiveTickJournal(
        stream,
        session_state_resolver=_open_state,
    )

    for exchange, token, price in (
        ("NSE", "99926000", 25000.0),
        ("BSE", "99919000", 80000.0),
    ):
        timestamp = (
            observed_at
            - timedelta(seconds=1)
        )

        journal.append(
            normalize_task9_websocket_tick(
                exchange=exchange,
                symbol_token=token,
                provider_timestamp=timestamp,
                received_at=timestamp,
                ltp=price,
            )
        )

    return (
        stream,
        observed_at,
    )


def _bootstrap(
    tmp_path,
    *,
    runtime_changes=None,
    seed_websocket=True,
):
    runtime = _runtime(
        tmp_path,
        **(
            runtime_changes
            or {}
        ),
    )

    snapshot = (
        build_task9_runtime_config_snapshot(
            runtime
        )
    )

    _seed_campaign(
        tmp_path,
        runtime,
        snapshot,
    )

    stream = (
        tmp_path
        / "live_stream"
    )

    observed_at = NOW

    if seed_websocket:
        (
            stream,
            observed_at,
        ) = _seed_websocket(
            tmp_path,
            market_date=runtime.market_date,
        )

    result = (
        run_task9_production_startup_bootstrap(
            runtime_config=runtime,
            snapshot=snapshot,
            field_registry=(
                default_provider_capability_registry()
            ),
            angel_capability_session=(
                build_task9_angel_capability_session()
            ),
            live_proof_bundle=_bundle(),
            preflight_id=PREFLIGHT_ID,
            observed_at=observed_at,
            live_stream_root=stream,
            repository_broker="PAPER",
            repository_enable_paper_trading=True,
            repository_enable_live_trading=False,
        )
    )

    return (
        runtime,
        snapshot,
        result,
    )


def test_complete_authorities_create_durable_approved_receipt(
    tmp_path,
):
    runtime, snapshot, result = (
        _bootstrap(
            tmp_path
        )
    )

    assert result.launch_approved is True
    assert (
        result.preflight.launch_approved
        is True
    )

    durable = (
        Task9StartupPreflightStore(
            tmp_path
        ).get(
            PREFLIGHT_ID
        )
    )

    assert durable == result.preflight

    assert (
        durable.runtime_config_snapshot_id
        == snapshot.snapshot_id
    )

    assert (
        durable.runtime_config_sha256
        == snapshot.content_sha256
    )

    assert (
        durable.campaign_id
        == runtime.campaign_id
    )

    assert (
        durable.market_date
        == runtime.market_date
    )

    assert (
        durable.official_run_id
        == runtime.official_run_id
    )


def test_bootstrap_persists_exact_content_addressed_snapshot(
    tmp_path,
):
    _, snapshot, _ = (
        _bootstrap(
            tmp_path
        )
    )

    durable = (
        Task9RuntimeConfigSnapshotStore(
            tmp_path
        ).get(
            snapshot.snapshot_id
        )
    )

    assert durable == snapshot


def test_launcher_kwargs_are_exact_canonical_provenance(
    tmp_path,
):
    runtime, snapshot, result = (
        _bootstrap(
            tmp_path
        )
    )

    kwargs = (
        result.launcher_kwargs()
    )

    assert kwargs == {
        "persistence_root": str(
            tmp_path
        ),
        "live_stream_root": str(
            tmp_path
            / "live_stream"
        ),
        "official_run_id": (
            runtime.official_run_id
        ),
        "startup_preflight_id": (
            PREFLIGHT_ID
        ),
        "runtime_config_snapshot_id": (
            snapshot.snapshot_id
        ),
        "runtime_config_sha256": (
            snapshot.content_sha256
        ),
        "campaign_id": (
            runtime.campaign_id
        ),
        "market_date": (
            runtime.market_date
        ),
        "run_classification": (
            runtime.run_classification
        ),
    }


def test_missing_websocket_evidence_never_approves_launch(
    tmp_path,
):
    _, _, result = (
        _bootstrap(
            tmp_path,
            seed_websocket=False,
        )
    )

    assert (
        result.launch_approved
        is False
    )

    assert (
        result.preflight.launch_approved
        is False
    )

    assert (
        result.preflight.blocking_phase
        is Task9StartupPreflightPhase.REQUIRED_ANGEL_CAPABILITY_READINESS
    )

    blocking_result = next(
        phase
        for phase in result.preflight.phase_results
        if phase.phase
        is Task9StartupPreflightPhase.REQUIRED_ANGEL_CAPABILITY_READINESS
    )

    assert (
        blocking_result.reason_code
        == "REQUIRED_CAPABILITY_TEMPORARILY_UNAVAILABLE"
    )

    durable = (
        Task9StartupPreflightStore(
            tmp_path
        ).get(
            PREFLIGHT_ID
        )
    )

    assert durable is not None
    assert durable.launch_approved is False

    with pytest.raises(
        ValueError,
        match="PREFLIGHT_NOT_APPROVED",
    ):
        result.launcher_kwargs()


def test_emergency_halt_never_approves_new_start(
    tmp_path,
):
    _, _, result = (
        _bootstrap(
            tmp_path,
            runtime_changes={
                "emergency_halt_enabled": True,
                "emergency_halt_reason": (
                    "operator requested halt"
                ),
            },
        )
    )

    assert (
        result.launch_approved
        is False
    )

    assert (
        result.preflight.blocking_phase
        is Task9StartupPreflightPhase.PAPER_SAFETY
    )

    with pytest.raises(
        ValueError,
        match="PREFLIGHT_NOT_APPROVED",
    ):
        result.launcher_kwargs()


def test_repository_live_trading_enabled_is_fatal_and_not_approved(
    tmp_path,
):
    runtime = _runtime(
        tmp_path
    )

    snapshot = (
        build_task9_runtime_config_snapshot(
            runtime
        )
    )

    _seed_campaign(
        tmp_path,
        runtime,
        snapshot,
    )

    (
        _,
        observed_at,
    ) = _seed_websocket(
        tmp_path,
        market_date=runtime.market_date,
    )

    result = (
        run_task9_production_startup_bootstrap(
            runtime_config=runtime,
            snapshot=snapshot,
            field_registry=(
                default_provider_capability_registry()
            ),
            angel_capability_session=(
                build_task9_angel_capability_session()
            ),
            live_proof_bundle=_bundle(),
            preflight_id=PREFLIGHT_ID,
            observed_at=observed_at,
            live_stream_root=(
                tmp_path
                / "live_stream"
            ),
            repository_broker="PAPER",
            repository_enable_paper_trading=True,
            repository_enable_live_trading=True,
        )
    )

    assert (
        result.launch_approved
        is False
    )

    assert (
        result.preflight.blocking_phase
        is Task9StartupPreflightPhase.PAPER_SAFETY
    )


def test_snapshot_mismatch_fails_before_receipt_creation(
    tmp_path,
):
    runtime = _runtime(
        tmp_path
    )

    correct = (
        build_task9_runtime_config_snapshot(
            runtime
        )
    )

    changed_runtime = replace(
        runtime,
        parent_cycle_cadence_seconds=(
            runtime.parent_cycle_cadence_seconds
            + 1.0
        ),
    )

    mismatched = (
        build_task9_runtime_config_snapshot(
            changed_runtime
        )
    )

    with pytest.raises(
        ValueError,
        match="SNAPSHOT_MISMATCH",
    ):
        run_task9_production_startup_bootstrap(
            runtime_config=runtime,
            snapshot=mismatched,
            field_registry=(
                default_provider_capability_registry()
            ),
            angel_capability_session=(
                build_task9_angel_capability_session()
            ),
            live_proof_bundle=_bundle(),
            preflight_id=PREFLIGHT_ID,
            observed_at=NOW,
            live_stream_root=(
                tmp_path
                / "live_stream"
            ),
        )

    assert (
        Task9StartupPreflightStore(
            tmp_path
        ).get(
            PREFLIGHT_ID
        )
        is None
    )

    assert (
        Task9RuntimeConfigSnapshotStore(
            tmp_path
        ).get(
            correct.snapshot_id
        )
        is None
    )


def test_bootstrap_result_remains_paper_only(
    tmp_path,
):
    _, _, result = (
        _bootstrap(
            tmp_path
        )
    )

    assert (
        result.execution_mode
        == "PAPER"
    )

    assert (
        result.broker_order_submission
        is False
    )

    assert (
        result.live_execution_eligible
        is False
    )
