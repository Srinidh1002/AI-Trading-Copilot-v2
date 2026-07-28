import pytest
from tests.test_external_market_observation_v1 import make
@pytest.mark.parametrize(("name","typ","region","asset"),(("GIFT_NIFTY","PREMARKET_INDICATOR","INDIA","EQUITY_INDEX_FUTURE"),("NASDAQ","INDEX_CLOSE","UNITED_STATES","EQUITY_INDEX"),("NIKKEI_225","INDEX_CLOSE","ASIA","EQUITY_INDEX"),("DXY","FX_INDEX","GLOBAL","FX"),("BRENT_CRUDE","COMMODITY","GLOBAL","COMMODITY"),("US_10Y_YIELD","BOND_YIELD","UNITED_STATES","FIXED_INCOME")))
def test_controlled_observation_matrix(name,typ,region,asset):assert make(canonical_name=name,observation_type=typ,market_region=region,asset_class=asset)
