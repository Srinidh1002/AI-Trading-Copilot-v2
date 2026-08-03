"""Default live-read composition for the Task 1C parent-only canary."""
from __future__ import annotations

import subprocess
from datetime import datetime, timezone

from services.angel_instrument_master import AngelInstrumentMaster
from services.broker.shared_client import get_market_client
from services.certification.task1c_parent_only_live_canary import Task1CParentOnlyDependenciesV1, Task1CParentOnlyExecutionV1
from services.certification.task8_live_candidate_adapter import adapt_task8_live_candidate
from services.contracts.paper_orchestration_policy_v1 import PaperOrchestrationPolicyV1
from services.contracts.two_market_decision_policy_v1 import TwoMarketDecisionPolicyV1
from services.contracts.two_market_parent_cycle_input_v1 import TwoMarketParentCycleInputV1
from services.market_session.validator import validate_session_timestamp
from services.paper_orchestration.certified_cycle_input_factory import build_certified_cycle_input
from services.paper_orchestration.certified_live_provider_readers import CertifiedLiveProviderReaders, market_spec_for
from services.paper_orchestration.certified_runtime_composition import build_default_runtime_providers, capture_certified_live_evidence
from services.paper_orchestration.authoritative_two_market_entry_point import run_authoritative_two_market_parent_cycle
from services.paper_orchestration.india_vix_live_reader import IndiaVixLiveReader


def _git(*args: str) -> str: return subprocess.check_output(("git", *args), text=True, encoding="utf-8").strip()


