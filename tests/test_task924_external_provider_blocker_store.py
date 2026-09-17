import json
from datetime import datetime, timedelta, timezone

import pytest

from services.certification.task9_external_provider_blocker import (
    BLOCKER_CODE, SCHEMA_VERSION, Task9ExternalProviderBlockerError, Task9ExternalProviderBlockerStore,
)
from services.certification.task9_external_provider_recovery_probe import bootstrap_verified_blocker
from services.dashboard_read_models.task9_external_provider_blocker_view import read_task9_external_provider_blocker


NOW = datetime(2026, 8, 10, 13, 4, tzinfo=timezone.utc)


def test_store_restart_updates_and_clears_without_secrets(tmp_path):
    store = Task9ExternalProviderBlockerStore(tmp_path)
    assert store.load("run") is None
    first = store.record("run", observed_at=NOW, probe_at=NOW)
    second = Task9ExternalProviderBlockerStore(tmp_path).record("run", observed_at=NOW + timedelta(minutes=1))
    cleared = store.clear("run", observed_at=NOW + timedelta(hours=1))
    assert first["blocker_code"] == BLOCKER_CODE and first["provider"] == "ANGEL_ONE" and first["endpoint"] == "historical-data"
    assert second["first_seen_at"] == first["first_seen_at"] and second["occurrence_count"] == 2
    assert datetime.fromisoformat(first["next_probe_not_before"]) == NOW + timedelta(seconds=120)
    assert cleared["status"] == "CLEARED" and "secret" not in str(cleared).lower()


def test_consecutive_rate_limits_use_adaptive_delays_and_survive_restart(tmp_path):
    store = Task9ExternalProviderBlockerStore(tmp_path)
    states = [
        store.record("run", observed_at=NOW + timedelta(minutes=number))
        for number in range(5)
    ]

    assert [state["consecutive_rate_limit_count"] for state in states] == [1, 2, 3, 4, 5]
    assert [
        datetime.fromisoformat(state["next_probe_not_before"])
        - datetime.fromisoformat(state["last_seen_at"])
        for state in states
    ] == [
        timedelta(seconds=120),
        timedelta(seconds=300),
        timedelta(seconds=900),
        timedelta(seconds=3600),
        timedelta(seconds=3600),
    ]
    reloaded = Task9ExternalProviderBlockerStore(tmp_path).load("run")
    assert reloaded["consecutive_rate_limit_count"] == 5
    assert reloaded["occurrence_count"] == 5


def test_success_resets_rate_limit_escalation_without_resetting_evidence(tmp_path):
    store = Task9ExternalProviderBlockerStore(tmp_path)
    store.record("run", observed_at=NOW)
    second = store.record("run", observed_at=NOW + timedelta(minutes=1))
    cleared = store.clear("run", observed_at=NOW + timedelta(minutes=2))
    resumed = store.record("run", observed_at=NOW + timedelta(minutes=3))

    assert second["occurrence_count"] == 2
    assert cleared["occurrence_count"] == 2
    assert cleared["consecutive_rate_limit_count"] == 0
    assert resumed["occurrence_count"] == 3
    assert resumed["consecutive_rate_limit_count"] == 1
    assert datetime.fromisoformat(resumed["next_probe_not_before"]) == NOW + timedelta(minutes=5)


def test_generic_failure_keeps_existing_rate_limit_escalation_level(tmp_path):
    store = Task9ExternalProviderBlockerStore(tmp_path)
    store.record("run", observed_at=NOW)
    second = store.record("run", observed_at=NOW + timedelta(minutes=1))
    failed = store.record(
        "run",
        observed_at=NOW + timedelta(minutes=2),
        probe_result="FAILED",
        failure_reason="HISTORICAL-DATA_UNAVAILABLE",
        increment_occurrence=False,
    )

    assert failed["status"] == "ACTIVE"
    assert failed["occurrence_count"] == second["occurrence_count"]
    assert failed["consecutive_rate_limit_count"] == 2
    assert datetime.fromisoformat(failed["next_probe_not_before"]) == NOW + timedelta(minutes=7)


def test_active_schema_v1_blocker_migrates_without_shortening_current_delay(tmp_path):
    store = Task9ExternalProviderBlockerStore(tmp_path)
    legacy = {
        "schema_version": 1,
        "blocker_code": BLOCKER_CODE,
        "provider": "ANGEL_ONE",
        "endpoint": "historical-data",
        "status": "ACTIVE",
        "first_seen_at": NOW.isoformat(),
        "last_seen_at": NOW.isoformat(),
        "last_probe_at": None,
        "last_probe_result": "RATE_LIMITED",
        "last_failure_reason": "HISTORICAL-DATA_RATE_LIMITED",
        "next_probe_not_before": (NOW + timedelta(hours=1)).isoformat(),
        "occurrence_count": 7,
        "official_run_id": "run",
    }
    store.path.write_text(json.dumps(legacy), encoding="utf-8")

    with pytest.raises(Task9ExternalProviderBlockerError, match="REBASE_NOT_ALLOWED"):
        store.rebase_active_rate_limit_probe_schedule("run")

    migrated = store.load("run")
    persisted = json.loads(store.path.read_text(encoding="utf-8"))

    assert migrated["schema_version"] == SCHEMA_VERSION
    assert migrated["occurrence_count"] == 7
    assert migrated["consecutive_rate_limit_count"] == 1
    assert migrated["next_probe_not_before"] == legacy["next_probe_not_before"]
    assert persisted == migrated

    rebased = store.rebase_active_rate_limit_probe_schedule("run")
    assert rebased["next_probe_not_before"] == (
        NOW + timedelta(seconds=120)
    ).isoformat()
    assert rebased["occurrence_count"] == legacy["occurrence_count"]


