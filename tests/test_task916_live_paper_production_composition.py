from datetime import timedelta
from dataclasses import replace

import pytest

from services.certification.task9_cycle_market_evidence_handoff import (
    Task9CycleMarketEvidenceV1,
)
from services.certification.task9_live_paper_production_composition import (
    build_task9_live_paper_production_runtime,
)
import services.certification.task9_live_paper_production_composition as production_composition
from services.certification.task9_prediction_lifecycle_timing import (
    resolve_prediction_lifecycle_window,
)
from services.contracts.prediction_lifecycle_outcome_policy_v1 import (
    PredictionLifecycleOutcomePolicyV1,
)
from services.market_session.policies import MarketSessionPolicy
from tests.test_task8_parent_typed_candidate_certification import (
    captured,
    cycle,
)
from tests.test_task916_production_child_evidence_authority import _runtime
from tests.task916_real_runtime_harness import (
    build_task916_real_runtime_harness,
)


def _build(runtime, root, *, official_start_at=None):
    return build_task9_live_paper_production_runtime(
        official_run_id="task916-production-run",
        official_start_at=(
            runtime["boundary"] - timedelta(seconds=1)
            if official_start_at is None
            else official_start_at
        ),
        evaluated_at=runtime["boundary"],
        persistence_root=root,
        cycle_evidence_by_market=runtime["handoffs"],
        available_capital=300000.0,
        portfolio_id="task916-production-portfolio",
        outcome_policy=PredictionLifecycleOutcomePolicyV1(
            policy_id="task916-production-policy",
            policy_version="1.0",
        ),
        persist=lambda _: None,
    )


def _persist_prediction_contexts(runtime, production):
    production.prediction_ledger.save_pair(runtime["predictions"])
    for item in runtime["predictions"]:
        production.lifecycle_context_store.save(
            resolve_prediction_lifecycle_window(
                prediction_record=item,
                session_policy=MarketSessionPolicy(),
            )
        )


def test_production_composition_builds_paper_runner_with_one_canonical_root(
    tmp_path,
):
    seed = _runtime(
        tmp_path / "seed",
        nifty_action="WAIT",
        sensex_action="NO_TRADE",
    )
    production = _build(seed, tmp_path / "production")
    layout = production.persistence_layout

    assert callable(production.child_authority)
    assert production.runner.child_authority is production.child_authority
    assert {
        path.parent
        for path in (
            layout.prediction_ledger_path,
            layout.binding_store_path,
            layout.lifecycle_context_store_path,
            layout.observation_window_store_path,
            layout.lifecycle_outcome_store_path,
            layout.lifecycle_reconciliation_store_path,
            layout.portfolio_policy_store_path,
            layout.paper_trade_repository_path,
            layout.paper_portfolio_repository_path,
            layout.pending_entry_store_path,
        )
    } == {layout.root}
    assert production.execution_mode == "PAPER"
    assert production.broker_order_submission is False
    assert production.live_execution_eligible is False
    assert production.pending_entry_store.file_path == layout.pending_entry_store_path


def test_two_market_abstention_uses_exact_quote_handoffs_without_p7_entry(
    tmp_path,
):
    seed = _runtime(
        tmp_path / "seed",
        nifty_action="WAIT",
        sensex_action="NO_TRADE",
    )
    production = _build(seed, tmp_path / "production")
    _persist_prediction_contexts(seed, production)

    nifty = production.child_authority("NIFTY", "NSE", False)
    sensex = production.child_authority("SENSEX", "BSE", False)

    assert (nifty.prediction.underlying_symbol, nifty.prediction.exchange) == (
        "NIFTY",
        "NSE",
    )
    assert (sensex.prediction.underlying_symbol, sensex.prediction.exchange) == (
        "SENSEX",
        "BSE",
    )
    assert nifty.terminal_position_closed is False
    assert sensex.terminal_position_closed is False
    assert production.trade_persistence_service.list_all() == ()


def test_production_composition_returns_data_incident_for_persisted_failed_nifty(
    tmp_path,
):
    seed = _runtime(tmp_path / "seed")
    original, sensex = seed["predictions"]
    failed = replace(
        original,
        terminal_status="FAILED",
        candidate_id=None,
        market_timestamp=None,
        predicted_direction="UNAVAILABLE",
        predicted_action="WAIT",
        eligibility="UNAVAILABLE",
        confidence=0.0,
        score=0.0,
        rank_value=0.0,
        eligible_for_comparison=False,
        outcome_reason="CHILD_FAILED",
        parent_decision="NO_TRADE",
        parent_selected=False,
        errors=("HISTORICAL-DATA_RATE_LIMITED",),
    )
    seed["predictions"] = (failed, sensex)
    seed["handoffs"][("NIFTY", "NSE")] = replace(
        seed["handoffs"][("NIFTY", "NSE")],
        prediction=failed,
        market_quote=None,
        data_quality=None,
        lifecycle_window=resolve_prediction_lifecycle_window(
            prediction_record=failed,
            session_policy=MarketSessionPolicy(),
        ),
    )

    production = _build(seed, tmp_path / "production")
    result = production.child_authority("NIFTY", "NSE", True)

    assert result.evidence_status == "DATA_INCIDENT"
    assert result.prediction.errors == ("HISTORICAL-DATA_RATE_LIMITED",)
    assert production.binding_store.by_prediction(failed.prediction_id) is None
    assert production.observation_store.recover(failed.prediction_id) is None
    assert production.outcome_store.recover(failed.prediction_id) is None
    assert production.reconciliation_store.recover(failed.prediction_id) is None


