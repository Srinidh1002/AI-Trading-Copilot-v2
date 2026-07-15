"""
Decision Evolution Analyzer.

Analyzes chronological MarketCycleJournal entries to understand
how AI market decisions, direction, regime, and confidence evolved
during a market session.

Research questions include:

- Was confidence rising or falling?
- How much did confidence change?
- How many consecutive confidence increases occurred?
- Was market direction stable?
- Was market regime stable?
- How often did decision state change?
- At which cycle was peak confidence observed?
- What was the final observed AI state?

IMPORTANT:
- READ ONLY.
- DOES NOT authorize trades.
- DOES NOT reject trades.
- DOES NOT modify live pipeline state.
- DOES NOT modify paper-trading state.
- DOES NOT place real orders.
"""

from collections import Counter
from copy import deepcopy


class DecisionEvolutionAnalyzer:
    """
    Analyze chronological decision evolution.
    """

    UNKNOWN = "UNKNOWN"

    TREND_RISING = "RISING"
    TREND_FALLING = "FALLING"
    TREND_FLAT = "FLAT"
    TREND_MIXED = "MIXED"
    TREND_UNAVAILABLE = "UNAVAILABLE"

    def _normalize_entries(
        self,
        entries,
    ):
        if entries is None:
            return []

        if not isinstance(
            entries,
            (
                list,
                tuple,
            ),
        ):
            raise ValueError(
                "entries must be a list or tuple."
            )

        normalized = []

        for entry in entries:
            if not isinstance(
                entry,
                dict,
            ):
                continue

            normalized.append(
                deepcopy(
                    entry
                )
            )

        return normalized

    def _normalize_label(
        self,
        value,
    ):
        if value is None:
            return self.UNKNOWN

        normalized = str(
            value
        ).strip()

        if not normalized:
            return self.UNKNOWN

        return normalized.upper()

    def _extract_decision(
        self,
        entry,
    ):
        return self._normalize_label(
            entry.get(
                "decision"
            )
        )

    def _extract_direction(
        self,
        entry,
    ):
        return self._normalize_label(
            entry.get(
                "direction"
            )
        )

    def _extract_regime(
        self,
        entry,
    ):
        regime = entry.get(
            "regime"
        )

        if isinstance(
            regime,
            dict,
        ):
            regime = (
                regime.get(
                    "primary_regime"
                )
                or regime.get(
                    "regime"
                )
                or regime.get(
                    "name"
                )
            )

        return self._normalize_label(
            regime
        )

    def _extract_confidence(
        self,
        entry,
    ):
        confidence = entry.get(
            "direction_confidence"
        )

        if confidence is None:
            confidence = entry.get(
                "confidence"
            )

        if confidence is None:
            strategy = entry.get(
                "strategy"
            )

            if isinstance(
                strategy,
                dict,
            ):
                confidence = strategy.get(
                    "direction_confidence",
                    strategy.get(
                        "confidence"
                    ),
                )

        if isinstance(
            confidence,
            bool,
        ):
            return None

        try:
            return float(
                confidence
            )

        except (
            TypeError,
            ValueError,
        ):
            return None

    def _extract_timestamp(
        self,
        entry,
    ):
        value = (
            entry.get(
                "timestamp"
            )
            or entry.get(
                "recorded_at"
            )
            or entry.get(
                "created_at"
            )
        )

        if value is None:
            return None

        normalized = str(
            value
        ).strip()

        return (
            normalized
            if normalized
            else None
        )

    def _build_confidence_series(
        self,
        entries,
    ):
        series = []

        for (
            index,
            entry,
        ) in enumerate(
            entries
        ):
            confidence = (
                self._extract_confidence(
                    entry
                )
            )

            if confidence is None:
                continue

            series.append(
                {
                    "index": index,
                    "timestamp": (
                        self._extract_timestamp(
                            entry
                        )
                    ),
                    "confidence": confidence,
                }
            )

        return series

    def _determine_confidence_trend(
        self,
        confidence_series,
    ):
        values = [
            item[
                "confidence"
            ]
            for item in confidence_series
        ]

        if len(
            values
        ) < 2:
            return self.TREND_UNAVAILABLE

        differences = [
            current - previous
            for (
                previous,
                current,
            ) in zip(
                values,
                values[
                    1:
                ],
            )
        ]

        positive = sum(
            1
            for difference in differences
            if difference > 0
        )

        negative = sum(
            1
            for difference in differences
            if difference < 0
        )

        if (
            positive > 0
            and negative == 0
        ):
            return self.TREND_RISING

        if (
            negative > 0
            and positive == 0
        ):
            return self.TREND_FALLING

        if (
            positive == 0
            and negative == 0
        ):
            return self.TREND_FLAT

        return self.TREND_MIXED

    def _longest_increase_sequence(
        self,
        confidence_series,
    ):
        values = [
            item[
                "confidence"
            ]
            for item in confidence_series
        ]

        if len(
            values
        ) < 2:
            return 0

        longest = 0
        current = 0

        for (
            previous,
            value,
        ) in zip(
            values,
            values[
                1:
            ],
        ):
            if value > previous:
                current += 1
                longest = max(
                    longest,
                    current,
                )

            else:
                current = 0

        return longest

    def _longest_decrease_sequence(
        self,
        confidence_series,
    ):
        values = [
            item[
                "confidence"
            ]
            for item in confidence_series
        ]

        if len(
            values
        ) < 2:
            return 0

        longest = 0
        current = 0

        for (
            previous,
            value,
        ) in zip(
            values,
            values[
                1:
            ],
        ):
            if value < previous:
                current += 1
                longest = max(
                    longest,
                    current,
                )

            else:
                current = 0

        return longest

    def _build_state_stability(
        self,
        values,
    ):
        if not values:
            return {
                "stable": True,
                "unique_states": 0,
                "changes": 0,
                "distribution": {},
            }

        distribution = dict(
            Counter(
                values
            )
        )

        changes = sum(
            1
            for (
                previous,
                current,
            ) in zip(
                values,
                values[
                    1:
                ],
            )
            if current != previous
        )

        return {
            "stable": changes == 0,
            "unique_states": len(
                distribution
            ),
            "changes": changes,
            "distribution": distribution,
        }

    def _build_decision_evolution(
        self,
        decisions,
    ):
        if not decisions:
            return []

        evolution = [
            decisions[
                0
            ],
        ]

        for decision in decisions[
            1:
        ]:
            if decision != evolution[
                -1
            ]:
                evolution.append(
                    decision
                )

        return evolution

    def _build_peak_confidence(
        self,
        confidence_series,
    ):
        if not confidence_series:
            return {
                "value": None,
                "index": None,
                "timestamp": None,
            }

        peak = max(
            confidence_series,
            key=lambda item: item[
                "confidence"
            ],
        )

        return deepcopy(
            {
                "value": peak[
                    "confidence"
                ],
                "index": peak[
                    "index"
                ],
                "timestamp": peak[
                    "timestamp"
                ],
            }
        )

    def _build_lowest_confidence(
        self,
        confidence_series,
    ):
        if not confidence_series:
            return {
                "value": None,
                "index": None,
                "timestamp": None,
            }

        lowest = min(
            confidence_series,
            key=lambda item: item[
                "confidence"
            ],
        )

        return deepcopy(
            {
                "value": lowest[
                    "confidence"
                ],
                "index": lowest[
                    "index"
                ],
                "timestamp": lowest[
                    "timestamp"
                ],
            }
        )

    def analyze(
        self,
        entries,
        *,
        session_date=None,
    ):
        """
        Analyze chronological AI decision evolution.
        """

        normalized_entries = (
            self._normalize_entries(
                entries
            )
        )

        decisions = [
            self._extract_decision(
                entry
            )
            for entry in normalized_entries
        ]

        directions = [
            self._extract_direction(
                entry
            )
            for entry in normalized_entries
        ]

        regimes = [
            self._extract_regime(
                entry
            )
            for entry in normalized_entries
        ]

        confidence_series = (
            self._build_confidence_series(
                normalized_entries
            )
        )

        confidence_values = [
            item[
                "confidence"
            ]
            for item in confidence_series
        ]

        first_confidence = (
            confidence_values[
                0
            ]
            if confidence_values
            else None
        )

        final_confidence = (
            confidence_values[
                -1
            ]
            if confidence_values
            else None
        )

        confidence_change = (
            round(
                final_confidence
                - first_confidence,
                2,
            )
            if (
                first_confidence is not None
                and final_confidence is not None
            )
            else None
        )

        final_state = (
            {
                "decision": decisions[
                    -1
                ],
                "direction": directions[
                    -1
                ],
                "regime": regimes[
                    -1
                ],
                "confidence": (
                    self._extract_confidence(
                        normalized_entries[
                            -1
                        ]
                    )
                ),
                "timestamp": (
                    self._extract_timestamp(
                        normalized_entries[
                            -1
                        ]
                    )
                ),
            }
            if normalized_entries
            else {
                "decision": None,
                "direction": None,
                "regime": None,
                "confidence": None,
                "timestamp": None,
            }
        )

        return {
            "status": "COMPLETED",
            "read_only": True,
            "session_date": session_date,
            "cycles_observed": len(
                normalized_entries
            ),
            "confidence": {
                "observations": len(
                    confidence_series
                ),
                "trend": (
                    self._determine_confidence_trend(
                        confidence_series
                    )
                ),
                "first": first_confidence,
                "final": final_confidence,
                "change": confidence_change,
                "longest_increase_sequence": (
                    self._longest_increase_sequence(
                        confidence_series
                    )
                ),
                "longest_decrease_sequence": (
                    self._longest_decrease_sequence(
                        confidence_series
                    )
                ),
                "peak": (
                    self._build_peak_confidence(
                        confidence_series
                    )
                ),
                "lowest": (
                    self._build_lowest_confidence(
                        confidence_series
                    )
                ),
                "series": confidence_series,
            },
            "decision_evolution": (
                self._build_decision_evolution(
                    decisions
                )
            ),
            "decision_stability": (
                self._build_state_stability(
                    decisions
                )
            ),
            "direction_stability": (
                self._build_state_stability(
                    directions
                )
            ),
            "regime_stability": (
                self._build_state_stability(
                    regimes
                )
            ),
            "final_state": final_state,
        }