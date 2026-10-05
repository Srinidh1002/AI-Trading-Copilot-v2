from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest
from test_task8_parent_typed_candidate_certification import (
    NOW,
    captured,
    cycle,
)

from services.paper_orchestration.certified_live_provider_readers import (
    CertifiedLiveProviderReaders,
)
from services.paper_orchestration.certified_live_read_authorities import (
    CertifiedLiveDataResultV1,
)
from services.paper_orchestration.r16_canonical_candidate_reader_v1 import (
    R16CanonicalCandidateReaderV1,
    _canonical_policy_source,
    install_r16_canonical_candidate_reader,
)
from services.analysis.live_canonical_engine_adapters import (
    build_default_live_canonical_evidence_engines,
)
from services.analysis.live_market_candidate_evaluator import (
    LiveCandidatePolicySourceV1,
    evaluate_captured_certified_market_candidate,
)
from tests.fixtures.p5_12 import (
    STRONG_BEARISH,
    build_market_regime,
    build_option_chain_intelligence,
    build_technical_intelligence,
)


class Analysis:
    def analyse(self, **_kwargs):
        return {"legacy": "ignored by canonical candidate reader"}


class Options:
    def analyse(self, **_kwargs):
        return {"decision": "NO_TRADE"}


def _data(cycle_input, spot):
    return CertifiedLiveDataResultV1(
        observation_id=cycle_input.observation_id,
        underlying_symbol=cycle_input.underlying_symbol,
        exchange=cycle_input.exchange,
        symboltoken=(
            "99926000"
            if cycle_input.underlying_symbol == "NIFTY"
            else "99919000"
        ),
        market_timestamp=cycle_input.market_timestamp,
        received_at=cycle_input.received_at,
        spot_price=spot,
    )


def test_canonical_policy_source_reaches_trade_from_two_aligned_families():
    identity = ("NIFTY", "NSE")
    evidence = SimpleNamespace(
        technical=build_technical_intelligence(
            identity,
            STRONG_BEARISH,
        ),
        option_chain=build_option_chain_intelligence(
            identity,
            STRONG_BEARISH,
        ),
        regime=build_market_regime(
            identity,
            STRONG_BEARISH,
        ),
        broader_market=None,
        external_context=None,
        observation=SimpleNamespace(
            spot=SimpleNamespace(
                underlying_symbol="NIFTY",
                exchange="NSE",
            )
        ),
    )

    policy = _canonical_policy_source(
        evidence=evidence,
        parent_cycle_id="r16-parent",
    )

    assert policy.direction == "BEARISH"
    assert policy.eligibility == "ELIGIBLE"
    assert policy.confidence >= 55.0
    assert policy.score == policy.confidence
    assert not policy.blockers


def test_candidate_reader_uses_supplied_capture_and_remains_shadow_only():
    value = captured(
        "NIFTY",
        "NSE",
        25000.0,
        complete_options=True,
    )
    cycle_input = cycle("NIFTY", "NSE", value)
    reader = R16CanonicalCandidateReaderV1()

    candidate = reader(
        cycle_input,
        _data(cycle_input, 25000.0),
        {"ignored": True},
        value,
        None,
        parent_cycle_id="r16-parent",
    )

    assert candidate.observation_id == cycle_input.observation_id
    assert candidate.underlying_symbol == "NIFTY"
    assert candidate.exchange == "NSE"
    assert candidate.market_timestamp == cycle_input.market_timestamp
    assert reader.mode == "SHADOW_ONLY"
    assert reader.execution_mode == "PAPER"
    assert reader.live_execution_eligible is False
    assert reader.broker_order_submission is False


def test_candidate_reader_requires_immutable_capture():
    value = captured("SENSEX", "BSE", 80000.0)
    cycle_input = cycle("SENSEX", "BSE", value)

    with pytest.raises(RuntimeError, match="CANONICAL_CAPTURE_REQUIRED"):
        R16CanonicalCandidateReaderV1()(
            cycle_input,
            _data(cycle_input, 80000.0),
            {},
            None,
            None,
            parent_cycle_id="r16-parent",
        )


def test_candidate_reader_rejects_cross_market_capture():
    nifty = captured("NIFTY", "NSE", 25000.0)
    sensex = captured("SENSEX", "BSE", 80000.0)
    nifty_cycle = cycle("NIFTY", "NSE", nifty)

    with pytest.raises(ValueError, match="captured evidence identity"):
        R16CanonicalCandidateReaderV1()(
            nifty_cycle,
            _data(nifty_cycle, 25000.0),
            {},
            sensex,
            None,
            parent_cycle_id="r16-parent",
        )


def test_installation_returns_fresh_reader_and_does_not_mutate_source():
    original = CertifiedLiveProviderReaders(
        quote_reader=lambda *_args: {
            "spot_price": 25000.0,
            "market_timestamp": NOW,
            "received_at": NOW,
        },
        analysis_pipeline=Analysis(),
        option_decision_pipeline=Options(),
        available_capital=10000.0,
        capture_reader=lambda _cycle: captured(
            "NIFTY",
            "NSE",
            25000.0,
        ),
    )

    installed = install_r16_canonical_candidate_reader(original)

    assert installed is not original
    assert original.candidate_reader is None
    assert type(installed.candidate_reader) is R16CanonicalCandidateReaderV1
    assert installed.capture_reader is original.capture_reader
    assert installed.available_capital == original.available_capital
    assert installed.candidate_reader.execution_mode == "PAPER"
    assert installed.candidate_reader.live_execution_eligible is False
    assert installed.candidate_reader.broker_order_submission is False


def test_source_contains_no_execution_stage_imports():
    from pathlib import Path

    source = Path(
        "services/paper_orchestration/"
        "r16_canonical_candidate_reader_v1.py"
    ).read_text(encoding="utf-8")

    forbidden = (
        "NewEntryPaperLifecycleExecutor",
        "placeOrder",
        "submit_order",
        "broker_order_submission=True",
        "live_execution_eligible=True",
    )
    assert all(item not in source for item in forbidden)

def test_fyers_capture_preserves_provider_provenance_through_normalization():
    value = captured(
        "NIFTY",
        "NSE",
        25000.0,
        complete_options=True,
    )
    value = replace(
        value,
        cache_metadata={
            "options": {
                "provider": "FYERS",
            }
        },
    )
    cycle_input = cycle("NIFTY", "NSE", value)

    result = evaluate_captured_certified_market_candidate(
        captured_evidence=value,
        session_validation=cycle_input.session_validation,
        policy_source=LiveCandidatePolicySourceV1.unavailable(),
        parent_cycle_id="r16-provider-parent",
        candidate_id="r16-provider-candidate",
        observation_id=cycle_input.observation_id,
        engines=build_default_live_canonical_evidence_engines(),
    )

    assert result.options.snapshot is not None
    assert result.options.universe is not None
    assert result.options.snapshot.provider_name == "FYERS"
    assert result.options.universe.source_name == "FYERS"