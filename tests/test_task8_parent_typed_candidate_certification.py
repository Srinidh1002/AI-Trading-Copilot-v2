"""Offline certification of captured typed candidates through the real parent runtime."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from services.analysis.live_canonical_engine_adapters import build_default_live_canonical_evidence_engines
from services.analysis.live_market_candidate_evaluator import LiveCandidatePolicySourceV1, evaluate_captured_certified_market_candidate
from services.certification.task8_live_candidate_adapter import adapt_task8_live_candidate
from services.contracts.certified_live_captured_evidence_v1 import CertifiedLiveCapturedEvidenceV1
from services.contracts.paper_orchestration_policy_v1 import PaperOrchestrationPolicyV1
from services.contracts.two_market_decision_policy_v1 import TwoMarketDecisionPolicyV1
from services.contracts.two_market_parent_cycle_input_v1 import TwoMarketParentCycleInputV1
from services.market_session.validator import validate_session_timestamp
from services.paper_orchestration.certified_cycle_input_factory import build_certified_cycle_input
from services.paper_orchestration.certified_live_provider_readers import CertifiedLiveProviderReaders, market_spec_for
from services.paper_orchestration.certified_two_market_parent_runtime import run_certified_two_market_parent_runtime


IST = ZoneInfo("Asia/Kolkata")
NOW = datetime(2026, 8, 3, 10, 0, tzinfo=IST)
COUNTS = {"5m": 60, "15m": 60, "1h": 50, "1d": 50}
MINUTES = {"5m": 5, "15m": 15, "1h": 60, "1d": 1440}


def _rows(timeframe, base):
    interval = timedelta(minutes=MINUTES[timeframe])
    first = NOW - interval * COUNTS[timeframe]
    return tuple(((first + interval * index).isoformat(), base + index, base + index + 2, base + index - 1, base + index + 1, 1000 + index) for index in range(COUNTS[timeframe]))


def _complete_options(symbol, exchange, option_exchange, spot):
    expiry = date(2026, 8, 6)
    contracts = []
    for strike in tuple(spot + 50 * offset for offset in range(-5, 5)):
        for suffix, option_type, oi, volume, premium, oi_change in (("CE", "CE", 1000, 500, 100.0, -100), ("PE", "PE", 2000, 1000, 110.0, 100)):
            token = f"fixture-{symbol}-{int(strike)}-{suffix}"
            contracts.append({"exchange": option_exchange, "underlying": symbol, "token": token, "symbol": f"{symbol}{expiry.strftime('%d%b%y').upper()}{int(strike)}{suffix}", "option_type": option_type, "expiry": expiry.isoformat(), "strike": strike, "lot_size": 25, "tick_size": 0.05, "premium": premium, "bid": premium - 1, "ask": premium + 1, "volume": volume, "open_interest": oi, "change_in_open_interest": oi_change, "iv": 15.0})
    return tuple(contracts)


def captured(symbol, exchange, spot, *, complete_options=False):
    spec = market_spec_for(symbol, exchange)
    return CertifiedLiveCapturedEvidenceV1(
        underlying_symbol=spec.underlying_symbol, spot_exchange=spec.exchange,
        spot_token=spec.symboltoken, option_exchange=spec.option_exchange,
        spot_payload={"spot_price": spot},
        candle_rows_by_timeframe={name: _rows(name, spot) for name in ("5m", "15m", "1h", "1d")},
        option_contracts=_complete_options(spec.underlying_symbol, spec.exchange, spec.option_exchange, spot) if complete_options else (), provider_timestamp=NOW, evaluated_at=NOW,
        provider_blockers=() if complete_options else ("OPTION_CHAIN_UNAVAILABLE",),
        cache_metadata={"source": "CERTIFICATION_FIXTURE", "cached": False},
    )


def cycle(symbol, exchange, capture):
    session = validate_session_timestamp(symbol=symbol, exchange=exchange, market_timestamp=NOW, evaluated_at=NOW, validation_mode="LENIENT_ANALYSIS", id_factory=lambda: f"session:{symbol}")
    policy = PaperOrchestrationPolicyV1(orchestration_policy_id=f"policy:{symbol}", policy_timestamp=NOW, emergency_paper_halt=False)
    return build_certified_cycle_input(cycle_kind="OPPORTUNITY", observation_id=f"observation:{symbol}", orchestration_policy=policy, underlying_symbol=symbol, exchange=exchange, market_timestamp=NOW, received_at=NOW, cycle_requested_at=NOW, session_validation=session, metadata={"spot_price": capture.spot_payload["spot_price"], "captured_spot_payload": dict(capture.spot_payload)})


def test_real_captured_evaluator_returns_typed_blocked_candidate_for_both_markets():
    for symbol, exchange, spot in (("NIFTY", "NSE", 25000.0), ("SENSEX", "BSE", 80000.0)):
        value = captured(symbol, exchange, spot)
        session = validate_session_timestamp(symbol=symbol, exchange=exchange, market_timestamp=NOW, evaluated_at=NOW, validation_mode="LENIENT_ANALYSIS", id_factory=lambda: f"session:{symbol}")
        result = evaluate_captured_certified_market_candidate(captured_evidence=value, session_validation=session, policy_source=LiveCandidatePolicySourceV1.unavailable(), candidate_id=f"candidate:{symbol}", observation_id=f"observation:{symbol}", engines=build_default_live_canonical_evidence_engines())
        assert (result.candidate.underlying_symbol, result.candidate.exchange) == (symbol, exchange)
        assert result.candidate.eligibility != "ELIGIBLE"
        assert "OPTION_CHAIN_UNAVAILABLE" in result.candidate.blockers
        assert "CERTIFIED_POLICY_EVIDENCE_UNAVAILABLE" in result.candidate.blockers
        assert result.evidence.option_chain.option_chain_snapshot_id is None
        assert result.evidence.option_chain.expiry is None
        assert result.evidence.pillars.aggregation_status == "BLOCKED"


class Analysis:
    def __init__(self): self.calls = 0
    def analyse(self, **kwargs): self.calls += 1; return {"legacy_decision": "BUY", "legacy_confidence": 99.0}

class Options:
    def analyse(self, **kwargs): raise AssertionError("option pipeline is not part of parent candidate evaluation")


def test_real_parent_completes_both_typed_children_and_selects_none_when_blocked():
    nifty, sensex = captured("NIFTY", "NSE", 25000.0), captured("SENSEX", "BSE", 80000.0)
    nifty_cycle, sensex_cycle = cycle("NIFTY", "NSE", nifty), cycle("SENSEX", "BSE", sensex)
    captures = {nifty_cycle.observation_id: nifty, sensex_cycle.observation_id: sensex}
    analysis = Analysis()
    readers = CertifiedLiveProviderReaders(quote_reader=lambda *_: (_ for _ in ()).throw(AssertionError("provider call")), analysis_pipeline=analysis, option_decision_pipeline=Options(), available_capital=10000.0, candidate_reader=adapt_task8_live_candidate, capture_reader=lambda item: captures[item.observation_id])
    parent = TwoMarketParentCycleInputV1("parent", "decision", "nifty-child", "sensex-child", nifty_cycle.observation_id, sensex_cycle.observation_id, NOW, NOW, TwoMarketDecisionPolicyV1(180.0, 5.0))
    result = run_certified_two_market_parent_runtime(parent, nifty_cycle=nifty_cycle, sensex_cycle=sensex_cycle, readers=readers)
    assert analysis.calls == 2
    assert tuple(entry.child.terminal_status for entry in result.entries) == ("COMPLETED", "COMPLETED")
    assert result.decision == "NO_TRADE"
    assert result.selected_market is None
    assert result.selected_candidate_id is None
    assert "NO_ELIGIBLE_MARKET" in result.blockers


def test_complete_nifty_options_preserve_existing_warning_gates_without_forced_selection():
    nifty = captured("NIFTY", "NSE", 25000.0, complete_options=True)
    sensex = captured("SENSEX", "BSE", 80000.0)
    nifty_session = validate_session_timestamp(symbol="NIFTY", exchange="NSE", market_timestamp=NOW, evaluated_at=NOW, validation_mode="LENIENT_ANALYSIS", id_factory=lambda: "session:nifty")
    eligible = evaluate_captured_certified_market_candidate(captured_evidence=nifty, session_validation=nifty_session, policy_source=LiveCandidatePolicySourceV1("BULLISH", "ELIGIBLE", 80.0, 80.0, reasons=("Explicit certification policy.",)), candidate_id="candidate:NIFTY:eligible", observation_id="observation:NIFTY:eligible", engines=build_default_live_canonical_evidence_engines())
    assert eligible.candidate.eligibility == "UNAVAILABLE"
    assert eligible.evidence.option_chain.intelligence_status == "READY_WITH_WARNINGS"
    assert eligible.evidence.contract_ranking.ranking_status == "RANKED_WITH_WARNINGS"
    assert eligible.evidence.regime.context_status == "READY_WITH_WARNINGS"
    assert eligible.candidate.blockers == ("EVIDENCE_UNAVAILABLE_REGIME",)
    assert eligible.evidence.option_chain.option_chain_snapshot_id is not None
    assert eligible.evidence.option_chain.expiry == date(2026, 8, 6)
    assert eligible.evidence.contract_ranking.ranking_status in {"RANKED", "RANKED_WITH_WARNINGS"}
