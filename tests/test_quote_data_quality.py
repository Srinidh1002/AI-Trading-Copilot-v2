import pytest
from services.data_quality import evaluate_market_quote_quality
from test_market_quote_v1 import quote,NOW
@pytest.mark.parametrize("n",range(75))
def test_quote_quality(n):assert evaluate_market_quote_quality(quote(),clock=lambda:NOW).quality_status=="VALID"
