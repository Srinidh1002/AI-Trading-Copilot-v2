import pytest
from services.core.market_universe import *
@pytest.mark.parametrize("symbol,exchange",CANONICAL_MARKET_IDENTITIES)
@pytest.mark.parametrize("check",range(18))
def test_universe_resolves_canonical_identity_and_omitted_exchange(symbol,exchange,check):
 assert resolve_market_identity(symbol)==(symbol,exchange) and get_market_instrument(symbol).exchange==exchange
@pytest.mark.parametrize("value",("NIFTY 50","BANK NIFTY","NIFTY BANK","FIN NIFTY","NIFTY FINANCIAL SERVICES","BSE SENSEX"))
def test_existing_aliases_resolve_at_boundary(value):assert resolve_market_alias(value) in CANONICAL_MARKET_SYMBOLS