def test_completed_unavailable_rate_limited_nifty_skips_wait_abstention(
    tmp_path,
):
    seed = _runtime(tmp_path / "seed", nifty_action="WAIT")
    original, sensex = seed["predictions"]
    provider_incident = replace(
        original,
        predicted_direction="UNAVAILABLE",
        eligibility="UNAVAILABLE",
        blockers=(*original.blockers, "HISTORICAL-DATA_RATE_LIMITED"),
    )
    seed["predictions"] = (provider_incident, sensex)
    seed["handoffs"][("NIFTY", "NSE")] = replace(
        seed["handoffs"][("NIFTY", "NSE")],
        prediction=provider_incident,
        lifecycle_window=resolve_prediction_lifecycle_window(
            prediction_record=provider_incident,
            session_policy=MarketSessionPolicy(),
        ),
    )

    production = _build(
        seed,
        tmp_path / "production",
        official_start_at=(
            provider_incident.completed_at - timedelta(seconds=1)
        ),
    )
    result = production.child_authority("NIFTY", "NSE", False)
    cycle_result = production.run_cycle(
        cycle_id="completed-provider-incident",
        evaluated_at=seed["boundary"],
    )

    assert result.evidence_status == "DATA_INCIDENT"
    assert "HISTORICAL-DATA_RATE_LIMITED" in result.prediction.blockers
    assert production.observation_store.recover(provider_incident.prediction_id) is None
    assert production.binding_store.by_prediction(provider_incident.prediction_id) is None
    assert production.trade_persistence_service.list_all() == ()
    assert production.outcome_store.recover(provider_incident.prediction_id) is None
    assert production.reconciliation_store.recover(provider_incident.prediction_id) is None
    assert cycle_result.market_results[0][1] == "DATA_INCIDENT"
    assert "HISTORICAL-DATA_RATE_LIMITED" in cycle_result.market_results[0][2].reason_codes
    assert cycle_result.market_results[0][2].trade_target_countable is False


def test_entry_delegate_receives_exact_selected_cycle_planning_and_prediction(
    tmp_path,
    monkeypatch,
):
    harness = build_task916_real_runtime_harness(
        tmp_path / "seed",
        market="NIFTY",
    )
    selected = harness.selected_prediction
    other = next(
        item
        for item in harness.predictions
        if item.prediction_id != selected.prediction_id
    )
    other_capture = captured(
        other.underlying_symbol,
        other.exchange,
        other.start_underlying_price,
    )
    other_cycle = cycle(
        other.underlying_symbol,
        other.exchange,
        other_capture,
    )
    seed = {
        "predictions": harness.predictions,
        "handoffs": {
            ("NIFTY", "NSE"): Task9CycleMarketEvidenceV1(
                prediction=selected,
                cycle=harness.selected_cycle,
                evaluation=harness.selected_evaluation,
                lifecycle_window=harness.lifecycle_context_store.recover(
                    selected.prediction_id
                ),
                selected_planning=harness.selected_planning,
            ),
            ("SENSEX", "BSE"): Task9CycleMarketEvidenceV1(
                prediction=other,
                cycle=other_cycle,
                lifecycle_window=harness.lifecycle_context_store.recover(
                    other.prediction_id
                ),
            ),
        },
        "boundary": harness.decision.completed_at,
    }
    calls = []
    monkeypatch.setattr(
        production_composition,
        "execute_task9_selected_market_lifecycle",
        lambda **kwargs: calls.append(kwargs),
    )
    production = _build(seed, tmp_path / "production")
    _persist_prediction_contexts(seed, production)

    result = production.child_authority("NIFTY", "NSE", True)

    assert result.terminal_position_closed is False
    assert len(calls) == 1
    assert calls[0]["prediction_id"] == selected.prediction_id
    assert calls[0]["selected_cycle"] is harness.selected_cycle
    assert calls[0]["selected_planning"] is harness.selected_planning
    assert calls[0]["persistence_root"] == production.persistence_layout.root


def test_runtime_rejects_a_different_runner_boundary(tmp_path):
    seed = _runtime(
        tmp_path / "seed",
        nifty_action="WAIT",
        sensex_action="NO_TRADE",
    )
    production = _build(seed, tmp_path / "production")

    with pytest.raises(ValueError, match="cycle boundary"):
        production.run_cycle(
            cycle_id="task916-production-cycle",
            evaluated_at=seed["boundary"] + timedelta(seconds=1),
        )
