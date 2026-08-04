import ast
from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timedelta, timezone
from math import inf, nan
from pathlib import Path

import pytest

from services.contracts.canonical_market_regime_result_v1 import CanonicalMarketRegimeResultV1
from services.contracts.broader_market_intelligence_result_v1 import BroaderMarketIntelligenceResultV1
from services.contracts.cross_market_evidence_v1 import CrossMarketEvidenceV1
from services.contracts.external_market_context_result_v1 import ExternalMarketContextResultV1
from services.contracts.market_analysis_candidate_v1 import MarketAnalysisCandidateV1, MarketAnalysisEvidenceV1
from services.contracts.market_data_quality_result_v1 import MarketDataQualityResultV1
from services.contracts.market_session_validation_v1 import MarketSessionValidationV1
from services.contracts.multi_timeframe_snapshot_v1 import MultiTimeframeSnapshotV1
from services.contracts.option_chain_intelligence_result_v1 import OptionChainIntelligenceResultV1
from services.contracts.option_chain_metric_v1 import OptionChainMetricV1
from services.contracts.option_contract_candidate_v1 import OptionContractCandidateV1
from services.contracts.option_contract_ranking_result_v1 import OptionContractRankingResultV1
from services.contracts.option_contract_v1 import OptionContractV1
from services.contracts.technical_indicator_value_v1 import TechnicalIndicatorValueV1
from services.contracts.technical_intelligence_result_v1 import TechnicalIntelligenceResultV1
from services.contracts.timeframe_evidence_v1 import TimeframeEvidenceV1
from services.contracts.timeframe_technical_evidence_v1 import TimeframeTechnicalEvidenceV1


MARKET = datetime(2026, 8, 3, 9, 29, tzinfo=timezone.utc)
REQUESTED = datetime(2026, 8, 3, 9, 30, tzinfo=timezone.utc)
RECEIVED = datetime(2026, 8, 3, 9, 31, tzinfo=timezone.utc)
NAMES = ("price_action", "candlestick", "chart_pattern", "volume", "volatility", "oi", "oi_change", "pcr", "support_resistance", "max_pain", "iv", "greeks", "premium_behavior", "liquidity_spread")
_CATEGORIES = ("TREND", "MOMENTUM", "VOLATILITY", "VOLUME", "LEVELS", "PATTERNS")


def identity(symbol="NIFTY"):
    return (symbol, "NSE", "NFO") if symbol == "NIFTY" else (symbol, "BSE", "BFO")


def evidence(status="READY", **changes):
    values = dict(status=status, source_ids=("fixture-source",), provenance={"provider": {"name": "fixture"}}, summary={"values": [1]})
    values.update(changes)
    return MarketAnalysisEvidenceV1(**values)


def quality(symbol, exchange, subject_type):
    return MarketDataQualityResultV1(f"{subject_type}-{symbol}", REQUESTED, subject_type, "VALID", underlying_symbol=symbol, exchange=exchange, item_count=1, valid_item_count=1)


def session(symbol, exchange):
    return MarketSessionValidationV1(f"session-{symbol}", REQUESTED, MARKET, symbol, exchange, "UTC", REQUESTED.date(), "REGULAR", "REGULAR_TRADING", "TRADING_DAY", is_trading_day=True, regular_session_open=True, analysis_allowed=True, paper_preparation_allowed=True)


def timeframe(symbol, exchange):
    return TimeframeEvidenceV1(f"frame-{symbol}", REQUESTED, symbol, exchange, "5m", f"candles-{symbol}", f"quality-{symbol}", "VALID", 20, 20, 0, MARKET - timedelta(minutes=95), MARKET, MARKET + timedelta(minutes=5), MARKET + timedelta(minutes=5), 0.0, 60.0, 20, True, True)


