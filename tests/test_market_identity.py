import pytest
from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES,SUPPORTED_MARKET_SYMBOLS,normalize_market_symbol,expected_exchange_for_symbol,normalize_market_identity,is_supported_market_identity
from services.market_session.identity import normalize_market_identity as session_identity
@pytest.mark.parametrize("pair",[("NIFTY","NSE"),("BANKNIFTY","NSE"),("FINNIFTY","NSE"),("SENSEX","BSE")])
def test_supported_pairs(pair):assert normalize_market_identity(*pair)==pair and is_supported_market_identity(*pair)
def test_supported_collections_are_ordered_and_immutable():
 assert SUPPORTED_MARKET_IDENTITIES==(("NIFTY","NSE"),("BANKNIFTY","NSE"),("FINNIFTY","NSE"),("SENSEX","BSE")) and SUPPORTED_MARKET_SYMBOLS==("NIFTY","BANKNIFTY","FINNIFTY","SENSEX")
@pytest.mark.parametrize("raw,canonical",[("NIFTY","NIFTY"),("NIFTY50","NIFTY"),("NIFTY 50","NIFTY"),(" nifty 50 ","NIFTY"),("BANKNIFTY","BANKNIFTY"),("BANK NIFTY","BANKNIFTY"),("NIFTY BANK","BANKNIFTY"),("FINNIFTY","FINNIFTY"),("FIN NIFTY","FINNIFTY"),("NIFTY FINANCIAL SERVICES","FINNIFTY"),("SENSEX","SENSEX"),("BSE SENSEX","SENSEX")])
def test_aliases(raw,canonical):assert normalize_market_symbol(raw)==canonical
@pytest.mark.parametrize("symbol,exchange",[("NIFTY","NSE"),("BANKNIFTY","NSE"),("FINNIFTY","NSE"),("SENSEX","BSE")])
def test_exchange_lookup(symbol,exchange):assert expected_exchange_for_symbol(symbol)==exchange
@pytest.mark.parametrize("symbol,exchange",[("NIFTY","NSE"),("BANKNIFTY","NSE"),("FINNIFTY","NSE"),("SENSEX","BSE")])
def test_omitted_exchange_resolves_to_canonical_pair(symbol,exchange):assert normalize_market_identity(symbol,None)==(symbol,exchange)
@pytest.mark.parametrize("symbol,exchange",[("NIFTY","BSE"),("BANKNIFTY","BSE"),("FINNIFTY","BSE"),("SENSEX","NSE"),("MIDCPNIFTY","NSE"),("", "NSE"),(" ","NSE"),(None,"NSE"),("NIFTY","")])
def test_rejections(symbol,exchange):assert normalize_market_identity(symbol,exchange) is None and not is_supported_market_identity(symbol,exchange)
@pytest.mark.parametrize("symbol,exchange",[("NIFTY","NSE"),("BANK NIFTY","NSE"),("FIN NIFTY","NSE"),("BSE SENSEX","BSE")])
def test_session_api_compatibility(symbol,exchange):
 value=session_identity(symbol,exchange);assert value and (value.canonical_symbol,value.exchange)==normalize_market_identity(symbol,exchange)
@pytest.mark.parametrize("index",range(20))
def test_outputs_are_deterministic(index):assert normalize_market_identity(" nifty "," nse ")==("NIFTY","NSE")
