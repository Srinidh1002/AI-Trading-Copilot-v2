from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from services.paper_orchestration.certified_live_provider_readers import (
    CertifiedLiveProviderReaders,
)
from services.paper_orchestration.r16_selector_paper_runtime_v1 import (
    execute_r16_selector_paper_cycle,
)
from services.paper_orchestration.r16_two_market_shadow_source_v1 import (
    R16TwoMarketShadowSourceV1,
)
from test_certified_two_market_parent_runtime import candidate_for
from test_two_market_runtime_readiness import (
    OfflineAnalysisPipeline,
    OfflineOptionPipeline,
)


NOW = datetime(2026, 8, 4, 5, 0, 10, tzinfo=timezone.utc)
MARKET_TS = datetime(2026, 8, 4, 5, 0, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self):
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return NOW + timedelta(milliseconds=self.calls)


def _source():
    scores = {"NIFTY": 85.0, "SENSEX": 60.0}

    def quote(exchange, token, symbol):
        offset = 0 if symbol == "NIFTY" else 1
        ts = MARKET_TS + timedelta(seconds=offset)
        return {
            "spot_price": 22000.0 if symbol == "NIFTY" else 72000.0,
            "market_timestamp": ts,
            "received_at": ts + timedelta(seconds=1),
            "timestamp_source": "TEST",
        }

    def candidate(
        cycle,
        data,
        analysis,
        captured,
        shared_context,
        *,
        parent_cycle_id,
    ):
        return candidate_for(
            cycle,
            data,
            score=scores[cycle.underlying_symbol],
        )

    readers = CertifiedLiveProviderReaders(
        quote_reader=quote,
        analysis_pipeline=OfflineAnalysisPipeline(),
        option_decision_pipeline=OfflineOptionPipeline(),
        available_capital=100_000.0,
        candidate_reader=candidate,
    )
    return R16TwoMarketShadowSourceV1(
        readers=readers,
        clock=Clock(),
    )


def test_default_r16_runtime_stops_after_shadow_selection(tmp_path):
    source = _source()

    result = execute_r16_selector_paper_cycle(
        source=source,
        repo_root=tmp_path,
        incumbent_runtime_root=tmp_path / "r15",
        available_capital=100_000.0,
        evaluated_at=NOW + timedelta(seconds=5),
    )

    assert result.status == "SHADOW_SELECTED"
    assert result.shadow_cycle.decision.decision == "SELECTED"
    assert result.activation.ready is False
    assert result.activation.mode == "SHADOW_ONLY"
    assert result.planning is None
    assert result.lifecycle is None
    assert result.execution_mode == "PAPER"
    assert result.live_execution_eligible is False
    assert result.broker_order_submission is False
    assert not (
        tmp_path
        / "data"
        / "paper_trading"
        / "r16_two_market_parent"
        / "runtime"
    ).exists()


def test_paper_manifest_still_stops_when_incumbent_lock_is_reported_busy(
    tmp_path,
    monkeypatch,
):
    from services.paper_orchestration import r16_strategy_authority_v1 as authority

    manifest = authority.activation_manifest_path(tmp_path)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    payload = authority.build_shadow_activation_manifest()
    payload.update(
        {
            "mode": "PAPER_ENTRY",
            "paper_entry_authorized": True,
        }
    )
    import json

    manifest.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        authority,
        "lock_available",
        lambda *_args, **_kwargs: False,
    )

    result = execute_r16_selector_paper_cycle(
        source=_source(),
        repo_root=tmp_path,
        incumbent_runtime_root=tmp_path / "r15",
        available_capital=100_000.0,
        evaluated_at=NOW + timedelta(seconds=5),
    )

    assert result.status == "SHADOW_SELECTED"
    assert result.activation.ready is False
    assert "INCUMBENT_PAPER_SUPERVISOR_ACTIVE" in result.activation.blockers
    assert result.planning is None
    assert result.lifecycle is None


def test_selector_runtime_source_contains_no_broker_or_live_order_calls():
    text = Path(
        "services/paper_orchestration/"
        "r16_selector_paper_runtime_v1.py"
    ).read_text(encoding="utf-8")

    forbidden = (
        "placeOrder(",
        "place_order(",
        "submit_order(",
        "modify_order(",
        "cancel_order(",
        "broker_order_submission=True",
        "live_execution_eligible=True",
    )
    assert all(token not in text for token in forbidden)
