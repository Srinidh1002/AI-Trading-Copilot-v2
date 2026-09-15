from dataclasses import replace
from datetime import timedelta
import logging

import pytest

from services.certification.task9_cycle_market_evidence_handoff import (
    Task9CycleMarketEvidenceV1,
)
from services.certification.task9_live_spot_quote_projection import (
    project_task9_live_spot_quote_with_quality,
)
from services.certification.task9_paper_portfolio_policy_store import (
    Task9PaperPortfolioPolicyStore,
)
from services.certification.task9_position_monitoring_runtime import (
    execute_task9_position_monitoring,
)
from services.certification.task9_prediction_lifecycle_context_store import (
    Task9PredictionLifecycleContextStore,
)
from services.certification.task9_prediction_lifecycle_outcome_store import (
    Task9PredictionLifecycleOutcomeStore,
)
from services.certification.task9_prediction_lifecycle_reconciliation_store import (
    Task9PredictionLifecycleReconciliationStore,
)
from services.certification.task9_prediction_lifecycle_timing import (
    resolve_prediction_lifecycle_window,
)
from services.certification.task9_prediction_observation_window_store import (
    Task9PredictionObservationWindowStore,
)
from services.certification.task9_prediction_paper_trade_binding_store import (
    Task9PredictionPaperTradeBindingStore,
    Task9PredictionPaperTradeBindingV1,
)
from services.certification.task9_production_child_evidence_authority import (
    build_task9_production_child_authority,
)
from services.certification.task9_selected_market_lifecycle_composition import (
    execute_task9_selected_market_lifecycle,
)
from services.contracts.prediction_lifecycle_outcome_policy_v1 import (
    PredictionLifecycleOutcomePolicyV1,
)
from services.market.angel_live_observation_normalizer import (
    AngelLiveSpotObservationV1,
)
from services.market_session.policies import (
    MarketSessionPolicy,
)
from services.paper_orchestration.continuous_position_monitoring_runtime import (
    execute_continuous_position_monitoring,
)
from services.paper_orchestration.prediction_ledger import (
    PredictionLedger,
)
from services.paper_portfolio.paper_portfolio_persistence_service import (
    PaperPortfolioPersistenceService,
)
from services.paper_portfolio_repository import (
    PaperPortfolioRepository,
)
from services.paper_trade_repository import (
    PaperTradeRepository,
)
from services.paper_trading.paper_trade_persistence_service import (
    PaperTradePersistenceService,
)
from tests.task916_real_runtime_harness import (
    build_task916_real_runtime_harness,
)
from tests.test_task8_parent_typed_candidate_certification import (
    captured,
    cycle,
)
from tests.test_task916_prediction_lifecycle_timing_policy import (
    prediction,
)
from tests.test_task9_position_monitoring_runtime import (
    PORTFOLIO_ID,
    _monitor_kwargs,
)


def _quote(prediction_record):
    observed_at = (
        prediction_record.completed_at
        + timedelta(seconds=1)
    )

    spot = AngelLiveSpotObservationV1(
        underlying_symbol=(
            prediction_record.underlying_symbol
        ),
        exchange=prediction_record.exchange,
        symboltoken=(
            "99926000"
            if prediction_record.underlying_symbol
            == "NIFTY"
            else "99919000"
        ),
        option_exchange=(
            "NFO"
            if prediction_record.underlying_symbol
            == "NIFTY"
            else "BFO"
        ),
        price=(
            prediction_record.start_underlying_price
        ),
        provider_timestamp=observed_at,
        evaluated_at=observed_at,
    )

    return project_task9_live_spot_quote_with_quality(
        spot=spot
    )


