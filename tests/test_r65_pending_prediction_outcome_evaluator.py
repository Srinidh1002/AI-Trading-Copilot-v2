from datetime import timedelta

from services.paper_orchestration.pending_prediction_outcome_evaluator import PendingPredictionOutcomeEvaluator
from services.paper_orchestration.prediction_ledger import PredictionLedger
from services.paper_orchestration.prediction_outcome_ledger import PredictionOutcomeLedger
from services.paper_orchestration.prediction_record_projector import project_parent_decision_predictions
from services.paper_orchestration.two_market_parent_cycle_coordinator import run_two_market_parent_cycle
from test_two_market_parent_cycle_coordinator import candidate_for, parent

def pair():
    decision = run_two_market_parent_cycle(parent(), child_evaluator=lambda symbol, exchange, observation_id: candidate_for(symbol, observation_id, score=80.0 if symbol == "NIFTY" else 60.0))
    return project_parent_decision_predictions(decision, start_underlying_prices={("NIFTY", "NSE"): 25000.0, ("SENSEX", "BSE"): 80000.0})

def test_due_pair_evaluates_once_and_restart_skips(tmp_path):
    predictions = pair(); prediction_path = tmp_path / "predictions.json"; outcome_path = tmp_path / "outcomes.json"
    PredictionLedger(prediction_path).save_pair(predictions)
    now = predictions[0].completed_at + timedelta(minutes=15)
    prices = {("NIFTY", "NSE"): 25100.0, ("SENSEX", "BSE"): 80020.0}
    def reader(symbol, exchange): return {"spot_price": prices[(symbol, exchange)], "observation_id": f"evaluation:{symbol}", "observed_at": now}
    first = PendingPredictionOutcomeEvaluator(prediction_ledger=PredictionLedger(prediction_path), outcome_ledger=PredictionOutcomeLedger(outcome_path), price_reader=reader, clock=lambda: now)()
    second = PendingPredictionOutcomeEvaluator(prediction_ledger=PredictionLedger(prediction_path), outcome_ledger=PredictionOutcomeLedger(outcome_path), price_reader=lambda *args: (_ for _ in ()).throw(AssertionError("restart must not reread")), clock=lambda: now)()
    assert tuple(item.outcome for item in first.evaluated_records) == ("CORRECT", "GOOD_WAIT")
    assert PredictionOutcomeLedger(outcome_path).count() == 2
    assert second.evaluated_records == ()
    assert second.skipped_existing_prediction_ids == tuple(item.prediction_id for item in predictions)

def test_not_due_predictions_remain_pending_without_reads(tmp_path):
    predictions = pair(); ledger = PredictionLedger(tmp_path / "predictions.json"); ledger.save_pair(predictions)
    result = PendingPredictionOutcomeEvaluator(prediction_ledger=ledger, outcome_ledger=PredictionOutcomeLedger(tmp_path / "outcomes.json"), price_reader=lambda *args: (_ for _ in ()).throw(AssertionError("not due")), clock=lambda: predictions[0].completed_at)()
    assert result.evaluated_records == ()
    assert result.pending_prediction_ids == tuple(item.prediction_id for item in predictions)

def test_missing_price_is_persisted_as_unevaluable(tmp_path):
    predictions = pair(); ledger = PredictionLedger(tmp_path / "predictions.json"); ledger.save_pair(predictions)
    now = predictions[0].completed_at + timedelta(minutes=15)
    result = PendingPredictionOutcomeEvaluator(prediction_ledger=ledger, outcome_ledger=PredictionOutcomeLedger(tmp_path / "outcomes.json"), price_reader=lambda *args: {}, clock=lambda: now)()
    assert len(result.evaluated_records) == 2
    assert all(item.outcome == "UNEVALUABLE" for item in result.evaluated_records)
