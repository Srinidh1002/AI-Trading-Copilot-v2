"""Task 9.98B dashboard active-campaign state binding."""
from pathlib import Path


DASHBOARD = Path(
    "dashboard/dashboard_v2.py"
)


def _source():
    return DASHBOARD.read_text(
        encoding="utf-8"
    )


def test_active_campaign_sync_is_imported():
    source = _source()

    assert (
        "from dashboard.task9_active_campaign_sync import ("
        in source
    )

    assert (
        "synchronize_task9_active_campaign_projection,"
        in source
    )


def test_active_campaign_sync_runs_after_publication_and_before_reads():
    source = _source()

    publication_sync = source.index(
        "synchronize_registered_dashboard_publication("
    )

    campaign_sync = source.index(
        "synchronize_task9_active_campaign_projection("
    )

    operator_read = source.index(
        "get_operator_application_view_model("
    )

    application_read = source.index(
        "get_application_view(st.session_state)"
    )

    assert (
        publication_sync
        < campaign_sync
        < operator_read
    )

    assert (
        campaign_sync
        < application_read
    )


def test_campaign_sync_and_progress_recovery_use_same_root():
    from dashboard.dashboard_publication_sync import (
        DEFAULT_TASK9_PUBLICATION_ROOT,
    )

    source = _source()

    assert (
        DEFAULT_TASK9_PUBLICATION_ROOT
        == "data/task9"
    )

    campaign_index = source.index(
        "synchronize_task9_active_campaign_projection("
    )

    recovery_index = source.index(
        "recover_task9_durable_authorities("
    )

    campaign_window = source[
        campaign_index:
        campaign_index + 400
    ]

    recovery_window = source[
        recovery_index:
        recovery_index + 400
    ]

    assert (
        "DEFAULT_TASK9_PUBLICATION_ROOT"
        in campaign_window
    )

    assert (
        "DEFAULT_TASK9_PUBLICATION_ROOT"
        in recovery_window
    )

def test_dashboard_never_mutates_campaign_authority():
    source = _source().lower()

    for forbidden in (
        "task9activecampaignpointerstore(",
        "task9campaignmanifeststore(",
        "set_task9_active_campaign",
        "save_task9_campaign_manifest",
    ):
        assert forbidden not in source
