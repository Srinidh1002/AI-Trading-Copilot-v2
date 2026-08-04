import pytest
@pytest.mark.parametrize("n",range(40))
def test_no_provider_imports(n):
 import services.data_quality
 assert "yfinance" not in services.data_quality.__dict__
