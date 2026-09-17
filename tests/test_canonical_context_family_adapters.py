"""Provider-free integration tests for bounded broader/external ownership."""
from services.analysis.canonical_evidence_family_adapters import broader_market_family, external_context_family
from tests.fixtures.p5_12 import STRONG_BULLISH, CONFLICTING, UNAVAILABLE, BLOCKED, build_broader_market_intelligence, build_external_context

def test_broader_confirmation_and_divergence_are_non_directional_context_only():
    confirming=broader_market_family(build_broader_market_intelligence(("NIFTY","NSE"),STRONG_BULLISH))
    conflicting=broader_market_family(build_broader_market_intelligence(("NIFTY","NSE"),CONFLICTING))
    assert (confirming.role,confirming.direction,confirming.strength)==("CONFIRMATION","NEUTRAL",0)
    assert (conflicting.role,conflicting.direction,conflicting.strength)==("CONTRADICTION","NEUTRAL",0)

def test_broader_unavailable_and_missing_breadth_remain_explicitly_unavailable():
    value=broader_market_family(build_broader_market_intelligence(("NIFTY","NSE"),UNAVAILABLE))
    assert (value.status,value.direction,value.strength)==("UNAVAILABLE","UNAVAILABLE",0)

def test_external_unavailable_is_not_neutral_or_blocking_but_event_block_is_gate():
    unavailable=external_context_family(build_external_context(("NIFTY","NSE"),UNAVAILABLE))
    blocked=external_context_family(build_external_context(("NIFTY","NSE"),BLOCKED))
    assert (unavailable.role,unavailable.status,unavailable.direction)==("INFORMATIONAL","UNAVAILABLE","UNAVAILABLE")
    assert (blocked.role,blocked.status,blocked.direction)==("ENTRY_RESTRICTION","BLOCKED","NEUTRAL")

def test_external_contradiction_is_preserved_without_a_directional_vote():
    value=external_context_family(build_external_context(("NIFTY","NSE"),CONFLICTING))
    assert (value.role,value.status,value.direction,value.strength)==("CONTRADICTION","AVAILABLE","NEUTRAL",0)
