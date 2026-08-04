from datetime import datetime,timezone
from services.market_regime import evaluate_technical_regime_component
def test_missing_context_is_unavailable():
 t=datetime(2026,1,1,tzinfo=timezone.utc);assert evaluate_technical_regime_component(underlying_symbol="NIFTY",exchange="NSE",technical_context=None,created_at=t,result_id="r").context_status=="UNAVAILABLE"
