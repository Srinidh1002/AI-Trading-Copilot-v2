from datetime import datetime, timezone
import pytest
from services.certification.task9_live_paper_certification_launcher import load_or_create_task9_run_manifest
from services.certification.task9_live_paper_trade_counting_evaluator import evaluate_task9_live_paper_trade_counting
from services.contracts.task9_live_paper_trade_counting_input_v1 import Task9LivePaperTradeCountingInputV1
from tests.test_task9_live_paper_trade_counting_evaluator import prediction, lifecycle_outcome, counting_input

NOW=datetime(2026,8,14,10,0,tzinfo=timezone.utc)

def test_manifest_classification_is_immutable_and_old_manifest_fails_closed(tmp_path):
 m=load_or_create_task9_run_manifest(persistence_root=tmp_path,official_run_id="diagnostic",started_at=NOW,run_classification="DIAGNOSTIC_NON_COUNTING")
 assert m.run_classification=="DIAGNOSTIC_NON_COUNTING"
 with pytest.raises(ValueError,match="CLASSIFICATION"):
  load_or_create_task9_run_manifest(persistence_root=tmp_path,official_run_id="diagnostic",started_at=NOW,run_classification="OFFICIAL_CERTIFICATION")
 legacy=tmp_path/"legacy"; legacy.mkdir(); (legacy/"task9-live-paper-run.json").write_text('{"official_run_id":"legacy","official_start_at":"2026-08-14T10:00:00+00:00","execution_mode":"PAPER","broker_order_submission":false,"live_execution_eligible":false}')
 with pytest.raises(ValueError,match="manifest"):
  load_or_create_task9_run_manifest(persistence_root=legacy,official_run_id="legacy",started_at=NOW)

def test_perfect_diagnostic_trade_is_excluded_by_counting_defense_in_depth():
 p=prediction(); outcome=lifecycle_outcome(p)
 value=counting_input(prediction_value=p,lifecycle_outcome_value=outcome,reconciliation_value=None,run_classification="DIAGNOSTIC_NON_COUNTING")
 decision=evaluate_task9_live_paper_trade_counting(value)
 assert decision.status=="EXCLUDED_NON_LIVE_SOURCE" and not decision.trade_target_countable
