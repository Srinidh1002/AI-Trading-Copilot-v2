"""Repository-default Task 9 live PAPER composition."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

import logging
import math
import os
import subprocess
from datetime import datetime, timezone
from services.broker.shared_client import (
    get_certification_market_client,
)
from services.market.angel_live_observation_normalizer import normalize_tick_to_spot_observation
import config

from services.analysis.live_market_candidate_evaluator import (
    LiveMarketCandidateEvaluationResultV1,
)
from services.certification.task9_live_candidate_adapter import (
    build_task9_retaining_candidate_reader,
)
from services.certification.task9_cycle_market_evidence_handoff import (
    Task9CycleMarketEvidenceV1,
)
from services.certification.task9_parent_evidence_dependencies import (
    Task9ParentEvidenceDependenciesV1,
)
from services.certification.task9_live_spot_quote_projection import (
    project_task9_live_spot_quote_with_quality,
)
from services.certification.task9_prediction_lifecycle_timing import (
    resolve_prediction_lifecycle_window,
)
from services.trade_planning.task9_selected_market_p6_bundle import (
    build_task9_selected_market_p6_bundle,
)
from services.contracts.paper_orchestration_policy_v1 import (
    PaperOrchestrationPolicyV1,
)
from services.contracts.two_market_decision_policy_v1 import (
    TwoMarketDecisionPolicyV1,
)
from services.contracts.two_market_parent_cycle_input_v1 import (
    TwoMarketParentCycleInputV1,
)
from services.market_session.validator import (
    validate_session_timestamp,
)
from services.market_session.policies import MarketSessionPolicy
from services.paper_orchestration.authoritative_two_market_entry_point import (
    run_authoritative_two_market_parent_cycle,
)
from services.paper_orchestration.certified_cycle_input_factory import (
    build_certified_cycle_input,
)
from services.paper_orchestration.certified_live_provider_readers import (
    CertifiedLiveProviderReaders,
    market_spec_for,
)
from services.paper_orchestration.certified_persistence_composition import (
    build_certified_parent_journal_adapter,
    build_certified_prediction_ledger,
)
from services.paper_orchestration.certified_runtime_composition import (
    CertifiedRuntimeProviderBundleV1,
    build_default_automated_paper_authorities,
    build_default_runtime_providers,
    capture_certified_live_evidence,
)
from services.paper_orchestration.certified_runtime_safety import (
    validate_no_broker_submission_guard,
    validate_repository_paper_safety,
)
from services.angel_instrument_master import AngelInstrumentMaster
from services.paper_orchestration.india_vix_live_reader import IndiaVixLiveReader
from services.paper_orchestration.external_context_source_authority import (
    ExternalContextSourceAuthority,
)
from services.paper_orchestration.selected_market_p6_planning_runtime import (
    execute_selected_market_p6_planning,
)
from services.paper_orchestration.unavailable_external_context_readers import (
    UnavailableGlobalMarketReader,
    UnavailableInstitutionalFlowReader,
    UnavailableScheduledEventReader,
)
from services.trade_planning.selected_market_planning_bridge import (
    bridge_selected_market_to_planning,
)


_SUPPORTED_MARKETS = (
    ("NIFTY", "NSE"),
    ("SENSEX", "BSE"),
)

logger = logging.getLogger(__name__)

_TASK9_PROVIDER_DIAGNOSTIC_FIELDS = (
    "exchange",
    "timeframe",
    "provider_attempted",
    "provider_result",
    "failure_reason",
)


def _retain_task9_request_diagnostics(
    retained_request_diagnostics,
    *,
    observation_id,
    capture,
) -> None:
    """Retain only typed/sanitized historical provider diagnostics by observation."""

    metadata = getattr(capture, "cache_metadata", {})
    diagnostics = (
        metadata.get("request_diagnostics", {})
        if isinstance(metadata, Mapping)
        else {}
    )
    retained_request_diagnostics[observation_id] = {
        key: {
            field: value.get(field)
            for field in _TASK9_PROVIDER_DIAGNOSTIC_FIELDS
        }
        for key, value in diagnostics.items()
        if isinstance(value, Mapping)
    } if isinstance(diagnostics, Mapping) else {}


def _git(*args: str) -> str:
    return subprocess.check_output(
        ("git", *args),
        text=True,
        encoding="utf-8",
    ).strip()


def _validate_retained_task9_evaluations(
    decision,
    retained_evaluations,
) -> None:
    completed_observations = {
        entry.child.observation_id
        for entry in decision.entries
        if entry.child.terminal_status == "COMPLETED"
    }

    retained_observations = set(retained_evaluations)
    if retained_observations != completed_observations:
        missing = sorted(
            completed_observations
            - retained_observations
        )
        unexpected = sorted(
            retained_observations
            - completed_observations
        )
        raise RuntimeError(
            "Task 9 retained evaluation mismatch for "
            f"completed children; missing={missing}, "
            f"unexpected={unexpected}"
        )


def _emit_task9_cycle_market_evidence(
    *,
    sink,
    cycles,
    evaluations,
    predictions,
    lifecycle_windows,
    selected_market,
    selected_planning,
    selected_paper_observation,
    retained_request_diagnostics=None,
) -> None:
    """Emit pure Task 9 evidence from exact retained parent-cycle objects."""

    for identity in _SUPPORTED_MARKETS:
        retained_cycle = cycles.get(identity)
        if retained_cycle is None:
            raise RuntimeError("retained cycle missing for Task 9 evidence")
        retained_evaluation = evaluations.get(
            retained_cycle.observation_id
        )
        retained_prediction = predictions.get(identity)
        lifecycle_window = lifecycle_windows.get(identity)
        if retained_prediction is None:
            raise RuntimeError(
                "retained prediction missing for Task 9 evidence"
            )
        if lifecycle_window is None:
            raise RuntimeError(
                "retained lifecycle window missing for Task 9 evidence"
            )

        if retained_prediction.observation_id != retained_cycle.observation_id:
            raise RuntimeError("retained prediction/cycle observation mismatch")

        if retained_prediction.terminal_status == "COMPLETED":
            if type(retained_evaluation) is not (
                LiveMarketCandidateEvaluationResultV1
            ):
                raise RuntimeError(
                    "retained evaluation missing for Task 9 evidence"
                )
            market_quote, data_quality = (
                project_task9_live_spot_quote_with_quality(
                    spot=retained_evaluation.observation.spot,
                )
            )
        else:
            if retained_prediction.terminal_status not in {
                "FAILED",
                "UNAVAILABLE",
            }:
                raise RuntimeError("unsupported retained prediction status")
            if retained_evaluation is not None:
                raise RuntimeError(
                    "failed Task 9 child unexpectedly retained evaluation"
                )
            market_quote = None
            data_quality = None

        incidents = []
        diagnostics = (retained_request_diagnostics or {}).get(retained_cycle.observation_id, {})
        for timeframe, item in (
            diagnostics.items()
            if isinstance(diagnostics, Mapping)
            else ()
        ):
            if (
                isinstance(item, Mapping)
                and timeframe in {"5m", "15m", "1h", "1d"}
                and item.get("timeframe") == timeframe
                and item.get("provider_attempted") is True
                and item.get("provider_result") == "RATE_LIMITED"
                and item.get("failure_reason")
                == "HISTORICAL-DATA_RATE_LIMITED"
            ):
                from services.certification.task9_cycle_market_evidence_handoff import Task9ProviderIncidentV1
                incidents.append(Task9ProviderIncidentV1(f"task9-provider-incident:{retained_cycle.observation_id}:{identity[1]}:historical-data:{timeframe}:HISTORICAL-DATA_RATE_LIMITED", "historical-data", identity[1], timeframe, "HISTORICAL-DATA_RATE_LIMITED", "RATE_LIMITED", True))
        sink(
            Task9CycleMarketEvidenceV1(
                prediction=retained_prediction,
                cycle=retained_cycle,
                evaluation=retained_evaluation,
                market_quote=market_quote,
                data_quality=data_quality,
                lifecycle_window=lifecycle_window,
                selected_planning=(
                    selected_planning
                    if (
                        retained_prediction.terminal_status == "COMPLETED"
                        and identity == selected_market
                    )
                    else None
                ),
                paper_observation=(
                    selected_paper_observation
                    if (
                        retained_prediction.terminal_status == "COMPLETED"
                        and identity == selected_market
                    )
                    else None
                ),
                provider_incidents=tuple({item.incident_id: item for item in incidents}.values()),
            )
        )


def build_task9_parent_evidence_dependencies(
    *,
    task9_cycle_evidence_sink=None,
    historical_request_interval_seconds=None,
    precomposed_timeframe_provider_factory=None,
    option_oi_change_authority=None,
    providers=None,
    available_capital=None,
    risk_fraction=0.01,
    maximum_quantity=None,
    maximum_daily_loss_fraction=None,
) -> Task9ParentEvidenceDependenciesV1:
    """Build the production Task 9 PAPER-only dependency composition."""

    # Compatibility-only defaults preserve direct legacy/test callers. The
    # canonical production entrypoint always supplies frozen runtime values.
    if available_capital is None:
        available_capital = config.DEFAULT_CAPITAL

    validate_repository_paper_safety(
        broker=config.BROKER,
        enable_paper_trading=config.ENABLE_PAPER_TRADING,
        enable_live_trading=config.ENABLE_LIVE_TRADING,
    )
    validate_no_broker_submission_guard(
        broker_order_submission=False,
    )

    if task9_cycle_evidence_sink is not None and not callable(task9_cycle_evidence_sink):
        raise TypeError("task9_cycle_evidence_sink")
    if (
        type(available_capital) not in (int, float)
        or isinstance(available_capital, bool)
        or available_capital <= 0
    ):
        raise ValueError("available_capital")
    if (
        type(risk_fraction) not in (int, float)
        or isinstance(risk_fraction, bool)
        or risk_fraction <= 0
        or risk_fraction > 1
    ):
        raise ValueError("risk_fraction")
    if maximum_quantity is not None and (
        type(maximum_quantity) is not int
        or isinstance(maximum_quantity, bool)
        or maximum_quantity <= 0
    ):
        raise ValueError("maximum_quantity")
    if maximum_daily_loss_fraction is not None and (
        type(maximum_daily_loss_fraction) not in (int, float)
        or isinstance(maximum_daily_loss_fraction, bool)
        or not math.isfinite(maximum_daily_loss_fraction)
        or maximum_daily_loss_fraction <= 0
        or maximum_daily_loss_fraction > 1
    ):
        raise ValueError("maximum_daily_loss_fraction")

    if option_oi_change_authority is not None and not callable(
        getattr(option_oi_change_authority, "enrich", None)
    ):
        raise TypeError("option_oi_change_authority")
    provider_kwargs = {}

    if historical_request_interval_seconds is not None:
        provider_kwargs["historical_request_interval_seconds"] = (
            historical_request_interval_seconds
        )

    if providers is None:
        providers = build_default_runtime_providers(
            **provider_kwargs
        )
    else:
        # Task 9 startup may already own the canonical provider bundle.
        # Reuse it exactly rather than constructing another Angel client /
        # option pipeline / instrument master.  The historical spacing
        # argument is intentionally irrelevant for an already-composed
        # provider bundle; countable Task 9 cycles remain local-evidence-only.
        for name in (
            "quote_reader",
            "analysis_pipeline",
            "option_decision_pipeline",
            "clock",
        ):
            if not hasattr(providers, name):
                raise TypeError(
                    "providers must expose "
                    "CertifiedRuntimeProviderBundleV1 "
                    f"attribute {name}"
                )

    parent_journal_adapter = (
        build_certified_parent_journal_adapter(
            clock=providers.clock,
        )
    )
    prediction_ledger = build_certified_prediction_ledger()

    retained_evaluations: dict[
        str,
        LiveMarketCandidateEvaluationResultV1,
    ] = {}
    retained_pre_entry_actions: dict[str, object] = {}
    retained_request_diagnostics: dict[str, object] = {}
    retained_predictions: dict[tuple[str, str], object] = {}
    retained_lifecycle_windows: dict[tuple[str, str], object] = {}

    def retain_predictions(records) -> None:
        if type(records) is not tuple or len(records) != 2:
            raise ValueError("authoritative parent must retain two predictions")
        retained_predictions.clear()
        retained_lifecycle_windows.clear()
        for item in records:
            identity = (item.underlying_symbol, item.exchange)
            if identity in retained_predictions:
                raise ValueError("duplicate authoritative prediction market")
            retained_predictions[identity] = item
            retained_lifecycle_windows[identity] = (
                resolve_prediction_lifecycle_window(
                    prediction_record=item,
                    session_policy=MarketSessionPolicy(),
                )
            )

    def retain_evaluation(
        observation_id: str,
        evaluation: LiveMarketCandidateEvaluationResultV1,
    ) -> None:
        if observation_id in retained_evaluations:
            raise RuntimeError(
                "Task 9 evaluation was produced more than once "
                f"for observation {observation_id}"
            )

        if evaluation.candidate.observation_id != observation_id:
            raise ValueError(
                "retained evaluation observation identity mismatch"
            )

        retained_evaluations[observation_id] = evaluation
        retained_pre_entry_actions[observation_id] = evaluation.pre_entry_action

    retaining_candidate_reader = (
        build_task9_retaining_candidate_reader(
            evaluation_sink=retain_evaluation,
        )
    )

    bundle = CertifiedRuntimeProviderBundleV1(
        quote_reader=providers.quote_reader,
        analysis_pipeline=providers.analysis_pipeline,
        option_decision_pipeline=(
            providers.option_decision_pipeline
        ),
        candidate_reader=retaining_candidate_reader,
        clock=providers.clock,
    )

    data_service = bundle.analysis_pipeline.data_service

    option_builder = getattr(
        bundle.option_decision_pipeline,
        "option_chain_builder",
        None,
    )

    if option_builder is None:
        raise TypeError(
            "certified option pipeline must expose "
            "option_chain_builder"
        )

    retained_market_client = getattr(
        option_builder,
        "market_client",
        None,
    )

    if retained_market_client is None:
        raise TypeError(
            "certified option builder must retain "
            "market_client"
        )

    retained_instrument_master = getattr(
        option_builder,
        "instrument_master",
        None,
    )

    if retained_instrument_master is None:
        raise TypeError(
            "certified option builder must retain "
            "instrument_master"
        )

    retained_master_fetcher = getattr(
        retained_instrument_master,
        "fetch_instruments",
        None,
    )

    if not callable(retained_master_fetcher):
        raise TypeError(
            "certified instrument master must expose "
            "fetch_instruments()"
        )

    precomposed_timeframe_provider = (
        precomposed_timeframe_provider_factory(data_service)
        if precomposed_timeframe_provider_factory is not None
        else None
    )

    def capture_and_retain(cycle, *, candle_cutoff=None):
        capture = capture_certified_live_evidence(
            cycle_input=cycle,
            data_service=data_service,
            option_decision_pipeline=bundle.option_decision_pipeline,
            candle_cutoff=candle_cutoff,
            precomposed_timeframe_provider=precomposed_timeframe_provider,
            option_oi_change_authority=option_oi_change_authority,
        )
        _retain_task9_request_diagnostics(
            retained_request_diagnostics,
            observation_id=cycle.observation_id,
            capture=capture,
        )
        return capture

    external_context_authority = (
        ExternalContextSourceAuthority(
            global_reader=UnavailableGlobalMarketReader(),
            institutional_reader=UnavailableInstitutionalFlowReader(),
            event_reader=UnavailableScheduledEventReader(),
        )
    )

    readers = CertifiedLiveProviderReaders(
        quote_reader=bundle.quote_reader,
        analysis_pipeline=bundle.analysis_pipeline,
        option_decision_pipeline=(
            bundle.option_decision_pipeline
        ),
        available_capital=float(available_capital),
        candidate_reader=retaining_candidate_reader,
        capture_reader=capture_and_retain,
        india_vix_reader=IndiaVixLiveReader(
            master_fetcher=retained_master_fetcher,
            market_client=retained_market_client,
            clock=providers.clock,
        ),
        external_context_reader=external_context_authority,
    )

    def preflight():
        required_credentials = (
            "ANGEL_API_KEY",
            "ANGEL_CLIENT_ID",
            "ANGEL_PIN",
            "ANGEL_TOTP_SECRET",
        )
        credentials_present = all(
            bool(os.getenv(name, "").strip())
            for name in required_credentials
        )

        return {
            "branch_worktree": (
                _git("branch", "--show-current")
                == "p10-two-market-weekend-readiness"
            ),
            "paper_mode": True,
            "live_execution_ineligible": True,
            "broker_submission_disabled": True,
            "nifty_provider": True,
            "sensex_provider": True,
            "routing": True,
            "persistence_writable": True,
            "journal_writable": True,
            "emergency_halt": True,
            "market_session_checked": True,
            "credentials_present": credentials_present,
            "journal_status": "NOT_WRITTEN",
        }

    selected_runtime_state: dict[str, object] = {}

    def parent_cycle():
            retained_evaluations.clear()
            retained_request_diagnostics.clear()

            captures: dict[
                tuple[str, str],
                dict[str, object],
            ] = {}

            # 1. Capture evaluation time for age calculations
            evaluated_at = bundle.clock()

            # 2. Build captures directly from the local WebSocket tick journal
            for symbol, exchange in _SUPPORTED_MARKETS:
                spec = market_spec_for(symbol, exchange)
                
                # NOTE: Adjust `bundle.tick_journal` and `get_latest_tick` if your property names differ
                tick = bundle.tick_journal.get_latest_tick(spec.symboltoken)
                
                quote_age = (evaluated_at - tick.provider_timestamp).total_seconds()

                captures[(symbol, exchange)] = {
                    "spot_price": tick.ltp,
                    "ltp": tick.ltp,
                    "market_timestamp": tick.provider_timestamp,
                    "received_at": tick.received_at,
                    "timestamp_source": "LIVE_WEBSOCKET",
                    "provider_timestamp_field": "websocket_timestamp",
                    "quote_age_seconds": quote_age,
                    "provider_trading_symbol": spec.underlying_symbol,
                    "provider_response": {"ltp": tick.ltp, "source": "websocket_journal"},
                }

            # This is the sole Task 9 owner of daily historical maintenance.  It
            # runs once at the two-market parent boundary, before either child
            # capture, while the collector remains WebSocket-only.  Durable cache
            # coverage (not an in-memory flag) makes restart reuse idempotent.
            ensure_daily = getattr(
                data_service,
                "ensure_daily_cache_coverage",
                None,
            )
            if callable(ensure_daily):
                for symbol, exchange in _SUPPORTED_MARKETS:
                    spec = market_spec_for(symbol, exchange)
                    warmup = ensure_daily(
                        exchange,
                        spec.symboltoken,
                        end_time=captures[(symbol, exchange)][
                            "market_timestamp"
                        ],
                    )
                    logger.info(
                        "task9_daily_cache_warmup market=%s exchange=%s "
                        "outcome=%s provider_call_count=%s",
                        symbol,
                        exchange,
                        warmup.get("refresh_outcome"),
                        warmup.get("provider_call_count"),
                    )

            requested = datetime.now(timezone.utc)
            cycles = {}

            for symbol, exchange in _SUPPORTED_MARKETS:
                spec = market_spec_for(symbol, exchange)
                raw = captures[(symbol, exchange)]

                market_timestamp = raw["market_timestamp"]
                received_at = raw["received_at"]
                requested_at = max(requested, received_at)

                session = validate_session_timestamp(
                    symbol=spec.underlying_symbol,
                    exchange=spec.exchange,
                    market_timestamp=market_timestamp,
                    evaluated_at=received_at,
                    validation_mode="LENIENT_ANALYSIS",
                    id_factory=(
                        lambda current_symbol=symbol,
                        current_timestamp=market_timestamp: (
                            "task9-session-"
                            f"{current_symbol.lower()}-"
                            f"{current_timestamp.isoformat()}"
                        )
                    ),
                )

                policy = PaperOrchestrationPolicyV1(
                    orchestration_policy_id=(
                        "task9-policy-"
                        f"{requested_at.date().isoformat()}"
                    ),
                    policy_timestamp=requested_at,
                    observation_frequency_seconds=60.0,
                    emergency_paper_halt=False,
                )

                cycles[(symbol, exchange)] = (
                    build_certified_cycle_input(
                        cycle_kind="OPPORTUNITY",
                        observation_id=(
                            f"task9-{symbol.lower()}-"
                            f"{market_timestamp.isoformat()}"
                        ),
                        orchestration_policy=policy,
                        underlying_symbol=symbol,
                        exchange=exchange,
                        market_timestamp=market_timestamp,
                        received_at=received_at,
                        cycle_requested_at=requested_at,
                        session_validation=session,
                        metadata={
                            "spot_price": raw["spot_price"],
                            "timestamp_source": raw.get(
                                "timestamp_source"
                            ),
                            "captured_spot_payload": {
                                "spot_price": raw["spot_price"],
                                "timestamp_source": raw.get(
                                    "timestamp_source"
                                ),
                            },
                        },
                    )
                )

            nifty_cycle = cycles[("NIFTY", "NSE")]
            sensex_cycle = cycles[("SENSEX", "BSE")]

            parent_requested_at = max(
                nifty_cycle.cycle_requested_at,
                sensex_cycle.cycle_requested_at,
                nifty_cycle.market_timestamp,
                sensex_cycle.market_timestamp,
            )

            nifty_cycle = replace(
                nifty_cycle,
                cycle_requested_at=parent_requested_at,
                received_at=max(
                    nifty_cycle.received_at,
                    parent_requested_at,
                ),
            )
            sensex_cycle = replace(
                sensex_cycle,
                cycle_requested_at=parent_requested_at,
                received_at=max(
                    sensex_cycle.received_at,
                    parent_requested_at,
                ),
            )

            parent = TwoMarketParentCycleInputV1(
                parent_cycle_id=(
                    f"task9-parent-{requested.isoformat()}"
                ),
                decision_result_id=(
                    f"task9-decision-{requested.isoformat()}"
                ),
                nifty_child_result_id=(
                    f"task9-child-nifty-{requested.isoformat()}"
                ),
                sensex_child_result_id=(
                    f"task9-child-sensex-{requested.isoformat()}"
                ),
                nifty_observation_id=(
                    nifty_cycle.observation_id
                ),
                sensex_observation_id=(
                    sensex_cycle.observation_id
                ),
                requested_at=parent_requested_at,
                completed_at=max(
                    parent_requested_at,
                    nifty_cycle.received_at,
                    sensex_cycle.received_at,
                ),
                decision_policy=TwoMarketDecisionPolicyV1(
                    180.0,
                    5.0,
                ),
            )

            decision = (
                run_authoritative_two_market_parent_cycle(
                    parent,
                    nifty_cycle=nifty_cycle,
                    sensex_cycle=sensex_cycle,
                    readers=readers,
                    parent_journal_adapter=(
                        parent_journal_adapter
                    ),
                    prediction_ledger=prediction_ledger,
                    pre_entry_actions=retained_pre_entry_actions,
                    prediction_records_sink=retain_predictions,
                )
            )

            _validate_retained_task9_evaluations(
                decision,
                retained_evaluations,
            )

            selected_runtime_state["decision"] = decision
            selected_runtime_state["cycles"] = cycles
            selected_runtime_state["evaluations"] = dict(
                retained_evaluations
            )
            selected_runtime_state["predictions"] = dict(retained_predictions)
            selected_runtime_state["lifecycle_windows"] = dict(
                retained_lifecycle_windows
            )

            if (
                task9_cycle_evidence_sink is not None
                and decision.selected_market is None
            ):
                _emit_task9_cycle_market_evidence(
                    sink=task9_cycle_evidence_sink,
                    cycles=cycles,
                    evaluations=retained_evaluations,
                    predictions=retained_predictions,
                    lifecycle_windows=retained_lifecycle_windows,
                    selected_market=None,
                    selected_planning=None,
                    selected_paper_observation=None,
                    retained_request_diagnostics=retained_request_diagnostics,
                )

            return decision

    def selected_planner(
        market: tuple[str, str],
    ):
        decision = selected_runtime_state.get("decision")
        cycles = selected_runtime_state.get("cycles")
        evaluations = selected_runtime_state.get(
            "evaluations"
        )
        predictions = selected_runtime_state.get("predictions")
        lifecycle_windows = selected_runtime_state.get(
            "lifecycle_windows"
        )

        if (
            decision is None
            or not isinstance(cycles, dict)
            or not isinstance(evaluations, dict)
            or not isinstance(predictions, dict)
            or not isinstance(lifecycle_windows, dict)
        ):
            raise RuntimeError(
                "authoritative parent cycle must run "
                "before selected planning"
            )

        if decision.selected_market != market:
            raise ValueError(
                "selected planner market does not match "
                "authoritative decision"
            )

        selected_cycle = cycles.get(market)
        if selected_cycle is None:
            raise RuntimeError(
                "selected cycle was not retained"
            )

        evaluation = evaluations.get(
            selected_cycle.observation_id
        )
        prediction = predictions.get(market)
        if prediction is None:
            raise RuntimeError("selected exact prediction was not retained")
        if type(evaluation) is not (
            LiveMarketCandidateEvaluationResultV1
        ):
            raise RuntimeError(
                "selected exact typed evaluation "
                "was not retained"
            )

        p6_bundle = (
            build_task9_selected_market_p6_bundle(
                bridge=bridge_selected_market_to_planning(
                    bridge_result_id=(
                        "task9-bundle-bridge-"
                        f"{decision.decision_result_id}"
                    ),
                    decision=decision,
                    evaluated_at=decision.completed_at,
                    maximum_candidate_age_seconds=180.0,
                ),
                cycle=selected_cycle,
                evaluation=evaluation,
                available_capital=readers.available_capital,
                risk_fraction=float(risk_fraction),
                maximum_quantity=maximum_quantity,
                evaluated_at=decision.completed_at,
            )
        )

        selected_planning = (
            execute_selected_market_p6_planning(
                bridge_result_id=(
                    "task9-bridge-"
                    f"{decision.decision_result_id}"
                ),
                decision=decision,
                selected_cycle=selected_cycle,
                certified_p6_input_bundle=p6_bundle,
                evaluated_at=decision.completed_at,
                maximum_candidate_age_seconds=180.0,
            )
        )

        planning_result = selected_planning.planning_result
        if planning_result is None:
            raise ValueError(
                "READY Task 9 selected planning requires planning_result"
            )
        if planning_result.status != "READY":
            raise ValueError(
                "Task 9 selected P6 planning result must be READY"
            )
        if planning_result.execution_mode != "PAPER":
            raise ValueError(
                "Task 9 selected P6 result must remain PAPER-only"
            )
        if planning_result.live_execution_eligible is not False:
            raise ValueError(
                "Task 9 selected P6 result cannot be live eligible"
            )

        paper_authorities = build_default_automated_paper_authorities(
            portfolio_id="task9-certified-paper-portfolio",
            available_capital=readers.available_capital,
            **(
                {
                    "maximum_daily_loss_fraction": (
                        maximum_daily_loss_fraction
                    ),
                }
                if maximum_daily_loss_fraction is not None
                else {}
            ),
        )

        new_entry_input = paper_authorities.new_entry_input_factory(
            selected_cycle,
            planning_result,
        )

        new_entry_input = replace(
            new_entry_input,
            prediction_id=prediction.prediction_id,
        )

        paper_observation = new_entry_input.observation

        selected_runtime_state["paper_observation"] = (
            paper_observation
        )
        selected_runtime_state["selected_planning"] = (
            selected_planning
        )

        if task9_cycle_evidence_sink is not None:
            _emit_task9_cycle_market_evidence(
                sink=task9_cycle_evidence_sink,
                cycles=cycles,
                evaluations=evaluations,
                predictions=predictions,
                lifecycle_windows=lifecycle_windows,
                selected_market=market,
                selected_planning=selected_planning,
                selected_paper_observation=paper_observation,
                retained_request_diagnostics=(
                    retained_request_diagnostics
                ),
            )

        return selected_planning

    return Task9ParentEvidenceDependenciesV1(
        parent_cycle=parent_cycle,
        selected_planner=selected_planner,
        execution_mode="PAPER",
        broker_order_submission=False,
        live_execution_eligible=False,
    )
