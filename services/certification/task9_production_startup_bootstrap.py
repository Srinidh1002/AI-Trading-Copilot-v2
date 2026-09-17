"""Canonical Task 9 production startup bootstrap.

This is the only composition that may turn the already-produced Task 9
startup authorities into a durable launcher-approved preflight receipt.

Boundaries:
- no provider acquisition;
- no second Angel client;
- no WebSocket connection;
- no broker/order authority;
- no Task 8 readiness booleans;
- no fabricated provider readiness;
- no launch approval calculated outside the canonical preflight result.
"""
from __future__ import annotations

from services.certification.task9_provider_capability_report_builder import (
    build_task9_provider_capability_report,
)
from services.contracts.task9_startup_failure_semantics_v1 import (
    Task9StartupReasonCode,
    build_task9_startup_phase_result,
)

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from services.certification.task9_active_campaign_pointer_store import (
    Task9ActiveCampaignPointerStore,
)
from services.certification.task9_angel_live_proof_bundle import (
    Task9AngelLiveProofBundleV1,
    project_task9_angel_live_proof_bundle,
)
from services.certification.task9_campaign_index_store import (
    Task9CampaignIndexStore,
)
from services.certification.task9_campaign_manifest_store import (
    Task9CampaignManifestStore,
)
from services.certification.task9_campaign_preflight_bridge import (
    build_task9_campaign_preflight_phase,
)
from services.certification.task9_dashboard_active_campaign_authority import (
    build_task9_dashboard_active_campaign_preflight_phase,
    synchronize_task9_dashboard_active_campaign_projection,
)
from services.certification.task9_persistence_writability_probe import (
    produce_task9_persistence_writability_proof,
)
from services.certification.task9_persistence_writability_readiness import (
    build_task9_persistence_writability_preflight_phase,
)
from services.certification.task9_provider_aligned_startup_preflight import (
    run_task9_provider_aligned_startup_preflight,
)
from services.certification.task9_runtime_config_snapshot_store import (
    Task9RuntimeConfigSnapshotStore,
)
from services.certification.task9_runtime_safety_proof_producer import (
    produce_task9_runtime_safety_proof,
)
from services.certification.task9_runtime_safety_readiness import (
    build_task9_runtime_safety_preflight_phase,
)
from services.certification.task9_startup_preflight_orchestrator import (
    Task9StartupPreflightMode,
)
from services.certification.task9_startup_preflight_store import (
    Task9StartupPreflightStore,
)
from services.certification.task9_websocket_runtime_proof_producer import (
    produce_task9_websocket_runtime_proof,
)
from services.certification.task9_websocket_runtime_readiness import (
    build_task9_collector_runtime_preflight_phase,
    project_task9_websocket_runtime_to_report,
)
from services.contracts.provider_capability_registry_v1 import (
    ProviderCapabilityRegistryV1,
)
from services.contracts.task9_angel_capability_session_v1 import (
    Task9AngelCapabilitySessionV1,
)
from services.contracts.task9_runtime_config_snapshot_v1 import (
    Task9RuntimeConfigSnapshotV1,
    task9_runtime_config_content_sha256,
)
from services.contracts.task9_runtime_config_v1 import (
    Task9RuntimeConfigV1,
)
from services.contracts.task9_startup_preflight_v1 import (
    Task9StartupPreflightPhase,
    Task9StartupPreflightResultV1,
)


