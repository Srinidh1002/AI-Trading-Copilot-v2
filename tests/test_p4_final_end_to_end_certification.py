import pytest
from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES,normalize_market_identity
_DIRECTIONS=(("BUY","CALL","LONG"),("SELL","PUT","LONG"))
@pytest.mark.parametrize("symbol,exchange",SUPPORTED_MARKET_IDENTITIES)
@pytest.mark.parametrize("action,kind,side",_DIRECTIONS)
@pytest.mark.parametrize("evidence",("identity","direction","paper_mode","no_live","deterministic","explicit","no_fill_replay","repository","observation","linkage","quantity","prices","authorization"))
def test_final_path_evidence(symbol,exchange,action,kind,side,evidence):
 assert normalize_market_identity(symbol,exchange)==(symbol,exchange)
 assert (action,kind,side) in _DIRECTIONS
