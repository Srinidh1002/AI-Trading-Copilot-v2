from datetime import datetime, timezone
from dataclasses import FrozenInstanceError
import pytest
from services.contracts import TechnicalIndicatorValueV1, TimeframeTechnicalEvidenceV1

NOW=datetime(2025,1,1,tzinfo=timezone.utc); C=("TREND","MOMENTUM","VOLATILITY","VOLUME","LEVELS","PATTERNS")
def indicator(timeframe="5m", **changes):
    data=dict(indicator_name="RSI",timeframe=timeframe,value=50.,signal="NEUTRAL",status="VALID",minimum_required_candles=15,available_complete_candles=20)
    data.update(changes);return TechnicalIndicatorValueV1(**data)
def valid(**changes):
    data=dict(timeframe_technical_evidence_id="te",created_at=NOW,underlying_symbol="NIFTY",exchange="NSE",timeframe="5m",timeframe_evidence_id="e",indicators=(indicator(),),category_biases=tuple((x,"NEUTRAL") for x in C),category_strengths=tuple((x,.5) for x in C))
    data.update(changes); return TimeframeTechnicalEvidenceV1(**data)
@pytest.mark.parametrize("symbol,exchange",[("NIFTY","NSE"),("BANKNIFTY","NSE"),("FINNIFTY","NSE"),("SENSEX","BSE")])
@pytest.mark.parametrize("timeframe",["5m","15m","1h","1d"])
def test_valid_four_market_evidence(symbol,exchange,timeframe):
    assert valid(underlying_symbol=symbol,exchange=exchange,timeframe=timeframe,indicators=(indicator(timeframe),)).timeframe==timeframe
@pytest.mark.parametrize("change",[{"underlying_symbol":"NIFTY","exchange":"BSE"},{"timeframe":"1m"},{"created_at":datetime(2025,1,1)},{"execution_mode":"LIVE"},{"live_execution_eligible":True},{"category_biases":(("TREND","NEUTRAL"),)},{"category_strengths":(("TREND",.5),)},{"category_biases":tuple((x,"BUY") for x in C)},{"category_strengths":tuple((x,1.5) for x in C)}])
def test_invalid_evidence_rejected(change):
    with pytest.raises(ValueError):valid(**change)
@pytest.mark.parametrize("signal",["BULLISH","BEARISH","NEUTRAL","OVERBOUGHT","OVERSOLD","EXPANDING","CONTRACTING","HIGH","LOW","NONE"])
def test_indicator_signals_are_preserved(signal): assert valid(indicators=(indicator(signal=signal),)).indicators[0].signal==signal
@pytest.mark.parametrize("strength",[0.,.1,.2,.3,.4,.5,.6,.7,.8,.9,1.])
def test_strength_boundaries(strength): assert valid(category_strengths=tuple((x,strength) for x in C)).category_strengths[0][1]==strength
def test_duplicate_indicator_rejected():
    with pytest.raises(ValueError):valid(indicators=(indicator(),indicator()))
def test_indicator_timeframe_mismatch_rejected():
    with pytest.raises(ValueError):valid(indicators=(indicator("15m"),))
def test_serialization_is_deterministic():assert valid().to_dict()==valid().to_dict()
def test_frozen():
    with pytest.raises(FrozenInstanceError):valid().timeframe="1h"

@pytest.mark.parametrize("bias",["BULLISH","BEARISH","NEUTRAL","UNAVAILABLE"])
def test_category_biases_are_controlled(bias):
    assert valid(category_biases=tuple((x,bias) for x in C)).category_biases[0][1] == bias
def test_empty_indicator_collection_is_valid_evidence(): assert valid(indicators=()).indicators == ()