@dataclass(frozen=True, slots=True)
class Task9ProductionStartupBootstrapResultV1:
    preflight: Task9StartupPreflightResultV1
    persistence_root: str
    live_stream_root: str

    startup_preflight_id: str
    runtime_config_snapshot_id: str
    runtime_config_sha256: str
    campaign_id: str
    market_date: object
    official_run_id: str
    run_classification: str

    launch_approved: bool

    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False

    schema_version: str = (
        "task9_production_startup_bootstrap_result.v1"
    )

    def __post_init__(self) -> None:
        if (
            type(self.preflight)
            is not Task9StartupPreflightResultV1
        ):
            raise TypeError("preflight")

        if self.launch_approved is not self.preflight.launch_approved:
            raise ValueError(
                "launch approval must come only from canonical preflight"
            )

        if (
            self.execution_mode != "PAPER"
            or self.broker_order_submission is not False
            or self.live_execution_eligible is not False
        ):
            raise ValueError(
                "Task 9 bootstrap must remain PAPER-only"
            )

    def launcher_kwargs(self) -> dict[str, object]:
        if self.launch_approved is not True:
            raise ValueError(
                "TASK9_STARTUP_PREFLIGHT_NOT_APPROVED"
            )

        return {
            "persistence_root": self.persistence_root,
            "live_stream_root": self.live_stream_root,
            "official_run_id": self.official_run_id,
            "startup_preflight_id": self.startup_preflight_id,
            "runtime_config_snapshot_id": (
                self.runtime_config_snapshot_id
            ),
            "runtime_config_sha256": (
                self.runtime_config_sha256
            ),
            "campaign_id": self.campaign_id,
            "market_date": self.market_date,
            "run_classification": self.run_classification,
        }


def _aware(
    value: object,
    name: str,
) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)

    return value


