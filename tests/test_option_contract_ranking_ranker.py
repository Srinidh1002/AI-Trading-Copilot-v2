from datetime import date, datetime, timedelta, timezone

import pytest

from services.contracts.option_contract_ranking_policy_v1 import (
    OptionContractRankingPolicyV1,
)
from services.contracts.option_contract_universe_v1 import (
    OptionContractUniverseV1,
)
from services.contracts.option_contract_v1 import OptionContractV1
from services.option_contract_ranking.ranker import (
    rank_option_contracts,
)


NOW = datetime(2026, 7, 27, tzinfo=timezone.utc)
EXPIRY = date(2026, 7, 30)


def make_contract(
    contract_id="c1",
    option_type="CALL",
    strike=25000,
    expiry_date=EXPIRY,
    **changes,
):
    values = dict(
        contract_id=contract_id,
        underlying_symbol="NIFTY",
        exchange="NSE",
        trading_symbol=f"{contract_id}-SYMBOL",
        option_type=option_type,
        strike=strike,
        expiry_date=expiry_date,
        lot_size=25,
        market_timestamp=NOW,
        last_price=100,
        bid_price=99,
        ask_price=101,
        open_interest=1000,
        volume=500,
        implied_volatility=18,
        tradable=True,
    )
    values.update(changes)
    return OptionContractV1(**values)


def make_universe(
    contracts=None,
    **changes,
):
    values = dict(
        universe_id="u1",
        underlying_symbol="NIFTY",
        exchange="NSE",
        captured_at=NOW,
        spot_price=25000,
        contracts=tuple(
            contracts
            if contracts is not None
            else (make_contract(),)
        ),
        source_name="synthetic",
        trusted=True,
    )
    values.update(changes)
    return OptionContractUniverseV1(**values)


def rank(
    universe=None,
    **kwargs,
):
    return rank_option_contracts(
        universe or make_universe(),
        directional_bias=kwargs.pop(
            "directional_bias",
            "BULLISH",
        ),
        now=kwargs.pop("now", NOW),
        ranking_id_factory=kwargs.pop(
            "ranking_id_factory",
            lambda: "r1",
        ),
        **kwargs,
    )


def test_bullish_ranking_selects_call():
    result = rank()

    assert result.ranking_status == "RANKED"
    assert result.required_option_type == "CALL"
    assert result.selected_candidate.contract.contract_id == "c1"


def test_bearish_ranking_selects_put():
    universe = make_universe(
        (make_contract(option_type="PUT"),)
    )

    result = rank(
        universe,
        directional_bias="BEARISH",
    )

    assert result.required_option_type == "PUT"
    assert result.selected_candidate.contract.option_type == "PUT"


@pytest.mark.parametrize(
    "bias",
    ["NEUTRAL", "MIXED", "UNAVAILABLE"],
)
def test_non_directional_bias_blocks_by_default(bias):
    result = rank(
        directional_bias=bias,
    )

    assert result.ranking_status == "BLOCKED"
    assert result.selected_candidate is None


def test_stale_universe_blocks():
    universe = make_universe(
        captured_at=NOW - timedelta(seconds=301)
    )

    result = rank(universe)

    assert result.ranking_status == "BLOCKED"
    assert "OPTION CONTRACT UNIVERSE IS STALE" in result.blockers


def test_future_universe_blocks():
    universe = make_universe(
        captured_at=NOW + timedelta(seconds=6)
    )

    result = rank(universe)

    assert result.ranking_status == "BLOCKED"


def test_untrusted_universe_blocks_in_strict_mode():
    result = rank(
        make_universe(trusted=False)
    )

    assert result.ranking_status == "BLOCKED"


def test_untrusted_universe_warns_in_lenient_mode():
    policy = OptionContractRankingPolicyV1(
        require_trusted_universe=False
    )

    result = rank(
        make_universe(trusted=False),
        policy=policy,
    )

    assert result.ranking_status == "RANKED_WITH_WARNINGS"
    assert result.warnings


def test_earliest_expiry_is_applied():
    contracts = (
        make_contract(
            contract_id="late",
            expiry_date=date(2026, 8, 6),
            strike=25000,
        ),
        make_contract(
            contract_id="early",
            expiry_date=EXPIRY,
            strike=25100,
        ),
    )

    result = rank(
        make_universe(contracts)
    )

    assert result.selected_candidate.contract.contract_id == "early"
    assert all(
        candidate.contract.expiry_date == EXPIRY
        for candidate in result.ranked_candidates
    )


