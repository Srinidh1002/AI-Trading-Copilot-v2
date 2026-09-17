from datetime import datetime,timezone
import pytest
from services.broader_market_intelligence import evaluate_market_breadth
from services.contracts.market_breadth_snapshot_v1 import MarketBreadthSnapshotV1
NOW=datetime(2026,1,1,tzinfo=timezone.utc)
@pytest.mark.parametrize(("symbol","exchange"),(("NIFTY","NSE"),("BANKNIFTY","NSE"),("FINNIFTY","NSE"),("SENSEX","BSE")))
def test_four_identities(symbol,exchange):
 s=MarketBreadthSnapshotV1("b",NOW,symbol,exchange,"source",NOW,60,30,10,100,100)
 assert evaluate_market_breadth(breadth_snapshot=s,created_at=NOW,evidence_id="e").underlying_symbol==symbol