def _runtime(
    tmp_path,
    *,
    nifty_action="CALL",
    sensex_action="NO_TRADE",
):
    predictions = (
        prediction(
            nifty_action,
            market="NIFTY",
            exchange="NSE",
        ),
        prediction(
            sensex_action,
            market="SENSEX",
            exchange="BSE",
        ),
    )

    ledger = PredictionLedger(
        tmp_path / "prediction-ledger.json"
    )
    ledger.save_pair(predictions)

    context_store = (
        Task9PredictionLifecycleContextStore(
            tmp_path / "lifecycle-context.json"
        )
    )

    for item in predictions:
        context_store.save(
            resolve_prediction_lifecycle_window(
                prediction_record=item,
                session_policy=MarketSessionPolicy(),
            )
        )

    handoffs = {}

    for item in predictions:
        captured_evidence = captured(
            item.underlying_symbol,
            item.exchange,
            item.start_underlying_price,
        )

        cycle_value = cycle(
            item.underlying_symbol,
            item.exchange,
            captured_evidence,
        )

        quote, quality = _quote(item)

        identity = (
            item.underlying_symbol,
            item.exchange,
        )

        handoffs[identity] = (
            Task9CycleMarketEvidenceV1(
                prediction=item,
                cycle=cycle_value,
                market_quote=quote,
                data_quality=quality,
                lifecycle_window=context_store.recover(
                    item.prediction_id
                ),
            )
        )

    return {
        "predictions": predictions,
        "handoffs": handoffs,
        "ledger": ledger,
        "binding_store": (
            Task9PredictionPaperTradeBindingStore(
                tmp_path / "bindings.json"
            )
        ),
        "trade_service": (
            PaperTradePersistenceService(
                PaperTradeRepository(
                    tmp_path / "p7-trades.json"
                )
            )
        ),
        "context_store": context_store,
        "observation_store": (
            Task9PredictionObservationWindowStore(
                tmp_path / "observations.json"
            )
        ),
        "outcome_store": (
            Task9PredictionLifecycleOutcomeStore(
                tmp_path / "outcomes.json"
            )
        ),
        "reconciliation_store": (
            Task9PredictionLifecycleReconciliationStore(
                tmp_path / "reconciliations.json"
            )
        ),
        "boundary": (
            predictions[0].completed_at
            + timedelta(minutes=1)
        ),
    }


def _authority(runtime, **changes):
    values = {
        "official_run_id": (
            "task916-production-run"
        ),
        "cycle_evidence_by_market": (
            runtime["handoffs"]
        ),
        "evaluated_at": runtime["boundary"],
        "prediction_ledger": runtime["ledger"],
        "binding_store": (
            runtime["binding_store"]
        ),
        "trade_persistence_service": (
            runtime["trade_service"]
        ),
        "lifecycle_context_store": (
            runtime["context_store"]
        ),
        "observation_store": (
            runtime["observation_store"]
        ),
        "outcome_store": (
            runtime["outcome_store"]
        ),
        "reconciliation_store": (
            runtime["reconciliation_store"]
        ),
        "outcome_policy": (
            PredictionLifecycleOutcomePolicyV1(
                policy_id=(
                    "task916-production-policy"
                ),
                policy_version="1.0",
            )
        ),
    }

    values.update(changes)

    return build_task9_production_child_authority(
        **values
    )


