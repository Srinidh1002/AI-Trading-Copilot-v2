from datetime import date, datetime, timezone

from dashboard.dashboard_read_model_state import (
    DECISION_OBSERVABILITY_STATE_KEY,
)
from dashboard.task9_decision_observability_sync import (
    synchronize_task9_decision_observability,
)
from services.certification.task9_active_campaign_pointer_store import (
    Task9ActiveCampaignPointerStore,
)
from services.certification.task9_live_decision_audit import (
    Task9LiveDecisionAuditStore,
)
from services.contracts.task9_campaign_manifest_v1 import (
    Task9ActiveCampaignPointerStatus,
    Task9ActiveCampaignPointerV1,
)
from services.contracts.task9_live_decision_audit_v1 import (
    Task9LiveDecisionAuditV1,
)
from services.contracts.task9_runtime_config_snapshot_v1 import (
    _SNAPSHOT_PREFIX,
)


UTC = timezone.utc


def _pointer(
    *,
    registry_root,
    campaign_root,
    run_id="run-active",
):
    return Task9ActiveCampaignPointerV1(
        campaign_id="campaign-1",
        campaign_manifest_ref="manifest-1",
        campaign_root=str(campaign_root),
        registry_root=str(registry_root),
        active_market_date=date(
            2026,
            8,
            25,
        ),
        active_official_run_id=run_id,
        run_classification=(
            "OFFICIAL_CERTIFICATION"
        ),
        runtime_config_snapshot_id=(
            f"{_SNAPSHOT_PREFIX}{'a' * 64}"
        ),
        runtime_config_sha256=(
            "a" * 64
        ),
        updated_at=datetime(
            2026,
            8,
            25,
            9,
            0,
            tzinfo=UTC,
        ),
        status=(
            Task9ActiveCampaignPointerStatus.ACTIVE
        ),
    )


def _audit(
    *,
    prediction_id,
    run_id,
    evaluated_at,
    market="NIFTY",
    exchange="NSE",
    blocker="REGIME_BLOCKED",
):
    return Task9LiveDecisionAuditV1(
        audit_id=f"audit:{prediction_id}",
        official_run_id=run_id,
        parent_cycle_id=(
            f"cycle:{prediction_id}"
        ),
        prediction_id=prediction_id,
        observation_id=(
            f"observation:{prediction_id}"
        ),
        underlying_symbol=market,
        exchange=exchange,
        evaluated_at=evaluated_at,
        disposition=(
            "POLICY_ABSTENTION"
        ),
        first_causal_blocker=blocker,
        prediction_action="NO_TRADE",
        prediction_direction="NEUTRAL",
        prediction_eligibility=(
            "INELIGIBLE"
        ),
        evaluation_present=True,
        trade_planner_reached=False,
        entry_observation_present=False,
        prediction_blockers=(
            blocker,
        ),
        provider_incident_ids=(),
        evaluation_snapshot={
            "candidate": {
                "direction": "NEUTRAL",
                "eligibility": (
                    "INELIGIBLE"
                ),
            },
        },
        selected_planning_snapshot=None,
    )


def test_sync_selects_latest_active_run_audit(
    tmp_path,
):
    registry_root = (
        tmp_path / "registry"
    )
    campaign_root = (
        tmp_path / "campaign"
    )

    Task9ActiveCampaignPointerStore(
        registry_root
    ).set(
        _pointer(
            registry_root=registry_root,
            campaign_root=campaign_root,
        )
    )

    store = Task9LiveDecisionAuditStore(
        campaign_root
        / "live-decision-audit.json"
    )

    older = _audit(
        prediction_id="prediction-older",
        run_id="run-active",
        evaluated_at=datetime(
            2026,
            8,
            25,
            9,
            20,
            tzinfo=UTC,
        ),
    )

    newer = _audit(
        prediction_id="prediction-newer",
        run_id="run-active",
        evaluated_at=datetime(
            2026,
            8,
            25,
            9,
            25,
            tzinfo=UTC,
        ),
        market="SENSEX",
        exchange="BSE",
        blocker="POLICY_INELIGIBLE",
    )

    other_run = _audit(
        prediction_id="prediction-other",
        run_id="run-old",
        evaluated_at=datetime(
            2026,
            8,
            25,
            10,
            0,
            tzinfo=UTC,
        ),
    )

    store.save(older)
    store.save(newer)
    store.save(other_run)

    state = {}

    changed = (
        synchronize_task9_decision_observability(
            state,
            registry_root=registry_root,
        )
    )

    assert changed is True

    view = state[
        DECISION_OBSERVABILITY_STATE_KEY
    ]

    assert view.market == "SENSEX"
    assert (
        view.first_blocker
        == "POLICY_INELIGIBLE"
    )


def test_sync_uses_prediction_id_tiebreak(
    tmp_path,
):
    registry_root = (
        tmp_path / "registry"
    )
    campaign_root = (
        tmp_path / "campaign"
    )

    Task9ActiveCampaignPointerStore(
        registry_root
    ).set(
        _pointer(
            registry_root=registry_root,
            campaign_root=campaign_root,
        )
    )

    store = Task9LiveDecisionAuditStore(
        campaign_root
        / "live-decision-audit.json"
    )

    when = datetime(
        2026,
        8,
        25,
        9,
        30,
        tzinfo=UTC,
    )

    store.save(
        _audit(
            prediction_id="prediction-a",
            run_id="run-active",
            evaluated_at=when,
            blocker="REGIME_BLOCKED",
        )
    )

    store.save(
        _audit(
            prediction_id="prediction-z",
            run_id="run-active",
            evaluated_at=when,
            blocker="POLICY_INELIGIBLE",
        )
    )

    state = {}

    synchronize_task9_decision_observability(
        state,
        registry_root=registry_root,
    )

    view = state[
        DECISION_OBSERVABILITY_STATE_KEY
    ]

    assert (
        view.first_blocker
        == "POLICY_INELIGIBLE"
    )


