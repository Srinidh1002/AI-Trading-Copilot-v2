import pytest
from services.core.provider_market_adapter import *
from services.core.market_universe import CANONICAL_MARKET_IDENTITIES
@pytest.mark.parametrize("provider",("YFINANCE","ANGEL_SMARTAPI","NSE_OPTION_CHAIN"))
@pytest.mark.parametrize("symbol,exchange",CANONICAL_MARKET_IDENTITIES)
@pytest.mark.parametrize("check",range(6))
def test_provider_mapping_is_static_and_observable(provider,symbol,exchange,check):
 value=get_provider_market_mapping(provider,symbol,exchange);assert value.provider==provider and (value.underlying_symbol,value.exchange)==(symbol,exchange)
def test_only_proven_nse_nifty_mapping_resolves():assert resolve_provider_symbol("NSE_OPTION_CHAIN","NIFTY")=="NIFTY"
@pytest.mark.parametrize("provider",("YFINANCE","ANGEL_SMARTAPI"))
def test_unknown_provider_mappings_fail_closed(provider):
 with pytest.raises(ValueError):resolve_provider_symbol(provider,"NIFTY")