def technical(symbol, exchange):
    indicator = TechnicalIndicatorValueV1("RSI", "5m", 55.0, "BULLISH", "VALID", 15, 20)
    frame = TimeframeTechnicalEvidenceV1(f"technical-frame-{symbol}", REQUESTED, symbol, exchange, "5m", f"frame-{symbol}", (indicator,), tuple((name, "NEUTRAL") for name in _CATEGORIES), tuple((name, 0.5) for name in _CATEGORIES), trend_bias="BULLISH", momentum_bias="BULLISH")
    return TechnicalIntelligenceResultV1(f"technical-{symbol}", REQUESTED, f"snapshot-{symbol}", f"quality-{symbol}", symbol, exchange, (frame,), "READY", "BULLISH", 0.5)


def multi_timeframe(symbol, exchange):
    return MultiTimeframeSnapshotV1(f"snapshot-{symbol}", REQUESTED, symbol, exchange, ("5m",), (timeframe(symbol, exchange),), "5m", MARKET)


def regime(symbol, exchange):
    return CanonicalMarketRegimeResultV1(f"regime-{symbol}", REQUESTED, symbol, exchange, technical(symbol, exchange), None, None, session(symbol, exchange), "READY", "BULLISH", "UPTREND", "NORMAL", "NORMAL", "CONFIRMING", "SUITABLE", 0.5, 0.5, 2, 2, 1, 0, primary_regime="BULLISH", event_risk_state="NONE", entry_restriction_state="OPEN", analysis_allowed=True, new_entries_allowed=True)


def unavailable_regime(symbol, exchange):
    return CanonicalMarketRegimeResultV1(f"regime-{symbol}", REQUESTED, symbol, exchange, None, None, None, None, "UNAVAILABLE", "UNAVAILABLE", "UNAVAILABLE", "UNAVAILABLE", "UNAVAILABLE", "UNAVAILABLE", "UNAVAILABLE", 0.0, 0.0, 0, 4, 0, 0)


def option_chain(symbol, exchange):
    metric = OptionChainMetricV1("PCR_OPEN_INTEREST", 1.2, "BULLISH", "VALID", 10)
    return OptionChainIntelligenceResultV1(f"chain-result-{symbol}", REQUESTED, f"chain-{symbol}", f"chain-quality-{symbol}", symbol, exchange, date(2026, 8, 27), (metric,), "READY", "BULLISH", 0.2, ("PCR_OPEN_INTEREST",), (), (), (), 1, 0, (), (), None)


def option_contract_eligibility(symbol, exchange):
    contract = OptionContractV1(contract_id=f"contract-{symbol}", underlying_symbol=symbol, exchange=exchange, trading_symbol=f"{symbol}-CALL", option_type="CALL", strike=25000.0, expiry_date=date(2026, 8, 27), lot_size=25, market_timestamp=MARKET, last_price=100.0, bid_price=99.0, ask_price=101.0, open_interest=1000, volume=500, implied_volatility=18.0)
    candidate = OptionContractCandidateV1(contract, "ELIGIBLE", "ATM", 0.0, 2.0, 0.8, 0.9, 0.5, 0.5, 0.6, 0.5, 0.8, 0.8)
    return OptionContractRankingResultV1(f"ranking-{symbol}", REQUESTED, f"universe-{symbol}", f"chain-result-{symbol}", symbol, exchange, "BULLISH", "CALL", "RANKED", (candidate,))


def valid_canonical_inputs(symbol="NIFTY"):
    symbol, exchange, _ = identity(symbol)
    return dict(freshness=quality(symbol, exchange, "QUOTE"), data_quality=quality(symbol, exchange, "CANDLE"), session=session(symbol, exchange), technical=technical(symbol, exchange), multi_timeframe=multi_timeframe(symbol, exchange), regime=regime(symbol, exchange), option_chain=option_chain(symbol, exchange), option_contract_eligibility=option_contract_eligibility(symbol, exchange))


