"""Certified exact-two-market parent runtime over existing single-market child reads."""
from __future__ import annotations

from services.contracts.market_analysis_candidate_v1 import (
    MarketAnalysisCandidateV1,
)
from services.contracts.paper_orchestration_cycle_input_v1 import (
    PaperOrchestrationCycleInputV1,
)
from services.contracts.two_market_decision_result_v1 import (
    TwoMarketDecisionResultV1,
)
from services.contracts.two_market_parent_cycle_input_v1 import (
    TwoMarketParentCycleInputV1,
)
from services.paper_orchestration.certified_live_provider_readers import (
    CertifiedLiveProviderReaders,
)
from services.paper_orchestration.certified_live_read_authorities import (
    CertifiedLiveAnalysisAuthority,
    CertifiedLiveDataAuthority,
    CertifiedSessionAuthority,
)
from services.paper_orchestration.two_market_parent_cycle_coordinator import (
    ChildEvaluationFailure,
    run_two_market_parent_cycle,
)


_EXACT_IDENTITIES = {
    "NIFTY": ("NIFTY", "NSE"),
    "SENSEX": ("SENSEX", "BSE"),
}


def _validate_child_cycle(
    *,
    parent: TwoMarketParentCycleInputV1,
    cycle: PaperOrchestrationCycleInputV1,
    symbol: str,
    observation_id: str,
) -> None:
    if type(cycle) is not PaperOrchestrationCycleInputV1:
        raise TypeError(f"{symbol.lower()}_cycle")

    expected_symbol, expected_exchange = _EXACT_IDENTITIES[symbol]
    actual = (
        cycle.underlying_symbol,
        cycle.exchange,
        cycle.observation_id,
        cycle.cycle_requested_at,
    )
    expected = (
        expected_symbol,
        expected_exchange,
        observation_id,
        parent.requested_at,
    )
    if actual != expected:
        raise ValueError(f"{symbol} certified child cycle mismatch")
    if cycle.received_at > parent.completed_at:
        raise ValueError(f"{symbol} received_at exceeds parent completion")
    if cycle.execution_mode != "PAPER":
        raise ValueError(f"{symbol} child cycle must remain PAPER")
    if cycle.orchestration_policy.live_execution_eligible:
        raise ValueError(f"{symbol} child cycle cannot be live eligible")
    if cycle.metadata.get("broker_order_submission", False) is not False:
        raise ValueError(f"{symbol} child cycle cannot submit broker orders")


def run_certified_two_market_parent_runtime(
    parent: TwoMarketParentCycleInputV1,
    *,
    nifty_cycle: PaperOrchestrationCycleInputV1,
    sensex_cycle: PaperOrchestrationCycleInputV1,
    readers: CertifiedLiveProviderReaders,
    substage_callback=None,
) -> TwoMarketDecisionResultV1:
    """Run each certified child analysis exactly once, then coordinate/rank."""

    if type(parent) is not TwoMarketParentCycleInputV1:
        raise TypeError("parent")
    if type(readers) is not CertifiedLiveProviderReaders:
        raise TypeError("readers")

    if callable(substage_callback): substage_callback("NIFTY_CYCLE_INPUT_BIND_START")
    _validate_child_cycle(
        parent=parent,
        cycle=nifty_cycle,
        symbol="NIFTY",
        observation_id=parent.nifty_observation_id,
    )
    if callable(substage_callback): substage_callback("NIFTY_CYCLE_INPUT_BIND_COMPLETE")

    if callable(substage_callback): substage_callback("SENSEX_CYCLE_INPUT_BIND_START")
    _validate_child_cycle(
        parent=parent,
        cycle=sensex_cycle,
        symbol="SENSEX",
        observation_id=parent.sensex_observation_id,
    )
    if callable(substage_callback): substage_callback("SENSEX_CYCLE_INPUT_BIND_COMPLETE")

    if readers.capture_reader is not None:
        if callable(substage_callback): substage_callback("SHARED_CONTEXT_BUILD_START")
        readers.prepare_shared_broader_context(nifty_cycle, sensex_cycle)

    cycles = {
        ("NIFTY", "NSE", parent.nifty_observation_id): nifty_cycle,
        ("SENSEX", "BSE", parent.sensex_observation_id): sensex_cycle,
    }

    data_authority = CertifiedLiveDataAuthority(reader=readers.read_data)
    session_authority = CertifiedSessionAuthority()
    analysis_authority = CertifiedLiveAnalysisAuthority(
        reader=readers.read_analysis
    )

    def evaluate(
        symbol: str,
        exchange: str,
        observation_id: str,
    ) -> MarketAnalysisCandidateV1:
        if callable(substage_callback): substage_callback(f"{symbol}_CANDIDATE_BUILD_START")
        cycle = cycles[(symbol, exchange, observation_id)]
        try:
            data = data_authority(cycle)
        except Exception as exc:
            raise ChildEvaluationFailure("spot", "SPOT_EVIDENCE_UNAVAILABLE") from exc
        try:
            session = session_authority(cycle, data)
        except Exception as exc:
            raise ChildEvaluationFailure("session", "SESSION_EVIDENCE_UNAVAILABLE") from exc
        try:
            analysis = analysis_authority(cycle, data, session)
        except Exception as exc:
            raise ChildEvaluationFailure("candidate_composition", "CANDIDATE_COMPOSITION_FAILED") from exc
        candidate = analysis.candidate
        if type(candidate) is not MarketAnalysisCandidateV1:
            raise RuntimeError(
                "certified child analysis did not attach a typed candidate"
            )
        if callable(substage_callback): substage_callback(f"{symbol}_CANDIDATE_BUILD_COMPLETE")
        return candidate

    if callable(substage_callback): substage_callback("PARENT_COMPARISON_START")
    result = run_two_market_parent_cycle(
        parent,
        child_evaluator=evaluate,
    )
    if callable(substage_callback): substage_callback("PARENT_COMPARISON_COMPLETE")
    return result
