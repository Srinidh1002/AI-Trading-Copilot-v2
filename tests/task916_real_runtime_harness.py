from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone
from pathlib import Path
from services.contracts.certified_live_captured_evidence_v1 import (
    CertifiedLiveCapturedEvidenceV1,
)
from services.analysis.live_canonical_engine_adapters import (
    build_default_live_canonical_evidence_engines,
)
from services.analysis.live_canonical_evidence_engines import (
    LiveCanonicalEvidenceEnginesV1,
)
from services.analysis.live_market_candidate_evaluator import (
    LiveCandidatePolicySourceV1,
    LiveMarketCandidateEvaluationResultV1,
    evaluate_captured_certified_market_candidate,
)
from services.certification.task8_selected_market_p6_bundle import (
    build_task8_selected_market_p6_bundle,
)
from services.certification.task9_prediction_lifecycle_context_store import (
    Task9PredictionLifecycleContextStore,
)
from services.certification.task9_prediction_lifecycle_timing import (
    resolve_prediction_lifecycle_window,
)
from services.certification.task9_prediction_observation_window_store import (
    Task9PredictionObservationWindowStore,
)
from services.certification.task9_prediction_paper_trade_binding_store import (
    Task9PredictionPaperTradeBindingStore,
)
from services.contracts.canonical_market_regime_result_v1 import (
    CanonicalMarketRegimeResultV1,
)
from services.contracts.two_market_child_terminal_result_v1 import (
    TwoMarketChildTerminalResultV1,
)
from services.contracts.two_market_decision_result_v1 import (
    TwoMarketDecisionEntryV1,
    TwoMarketDecisionResultV1,
)
from services.market_session.policies import MarketSessionPolicy
from services.paper_orchestration.prediction_ledger import PredictionLedger
from services.paper_orchestration.prediction_record_projector import (
    project_parent_decision_predictions,
)
from services.paper_orchestration.selected_market_p6_planning_runtime import (
    SelectedMarketP6PlanningResultV1,
    execute_selected_market_p6_planning,
)
from services.trade_planning.selected_market_planning_bridge import (
    bridge_selected_market_to_planning,
)
from tests.p7_fixture_helpers import make_observation
from tests.test_apt2_paper_lifecycle_certification import _services
from tests.test_task8_selected_market_p6_bundle import (
    captured,
    cycle,
)


UTC = timezone.utc


@dataclass(frozen=True, slots=True)
class Task916RuntimeSeed:
    parent_cycle_id: str
    decision_result_id: str
    selected_market: tuple[str, str]
    nifty_observation_id: str
    sensex_observation_id: str
    nifty_price: float
    sensex_price: float
    entry_observation_id: str


@dataclass(frozen=True, slots=True)
class Task916RealRuntimeHarness:
    seed: Task916RuntimeSeed
    decision: TwoMarketDecisionResultV1
    predictions: tuple
    selected_prediction: object
    selected_cycle: object
    selected_evaluation: LiveMarketCandidateEvaluationResultV1
    selected_bridge: object
    selected_p6_bundle: object
    selected_planning: SelectedMarketP6PlanningResultV1
    entry_observation: object
    prediction_ledger: PredictionLedger
    lifecycle_context_store: Task9PredictionLifecycleContextStore
    binding_store: Task9PredictionPaperTradeBindingStore
    observation_store: Task9PredictionObservationWindowStore
    portfolio_service: object
    trade_service: object


def _default_seed(
    *,
    market: str,
) -> Task916RuntimeSeed:
    normalized = market.upper()

    if normalized not in {"NIFTY", "SENSEX"}:
        raise ValueError("market")

    return Task916RuntimeSeed(
        parent_cycle_id=f"task916-parent-{normalized.lower()}",
        decision_result_id=f"task916-decision-{normalized.lower()}",
        selected_market=(
            ("NIFTY", "NSE")
            if normalized == "NIFTY"
            else ("SENSEX", "BSE")
        ),
        nifty_observation_id="observation:NIFTY",
        sensex_observation_id="observation:SENSEX",
        nifty_price=25000.0,
        sensex_price=80000.0,
        entry_observation_id=(
            f"task916-entry-{normalized.lower()}"
        ),
    )


