from __future__ import annotations
import json, math
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Any, Mapping

@dataclass(frozen=True, slots=True)
class PaperOrchestrationPolicyV1:
    orchestration_policy_id: str
    policy_timestamp: datetime
    supported_instruments: tuple[str, ...] = ("NIFTY","SENSEX")
    supported_exchanges: tuple[str, ...] = ("NSE","BSE")
    observation_frequency_seconds: float = 60.0
    maximum_observation_age_seconds: float = 120.0
    maximum_future_skew_seconds: float = 5.0
    analysis_cooldown_seconds: float = 60.0
    duplicate_signal_cooldown_seconds: float = 300.0
    entry_monitoring_frequency_seconds: float = 15.0
    open_position_monitoring_frequency_seconds: float = 15.0
    entry_cutoff_time: time = time(15,0)
    maximum_retry_attempts: int = 2
    retry_delay_seconds: float = 2.0
    require_strict_session_for_paper_action: bool = True
    require_persistence: bool = True
    emergency_paper_halt: bool = False
    execution_mode: str = "PAPER"
    live_execution_eligible: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = "paper_orchestration_policy.v1"

    def __post_init__(self):
        if self.schema_version != "paper_orchestration_policy.v1":
            raise ValueError("unsupported schema_version")
        if not self.orchestration_policy_id:
            raise ValueError("orchestration_policy_id")
        if self.policy_timestamp.tzinfo is None:
            raise ValueError("policy_timestamp")
        if set(map(str.upper,self.supported_instruments)) != {"NIFTY","SENSEX"}:
            raise ValueError("supported_instruments")
        if set(map(str.upper,self.supported_exchanges)) != {"NSE","BSE"}:
            raise ValueError("supported_exchanges")
        for name in ("observation_frequency_seconds","maximum_observation_age_seconds","maximum_future_skew_seconds","analysis_cooldown_seconds","duplicate_signal_cooldown_seconds","entry_monitoring_frequency_seconds","open_position_monitoring_frequency_seconds","retry_delay_seconds"):
            value=float(getattr(self,name))
            if not math.isfinite(value) or value < 0:
                raise ValueError(name)
            object.__setattr__(self,name,value)
        if self.execution_mode != "PAPER" or self.live_execution_eligible:
            raise ValueError("PAPER-only")
        object.__setattr__(self,"metadata",dict(self.metadata))

    def to_dict(self):
        result={name:getattr(self,name) for name in self.__dataclass_fields__}
        result["policy_timestamp"]=self.policy_timestamp.isoformat()
        result["supported_instruments"]=list(self.supported_instruments)
        result["supported_exchanges"]=list(self.supported_exchanges)
        result["entry_cutoff_time"]=self.entry_cutoff_time.isoformat()
        result["metadata"]=dict(sorted(self.metadata.items()))
        return result

    def to_json(self):
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
