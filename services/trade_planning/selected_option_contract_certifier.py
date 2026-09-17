"""Task 3B exact option-contract certification."""
from __future__ import annotations

from datetime import datetime
from math import isfinite

from services.contracts.selected_market_planning_bridge_result_v1 import (
    SelectedMarketPlanningBridgeResultV1,
)
from services.contracts.selected_option_contract_certification_result_v1 import (
    SelectedOptionContractCertificationResultV1,
)


def _aware(value: object, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(name)
    return value


def _non_negative(value: object, name: str, *, maximum: float | None = None) -> float:
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not isfinite(value)
        or value < 0.0
        or (maximum is not None and value > maximum)
    ):
        raise ValueError(name)
    return float(value)


def _positive(value: object, name: str) -> float:
    result = _non_negative(value, name)
    if result <= 0.0:
        raise ValueError(name)
    return result


def _blocked(
    *,
    certification_result_id: str,
    bridge: SelectedMarketPlanningBridgeResultV1,
    evaluated_at: datetime,
    status: str,
    blockers: tuple[str, ...],
    warnings: tuple[str, ...] = (),
    reasons: tuple[str, ...] = (),
    ranking_result_id: str | None = None,
    universe_id: str | None = None,
) -> SelectedOptionContractCertificationResultV1:
    return SelectedOptionContractCertificationResultV1(
        certification_result_id=certification_result_id,
        parent_cycle_id=bridge.parent_cycle_id,
        parent_decision_id=bridge.parent_decision_id,
        bridge_result_id=bridge.bridge_result_id,
        selected_child_result_id=bridge.selected_child_result_id,
        candidate_id=bridge.candidate_id,
        observation_id=bridge.observation_id,
        ranking_result_id=ranking_result_id,
        universe_id=universe_id,
        evaluated_at=evaluated_at,
        status=status,
        selected_market=bridge.selected_market,
        direction=bridge.direction,
        option_right=(
            bridge.action if bridge.action in {"CALL", "PUT"} else None
        ),
        selected_rank=None,
        selected_candidate=None,
        selected_contract=None,
        contract_id=None,
        trading_symbol=None,
        instrument_token=None,
        expiry_date=None,
        strike=None,
        lot_size=None,
        premium=None,
        bid_price=None,
        ask_price=None,
        spread_value=None,
        spread_fraction=None,
        quote_timestamp=None,
        contract_age_seconds=None,
        quote_age_seconds=None,
        liquidity_score=None,
        open_interest=None,
        volume=None,
        blockers=blockers,
        warnings=warnings,
        reasons=reasons,
    )