@pytest.mark.parametrize(
    ("level", "expected_delay_seconds"),
    ((1, 120), (2, 300), (3, 900), (4, 3600), (5, 3600)),
)
def test_rebase_active_rate_limit_hold_uses_adaptive_delay_and_preserves_evidence(
    tmp_path,
    level,
    expected_delay_seconds,
):
    store = Task9ExternalProviderBlockerStore(tmp_path)
    state = None
    for offset in range(level):
        state = store.record("run", observed_at=NOW + timedelta(minutes=offset))

    state = dict(state)
    last_seen_at = datetime.fromisoformat(state["last_seen_at"])
    state["next_probe_not_before"] = (
        last_seen_at + timedelta(hours=2)
    ).isoformat()
    store._write(state)

    rebased = store.rebase_active_rate_limit_probe_schedule("run")

    assert datetime.fromisoformat(rebased["next_probe_not_before"]) == (
        last_seen_at + timedelta(seconds=expected_delay_seconds)
    )
    assert {
        key: value
        for key, value in rebased.items()
        if key != "next_probe_not_before"
    } == {
        key: value
        for key, value in state.items()
        if key != "next_probe_not_before"
    }
    assert store.rebase_active_rate_limit_probe_schedule("run") == rebased


def test_rebase_never_extends_an_already_shorter_active_hold(tmp_path):
    store = Task9ExternalProviderBlockerStore(tmp_path)
    state = store.record("run", observed_at=NOW)
    shorter = dict(state)
    shorter["next_probe_not_before"] = (NOW + timedelta(seconds=60)).isoformat()
    store._write(shorter)

    assert store.rebase_active_rate_limit_probe_schedule("run") == shorter


def test_rebase_rejects_ineligible_blockers_and_wrong_run_id(tmp_path):
    store = Task9ExternalProviderBlockerStore(tmp_path)
    store.record(
        "run",
        observed_at=NOW,
        probe_result="FAILED",
        failure_reason="HISTORICAL-DATA_UNAVAILABLE",
        increment_occurrence=False,
    )
    with pytest.raises(Task9ExternalProviderBlockerError, match="REBASE_NOT_ALLOWED"):
        store.rebase_active_rate_limit_probe_schedule("run")

    store = Task9ExternalProviderBlockerStore(tmp_path / "cleared")
    store.record("run", observed_at=NOW)
    store.clear("run", observed_at=NOW + timedelta(minutes=1))
    with pytest.raises(Task9ExternalProviderBlockerError, match="REBASE_NOT_ALLOWED"):
        store.rebase_active_rate_limit_probe_schedule("run")

    store = Task9ExternalProviderBlockerStore(tmp_path / "wrong-run")
    store.record("run", observed_at=NOW)
    with pytest.raises(Task9ExternalProviderBlockerError):
        store.rebase_active_rate_limit_probe_schedule("other")


def test_store_corruption_and_run_mismatch_fail_closed(tmp_path):
    store = Task9ExternalProviderBlockerStore(tmp_path)
    store.path.parent.mkdir(parents=True, exist_ok=True); store.path.write_text("{}", encoding="utf-8")
    with pytest.raises(Task9ExternalProviderBlockerError): store.load("run")
    store.path.unlink(); store.record("run", observed_at=NOW)
    with pytest.raises(Task9ExternalProviderBlockerError): store.load("other")


def test_bootstrap_is_idempotent_and_dashboard_projection_is_read_only(tmp_path):
    first = bootstrap_verified_blocker(persistence_root=tmp_path, official_run_id="run", observed_at=NOW)
    second = bootstrap_verified_blocker(persistence_root=tmp_path, official_run_id="run", observed_at=NOW + timedelta(minutes=1))
    view = read_task9_external_provider_blocker(persistence_root=tmp_path, official_run_id="run")
    assert second == first and view["status"] == "ACTIVE" and "official_run_id" not in view


def test_probe_lease_rejects_fresh_loser_and_recovers_stale(tmp_path):
    clock = [100.0]
    store = Task9ExternalProviderBlockerStore(tmp_path, time_function=lambda: clock[0])
    store.acquire_probe_lease()
    with pytest.raises(Task9ExternalProviderBlockerError): store.acquire_probe_lease(stale_after_seconds=20)
    clock[0] = 121.0
    store.acquire_probe_lease(stale_after_seconds=20)
    store.release_probe_lease()
