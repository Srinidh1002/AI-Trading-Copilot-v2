from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import services.certification.task9_external_provider_recovery_probe as recovery_probe

from services.certification.task9_external_provider_blocker import (
    ACTIVE,
    CLEARED,
    RUNTIME_INCIDENT_LEDGER_FILE_NAME,
    Task9ExternalProviderBlockerError,
    Task9ExternalProviderBlockerStore,
)
from services.certification.task9_external_provider_recovery_probe import (
    record_verified_runtime_rate_limit,
)
from services.certification.task9_live_paper_certification_launcher import (
    Task9ExternalProviderBlockedError,
    Task9LivePaperCertificationLauncher,
)


NOW = datetime(2026, 8, 10, 13, 5, tzinfo=timezone.utc)


def _incident(value="one"):
    return (
        "task9-provider-incident:"
        f"observation-{value}:NSE:historical-data:5m:"
        "HISTORICAL-DATA_RATE_LIMITED"
    )


def _write_valid_startup_preflight(root):
    from services.certification.task9_startup_preflight_store import (
        Task9StartupPreflightStore,
    )
    from services.contracts.task9_startup_preflight_v1 import (
        Task9StartupPreflightPhase,
        Task9StartupPreflightPhaseResultV1,
        Task9StartupPreflightPhaseStatus,
        Task9StartupPreflightResultV1,
    )

    sha = "a" * 64

    receipt = Task9StartupPreflightResultV1(
        preflight_id="task9102-preflight",
        runtime_config_snapshot_id=(
            "task9-runtime-config-" + sha
        ),
        runtime_config_sha256=sha,
        campaign_id="task9102-campaign",
        market_date=NOW.date(),
        official_run_id="run",
        run_classification="OFFICIAL_CERTIFICATION",
        started_at=NOW,
        completed_at=NOW,
        phase_results=tuple(
            Task9StartupPreflightPhaseResultV1(
                phase,
                Task9StartupPreflightPhaseStatus.PASS,
                False,
                "TASK9102_TEST_PASS",
                None,
                NOW,
            )
            for phase in Task9StartupPreflightPhase
        ),
    )

    Task9StartupPreflightStore(
        root
    ).save(receipt)


def _launcher(root):
    return Task9LivePaperCertificationLauncher(
        persistence_root=root,
        official_run_id="run",
            startup_preflight_id="task9102-preflight",
            runtime_config_snapshot_id="task9-runtime-config-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            runtime_config_sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            campaign_id="task9102-campaign",
            market_date=NOW.date(),
        clock=lambda: NOW,
        sleep=lambda _: None,
    )


def _handoffs(*incident_groups):
    return {
        identity: SimpleNamespace(
            provider_incidents=tuple(
                SimpleNamespace(incident_id=incident_id)
                for incident_id in incidents
            )
        )
        for identity, incidents in zip(
            (("NIFTY", "NSE"), ("SENSEX", "BSE")),
            incident_groups,
            strict=True,
        )
    }


def test_runtime_incident_ledger_is_durable_and_idempotent(tmp_path):
    store = Task9ExternalProviderBlockerStore(tmp_path)
    first = store.record_runtime_rate_limit(
        "run", observed_at=NOW, incident_id=_incident()
    )
    duplicate = Task9ExternalProviderBlockerStore(
        tmp_path
    ).record_runtime_rate_limit(
        "run", observed_at=NOW + timedelta(minutes=1), incident_id=_incident()
    )

    assert first["status"] == ACTIVE
    assert first["occurrence_count"] == 1
    assert first["consecutive_rate_limit_count"] == 1
    assert duplicate == first
    assert (tmp_path / RUNTIME_INCIDENT_LEDGER_FILE_NAME).exists()


@pytest.mark.parametrize(
    "document",
    ("{", '{"schema_version":2,"official_run_id":"run","incidents":{}}'),
)
def test_runtime_incident_ledger_corruption_fails_closed(tmp_path, document):
    ledger = tmp_path / RUNTIME_INCIDENT_LEDGER_FILE_NAME
    ledger.write_text(document, encoding="utf-8")
    store = Task9ExternalProviderBlockerStore(tmp_path)
    with pytest.raises(Task9ExternalProviderBlockerError):
        store.record_runtime_rate_limit("run", observed_at=NOW, incident_id=_incident())


