from datetime import datetime,timezone
from services.contracts import CapitalQuantityTradingCostPolicyV1
def test_policy():assert CapitalQuantityTradingCostPolicyV1('p','CALLER_SUPPLIED_EVIDENCE',policy_timestamp=datetime(2026,1,1,tzinfo=timezone.utc)).execution_mode=='PAPER'
