from datetime import date,datetime,timezone
import pytest
from services.contracts.pre_market_brain_v1 import PreMarketBrainV1
def test_premarket_is_non_authorizing_with_missing_context():
 x=PreMarketBrainV1(date(2026,8,14),"NIFTY","NSE",datetime.now(timezone.utc),False)
 assert x.external_status=="UNAVAILABLE" and x.official_live_count==0
 with pytest.raises(ValueError): PreMarketBrainV1(date.today(),"NIFTY","NSE",datetime.now(timezone.utc),False,official_live_count=1)