def nonready_canonical_input(name, symbol="NIFTY"):
    symbol, exchange, _ = identity(symbol)
    if name == "freshness": return MarketDataQualityResultV1(f"stale-{symbol}", REQUESTED, "QUOTE", "STALE", underlying_symbol=symbol, exchange=exchange, blockers=("STALE",))
    if name == "data_quality": return MarketDataQualityResultV1(f"malformed-{symbol}", REQUESTED, "CANDLE", "MALFORMED", underlying_symbol=symbol, exchange=exchange, blockers=("MALFORMED",))
    if name == "session": return replace(session(symbol, exchange), analysis_allowed=False, blockers=("SESSION_BLOCKED",))
    if name == "technical": return replace(technical(symbol, exchange), status="FAILED", aggregate_bias="UNAVAILABLE", aggregate_strength=0.0, blockers=("TECHNICAL_FAILED",))
    if name == "multi_timeframe": return replace(multi_timeframe(symbol, exchange), blockers=("MULTI_TIMEFRAME_BLOCKED",))
    if name == "regime": return unavailable_regime(symbol, exchange)
    if name == "option_chain": return replace(option_chain(symbol, exchange), intelligence_status="FAILED", aggregate_bias="UNAVAILABLE", aggregate_strength=0.0, blockers=("OPTION_CHAIN_FAILED",))
    if name == "option_contract_eligibility": return OptionContractRankingResultV1(f"ranking-{symbol}", REQUESTED, f"universe-{symbol}", f"chain-result-{symbol}", symbol, exchange, "NEUTRAL", None, "BLOCKED", (), blockers=("RANKING_BLOCKED",))
    raise ValueError(name)


def broader_market(symbol, exchange):
    related_symbol, related_exchange = ("SENSEX", "BSE") if symbol == "NIFTY" else ("NIFTY", "NSE")
    cross = CrossMarketEvidenceV1(f"cross-{symbol}", REQUESTED, symbol, exchange, related_symbol, related_exchange, "BROAD_MARKET", "5m", 30, 29, 0.8, 0.8, "STRONG_POSITIVE", "BULLISH", "BULLISH", "CONFIRMING", "NONE", "READY", "fixture", "fixture", MARKET, REQUESTED)
    return BroaderMarketIntelligenceResultV1(f"broader-{symbol}", REQUESTED, symbol, exchange, (cross,), None, None, "READY", "BULLISH", 0.8, "CONFIRMING", "NONE", 1, 0)


def external_context(symbol, exchange):
    return ExternalMarketContextResultV1(f"external-{symbol}", REQUESTED, symbol, exchange, None, None, None, "READY", "POSITIVE", 0.5, "CONFIRMING", "NONE", "OPEN", True, True, 3, 0, 1, 0)


def nonready_broader_market(symbol, exchange):
    return replace(broader_market(symbol, exchange), intelligence_status="UNAVAILABLE", aggregate_bias="UNAVAILABLE", aggregate_strength=0.0, confirmation_state="UNAVAILABLE", divergence_state="UNAVAILABLE", blockers=("BROADER_UNAVAILABLE",))


def nonready_external_context(symbol, exchange):
    return replace(external_context(symbol, exchange), context_status="BLOCKED", aggregate_direction="UNAVAILABLE", aggregate_strength=0.0, confirmation_state="UNAVAILABLE", risk_level="UNAVAILABLE", entry_restriction_state="BLOCKED", analysis_allowed=False, new_entries_allowed=False, blockers=("EXTERNAL_BLOCKED",))


def build(**changes):
    symbol = changes.get("underlying_symbol", "NIFTY")
    symbol, exchange, option_exchange = identity(symbol)
    values = dict(candidate_id="candidate-1", observation_id="observation-1", underlying_symbol=symbol, exchange=exchange, option_exchange=option_exchange, symboltoken="99926000", requested_at=REQUESTED, market_timestamp=MARKET, received_at=RECEIVED, broader_market=None, external_context=None, direction="BULLISH", eligibility="ELIGIBLE", confidence=75.0, score=75.0, evidence_references={"technical": {"ids": [f"technical-{symbol}"]}}, provenance={"fixture": {"version": 1}})
    values.update(valid_canonical_inputs(symbol))
    values.update({name: evidence() for name in NAMES})
    values.update(changes)
    return MarketAnalysisCandidateV1(**values)


