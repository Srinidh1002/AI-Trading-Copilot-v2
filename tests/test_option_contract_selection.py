from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import pytest

from services.contracts.option_contract_universe_v1 import (
    OptionContractUniverseV1,
)
from services.contracts.option_contract_v1 import OptionContractV1
from services.options.policies import OptionSelectionPolicy
from services.options.selection import select_option_contract


NOW = datetime(2026, 7, 27, 10, 0, tzinfo=timezone.utc)
DEFAULT_EXPIRY = date(2026, 7, 30)


@dataclass
class Decision:
    action: str = "BUY"
    authorization_status: str = "ANALYSIS_ONLY"
    snapshot_id: str = "snap"
    decision_id: str = "dec"
    symbol: str = "NIFTY"
    exchange: str = "NSE"


def make_contract(
    option_type: str = "CALL",
    strike: float = 25000,
    expiry_date: date = DEFAULT_EXPIRY,
    *,
    contract_id: str | None = None,
    trading_symbol: str | None = None,
    underlying_symbol: str = "NIFTY",
    exchange: str = "NSE",
    instrument_token: str | None = None,
    lot_size: int = 25,
    tick_size: float | None = 0.05,
    last_price: float | None = 100.0,
    bid_price: float | None = 99.0,
    ask_price: float | None = 101.0,
    open_interest: float | None = 1000.0,
    volume: float | None = 500.0,
    implied_volatility: float | None = 18.0,
    market_timestamp: datetime = NOW,
    tradable: bool = True,
    metadata: dict | None = None,
) -> OptionContractV1:
    resolved_id = (
        contract_id
        or (
            f"{underlying_symbol}-{exchange}-{option_type}-"
            f"{strike}-{expiry_date.isoformat()}"
        )
    )
    resolved_symbol = trading_symbol or resolved_id

    return OptionContractV1(
        contract_id=resolved_id,
        underlying_symbol=underlying_symbol,
        exchange=exchange,
        trading_symbol=resolved_symbol,
        instrument_token=instrument_token,
        option_type=option_type,
        strike=strike,
        expiry_date=expiry_date,
        lot_size=lot_size,
        tick_size=tick_size,
        last_price=last_price,
        bid_price=bid_price,
        ask_price=ask_price,
        open_interest=open_interest,
        volume=volume,
        implied_volatility=implied_volatility,
        market_timestamp=market_timestamp,
        tradable=tradable,
        metadata=metadata or {},
    )


def make_universe(
    contracts: tuple[OptionContractV1, ...] | None = None,
    *,
    universe_id: str = "universe-1",
    underlying_symbol: str = "NIFTY",
    exchange: str = "NSE",
    captured_at: datetime = NOW,
    spot_price: float = 25000,
    source_name: str = "synthetic",
    trusted: bool = True,
    warnings: tuple[str, ...] = (),
    metadata: dict | None = None,
) -> OptionContractUniverseV1:
    resolved_contracts = (
        contracts
        if contracts is not None
        else (
            make_contract(
                underlying_symbol=underlying_symbol,
                exchange=exchange,
            ),
        )
    )

    return OptionContractUniverseV1(
        universe_id=universe_id,
        underlying_symbol=underlying_symbol,
        exchange=exchange,
        captured_at=captured_at,
        spot_price=spot_price,
        contracts=tuple(resolved_contracts),
        source_name=source_name,
        trusted=trusted,
        warnings=warnings,
        metadata=metadata or {},
    )


def run_selection(
    decision: Decision | None = None,
    universe: OptionContractUniverseV1 | None = None,
    **kwargs,
):
    return select_option_contract(
        decision or Decision(),
        universe or make_universe(),
        now=NOW,
        **kwargs,
    )


@pytest.mark.parametrize(
    "symbol,exchange,action,option_type",
    [
        ("NIFTY", "NSE", "BUY", "CALL"),
        ("NIFTY", "NSE", "SELL", "PUT"),
        ("SENSEX", "BSE", "BUY", "CALL"),
        ("SENSEX", "BSE", "SELL", "PUT"),
    ],
)
def test_direction_mapping(symbol, exchange, action, option_type):
    decision = Decision(
        action=action,
        symbol=symbol,
        exchange=exchange,
    )
    contract = make_contract(
        option_type=option_type,
        underlying_symbol=symbol,
        exchange=exchange,
    )
    universe = make_universe(
        (contract,),
        underlying_symbol=symbol,
        exchange=exchange,
    )

    result = run_selection(decision, universe)

    assert result.selection_valid is True
    assert result.option_type == option_type


@pytest.mark.parametrize(
    "action",
    ["WAIT", "HOLD", "NEUTRAL", "UNKNOWN"],
)
def test_non_actionable_decisions_have_no_contract(action):
    result = run_selection(Decision(action=action))

    assert result.selection_valid is False
    assert result.universe_id is None
    assert result.contract_id is None
    assert result.trading_symbol is None
    assert result.expiry_date is None
    assert result.strike is None
    assert result.lot_size is None


def test_blocked_decision_has_no_contract():
    result = run_selection(
        Decision(authorization_status="BLOCKED")
    )

    assert result.selection_valid is False
    assert result.contract_id is None


def test_earliest_expiry_is_selected():
    contracts = (
        make_contract(
            "CALL",
            25100,
            date(2026, 8, 6),
        ),
        make_contract(
            "CALL",
            24900,
            date(2026, 7, 30),
        ),
        make_contract(
            "CALL",
            25100,
            date(2026, 7, 30),
        ),
    )

    result = run_selection(
        universe=make_universe(contracts)
    )

    assert result.selection_valid is True
    assert result.expiry_date == date(2026, 7, 30)


