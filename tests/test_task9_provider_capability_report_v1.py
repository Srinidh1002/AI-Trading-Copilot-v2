from dataclasses import FrozenInstanceError
import pytest
from services.contracts.task9_provider_capability_report_v1 import *

def test_state_and_report_are_immutable_deterministic_and_round_trip():
 state=Task9ProviderCapabilityStateV1(Task9ProviderFamily.ANGEL_SPOT,Task9ProviderCapability.SPOT_QUOTES,"NIFTY","NSE",True,ProviderFeatureStateV1.ENABLED_REQUIRED,Task9ProviderSupportStatus.DOCUMENTED,Task9ProviderSupportStatus.IMPLEMENTED,Task9LiveProofStatus.PENDING,Task9ProviderReadinessStatus.READY_PENDING_LIVE_PROOF,Task9StartupSemantic.STARTUP_BLOCKED_RETRYABLE,evidence_refs=("evidence:1",))
 report=Task9ProviderCapabilityReportV1("runtime-1","1",(state,))
 with pytest.raises(FrozenInstanceError):report.runtime_config_id="other"
 assert Task9ProviderCapabilityReportV1.from_dict(report.to_dict())==report
 with pytest.raises(ValueError,match="duplicate") :Task9ProviderCapabilityReportV1("runtime-1","1",(state,state))
 with pytest.raises(ValueError):Task9ProviderCapabilityStateV1(Task9ProviderFamily.ANGEL_SPOT,Task9ProviderCapability.SPOT_QUOTES,None,None,True,ProviderFeatureStateV1.ENABLED_REQUIRED,Task9ProviderSupportStatus.DOCUMENTED,Task9ProviderSupportStatus.IMPLEMENTED,Task9LiveProofStatus.PENDING,Task9ProviderReadinessStatus.READY,None)
