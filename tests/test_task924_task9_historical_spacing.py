"""Deterministic Task 9-only historical request spacing coverage."""
from __future__ import annotations

from pathlib import Path

from services.certification.task9_live_paper_certification_launcher import (
    Task9LivePaperCertificationLauncher,
    _TASK9_HISTORICAL_INTER_REQUEST_SECONDS,
)
from services.historical_request_gate import HistoricalRequestGate
from services.market.live_multi_timeframe_data import LiveMultiTimeframeData
from services.broker.shared_client import (
    get_shared_request_controller,
    reset_shared_market_clients_for_testing,
)


def test_task9_launcher_passes_explicit_five_second_spacing(tmp_path):
    received = {}

    def factory(**kwargs):
        received.update(kwargs)
        return object()

    launcher = Task9LivePaperCertificationLauncher(
        persistence_root=tmp_path,
        official_run_id="run",
            startup_preflight_id="task9102-preflight",
            runtime_config_snapshot_id="task9-runtime-config-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            runtime_config_sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            campaign_id="task9102-campaign",
            market_date=__import__("datetime").date(2026, 8, 11),
        task9_evidence_dependencies_factory=factory,
        clock=lambda: None,
        sleep=lambda _: None,
    )
    assert launcher._build_task9_evidence_dependencies(lambda _: None)
    assert received["historical_request_interval_seconds"] == 15.0


def test_durable_gate_spaces_only_second_outbound_request_and_survives_restart(tmp_path):
    now = [100.0]
    waits = []

    def sleep(seconds):
        waits.append(seconds)
        now[0] += seconds

    path = Path(tmp_path) / "gate.json"
    first = HistoricalRequestGate(path, interval_seconds=15.0, time_function=lambda: now[0], sleep_function=sleep)
    assert first.acquire()["wait_seconds"] == 0.0
    second = HistoricalRequestGate(path, interval_seconds=15.0, time_function=lambda: now[0], sleep_function=sleep)
    assert second.acquire()["wait_seconds"] == 15.0
    assert waits == [15.0]


def test_normal_live_data_gate_default_remains_one_second(tmp_path):
    class Cache:
        file_path = Path(tmp_path) / "candles.json"

    service = LiveMultiTimeframeData(
        client=object(),
        cache=Cache(),
        provider_cooldown=None,
        cache_enabled=True,
    )
    assert service.historical_request_gate.interval_seconds == 1.0


def test_task9_shared_quote_policy_is_one_second_and_separate_from_five_second_gate():
    reset_shared_market_clients_for_testing()
    controller = get_shared_request_controller()

    assert controller.market_quote_request_interval_seconds == 1.0
    # The launcher owns this separate durable historical policy; the shared
    # REST quote interval must not weaken it.
    assert _TASK9_HISTORICAL_INTER_REQUEST_SECONDS == 15.0
