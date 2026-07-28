"""Immutable, non-executable instruction for a future paper executor."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date, datetime
from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES

_MARKETS = SUPPORTED_MARKET_IDENTITIES

def _text(value, name):
    if not isinstance(value, str) or not value.strip(): raise ValueError(f"{name} is required.")
def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0: raise ValueError(f"{name} must be finite and positive.")
def _integer(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0: raise ValueError(f"{name} must be a positive integer.")
def _aware(value, name):
    if not isinstance(value, datetime) or value.tzinfo is None: raise ValueError(f"{name} must be timezone-aware.")

@dataclass(frozen=True, slots=True)
class PaperExecutionRequestV1:
    execution_request_id: str; created_at: datetime; authorization_id: str; idempotency_key: str
    snapshot_id: str; analysis_id: str; decision_id: str; trade_plan_result_id: str; trade_plan_id: str; sizing_result_id: str; canonical_risk_result_id: str; paper_candidate_id: str
    underlying_symbol: str; exchange: str; action: str; option_type: str; position_side: str; trading_symbol: str; expiry_date: date; strike: float
    lot_size: int; quantity: int; lots: int; entry_reference_price: float; stop_loss_price: float; target_price: float; capital_required: float; maximum_loss: float; reward_risk_ratio: float
    valid_from: datetime; valid_until: datetime; schema_version: str = "paper_execution_request.v1"; execution_mode: str = "PAPER"; live_execution_eligible: bool = False
    def __post_init__(self):
        if self.schema_version != "paper_execution_request.v1" or self.execution_mode != "PAPER" or self.live_execution_eligible is not False: raise ValueError("Paper-only non-live execution is required.")
        for name in ("execution_request_id","authorization_id","idempotency_key","snapshot_id","analysis_id","decision_id","trade_plan_result_id","trade_plan_id","sizing_result_id","canonical_risk_result_id","paper_candidate_id","underlying_symbol","exchange","action","option_type","position_side","trading_symbol"): _text(getattr(self,name),name)
        _aware(self.created_at,"created_at"); _aware(self.valid_from,"valid_from"); _aware(self.valid_until,"valid_until")
        if self.valid_until <= self.valid_from: raise ValueError("valid_until must be after valid_from.")
        if not isinstance(self.expiry_date,date) or isinstance(self.expiry_date,datetime): raise ValueError("expiry_date is required.")
        if (self.underlying_symbol,self.exchange) not in _MARKETS: raise ValueError("Unsupported underlying identity.")
        if (self.action,self.option_type) not in {("BUY","CALL"),("SELL","PUT")} or self.position_side != "LONG": raise ValueError("Only long BUY/CALL or SELL/PUT premium is supported.")
        for name in ("lot_size","quantity","lots"): _integer(getattr(self,name),name)
        if self.quantity != self.lots * self.lot_size: raise ValueError("quantity must equal lots times lot_size.")
        for name in ("strike","entry_reference_price","stop_loss_price","target_price","capital_required","maximum_loss","reward_risk_ratio"): _number(getattr(self,name),name)
        if self.stop_loss_price >= self.entry_reference_price or self.target_price <= self.entry_reference_price: raise ValueError("Invalid long-premium stop or target geometry.")
    def to_dict(self):
        return {name: (value.isoformat() if isinstance(value,(datetime,date)) else value) for name,value in ((name,getattr(self,name)) for name in self.__dataclass_fields__)}
    def to_json(self): return json.dumps(self.to_dict(),sort_keys=True,separators=(",",":"),allow_nan=False)
    def semantic_dict(self):
        value=self.to_dict(); value.pop("execution_request_id"); value.pop("created_at"); return value