def test_runtime_rate_limit_reactivates_without_fabricating_probe(tmp_path):
    store = Task9ExternalProviderBlockerStore(tmp_path)
    original = store.record("run", observed_at=NOW, probe_at=NOW)
    cleared = store.clear("run", observed_at=NOW + timedelta(minutes=1))
    result = store.record_runtime_rate_limit(
        "run", observed_at=NOW + timedelta(minutes=2), incident_id=_incident()
    )

    assert cleared["status"] == CLEARED
    assert result["status"] == ACTIVE
    assert result["first_seen_at"] == original["first_seen_at"]
    assert result["last_probe_at"] == cleared["last_probe_at"]
    assert result["last_probe_result"] == "SUCCESS"
    assert result["official_run_id"] == "run"
    assert result["occurrence_count"] == original["occurrence_count"] + 1
    assert result["consecutive_rate_limit_count"] == 1
    assert datetime.fromisoformat(result["next_probe_not_before"]) == NOW + timedelta(minutes=4)


def test_launcher_retains_unique_incidents_only(tmp_path):
    launcher = _launcher(tmp_path)
    launcher._record_retained_runtime_provider_incidents(
        handoffs=_handoffs((_incident(),), (_incident(),)), observed_at=NOW
    )
    first = Task9ExternalProviderBlockerStore(tmp_path).load("run")
    launcher._record_retained_runtime_provider_incidents(
        handoffs=_handoffs((_incident("two"),), ()), observed_at=NOW
    )
    second = Task9ExternalProviderBlockerStore(tmp_path).load("run")

    assert first["occurrence_count"] == 1
    assert second["occurrence_count"] == 2


def test_launcher_no_incident_does_not_mutate_blocker(tmp_path):
    _launcher(tmp_path)._record_retained_runtime_provider_incidents(
        handoffs=_handoffs((), ()), observed_at=NOW
    )
    assert Task9ExternalProviderBlockerStore(tmp_path).load("run") is None
def test_runtime_reactivation_blocks_launcher_before_provider_work(tmp_path):
    _write_valid_startup_preflight(tmp_path)

    Task9ExternalProviderBlockerStore(tmp_path).record(
        "run",
        observed_at=NOW,
        probe_at=NOW,
        probe_result="FAILED",
        failure_reason="HISTORICAL-DATA_UNAVAILABLE",
    )

    provider_work = []

    launcher = Task9LivePaperCertificationLauncher(
        persistence_root=tmp_path,
        official_run_id="run",
            startup_preflight_id="task9102-preflight",
            runtime_config_snapshot_id="task9-runtime-config-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            runtime_config_sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            campaign_id="task9102-campaign",
            market_date=NOW.date(),
        clock=lambda: NOW,
        sleep=lambda _: None,
        task9_evidence_dependencies_factory=lambda **_: provider_work.append("task8"),
        runtime_factory=lambda **_: provider_work.append("runtime"),
        session_state_resolver=lambda **_: object(),
    )

    with pytest.raises(Task9ExternalProviderBlockedError):
        launcher.run(max_cycles=1)

    assert provider_work == []
def test_operator_runtime_record_is_zero_provider_side_effect(tmp_path, monkeypatch):
    def provider_must_not_be_called():
        raise AssertionError("operator record path made a provider call")

    monkeypatch.setattr(
        recovery_probe,
        "get_certification_market_client",
        provider_must_not_be_called,
    )
    result = record_verified_runtime_rate_limit(
        persistence_root=tmp_path,
        official_run_id="run",
            observed_at=NOW,
        incident_id=_incident(),
    )
    duplicate = record_verified_runtime_rate_limit(
        persistence_root=tmp_path,
        official_run_id="run",
            observed_at=NOW + timedelta(minutes=1),
        incident_id=_incident(),
    )

    assert result["last_probe_at"] is None
    assert result["last_probe_result"] is None
    assert duplicate == result
    assert not (tmp_path / "task9-external-provider-probe.lock").exists()
    assert not list(tmp_path.glob("task9-cycle-results/*"))
