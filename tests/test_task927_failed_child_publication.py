"""Durable Task 9 child failures are exclusions, not lifecycle pending."""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import timedelta

import pytest

from services.certification.task9_certification_publication import (
    Task9CertificationPublicationAuthority,
)
from services.certification.task9_abstention_later_observation_recovery import (
    recover_task9_later_abstention_observations,
)
from services.certification.task9_live_paper_certification_launcher import (
    Task9LivePaperCycleResultStore,
)
from services.certification.task9_live_paper_certification_runner import (
    Task9InternalChildFailureV1,
    Task9LivePaperCycleResultV1,
)
from services.contracts.prediction_lifecycle_outcome_policy_v1 import (
    PredictionLifecycleOutcomePolicyV1,
)
from tests.test_task916_production_child_evidence_authority import _quote, _runtime
from tests.test_task9_live_paper_trade_counting_evaluator import lifecycle_outcome


def _authority(tmp_path, runtime, official_run_id, prediction):
    return Task9CertificationPublicationAuthority(
        official_run_id=official_run_id,
        official_start_at=prediction.completed_at - timedelta(seconds=1),
        root=tmp_path,
        prediction_ledger=runtime["ledger"],
        binding_store=runtime["binding_store"],
        outcome_store=runtime["outcome_store"],
        reconciliation_store=runtime["reconciliation_store"],
        trade_persistence_service=runtime["trade_service"],
        starting_capital=10_000.0,
    )


@pytest.mark.parametrize("market", ("NIFTY", "SENSEX"))
def test_durable_internal_child_failure_is_excluded_not_pending(tmp_path, market):
    runtime = _runtime(tmp_path, nifty_action="WAIT", sensex_action="NO_TRADE")
    prediction = next(item for item in runtime["predictions"] if item.underlying_symbol == market)
    other = next(item for item in runtime["predictions"] if item.underlying_symbol != market)
    official_run_id = "task9-failed-child-publication"
    cycle_id = f"task9:{official_run_id}:{prediction.parent_cycle_id}"
    Task9LivePaperCycleResultStore(tmp_path).save(
        Task9LivePaperCycleResultV1(
            cycle_id=cycle_id,
            started_at=prediction.completed_at,
            completed_at=prediction.completed_at,
            market_results=(
                (market, "INTERNAL_CHILD_FAILURE", Task9InternalChildFailureV1(reason_code="INTERNAL_CHILD_FAILURE_VALUEERROR")),
                (other.underlying_symbol, "ENTRY_ALLOWED", None),
            ),
        )
    )
    authority = _authority(tmp_path, runtime, official_run_id, prediction)
    quote, quality = _quote(prediction)
    assert recover_task9_later_abstention_observations(
        market=prediction.underlying_symbol,
        exchange=prediction.exchange,
        quote=quote,
        data_quality=quality,
        prediction_ledger=runtime["ledger"],
        lifecycle_context_store=runtime["context_store"],
        observation_store=runtime["observation_store"],
        outcome_store=runtime["outcome_store"],
        outcome_policy=PredictionLifecycleOutcomePolicyV1(policy_id="task927", policy_version="1.0"),
        evaluated_at=quote.observed_at,
    ) == ()
    assert runtime["observation_store"].recover(prediction.prediction_id) is None
    assert runtime["outcome_store"].recover(prediction.prediction_id) is None
    progress = authority.refresh(session_date=prediction.completed_at.date(), evaluated_at=prediction.completed_at)
    report = json.loads((tmp_path / "current-session-reports" / f"{prediction.completed_at.date().isoformat()}.json").read_text(encoding="utf-8"))
    failed_fact = next(item for item in report["prediction_facts"] if item["prediction_id"] == prediction.prediction_id)
    other_fact = next(item for item in report["prediction_facts"] if item["prediction_id"] == other.prediction_id)

    assert failed_fact["counting_status"] == "EXCLUDED_CHILD_FAILURE"
    assert failed_fact["outcome"] == "CHILD_FAILURE"
    assert failed_fact["officially_counted"] is False
    assert other_fact["counting_status"] == "PENDING_OUTCOME"
    assert report["excluded_prediction_count"] == 1
    assert report["pending_outcome_count"] == 1
    assert dict(report["outcome_distribution"])["CHILD_FAILURE"] == 1
    assert dict(report["outcome_distribution"])["PENDING"] == 1
    assert sum(dict(report["outcome_distribution"]).values()) == report["source_prediction_count"]
    assert all(item["prediction_id"] != prediction.prediction_id for item in report["unresolved_audit"])
    exclusion = next(item for item in report["excluded_audit"] if item["prediction_id"] == prediction.prediction_id)
    assert exclusion["status"] == "EXCLUDED_CHILD_FAILURE"
    assert exclusion["reason_codes"] == ["INTERNAL_CHILD_FAILURE_VALUEERROR"]
    assert progress.nifty.completed_live_paper_trades == 0
    assert progress.sensex.completed_live_paper_trades == 0
    assert progress.nifty.no_trade_completed == 0
    assert progress.sensex.no_trade_completed == 0
    assert progress.unresolved == 1
    assert progress.invalid_excluded == 1

    later_prediction = replace(prediction, prediction_id=f"{prediction.prediction_id}:later", parent_cycle_id=f"{prediction.parent_cycle_id}:later")
    assert authority._child_failure(later_prediction) is None


@pytest.mark.parametrize("action", ("WAIT", "NO_TRADE"))
def test_data_unavailable_lifecycle_status_is_preserved_in_publication(tmp_path, action):
    runtime = _runtime(tmp_path, nifty_action=action, sensex_action="WAIT")
    prediction = runtime["predictions"][0]
    outcome = lifecycle_outcome(
        prediction,
        outcome="DATA_UNAVAILABLE",
        evaluation_status="DATA_UNAVAILABLE",
        entry_occurred=False,
        entry_at=None,
        entry_premium=None,
        terminal_event_type=None,
        terminal_event_at=None,
        terminal_option_premium=None,
        blockers=("UNDERLYING_EXTREMA_UNAVAILABLE",),
    )
    runtime["outcome_store"].save(outcome)
    authority = _authority(tmp_path, runtime, "task9-data-unavailable-publication", prediction)
    authority.refresh(session_date=prediction.completed_at.date(), evaluated_at=prediction.completed_at)
    report = json.loads((tmp_path / "current-session-reports" / f"{prediction.completed_at.date().isoformat()}.json").read_text(encoding="utf-8"))
    fact = next(item for item in report["prediction_facts"] if item["prediction_id"] == prediction.prediction_id)
    audit = next(item for item in report["excluded_audit"] if item["prediction_id"] == prediction.prediction_id)

    assert fact["counting_status"] == "EXCLUDED_DATA_UNAVAILABLE"
    assert fact["lifecycle_status"] == "DATA_UNAVAILABLE"
    assert audit["status"] == "EXCLUDED_DATA_UNAVAILABLE"
    assert "LIFECYCLE_STATUS_DATA_UNAVAILABLE" in audit["reason_codes"]
    assert "UNDERLYING_EXTREMA_UNAVAILABLE" in audit["reason_codes"]
