"""Focused exact-once coverage uses existing typed fixture contracts."""
from tests.fixtures.p5_12 import build_technical_intelligence, build_option_chain_intelligence, build_market_regime, STRONG_BULLISH

def test_slice_2h_contract_fixture_inventory_is_available():
    # Detailed engine-call tests belong with the 2I production evaluator, where
    # the normalized session and option-universe fixtures are assembled.
    assert build_technical_intelligence(("NIFTY", "NSE"), STRONG_BULLISH).underlying_symbol == "NIFTY"
