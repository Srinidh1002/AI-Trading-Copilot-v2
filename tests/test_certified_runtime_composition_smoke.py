from datetime import datetime, timezone

from services.paper_orchestration.certified_runtime_composition import (
    CertifiedRuntimeCompositionSettingsV1,
    CertifiedRuntimeProviderBundleV1,
    build_certified_launcher,
)
from services.paper_orchestration.certified_runtime_launcher import (
    CertifiedPaperRuntimeLauncher,
)


NOW = datetime(2026, 1, 8, 10, 0, tzinfo=timezone.utc)


class Analysis:
    def analyse(self, **kwargs):
        return {
            "decision": "NEUTRAL",
            "timeframes": {},
            "technical": {},
        }


class Options:
    def analyse(self, **kwargs):
        return {
            "decision": "NO_TRADE",
            "reasons": ["observe-only smoke"],
        }


def test_one_cycle_observe_only_smoke(tmp_path, monkeypatch):
    monkeypatch.setattr("config.BROKER", "PAPER")
    monkeypatch.setattr("config.ENABLE_PAPER_TRADING", True)
    monkeypatch.setattr("config.ENABLE_LIVE_TRADING", False)

    providers = CertifiedRuntimeProviderBundleV1(
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
    composition = build_certified_launcher(
        settings=CertifiedRuntimeCompositionSettingsV1(
            data_root=tmp_path / "runtime",
            log_path=tmp_path / "runtime" / "runtime.jsonl",
            interval_seconds=0.001,
        ),
        providers=providers,
    )

    result = CertifiedPaperRuntimeLauncher(
        composition=composition,
        clock=lambda: NOW,
    ).run(max_cycles=1)

    assert result["cycles_completed"] == 1
    assert composition.controls.snapshot().new_entries_allowed is False
    log = (tmp_path / "runtime" / "runtime.jsonl").read_text(
        encoding="utf-8"
    )
    assert "RUNTIME_STARTING" in log
    assert "RUNTIME_STOPPED" in log

