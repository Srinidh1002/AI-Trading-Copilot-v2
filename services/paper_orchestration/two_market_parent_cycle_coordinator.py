"""Exact-once NIFTY/SENSEX parent coordinator for deterministic PAPER analysis."""
from __future__ import annotations

from collections.abc import Callable

from services.analysis.two_market_decision_ranker import (
    rank_two_market_candidates,
)
from services.contracts.market_analysis_candidate_v1 import (
    MarketAnalysisCandidateV1,
)
from services.contracts.two_market_child_terminal_result_v1 import (
    TwoMarketChildTerminalResultV1,
)
from services.contracts.two_market_decision_result_v1 import (
    TwoMarketDecisionResultV1,
)
from services.contracts.two_market_parent_cycle_input_v1 import (
    TwoMarketParentCycleInputV1,
)


ChildEvaluator = Callable[
    [str, str, str],
    MarketAnalysisCandidateV1,
]


class ChildEvaluationFailure(RuntimeError):
    """Safe, deterministic child-evaluation failure passed to the coordinator."""
    def __init__(self, component: str, reason_code: str) -> None:
        self.component = component
        self.reason_code = reason_code
        super().__init__(reason_code)


def _evaluate_once(
    *,
    parent: TwoMarketParentCycleInputV1,
    child_result_id: str,
    observation_id: str,
    symbol: str,
    exchange: str,
    evaluator: ChildEvaluator,
) -> TwoMarketChildTerminalResultV1:
    try:
        candidate = evaluator(symbol, exchange, observation_id)
        if type(candidate) is not MarketAnalysisCandidateV1:
            raise TypeError(
                "child evaluator must return exact MarketAnalysisCandidateV1"
            )

        expected = (
            observation_id,
            symbol,
            exchange,
            parent.requested_at,
        )
        actual = (
            candidate.observation_id,
            candidate.underlying_symbol,
            candidate.exchange,
            candidate.requested_at,
        )
        if actual != expected:
            raise ValueError(
                "candidate identity or requested_at mismatch"
            )
        if candidate.received_at > parent.completed_at:
            raise ValueError(
                "candidate received_at exceeds parent completed_at"
            )

        return TwoMarketChildTerminalResultV1(
            child_result_id=child_result_id,
            parent_cycle_id=parent.parent_cycle_id,
            observation_id=observation_id,
            underlying_symbol=symbol,
            exchange=exchange,
            requested_at=parent.requested_at,
            received_at=candidate.received_at,
            terminal_status="COMPLETED",
            candidate=candidate,
        )
    except Exception as exc:
        if isinstance(exc, ChildEvaluationFailure):
            blockers = (exc.reason_code,)
            errors = (exc.reason_code,)
        else:
            blockers = ("CANDIDATE_COMPOSITION_FAILED",)
            errors = ("CANDIDATE_COMPOSITION_FAILED",)
        return TwoMarketChildTerminalResultV1(
            child_result_id=child_result_id,
            parent_cycle_id=parent.parent_cycle_id,
            observation_id=observation_id,
            underlying_symbol=symbol,
            exchange=exchange,
            requested_at=parent.requested_at,
            received_at=parent.completed_at,
            terminal_status="FAILED",
            blockers=blockers,
            errors=errors,
        )


def run_two_market_parent_cycle(
    parent: TwoMarketParentCycleInputV1,
    *,
    child_evaluator: ChildEvaluator,
) -> TwoMarketDecisionResultV1:
    """Evaluate NIFTY once and SENSEX once, retain both, then rank."""

    if type(parent) is not TwoMarketParentCycleInputV1:
        raise TypeError("parent")
    if not callable(child_evaluator):
        raise TypeError("child_evaluator")

    nifty = _evaluate_once(
        parent=parent,
        child_result_id=parent.nifty_child_result_id,
        observation_id=parent.nifty_observation_id,
        symbol="NIFTY",
        exchange="NSE",
        evaluator=child_evaluator,
    )
    sensex = _evaluate_once(
        parent=parent,
        child_result_id=parent.sensex_child_result_id,
        observation_id=parent.sensex_observation_id,
        symbol="SENSEX",
        exchange="BSE",
        evaluator=child_evaluator,
    )

    return rank_two_market_candidates(
        decision_result_id=parent.decision_result_id,
        parent_cycle_id=parent.parent_cycle_id,
        requested_at=parent.requested_at,
        completed_at=parent.completed_at,
        nifty=nifty,
        sensex=sensex,
        policy=parent.decision_policy,
    )
