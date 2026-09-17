from datetime import datetime, timezone
import pytest
from services.certification.task9_prediction_paper_trade_binding_store import Task9PredictionPaperTradeBindingStore, Task9PredictionPaperTradeBindingV1

def binding(): return Task9PredictionPaperTradeBindingV1("run-1", "prediction-1", "NIFTY", "trade-1", "position-1", "NIFTY26JAN24000CE", datetime(2026,1,8,tzinfo=timezone.utc))
def test_binding_store_recovers_and_rejects_conflict(tmp_path):
    path=tmp_path / "bindings.json"; store=Task9PredictionPaperTradeBindingStore(path); value=binding()
    assert store.save(value)=="SAVED"; assert store.save(value)=="DUPLICATE_SAME_PAYLOAD"
    assert Task9PredictionPaperTradeBindingStore(path).by_trade("trade-1") == value
    with pytest.raises(ValueError): store.save(Task9PredictionPaperTradeBindingV1("run-1", "prediction-1", "NIFTY", "trade-2", "position-2", "NIFTY26JAN24000CE", value.entered_at))
