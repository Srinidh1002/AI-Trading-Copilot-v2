import pytest
from services.broader_market_intelligence import build_broader_market_intelligence
from tests.fixtures.broader_market_intelligence import NOW,PAIRS,series,breadth,volatility
@pytest.mark.parametrize(("symbol","exchange","related","related_exchange"),PAIRS)
def test_fresh_confirmation_matrix(symbol,exchange,related,related_exchange):
 result=build_broader_market_intelligence(primary_series=series(symbol,exchange),related_series=series(related,related_exchange),breadth_snapshot=breadth(symbol,exchange),volatility_snapshot=volatility(symbol,exchange),created_at=NOW,cross_market_evidence_id="cross",breadth_evidence_id="breadth",volatility_context_id="vix",result_id="result")
 assert result.underlying_symbol==symbol;assert result.confirmation_state=="CONFIRMING";assert result.aggregate_bias=="BULLISH";assert result.live_execution_eligible is False;assert "CROSS_MARKET:"+related in result.source_timestamps
