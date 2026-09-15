"""Explicit durable Task 9 prediction-to-PAPER-entry binding."""
from __future__ import annotations

from services.certification.task9_atomic_file_replace import replace_task9_atomic_file
import json, os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from services.underlying_registry import UnderlyingRegistry

@dataclass(frozen=True, slots=True)
class Task9PredictionPaperTradeBindingV1:
    official_run_id: str; prediction_id: str; market: str; paper_trade_id: str; paper_position_id: str; option_symbol: str; entered_at: datetime
    execution_mode: str = "PAPER"; broker_order_submission: bool = False; live_execution_eligible: bool = False
    underlying_exchange: str | None = None; derivative_exchange: str | None = None
    def __post_init__(self):
        if any(type(getattr(self, n)) is not str or not getattr(self, n).strip() for n in ("official_run_id","prediction_id","market","paper_trade_id","paper_position_id","option_symbol")): raise ValueError("binding identity")
        if self.market not in {"NIFTY", "SENSEX"} or self.entered_at.tzinfo is None or self.execution_mode != "PAPER" or self.broker_order_submission or self.live_execution_eligible: raise ValueError("PAPER binding")
        authority = UnderlyingRegistry.get(self.market)
        underlying_exchange = authority.exchange if self.underlying_exchange is None else self.underlying_exchange.strip().upper()
        derivative_exchange = authority.option_exchange if self.derivative_exchange is None else self.derivative_exchange.strip().upper()
        if (underlying_exchange, derivative_exchange) != (authority.exchange, authority.option_exchange): raise ValueError("binding market venues")
        object.__setattr__(self, "underlying_exchange", underlying_exchange)
        object.__setattr__(self, "derivative_exchange", derivative_exchange)
    def to_dict(self):
        value = asdict(self); value["entered_at"] = self.entered_at.isoformat(); return value

class Task9PredictionPaperTradeBindingStore:
    def __init__(self, file_path: str | Path): self.file_path = Path(file_path)
    def _read(self):
        if not self.file_path.exists(): return {"version": 1, "by_prediction": {}, "by_trade": {}}
        value=json.loads(self.file_path.read_text(encoding="utf-8"))
        if type(value) is not dict or set(value)!={"version","by_prediction","by_trade"} or value["version"]!=1: raise ValueError("invalid Task 9 binding store")
        return value
    def save(self, binding: Task9PredictionPaperTradeBindingV1):
        if type(binding) is not Task9PredictionPaperTradeBindingV1: raise TypeError("binding")
        doc=self._read(); raw=binding.to_dict(); existing=doc["by_prediction"].get(binding.prediction_id) or doc["by_trade"].get(binding.paper_trade_id)
        if existing is not None:
            if existing != raw: raise ValueError("conflicting Task 9 binding")
            return "DUPLICATE_SAME_PAYLOAD"
        doc["by_prediction"][binding.prediction_id]=raw; doc["by_trade"][binding.paper_trade_id]=raw; self.file_path.parent.mkdir(parents=True,exist_ok=True); tmp=self.file_path.with_suffix(self.file_path.suffix+".tmp")
        try: tmp.write_text(json.dumps(doc,sort_keys=True,separators=(",",":")),encoding="utf-8"); replace_task9_atomic_file(tmp,self.file_path)
        finally: tmp.unlink(missing_ok=True)
        return "SAVED"
    @staticmethod
    def _binding(raw):
        value=dict(raw); value["entered_at"]=datetime.fromisoformat(value["entered_at"]); return Task9PredictionPaperTradeBindingV1(**value)
    def by_prediction(self, prediction_id: str):
        raw=self._read()["by_prediction"].get(prediction_id); return None if raw is None else self._binding(raw)
    def by_trade(self, paper_trade_id: str):
        raw=self._read()["by_trade"].get(paper_trade_id); return None if raw is None else self._binding(raw)
    def list_all(self):
        return tuple(sorted((self._binding(raw) for raw in self._read()["by_trade"].values()), key=lambda item: (item.market, item.prediction_id, item.paper_trade_id)))
