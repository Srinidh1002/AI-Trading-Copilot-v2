"""Explicit bridge between a prediction's underlying and its PAPER option venue."""
from __future__ import annotations

from dataclasses import dataclass

from services.certification.task9_prediction_paper_trade_binding_store import Task9PredictionPaperTradeBindingV1
from services.contracts.prediction_record_v1 import PredictionRecordV1
from services.underlying_registry import UnderlyingRegistry


@dataclass(frozen=True, slots=True)
class Task9PredictionPaperMarketIdentityV1:
    prediction_id: str
    underlying_symbol: str
    underlying_exchange: str
    derivative_exchange: str
    option_symbol: str
    paper_trade_id: str
    position_id: str
    execution_mode: str = "PAPER"
    broker_order_submission: bool = False
    live_execution_eligible: bool = False
    schema_version: str = "task9_prediction_paper_market_identity.v1"

    def __post_init__(self) -> None:
        for name in ("prediction_id", "underlying_symbol", "underlying_exchange", "derivative_exchange", "option_symbol", "paper_trade_id", "position_id"):
            value = getattr(self, name)
            if type(value) is not str or not value.strip():
                raise ValueError(name)
            object.__setattr__(self, name, value.strip().upper() if name in {"underlying_symbol", "underlying_exchange", "derivative_exchange"} else value.strip())
        authority = UnderlyingRegistry.get(self.underlying_symbol)
        if (self.underlying_exchange, self.derivative_exchange) != (authority.exchange, authority.option_exchange):
            raise ValueError("unsupported underlying/derivative venue relationship")
        if self.execution_mode != "PAPER" or self.broker_order_submission or self.live_execution_eligible or self.schema_version != "task9_prediction_paper_market_identity.v1":
            raise ValueError("PAPER-only identity bridge")


def build_task9_prediction_paper_market_identity(*, prediction: PredictionRecordV1, binding: Task9PredictionPaperTradeBindingV1) -> Task9PredictionPaperMarketIdentityV1:
    if type(prediction) is not PredictionRecordV1 or type(binding) is not Task9PredictionPaperTradeBindingV1:
        raise TypeError("prediction identity bridge inputs")
    if (prediction.prediction_id, prediction.underlying_symbol) != (binding.prediction_id, binding.market):
        raise ValueError("prediction binding identity mismatch")
    return Task9PredictionPaperMarketIdentityV1(
        prediction_id=prediction.prediction_id, underlying_symbol=prediction.underlying_symbol,
        underlying_exchange=prediction.exchange, derivative_exchange=binding.derivative_exchange,
        option_symbol=binding.option_symbol, paper_trade_id=binding.paper_trade_id,
        position_id=binding.paper_position_id,
    )