def _harness_runtime(
    tmp_path,
    paper_observation=None,
):
    harness = build_task916_real_runtime_harness(
        tmp_path,
        market="NIFTY",
    )

    if paper_observation is None:
        paper_observation = (
            harness.entry_observation
        )

    selected = harness.selected_prediction

    other = next(
        item
        for item in harness.predictions
        if item.prediction_id
        != selected.prediction_id
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

    persistence_root = tmp_path / "p7"

    return {
        "harness": harness,
        "handoffs": {
            (
                "NIFTY",
                "NSE",
            ): Task9CycleMarketEvidenceV1(
                prediction=selected,
                cycle=harness.selected_cycle,
                evaluation=(
                    harness.selected_evaluation
                ),
                paper_observation=(
                    paper_observation
                ),
            ),
            (
                "SENSEX",
                "BSE",
            ): Task9CycleMarketEvidenceV1(
                prediction=other,
                cycle=other_cycle,
            ),
        },
        "ledger": harness.prediction_ledger,
        "binding_store": harness.binding_store,
        "trade_service": (
            PaperTradePersistenceService(
                PaperTradeRepository(
                    persistence_root
                    / "p7_trades.json"
                )
            )
        ),
        "portfolio_service": (
            PaperPortfolioPersistenceService(
                PaperPortfolioRepository(
                    persistence_root
                    / "p8_portfolios.json"
                )
            )
        ),
        "context_store": (
            harness.lifecycle_context_store
        ),
        "observation_store": (
            harness.observation_store
        ),
        "outcome_store": (
            Task9PredictionLifecycleOutcomeStore(
                tmp_path / "outcomes.json"
            )
        ),
        "reconciliation_store": (
            Task9PredictionLifecycleReconciliationStore(
                tmp_path / "reconciliations.json"
            )
        ),
        "boundary": (
            paper_observation.observed_at
            + timedelta(seconds=2)
        ),
    }


def _entry_delegate(
    tmp_path,
    runtime,
    policy_store,
):
    harness = runtime["harness"]

    def delegate(
        evidence,
        prediction_id,
    ):
        assert (
            evidence
            is runtime["handoffs"][
                ("NIFTY", "NSE")
            ]
        )

        return (
            execute_task9_selected_market_lifecycle(
                official_run_id=(
                    "task916-production-run"
                ),
                binding_store=(
                    harness.binding_store
                ),
                prediction_id=prediction_id,
                prediction_ledger=(
                    harness.prediction_ledger
                ),
                lifecycle_context_store=(
                    harness.lifecycle_context_store
                ),
                observation_store=(
                    harness.observation_store
                ),
                portfolio_policy_store=(
                    policy_store
                ),
                selected_cycle=(
                    harness.selected_cycle
                ),
                selected_planning=(
                    harness.selected_planning
                ),
                available_capital=300000.0,
                evaluated_at=(
                    harness.decision.completed_at
                ),
                persistence_root=(
                    tmp_path / "p7"
                ),
                portfolio_id=PORTFOLIO_ID,
            )
        )

    return delegate


@pytest.mark.parametrize(
    (
        "market",
        "exchange",
        "action",
    ),
    (
        (
            "NIFTY",
            "NSE",
            "WAIT",
        ),
        (
            "SENSEX",
            "BSE",
            "NO_TRADE",
        ),
    ),
)
def test_abstention_records_quote_observation_and_remains_non_countable(
    tmp_path,
    market,
    exchange,
    action,
):
    runtime = _runtime(
        tmp_path,
        nifty_action=(
            action
            if market == "NIFTY"
            else "WAIT"
        ),
        sensex_action=(
            action
            if market == "SENSEX"
            else "NO_TRADE"
        ),
    )

    authority = _authority(runtime)

    first = authority(
        market,
        exchange,
        False,
    )

    second = authority(
        market,
        exchange,
        False,
    )

    prediction_record = next(
        item
        for item in runtime["predictions"]
        if (
            item.underlying_symbol,
            item.exchange,
        )
        == (
            market,
            exchange,
        )
    )

    window = (
        runtime["observation_store"].recover(
            prediction_record.prediction_id
        )
    )

    assert first == second
    assert (
        first.terminal_position_closed
        is False
    )
    assert first.reconciliation is None

    assert (
        runtime[
            "binding_store"
        ].by_prediction(
            prediction_record.prediction_id
        )
        is None
    )

    assert window is not None
    assert len(window.observations) == 1


def test_call_without_binding_and_entry_disallowed_creates_no_trade(
    tmp_path,
):
    runtime = _runtime(tmp_path)
    calls = []

    authority = _authority(
        runtime,
        entry_delegate=(
            lambda evidence, prediction_id:
            calls.append(
                (
                    evidence,
                    prediction_id,
                )
            )
        ),
    )

    result = authority(
        "NIFTY",
        "NSE",
        False,
    )

    assert calls == []

    assert (
        result.terminal_position_closed
        is False
    )

    assert (
        runtime[
            "binding_store"
        ].by_prediction(
            result.prediction.prediction_id
        )
        is None
    )


def test_failed_child_is_returned_as_data_incident_without_entry_or_lifecycle(
    tmp_path,
):
    runtime = _runtime(tmp_path)
    original, other = runtime["predictions"]

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

    ledger = PredictionLedger(
        tmp_path / "failed-prediction-ledger.json"
    )
    ledger.save_pair((failed, other))

    runtime["ledger"] = ledger

    runtime["handoffs"][("NIFTY", "NSE")] = replace(
        runtime["handoffs"][("NIFTY", "NSE")],
        prediction=failed,
        market_quote=None,
        data_quality=None,
    )

    result = _authority(runtime)(
        "NIFTY",
        "NSE",
        True,
    )

    assert (
        result.evidence_status
        == "DATA_INCIDENT"
    )

    assert (
        result.prediction.errors
        == ("HISTORICAL-DATA_RATE_LIMITED",)
    )

    assert (
        result.terminal_position_closed
        is False
    )

    assert (
        runtime[
            "binding_store"
        ].by_prediction(
            failed.prediction_id
        )
        is None
    )

    assert (
        runtime[
            "outcome_store"
        ].recover(
            failed.prediction_id
        )
        is None
    )

    assert (
        runtime[
            "reconciliation_store"
        ].recover(
            failed.prediction_id
        )
        is None
    )


@pytest.mark.parametrize(
    ("failure_code", "exception_class"),
    (
        ("CANDIDATE_COMPOSITION_FAILED", "ValueError"),
        ("ANALYSIS_EVALUATION_FAILED", "RuntimeError"),
    ),
)
def test_generic_failed_child_remains_non_trading_without_provider_incident(
    tmp_path,
    failure_code,
    exception_class,
):
    runtime = _runtime(tmp_path)
    original, other = runtime["predictions"]
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
        blockers=(failure_code,),
        errors=(failure_code,),
        failure_diagnostic={
            "failure_stage": "ANALYSIS_AUTHORITY",
            "exception_class": exception_class,
            "stable_failure_code": failure_code,
        },
    )
    ledger = PredictionLedger(tmp_path / "generic-failed-ledger.json")
    ledger.save_pair((failed, other))
    runtime["ledger"] = ledger
    runtime["handoffs"][("NIFTY", "NSE")] = replace(
        runtime["handoffs"][("NIFTY", "NSE")],
        prediction=failed,
        market_quote=None,
        data_quality=None,
    )

    result = _authority(runtime)("NIFTY", "NSE", True)

    assert result.evidence_status == "VALID"
    assert result.prediction.terminal_status == "FAILED"
    assert result.prediction.predicted_action == "WAIT"
    assert result.lifecycle_outcome is None
    assert result.reconciliation is None
    assert result.terminal_position_closed is False
    assert dict(result.prediction.failure_diagnostic) == {
        "failure_stage": "ANALYSIS_AUTHORITY",
        "exception_class": exception_class,
        "stable_failure_code": failure_code,
    }
    assert "secret" not in repr(result)
    assert "Traceback" not in repr(result)
    assert runtime["binding_store"].by_prediction(failed.prediction_id) is None
    assert runtime["observation_store"].recover(failed.prediction_id) is None
    assert runtime["outcome_store"].recover(failed.prediction_id) is None
    assert runtime["reconciliation_store"].recover(failed.prediction_id) is None
    assert runtime["trade_service"].list_all() == ()


