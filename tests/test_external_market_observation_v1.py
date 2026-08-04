from datetime import datetime,timezone
from dataclasses import FrozenInstanceError
import pytest
from services.contracts.external_market_observation_v1 import ExternalMarketObservationV1
NOW=datetime(2026,1,1,tzinfo=timezone.utc)
def make(**x):
 d=dict(external_market_observation_id="o",created_at=NOW,canonical_name="SP500",observation_type="INDEX_CLOSE",market_region="UNITED_STATES",asset_class="EQUITY_INDEX",source_id="s",source_timestamp=NOW,session_reference="PREVIOUS_SESSION_CLOSE",current_value=101,previous_value=100,change_value=1,change_percent=1,direction="POSITIVE",observation_status="READY")
 d.update(x);return ExternalMarketObservationV1(**d)
def test_ready_frozen_and_semantic(): 
 with pytest.raises(FrozenInstanceError):make().current_value=2
 assert "external_market_observation_id" not in make().semantic_dict()
def test_mapping_and_numeric_validation():
 with pytest.raises(ValueError):make(canonical_name="DXY",observation_type="INDEX_CLOSE")
 with pytest.raises(ValueError):make(change_percent=2)
