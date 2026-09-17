import pytest
from dataclasses import replace

from services.certification.task9_cycle_market_evidence_handoff import Task9CycleMarketEvidenceV1
from services.certification.task9_live_spot_quote_projection import (
    project_task9_live_spot_quote_with_quality,
)
from services.certification.task9_external_provider_blocker import (
    Task9ExternalProviderBlockerStore,
)
from services.certification.task9_live_paper_certification_launcher import (
    Task9LivePaperCertificationLauncher,
)
from services.certification.task9_prediction_lifecycle_timing import (
    resolve_prediction_lifecycle_window,
)
from services.certification.task8_live_paper_default_composition import (
    _emit_task9_cycle_market_evidence,
    _retain_task9_request_diagnostics,
)
from services.analysis.live_canonical_engine_adapters import (
    build_default_live_canonical_evidence_engines,
)
from services.analysis.live_market_candidate_evaluator import (
    LiveCandidatePolicySourceV1,
    evaluate_captured_certified_market_candidate,
)
from tests.test_task8_selected_market_lifecycle_runtime import _ready_selected_planning
from tests.test_task916_prediction_ledger_restart_lookup import records
from tests.test_task8_parent_typed_candidate_certification import captured, cycle
from tests.p7_fixture_helpers import make_observation
from services.market_session.policies import MarketSessionPolicy


