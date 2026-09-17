from datetime import datetime,timezone
from unittest.mock import Mock
from tests.test_cross_market_correlation_evaluator import series,NOW
from services.broader_market_intelligence import build_broader_market_intelligence
def test_correlation_then_aggregate_once():
 correlation=object();aggregate=Mock(return_value="result");correlator=Mock(return_value=correlation)
 value=build_broader_market_intelligence(primary_series=series(),related_series=series("SENSEX","BSE"),created_at=NOW,cross_market_evidence_id="c",result_id="r",correlation_evaluator=correlator,aggregate_evaluator=aggregate)
 assert value=="result";correlator.assert_called_once();aggregate.assert_called_once();assert aggregate.call_args.kwargs["cross_market_evidence"]==(correlation,)
