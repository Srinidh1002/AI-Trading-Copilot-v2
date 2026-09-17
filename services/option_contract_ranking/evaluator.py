"""Eligibility evaluation and deterministic scoring for option contracts."""

from __future__ import annotations

import math
from datetime import datetime

from services.contracts.option_contract_candidate_v1 import (
    OptionContractCandidateV1,
)
from services.contracts.option_contract_ranking_policy_v1 import (
    OptionContractRankingPolicyV1,
)
from services.contracts.option_contract_v1 import OptionContractV1


def evaluate_option_contract(
    contract: OptionContractV1,
    *,
    spot_price: float,
    required_option_type: str,
    now: datetime,
    policy: OptionContractRankingPolicyV1,
    intelligence_alignment_score: float = 1.0,
) -> OptionContractCandidateV1:
    """Evaluate one contract for eligibility and ranking.

    This function is deterministic, side-effect free, and paper-only.
    """

    if not isinstance(contract, OptionContractV1):
        raise TypeError(
            "contract must be an OptionContractV1"
        )

    if (
        isinstance(spot_price, bool)
        or not isinstance(spot_price, (int, float))
        or not math.isfinite(float(spot_price))
        or float(spot_price) <= 0.0
    ):
        raise ValueError(
            "spot_price must be a positive finite number"
        )

    if not isinstance(now, datetime):
        raise TypeError("now must be a datetime")

    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")

    if not isinstance(policy, OptionContractRankingPolicyV1):
        raise TypeError(
            "policy must be an OptionContractRankingPolicyV1"
        )

    required_option_type = str(
        required_option_type
    ).strip().upper()

    if required_option_type not in {"CALL", "PUT"}:
        raise ValueError(
            "required_option_type must be CALL or PUT"
        )

    if (
        isinstance(intelligence_alignment_score, bool)
        or not isinstance(
            intelligence_alignment_score,
            (int, float),
        )
        or not math.isfinite(
            float(intelligence_alignment_score)
        )
        or not 0.0
        <= float(intelligence_alignment_score)
        <= 1.0
    ):
        raise ValueError(
            "intelligence_alignment_score must be "
            "between zero and one"
        )

    spot_price = float(spot_price)
    intelligence_alignment_score = float(
        intelligence_alignment_score
    )

    rejection_reasons: list[str] = []
    warnings: list[str] = []

    strike_distance_percent = (
        abs(contract.strike - spot_price)
        / spot_price
        * 100.0
    )

    moneyness = _moneyness(
        option_type=contract.option_type,
        strike=contract.strike,
        spot_price=spot_price,
    )

    spread_percent = _spread_percent(contract)

    contract_age_seconds = (
        now - contract.market_timestamp
    ).total_seconds()

    future_skew_seconds = (
        contract.market_timestamp - now
    ).total_seconds()

    if contract.option_type != required_option_type:
        rejection_reasons.append(
            "OPTION TYPE DOES NOT MATCH DIRECTIONAL BIAS"
        )

    if not contract.tradable:
        rejection_reasons.append(
            "CONTRACT IS NOT TRADABLE"
        )

    if contract.expiry_date < now.date():
        rejection_reasons.append(
            "CONTRACT IS EXPIRED"
        )

    if (
        contract_age_seconds
        > policy.maximum_contract_age_seconds
    ):
        rejection_reasons.append(
            "CONTRACT QUOTE IS STALE"
        )

    if (
        future_skew_seconds
        > policy.maximum_future_skew_seconds
    ):
        rejection_reasons.append(
            "CONTRACT TIMESTAMP IS IN THE FUTURE"
        )

    if (
        strike_distance_percent
        > policy.maximum_strike_distance_percent
    ):
        rejection_reasons.append(
            "STRIKE DISTANCE EXCEEDS POLICY LIMIT"
        )

    if policy.require_bid_ask:
        if (
            contract.bid_price is None
            or contract.ask_price is None
        ):
            rejection_reasons.append(
                "BID AND ASK ARE REQUIRED"
            )
        elif (
            contract.bid_price <= 0.0
            or contract.ask_price <= 0.0
        ):
            rejection_reasons.append(
                "BID AND ASK MUST BE POSITIVE"
            )
        elif contract.ask_price < contract.bid_price:
            rejection_reasons.append(
                "ASK PRICE IS BELOW BID PRICE"
            )

    if spread_percent is None:
        if policy.require_bid_ask:
            rejection_reasons.append(
                "SPREAD IS UNAVAILABLE"
            )
        else:
            warnings.append(
                "SPREAD IS UNAVAILABLE"
            )
    elif (
        spread_percent
        > policy.maximum_spread_percent
    ):
        rejection_reasons.append(
            "BID-ASK SPREAD EXCEEDS POLICY LIMIT"
        )

    if contract.volume is None:
        if policy.require_volume:
            rejection_reasons.append(
                "VOLUME IS REQUIRED"
            )
        else:
            warnings.append(
                "VOLUME IS UNAVAILABLE"
            )
    elif contract.volume < policy.minimum_volume:
        rejection_reasons.append(
            "VOLUME IS BELOW POLICY MINIMUM"
        )

    if contract.open_interest is None:
        if policy.require_open_interest:
            rejection_reasons.append(
                "OPEN INTEREST IS REQUIRED"
            )
        else:
            warnings.append(
                "OPEN INTEREST IS UNAVAILABLE"
            )
    elif (
        contract.open_interest
        < policy.minimum_open_interest
    ):
        rejection_reasons.append(
            "OPEN INTEREST IS BELOW POLICY MINIMUM"
        )

    if contract.implied_volatility is None:
        if policy.require_implied_volatility:
            rejection_reasons.append(
                "IMPLIED VOLATILITY IS REQUIRED"
            )
        else:
            warnings.append(
                "IMPLIED VOLATILITY IS UNAVAILABLE"
            )
    elif not (
        policy.minimum_implied_volatility
        <= contract.implied_volatility
        <= policy.maximum_implied_volatility
    ):
        rejection_reasons.append(
            "IMPLIED VOLATILITY IS OUTSIDE POLICY RANGE"
        )

    if rejection_reasons:
        return OptionContractCandidateV1(
            contract=contract,
            candidate_status="REJECTED",
            moneyness=moneyness,
            strike_distance_percent=(
                strike_distance_percent
            ),
            spread_percent=spread_percent,
            liquidity_score=0.0,
            proximity_score=0.0,
            open_interest_score=0.0,
            volume_score=0.0,
            spread_score=0.0,
            implied_volatility_score=0.0,
            intelligence_alignment_score=0.0,
            total_score=0.0,
            rejection_reasons=tuple(
                sorted(set(rejection_reasons))
            ),
            warnings=tuple(
                sorted(set(warnings))
            ),
        )

    proximity_score = _proximity_score(
        strike_distance_percent,
        policy.maximum_strike_distance_percent,
    )

    spread_score = _spread_score(
        spread_percent,
        policy.maximum_spread_percent,
    )

    volume_score = _threshold_score(
        contract.volume,
        policy.minimum_volume,
    )

    open_interest_score = _threshold_score(
        contract.open_interest,
        policy.minimum_open_interest,
    )

    implied_volatility_score = _iv_score(
        contract.implied_volatility,
        policy.minimum_implied_volatility,
        policy.maximum_implied_volatility,
    )

    liquidity_score = (
        spread_score
        + volume_score
        + open_interest_score
    ) / 3.0

    total_score = (
        liquidity_score
        * policy.liquidity_weight
        + proximity_score
        * policy.proximity_weight
        + open_interest_score
        * policy.open_interest_weight
        + volume_score
        * policy.volume_weight
        + spread_score
        * policy.spread_weight
        + implied_volatility_score
        * policy.implied_volatility_weight
        + intelligence_alignment_score
        * policy.intelligence_alignment_weight
    )

    status = (
        "ELIGIBLE_WITH_WARNINGS"
        if warnings
        else "ELIGIBLE"
    )

    return OptionContractCandidateV1(
        contract=contract,
        candidate_status=status,
        moneyness=moneyness,
        strike_distance_percent=strike_distance_percent,
        spread_percent=spread_percent,
        liquidity_score=_clamp(liquidity_score),
        proximity_score=_clamp(proximity_score),
        open_interest_score=_clamp(
            open_interest_score
        ),
        volume_score=_clamp(volume_score),
        spread_score=_clamp(spread_score),
        implied_volatility_score=_clamp(
            implied_volatility_score
        ),
        intelligence_alignment_score=_clamp(
            intelligence_alignment_score
        ),
        total_score=_clamp(total_score),
        rejection_reasons=(),
        warnings=tuple(sorted(set(warnings))),
    )


