from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from test_certified_two_market_parent_runtime import candidate_for
from test_two_market_runtime_readiness import (
    OfflineAnalysisPipeline,
    OfflineOptionPipeline,
)

from services.paper_orchestration.certified_live_provider_readers import (
    CertifiedLiveProviderReaders,
)
from services.paper_orchestration.r16_two_market_shadow_source_v1 import (
    R16TwoMarketShadowSourceV1,
)


NOW = datetime(2026, 8, 4, 5, 0, 10, tzinfo=UTC)
MARKET_TS = datetime(2026, 8, 4, 5, 0, 0, tzinfo=UTC)


class Clock:
    def __init__(self):
        self.value = NOW
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self.value + timedelta(milliseconds=self.calls)


def _readers(*, scores=None, failing=None, quote_calls=None):
    scores = scores or {"NIFTY": 80.0, "SENSEX": 60.0}
    quote_calls = quote_calls if quote_calls is not None else []

    def quote(exchange, token, symbol):
        quote_calls.append((symbol, exchange, token))
        offset = 0 if symbol == "NIFTY" else 1
        return {
            "spot_price": 22000.0 if symbol == "NIFTY" else 72000.0,
            "market_timestamp": MARKET_TS + timedelta(seconds=offset),
            "received_at": MARKET_TS + timedelta(seconds=offset + 1),
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
        if cycle.underlying_symbol == failing:
            raise RuntimeError("injected child failure")
        value = candidate_for(
            cycle,
            data,
            score=scores[cycle.underlying_symbol],
        )
        return replace(
            value,
            provenance={
                **dict(value.provenance),
                "r16_parent_cycle_id": parent_cycle_id,
            },
        )

    return CertifiedLiveProviderReaders(
        quote_reader=quote,
        analysis_pipeline=OfflineAnalysisPipeline(),
        option_decision_pipeline=OfflineOptionPipeline(),
        available_capital=10_000.0,
        candidate_reader=candidate,
    )


def test_shadow_source_reads_both_markets_exactly_once_and_builds_common_parent():
    calls = []
    clock = Clock()
    source = R16TwoMarketShadowSourceV1(
        readers=_readers(quote_calls=calls),
        clock=clock,
    )

    parent, nifty, sensex = source.build_inputs()

    assert [item[:2] for item in calls] == [
        ("NIFTY", "NSE"),
        ("SENSEX", "BSE"),
    ]
    assert parent.nifty_observation_id == nifty.observation_id
    assert parent.sensex_observation_id == sensex.observation_id
    assert nifty.cycle_requested_at == parent.requested_at
    assert sensex.cycle_requested_at == parent.requested_at
    assert nifty.execution_mode == "PAPER"
    assert sensex.execution_mode == "PAPER"
    assert nifty.metadata["broker_order_submission"] is False
    assert sensex.metadata["broker_order_submission"] is False
    assert nifty.metadata["shadow_only"] is True
    assert sensex.metadata["shadow_only"] is True


def test_shadow_cycle_selects_only_stronger_eligible_market_without_execution():
    calls = []
    source = R16TwoMarketShadowSourceV1(
        readers=_readers(
            scores={"NIFTY": 61.0, "SENSEX": 88.0},
            quote_calls=calls,
        ),
        clock=Clock(),
    )

    result = source.run_shadow_cycle()

    assert result.mode == "SHADOW_ONLY"
    assert result.decision.decision == "SELECTED"
    assert result.decision.selected_market == ("SENSEX", "BSE")
    assert result.execution_mode == "PAPER"
    assert result.live_execution_eligible is False
    assert result.broker_order_submission is False
    assert sum(
        entry.outcome_reason == "SELECTED"
        for entry in result.decision.entries
    ) == 1
    assert calls[0][0] == "NIFTY"
    assert calls[1][0] == "SENSEX"


def test_shadow_cycle_retains_one_market_failure_and_selects_other():
    source = R16TwoMarketShadowSourceV1(
        readers=_readers(failing="NIFTY"),
        clock=Clock(),
    )

    result = source.run_shadow_cycle()

    assert result.decision.entries[0].child.terminal_status == "FAILED"
    assert result.decision.entries[1].child.terminal_status == "COMPLETED"
    assert result.decision.selected_market == ("SENSEX", "BSE")


def test_shadow_source_timestamp_skew_fails_closed_at_parent():
    calls = []

    def quote(exchange, token, symbol):
        calls.append(symbol)
        offset = 0 if symbol == "NIFTY" else 20
        ts = MARKET_TS + timedelta(seconds=offset)
        return {
            "spot_price": 22000.0 if symbol == "NIFTY" else 72000.0,
            "market_timestamp": ts,
            "received_at": ts + timedelta(seconds=1),
            "timestamp_source": "TEST",
        }

    base = _readers()
    readers = CertifiedLiveProviderReaders(
        quote_reader=quote,
        analysis_pipeline=base.analysis_pipeline,
        option_decision_pipeline=base.option_decision_pipeline,
        available_capital=10_000.0,
        candidate_reader=base.candidate_reader,
    )
    source = R16TwoMarketShadowSourceV1(
        readers=readers,
        clock=Clock(),
        max_timestamp_skew_seconds=5.0,
    )

    result = source.run_shadow_cycle()

    assert calls == ["NIFTY", "SENSEX"]
    assert result.decision.decision == "NO_TRADE"
    assert "CANDIDATE_TIMESTAMP_SKEW_EXCEEDED" in result.decision.blockers


def test_shadow_source_rejects_non_certified_reader_type():
    with pytest.raises(TypeError, match="readers"):
        R16TwoMarketShadowSourceV1(
            readers=object(),
            clock=Clock(),
        )