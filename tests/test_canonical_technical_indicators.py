import math
import pytest
from services.technical_intelligence import calculate_sma,calculate_ema,calculate_rsi,calculate_macd,calculate_true_range,calculate_atr,calculate_adx,calculate_bollinger_bands,calculate_vwap,calculate_volume_average

VALUES=tuple(float(x) for x in range(1,81)); H=tuple(x+1 for x in VALUES); L=tuple(x-1 for x in VALUES); V=tuple(float(x*10) for x in range(1,81))

@pytest.mark.parametrize("period",range(1,31))
def test_sma_and_ema_are_deterministic(period):
    assert calculate_sma(VALUES,period)==calculate_sma(VALUES,period)
    assert calculate_ema(VALUES,period)==calculate_ema(VALUES,period)
@pytest.mark.parametrize("period",range(1,21))
def test_rsi_is_finite_and_bounded(period):
    value=calculate_rsi(VALUES,period);assert value is not None and 0<=value<=100
@pytest.mark.parametrize("period",range(1,21))
def test_atr_is_finite(period):
    value=calculate_atr(H,L,VALUES,period);assert value is not None and math.isfinite(value)
@pytest.mark.parametrize("period",range(1,21))
def test_bollinger_is_ordered(period):
    bands=calculate_bollinger_bands(VALUES,period,2.0);assert bands is not None and bands[0]<=bands[1]<=bands[2]
@pytest.mark.parametrize("period",range(1,11))
def test_volume_average_is_finite(period):assert calculate_volume_average(V,period) is not None
@pytest.mark.parametrize("bad",[[],[1,float("nan")],[True,2],"abc",None])
def test_numeric_input_validation_returns_none(bad):
    assert calculate_sma(bad,2) is None
    assert calculate_ema(bad,2) is None
@pytest.mark.parametrize("period",[0,-1,True,1.5,None])
def test_invalid_period_returns_none(period):
    assert calculate_sma(VALUES,period) is None
    assert calculate_rsi(VALUES,period) is None
def test_known_sma():assert calculate_sma((1,2,3,4),2)==3.5
def test_known_ema_seed():assert calculate_ema((1,2,3),2)==2.5
def test_flat_rsi_is_neutral():assert calculate_rsi((4,4,4,4),2)==50.0
def test_true_range():assert calculate_true_range((10,12),(8,9),(9,10))==(2.0,3.0)
def test_macd_has_three_finite_values():
    answer=calculate_macd(VALUES,12,26,9);assert answer and len(answer)==3 and all(math.isfinite(x) for x in answer)
def test_macd_rejects_bad_period_order():assert calculate_macd(VALUES,26,12,9) is None
def test_adx_is_bounded():
    answer=calculate_adx(H,L,VALUES,14);assert answer is not None and 0<=answer<=100
def test_vwap():assert calculate_vwap((2,4),(0,2),(1,3),(1,1))==2.0
def test_zero_volume_vwap_unavailable():assert calculate_vwap((2,4),(0,2),(1,3),(0,0)) is None
def test_insufficient_history_never_fabricates():
    assert calculate_rsi((1,2),14) is None and calculate_macd((1,2),12,26,9) is None and calculate_bollinger_bands((1,2),20,2) is None