def test_call_without_binding_and_entry_allowed_delegates_exact_evidence(
    tmp_path,
):
    runtime = _runtime(tmp_path)
    calls = []

    authority = _authority(
        runtime,
        entry_delegate=(
            lambda evidence, prediction_id:
            calls.append(
                (
                    evidence,
                    prediction_id,
                )
            )
        ),
    )

    result = authority(
        "NIFTY",
        "NSE",
        True,
    )

    assert (
        result.terminal_position_closed
        is False
    )

    assert calls == [
        (
            runtime["handoffs"][
                ("NIFTY", "NSE")
            ],
            result.prediction.prediction_id,
        )
    ]


def test_missing_durable_snapshot_for_existing_binding_fails_closed(
    tmp_path,
):
    runtime = _runtime(tmp_path)

    prediction_record = (
        runtime["predictions"][0]
    )

    runtime["binding_store"].save(
        Task9PredictionPaperTradeBindingV1(
            official_run_id=(
                "task916-production-run"
            ),
            prediction_id=(
                prediction_record.prediction_id
            ),
            market="NIFTY",
            paper_trade_id=(
                "missing-paper-trade"
            ),
            paper_position_id=(
                "missing-position"
            ),
            option_symbol=(
                "NIFTY26AUG25000CE"
            ),
            entered_at=(
                prediction_record.completed_at
            ),
        )
    )

    with pytest.raises(
        ValueError,
        match="snapshot unavailable",
    ):
        _authority(runtime)(
            "NIFTY",
            "NSE",
            False,
        )