def _task916_ready_regime(
    technical,
    session,
    evaluated_at,
    broader_market=None,
    external_context=None,
):
    return CanonicalMarketRegimeResultV1(
        market_regime_result_id=(
            f"task916-regime-"
            f"{technical.underlying_symbol.lower()}"
        ),
        created_at=evaluated_at,
        underlying_symbol=technical.underlying_symbol,
        exchange=technical.exchange,
        technical_context=technical,
        broader_market_context=broader_market,
        external_market_context=external_context,
        market_session_validation=session,
        context_status="READY",
        directional_regime="BULLISH",
        trend_state="UPTREND",
        volatility_state="NORMAL",
        market_condition="NORMAL",
        confirmation_state="CONFIRMING",
        entry_suitability="SUITABLE",
        regime_strength=0.8,
        confidence=0.8,
        available_component_count=2,
        unavailable_component_count=2,
        confirming_component_count=1,
        conflicting_component_count=0,
        supporting_evidence=(
            "TASK916_CERTIFICATION_REGIME",
        ),
        primary_regime="BULLISH",
        event_risk_state="NONE",
        entry_restriction_state="OPEN",
        analysis_allowed=True,
        new_entries_allowed=True,
    )


def _task916_engines() -> LiveCanonicalEvidenceEnginesV1:
    default = (
        build_default_live_canonical_evidence_engines()
    )

    return LiveCanonicalEvidenceEnginesV1(
        data_quality=default.data_quality,
        multi_timeframe=default.multi_timeframe,
        technical=default.technical,
        regime=_task916_ready_regime,
        option_chain=default.option_chain,
        contract_ranking=default.contract_ranking,
        pillars=default.pillars,
    )
def _task916_capture(
    *,
    symbol: str,
    exchange: str,
    spot: float,
) -> CertifiedLiveCapturedEvidenceV1:
    base = captured(
        symbol,
        exchange,
        spot,
        complete_options=False,
    )
    candle_rows_by_timeframe = {}

    for timeframe, source_rows in (
        base.candle_rows_by_timeframe.items()
    ):
        rows = list(source_rows)

        if len(rows) < 2:
            raise AssertionError(
                f"Task916 {timeframe} candle history "
                "is insufficient"
            )

        prior_window = rows[-21:-1]

        if not prior_window:
            raise AssertionError(
                f"Task916 {timeframe} prior resistance "
                "window is unavailable"
            )

        prior_resistance = max(
            float(row[2])
            for row in prior_window
        )

        last = rows[-1]

        breakout_close = prior_resistance + 5.0
        breakout_high = breakout_close + 1.0

        rows[-1] = (
            last[0],
            last[1],
            breakout_high,
            last[3],
            breakout_close,
            last[5],
        )

        candle_rows_by_timeframe[timeframe] = tuple(rows)
    expiry = "2026-08-06"
    contracts = []

    strikes = tuple(
        spot + 50.0 * offset
        for offset in range(-5, 5)
    )

    for index, strike in enumerate(strikes):
        # Deliberately vary liquidity by strike so OI concentration has
        # one deterministic dominant strike instead of a ten-way tie.
        distance_steps = abs(strike - spot) / 50.0

        call_oi = int(
            2000 - distance_steps * 120
        )
        put_oi = int(
            call_oi * 1.20
        )

        call_volume = int(
            1000 - distance_steps * 60
        )
        put_volume = int(
            call_volume * 1.20
        )

        for (
            suffix,
            option_type,
            oi,
            volume,
            premium,
            oi_change,
        ) in (
            (
                "CE",
                "CE",
                call_oi,
                call_volume,
                100.0,
                -100,
            ),
            (
                "PE",
                "PE",
                put_oi,
                put_volume,
                110.0,
                100,
            ),
        ):
            token = (
                f"task916-{symbol}-"
                f"{int(strike)}-{suffix}"
            )

            contracts.append(
                {
                    "exchange": base.option_exchange,
                    "underlying": symbol,
                    "token": token,
                    "symbol": (
                        f"{symbol}06AUG26"
                        f"{int(strike)}{suffix}"
                    ),
                    "option_type": option_type,
                    "expiry": expiry,
                    "strike": strike,
                    "lot_size": 25,
                    "tick_size": 0.05,
                    "premium": premium,
                    "bid": premium - 1.0,
                    "ask": premium + 1.0,
                    "volume": volume,
                    "open_interest": oi,
                    "change_in_open_interest": oi_change,
                    "iv": 15.0,
                }
            )

    return CertifiedLiveCapturedEvidenceV1(
        underlying_symbol=base.underlying_symbol,
        spot_exchange=base.spot_exchange,
        spot_token=base.spot_token,
        option_exchange=base.option_exchange,
        spot_payload=dict(base.spot_payload),
        candle_rows_by_timeframe=(
            candle_rows_by_timeframe
        ),
        option_contracts=tuple(contracts),
        provider_timestamp=base.provider_timestamp,
        evaluated_at=base.evaluated_at,
        provider_blockers=(),
        provider_warnings=(),
        cache_metadata={
            "source": "TASK916_CANONICAL_FIXTURE",
            "cached": False,
        },
    )