def _spread_percent(
    contract: OptionContractV1,
) -> float | None:
    bid = contract.bid_price
    ask = contract.ask_price

    if (
        bid is None
        or ask is None
        or bid <= 0.0
        or ask <= 0.0
        or ask < bid
    ):
        return None

    midpoint = (bid + ask) / 2.0

    if midpoint <= 0.0:
        return None

    return (ask - bid) / midpoint * 100.0


def _moneyness(
    *,
    option_type: str,
    strike: float,
    spot_price: float,
) -> str:
    distance_percent = (
        abs(strike - spot_price)
        / spot_price
        * 100.0
    )

    if distance_percent <= 0.25:
        return "ATM"

    if option_type == "CALL":
        return "ITM" if strike < spot_price else "OTM"

    if option_type == "PUT":
        return "ITM" if strike > spot_price else "OTM"

    return "UNKNOWN"


def _proximity_score(
    strike_distance_percent: float,
    maximum_distance_percent: float,
) -> float:
    return _clamp(
        1.0
        - (
            strike_distance_percent
            / maximum_distance_percent
        )
    )


def _spread_score(
    spread_percent: float | None,
    maximum_spread_percent: float,
) -> float:
    if spread_percent is None:
        return 0.0

    return _clamp(
        1.0
        - spread_percent
        / maximum_spread_percent
    )


def _threshold_score(
    value: float | None,
    minimum: float,
) -> float:
    if value is None:
        return 0.0

    if minimum == 0.0:
        return 1.0

    return _clamp(value / (minimum * 4.0))


def _iv_score(
    value: float | None,
    minimum: float,
    maximum: float,
) -> float:
    if value is None:
        return 0.0

    if maximum == minimum:
        return 1.0

    midpoint = (minimum + maximum) / 2.0
    half_range = (maximum - minimum) / 2.0

    if half_range == 0.0:
        return 1.0

    return _clamp(
        1.0 - abs(value - midpoint) / half_range
    )


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, float(value)))