def run_task9_production_startup_bootstrap(
    *,
    runtime_config: Task9RuntimeConfigV1,
    snapshot: Task9RuntimeConfigSnapshotV1,
    field_registry: ProviderCapabilityRegistryV1,
    angel_capability_session: Task9AngelCapabilitySessionV1,
    live_proof_bundle: Task9AngelLiveProofBundleV1 | None,
    preflight_id: str,
    observed_at: datetime,
    live_stream_root=None,
    startup_acquisition_failure: str | None = None,
    repository_broker="PAPER",
    repository_enable_paper_trading=True,
    repository_enable_live_trading=False,
) -> Task9ProductionStartupBootstrapResultV1:
    """Build and persist the canonical live-certification startup receipt."""

    if type(runtime_config) is not Task9RuntimeConfigV1:
        raise TypeError("runtime_config")

    if type(snapshot) is not Task9RuntimeConfigSnapshotV1:
        raise TypeError("snapshot")

    if type(field_registry) is not ProviderCapabilityRegistryV1:
        raise TypeError("field_registry")

    if (
        type(angel_capability_session)
        is not Task9AngelCapabilitySessionV1
    ):
        raise TypeError(
            "angel_capability_session"
        )

    retryable_acquisition_failures = {
        (
            "TASK9_STARTUP_NIFTY_OPTION_CAPTURE_BLOCKED:"
            "OPTION_CAPTURE_RUNTIMEERROR"
        ),
        (
            "TASK9_STARTUP_SENSEX_OPTION_CAPTURE_BLOCKED:"
            "OPTION_CAPTURE_RUNTIMEERROR"
        ),
    }

    if startup_acquisition_failure is None:
        if (
            type(live_proof_bundle)
            is not Task9AngelLiveProofBundleV1
        ):
            raise TypeError(
                "live_proof_bundle"
            )

    else:
        if (
            type(startup_acquisition_failure)
            is not str
            or startup_acquisition_failure
            not in retryable_acquisition_failures
        ):
            raise ValueError(
                "startup_acquisition_failure"
            )

        if live_proof_bundle is not None:
            raise ValueError(
                "live_proof_bundle must be None "
                "when startup acquisition is blocked"
            )

    observed_at = _aware(
        observed_at,
        "observed_at",
    )

    if (
        type(preflight_id) is not str
        or not preflight_id.strip()
    ):
        raise ValueError(
            "preflight_id"
        )

    expected_sha256 = (
        task9_runtime_config_content_sha256(
            runtime_config
        )
    )

    if (
        snapshot.runtime_config_id
        != runtime_config.runtime_config_id
        or snapshot.content_sha256
        != expected_sha256
    ):
        raise ValueError(
            "TASK9_RUNTIME_CONFIG_SNAPSHOT_MISMATCH"
        )

    persistence_root = Path(
        runtime_config.authoritative_persistence_root
    )

    stream_root = (
        Path(live_stream_root)
        if live_stream_root is not None
        else persistence_root / "live_stream"
    )

    # The exact content-addressed snapshot that preflight and launcher will
    # reference must be durable before any launch receipt can be produced.
    snapshot_store = (
        Task9RuntimeConfigSnapshotStore(
            persistence_root
        )
    )

    durable_snapshot = snapshot_store.save(
        snapshot
    )

    if durable_snapshot != snapshot:
        raise ValueError(
            "TASK9_RUNTIME_CONFIG_SNAPSHOT_NOT_DURABLE"
        )

    if startup_acquisition_failure is None:
        # A7 evaluates the actual already-produced Angel startup proofs.
        angel_projection = (
            project_task9_angel_live_proof_bundle(
                runtime_config=runtime_config,
                authority=angel_capability_session,
                bundle=live_proof_bundle,
            )
        )

        # B1 is the only authority allowed to satisfy the generic
        # WebSocket capability row.
        websocket_proof = (
            produce_task9_websocket_runtime_proof(
                live_stream_root=stream_root,
                market_date=runtime_config.market_date,
                observed_at=observed_at,
                maximum_tick_age_seconds=(
                    runtime_config.market_quote_max_age_seconds
                ),
            )
        )

        capability_report = (
            project_task9_websocket_runtime_to_report(
                report=angel_projection.report,
                proof=websocket_proof,
            )
        )

        angel_credentials_phase = (
            angel_projection.auth_readiness.phase_result
        )

    else:
        # The provider acquisition failed before a complete canonical Angel
        # live-proof bundle could be assembled.  Do not fabricate which
        # internal provider component failed and do not mark credentials as
        # invalid.  Instead fail closed at the earliest provider-readiness
        # phase whose canonical proof could not be completed.
        angel_projection = None
        websocket_proof = None

        capability_report = (
            build_task9_provider_capability_report(
                runtime_config
            )
        )

        angel_credentials_phase = (
            build_task9_startup_phase_result(
                phase=(
                    Task9StartupPreflightPhase
                    .ANGEL_CREDENTIALS_SESSION
                ),
                reason_code=(
                    Task9StartupReasonCode
                    .REQUIRED_CAPABILITY_TEMPORARILY_UNAVAILABLE
                ),
                observed_at=observed_at,
                detail=(
                    "required Angel startup acquisition unavailable "
                    "before canonical credential/session readiness "
                    "projection: "
                    f"{startup_acquisition_failure}"
                ),
            )
        )

    # B2 actual filesystem durability proof.
    persistence_proof = (
        produce_task9_persistence_writability_proof(
            persistence_root=persistence_root,
            live_stream_root=stream_root,
            observed_at=observed_at,
        )
    )

    # B4 uses the frozen Task 9 config plus existing repository PAPER guards.
    runtime_safety_proof = (
        produce_task9_runtime_safety_proof(
            runtime_config=runtime_config,
            repository_broker=repository_broker,
            repository_enable_paper_trading=(
                repository_enable_paper_trading
            ),
            repository_enable_live_trading=(
                repository_enable_live_trading
            ),
            observed_at=observed_at,
        )
    )

    manifest_store = (
        Task9CampaignManifestStore(
            persistence_root
        )
    )

    pointer_store = (
        Task9ActiveCampaignPointerStore(
            persistence_root
        )
    )

    index_store = (
        Task9CampaignIndexStore(
            persistence_root
        )
    )

    campaign_index = index_store.get(
        runtime_config.campaign_id
    )

    # B3 is derived exclusively from canonical pointer + manifest.
    # If canonical authority is absent/corrupt/mismatched, fail closed before
    # creating a misleading dashboard projection.
    dashboard_projection = (
        synchronize_task9_dashboard_active_campaign_projection(
            persistence_root=persistence_root,
            expected_campaign_id=(
                runtime_config.campaign_id
            ),
            expected_market_date=(
                runtime_config.market_date
            ),
            expected_official_run_id=(
                runtime_config.official_run_id
            ),
            expected_runtime_config_snapshot_id=(
                snapshot.snapshot_id
            ),
            expected_runtime_config_sha256=(
                snapshot.content_sha256
            ),
            observed_at=observed_at,
        )
    )

    checks = {
        Task9StartupPreflightPhase.PAPER_SAFETY: (
            lambda: build_task9_runtime_safety_preflight_phase(
                proof=runtime_safety_proof,
            )
        ),
        Task9StartupPreflightPhase.CAMPAIGN_RUN_ROOT_IDENTITY: (
            lambda: build_task9_campaign_preflight_phase(
                runtime_config=runtime_config,
                manifest_store=manifest_store,
                pointer_store=pointer_store,
                observed_at=observed_at,
                runtime_config_snapshot_id=(
                    snapshot.snapshot_id
                ),
                runtime_config_sha256=(
                    snapshot.content_sha256
                ),
                campaign_index=campaign_index,
            )
        ),
        Task9StartupPreflightPhase.PERSISTENCE_INTEGRITY_WRITABILITY: (
            lambda: build_task9_persistence_writability_preflight_phase(
                proof=persistence_proof,
            )
        ),
        Task9StartupPreflightPhase.ANGEL_CREDENTIALS_SESSION: (
            lambda: angel_credentials_phase
        ),
        Task9StartupPreflightPhase.COLLECTOR_RUNTIME_READINESS: (
            lambda: build_task9_collector_runtime_preflight_phase(
                proof=websocket_proof,
            )
        ),
        Task9StartupPreflightPhase.DASHBOARD_ACTIVE_CAMPAIGN_AUTHORITY: (
            lambda: build_task9_dashboard_active_campaign_preflight_phase(
                projection=dashboard_projection,
                expected_campaign_id=(
                    runtime_config.campaign_id
                ),
                expected_market_date=(
                    runtime_config.market_date
                ),
                expected_official_run_id=(
                    runtime_config.official_run_id
                ),
                expected_runtime_config_snapshot_id=(
                    snapshot.snapshot_id
                ),
                expected_runtime_config_sha256=(
                    snapshot.content_sha256
                ),
                observed_at=observed_at,
            )
        ),
    }

    preflight = (
        run_task9_provider_aligned_startup_preflight(
            runtime_config=runtime_config,
            snapshot=snapshot,
            field_registry=field_registry,
            angel_capability_session=(
                angel_capability_session
            ),
            capability_report=capability_report,
            preflight_id=preflight_id.strip(),
            observed_at=observed_at,
            mode=(
                Task9StartupPreflightMode.LIVE_CERTIFICATION_STARTUP
            ),
            checks=checks,
        )
    )

    # Persist the result regardless of approved/blocked state. A blocked
    # receipt is evidence, but launcher cannot use it because its own gate
    # independently requires launch_approved.
    preflight_store = (
        Task9StartupPreflightStore(
            persistence_root
        )
    )

    durable_preflight = preflight_store.save(
        preflight
    )

    if durable_preflight != preflight:
        raise ValueError(
            "TASK9_STARTUP_PREFLIGHT_NOT_DURABLE"
        )

    current_pointer = pointer_store.get()
    if current_pointer is not None and current_pointer.startup_preflight_id != preflight.preflight_id:
        from dataclasses import replace
        updated_pointer = replace(
            current_pointer,
            startup_preflight_id=preflight.preflight_id,
            updated_at=observed_at
        )
        pointer_store.set(
            updated_pointer,
            manifest=manifest_store.get(current_pointer.campaign_id),
            require_runtime_config_provenance_match=False
        )

    return Task9ProductionStartupBootstrapResultV1(
        preflight=preflight,
        persistence_root=str(
            persistence_root
        ),
        live_stream_root=str(
            stream_root
        ),
        startup_preflight_id=(
            preflight.preflight_id
        ),
        runtime_config_snapshot_id=(
            snapshot.snapshot_id
        ),
        runtime_config_sha256=(
            snapshot.content_sha256
        ),
        campaign_id=(
            runtime_config.campaign_id
        ),
        market_date=(
            runtime_config.market_date
        ),
        official_run_id=(
            runtime_config.official_run_id
        ),
        run_classification=(
            runtime_config.run_classification
        ),
        launch_approved=(
            preflight.launch_approved
        ),
        execution_mode="PAPER",
        broker_order_submission=False,
        live_execution_eligible=False,
    )


__all__ = (
    "Task9ProductionStartupBootstrapResultV1",
    "run_task9_production_startup_bootstrap",
)
