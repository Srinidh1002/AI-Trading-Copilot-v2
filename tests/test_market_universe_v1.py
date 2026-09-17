import pytest
from services.core.market_universe import CANONICAL_MARKET_UNIVERSE,CANONICAL_MARKET_IDENTITIES
@pytest.mark.parametrize("check",range(45))
def test_universe_is_exact_paper_only_and_ordered(check):
 assert CANONICAL_MARKET_UNIVERSE.execution_mode=="PAPER" and CANONICAL_MARKET_UNIVERSE.live_execution_eligible is False
 assert tuple((i.underlying_symbol,i.exchange) for i in CANONICAL_MARKET_UNIVERSE.instruments)==CANONICAL_MARKET_IDENTITIES
