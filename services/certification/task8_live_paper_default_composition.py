"""Repository-default Task 8 factory.

The live runtime is assembled through the existing certified composition.  It
also makes the candidate seam explicit: a deployment must supply the typed
evidence producer before a live read can be certified.  This is safer than
converting legacy dictionaries into apparently valid candidate evidence.
"""
from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone

import config

from services.certification.task8_live_paper_canary import Task8CanaryDependenciesV1
from services.certification.task8_live_candidate_adapter import adapt_task8_live_candidate
from services.paper_orchestration.certified_runtime_composition import (
    CertifiedRuntimeProviderBundleV1,
    build_default_runtime_providers,
    capture_certified_live_evidence,
)
from services.paper_orchestration.certified_live_provider_readers import CertifiedLiveProviderReaders, market_spec_for
from services.paper_orchestration.certified_live_read_authorities import CertifiedLiveDataResultV1
from services.paper_orchestration.certified_cycle_input_factory import build_certified_cycle_input
from services.contracts.paper_orchestration_policy_v1 import PaperOrchestrationPolicyV1
from services.contracts.two_market_decision_policy_v1 import TwoMarketDecisionPolicyV1
from services.contracts.two_market_parent_cycle_input_v1 import TwoMarketParentCycleInputV1
from services.market_session.validator import validate_session_timestamp
from services.paper_orchestration.certified_two_market_parent_runtime import run_certified_two_market_parent_runtime
from services.paper_orchestration.certified_runtime_safety import (
    validate_no_broker_submission_guard,
    validate_repository_paper_safety,
)


def _git(*args: str) -> str:
    return subprocess.check_output(("git", *args), text=True, encoding="utf-8").strip()


def build_task8_dependencies() -> Task8CanaryDependenciesV1:
    """Return the default dependency factory without exposing credentials.

    The current repository's live analysis pipeline returns legacy analytical
    mappings, not the required exact candidate-composition evidence.  Raising
    here deliberately yields CLI exit 2 rather than a false certification.
    """
    validate_repository_paper_safety(broker=config.BROKER, enable_paper_trading=config.ENABLE_PAPER_TRADING, enable_live_trading=config.ENABLE_LIVE_TRADING)
    validate_no_broker_submission_guard(broker_order_submission=False)
    providers = build_default_runtime_providers()
    # This validates that the production adapter can be injected into the
    # existing live reader bundle; no provider call occurs at factory time.
    bundle = CertifiedRuntimeProviderBundleV1(
        quote_reader=providers.quote_reader,
        analysis_pipeline=providers.analysis_pipeline,
        option_decision_pipeline=providers.option_decision_pipeline,
        candidate_reader=adapt_task8_live_candidate,
        clock=providers.clock,
    )
    data_service = bundle.analysis_pipeline.data_service
    readers = CertifiedLiveProviderReaders(
        quote_reader=bundle.quote_reader, analysis_pipeline=bundle.analysis_pipeline,
        option_decision_pipeline=bundle.option_decision_pipeline, available_capital=10_000.0,
        candidate_reader=adapt_task8_live_candidate,
        capture_reader=lambda cycle, *, candle_cutoff=None: capture_certified_live_evidence(
            cycle_input=cycle, data_service=data_service,
            option_decision_pipeline=bundle.option_decision_pipeline,
            candle_cutoff=candle_cutoff,
        ),
    )

    def preflight():
        required = ("ANGEL_API_KEY", "ANGEL_CLIENT_ID", "ANGEL_PIN", "ANGEL_TOTP_SECRET")
        present = all(bool(os.getenv(name, "").strip()) for name in required)
        return {"branch_worktree": _git("branch", "--show-current") == "p10-two-market-weekend-readiness", "paper_mode": True, "live_execution_ineligible": True, "broker_submission_disabled": True, "nifty_provider": True, "sensex_provider": True, "routing": True, "persistence_writable": True, "journal_writable": True, "emergency_halt": True, "market_session_checked": True, "credentials_present": present, "journal_status": "NOT_WRITTEN"}

    def parent_cycle():
        # Capture each index LTP once before its child cycle is built.  The
        # certified reader reuses the captured value in DATA and does not re-read it.
        captures = {}
        for symbol, exchange in (("NIFTY", "NSE"), ("SENSEX", "BSE")):
            spec = market_spec_for(symbol, exchange)
            captures[(symbol, exchange)] = bundle.quote_reader(spec.exchange, spec.symboltoken, spec.underlying_symbol)
        requested = datetime.now(timezone.utc)
        cycles = {}
        for symbol, exchange in (("NIFTY", "NSE"), ("SENSEX", "BSE")):
            spec = market_spec_for(symbol, exchange); raw = captures[(symbol, exchange)]
            market_timestamp = raw["market_timestamp"]; received_at = raw["received_at"]
            requested_at = max(requested, received_at)
            session = validate_session_timestamp(symbol=spec.underlying_symbol, exchange=spec.exchange, market_timestamp=market_timestamp, evaluated_at=received_at, validation_mode="LENIENT_ANALYSIS", id_factory=lambda s=symbol: f"task8-session-{s.lower()}-{market_timestamp.isoformat()}")
            policy = PaperOrchestrationPolicyV1(orchestration_policy_id=f"task8-policy-{requested_at.date().isoformat()}", policy_timestamp=requested_at, observation_frequency_seconds=60.0, emergency_paper_halt=False)
            cycles[(symbol, exchange)] = build_certified_cycle_input(cycle_kind="OPPORTUNITY", observation_id=f"task8-{symbol.lower()}-{market_timestamp.isoformat()}", orchestration_policy=policy, underlying_symbol=symbol, exchange=exchange, market_timestamp=market_timestamp, received_at=received_at, cycle_requested_at=requested_at, session_validation=session, metadata={"spot_price": raw["spot_price"], "timestamp_source": raw.get("timestamp_source"), "captured_spot_payload":{"spot_price":raw["spot_price"],"timestamp_source":raw.get("timestamp_source")}})
        parent = TwoMarketParentCycleInputV1(parent_cycle_id=f"task8-parent-{requested.isoformat()}", decision_result_id=f"task8-decision-{requested.isoformat()}", nifty_child_result_id=f"task8-child-nifty-{requested.isoformat()}", sensex_child_result_id=f"task8-child-sensex-{requested.isoformat()}", nifty_observation_id=cycles[("NIFTY", "NSE")].observation_id, sensex_observation_id=cycles[("SENSEX", "BSE")].observation_id, requested_at=cycles[("NIFTY", "NSE")].cycle_requested_at, completed_at=datetime.now(timezone.utc), decision_policy=TwoMarketDecisionPolicyV1(180.0, 5.0))
        return run_certified_two_market_parent_runtime(parent, nifty_cycle=cycles[("NIFTY", "NSE")], sensex_cycle=cycles[("SENSEX", "BSE")], readers=readers)

    return Task8CanaryDependenciesV1(branch=_git("branch", "--show-current"), commit=_git("rev-parse", "--short", "HEAD"), preflight=preflight, parent_cycle=parent_cycle, selected_planner=lambda market: (_ for _ in ()).throw(RuntimeError("selected-market lifecycle wiring is unavailable")), monitoring=lambda: None, clock=lambda: datetime.now(timezone.utc), id_factory=lambda: f"task8-live-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}")