def build_task1c_parent_only_dependencies() -> Task1CParentOnlyDependenciesV1:
    providers = build_default_runtime_providers()
    data_service = providers.analysis_pipeline.data_service
    vix_reader = IndiaVixLiveReader(master_fetcher=AngelInstrumentMaster().fetch_instruments, market_client=get_market_client(), clock=providers.clock)
    counts = {"nifty_spot_calls": 0, "sensex_spot_calls": 0, "nifty_candle_capture_count": 0, "sensex_candle_capture_count": 0, "nifty_option_capture_count": 0, "sensex_option_capture_count": 0, "broader_intelligence_calls": 2}
    substage = {"value": "DEPENDENCY_READY"}
    def mark(value: str) -> None: substage["value"] = value
    def capture(cycle, *, candle_cutoff=None):
        key = cycle.underlying_symbol.lower()
        if cycle.underlying_symbol == "NIFTY": mark("NIFTY_CANDLE_CAPTURE_START")
        counts[f"{key}_candle_capture_count"] += 1; counts[f"{key}_option_capture_count"] += 1
        result = capture_certified_live_evidence(cycle_input=cycle, data_service=data_service, option_decision_pipeline=providers.option_decision_pipeline, candle_cutoff=candle_cutoff)
        if cycle.underlying_symbol == "NIFTY": mark("NIFTY_OPTION_CAPTURE_COMPLETE"); mark("NIFTY_NORMALIZATION_START"); mark("NIFTY_NORMALIZATION_COMPLETE"); mark("NIFTY_TYPED_EVIDENCE_START")
        mark(f"{cycle.underlying_symbol}_CAPTURE_COMPLETE")
        return result
    readers = CertifiedLiveProviderReaders(quote_reader=providers.quote_reader, analysis_pipeline=providers.analysis_pipeline, option_decision_pipeline=providers.option_decision_pipeline, available_capital=10_000.0, candidate_reader=adapt_task8_live_candidate, capture_reader=capture, india_vix_reader=vix_reader, substage_callback=mark)
    def run_parent() -> Task1CParentOnlyExecutionV1:
        mark("PARENT_RUN_START"); requested = datetime.now(timezone.utc); quotes = {}
        for symbol, exchange in (("NIFTY", "NSE"), ("SENSEX", "BSE")):
            spec = market_spec_for(symbol, exchange); counts[f"{symbol.lower()}_spot_calls"] += 1
            if symbol == "NIFTY": mark("NIFTY_CAPTURE_START"); mark("NIFTY_SPOT_CAPTURE_START")
            raw = providers.quote_reader(spec.exchange, spec.symboltoken, spec.underlying_symbol)
            if symbol == "NIFTY": mark("NIFTY_SPOT_RESPONSE_RECEIVED"); mark("NIFTY_SPOT_CAPTURE_COMPLETE")
            quotes[(symbol, exchange)] = raw
        parent_requested_at = max(requested, *(raw["received_at"] for raw in quotes.values()))
        cycles = {}
        for symbol, exchange in (("NIFTY", "NSE"), ("SENSEX", "BSE")):
            raw = quotes[(symbol, exchange)]; market_timestamp, received_at = raw["market_timestamp"], raw["received_at"]
            if symbol == "NIFTY": mark("NIFTY_SPOT_FRESHNESS_VALIDATION_START")
            session = validate_session_timestamp(symbol=symbol, exchange=exchange, market_timestamp=market_timestamp, evaluated_at=received_at, validation_mode="LENIENT_ANALYSIS", id_factory=lambda: f"task1c-session-{symbol.lower()}-{market_timestamp.isoformat()}")
            if symbol == "NIFTY": mark("NIFTY_SPOT_FRESHNESS_VALIDATION_COMPLETE")
            policy = PaperOrchestrationPolicyV1(orchestration_policy_id=f"task1c-policy-{parent_requested_at.date().isoformat()}", policy_timestamp=parent_requested_at, observation_frequency_seconds=60.0, emergency_paper_halt=False)
            if symbol == "NIFTY": mark("NIFTY_SPOT_CONTRACT_BUILD_START")
            cycles[(symbol, exchange)] = build_certified_cycle_input(cycle_kind="OPPORTUNITY", observation_id=f"task1c-{symbol.lower()}-{market_timestamp.isoformat()}", orchestration_policy=policy, underlying_symbol=symbol, exchange=exchange, market_timestamp=market_timestamp, received_at=received_at, cycle_requested_at=parent_requested_at, session_validation=session, metadata={"spot_price": raw["spot_price"], "timestamp_source": raw.get("timestamp_source"), "captured_spot_payload": {"spot_price": raw["spot_price"], "timestamp_source": raw.get("timestamp_source")}})
            if symbol == "NIFTY": mark("NIFTY_SPOT_CONTRACT_BUILD_COMPLETE")
        nifty, sensex = cycles[("NIFTY", "NSE")], cycles[("SENSEX", "BSE")]
        parent = TwoMarketParentCycleInputV1(parent_cycle_id=f"task1c-parent-{parent_requested_at.isoformat()}", decision_result_id=f"task1c-decision-{parent_requested_at.isoformat()}", nifty_child_result_id=f"task1c-nifty-{parent_requested_at.isoformat()}", sensex_child_result_id=f"task1c-sensex-{parent_requested_at.isoformat()}", nifty_observation_id=nifty.observation_id, sensex_observation_id=sensex.observation_id, requested_at=parent_requested_at, completed_at=datetime.now(timezone.utc), decision_policy=TwoMarketDecisionPolicyV1(180.0, 5.0))
        decision = run_authoritative_two_market_parent_cycle(parent, nifty_cycle=nifty, sensex_cycle=sensex, readers=readers, substage_callback=mark)
        context = readers.shared_context_for(nifty.observation_id)
        if context is None: raise RuntimeError("INDIA_VIX_SHARED_CONTEXT_MISSING")
        values = dict(counts, india_vix_master_resolution_count=vix_reader.master_resolution_count, india_vix_quote_count=vix_reader.quote_count, india_vix_normalization_count=readers.india_vix_normalization_count)
        return Task1CParentOnlyExecutionV1(decision, context, values)
    return Task1CParentOnlyDependenciesV1(branch=_git("branch", "--show-current"), commit=_git("rev-parse", "--short", "HEAD"), run_parent=run_parent, clock=lambda: datetime.now(timezone.utc), id_factory=lambda: f"task1c-parent-only-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}", last_substage=lambda: substage["value"])