def unavailable_candidate(**changes):
    values = dict(eligibility="UNAVAILABLE", direction="UNAVAILABLE", confidence=0.0, score=0.0, blockers=("CANONICAL_EVIDENCE_UNAVAILABLE",), freshness=None, data_quality=None, session=None, technical=None, multi_timeframe=None, regime=None, option_chain=None, option_contract_eligibility=None)
    values.update(changes)
    return build(**values)


@pytest.mark.parametrize("market", ("NIFTY", "SENSEX"))
def test_valid_immutable_market_identities_with_canonical_evidence(market):
    value = build(underlying_symbol=market)
    assert (value.underlying_symbol, value.exchange, value.option_exchange) == identity(market)
    assert all(getattr(value, name) is not None for name in ("freshness", "data_quality", "session", "technical", "multi_timeframe", "regime", "option_chain", "option_contract_eligibility"))
    with pytest.raises(FrozenInstanceError): value.score = 2.0


def test_timestamp_ordering_is_market_then_request_then_receipt():
    assert build().market_timestamp < build().requested_at < build().received_at
    with pytest.raises(ValueError, match="timestamp ordering"): build(requested_at=RECEIVED + timedelta(seconds=1))
    with pytest.raises(ValueError, match="timestamp ordering"): build(market_timestamp=REQUESTED + timedelta(seconds=1))
    with pytest.raises(ValueError, match="timestamp ordering"): build(market_timestamp=RECEIVED + timedelta(seconds=1))


@pytest.mark.parametrize("changes", ({"underlying_symbol": "BANKNIFTY"}, {"exchange": "BSE"}, {"option_exchange": "BFO"}, {"candidate_id": " "}, {"observation_id": ""}, {"requested_at": datetime(2026, 8, 3, 9, 30)}, {"execution_mode": "LIVE"}, {"live_execution_eligible": True}, {"broker_order_submission": True}, {"confidence": 100.1}, {"score": 100.1}, {"confidence": nan}, {"score": inf}, {"score": -0.1}))
def test_invalid_identity_ids_timestamps_safety_and_scores_are_rejected(changes):
    with pytest.raises((TypeError, ValueError)): build(**changes)


@pytest.mark.parametrize("confidence,score", ((100.0, 100.0),))
def test_score_and_confidence_accept_closed_zero_to_one_hundred_range(confidence, score):
    value = build(confidence=confidence, score=score)
    assert (value.confidence, value.score) == (confidence, score)


def test_eligible_candidate_rejects_zero_confidence_or_score():
    with pytest.raises(ValueError, match="non-ready evidence"): build(confidence=0.0)
    with pytest.raises(ValueError, match="non-ready evidence"): build(score=0.0)
    assert unavailable_candidate().confidence == unavailable_candidate().score == 0.0


@pytest.mark.parametrize("eligibility,direction,diagnostic", (("UNAVAILABLE", "UNAVAILABLE", {"blockers": ("UNAVAILABLE",)}), ("CONFLICTING", "CONFLICTING", {"contradictions": ("CONFLICTING",)}), ("INELIGIBLE", "BULLISH", {"contradictions": ("INELIGIBLE",)})))
def test_zero_confidence_and_score_accept_either_explicit_diagnostic(eligibility, direction, diagnostic):
    value = build(eligibility=eligibility, direction=direction, confidence=0.0, score=0.0, **diagnostic)
    assert value.eligibility == eligibility


def test_zero_confidence_and_score_without_diagnostic_is_rejected():
    with pytest.raises(ValueError, match="zero unavailable score requires blocker or contradiction"):
        build(eligibility="INELIGIBLE", direction="BULLISH", confidence=0.0, score=0.0)


@pytest.mark.parametrize("field_name", ("freshness", "data_quality", "session", "technical", "multi_timeframe", "regime", "option_chain", "option_contract_eligibility"))
def test_eligible_candidate_requires_every_canonical_evidence_contract(field_name):
    with pytest.raises(ValueError, match="eligible candidate cannot contain"):
        build(**{field_name: None})


