from datetime import datetime,timezone
from services.external_context import evaluate_external_market_context
def test_empty_aggregate_is_unavailable():
 t=datetime(2026,1,1,tzinfo=timezone.utc);assert evaluate_external_market_context(underlying_symbol="NIFTY",exchange="NSE",global_context=None,institutional_context=None,event_context=None,created_at=t,result_id="r").context_status=="UNAVAILABLE"
