from datetime import date,datetime,timezone
import pytest
from services.contracts import OptionContractEligibilityEvidenceV1
T=datetime(2026,1,1,tzinfo=timezone.utc)
def _e(**x):
 d=dict(evidence_id='e',candidate_id='c',underlying_symbol='NIFTY',exchange='NSE',option_right='CALL',trading_symbol='NIFTY-C',strike_price=25000.,expiry_date=date(2026,1,8),moneyness_steps=0,expiry_category='WEEKLY',days_to_expiry=0,evidence_timestamp=T,evidence_source='APPROVED_BOUNDARY',source_timestamps={'x':T},metadata={'x':[1]});d.update(x);return OptionContractEligibilityEvidenceV1(**d)
def test_valid_serialization():assert _e().to_json()==_e().to_json() and set(_e().to_dict())-set(_e().semantic_dict())=={'evidence_id','evidence_timestamp','source_timestamps'}
@pytest.mark.parametrize('k,v',[('moneyness_steps',-1),('expiry_category','DAILY'),('days_to_expiry',-1),('strike_price',0),('execution_mode','LIVE')])
def test_invalid(k,v):
 with pytest.raises(ValueError):_e(**{k:v})