def certify_selected_option_contract(
    *,
    certification_result_id: str,
    bridge: SelectedMarketPlanningBridgeResultV1,
    evaluated_at: datetime,
    maximum_ranking_age_seconds: float,
    maximum_contract_age_seconds: float,
    maximum_quote_age_seconds: float,
    maximum_spread_fraction: float,
    minimum_liquidity_score: float,
    minimum_open_interest: float,
    minimum_volume: float,
) -> SelectedOptionContractCertificationResultV1:
    """Certify the canonical top-ranked contract without provider or capital calls."""

    if type(bridge) is not SelectedMarketPlanningBridgeResultV1:
        raise TypeError("bridge")

    now = _aware(evaluated_at, "evaluated_at")
    max_ranking_age = _positive(maximum_ranking_age_seconds, "maximum_ranking_age_seconds")
    max_contract_age = _positive(maximum_contract_age_seconds, "maximum_contract_age_seconds")
    max_quote_age = _positive(maximum_quote_age_seconds, "maximum_quote_age_seconds")
    max_spread = _non_negative(maximum_spread_fraction, "maximum_spread_fraction", maximum=1.0)
    min_liquidity = _non_negative(minimum_liquidity_score, "minimum_liquidity_score", maximum=1.0)
    min_oi = _non_negative(minimum_open_interest, "minimum_open_interest")
    min_volume = _non_negative(minimum_volume, "minimum_volume")

    handoff_blockers: list[str] = []
    if not bridge.planning_allowed:
        handoff_blockers.append("PLANNING_HANDOFF_NOT_ALLOWED")
    if bridge.action not in {"CALL", "PUT"} or bridge.selected_child_action != bridge.action:
        handoff_blockers.append("PLANNING_HANDOFF_NOT_ACTIONABLE")
    if bridge.selected_candidate is None:
        handoff_blockers.append("PLANNING_HANDOFF_IDENTITY_MISMATCH")
    else:
        candidate = bridge.selected_candidate
        if (
            bridge.selected_market != (candidate.underlying_symbol, candidate.exchange)
            or bridge.candidate_id != candidate.candidate_id
            or bridge.observation_id != candidate.observation_id
            or bridge.direction != candidate.direction
        ):
            handoff_blockers.append("PLANNING_HANDOFF_IDENTITY_MISMATCH")

    if handoff_blockers:
        return _blocked(
            certification_result_id=certification_result_id,
            bridge=bridge,
            evaluated_at=now,
            status="BLOCKED",
            blockers=tuple(dict.fromkeys(handoff_blockers + list(bridge.blockers))),
            warnings=bridge.warnings,
            reasons=bridge.reasons,
        )

    market_candidate = bridge.selected_candidate
    ranking = market_candidate.option_contract_eligibility
    if ranking is None:
        return _blocked(
            certification_result_id=certification_result_id,
            bridge=bridge,
            evaluated_at=now,
            status="UNAVAILABLE",
            blockers=("OPTION_RANKING_UNAVAILABLE",),
            warnings=bridge.warnings,
            reasons=bridge.reasons,
        )

    ranking_blockers: list[str] = []
    expected_right = bridge.action
    if (ranking.underlying_symbol, ranking.exchange) != bridge.selected_market:
        ranking_blockers.append("OPTION_RANKING_IDENTITY_MISMATCH")
    if ranking.directional_bias != bridge.direction:
        ranking_blockers.append("OPTION_RANKING_DIRECTION_MISMATCH")
    if ranking.required_option_type != expected_right:
        ranking_blockers.append("OPTION_RANKING_RIGHT_MISMATCH")

    ranking_age = (now - ranking.ranked_at).total_seconds()
    if ranking_age < 0.0:
        ranking_blockers.append("OPTION_RANKING_TIMESTAMP_IN_FUTURE")
    elif ranking_age > max_ranking_age:
        ranking_blockers.append("OPTION_RANKING_STALE")

    if ranking.ranking_status not in {"RANKED", "RANKED_WITH_WARNINGS"}:
        if ranking.ranking_status in {"INSUFFICIENT_DATA", "FAILED", "NO_ELIGIBLE_CONTRACTS"}:
            ranking_blockers.append("OPTION_RANKING_UNAVAILABLE")
        else:
            ranking_blockers.append("OPTION_RANKING_BLOCKED")
        ranking_blockers.extend(ranking.blockers)

    selected = ranking.selected_candidate
    if selected is None:
        ranking_blockers.append("OPTION_CONTRACT_UNAVAILABLE")

    if ranking_blockers:
        status = (
            "UNAVAILABLE"
            if "OPTION_RANKING_UNAVAILABLE" in ranking_blockers
            or "OPTION_CONTRACT_UNAVAILABLE" in ranking_blockers
            else "BLOCKED"
        )
        return _blocked(
            certification_result_id=certification_result_id,
            bridge=bridge,
            evaluated_at=now,
            status=status,
            blockers=tuple(dict.fromkeys(ranking_blockers)),
            warnings=tuple(dict.fromkeys(bridge.warnings + ranking.warnings)),
            reasons=tuple(dict.fromkeys(bridge.reasons + ranking.diagnostics)),
            ranking_result_id=ranking.ranking_id,
            universe_id=ranking.universe_id,
        )

    contract = selected.contract
    blockers: list[str] = []

    if (contract.underlying_symbol, contract.exchange) != bridge.selected_market:
        blockers.append("OPTION_CONTRACT_IDENTITY_MISMATCH")
    if contract.option_type != expected_right:
        blockers.append("OPTION_CONTRACT_RIGHT_MISMATCH")
    if not contract.tradable:
        blockers.append("OPTION_CONTRACT_NOT_TRADABLE")
    if not contract.trading_symbol.strip():
        blockers.append("OPTION_CONTRACT_SYMBOL_UNAVAILABLE")
    if contract.instrument_token is None or not str(contract.instrument_token).strip():
        blockers.append("OPTION_CONTRACT_TOKEN_UNAVAILABLE")
    if contract.expiry_date is None:
        blockers.append("OPTION_CONTRACT_EXPIRY_UNAVAILABLE")
    if type(contract.strike) not in (int, float) or not isfinite(contract.strike) or contract.strike <= 0:
        blockers.append("OPTION_CONTRACT_STRIKE_INVALID")
    if (
        type(contract.lot_size) is not int
        or isinstance(contract.lot_size, bool)
        or contract.lot_size <= 0
    ):
        blockers.append("OPTION_CONTRACT_LOT_SIZE_INVALID")

    premium = contract.last_price
    bid = contract.bid_price
    ask = contract.ask_price
    if premium is None or premium <= 0:
        blockers.append("OPTION_PREMIUM_UNAVAILABLE")
    if bid is None or bid <= 0:
        blockers.append("OPTION_BID_UNAVAILABLE")
    if ask is None or ask <= 0:
        blockers.append("OPTION_ASK_UNAVAILABLE")

    spread_value = None
    spread_fraction = None
    if bid is not None and ask is not None and bid > 0 and ask > 0:
        if ask < bid:
            blockers.append("OPTION_QUOTE_CROSSED")
        else:
            spread_value = ask - bid
            midpoint = (ask + bid) / 2.0
            spread_fraction = spread_value / midpoint
            if spread_fraction > max_spread:
                blockers.append("OPTION_SPREAD_EXCEEDS_LIMIT")

    timestamp = contract.market_timestamp
    age = (now - timestamp).total_seconds()
    if age < 0.0:
        blockers.extend(
            (
                "OPTION_CONTRACT_TIMESTAMP_IN_FUTURE",
                "OPTION_QUOTE_TIMESTAMP_IN_FUTURE",
            )
        )
    else:
        if age > max_contract_age:
            blockers.append("OPTION_CONTRACT_STALE")
        if age > max_quote_age:
            blockers.append("OPTION_QUOTE_STALE")

    liquidity = selected.liquidity_score
    if liquidity is None:
        blockers.append("OPTION_LIQUIDITY_UNAVAILABLE")
    elif liquidity < min_liquidity:
        blockers.append("OPTION_LIQUIDITY_BELOW_MINIMUM")

    if contract.open_interest is None:
        blockers.append("OPTION_OPEN_INTEREST_UNAVAILABLE")
    elif contract.open_interest < min_oi:
        blockers.append("OPTION_OPEN_INTEREST_BELOW_MINIMUM")

    if contract.volume is None:
        blockers.append("OPTION_VOLUME_UNAVAILABLE")
    elif contract.volume < min_volume:
        blockers.append("OPTION_VOLUME_BELOW_MINIMUM")

    if selected.spread_percent is None:
        blockers.append("OPTION_SPREAD_UNAVAILABLE")
    elif spread_fraction is not None:
        candidate_fraction = selected.spread_percent / 100.0
        if abs(candidate_fraction - spread_fraction) > 1e-9:
            blockers.append("OPTION_SPREAD_EVIDENCE_MISMATCH")

    warnings = tuple(dict.fromkeys(bridge.warnings + ranking.warnings + selected.warnings))
    reasons = tuple(
    dict.fromkeys(
        bridge.reasons
        + ranking.diagnostics
        + (
            f"OPTION_CONTRACT_ID={contract.contract_id}",
            f"OPTION_TRADING_SYMBOL={contract.trading_symbol}",
            "OPTION_RANK=1",
        )
    )
)

    if blockers:
        return _blocked(
            certification_result_id=certification_result_id,
            bridge=bridge,
            evaluated_at=now,
            status="BLOCKED",
            blockers=tuple(dict.fromkeys(blockers)),
            warnings=warnings,
            reasons=reasons,
            ranking_result_id=ranking.ranking_id,
            universe_id=ranking.universe_id,
        )

    return SelectedOptionContractCertificationResultV1(
        certification_result_id=certification_result_id,
        parent_cycle_id=bridge.parent_cycle_id,
        parent_decision_id=bridge.parent_decision_id,
        bridge_result_id=bridge.bridge_result_id,
        selected_child_result_id=bridge.selected_child_result_id,
        candidate_id=bridge.candidate_id,
        observation_id=bridge.observation_id,
        ranking_result_id=ranking.ranking_id,
        universe_id=ranking.universe_id,
        evaluated_at=now,
        status="CERTIFIED",
        selected_market=bridge.selected_market,
        direction=bridge.direction,
        option_right=expected_right,
        selected_rank=1,
        selected_candidate=selected,
        selected_contract=contract,
        contract_id=contract.contract_id,
        trading_symbol=contract.trading_symbol,
        instrument_token=str(contract.instrument_token).strip(),
        expiry_date=contract.expiry_date,
        strike=contract.strike,
        lot_size=contract.lot_size,
        premium=premium,
        bid_price=bid,
        ask_price=ask,
        spread_value=spread_value,
        spread_fraction=spread_fraction,
        quote_timestamp=timestamp,
        contract_age_seconds=age,
        quote_age_seconds=age,
        liquidity_score=liquidity,
        open_interest=contract.open_interest,
        volume=contract.volume,
        blockers=(),
        warnings=warnings,
        reasons=reasons,
    )