def _market_cycle_and_evaluation(
    *,
    seed: Task916RuntimeSeed,
    symbol: str,
    exchange: str,
    price: float,
    selected: bool,
):
    capture = _task916_capture(
        symbol=symbol,
        exchange=exchange,
        spot=price,
    )

    cycle_value = cycle(
        symbol,
        exchange,
        capture,
    )

    evaluation = evaluate_captured_certified_market_candidate(
        captured_evidence=capture,
        session_validation=cycle_value.session_validation,
        policy_source=LiveCandidatePolicySourceV1(
            "BULLISH",
            "ELIGIBLE",
            80.0 if selected else 60.0,
            80.0 if selected else 60.0,
            reasons=(
                "TASK916 CANONICAL FIXTURE",
            ),
        ),
        parent_cycle_id=seed.parent_cycle_id,
        candidate_id=(
            f"task916-candidate-{symbol.lower()}"
        ),
        observation_id=cycle_value.observation_id,
        engines=_task916_engines(),
    )

    candidate = evaluation.candidate

    if candidate.direction != "BULLISH":
        raise AssertionError(
            f"Task916 candidate direction: "
            f"{candidate.direction}"
        )

    if candidate.eligibility != "ELIGIBLE":
        raise AssertionError(
            f"Task916 candidate eligibility: "
            f"{candidate.eligibility}; "
            f"blockers={candidate.blockers}"
        )

    if candidate.blockers:
        raise AssertionError(
            f"Task916 candidate blockers: "
            f"{candidate.blockers}"
        )

    if candidate.contradictions:
        raise AssertionError(
            f"Task916 candidate contradictions: "
            f"{candidate.contradictions}"
        )

    return cycle_value, evaluation


def _child_from_evaluation(
    *,
    seed: Task916RuntimeSeed,
    evaluation: LiveMarketCandidateEvaluationResultV1,
) -> TwoMarketChildTerminalResultV1:
    candidate = evaluation.candidate

    return TwoMarketChildTerminalResultV1(
        child_result_id=(
            f"task916-child-"
            f"{candidate.underlying_symbol.lower()}"
        ),
        parent_cycle_id=seed.parent_cycle_id,
        observation_id=candidate.observation_id,
        underlying_symbol=candidate.underlying_symbol,
        exchange=candidate.exchange,
        requested_at=candidate.requested_at,
        received_at=candidate.received_at,
        terminal_status="COMPLETED",
        candidate=candidate,
    )


