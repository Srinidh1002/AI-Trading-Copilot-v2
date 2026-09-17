"""Deterministic replacement trade scenarios for Task 7A completion."""
from __future__ import annotations

from datetime import timedelta

from services.certification.replay_scenario_catalogue import (
    CATALOGUE_STARTED_AT,
)
from services.contracts.replay_certification_v1 import (
    ReplayScenarioV1,
)


_REPLACEMENT_TYPES = (
    "TRENDING_UP",
    "TRENDING_DOWN",
    "RANGE",
    "HIGH_VOLATILITY",
    "LOW_VOLATILITY",
    "GAP",
    "REVERSAL",
    "FALSE_BREAKOUT",
    "PARTIAL_EXITS",
    "ALL_TARGETS",
    "STOP_HIT",
    "EARLY_SAFETY_EXIT",
)

_EXPECTED_ACTIONS = {
    "TRENDING_UP": ("HOLD", "TARGET_3_HIT"),
    "TRENDING_DOWN": ("HOLD", "TARGET_3_HIT"),
    "RANGE": ("HOLD", "STOP_HIT"),
    "HIGH_VOLATILITY": ("HOLD_WITH_CAUTION", "EXIT_NOW"),
    "LOW_VOLATILITY": ("HOLD", "STOP_HIT"),
    "GAP": ("HOLD_WITH_CAUTION", "EXIT_NOW"),
    "REVERSAL": ("TARGET_1_HIT", "TARGET_2_HIT", "STOP_HIT"),
    "FALSE_BREAKOUT": ("HOLD_WITH_CAUTION", "STOP_HIT"),
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
}


def _build_market_replacements(
    market: tuple[str, str],
) -> tuple[ReplayScenarioV1, ...]:
    symbol, _ = market
    values = []

    for offset, scenario_type in enumerate(
        _REPLACEMENT_TYPES,
        start=1,
    ):
        sequence = 60 + offset
        scenario_id = (
            f"{symbol.lower()}-replacement-{offset:02d}"
        )

        values.append(
            ReplayScenarioV1(
                scenario_id=scenario_id,
                sequence=sequence,
                market=market,
                scenario_type=scenario_type,
                expected_outcome="CLOSED_TRADE",
                fixture_id=f"fixture-{scenario_id}",
                replay_started_at=(
                    CATALOGUE_STARTED_AT
                    + timedelta(
                        minutes=1000 + sequence,
                    )
                ),
                tags=(
                    "task-7a",
                    "replacement-trade",
                    symbol.lower(),
                    scenario_type.lower(),
                ),
                expected_actions=_EXPECTED_ACTIONS[
                    scenario_type
                ],
            )
        )

    return tuple(values)


def build_replacement_trade_scenarios(
) -> tuple[ReplayScenarioV1, ...]:
    return (
        *_build_market_replacements(
            ("NIFTY", "NSE"),
        ),
        *_build_market_replacements(
            ("SENSEX", "BSE"),
        ),
    )
