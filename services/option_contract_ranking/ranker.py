"""Deterministic ranking of canonical option-contract universes."""

from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

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

from .evaluator import evaluate_option_contract


def rank_option_contracts(
    universe: OptionContractUniverseV1,
    *,
    directional_bias: str,
    now: datetime,
    policy: OptionContractRankingPolicyV1 | None = None,
    intelligence_result_id: str | None = None,
    requested_expiry: date | None = None,
    intelligence_alignment_score: float = 1.0,
    ranking_id_factory=None,
) -> OptionContractRankingResultV1:
    """Rank eligible contracts in a normalized option universe."""

    if not isinstance(universe, OptionContractUniverseV1):
        raise TypeError(
            "universe must be an OptionContractUniverseV1"
        )

    if not isinstance(now, datetime):
        raise TypeError("now must be a datetime")

    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")

    policy = (
        policy
        or DEFAULT_OPTION_CONTRACT_RANKING_POLICY
    )

    if not isinstance(policy, OptionContractRankingPolicyV1):
        raise TypeError(
            "policy must be an OptionContractRankingPolicyV1"
        )

    bias = str(directional_bias).strip().upper()

    if bias not in {
        "BULLISH",
        "BEARISH",
        "NEUTRAL",
        "MIXED",
        "UNAVAILABLE",
    }:
        raise ValueError(
            "unsupported directional_bias"
        )

    required_option_type = (
        "CALL"
        if bias == "BULLISH"
        else "PUT"
        if bias == "BEARISH"
        else None
    )

    ranking_id = (
        ranking_id_factory
        or (lambda: str(uuid4()))
    )()

    blockers: list[str] = []
    warnings: list[str] = []
    diagnostics: list[str] = []

    universe_age_seconds = (
        now - universe.captured_at
    ).total_seconds()

    future_skew_seconds = (
        universe.captured_at - now
    ).total_seconds()

    if (
        universe_age_seconds
        > policy.maximum_universe_age_seconds
    ):
        blockers.append(
            "OPTION CONTRACT UNIVERSE IS STALE"
        )

    if (
        future_skew_seconds
        > policy.maximum_future_skew_seconds
    ):
        blockers.append(
            "OPTION CONTRACT UNIVERSE TIMESTAMP "
            "IS IN THE FUTURE"
        )

    if (
        policy.require_trusted_universe
        and not universe.trusted
    ):
        blockers.append(
            "TRUSTED OPTION CONTRACT UNIVERSE "
            "IS REQUIRED"
        )
    elif not universe.trusted:
        warnings.append(
            "OPTION CONTRACT UNIVERSE IS UNTRUSTED"
        )

    warnings.extend(
        str(item).strip().upper()
        for item in universe.warnings
        if str(item).strip()
    )

    if required_option_type is None:
        if policy.intelligence_policy == "REQUIRE_DIRECTIONAL":
            blockers.append(
                "DIRECTIONAL INTELLIGENCE IS REQUIRED"
            )
        elif (
            policy.intelligence_policy == "ALLOW_NEUTRAL"
        ):
            blockers.append(
                "NEUTRAL INTELLIGENCE CANNOT DETERMINE "
                "AN OPTION TYPE"
            )
        else:
            blockers.append(
                "OPTION TYPE CANNOT BE DETERMINED"
            )

    if blockers:
        return OptionContractRankingResultV1(
            ranking_id=ranking_id,
            ranked_at=now,
            universe_id=universe.universe_id,
            intelligence_result_id=(
                intelligence_result_id
            ),
            underlying_symbol=(
                universe.underlying_symbol
            ),
            exchange=universe.exchange,
            directional_bias=bias,
            required_option_type=(
                required_option_type
            ),
            ranking_status="BLOCKED",
            blockers=tuple(
                sorted(set(blockers))
            ),
            warnings=tuple(
                sorted(set(warnings))
            ),
            diagnostics=tuple(
                sorted(set(diagnostics))
            ),
        )

    contracts = tuple(universe.contracts)

    if requested_expiry is not None:
        contracts = tuple(
            contract
            for contract in contracts
            if contract.expiry_date == requested_expiry
        )
        diagnostics.append(
            "EXPLICIT EXPIRY FILTER APPLIED"
        )

    elif (
        policy.expiry_policy
        == "EXPLICIT_EXPIRY_ONLY"
    ):
        return OptionContractRankingResultV1(
            ranking_id=ranking_id,
            ranked_at=now,
            universe_id=universe.universe_id,
            intelligence_result_id=(
                intelligence_result_id
            ),
            underlying_symbol=(
                universe.underlying_symbol
            ),
            exchange=universe.exchange,
            directional_bias=bias,
            required_option_type=(
                required_option_type
            ),
            ranking_status="BLOCKED",
            blockers=(
                "EXPLICIT EXPIRY IS REQUIRED",
            ),
            warnings=tuple(
                sorted(set(warnings))
            ),
            diagnostics=(),
        )

    elif (
        policy.expiry_policy
        == "EARLIEST_ELIGIBLE"
    ):
        eligible_expiries = tuple(
            sorted(
                {
                    contract.expiry_date
                    for contract in contracts
                    if (
                        contract.option_type
                        == required_option_type
                        and contract.expiry_date
                        >= now.date()
                    )
                }
            )
        )

        if eligible_expiries:
            earliest_expiry = eligible_expiries[0]
            contracts = tuple(
                contract
                for contract in contracts
                if contract.expiry_date
                == earliest_expiry
            )
            diagnostics.append(
                "EARLIEST ELIGIBLE EXPIRY APPLIED"
            )

    evaluated = tuple(
        evaluate_option_contract(
            contract,
            spot_price=universe.spot_price,
            required_option_type=(
                required_option_type
            ),
            now=now,
            policy=policy,
            intelligence_alignment_score=(
                intelligence_alignment_score
            ),
        )
        for contract in contracts
    )

    ranked_candidates = tuple(
        sorted(
            (
                candidate
                for candidate in evaluated
                if candidate.eligible
            ),
            key=lambda candidate: (
                -candidate.total_score,
                candidate.strike_distance_percent,
                (
                    candidate.spread_percent
                    if candidate.spread_percent
                    is not None
                    else float("inf")
                ),
                candidate.contract.expiry_date,
                candidate.contract.strike,
                candidate.contract.contract_id,
            ),
        )[
            : policy.maximum_ranked_candidates
        ]
    )

    rejected_candidates = tuple(
        sorted(
            (
                candidate
                for candidate in evaluated
                if not candidate.eligible
            ),
            key=lambda candidate: (
                candidate.contract.expiry_date,
                candidate.contract.strike,
                candidate.contract.contract_id,
            ),
        )
    )

    if not ranked_candidates:
        if not rejected_candidates:
            blockers.append(
                "OPTION CONTRACT UNIVERSE HAS NO "
                "CANDIDATES AFTER FILTERING"
            )

            return OptionContractRankingResultV1(
                ranking_id=ranking_id,
                ranked_at=now,
                universe_id=universe.universe_id,
                intelligence_result_id=(
                    intelligence_result_id
                ),
                underlying_symbol=(
                    universe.underlying_symbol
                ),
                exchange=universe.exchange,
                directional_bias=bias,
                required_option_type=(
                    required_option_type
                ),
                ranking_status="INSUFFICIENT_DATA",
                blockers=tuple(
                    sorted(set(blockers))
                ),
                warnings=tuple(
                    sorted(set(warnings))
                ),
                diagnostics=tuple(
                    sorted(set(diagnostics))
                ),
            )

        return OptionContractRankingResultV1(
            ranking_id=ranking_id,
            ranked_at=now,
            universe_id=universe.universe_id,
            intelligence_result_id=(
                intelligence_result_id
            ),
            underlying_symbol=(
                universe.underlying_symbol
            ),
            exchange=universe.exchange,
            directional_bias=bias,
            required_option_type=(
                required_option_type
            ),
            ranking_status=(
                "NO_ELIGIBLE_CONTRACTS"
            ),
            rejected_candidates=(
                rejected_candidates
            ),
            warnings=tuple(
                sorted(set(warnings))
            ),
            diagnostics=tuple(
                sorted(set(diagnostics))
            ),
        )

    candidate_warnings = tuple(
        warning
        for candidate in ranked_candidates
        for warning in candidate.warnings
    )

    all_warnings = tuple(
        sorted(
            set(warnings)
            | set(candidate_warnings)
        )
    )

    status = (
        "RANKED_WITH_WARNINGS"
        if all_warnings
        else "RANKED"
    )

    return OptionContractRankingResultV1(
        ranking_id=ranking_id,
        ranked_at=now,
        universe_id=universe.universe_id,
        intelligence_result_id=(
            intelligence_result_id
        ),
        underlying_symbol=universe.underlying_symbol,
        exchange=universe.exchange,
        directional_bias=bias,
        required_option_type=required_option_type,
        ranking_status=status,
        ranked_candidates=ranked_candidates,
        rejected_candidates=rejected_candidates,
        warnings=all_warnings,
        diagnostics=tuple(
            sorted(set(diagnostics))
        ),
    )