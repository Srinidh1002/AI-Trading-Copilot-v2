from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from services.paper_orchestration.prediction_ledger import PredictionLedger
from services.paper_orchestration.prediction_record_projector import project_parent_decision_predictions
from services.analysis.pre_entry_action_resolver import resolve_pre_entry_market_action
from services.paper_orchestration.two_market_parent_cycle_coordinator import run_two_market_parent_cycle
from test_two_market_parent_cycle_coordinator import candidate_for, parent


def records():
    decision = run_two_market_parent_cycle(parent(), child_evaluator=lambda symbol, exchange, observation_id: candidate_for(symbol, observation_id, score=80.0 if symbol == "NIFTY" else 60.0))
    pre_entry_actions = {entry.child.observation_id: resolve_pre_entry_market_action(candidate=entry.child.candidate, cycle_id=decision.parent_cycle_id, observation_id=entry.child.observation_id, evaluated_at=decision.completed_at) for entry in decision.entries if entry.child.terminal_status == "COMPLETED"}
    return project_parent_decision_predictions(decision, start_underlying_prices={("NIFTY", "NSE"): 25000.0, ("SENSEX", "BSE"): 80000.0}, pre_entry_actions=pre_entry_actions)


def test_exact_prediction_id_lookup_survives_fresh_ledger_instance(tmp_path):
    ledger_path = tmp_path / "ledger.json"; pair = records()
    PredictionLedger(ledger_path).save_pair(pair)
    assert PredictionLedger(ledger_path).recover(pair[0].prediction_id) == pair[0]
    assert PredictionLedger(ledger_path).recover("missing") is None


def test_corrupt_ledger_fails_closed(tmp_path):
    path = tmp_path / "ledger.json"; path.write_text("not-json", encoding="utf-8")
    with pytest.raises(ValueError):
        PredictionLedger(path).recover("prediction")