@pytest.mark.parametrize("field_name", ("freshness", "data_quality", "session", "technical", "multi_timeframe", "regime", "option_chain", "option_contract_eligibility"))
def test_eligible_candidate_accepts_each_ready_canonical_contract(field_name):
    assert getattr(build(), field_name) is not None


@pytest.mark.parametrize("field_name", ("freshness", "data_quality", "session", "technical", "multi_timeframe", "regime", "option_chain", "option_contract_eligibility"))
def test_nonready_canonical_contract_rejects_eligible_and_requires_reason_when_ineligible(field_name):
    nonready = nonready_canonical_input(field_name)
    with pytest.raises(ValueError, match="non-ready evidence"):
        build(**{field_name: nonready})
    with pytest.raises(ValueError, match="requires blocker or contradiction"):
        build(eligibility="INELIGIBLE", direction="UNAVAILABLE", confidence=0.0, score=0.0, blockers=(), **{field_name: nonready})
    value = build(eligibility="INELIGIBLE", direction="UNAVAILABLE", confidence=0.0, score=0.0, blockers=(f"{field_name.upper()}_UNAVAILABLE",), **{field_name: nonready})
    assert value.eligibility == "INELIGIBLE"


@pytest.mark.parametrize("field_name", ("freshness", "data_quality", "session", "technical", "multi_timeframe", "regime", "option_chain", "option_contract_eligibility"))
def test_every_noneligible_state_requires_explicit_reason_for_nonready_canonical_evidence(field_name):
    nonready = nonready_canonical_input(field_name)
    with pytest.raises(ValueError, match="missing or non-ready canonical evidence"):
        build(eligibility="INELIGIBLE", direction="BULLISH", confidence=75.0, score=75.0, blockers=(), contradictions=(), **{field_name: nonready})
    assert build(eligibility="INELIGIBLE", direction="BULLISH", confidence=75.0, score=75.0, blockers=("NONREADY",), **{field_name: nonready}).eligibility == "INELIGIBLE"
    assert build(eligibility="UNAVAILABLE", direction="UNAVAILABLE", confidence=0.0, score=0.0, blockers=("NONREADY",), **{field_name: nonready}).eligibility == "UNAVAILABLE"
    assert build(eligibility="CONFLICTING", direction="CONFLICTING", confidence=75.0, score=75.0, contradictions=("NONREADY",), **{field_name: nonready}).eligibility == "CONFLICTING"


@pytest.mark.parametrize("field_name", ("freshness", "data_quality", "session", "technical", "multi_timeframe", "regime", "option_chain", "option_contract_eligibility"))
def test_eligible_candidate_rejects_each_nested_identity_mismatch(field_name):
    with pytest.raises(ValueError, match="identity mismatch"):
        build(**{field_name: valid_canonical_inputs("SENSEX")[field_name]})


def test_missing_canonical_evidence_for_unavailable_or_ineligible_needs_reason():
    with pytest.raises(ValueError, match="missing or non-ready canonical evidence requires blocker or contradiction"):
        unavailable_candidate(blockers=())
    assert unavailable_candidate().blockers == ("CANONICAL_EVIDENCE_UNAVAILABLE",)
    ineligible = build(eligibility="INELIGIBLE", confidence=0.0, score=0.0, freshness=None, blockers=("FRESHNESS_UNAVAILABLE",))
    assert ineligible.eligibility == "INELIGIBLE"


def test_optional_contexts_accept_matching_identity_and_reject_actual_mismatches():
    value = build(broader_market=broader_market("NIFTY", "NSE"), external_context=external_context("NIFTY", "NSE"))
    assert value.broader_market is not None and value.external_context is not None
    with pytest.raises(ValueError, match="broader_market identity mismatch"):
        build(broader_market=broader_market("SENSEX", "BSE"))
    with pytest.raises(ValueError, match="external_context identity mismatch"):
        build(external_context=external_context("SENSEX", "BSE"))


def test_ready_optional_contexts_are_accepted_independently():
    assert build(broader_market=broader_market("NIFTY", "NSE")).broader_market is not None
    assert build(external_context=external_context("NIFTY", "NSE")).external_context is not None


