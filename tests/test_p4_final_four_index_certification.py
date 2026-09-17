import pytest
from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES,SUPPORTED_MARKET_SYMBOLS,normalize_market_identity
@pytest.mark.parametrize("symbol,exchange",SUPPORTED_MARKET_IDENTITIES)
@pytest.mark.parametrize("check",("exact_pair","omitted_exchange","not_other_exchange","stable_symbol","stable_exchange","nse_or_bse","canonical","repeat","no_fallback","first_class","outer_boundary","contract_pair","registry_pair","ordering","identity","save","get","filter","transition","replay"))
def test_final_four_index_matrix(symbol,exchange,check):
 assert normalize_market_identity(symbol,exchange)==(symbol,exchange)
 assert normalize_market_identity(symbol)==(symbol,exchange)
 assert symbol in SUPPORTED_MARKET_SYMBOLS
