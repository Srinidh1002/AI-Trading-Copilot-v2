import pytest
@pytest.mark.parametrize("repeat",range(35))
def test_universe_imports_are_static_and_provider_free(repeat):
 import services.core.market_universe as universe,services.core.provider_market_adapter as adapter
 assert not any(name in universe.__dict__ or name in adapter.__dict__ for name in ("yfinance","requests","SmartApi","streamlit"))
