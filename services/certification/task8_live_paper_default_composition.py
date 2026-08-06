"""Repository-default Task 8 live PAPER composition."""
from __future__ import annotations

from dataclasses import replace

import os
import subprocess
from datetime import datetime, timezone

import config

from services.analysis.live_market_candidate_evaluator import (
    LiveMarketCandidateEvaluationResultV1,
)
from services.certification.task8_live_candidate_adapter import (
    build_task8_retaining_candidate_reader,
)
from services.certification.task8_live_paper_canary import (
    Task8CanaryDependenciesV1,
)
from services.certification.task8_selected_market_p6_bundle import (
    build_task8_selected_market_p6_bundle,
)
from services.certification.task8_selected_market_lifecycle_runtime import (
    execute_task8_selected_market_lifecycle,
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
    build_default_runtime_providers,
    capture_certified_live_evidence,
)
from services.paper_orchestration.certified_runtime_safety import (
    validate_no_broker_submission_guard,
    validate_repository_paper_safety,
)
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


def _git(*args: str) -> str:
    return subprocess.check_output(
        ("git", *args),
        text=True,
        encoding="utf-8",
    ).strip()


def build_task8_dependencies() -> Task8CanaryDependenciesV1:
    """Build the production Task 8 PAPER-only dependency composition."""

    validate_repository_paper_safety(
        broker=config.BROKER,
        enable_paper_trading=config.ENABLE_PAPER_TRADING,
        enable_live_trading=config.ENABLE_LIVE_TRADING,
    )
    validate_no_broker_submission_guard(
        broker_order_submission=False,
    )

    providers = build_default_runtime_providers()

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

    def retain_evaluation(
        observation_id: str,
        evaluation: LiveMarketCandidateEvaluationResultV1,
    ) -> None:
        if observation_id in retained_evaluations:
            raise RuntimeError(
                "Task 8 evaluation was produced more than once "
                f"for observation {observation_id}"
            )

        if evaluation.candidate.observation_id != observation_id:
            raise ValueError(
                "retained evaluation observation identity mismatch"
            )

        retained_evaluations[observation_id] = evaluation

    retaining_candidate_reader = (
        build_task8_retaining_candidate_reader(
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
        available_capital=10_000.0,
        candidate_reader=retaining_candidate_reader,
        capture_reader=(
            lambda cycle, *, candle_cutoff=None:
            capture_certified_live_evidence(
                cycle_input=cycle,
                data_service=data_service,
                option_decision_pipeline=(
                    bundle.option_decision_pipeline
                ),
                candle_cutoff=candle_cutoff,
            )
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

        captures: dict[
            tuple[str, str],
            dict[str, object],
        ] = {}

        for symbol, exchange in _SUPPORTED_MARKETS:
            spec = market_spec_for(symbol, exchange)
            captures[(symbol, exchange)] = (
                bundle.quote_reader(
                    spec.exchange,
                    spec.symboltoken,
                    spec.underlying_symbol,
                )
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
                        "task8-session-"
                        f"{current_symbol.lower()}-"
                        f"{current_timestamp.isoformat()}"
                    )
                ),
            )

            policy = PaperOrchestrationPolicyV1(
                orchestration_policy_id=(
                    "task8-policy-"
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
                        f"task8-{symbol.lower()}-"
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
                f"task8-parent-{requested.isoformat()}"
            ),
            decision_result_id=(
                f"task8-decision-{requested.isoformat()}"
            ),
            nifty_child_result_id=(
                f"task8-child-nifty-{requested.isoformat()}"
            ),
            sensex_child_result_id=(
                f"task8-child-sensex-{requested.isoformat()}"
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
            )
        )

        expected_observations = {
            nifty_cycle.observation_id,
            sensex_cycle.observation_id,
        }

        if set(retained_evaluations) != expected_observations:
            missing = sorted(
                expected_observations
                - set(retained_evaluations)
            )
            unexpected = sorted(
                set(retained_evaluations)
                - expected_observations
            )
            raise RuntimeError(
                "Task 8 did not retain exactly one evaluation "
                f"per child; missing={missing}, "
                f"unexpected={unexpected}"
            )

        selected_runtime_state["decision"] = decision
        selected_runtime_state["cycles"] = cycles
        selected_runtime_state["evaluations"] = dict(
            retained_evaluations
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

        if (
            decision is None
            or not isinstance(cycles, dict)
            or not isinstance(evaluations, dict)
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
        if type(evaluation) is not (
            LiveMarketCandidateEvaluationResultV1
        ):
            raise RuntimeError(
                "selected exact typed evaluation "
                "was not retained"
            )

        p6_bundle = (
            build_task8_selected_market_p6_bundle(
                bridge=bridge_selected_market_to_planning(
                    bridge_result_id=(
                        "task8-bundle-bridge-"
                        f"{decision.decision_result_id}"
                    ),
                    decision=decision,
                    evaluated_at=decision.completed_at,
                    maximum_candidate_age_seconds=180.0,
                ),
                cycle=selected_cycle,
                evaluation=evaluation,
                available_capital=readers.available_capital,
                evaluated_at=decision.completed_at,
            )
        )

        selected_planning = (
            execute_selected_market_p6_planning(
                bridge_result_id=(
                    "task8-bridge-"
                    f"{decision.decision_result_id}"
                ),
                decision=decision,
                selected_cycle=selected_cycle,
                certified_p6_input_bundle=p6_bundle,
                evaluated_at=decision.completed_at,
                maximum_candidate_age_seconds=180.0,
            )
        )

        return execute_task8_selected_market_lifecycle(
            selected_cycle=selected_cycle,
            selected_planning=selected_planning,
            available_capital=readers.available_capital,
            evaluated_at=decision.completed_at,
            persistence_root=(
                "data/paper_trading/"
                "certified_runtime/task8"
            ),
            portfolio_id=(
                "task8-certified-paper-portfolio"
            ),
        )

    return Task8CanaryDependenciesV1(
        branch=_git("branch", "--show-current"),
        commit=_git("rev-parse", "--short", "HEAD"),
        preflight=preflight,
        parent_cycle=parent_cycle,
        selected_planner=selected_planner,
        monitoring=lambda: None,
        clock=lambda: datetime.now(timezone.utc),
        id_factory=lambda: (
            "task8-live-"
            + datetime.now(timezone.utc).strftime(
                "%Y%m%dT%H%M%S%fZ"
            )
        ),
    )