def test_sync_filters_other_official_runs(
    tmp_path,
):
    registry_root = (
        tmp_path / "registry"
    )
    campaign_root = (
        tmp_path / "campaign"
    )

    Task9ActiveCampaignPointerStore(
        registry_root
    ).set(
        _pointer(
            registry_root=registry_root,
            campaign_root=campaign_root,
        )
    )

    store = Task9LiveDecisionAuditStore(
        campaign_root
        / "live-decision-audit.json"
    )

    store.save(
        _audit(
            prediction_id="old-run",
            run_id="run-old",
            evaluated_at=datetime(
                2026,
                8,
                25,
                10,
                0,
                tzinfo=UTC,
            ),
        )
    )

    state = {}

    changed = (
        synchronize_task9_decision_observability(
            state,
            registry_root=registry_root,
        )
    )

    assert changed is False

    assert (
        DECISION_OBSERVABILITY_STATE_KEY
        not in state
    )


def test_sync_clears_stale_view_on_campaign_without_audit(
    tmp_path,
):
    registry_root = (
        tmp_path / "registry"
    )
    campaign_root = (
        tmp_path / "campaign"
    )

    Task9ActiveCampaignPointerStore(
        registry_root
    ).set(
        _pointer(
            registry_root=registry_root,
            campaign_root=campaign_root,
        )
    )

    state = {
        DECISION_OBSERVABILITY_STATE_KEY:
            "stale-view",
    }

    changed = (
        synchronize_task9_decision_observability(
            state,
            registry_root=registry_root,
        )
    )

    assert changed is True

    assert (
        DECISION_OBSERVABILITY_STATE_KEY
        not in state
    )


def test_sync_clears_stale_view_without_pointer(
    tmp_path,
):
    state = {
        DECISION_OBSERVABILITY_STATE_KEY:
            "stale-view",
    }

    changed = (
        synchronize_task9_decision_observability(
            state,
            registry_root=(
                tmp_path / "registry"
            ),
        )
    )

    assert changed is True

    assert (
        DECISION_OBSERVABILITY_STATE_KEY
        not in state
    )


def test_sync_is_idempotent(
    tmp_path,
):
    registry_root = (
        tmp_path / "registry"
    )
    campaign_root = (
        tmp_path / "campaign"
    )

    Task9ActiveCampaignPointerStore(
        registry_root
    ).set(
        _pointer(
            registry_root=registry_root,
            campaign_root=campaign_root,
        )
    )

    Task9LiveDecisionAuditStore(
        campaign_root
        / "live-decision-audit.json"
    ).save(
        _audit(
            prediction_id="prediction-1",
            run_id="run-active",
            evaluated_at=datetime(
                2026,
                8,
                25,
                9,
                30,
                tzinfo=UTC,
            ),
        )
    )

    state = {}

    assert (
        synchronize_task9_decision_observability(
            state,
            registry_root=registry_root,
        )
        is True
    )

    assert (
        synchronize_task9_decision_observability(
            state,
            registry_root=registry_root,
        )
        is False
    )


def test_sync_creates_no_observability_persistence(
    tmp_path,
):
    registry_root = (
        tmp_path / "registry"
    )
    campaign_root = (
        tmp_path / "campaign"
    )

    Task9ActiveCampaignPointerStore(
        registry_root
    ).set(
        _pointer(
            registry_root=registry_root,
            campaign_root=campaign_root,
        )
    )

    audit_path = (
        campaign_root
        / "live-decision-audit.json"
    )

    Task9LiveDecisionAuditStore(
        audit_path
    ).save(
        _audit(
            prediction_id="prediction-1",
            run_id="run-active",
            evaluated_at=datetime(
                2026,
                8,
                25,
                9,
                30,
                tzinfo=UTC,
            ),
        )
    )

    before = {
        path.relative_to(tmp_path)
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    state = {}

    synchronize_task9_decision_observability(
        state,
        registry_root=registry_root,
    )

    after = {
        path.relative_to(tmp_path)
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    assert after == before


def test_sync_keeps_paper_safety_visible(
    tmp_path,
):
    registry_root = (
        tmp_path / "registry"
    )
    campaign_root = (
        tmp_path / "campaign"
    )

    Task9ActiveCampaignPointerStore(
        registry_root
    ).set(
        _pointer(
            registry_root=registry_root,
            campaign_root=campaign_root,
        )
    )

    Task9LiveDecisionAuditStore(
        campaign_root
        / "live-decision-audit.json"
    ).save(
        _audit(
            prediction_id="prediction-1",
            run_id="run-active",
            evaluated_at=datetime(
                2026,
                8,
                25,
                9,
                30,
                tzinfo=UTC,
            ),
        )
    )

    state = {}

    synchronize_task9_decision_observability(
        state,
        registry_root=registry_root,
    )

    view = state[
        DECISION_OBSERVABILITY_STATE_KEY
    ]

    assert view.action == "NO_TRADE"
    assert view.paper_entry_reached is False

