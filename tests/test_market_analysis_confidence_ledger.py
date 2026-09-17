from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from services.contracts.market_analysis_confidence_ledger_v1 import MarketAnalysisConfidenceEntryV1, MarketAnalysisConfidenceLedgerV1

NOW=datetime(2026,8,3,10,tzinfo=ZoneInfo("Asia/Kolkata"))
def entry(**changes):
    values=dict(entry_id="cycle:policy",entry_type="DIRECTIONAL",source_component="candidate_policy",source_result_id=None,pillar_name=None,underlying_symbol="NIFTY",exchange="NSE",cycle_id="cycle",observation_id="observation",direction="BULLISH",raw_value=80.0,normalized_value=.8,weight=1.0,weighted_value=80.0,adjustment_value=0.0,counted=True,exclusion_reason=None,source_timestamp=None,evaluated_at=NOW)
    values.update(changes);return MarketAnalysisConfidenceEntryV1(**values)
def ledger(entries=(entry(),)):
    return MarketAnalysisConfidenceLedgerV1("ledger","NIFTY","NSE","cycle","observation",NOW,80,80,80,0,0,0,0,0,80,80,"BULLISH","READY",entries)
def test_contract_is_paper_only_deterministic_and_immutable():
    assert ledger().to_json()==ledger().to_json()
    with pytest.raises(ValueError): entry(execution_mode="LIVE")
    with pytest.raises(ValueError): entry(metadata={"api_key":"x"})
    with pytest.raises(ValueError): entry(normalized_value=1.1)
    with pytest.raises(ValueError): ledger((entry(entry_id="z"),entry(entry_id="a")))