def test_child_signature_rejects_market_identity_mismatch_and_has_no_progress_side_effect(
    tmp_path,
):
    runtime = _runtime(tmp_path)
    authority = _authority(runtime)

    with pytest.raises(
        ValueError,
        match="market identity",
    ):
        authority(
            "NIFTY",
            "BSE",
            False,
        )

    assert (
        runtime["outcome_store"].recover(
            runtime[
                "predictions"
            ][0].prediction_id
        )
        is None
    )

    assert (
        runtime[
            "reconciliation_store"
        ].recover(
            runtime[
                "predictions"
            ][0].prediction_id
        )
        is None
    )


def test_bound_active_call_delegates_exact_observation_and_remains_non_countable(
    tmp_path,
):
    runtime = _harness_runtime(
        tmp_path,
    )

    policy_store = (
        Task9PaperPortfolioPolicyStore(
            tmp_path
            / "portfolio-policies.json"
        )
    )

    entry = _entry_delegate(
        tmp_path,
        runtime,
        policy_store,
    )

    _authority(
        runtime,
        entry_delegate=entry,
    )(
        "NIFTY",
        "NSE",
        True,
    )

    received = []

    def monitor(
        evidence,
        snapshot,
        observation,
    ):
        received.append(
            (
                evidence,
                snapshot,
                observation,
            )
        )

    result = _authority(
        runtime,
        monitoring_delegate=monitor,
    )(
        "NIFTY",
        "NSE",
        False,
    )

    assert (
        result.terminal_position_closed
        is False
    )

    assert len(received) == 1

    assert (
        received[0][0]
        is runtime["handoffs"][
            ("NIFTY", "NSE")
        ]
    )

    assert (
        received[0][2]
        is runtime["handoffs"][
            ("NIFTY", "NSE")
        ].paper_observation
    )