def _failed_prediction(value):
    return replace(
        value,
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


def _market_evidence(identity):
    if identity == ("NIFTY", "NSE"):
        _, cycle_value, evaluation, _, _ = _ready_selected_planning()
        # The real Task 8 parent supplies this cycle observation ID to the
        # child coordinator; its projected prediction retains that same ID.
        prediction = replace(
            records()[0],
            observation_id=cycle_value.observation_id,
        )
        return prediction, cycle_value, evaluation

    capture = captured(
        "SENSEX",
        "BSE",
        80000.0,
        complete_options=True,
    )
    cycle_value = cycle("SENSEX", "BSE", capture)
    evaluation = evaluate_captured_certified_market_candidate(
        captured_evidence=capture,
        session_validation=cycle_value.session_validation,
        policy_source=LiveCandidatePolicySourceV1.unavailable(),
        parent_cycle_id="task9-handoff-sensex",
        candidate_id="task9-handoff-sensex",
        observation_id=cycle_value.observation_id,
        engines=build_default_live_canonical_evidence_engines(),
    )
    # Match the production parent->child->prediction observation identity.
    return (
        replace(
            records()[1],
            observation_id=cycle_value.observation_id,
        ),
        cycle_value,
        evaluation,
    )


@pytest.mark.parametrize("identity", (("NIFTY", "NSE"), ("SENSEX", "BSE")))
def test_handoff_projects_quote_specific_quality_for_each_market(identity):
    prediction, cycle_value, evaluation = _market_evidence(identity)
    quote, quality = project_task9_live_spot_quote_with_quality(
        spot=evaluation.observation.spot,
    )

    value = Task9CycleMarketEvidenceV1(
        prediction=prediction,
        cycle=cycle_value,
        evaluation=evaluation,
        market_quote=quote,
        data_quality=quality,
    )

    assert (value.market_quote.underlying_symbol, value.market_quote.exchange) == identity
    assert (value.data_quality.underlying_symbol, value.data_quality.exchange) == identity
    assert value.data_quality.subject_type == "QUOTE"
    assert value.data_quality.observed_at == value.market_quote.observed_at
    assert value.data_quality.received_at == value.market_quote.received_at
    assert value.data_quality is not value.evaluation.evidence.data_quality


def test_retains_exact_prediction_and_cycle_without_market_refetch():
    _, cycle, evaluation, _, _ = _ready_selected_planning()
    prediction = records()[0]
    value = Task9CycleMarketEvidenceV1(prediction=prediction, cycle=cycle, evaluation=evaluation)
    assert value.prediction is prediction and value.cycle is cycle and value.evaluation is evaluation


def test_rejects_cross_market_handoff():
    _, cycle, evaluation, _, _ = _ready_selected_planning()
    with pytest.raises(ValueError, match="market identity"):
        Task9CycleMarketEvidenceV1(prediction=records()[1], cycle=cycle, evaluation=evaluation)


def test_unselected_market_can_remain_without_a_paper_observation():
    _, cycle, evaluation, _, _ = _ready_selected_planning()
    value = Task9CycleMarketEvidenceV1(prediction=records()[0], cycle=cycle, evaluation=evaluation)
    assert value.paper_observation is None


def test_quote_and_quality_must_be_supplied_together():
    prediction, cycle_value, evaluation = _market_evidence(("NIFTY", "NSE"))
    quote, quality = project_task9_live_spot_quote_with_quality(
        spot=evaluation.observation.spot,
    )

    with pytest.raises(ValueError, match="supplied together"):
        Task9CycleMarketEvidenceV1(
            prediction=prediction,
            cycle=cycle_value,
            evaluation=evaluation,
            market_quote=quote,
        )

    with pytest.raises(ValueError, match="supplied together"):
        Task9CycleMarketEvidenceV1(
            prediction=prediction,
            cycle=cycle_value,
            evaluation=evaluation,
            data_quality=quality,
        )


def test_rejects_cross_market_quote_and_quality():
    prediction, cycle_value, evaluation = _market_evidence(("NIFTY", "NSE"))
    _, _, sensex_evaluation = _market_evidence(("SENSEX", "BSE"))
    sensex_quote, sensex_quality = project_task9_live_spot_quote_with_quality(
        spot=sensex_evaluation.observation.spot,
    )

    with pytest.raises(ValueError, match="market_quote identity"):
        Task9CycleMarketEvidenceV1(
            prediction=prediction,
            cycle=cycle_value,
            evaluation=evaluation,
            market_quote=sensex_quote,
            data_quality=sensex_quality,
        )


def test_composition_emits_both_market_quote_evidence_without_refetch():
    nifty_prediction, nifty_cycle, nifty_evaluation = _market_evidence(
        ("NIFTY", "NSE")
    )
    sensex_prediction, sensex_cycle, sensex_evaluation = _market_evidence(
        ("SENSEX", "BSE")
    )
    received = []
    selected_paper_observation = make_observation()

    _emit_task9_cycle_market_evidence(
        sink=received.append,
        cycles={
            ("NIFTY", "NSE"): nifty_cycle,
            ("SENSEX", "BSE"): sensex_cycle,
        },
        evaluations={
            nifty_cycle.observation_id: nifty_evaluation,
            sensex_cycle.observation_id: sensex_evaluation,
        },
        predictions={
            ("NIFTY", "NSE"): nifty_prediction,
            ("SENSEX", "BSE"): sensex_prediction,
        },
        selected_market=("NIFTY", "NSE"),
        lifecycle_windows={
            ("NIFTY", "NSE"): resolve_prediction_lifecycle_window(
                prediction_record=nifty_prediction,
                session_policy=MarketSessionPolicy(),
            ),
            ("SENSEX", "BSE"): resolve_prediction_lifecycle_window(
                prediction_record=sensex_prediction,
                session_policy=MarketSessionPolicy(),
            ),
        },
        selected_planning=None,
        selected_paper_observation=selected_paper_observation,
    )

    assert [
        (item.prediction.underlying_symbol, item.prediction.exchange)
        for item in received
    ] == [("NIFTY", "NSE"), ("SENSEX", "BSE")]
    assert all(item.market_quote is not None for item in received)
    assert all(item.data_quality.subject_type == "QUOTE" for item in received)
    assert received[0].paper_observation is selected_paper_observation
    assert received[1].paper_observation is None


def test_composition_emits_failed_children_without_synthesizing_quote_evidence():
    nifty_prediction, nifty_cycle, _ = _market_evidence(("NIFTY", "NSE"))
    sensex_prediction, sensex_cycle, _ = _market_evidence(("SENSEX", "BSE"))
    nifty_prediction = _failed_prediction(nifty_prediction)
    sensex_prediction = _failed_prediction(sensex_prediction)
    received = []

    _emit_task9_cycle_market_evidence(
        sink=received.append,
        cycles={("NIFTY", "NSE"): nifty_cycle, ("SENSEX", "BSE"): sensex_cycle},
        evaluations={},
        predictions={("NIFTY", "NSE"): nifty_prediction, ("SENSEX", "BSE"): sensex_prediction},
        lifecycle_windows={
            ("NIFTY", "NSE"): resolve_prediction_lifecycle_window(prediction_record=nifty_prediction, session_policy=MarketSessionPolicy()),
            ("SENSEX", "BSE"): resolve_prediction_lifecycle_window(prediction_record=sensex_prediction, session_policy=MarketSessionPolicy()),
        },
        selected_market=None,
        selected_planning=None,
        selected_paper_observation=None,
    )

    assert len(received) == 2
    assert all(item.evaluation is None and item.market_quote is None and item.data_quality is None for item in received)
    assert all(item.selected_planning is None and item.paper_observation is None for item in received)


def test_live_rate_limited_capture_metadata_reaches_only_nifty_handoff(tmp_path):
    nifty_prediction, nifty_cycle, _ = _market_evidence(("NIFTY", "NSE"))
    sensex_prediction, sensex_cycle, _ = _market_evidence(("SENSEX", "BSE"))
    nifty_prediction = _failed_prediction(nifty_prediction)
    sensex_prediction = _failed_prediction(sensex_prediction)
    live_capture = replace(
        captured("NIFTY", "NSE", 25000.0, complete_options=True),
        cache_metadata={
            "request_diagnostics": {
                "5m": {
                    "exchange": "NSE",
                    "timeframe": "5m",
                    "provider_attempted": True,
                    "provider_result": "RATE_LIMITED",
                    "failure_reason": "HISTORICAL-DATA_RATE_LIMITED",
                }
            }
        },
    )
    retained_diagnostics = {}
    _retain_task9_request_diagnostics(
        retained_diagnostics,
        observation_id=nifty_cycle.observation_id,
        capture=live_capture,
    )
    received = []

    _emit_task9_cycle_market_evidence(
        sink=received.append,
        cycles={
            ("NIFTY", "NSE"): nifty_cycle,
            ("SENSEX", "BSE"): sensex_cycle,
        },
        evaluations={},
        predictions={
            ("NIFTY", "NSE"): nifty_prediction,
            ("SENSEX", "BSE"): sensex_prediction,
        },
        lifecycle_windows={
            ("NIFTY", "NSE"): resolve_prediction_lifecycle_window(
                prediction_record=nifty_prediction,
                session_policy=MarketSessionPolicy(),
            ),
            ("SENSEX", "BSE"): resolve_prediction_lifecycle_window(
                prediction_record=sensex_prediction,
                session_policy=MarketSessionPolicy(),
            ),
        },
        selected_market=None,
        selected_planning=None,
        selected_paper_observation=None,
        retained_request_diagnostics=retained_diagnostics,
    )

    incidents = {
        (item.prediction.underlying_symbol, item.prediction.exchange): (
            item.provider_incidents
        )
        for item in received
    }
    assert len(incidents[("NIFTY", "NSE")]) == 1
    assert incidents[("NIFTY", "NSE")][0].incident_id == (
        "task9-provider-incident:"
        f"{nifty_cycle.observation_id}:NSE:historical-data:5m:"
        "HISTORICAL-DATA_RATE_LIMITED"
    )
    assert incidents[("SENSEX", "BSE")] == ()
    launcher = Task9LivePaperCertificationLauncher(
        persistence_root=tmp_path,
        official_run_id="run",
        startup_preflight_id="startup-preflight-1",
        runtime_config_snapshot_id="task9-runtime-config-" + ("a" * 64),
        runtime_config_sha256="a" * 64,
        campaign_id="campaign-1",
        market_date=nifty_cycle.received_at.date(),
        clock=lambda: nifty_cycle.received_at,
        sleep=lambda _: None,
    )
    launcher._record_retained_runtime_provider_incidents(
        handoffs={
            (item.prediction.underlying_symbol, item.prediction.exchange): item
            for item in received
        },
        observed_at=nifty_cycle.received_at,
    )
    blocker = Task9ExternalProviderBlockerStore(tmp_path).load("run")
    assert blocker["status"] == "ACTIVE"
    assert blocker["occurrence_count"] == 1


def test_composition_preserves_completed_market_when_other_market_failed():
    nifty_prediction, nifty_cycle, nifty_evaluation = _market_evidence(("NIFTY", "NSE"))
    sensex_prediction, sensex_cycle, _ = _market_evidence(("SENSEX", "BSE"))
    sensex_prediction = _failed_prediction(sensex_prediction)
    received = []

    _emit_task9_cycle_market_evidence(
        sink=received.append,
        cycles={("NIFTY", "NSE"): nifty_cycle, ("SENSEX", "BSE"): sensex_cycle},
        evaluations={nifty_cycle.observation_id: nifty_evaluation},
        predictions={("NIFTY", "NSE"): nifty_prediction, ("SENSEX", "BSE"): sensex_prediction},
        lifecycle_windows={
            ("NIFTY", "NSE"): resolve_prediction_lifecycle_window(prediction_record=nifty_prediction, session_policy=MarketSessionPolicy()),
            ("SENSEX", "BSE"): resolve_prediction_lifecycle_window(prediction_record=sensex_prediction, session_policy=MarketSessionPolicy()),
        },
        selected_market=None,
        selected_planning=None,
        selected_paper_observation=None,
    )

    assert received[0].evaluation is nifty_evaluation
    assert received[0].market_quote is not None
    assert received[1].evaluation is None
    assert received[1].market_quote is None
    assert received[1].data_quality is None


def test_completed_prediction_without_retained_evaluation_still_fails_closed():
    nifty_prediction, nifty_cycle, _ = _market_evidence(("NIFTY", "NSE"))
    sensex_prediction, sensex_cycle, sensex_evaluation = _market_evidence(("SENSEX", "BSE"))
    with pytest.raises(RuntimeError, match="retained evaluation missing"):
        _emit_task9_cycle_market_evidence(
            sink=lambda _: None,
            cycles={("NIFTY", "NSE"): nifty_cycle, ("SENSEX", "BSE"): sensex_cycle},
            evaluations={sensex_cycle.observation_id: sensex_evaluation},
            predictions={("NIFTY", "NSE"): nifty_prediction, ("SENSEX", "BSE"): sensex_prediction},
            lifecycle_windows={("NIFTY", "NSE"): resolve_prediction_lifecycle_window(prediction_record=nifty_prediction, session_policy=MarketSessionPolicy()), ("SENSEX", "BSE"): resolve_prediction_lifecycle_window(prediction_record=sensex_prediction, session_policy=MarketSessionPolicy())},
            selected_market=None, selected_planning=None, selected_paper_observation=None,
        )


def test_failed_prediction_with_retained_evaluation_still_fails_closed():
    nifty_prediction, nifty_cycle, nifty_evaluation = _market_evidence(("NIFTY", "NSE"))
    sensex_prediction, sensex_cycle, _ = _market_evidence(("SENSEX", "BSE"))
    nifty_prediction = _failed_prediction(nifty_prediction)
    sensex_prediction = _failed_prediction(sensex_prediction)
    with pytest.raises(RuntimeError, match="unexpectedly retained evaluation"):
        _emit_task9_cycle_market_evidence(
            sink=lambda _: None,
            cycles={("NIFTY", "NSE"): nifty_cycle, ("SENSEX", "BSE"): sensex_cycle},
            evaluations={nifty_cycle.observation_id: nifty_evaluation},
            predictions={("NIFTY", "NSE"): nifty_prediction, ("SENSEX", "BSE"): sensex_prediction},
            lifecycle_windows={("NIFTY", "NSE"): resolve_prediction_lifecycle_window(prediction_record=nifty_prediction, session_policy=MarketSessionPolicy()), ("SENSEX", "BSE"): resolve_prediction_lifecycle_window(prediction_record=sensex_prediction, session_policy=MarketSessionPolicy())},
            selected_market=None, selected_planning=None, selected_paper_observation=None,
        )


def test_failed_handoff_rejects_selected_planning_or_paper_observation():
    _, cycle_value, _, _, planning = _ready_selected_planning()
    prediction = records()[0]
    failed = _failed_prediction(prediction)

    with pytest.raises(ValueError, match="selected planning requires evaluation"):
        Task9CycleMarketEvidenceV1(
            prediction=failed,
            cycle=cycle_value,
            selected_planning=planning,
        )

    with pytest.raises(ValueError, match="paper observation requires evaluation"):
        Task9CycleMarketEvidenceV1(
            prediction=failed,
            cycle=cycle_value,
            paper_observation=make_observation(),
        )

    quote, quality = project_task9_live_spot_quote_with_quality(
        spot=_market_evidence(("NIFTY", "NSE"))[2].observation.spot,
    )
    with pytest.raises(ValueError, match="cannot retain quote evidence"):
        Task9CycleMarketEvidenceV1(
            prediction=failed,
            cycle=cycle_value,
            market_quote=quote,
            data_quality=quality,
        )
