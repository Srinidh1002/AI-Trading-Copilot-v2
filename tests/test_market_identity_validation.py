from services.market_session import normalize_market_identity
def test_identity_aliases_and_cross_exchange_rejection():
    assert normalize_market_identity(" nifty 50 ","nse").canonical_symbol == "NIFTY"
    assert normalize_market_identity("SENSEX","NSE") is None
