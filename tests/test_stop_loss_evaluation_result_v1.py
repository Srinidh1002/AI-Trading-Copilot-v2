from datetime import datetime,timezone
import pytest
from services.contracts import StopLossEvaluationResultV1
T=datetime(2026,1,2,tzinfo=timezone.utc)
def _r(**x):
 d=dict(evaluation_result_id='r',evaluation_id='e',evaluated_at=T,underlying_symbol='NIFTY',exchange='NSE',direction='BULLISH',option_right='CALL',stop_method='ATR',selected_stop_source='ATR',status='READY',stop_loss_price=95.,stop_reference_price=100.,stop_distance=5.,stop_distance_fraction=.05,minimum_stop_distance_fraction=.01,maximum_stop_distance_fraction=.2,invalidation_rules=('STOP_OPTION_PREMIUM_BREACH',),source_timestamps={'x':T},metadata={'x':[1]});d.update(x);return StopLossEvaluationResultV1(**d)
def test_ready_serialization_and_properties():
 v=_r();assert (v.risk_per_unit,v.distance_from_entry_fraction)==(5.,.05);assert v.to_json()==v.to_json();assert set(v.to_dict())-set(v.semantic_dict())=={'evaluation_result_id','evaluation_id','evaluated_at','source_timestamps'}
def test_blocked_and_no_stop():assert _r(status='BLOCKED',selected_stop_source=None,stop_loss_price=None,stop_reference_price=None,stop_distance=None,stop_distance_fraction=None,minimum_stop_distance_fraction=None,maximum_stop_distance_fraction=None,blockers=('X',),invalidation_rules=()).status=='BLOCKED';assert _r(status='NO_STOP',selected_stop_source=None,stop_loss_price=None,stop_reference_price=None,stop_distance=None,stop_distance_fraction=None,minimum_stop_distance_fraction=None,maximum_stop_distance_fraction=None,decision_reasons=('X',),invalidation_rules=()).status=='NO_STOP'
@pytest.mark.parametrize('x',[{'stop_loss_price':101.},{'status':'READY','invalidation_rules':()},{'execution_mode':'LIVE'}])
def test_invalid(x):
 with pytest.raises(ValueError):_r(**x)
