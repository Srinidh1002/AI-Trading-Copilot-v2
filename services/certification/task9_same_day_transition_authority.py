"""Read-only, provider-free gate from a diagnostic Task 9 root to a fresh official root."""
from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from services.certification.task9_live_paper_production_composition import Task9ProductionPersistenceLayoutV1
from services.certification.task9_prediction_paper_trade_binding_store import Task9PredictionPaperTradeBindingStore
from services.certification.task9_prediction_lifecycle_reconciliation_store import Task9PredictionLifecycleReconciliationStore
from services.paper_trade_repository import PaperTradeRepository
from services.paper_trading.paper_trade_persistence_service import PaperTradePersistenceService

@dataclass(frozen=True,slots=True)
class Task9SameDayTransitionReadinessV1:
 status:str; reasons:tuple[str,...]; diagnostic_run_id:str; official_run_id:str
 def __post_init__(self):
  if self.status not in {"READY","BLOCKED_OPEN_DIAGNOSTIC_POSITION","BLOCKED_UNRECONCILED_DIAGNOSTIC_POSITION","BLOCKED_UNRESOLVED_DIAGNOSTIC_STATE","INVALID_DIAGNOSTIC_STATE"}: raise ValueError("status")

def _manifest(root:Path):
 path=root/"task9-live-paper-run.json"
 try: value=json.loads(path.read_text(encoding="utf-8"))
 except (OSError,json.JSONDecodeError) as exc: raise ValueError("INVALID_DIAGNOSTIC_MANIFEST") from exc
 if type(value) is not dict or value.get("run_classification")!="DIAGNOSTIC_NON_COUNTING" or type(value.get("official_run_id")) is not str: raise ValueError("INVALID_DIAGNOSTIC_MANIFEST")
 return value

def evaluate_task9_same_day_transition(*, diagnostic_root:str|Path, diagnostic_run_id:str, official_root:str|Path, official_run_id:str)->Task9SameDayTransitionReadinessV1:
 """Never mutates roots; official root must be fresh and diagnostic state terminal."""
 droot,oroot=Path(diagnostic_root),Path(official_root)
 if droot.resolve()==oroot.resolve(): return Task9SameDayTransitionReadinessV1("INVALID_DIAGNOSTIC_STATE",("ROOTS_MUST_BE_SEPARATE",),diagnostic_run_id,official_run_id)
 try: manifest=_manifest(droot)
 except ValueError as exc: return Task9SameDayTransitionReadinessV1("INVALID_DIAGNOSTIC_STATE",(str(exc),),diagnostic_run_id,official_run_id)
 if manifest["official_run_id"]!=diagnostic_run_id: return Task9SameDayTransitionReadinessV1("INVALID_DIAGNOSTIC_STATE",("DIAGNOSTIC_RUN_ID_MISMATCH",),diagnostic_run_id,official_run_id)
 if oroot.exists() and any(oroot.iterdir()): return Task9SameDayTransitionReadinessV1("INVALID_DIAGNOSTIC_STATE",("OFFICIAL_ROOT_NOT_FRESH",),diagnostic_run_id,official_run_id)
 try:
  layout=Task9ProductionPersistenceLayoutV1.from_root(droot); bindings=Task9PredictionPaperTradeBindingStore(layout.binding_store_path); trades=PaperTradePersistenceService(PaperTradeRepository(layout.paper_trade_repository_path)); reconciliations=Task9PredictionLifecycleReconciliationStore(layout.lifecycle_reconciliation_store_path)
  for binding in bindings.list_all():
   snapshot=trades.get(binding.paper_trade_id)
   if snapshot is None: return Task9SameDayTransitionReadinessV1("INVALID_DIAGNOSTIC_STATE",("DIAGNOSTIC_BINDING_TRADE_MISSING",),diagnostic_run_id,official_run_id)
   if snapshot.lifecycle_state.current_state in {"OPEN","PARTIALLY_EXITED"}: return Task9SameDayTransitionReadinessV1("BLOCKED_OPEN_DIAGNOSTIC_POSITION",("DIAGNOSTIC_POSITION_OPEN",),diagnostic_run_id,official_run_id)
   if reconciliations.recover(binding.prediction_id) is None: return Task9SameDayTransitionReadinessV1("BLOCKED_UNRECONCILED_DIAGNOSTIC_POSITION",("DIAGNOSTIC_TERMINAL_UNRECONCILED",),diagnostic_run_id,official_run_id)
 except Exception: return Task9SameDayTransitionReadinessV1("INVALID_DIAGNOSTIC_STATE",("DIAGNOSTIC_STATE_UNREADABLE",),diagnostic_run_id,official_run_id)
 return Task9SameDayTransitionReadinessV1("READY",(),diagnostic_run_id,official_run_id)
