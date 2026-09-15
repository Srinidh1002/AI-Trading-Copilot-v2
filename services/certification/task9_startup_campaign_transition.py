"""Production Task 9 first-campaign / existing-campaign transition authority."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from services.certification.task9_active_campaign_pointer_store import (
    Task9ActiveCampaignPointerStore,
)
from services.certification.task9_campaign_authority import (
    validate_task9_campaign_pointer_compatibility,
)
from services.certification.task9_campaign_index_store import (
    Task9CampaignIndexStore,
)
from services.certification.task9_campaign_manifest_store import (
    Task9CampaignManifestStore,
)
from services.certification.task9_campaign_rollover import (
    apply_task9_campaign_rollover,
    plan_task9_campaign_rollover,
)
from services.certification.task9_campaign_rollover_store import (
    Task9CampaignRolloverStore,
)
from services.certification.task9_campaign_rollover_target_run import (
    validate_task9_rollover_target_run_manifest,
)
from services.certification.task9_close_drain_state_store import (
    Task9CloseDrainStateStore,
)
from services.certification.task9_daily_report_index_scope import (
    open_task9_daily_report_index_for_run,
)
from services.certification.task9_prelaunch_campaign_supersession import (
    prepare_task9_startup_campaign_authority as prepare_task9_prelaunch_campaign_authority,
)
from services.certification.task9_official_run_manifest_store import (
    Task9OfficialRunManifestStore,
)
from services.certification.task9_runtime_config_snapshot_store import (
    Task9RuntimeConfigSnapshotStore,
)
from services.contracts.task9_campaign_manifest_v1 import (
    Task9ActiveCampaignPointerStatus,
)
from services.contracts.task9_campaign_rollover_v1 import (
    Task9CampaignRolloverAction,
    Task9CampaignRolloverReceiptStatus,
)
from services.contracts.task9_runtime_config_snapshot_v1 import (
    Task9RuntimeConfigSnapshotV1,
)
from services.contracts.task9_runtime_config_v1 import (
    Task9RuntimeConfigV1,
)
from datetime import date, datetime, timedelta

from services.certification.task9_live_collector_session_resolver import (
    get_bse_holiday_calendar,
    get_nse_holiday_calendar,
)


def next_task9_common_trading_day(*, market_date: date) -> date:
    if type(market_date) is not date:
        raise TypeError("market_date")

    nse_calendar = get_nse_holiday_calendar()
    bse_calendar = get_bse_holiday_calendar()

    candidate = market_date + timedelta(days=1)

    while True:
        if (
            candidate.weekday() < 5
            and not nse_calendar.is_holiday(candidate)
            and not bse_calendar.is_holiday(candidate)
        ):
            return candidate

        candidate += timedelta(days=1)

def _rollover_previous_official_run_publication(
    *,
    root,
    previous_run_manifest,
    target_market_date,
    evaluated_at,
    starting_capital,
):
    """Finalize eligible prior-session publication before campaign rollover."""

    from services.certification.task9_certification_publication import (
        Task9CertificationPublicationAuthority,
    )
    from services.certification.task9_live_paper_production_composition import (
        Task9ProductionPersistenceLayoutV1,
    )
    from services.certification.task9_prediction_lifecycle_outcome_store import (
        Task9PredictionLifecycleOutcomeStore,
    )
    from services.certification.task9_prediction_lifecycle_reconciliation_store import (
        Task9PredictionLifecycleReconciliationStore,
    )
    from services.certification.task9_prediction_paper_trade_binding_store import (
        Task9PredictionPaperTradeBindingStore,
    )
    from services.paper_orchestration.prediction_ledger import (
        PredictionLedger,
    )
    from services.paper_trade_repository import (
        PaperTradeRepository,
    )
    from services.paper_trading.paper_trade_persistence_service import (
        PaperTradePersistenceService,
    )

    layout = (
        Task9ProductionPersistenceLayoutV1.from_root(
            root
        )
    )

    prediction_ledger = PredictionLedger(
        layout.prediction_ledger_path
    )

    binding_store = (
        Task9PredictionPaperTradeBindingStore(
            layout.binding_store_path
        )
    )

    outcome_store = (
        Task9PredictionLifecycleOutcomeStore(
            layout.lifecycle_outcome_store_path
        )
    )

    reconciliation_store = (
        Task9PredictionLifecycleReconciliationStore(
            layout.lifecycle_reconciliation_store_path
        )
    )

    trade_persistence_service = (
        PaperTradePersistenceService(
            PaperTradeRepository(
                layout.paper_trade_repository_path
            )
        )
    )

    return (
        Task9CertificationPublicationAuthority(
            official_run_id=(
                previous_run_manifest.official_run_id
            ),
            official_start_at=(
                previous_run_manifest.official_start_at
            ),
            root=root,
            prediction_ledger=prediction_ledger,
            binding_store=binding_store,
            outcome_store=outcome_store,
            reconciliation_store=(
                reconciliation_store
            ),
            trade_persistence_service=(
                trade_persistence_service
            ),
            starting_capital=float(
                starting_capital
            ),
            run_classification=(
                previous_run_manifest.run_classification
            ),
        ).rollover(
            session_date=target_market_date,
            evaluated_at=evaluated_at,
        )
    )


def prepare_task9_startup_campaign_authority(
    *,
    runtime_config: Task9RuntimeConfigV1,
    snapshot: Task9RuntimeConfigSnapshotV1,
    observed_at: datetime,
):
    if type(runtime_config) is not Task9RuntimeConfigV1:
        raise TypeError("runtime_config")

    if type(snapshot) is not Task9RuntimeConfigSnapshotV1:
        raise TypeError("snapshot")

    if (
        not isinstance(observed_at, datetime)
        or observed_at.tzinfo is None
        or observed_at.utcoffset() is None
    ):
        raise ValueError("observed_at")

    if (
        runtime_config.execution_mode != "PAPER"
        or runtime_config.broker_order_submission is not False
        or runtime_config.live_execution_eligible is not False
        or runtime_config.run_classification
        != "OFFICIAL_CERTIFICATION"
    ):
        raise ValueError(
            "TASK9_STARTUP_CAMPAIGN_TRANSITION_REQUIRES_SAFE_OFFICIAL_PAPER"
        )

    root = Path(
        runtime_config.authoritative_persistence_root
    )

    manifest_store = Task9CampaignManifestStore(
        root
    )

    pointer_store = Task9ActiveCampaignPointerStore(
        root
    )

    manifest = manifest_store.get(
        runtime_config.campaign_id
    )

    pointer = pointer_store.get()

    # Preserve the existing prelaunch authority for:
    # - first campaign creation,
    # - orphan/conflict detection,
    # - same-day prelaunch idempotent recovery,
    # - bounded prelaunch snapshot supersession.
    #
    # A same-day restart after a canonical cross-day rollover is different:
    # the immutable campaign manifest retains campaign-creation provenance,
    # while the active pointer and official-run manifest retain the current
    # run provenance.  Recover that exact run idempotently instead of routing
    # it back through the prelaunch manifest/pointer provenance contract.
    if manifest is None or pointer is None:
        prepared = prepare_task9_prelaunch_campaign_authority(
            runtime_config=runtime_config,
            snapshot=snapshot,
            observed_at=observed_at,
        )

        return (
            prepared[0],
            prepared[1],
            None,
        )

    if (
        runtime_config.market_date
        == pointer.active_market_date
    ):
        is_post_rollover_current_run = (
            pointer.active_official_run_id
            == runtime_config.official_run_id
            and pointer.runtime_config_snapshot_id
            == snapshot.snapshot_id
            and pointer.runtime_config_sha256
            == snapshot.content_sha256
            and (
                manifest.runtime_config_snapshot_id,
                manifest.runtime_config_sha256,
            )
            != (
                pointer.runtime_config_snapshot_id,
                pointer.runtime_config_sha256,
            )
        )

        if is_post_rollover_current_run:
            validate_task9_campaign_pointer_compatibility(
                manifest,
                pointer,
                require_runtime_config_provenance_match=False,
            )

            run_manifest = (
                Task9OfficialRunManifestStore(
                    root
                ).get(
                    runtime_config.official_run_id
                )
            )

            if run_manifest is None:
                raise ValueError(
                    "TASK9_STARTUP_CURRENT_RUN_MANIFEST_MISSING"
                )

            validate_task9_rollover_target_run_manifest(
                run_manifest=run_manifest,
                campaign_id=runtime_config.campaign_id,
                market_date=runtime_config.market_date,
                official_run_id=runtime_config.official_run_id,
                runtime_config_snapshot_id=(
                    snapshot.snapshot_id
                ),
                runtime_config_sha256=(
                    snapshot.content_sha256
                ),
            )

            if (
                pointer.status
                is not
                Task9ActiveCampaignPointerStatus.ACTIVE
            ):
                raise ValueError(
                    "TASK9_STARTUP_CAMPAIGN_NOT_ACTIVE:"
                    f"{pointer.status.value}"
                )

            return (
                manifest,
                pointer,
                None,
            )

        prepared = prepare_task9_prelaunch_campaign_authority(
            runtime_config=runtime_config,
            snapshot=snapshot,
            observed_at=observed_at,
        )

        return (
            prepared[0],
            prepared[1],
            None,
        )

    validate_task9_campaign_pointer_compatibility(
        manifest,
        pointer,
        require_runtime_config_provenance_match=False,
    )

    if (
        manifest.campaign_id
        != runtime_config.campaign_id
        or pointer.campaign_id
        != runtime_config.campaign_id
    ):
        raise ValueError(
            "TASK9_STARTUP_CAMPAIGN_ID_MISMATCH"
        )

    if (
        manifest.campaign_status.value
        in {"COMPLETED", "INVALID"}
    ):
        raise ValueError(
            "TASK9_STARTUP_CAMPAIGN_TERMINAL"
        )

    if (
        pointer.status
        is not Task9ActiveCampaignPointerStatus.ACTIVE
    ):
        raise ValueError(
            "TASK9_STARTUP_CAMPAIGN_NOT_ACTIVE:"
            f"{pointer.status.value}"
        )

    # plan_task9_campaign_rollover also rejects backward dates,
    # but keep this explicit at the production transition boundary.
    if (
        runtime_config.market_date
        < pointer.active_market_date
    ):
        raise ValueError(
            "TASK9_STARTUP_BACKWARD_MARKET_DATE"
        )

    index_store = Task9CampaignIndexStore(
        root
    )

    index = index_store.get(
        runtime_config.campaign_id
    )

    if index is None:
        raise ValueError(
            "TASK9_STARTUP_CAMPAIGN_INDEX_REQUIRED_FOR_ROLLOVER"
        )

    decision = plan_task9_campaign_rollover(
        manifest=manifest,
        pointer=pointer,
        index=index,
        target_market_date=(
            runtime_config.market_date
        ),
        requested_official_run_id=(
            runtime_config.official_run_id
        ),
    )

    if (
        decision.action
        is not
        Task9CampaignRolloverAction.ADVANCE_TO_NEXT_MARKET_DAY
    ):
        raise ValueError(
            "TASK9_STARTUP_UNEXPECTED_ROLLOVER_ACTION:"
            f"{decision.action.value}"
        )

    # The pointer must never reference an in-memory-only snapshot.
    snapshot_store = Task9RuntimeConfigSnapshotStore(
        root
    )

    durable_snapshot = snapshot_store.save(
        snapshot
    )

    if durable_snapshot != snapshot:
        raise ValueError(
            "TASK9_STARTUP_RUNTIME_SNAPSHOT_VERIFICATION_FAILED"
        )

    previous_run_manifest_store = (
        Task9OfficialRunManifestStore(
            root
        )
    )

    previous_run_manifest = (
        previous_run_manifest_store.get(
            pointer.active_official_run_id
        )
    )

    if previous_run_manifest is None:
        raise ValueError(
            "TASK9_STARTUP_PREVIOUS_RUN_MANIFEST_MISSING"
        )

    _rollover_previous_official_run_publication(
        root=root,
        previous_run_manifest=(
            previous_run_manifest
        ),
        target_market_date=(
            runtime_config.market_date
        ),
        evaluated_at=observed_at,
        starting_capital=(
            runtime_config.available_capital
        ),
    )

    previous_report_index = (
        open_task9_daily_report_index_for_run(
            root=root,
            official_run_id=(
                pointer.active_official_run_id
            ),
        )
    )

    receipt = apply_task9_campaign_rollover(
        decision=decision,
        manifest=manifest,
        pointer_store=pointer_store,
        index=index,
        runtime_config=runtime_config,
        runtime_config_snapshot_id=(
            snapshot.snapshot_id
        ),
        runtime_config_sha256=(
            snapshot.content_sha256
        ),
        run_manifest_store=(
            Task9OfficialRunManifestStore(
                root
            )
        ),
        receipt_store=(
            Task9CampaignRolloverStore(
                root
            )
        ),
        observed_at=observed_at,
        close_drain_state_store=(
            Task9CloseDrainStateStore(
                root
            )
        ),
        finalized_daily_report_index=(
            previous_report_index
        ),
    )

    if (
        receipt.status
        is not Task9CampaignRolloverReceiptStatus.APPLIED
    ):
        raise ValueError(
            "TASK9_STARTUP_ROLLOVER_NOT_APPLIED"
        )

    durable_pointer = pointer_store.get()

    if durable_pointer is None:
        raise ValueError(
            "TASK9_STARTUP_TARGET_POINTER_MISSING"
        )

    if (
        durable_pointer.active_market_date
        != runtime_config.market_date
        or durable_pointer.active_official_run_id
        != runtime_config.official_run_id
        or durable_pointer.runtime_config_snapshot_id
        != snapshot.snapshot_id
        or durable_pointer.runtime_config_sha256
        != snapshot.content_sha256
        or durable_pointer.status
        is not Task9ActiveCampaignPointerStatus.ACTIVE
    ):
        raise ValueError(
            "TASK9_STARTUP_TARGET_POINTER_VERIFICATION_FAILED"
        )

    return (
        manifest,
        durable_pointer,
        receipt,
    )


__all__ = (
    "prepare_task9_startup_campaign_authority",
)
