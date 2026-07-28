from datetime import datetime,timezone
from services.market_regime import evaluate_external_context_regime_component
from services.contracts import DEFAULT_MARKET_REGIME_POLICY
def test_missing_context():
 t=datetime(2026,1,1,tzinfo=timezone.utc);assert evaluate_external_context_regime_component(underlying_symbol="NIFTY",exchange="NSE",external_market_context=None,policy=DEFAULT_MARKET_REGIME_POLICY,created_at=t,result_id="r").context_status=="UNAVAILABLE"
