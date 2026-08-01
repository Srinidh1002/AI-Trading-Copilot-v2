"""Deterministic Task 7A replay scenario catalogue."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.contracts.replay_certification_v1 import ReplayScenarioV1


CATALOGUE_STARTED_AT = datetime(
    2026,
    8,
    2,
    0,
    0,
    tzinfo=timezone.utc,
)

REQUIRED_SCENARIO_TYPES = (
    "TRENDING_UP",
    "TRENDING_DOWN",
    "RANGE",
    "HIGH_VOLATILITY",
    "LOW_VOLATILITY",
    "GAP",
    "REVERSAL",
    "FALSE_BREAKOUT",
    "STALE_DATA",
    "MISSING_OPTION_CHAIN",
    "ONE_MARKET_UNAVAILABLE",
    "BOTH_BLOCKED",
    "DUPLICATE_ENTRY",
    "PARTIAL_EXITS",
    "ALL_TARGETS",
    "STOP_HIT",
    "EARLY_SAFETY_EXIT",
    "RESTART_RECOVERY",
)

_MARKETS = (
    ("NIFTY", "NSE"),
    ("SENSEX", "BSE"),
)

_CLOSED_TRADE_TYPES = {
    "TRENDING_UP",
    "TRENDING_DOWN",
    "RANGE",
    "HIGH_VOLATILITY",
    "LOW_VOLATILITY",
    "GAP",
    "REVERSAL",
    "FALSE_BREAKOUT",
    "DUPLICATE_ENTRY",
    "PARTIAL_EXITS",
    "ALL_TARGETS",
    "STOP_HIT",
    "EARLY_SAFETY_EXIT",
    "RESTART_RECOVERY",
}

_NON_TRADE_OUTCOMES = {
    "STALE_DATA": "NO_TRADE",
    "MISSING_OPTION_CHAIN": "NO_TRADE",
    "ONE_MARKET_UNAVAILABLE": "BLOCKED",
    "BOTH_BLOCKED": "BLOCKED",
}

_EXPECTED_ACTIONS = {
    "TRENDING_UP": ("HOLD", "TARGET_3_HIT"),
    "TRENDING_DOWN": ("HOLD", "TARGET_3_HIT"),
    "RANGE": ("HOLD", "STOP_HIT"),
    "HIGH_VOLATILITY": ("HOLD_WITH_CAUTION", "EXIT_NOW"),
    "LOW_VOLATILITY": ("HOLD", "TARGET_1_HIT", "STOP_HIT"),
    "GAP": ("HOLD_WITH_CAUTION", "EXIT_NOW"),
    "REVERSAL": ("HOLD", "TARGET_2_HIT", "EXIT_NOW"),
    "FALSE_BREAKOUT": ("HOLD_WITH_CAUTION", "STOP_HIT"),
    "STALE_DATA": ("NO_TRADE",),
    "MISSING_OPTION_CHAIN": ("NO_TRADE",),
    "ONE_MARKET_UNAVAILABLE": ("BLOCKED",),
    "BOTH_BLOCKED": ("BLOCKED",),
    "DUPLICATE_ENTRY": ("HOLD", "TRADE_CLOSED"),
    "PARTIAL_EXITS": (
        "TARGET_1_HIT",
        "TARGET_2_HIT",
        "TARGET_3_HIT",
    ),
    "ALL_TARGETS": (
        "TARGET_1_HIT",
        "TARGET_2_HIT",
        "TARGET_3_HIT",
    ),
    "STOP_HIT": ("STOP_HIT",),
    "EARLY_SAFETY_EXIT": ("EXIT_NOW",),
    "RESTART_RECOVERY": ("HOLD", "TRADE_CLOSED"),
}


def _expected_outcome(scenario_type: str) -> str:
    if scenario_type in _CLOSED_TRADE_TYPES:
        return "CLOSED_TRADE"
    return _NON_TRADE_OUTCOMES[scenario_type]


def _scenario_type_for_sequence(sequence: int) -> str:
    return REQUIRED_SCENARIO_TYPES[
        (sequence - 1) % len(REQUIRED_SCENARIO_TYPES)
    ]


def _build_market_scenarios(
    market: tuple[str, str],
    *,
    total: int = 60,
) -> tuple[ReplayScenarioV1, ...]:
    if (
        type(total) is not int
        or isinstance(total, bool)
        or total <= 0
    ):
        raise ValueError("total")

    symbol, exchange = market
    values = []

    for sequence in range(1, total + 1):
        scenario_type = _scenario_type_for_sequence(sequence)
        scenario_id = f"{symbol.lower()}-{sequence:03d}"

        values.append(
            ReplayScenarioV1(
                scenario_id=scenario_id,
                sequence=sequence,
                market=market,
                scenario_type=scenario_type,
                expected_outcome=_expected_outcome(
                    scenario_type
                ),
                fixture_id=f"fixture-{scenario_id}",
                replay_started_at=(
                    CATALOGUE_STARTED_AT
                    + timedelta(
                        minutes=sequence,
                    )
                ),
                tags=(
                    "task-7a",
                    "deterministic",
                    symbol.lower(),
                    scenario_type.lower(),
                ),
                expected_actions=_EXPECTED_ACTIONS[
                    scenario_type
                ],
            )
        )

    return tuple(values)


def build_replay_scenario_catalogue(
    *,
    closed_trade_target_per_market: int = 60,
) -> tuple[ReplayScenarioV1, ...]:
    """Return the immutable two-market replay catalogue.

    The closed trade target is represented separately from the
    non-trade safety catalogue.  This function builds the fixed
    60-case base catalogue per market. Later runner slices may
    deterministically add replacement trade cases when a base case
    intentionally yields NO_TRADE or BLOCKED.
    """
    if closed_trade_target_per_market != 60:
        raise ValueError(
            "Task 7A requires exactly 60 base scenarios per market"
        )

    return tuple(
        scenario
        for market in _MARKETS
        for scenario in _build_market_scenarios(
            market,
            total=closed_trade_target_per_market,
        )
    )


def scenarios_for_market(
    catalogue: tuple[ReplayScenarioV1, ...],
    market: tuple[str, str],
) -> tuple[ReplayScenarioV1, ...]:
    return tuple(
        scenario
        for scenario in catalogue
        if scenario.market == market
    )


def scenario_coverage(
    catalogue: tuple[ReplayScenarioV1, ...],
) -> dict[str, int]:
    counts = {
        scenario_type: 0
        for scenario_type in REQUIRED_SCENARIO_TYPES
    }
    for scenario in catalogue:
        counts[scenario.scenario_type] += 1
    return counts