def test_all_eligible_expiries_are_ranked():
    contracts = (
        make_contract(
            contract_id="early",
            expiry_date=EXPIRY,
        ),
        make_contract(
            contract_id="late",
            expiry_date=date(2026, 8, 6),
            strike=25100,
        ),
    )
    policy = OptionContractRankingPolicyV1(
        expiry_policy="ALL_ELIGIBLE"
    )

    result = rank(
        make_universe(contracts),
        policy=policy,
    )

    assert result.eligible_candidate_count == 2


def test_explicit_expiry_filter():
    requested = date(2026, 8, 6)
    contracts = (
        make_contract(
            contract_id="early",
            expiry_date=EXPIRY,
        ),
        make_contract(
            contract_id="late",
            expiry_date=requested,
        ),
    )

    result = rank(
        make_universe(contracts),
        requested_expiry=requested,
    )

    assert result.selected_candidate.contract.contract_id == "late"
    assert "EXPLICIT EXPIRY FILTER APPLIED" in result.diagnostics


def test_explicit_expiry_required_by_policy():
    policy = OptionContractRankingPolicyV1(
        expiry_policy="EXPLICIT_EXPIRY_ONLY"
    )

    result = rank(
        policy=policy
    )

    assert result.ranking_status == "BLOCKED"
    assert "EXPLICIT EXPIRY IS REQUIRED" in result.blockers


def test_missing_requested_expiry_is_insufficient_data():
    result = rank(
        requested_expiry=date(2026, 9, 1)
    )

    assert result.ranking_status == "INSUFFICIENT_DATA"


def test_no_eligible_contracts_returns_rejections():
    contract = make_contract(
        volume=1,
        open_interest=1,
    )

    result = rank(
        make_universe((contract,))
    )

    assert result.ranking_status == "NO_ELIGIBLE_CONTRACTS"
    assert result.rejected_candidate_count == 1


def test_empty_universe_is_insufficient_data():
    result = rank(
        make_universe(())
    )

    assert result.ranking_status == "INSUFFICIENT_DATA"


def test_ranking_order_prefers_higher_score():
    strong = make_contract(
        contract_id="strong",
        strike=25000,
        bid_price=99.5,
        ask_price=100.5,
        volume=5000,
        open_interest=5000,
    )
    weak = make_contract(
        contract_id="weak",
        strike=25100,
        bid_price=98,
        ask_price=102,
        volume=100,
        open_interest=500,
    )

    result = rank(
        make_universe((weak, strong))
    )

    assert result.ranked_candidates[0].contract.contract_id == "strong"


def test_ranking_limit_is_enforced():
    contracts = tuple(
        make_contract(
            contract_id=f"c{index}",
            strike=25000 + index,
        )
        for index in range(5)
    )
    policy = OptionContractRankingPolicyV1(
        maximum_ranked_candidates=2
    )

    result = rank(
        make_universe(contracts),
        policy=policy,
    )

    assert result.eligible_candidate_count == 2


def test_result_is_deterministic():
    universe = make_universe(
        (
            make_contract(
                contract_id="b",
                strike=25100,
            ),
            make_contract(
                contract_id="a",
                strike=24900,
            ),
        )
    )

    first = rank(universe)
    second = rank(universe)

    assert first.semantic_dict() == second.semantic_dict()


def test_intelligence_reference_is_preserved():
    result = rank(
        intelligence_result_id="i1"
    )

    assert result.intelligence_result_id == "i1"


@pytest.mark.parametrize(
    "field,value",
    [
        ("directional_bias", "UP"),
        ("now", datetime(2026, 7, 27)),
    ],
)
def test_invalid_inputs(field, value):
    with pytest.raises((TypeError, ValueError)):
        rank(**{field: value})


def test_universe_type_is_enforced():
    with pytest.raises(TypeError):
        rank_option_contracts(
            object(),
            directional_bias="BULLISH",
            now=NOW,
        )


def test_policy_type_is_enforced():
    with pytest.raises(TypeError):
        rank(
            policy=object()
        )