def _decision_from_evaluations(
    *,
    seed: Task916RuntimeSeed,
    nifty_evaluation: LiveMarketCandidateEvaluationResultV1,
    sensex_evaluation: LiveMarketCandidateEvaluationResultV1,
) -> TwoMarketDecisionResultV1:
    nifty = _child_from_evaluation(
        seed=seed,
        evaluation=nifty_evaluation,
    )

    sensex = _child_from_evaluation(
        seed=seed,
        evaluation=sensex_evaluation,
    )

    selected_symbol = seed.selected_market[0]

    selected_child = (
        nifty
        if selected_symbol == "NIFTY"
        else sensex
    )

    entries = (
        TwoMarketDecisionEntryV1(
            child=nifty,
            eligible_for_comparison=True,
            rank_value=nifty.candidate.score,
            outcome_reason=(
                "SELECTED"
                if selected_symbol == "NIFTY"
                else "LOWER_RANK"
            ),
            rationale=(
                ("TASK916_SELECTED",)
                if selected_symbol == "NIFTY"
                else ("LOWER_SCORE",)
            ),
        ),
        TwoMarketDecisionEntryV1(
            child=sensex,
            eligible_for_comparison=True,
            rank_value=sensex.candidate.score,
            outcome_reason=(
                "SELECTED"
                if selected_symbol == "SENSEX"
                else "LOWER_RANK"
            ),
            rationale=(
                ("TASK916_SELECTED",)
                if selected_symbol == "SENSEX"
                else ("LOWER_SCORE",)
            ),
        ),
    )

    return TwoMarketDecisionResultV1(
        decision_result_id=seed.decision_result_id,
        parent_cycle_id=seed.parent_cycle_id,
        requested_at=min(
            nifty.requested_at,
            sensex.requested_at,
        ),
        completed_at=max(
            nifty.received_at,
            sensex.received_at,
        ),
        entries=entries,
        decision="SELECTED",
        selected_market=seed.selected_market,
        selected_candidate_id=(
            selected_child.candidate.candidate_id
        ),
        timestamp_skew_seconds=0.0,
    )


