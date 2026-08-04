from datetime import datetime, timezone
from pathlib import Path

from services.paper_orchestration.certified_runtime_composition import (
    CertifiedRuntimeCompositionSettingsV1,
    CertifiedRuntimeProviderBundleV1,
    build_certified_launcher,
)
from services.paper_orchestration.certified_runtime_launcher import (
    CertifiedLauncherCompositionV1,
)
from services.paper_orchestration.continuous_runtime_adapter import (
    ContinuousPaperOrchestrationRuntimeAdapter,
)


NOW = datetime(2026, 1, 8, 10, 0, tzinfo=timezone.utc)


class Analysis:
    def analyse(self, **kwargs):
        return {"decision": "NEUTRAL", "timeframes": {}}


class Options:
    def analyse(self, **kwargs):
        return {"decision": "NO_TRADE", "reasons": ["observe-only test"]}


def providers():
    return CertifiedRuntimeProviderBundleV1(
        quote_reader=lambda *_: {
            "ltp": 25000.0,
            "market_timestamp": NOW,
            "received_at": NOW,
            "timestamp_source": "TEST",
        },
        analysis_pipeline=Analysis(),
        option_decision_pipeline=Options(),
        clock=lambda: NOW,
    )


def test_builds_exact_repository_owned_launcher(tmp_path, monkeypatch):
    monkeypatch.setattr("config.BROKER", "PAPER")
    monkeypatch.setattr("config.ENABLE_PAPER_TRADING", True)
    monkeypatch.setattr("config.ENABLE_LIVE_TRADING", False)

    settings = CertifiedRuntimeCompositionSettingsV1(
        data_root=tmp_path / "runtime",
        log_path=tmp_path / "runtime" / "runtime.jsonl",
        interval_seconds=0.001,
    )
    result = build_certified_launcher(
        settings=settings,
        providers=providers(),
    )

    assert type(result) is CertifiedLauncherCompositionV1
    assert (
        type(result.runtime_adapter)
        is ContinuousPaperOrchestrationRuntimeAdapter
    )
    assert result.controls.snapshot().observe_only is True
    assert result.controls.snapshot().new_entries_allowed is False
    assert result.execution_mode == "PAPER"
    assert result.live_execution_eligible is False


def test_composition_uses_separate_journals(tmp_path, monkeypatch):
    monkeypatch.setattr("config.BROKER", "PAPER")
    monkeypatch.setattr("config.ENABLE_PAPER_TRADING", True)
    monkeypatch.setattr("config.ENABLE_LIVE_TRADING", False)

    result = build_certified_launcher(
        settings=CertifiedRuntimeCompositionSettingsV1(
            data_root=tmp_path / "runtime",
            log_path=tmp_path / "runtime" / "runtime.jsonl",
            interval_seconds=0.001,
        ),
        providers=providers(),
    )
    runtime = result.runtime_adapter

    opportunity_path = runtime.opportunity_coordinator.journal.file_path
    monitoring_path = runtime.monitoring_coordinator.journal.file_path

    assert opportunity_path != monitoring_path
    assert Path(opportunity_path).parent == tmp_path / "runtime"
    assert Path(monitoring_path).parent == tmp_path / "runtime"