def test_explicit_expiry_is_selected():
    contracts = (
        make_contract(
            "CALL",
            24900,
            date(2026, 7, 30),
        ),
        make_contract(
            "CALL",
            25100,
            date(2026, 8, 6),
        ),
    )

    result = run_selection(
        universe=make_universe(contracts),
        requested_expiry=date(2026, 8, 6),
    )

    assert result.selection_valid is True
    assert result.expiry_date == date(2026, 8, 6)


def test_missing_explicit_expiry_blocks():
    contracts = (
        make_contract(
            "CALL",
            24900,
            date(2026, 7, 30),
        ),
    )

    result = run_selection(
        universe=make_universe(contracts),
        requested_expiry=date(2026, 9, 1),
    )

    assert result.selection_valid is False
    assert result.contract_id is None


def test_explicit_strike_is_selected():
    contracts = (
        make_contract("CALL", 24900),
        make_contract("CALL", 25100),
    )

    result = run_selection(
        universe=make_universe(contracts),
        requested_strike=24900,
    )

    assert result.selection_valid is True
    assert result.strike == 24900


def test_missing_explicit_strike_blocks():
    contracts = (
        make_contract("CALL", 24900),
        make_contract("CALL", 25100),
    )

    result = run_selection(
        universe=make_universe(contracts),
        requested_strike=25200,
    )

    assert result.selection_valid is False
    assert result.contract_id is None


def test_call_atm_tie_selects_lower_strike():
    contracts = (
        make_contract("CALL", 24900),
        make_contract("CALL", 25100),
    )

    result = run_selection(
        universe=make_universe(contracts)
    )

    assert result.selection_valid is True
    assert result.strike == 24900


def test_put_atm_tie_selects_higher_strike():
    contracts = (
        make_contract("PUT", 24900),
        make_contract("PUT", 25100),
    )

    result = run_selection(
        decision=Decision(action="SELL"),
        universe=make_universe(contracts),
    )

    assert result.selection_valid is True
    assert result.strike == 25100


@pytest.mark.parametrize(
    "policy,prices,expected_price,expected_source",
    [
        (
            "MID",
            {
                "bid_price": 90.0,
                "ask_price": 110.0,
                "last_price": None,
            },
            100.0,
            "MID",
        ),
        (
            "ASK",
            {
                "bid_price": None,
                "ask_price": 110.0,
                "last_price": None,
            },
            110.0,
            "ASK",
        ),
        (
            "LAST",
            {
                "bid_price": None,
                "ask_price": None,
                "last_price": 99.0,
            },
            99.0,
            "LAST",
        ),
        (
            "BEST_AVAILABLE",
            {
                "bid_price": 90.0,
                "ask_price": 110.0,
                "last_price": 99.0,
            },
            100.0,
            "MID",
        ),
        (
            "BEST_AVAILABLE",
            {
                "bid_price": None,
                "ask_price": 110.0,
                "last_price": 99.0,
            },
            110.0,
            "ASK",
        ),
        (
            "BEST_AVAILABLE",
            {
                "bid_price": None,
                "ask_price": None,
                "last_price": 99.0,
            },
            99.0,
            "LAST",
        ),
        (
            "BEST_AVAILABLE",
            {
                "bid_price": 90.0,
                "ask_price": None,
                "last_price": None,
            },
            90.0,
            "BID",
        ),
        (
            "BEST_AVAILABLE",
            {
                "bid_price": None,
                "ask_price": None,
                "last_price": None,
            },
            None,
            "UNAVAILABLE",
        ),
    ],
)
def test_reference_price_selection(
    policy,
    prices,
    expected_price,
    expected_source,
):
    contract = make_contract(**prices)
    universe = make_universe((contract,))
    selection_policy = OptionSelectionPolicy(
        reference_price_policy=policy
    )

    result = run_selection(
        universe=universe,
        policy=selection_policy,
    )

    assert result.selection_valid is True
    assert result.reference_option_price == expected_price
    assert result.reference_price_source == expected_source


@pytest.mark.parametrize(
    "universe_factory",
    [
        lambda: make_universe(()),
        lambda: make_universe(
            (
                make_contract(
                    market_timestamp=(
                        NOW - timedelta(seconds=301)
                    )
                ),
            )
        ),
        lambda: make_universe(
            (
                make_contract(tradable=False),
            )
        ),
        lambda: make_universe(
            (
                make_contract("PUT"),
            )
        ),
    ],
)
def test_invalid_universes_and_contracts_block(
    universe_factory,
):
    result = run_selection(
        universe=universe_factory()
    )

    assert result.selection_valid is False
    assert result.contract_id is None


def test_stale_universe_blocks():
    universe = make_universe(
        captured_at=NOW - timedelta(seconds=301)
    )

    result = run_selection(universe=universe)

    assert result.selection_valid is False


def test_future_universe_blocks():
    universe = make_universe(
        captured_at=NOW + timedelta(seconds=6)
    )

    result = run_selection(universe=universe)

    assert result.selection_valid is False


def test_untrusted_universe_blocks_in_strict_mode():
    universe = make_universe(trusted=False)

    result = run_selection(universe=universe)

    assert result.selection_valid is False


def test_untrusted_universe_warns_in_lenient_mode():
    universe = make_universe(trusted=False)
    policy = OptionSelectionPolicy(
        require_trusted_universe=False
    )

    result = run_selection(
        universe=universe,
        policy=policy,
    )

    assert result.selection_valid is True
    assert result.warnings


def test_injected_id_and_semantic_result_are_deterministic():
    first = run_selection(
        id_factory=lambda: "fixed-selection-id"
    )
    second = run_selection(
        id_factory=lambda: "fixed-selection-id"
    )

    assert first.selection_id == "fixed-selection-id"
    assert second.selection_id == "fixed-selection-id"
    assert first.semantic_dict() == second.semantic_dict()