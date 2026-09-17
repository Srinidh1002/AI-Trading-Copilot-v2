import pytest
from services.data_quality import evaluate_provider_quote_consensus
from test_market_quote_v1 import quote,NOW
@pytest.mark.parametrize("n",range(65))
def test_consensus(n):assert evaluate_provider_quote_consensus((quote(),),clock=lambda:NOW).quality_status=="VALID"