def test_monitoring_terminal_state_persists_and_restart_recovers_identical_evidence(
    tmp_path,
):
    runtime = _harness_runtime(
        tmp_path,
    )

    policy_store = (
        Task9PaperPortfolioPolicyStore(
            tmp_path
            / "portfolio-policies.json"
        )
    )

    _authority(
        runtime,
        entry_delegate=_entry_delegate(
            tmp_path,
            runtime,
            policy_store,
        ),
    )(
        "NIFTY",
        "NSE",
        True,
    )

    prediction_record = (
        runtime[
            "harness"
        ].selected_prediction
    )

    binding = (
        runtime[
            "binding_store"
        ].by_prediction(
            prediction_record.prediction_id
        )
    )

    assert binding is not None

    snapshot = (
        runtime[
            "trade_service"
        ].get(
            binding.paper_trade_id
        )
    )

    assert snapshot is not None
    assert snapshot.position is not None

    entry_observation = (
        runtime[
            "harness"
        ].entry_observation
    )

    terminal_observation = replace(
        entry_observation,
        observation_id=(
            "task916-production-"
            "terminal-observation"
        ),
        trade_plan_id=(
            snapshot.position.trade_plan_id
        ),
        integrated_trade_plan_result_id=(
            snapshot.position.integrated_trade_plan_result_id
        ),
        selected_option_contract_id=(
            snapshot.position.selected_option_contract_id
        ),
        underlying_symbol=(
            snapshot.position.underlying_symbol
        ),
        option_symbol=(
            snapshot.position.option_symbol
        ),
        observed_at=(
            entry_observation.observed_at
            + timedelta(seconds=1)
        ),
        received_at=(
            entry_observation.received_at
            + timedelta(seconds=1)
        ),
        option_last_price=(
            snapshot.position.target_2
        ),
    )

    runtime["handoffs"][
        ("NIFTY", "NSE")
    ] = replace(
        runtime["handoffs"][
            ("NIFTY", "NSE")
        ],
        paper_observation=(
            terminal_observation
        ),
    )

    runtime["boundary"] = (
        terminal_observation.observed_at
        + timedelta(seconds=1)
    )

    def monitor(
        evidence,
        recovered_snapshot,
        observation,
    ):
        portfolio = (
            runtime[
                "portfolio_service"
            ].get(
                PORTFOLIO_ID
            )
        )

        assert portfolio is not None

        portfolio_policy = (
            policy_store.recover(
                portfolio
                .portfolio_snapshot
                .portfolio_policy_id
            )
        )

        assert portfolio_policy is not None

        return execute_task9_position_monitoring(
            recovered_snapshot=(
                recovered_snapshot
            ),
            observation=observation,
            prediction_ledger=(
                runtime["ledger"]
            ),
            binding_store=(
                runtime["binding_store"]
            ),
            lifecycle_context_store=(
                runtime["context_store"]
            ),
            observation_store=(
                runtime["observation_store"]
            ),
            monitor=(
                execute_continuous_position_monitoring
            ),
            monitor_kwargs=_monitor_kwargs(
                portfolio_service=(
                    runtime[
                        "portfolio_service"
                    ]
                ),
                trade_service=(
                    runtime[
                        "trade_service"
                    ]
                ),
                portfolio_policy=(
                    portfolio_policy
                ),
                paper_trade_id=(
                    recovered_snapshot
                    .paper_trade_id
                ),
                observation=observation,
            ),
        )

    terminal = _authority(
        runtime,
        monitoring_delegate=monitor,
    )(
        "NIFTY",
        "NSE",
        False,
    )

    restarted_runtime = dict(runtime)

    restarted_runtime.update(
        {
            "ledger": PredictionLedger(
                tmp_path
                / "task916-prediction-ledger.json"
            ),
            "binding_store": (
                Task9PredictionPaperTradeBindingStore(
                    tmp_path
                    / "task916-bindings.json"
                )
            ),
            "trade_service": (
                PaperTradePersistenceService(
                    PaperTradeRepository(
                        tmp_path
                        / "p7"
                        / "p7_trades.json"
                    )
                )
            ),
            "portfolio_service": (
                PaperPortfolioPersistenceService(
                    PaperPortfolioRepository(
                        tmp_path
                        / "p7"
                        / "p8_portfolios.json"
                    )
                )
            ),
            "context_store": (
                Task9PredictionLifecycleContextStore(
                    tmp_path
                    / "task916-lifecycle-context.json"
                )
            ),
            "observation_store": (
                Task9PredictionObservationWindowStore(
                    tmp_path
                    / "task916-observations.json"
                )
            ),
            "outcome_store": (
                Task9PredictionLifecycleOutcomeStore(
                    tmp_path
                    / "outcomes.json"
                )
            ),
            "reconciliation_store": (
                Task9PredictionLifecycleReconciliationStore(
                    tmp_path
                    / "reconciliations.json"
                )
            ),
        }
    )

    restarted = _authority(
        restarted_runtime,
        monitoring_delegate=(
            lambda *_: pytest.fail(
                "monitoring must not recur"
            )
        ),
    )(
        "NIFTY",
        "NSE",
        False,
    )

    assert (
        terminal.terminal_position_closed
        is True
    )

    assert (
        terminal.lifecycle_outcome
        is not None
    )

    assert (
        terminal.reconciliation
        is not None
    )

    assert restarted == terminal


@pytest.mark.parametrize(
    "market,exchange",
    (
        ("NIFTY", "BSE"),
        ("SENSEX", "NSE"),
    ),
)
def test_child_authority_input_failure_logs_only_safe_stage_and_reraises(
    tmp_path,
    caplog,
    market,
    exchange,
):
    authority = _authority(
        _runtime(tmp_path)
    )

    with caplog.at_level(
        logging.ERROR,
        logger=(
            "services.certification."
            "task9_production_child_evidence_authority"
        ),
    ):
        with pytest.raises(ValueError):
            authority(
                market,
                exchange,
                False,
            )

    message = caplog.messages[-1]

    assert message == (
        "TASK9_CHILD_AUTHORITY_FAILURE "
        f"market={market} "
        "stage=INPUT_HANDOFF_VALIDATION "
        "error_type=ValueError"
    )

    assert "market identity" not in message


