"""Canonical bridge from option-chain intelligence to contract ranking."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

from services.contracts.option_chain_intelligence_result_v1 import (
    OptionChainIntelligenceResultV1,
)
from services.contracts.option_contract_ranking_policy_v1 import (
    DEFAULT_OPTION_CONTRACT_RANKING_POLICY,
    OptionContractRankingPolicyV1,
)
from services.contracts.option_contract_ranking_result_v1 import (
    OptionContractRankingResultV1,
)
from services.contracts.option_contract_universe_v1 import (
    OptionContractUniverseV1,
)

from .ranker import rank_option_contracts


_READY_INTELLIGENCE_STATUSES = frozenset(
    {
        "READY",
        "READY_WITH_WARNINGS",
    }
)

_BLOCKING_INTELLIGENCE_STATUSES = frozenset(
    {
        "INSUFFICIENT_METRICS",
        "MALFORMED",
        "UNSUPPORTED",
        "FAILED",
    }
)


def build_canonical_option_contract_ranking(
    *,
    intelligence_result: OptionChainIntelligenceResultV1,
    universe: OptionContractUniverseV1,
    now: datetime,
    policy: OptionContractRankingPolicyV1 = (
        DEFAULT_OPTION_CONTRACT_RANKING_POLICY
    ),
    ranking_id_factory: Callable[[], str] | None = None,
) -> OptionContractRankingResultV1:
    """Build a canonical paper-only option-contract ranking result.

    The intelligence result determines direction and expiry. The universe
    supplies already-normalized option contracts. This function performs no
    provider calls, caching, risk calculation, order construction, or
    execution.
    """

    if not isinstance(
        intelligence_result,
        OptionChainIntelligenceResultV1,
    ):
        raise TypeError(
            "intelligence_result must be an "
            "OptionChainIntelligenceResultV1"
        )

    if not isinstance(
        universe,
        OptionContractUniverseV1,
    ):
        raise TypeError(
            "universe must be an OptionContractUniverseV1"
        )

    if not isinstance(now, datetime):
        raise TypeError("now must be a datetime")

    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")

    if not isinstance(
        policy,
        OptionContractRankingPolicyV1,
    ):
        raise TypeError(
            "policy must be an "
            "OptionContractRankingPolicyV1"
        )

    ranking_id_factory = (
        ranking_id_factory
        or (lambda: str(uuid4()))
    )

    identity = (
        intelligence_result.underlying_symbol,
        intelligence_result.exchange,
    )
    universe_identity = (
        universe.underlying_symbol,
        universe.exchange,
    )

    if identity != universe_identity:
        return _blocked_result(
            ranking_id=ranking_id_factory(),
            ranked_at=now,
            intelligence_result=intelligence_result,
            universe=universe,
            blocker=(
                "OPTION-CHAIN INTELLIGENCE AND CONTRACT "
                "UNIVERSE IDENTITIES DO NOT MATCH"
            ),
        )

    intelligence_status = (
        intelligence_result.intelligence_status
    )
    aggregate_bias = intelligence_result.aggregate_bias

    if intelligence_status in _BLOCKING_INTELLIGENCE_STATUSES:
        blockers = tuple(
            sorted(
                set(intelligence_result.blockers)
                | {
                    "OPTION-CHAIN INTELLIGENCE DOES NOT "
                    "PERMIT CONTRACT RANKING"
                }
            )
        )

        return _blocked_result(
            ranking_id=ranking_id_factory(),
            ranked_at=now,
            intelligence_result=intelligence_result,
            universe=universe,
            blockers=blockers,
            status="INSUFFICIENT_DATA",
        )

    if intelligence_status == "CONFLICTING":
        blockers = tuple(
            sorted(
                set(intelligence_result.blockers)
                | {
                    "CONFLICTING OPTION-CHAIN INTELLIGENCE "
                    "DOES NOT PERMIT CONTRACT RANKING"
                }
            )
        )

        return _blocked_result(
            ranking_id=ranking_id_factory(),
            ranked_at=now,
            intelligence_result=intelligence_result,
            universe=universe,
            blockers=blockers,
        )

    if intelligence_status not in _READY_INTELLIGENCE_STATUSES:
        return _blocked_result(
            ranking_id=ranking_id_factory(),
            ranked_at=now,
            intelligence_result=intelligence_result,
            universe=universe,
            blocker=(
                "OPTION-CHAIN INTELLIGENCE STATUS IS "
                "NOT SUPPORTED FOR CONTRACT RANKING"
            ),
        )

    if aggregate_bias not in {"BULLISH", "BEARISH"}:
        return _blocked_result(
            ranking_id=ranking_id_factory(),
            ranked_at=now,
            intelligence_result=intelligence_result,
            universe=universe,
            blocker=(
                "DIRECTIONAL OPTION-CHAIN INTELLIGENCE "
                "IS REQUIRED FOR CONTRACT RANKING"
            ),
        )

    universe_expiries = {
        contract.expiry_date
        for contract in universe.contracts
    }

    if intelligence_result.expiry not in universe_expiries:
        return _blocked_result(
            ranking_id=ranking_id_factory(),
            ranked_at=now,
            intelligence_result=intelligence_result,
            universe=universe,
            blocker=(
                "INTELLIGENCE EXPIRY IS NOT PRESENT IN "
                "THE OPTION CONTRACT UNIVERSE"
            ),
        )

    ranking = rank_option_contracts(
        universe,
        directional_bias=aggregate_bias,
        now=now,
        policy=policy,
        intelligence_result_id=(
            intelligence_result
            .option_chain_intelligence_result_id
        ),
        requested_expiry=intelligence_result.expiry,
        intelligence_alignment_score=(
            intelligence_result.aggregate_strength
        ),
        ranking_id_factory=ranking_id_factory,
    )

    intelligence_warnings = tuple(
        sorted(set(intelligence_result.warnings))
    )

    if not intelligence_warnings:
        return ranking

    combined_warnings = tuple(
        sorted(
            set(ranking.warnings)
            | set(intelligence_warnings)
        )
    )

    ranking_status = ranking.ranking_status

    if ranking_status == "RANKED":
        ranking_status = "RANKED_WITH_WARNINGS"

    return OptionContractRankingResultV1(
        ranking_id=ranking.ranking_id,
        ranked_at=ranking.ranked_at,
        universe_id=ranking.universe_id,
        intelligence_result_id=(
            ranking.intelligence_result_id
        ),
        underlying_symbol=ranking.underlying_symbol,
        exchange=ranking.exchange,
        directional_bias=ranking.directional_bias,
        required_option_type=(
            ranking.required_option_type
        ),
        ranking_status=ranking_status,
        ranked_candidates=ranking.ranked_candidates,
        rejected_candidates=(
            ranking.rejected_candidates
        ),
        blockers=ranking.blockers,
        warnings=combined_warnings,
        diagnostics=ranking.diagnostics,
        metadata=ranking.metadata,
    )


def _blocked_result(
    *,
    ranking_id: str,
    ranked_at: datetime,
    intelligence_result: OptionChainIntelligenceResultV1,
    universe: OptionContractUniverseV1,
    blocker: str | None = None,
    blockers: tuple[str, ...] = (),
    status: str = "BLOCKED",
) -> OptionContractRankingResultV1:
    resolved_blockers = set(blockers)

    if blocker is not None:
        resolved_blockers.add(blocker)

    resolved_blockers.update(
        intelligence_result.blockers
    )

    return OptionContractRankingResultV1(
        ranking_id=ranking_id,
        ranked_at=ranked_at,
        universe_id=universe.universe_id,
        intelligence_result_id=(
            intelligence_result
            .option_chain_intelligence_result_id
        ),
        underlying_symbol=universe.underlying_symbol,
        exchange=universe.exchange,
        directional_bias=(
            intelligence_result.aggregate_bias
        ),
        required_option_type=(
            "CALL"
            if intelligence_result.aggregate_bias
            == "BULLISH"
            else "PUT"
            if intelligence_result.aggregate_bias
            == "BEARISH"
            else None
        ),
        ranking_status=status,
        blockers=tuple(
            sorted(resolved_blockers)
        ),
        warnings=tuple(
            sorted(
                set(intelligence_result.warnings)
                | set(universe.warnings)
            )
        ),
    )


__all__ = [
    "build_canonical_option_contract_ranking",
]