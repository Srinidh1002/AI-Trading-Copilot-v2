"""Pure Task 2C action projection; no planning or execution imports."""

from services.contracts.pre_entry_action_policy_v1 import PreEntryActionPolicyV1
from services.contracts.pre_entry_market_action_v1 import PreEntryMarketActionV1


def resolve_pre_entry_market_action(
    *,
    candidate,
    cycle_id: str,
    observation_id: str,
    evaluated_at,
    ledger=None,
    policy=PreEntryActionPolicyV1(),
    failure_codes: tuple[str, ...] = (),
):
    if type(policy) is not PreEntryActionPolicyV1:
        raise TypeError("policy")

    if candidate is None:
        return PreEntryMarketActionV1(
            f"action:{cycle_id}:{observation_id}",
            "NIFTY",
            "NSE",
            cycle_id,
            observation_id,
            None,
            "NO_TRADE",
            "UNAVAILABLE",
            "UNAVAILABLE",
            0.0,
            0.0,
            None,
            False,
            getattr(ledger, "ledger_id", None),
            evaluated_at,
            blockers=tuple(failure_codes) or ("CANDIDATE_UNAVAILABLE",),
            reasons=("CANDIDATE_COMPOSITION_FAILED",),
        )

    symbol = candidate.underlying_symbol
    exchange = candidate.exchange
    suitability = getattr(
        candidate.regime,
        "entry_suitability",
        None,
    )
    ledger_id = getattr(
        ledger,
        "ledger_id",
        None,
    )

    # A canonical policy abstention is not evidence unavailability.
    # Preserve its valid directional conclusion while remaining NO_TRADE.
    policy_abstention = (
        candidate.direction in {"BULLISH", "BEARISH"}
        and candidate.eligibility == "INELIGIBLE"
        and suitability == "SUITABLE"
        and candidate.blockers == ("POLICY_INELIGIBLE",)
        and not candidate.contradictions
    )

    if policy_abstention:
        return PreEntryMarketActionV1(
            f"action:{cycle_id}:{observation_id}",
            symbol,
            exchange,
            cycle_id,
            observation_id,
            candidate.candidate_id,
            "NO_TRADE",
            candidate.direction,
            candidate.eligibility,
            0.0,
            0.0,
            suitability,
            False,
            ledger_id,
            evaluated_at,
            blockers=("POLICY_INELIGIBLE",),
            reasons=("POLICY_INELIGIBLE",),
            warnings=candidate.warnings,
        )

    unavailable = bool(
        candidate.blockers
        or candidate.contradictions
        or candidate.direction in {"UNAVAILABLE", "CONFLICTING"}
        or candidate.eligibility in {"UNAVAILABLE", "CONFLICTING"}
        or suitability in {"BLOCKED", "NOT_SUITABLE", "UNAVAILABLE"}
    )

    if unavailable:
        policy_blocker = next(
            (
                item
                for item in candidate.blockers
                if item
                in {
                    "OPTION_CHAIN_CONFLICTING",
                    "OPTION_RANKING_BLOCKED",
                    "REGIME_CAUTION",
                }
            ),
            None,
        )

        code = (
            "EVIDENCE_CONFLICTING"
            if candidate.contradictions
            else "REGIME_BLOCKED"
            if suitability in {"BLOCKED", "NOT_SUITABLE"}
            else "EVIDENCE_UNAVAILABLE_REGIME"
            if suitability == "UNAVAILABLE"
            else policy_blocker
            if policy_blocker is not None
            else "REQUIRED_EVIDENCE_UNAVAILABLE"
        )

        return PreEntryMarketActionV1(
            f"action:{cycle_id}:{observation_id}",
            symbol,
            exchange,
            cycle_id,
            observation_id,
            candidate.candidate_id,
            "NO_TRADE",
            "UNAVAILABLE",
            candidate.eligibility,
            0.0,
            0.0,
            suitability,
            False,
            ledger_id,
            evaluated_at,
            blockers=tuple(
                dict.fromkeys(
                    (
                        *candidate.blockers,
                        *candidate.contradictions,
                        code,
                    )
                )
            ),
            reasons=(code,),
            warnings=candidate.warnings,
        )

    if (
        candidate.eligibility == "ELIGIBLE"
        and candidate.direction == "BULLISH"
    ):
        action = "CALL"
        reason = "ELIGIBLE_BULLISH_CANDIDATE"

    elif (
        candidate.eligibility == "ELIGIBLE"
        and candidate.direction == "BEARISH"
    ):
        action = "PUT"
        reason = "ELIGIBLE_BEARISH_CANDIDATE"

    else:
        action = "WAIT"
        reason = (
            "DIRECTION_NEUTRAL_NO_ENTRY"
            if candidate.direction == "NEUTRAL"
            else "VALID_EVIDENCE_INSUFFICIENT_CONFIRMATION"
        )

    return PreEntryMarketActionV1(
        f"action:{cycle_id}:{observation_id}",
        symbol,
        exchange,
        cycle_id,
        observation_id,
        candidate.candidate_id,
        action,
        candidate.direction,
        candidate.eligibility,
        candidate.confidence,
        candidate.score,
        suitability,
        action in {"CALL", "PUT"},
        ledger_id,
        evaluated_at,
        reasons=(reason,),
        warnings=candidate.warnings,
    )
