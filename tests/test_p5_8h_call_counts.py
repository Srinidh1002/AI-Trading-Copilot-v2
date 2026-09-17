from unittest.mock import Mock
from tests.test_cross_market_correlation_evaluator import series,NOW
from tests.test_market_breadth_evaluator import snap
from tests.test_volatility_snapshot_v1 import make
from services.broader_market_intelligence import build_broader_market_intelligence
def test_optional_evaluators_called_once_only_when_present():
 c,b,v,a=Mock(return_value=object()),Mock(return_value=object()),Mock(return_value=object()),Mock(return_value="r")
 build_broader_market_intelligence(primary_series=series(),related_series=series("SENSEX","BSE"),breadth_snapshot=snap(),volatility_snapshot=make(),created_at=NOW,cross_market_evidence_id="c",breadth_evidence_id="b",volatility_context_id="v",result_id="r",correlation_evaluator=c,breadth_evaluator=b,volatility_evaluator=v,aggregate_evaluator=a)
 c.assert_called_once();b.assert_called_once();v.assert_called_once();a.assert_called_once()
