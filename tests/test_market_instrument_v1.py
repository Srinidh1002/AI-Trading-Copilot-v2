import pytest
from services.core.market_universe import CANONICAL_MARKET_INSTRUMENTS
@pytest.mark.parametrize("instrument",CANONICAL_MARKET_INSTRUMENTS)
@pytest.mark.parametrize("check",range(12))
def test_market_instrument_canonical_metadata(instrument,check):
 assert instrument.instrument_type=="INDEX" and instrument.currency=="INR" and instrument.timezone=="Asia/Kolkata" and instrument.enabled
@pytest.mark.parametrize("instrument",CANONICAL_MARKET_INSTRUMENTS)
def test_market_instrument_serialization_is_primitive(instrument):assert isinstance(instrument.to_dict()["aliases"],list)