@pytest.mark.parametrize("field_name,context", (("broader_market", nonready_broader_market("NIFTY", "NSE")), ("external_context", nonready_external_context("NIFTY", "NSE"))))
def test_nonready_optional_context_fails_closed_for_eligible(field_name, context):
    with pytest.raises(ValueError, match="non-ready evidence"):
        build(**{field_name: context})


@pytest.mark.parametrize("field_name,context", (("broader_market", nonready_broader_market("NIFTY", "NSE")), ("external_context", nonready_external_context("NIFTY", "NSE"))))
def test_nonready_optional_context_requires_explicit_diagnostic_for_noneligible(field_name, context):
    with pytest.raises(ValueError, match="missing or non-ready canonical evidence"):
        build(eligibility="INELIGIBLE", direction="BULLISH", blockers=(), contradictions=(), **{field_name: context})
    assert build(eligibility="INELIGIBLE", direction="BULLISH", blockers=("CONTEXT_NONREADY",), **{field_name: context}).eligibility == "INELIGIBLE"
    assert build(eligibility="CONFLICTING", direction="CONFLICTING", contradictions=("CONTEXT_NONREADY",), **{field_name: context}).eligibility == "CONFLICTING"


def test_unavailable_or_conflicting_pillar_evidence_requires_explicit_reason():
    with pytest.raises(ValueError, match="requires blocker or contradiction"):
        build(volume=evidence("UNAVAILABLE"), eligibility="UNAVAILABLE", direction="UNAVAILABLE", confidence=0, score=0, blockers=())
    value = build(volume=evidence("UNAVAILABLE"), eligibility="UNAVAILABLE", direction="UNAVAILABLE", confidence=0, score=0, blockers=("VOLUME_UNAVAILABLE",))
    assert value.blockers == ("VOLUME_UNAVAILABLE",)


def test_ready_evidence_requires_source_and_retained_detail():
    with pytest.raises(ValueError, match="source_id"): evidence(source_ids=())
    with pytest.raises(ValueError, match="retained detail"): evidence(provenance={}, summary={})
    unavailable = MarketAnalysisEvidenceV1("UNAVAILABLE")
    assert unavailable.status == "UNAVAILABLE" and unavailable.source_ids == ()


def test_nested_mappings_and_lists_are_defensively_frozen():
    source = {"outer": {"items": ["one"]}}
    candidate_source = {"refs": {"items": ["two"]}}
    pillar = evidence(provenance=source, summary={"nested": ["three"]})
    value = build(price_action=pillar, evidence_references=candidate_source, provenance=source)
    source["outer"]["items"].append("changed")
    candidate_source["refs"]["items"].append("changed")
    assert value.price_action.provenance["outer"]["items"] == ("one",)
    assert value.price_action.summary["nested"] == ("three",)
    assert value.evidence_references["refs"]["items"] == ("two",)
    assert value.provenance["outer"]["items"] == ("one",)
    with pytest.raises(TypeError): value.provenance["new"] = "value"
    with pytest.raises(TypeError): value.provenance["outer"]["new"] = "value"


def test_eligible_candidate_requires_nonempty_traceability():
    with pytest.raises(ValueError, match="traceable evidence"): build(evidence_references={})
    with pytest.raises(ValueError, match="traceable evidence"): build(provenance={})


def test_identical_supplied_input_is_deterministic():
    assert build() == build()


def test_contract_has_no_prohibited_runtime_imports_or_side_effect_dependencies():
    path = Path(__file__).parents[1] / "services/contracts/market_analysis_candidate_v1.py"
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import): modules.update(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module: modules.add(node.module)
    forbidden = ("services.broker", "dashboard", "services.paper_orchestration", "services.paper_trading", "services.paper_portfolio", "services.opportunity_ranking", "services.market_ranking_engine", "services.analysis.option_chain", "archive", "requests", "random")
    assert not any(any(module == item or module.startswith(item + ".") for item in forbidden) for module in modules)
    for token in ("datetime.now(", "datetime.utcnow(", "uuid4(", "time.sleep(", "place_order("):
        assert token not in text