def build_task916_real_runtime_harness(
    tmp_path: Path,
    *,
    market: str = "NIFTY",
) -> Task916RealRuntimeHarness:
    normalized_market = market.upper()

    seed = _default_seed(
        market=normalized_market,
    )

    nifty_cycle, nifty_evaluation = (
        _market_cycle_and_evaluation(
            seed=seed,
            symbol="NIFTY",
            exchange="NSE",
            price=seed.nifty_price,
            selected=normalized_market == "NIFTY",
        )
    )

    sensex_cycle, sensex_evaluation = (
        _market_cycle_and_evaluation(
            seed=seed,
            symbol="SENSEX",
            exchange="BSE",
            price=seed.sensex_price,
            selected=normalized_market == "SENSEX",
        )
    )

    decision = _decision_from_evaluations(
        seed=seed,
        nifty_evaluation=nifty_evaluation,
        sensex_evaluation=sensex_evaluation,
    )

    predictions = project_parent_decision_predictions(
        decision,
        start_underlying_prices={
            ("NIFTY", "NSE"): seed.nifty_price,
            ("SENSEX", "BSE"): seed.sensex_price,
        },
    )

    selected_prediction = next(
        item
        for item in predictions
        if (
            item.underlying_symbol,
            item.exchange,
        )
        == seed.selected_market
    )

    selected_cycle = (
        nifty_cycle
        if normalized_market == "NIFTY"
        else sensex_cycle
    )

    selected_evaluation = (
        nifty_evaluation
        if normalized_market == "NIFTY"
        else sensex_evaluation
    )

    if (
        selected_evaluation.candidate
        is not next(
            entry.child.candidate
            for entry in decision.entries
            if entry.child.underlying_symbol
            == normalized_market
        )
    ):
        raise AssertionError(
            "Task916 parent did not retain exact "
            "selected evaluation candidate"
        )

    prediction_ledger = PredictionLedger(
        tmp_path / "task916-prediction-ledger.json"
    )

    prediction_ledger.save_pair(
        predictions
    )

    lifecycle_context_store = (
        Task9PredictionLifecycleContextStore(
            tmp_path / "task916-lifecycle-context.json"
        )
    )

    session_policy = MarketSessionPolicy()

    for prediction in predictions:
        lifecycle_context_store.save(
            resolve_prediction_lifecycle_window(
                prediction_record=prediction,
                session_policy=session_policy,
            )
        )

    selected_bridge = bridge_selected_market_to_planning(
        bridge_result_id=(
            f"task916-bridge-"
            f"{normalized_market.lower()}"
        ),
        decision=decision,
        evaluated_at=decision.completed_at,
        maximum_candidate_age_seconds=180.0,
    )

    bundle = build_task8_selected_market_p6_bundle(
        bridge=selected_bridge,
        cycle=selected_cycle,
        evaluation=selected_evaluation,
        available_capital=300000.0,
        evaluated_at=decision.completed_at,
    )

    planning = execute_selected_market_p6_planning(
        bridge_result_id=(
            f"task916-p6-bridge-"
            f"{normalized_market.lower()}"
        ),
        decision=decision,
        selected_cycle=selected_cycle,
        certified_p6_input_bundle=bundle,
        evaluated_at=decision.completed_at,
        maximum_candidate_age_seconds=180.0,
    )

    if planning.status != "READY":
        raise AssertionError(
            "Task916 P6 planning not READY: "
            f"{planning}"
        )

    context = lifecycle_context_store.recover(
        selected_prediction.prediction_id
    )

    if context is None:
        raise AssertionError(
            "Task916 selected lifecycle context missing"
        )

    planning_result = planning.planning_result

    if planning_result is None:
        raise AssertionError(
            "Task916 READY planning missing result"
        )

    selected_candidate = (
        planning_result
        .option_contract_selection_result
        .selected_contract
    )

    selected_contract = selected_candidate.contract

    option_symbol = selected_contract.trading_symbol

    derivative_exchange = (
        "NFO"
        if normalized_market == "NIFTY"
        else "BFO"
    )

    selected_price = (
        seed.nifty_price
        if normalized_market == "NIFTY"
        else seed.sensex_price
    )

    entry_observation = make_observation(
        observation_id=seed.entry_observation_id,
        observed_at=decision.completed_at,
        received_at=decision.completed_at,
        underlying_symbol=normalized_market,
        market=normalized_market,
        exchange=derivative_exchange,
        option_symbol=option_symbol,
        underlying_last_price=selected_price,
    )

    if not (
        context.window_starts_at
        <= entry_observation.observed_at
        <= context.entry_window_ends_at
    ):
        raise AssertionError(
            "Task916 entry observation outside "
            "prediction lifecycle window"
        )

    p7_root = tmp_path / "p7"
    p7_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    portfolio_service, trade_service = _services(
        p7_root
    )

    return Task916RealRuntimeHarness(
        seed=seed,
        decision=decision,
        predictions=predictions,
        selected_prediction=selected_prediction,
        selected_cycle=selected_cycle,
        selected_evaluation=selected_evaluation,
        selected_bridge=selected_bridge,
        selected_p6_bundle=bundle,
        selected_planning=planning,
        entry_observation=entry_observation,
        prediction_ledger=prediction_ledger,
        lifecycle_context_store=lifecycle_context_store,
        binding_store=(
            Task9PredictionPaperTradeBindingStore(
                tmp_path / "task916-bindings.json"
            )
        ),
        observation_store=(
            Task9PredictionObservationWindowStore(
                tmp_path / "task916-observations.json"
            )
        ),
        portfolio_service=portfolio_service,
        trade_service=trade_service,
    )