def test_child_authority_prediction_recovery_hides_raw_exception_text(
    tmp_path,
    caplog,
    monkeypatch,
):
    runtime = _runtime(tmp_path)

    def unsafe_recover(_):
        raise ValueError(
            "jwtToken=secret provider-payload"
        )

    monkeypatch.setattr(
        PredictionLedger,
        "recover",
        lambda self, value: unsafe_recover(value),
    )

    authority = _authority(runtime)

    with caplog.at_level(
        logging.ERROR,
        logger=(
            "services.certification."
            "task9_production_child_evidence_authority"
        ),
    ):
        with pytest.raises(
            ValueError,
            match=(
                "jwtToken=secret provider-payload"
            ),
        ):
            authority(
                "NIFTY",
                "NSE",
                False,
            )

    message = caplog.messages[-1]

    assert message == (
        "TASK9_CHILD_AUTHORITY_FAILURE "
        "market=NIFTY "
        "stage=PREDICTION_RECOVERY "
        "error_type=ValueError"
    )

    assert "secret" not in message
    assert "payload" not in message


@pytest.mark.parametrize(
    "market,exchange",
    (
        ("NIFTY", "NSE"),
        ("SENSEX", "BSE"),
    ),
)
def test_pre_prediction_abstention_quote_initializes_window_without_projection_or_failure(
    tmp_path,
    market,
    exchange,
):
    runtime = _runtime(
        tmp_path,
        nifty_action="NO_TRADE",
        sensex_action="WAIT",
    )

    identity = (
        market,
        exchange,
    )

    handoff = runtime["handoffs"][identity]

    older_at = (
        handoff.prediction.completed_at
        - timedelta(seconds=1)
    )

    older_quote = replace(
        handoff.market_quote,
        observed_at=older_at,
        received_at=older_at,
    )

    older_quality = replace(
        handoff.data_quality,
        observed_at=older_at,
        received_at=older_at,
    )

    runtime["handoffs"][identity] = replace(
        handoff,
        market_quote=older_quote,
        data_quality=older_quality,
    )

    authority = _authority(runtime)

    first = authority(
        market,
        exchange,
        False,
    )

    restarted = _authority(runtime)(
        market,
        exchange,
        False,
    )

    window = (
        runtime["observation_store"].recover(
            handoff.prediction.prediction_id
        )
    )

    assert (
        first.lifecycle_outcome
        is None
    )

    assert (
        restarted.lifecycle_outcome
        is None
    )

    assert window is not None

    assert (
        window.observations
        == ()
    )

    assert (
        first.prediction.execution_mode
        == "PAPER"
    )

    assert (
        first.prediction.live_execution_eligible
        is False
    )

    assert (
        first.prediction.broker_order_submission
        is False
    )

    assert (
        runtime[
            "binding_store"
        ].by_prediction(
            handoff.prediction.prediction_id
        )
        is None
    )

    assert (
        runtime[
            "outcome_store"
        ].recover(
            handoff.prediction.prediction_id
        )
        is None
    )

    assert (
        runtime[
            "reconciliation_store"
        ].recover(
            handoff.prediction.prediction_id
        )
        is None
    )


@pytest.mark.parametrize(
    "market,exchange,action",
    (
        ("NIFTY", "NSE", "WAIT"),
        ("NIFTY", "NSE", "NO_TRADE"),
        ("SENSEX", "BSE", "WAIT"),
        ("SENSEX", "BSE", "NO_TRADE"),
    ),
)
def test_abstention_never_invokes_entry_delegate_even_when_session_allows_entry(
    tmp_path,
    market,
    exchange,
    action,
):
    runtime = _runtime(
        tmp_path,
        nifty_action=(
            action
            if market == "NIFTY"
            else "WAIT"
        ),
        sensex_action=(
            action
            if market == "SENSEX"
            else "NO_TRADE"
        ),
    )

    calls = []

    authority = _authority(
        runtime,
        entry_delegate=(
            lambda evidence, prediction_id:
            calls.append(
                (
                    evidence,
                    prediction_id,
                )
            )
        ),
    )

    result = authority(
        market,
        exchange,
        True,
    )

    prediction_record = next(
        item
        for item in runtime["predictions"]
        if (
            item.underlying_symbol,
            item.exchange,
        )
        == (
            market,
            exchange,
        )
    )

    assert (
        prediction_record.predicted_action
        == action
    )

    assert calls == []

    assert (
        result.prediction.prediction_id
        == prediction_record.prediction_id
    )

    assert (
        result.terminal_position_closed
        is False
    )

    assert (
        runtime["binding_store"].by_prediction(
            prediction_record.prediction_id
        )
        is None
    )
