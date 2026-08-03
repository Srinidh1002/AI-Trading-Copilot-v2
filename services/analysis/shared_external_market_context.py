"""Provider-free shared external-context construction for one PAPER parent cycle."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from services.contracts.external_context_policy_v1 import DEFAULT_EXTERNAL_CONTEXT_POLICY, ExternalContextPolicyV1
from services.contracts.external_market_context_result_v1 import ExternalMarketContextResultV1
from services.contracts.external_market_observation_v1 import ExternalMarketObservationV1
from services.contracts.institutional_flow_snapshot_v1 import InstitutionalFlowSnapshotV1
from services.contracts.scheduled_market_event_v1 import ScheduledMarketEventV1
from services.external_context.integration import evaluate_external_context_pipeline


@dataclass(frozen=True, slots=True)
class SharedExternalMarketContextV1:
    cycle_id: str
    evaluated_at: datetime
    nifty: ExternalMarketContextResultV1
    sensex: ExternalMarketContextResultV1
    build_count: int = 1
    global_provider_call_count: int = 0
    institutional_provider_call_count: int = 0
    event_provider_call_count: int = 0
    breadth_provider_call_count: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.cycle_id, str) or not self.cycle_id.strip() or not isinstance(self.evaluated_at, datetime) or self.evaluated_at.tzinfo is None:
            raise ValueError("shared external context identity")
        if type(self.nifty) is not ExternalMarketContextResultV1 or type(self.sensex) is not ExternalMarketContextResultV1:
            raise TypeError("external projections")
        if (self.nifty.underlying_symbol, self.nifty.exchange, self.sensex.underlying_symbol, self.sensex.exchange) != ("NIFTY", "NSE", "SENSEX", "BSE"):
            raise ValueError("external projection identity")
        if (self.build_count, self.global_provider_call_count, self.institutional_provider_call_count, self.event_provider_call_count, self.breadth_provider_call_count) != (1, 0, 0, 0, 0):
            raise ValueError("shared external context is provider-free and built once")

    def for_market(self, symbol: str, exchange: str) -> ExternalMarketContextResultV1:
        if (symbol, exchange) == ("NIFTY", "NSE"): return self.nifty
        if (symbol, exchange) == ("SENSEX", "BSE"): return self.sensex
        raise ValueError("market identity")


def build_shared_external_market_context(*, cycle_id: str, evaluated_at: datetime, policy: ExternalContextPolicyV1 = DEFAULT_EXTERNAL_CONTEXT_POLICY, observations: tuple[ExternalMarketObservationV1, ...] = (), institutional_snapshot: InstitutionalFlowSnapshotV1 | None = None, scheduled_events: tuple[ScheduledMarketEventV1, ...] = ()) -> SharedExternalMarketContextV1:
    if not isinstance(evaluated_at, datetime) or evaluated_at.tzinfo is None or type(policy) is not ExternalContextPolicyV1:
        raise ValueError("external context boundary")
    def project(symbol: str, exchange: str) -> ExternalMarketContextResultV1:
        prefix = f"{cycle_id}:external:{symbol.lower()}"
        return evaluate_external_context_pipeline(underlying_symbol=symbol, exchange=exchange, observations=observations, institutional_snapshot=institutional_snapshot, scheduled_events=scheduled_events, policy=policy, created_at=evaluated_at, global_result_id=f"{prefix}:global", institutional_result_id=f"{prefix}:institutional", event_result_id=f"{prefix}:event", aggregate_result_id=f"{prefix}:aggregate")
    return SharedExternalMarketContextV1(cycle_id, evaluated_at, project("NIFTY", "NSE"), project("SENSEX", "BSE"))
