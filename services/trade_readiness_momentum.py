"""
Trade Readiness Momentum Engine.

Analyzes chronological MarketCycleJournal entries to understand
whether the live market pipeline was gradually moving toward
trade readiness.

Research questions include:

- Was confidence improving?
- Were risk flags reducing?
- Was setup quality improving?
- Was directional bias stable?
- Did TRADE_READY appear after a measurable build-up?
- How many observed cycles occurred before trade readiness?
- Was readiness improving, deteriorating, flat, or mixed?

IMPORTANT:
- READ ONLY.
- RESEARCH AND OBSERVABILITY ONLY.
- DOES NOT authorize trades.
- DOES NOT reject trades.
- DOES NOT front-run the live decision engine.
- DOES NOT modify paper-trading state.
- DOES NOT place real orders.
"""

from copy import deepcopy


class TradeReadinessMomentum:
    """
    Analyze trade-readiness momentum from chronological
    market-cycle journal entries.
    """

    UNKNOWN = "UNKNOWN"

    MOMENTUM_BUILDING = "BUILDING"
    MOMENTUM_DETERIORATING = "DETERIORATING"
    MOMENTUM_FLAT = "FLAT"
    MOMENTUM_MIXED = "MIXED"
    MOMENTUM_UNAVAILABLE = "UNAVAILABLE"

    TRADE_READY = "TRADE_READY"

    SETUP_SCORES = {
        "NO_SETUP": 0.0,
        "NONE": 0.0,
        "WATCH": 20.0,
        "WATCHING": 20.0,
        "DEVELOPING": 40.0,
        "FORMING": 40.0,
        "PENDING_CONFIRMATION": 60.0,
        "CONFIRMING": 60.0,
        "CONFIRMED": 80.0,
        "TRADE_READY": 100.0,
        "READY": 100.0,
    }

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

    def _extract_risk_flags(
        self,
        entry,
    ):
        risk_flags = entry.get(
            "risk_flags"
        )

        if risk_flags is None:
            market_decision = entry.get(
                "market_decision"
            )

            if isinstance(
                market_decision,
                dict,
            ):
                risk_flags = market_decision.get(
                    "risk_flags"
                )

        if risk_flags is None:
            return []

        if isinstance(
            risk_flags,
            str,
        ):
            normalized = risk_flags.strip()

            return (
                [
                    normalized,
                ]
                if normalized
                else []
            )

        if isinstance(
            risk_flags,
            (
                list,
                tuple,
                set,
            ),
        ):
            return [
                str(
                    flag
                ).strip()
                for flag in risk_flags
                if str(
                    flag
                ).strip()
            ]

        return []

    def _extract_setup_status(
        self,
        entry,
    ):
        setup = (
            entry.get(
                "setup_status"
            )
            or entry.get(
                "setup"
            )
        )

        if isinstance(
            setup,
            dict,
        ):
            setup = (
                setup.get(
                    "status"
                )
                or setup.get(
                    "setup_status"
                )
                or setup.get(
                    "state"
                )
            )

        return self._normalize_label(
            setup
        )

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

    def _setup_score(
        self,
        setup_status,
    ):
        return self.SETUP_SCORES.get(
            setup_status,
            0.0,
        )

    def _risk_score(
        self,
        risk_flag_count,
    ):
        return max(
            0.0,
            100.0 - (
                float(
                    risk_flag_count
                )
                * 20.0
            ),
        )

    def _confidence_score(
        self,
        confidence,
    ):
        if confidence is None:
            return 0.0

        return max(
            0.0,
            min(
                100.0,
                float(
                    confidence
                ),
            ),
        )

    def _decision_score(
        self,
        decision,
    ):
        if decision == self.TRADE_READY:
            return 100.0

        if decision in {
            "TRADE",
            "BUY",
            "SELL",
        }:
            return 100.0

        if decision in {
            "WAIT",
            "WATCH",
            "HOLD",
        }:
            return 30.0

        return 0.0

    def _build_cycle_state(
        self,
        entry,
        index,
    ):
        decision = self._extract_decision(
            entry
        )

        direction = self._extract_direction(
            entry
        )

        confidence = self._extract_confidence(
            entry
        )

        risk_flags = self._extract_risk_flags(
            entry
        )

        setup_status = (
            self._extract_setup_status(
                entry
            )
        )

        confidence_score = (
            self._confidence_score(
                confidence
            )
        )

        risk_score = self._risk_score(
            len(
                risk_flags
            )
        )

        setup_score = self._setup_score(
            setup_status
        )

        decision_score = (
            self._decision_score(
                decision
            )
        )

        readiness_score = round(
            (
                confidence_score
                * 0.40
            )
            + (
                risk_score
                * 0.25
            )
            + (
                setup_score
                * 0.25
            )
            + (
                decision_score
                * 0.10
            ),
            2,
        )

        return {
            "index": index,
            "timestamp": (
                self._extract_timestamp(
                    entry
                )
            ),
            "decision": decision,
            "direction": direction,
            "confidence": confidence,
            "risk_flags": risk_flags,
            "risk_flag_count": len(
                risk_flags
            ),
            "setup_status": setup_status,
            "confidence_score": confidence_score,
            "risk_score": risk_score,
            "setup_score": setup_score,
            "decision_score": decision_score,
            "readiness_score": readiness_score,
        }

    def _determine_momentum(
        self,
        cycle_states,
    ):
        if len(
            cycle_states
        ) < 2:
            return self.MOMENTUM_UNAVAILABLE

        values = [
            state[
                "readiness_score"
            ]
            for state in cycle_states
        ]

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
            return self.MOMENTUM_BUILDING

        if (
            negative > 0
            and positive == 0
        ):
            return self.MOMENTUM_DETERIORATING

        if (
            positive == 0
            and negative == 0
        ):
            return self.MOMENTUM_FLAT

        return self.MOMENTUM_MIXED

    def _is_improving(
        self,
        values,
        *,
        lower_is_better=False,
    ):
        if len(
            values
        ) < 2:
            return None

        first = values[
            0
        ]

        final = values[
            -1
        ]

        if lower_is_better:
            return final < first

        return final > first

    def _direction_stability(
        self,
        cycle_states,
    ):
        directions = [
            state[
                "direction"
            ]
            for state in cycle_states
        ]

        if not directions:
            return {
                "stable": True,
                "changes": 0,
            }

        changes = sum(
            1
            for (
                previous,
                current,
            ) in zip(
                directions,
                directions[
                    1:
                ],
            )
            if current != previous
        )

        return {
            "stable": changes == 0,
            "changes": changes,
        }

    def _first_trade_ready(
        self,
        cycle_states,
    ):
        for state in cycle_states:
            if (
                state[
                    "decision"
                ]
                == self.TRADE_READY
            ):
                return deepcopy(
                    state
                )

        return None

    def _pre_trade_build_up(
        self,
        cycle_states,
        first_trade_ready,
    ):
        if first_trade_ready is None:
            return False

        trade_ready_index = (
            first_trade_ready[
                "index"
            ]
        )

        if trade_ready_index < 2:
            return False

        pre_trade_states = cycle_states[
            :trade_ready_index
        ]

        if len(
            pre_trade_states
        ) < 2:
            return False

        first_score = pre_trade_states[
            0
        ][
            "readiness_score"
        ]

        final_score = pre_trade_states[
            -1
        ][
            "readiness_score"
        ]

        score_improved = (
            final_score > first_score
        )

        confidence_values = [
            state[
                "confidence"
            ]
            for state in pre_trade_states
            if state[
                "confidence"
            ]
            is not None
        ]

        confidence_improved = (
            len(
                confidence_values
            )
            >= 2
            and confidence_values[
                -1
            ]
            > confidence_values[
                0
            ]
        )

        risk_counts = [
            state[
                "risk_flag_count"
            ]
            for state in pre_trade_states
        ]

        risk_improved = (
            len(
                risk_counts
            )
            >= 2
            and risk_counts[
                -1
            ]
            < risk_counts[
                0
            ]
        )

        setup_scores = [
            state[
                "setup_score"
            ]
            for state in pre_trade_states
        ]

        setup_improved = (
            len(
                setup_scores
            )
            >= 2
            and setup_scores[
                -1
            ]
            > setup_scores[
                0
            ]
        )

        supporting_signals = sum(
            [
                score_improved,
                confidence_improved,
                risk_improved,
                setup_improved,
            ]
        )

        return supporting_signals >= 2

    def analyze(
        self,
        entries,
        *,
        session_date=None,
    ):
        """
        Analyze trade-readiness momentum.
        """

        normalized_entries = (
            self._normalize_entries(
                entries
            )
        )

        cycle_states = [
            self._build_cycle_state(
                entry,
                index,
            )
            for (
                index,
                entry,
            ) in enumerate(
                normalized_entries
            )
        ]

        readiness_values = [
            state[
                "readiness_score"
            ]
            for state in cycle_states
        ]

        confidence_values = [
            state[
                "confidence"
            ]
            for state in cycle_states
            if state[
                "confidence"
            ]
            is not None
        ]

        risk_counts = [
            state[
                "risk_flag_count"
            ]
            for state in cycle_states
        ]

        setup_scores = [
            state[
                "setup_score"
            ]
            for state in cycle_states
        ]

        first_trade_ready = (
            self._first_trade_ready(
                cycle_states
            )
        )

        readiness_change = (
            round(
                readiness_values[
                    -1
                ]
                - readiness_values[
                    0
                ],
                2,
            )
            if readiness_values
            else None
        )

        confidence_change = (
            round(
                confidence_values[
                    -1
                ]
                - confidence_values[
                    0
                ],
                2,
            )
            if confidence_values
            else None
        )

        return {
            "status": "COMPLETED",
            "read_only": True,
            "session_date": session_date,
            "cycles_observed": len(
                cycle_states
            ),
            "momentum": (
                self._determine_momentum(
                    cycle_states
                )
            ),
            "readiness": {
                "first": (
                    readiness_values[
                        0
                    ]
                    if readiness_values
                    else None
                ),
                "final": (
                    readiness_values[
                        -1
                    ]
                    if readiness_values
                    else None
                ),
                "change": readiness_change,
            },
            "confidence": {
                "first": (
                    confidence_values[
                        0
                    ]
                    if confidence_values
                    else None
                ),
                "final": (
                    confidence_values[
                        -1
                    ]
                    if confidence_values
                    else None
                ),
                "change": confidence_change,
                "improving": (
                    self._is_improving(
                        confidence_values
                    )
                ),
            },
            "risk_flags": {
                "first_count": (
                    risk_counts[
                        0
                    ]
                    if risk_counts
                    else None
                ),
                "final_count": (
                    risk_counts[
                        -1
                    ]
                    if risk_counts
                    else None
                ),
                "improving": (
                    self._is_improving(
                        risk_counts,
                        lower_is_better=True,
                    )
                ),
            },
            "setup": {
                "first_score": (
                    setup_scores[
                        0
                    ]
                    if setup_scores
                    else None
                ),
                "final_score": (
                    setup_scores[
                        -1
                    ]
                    if setup_scores
                    else None
                ),
                "improving": (
                    self._is_improving(
                        setup_scores
                    )
                ),
            },
            "direction_stability": (
                self._direction_stability(
                    cycle_states
                )
            ),
            "trade_ready": {
                "observed": (
                    first_trade_ready
                    is not None
                ),
                "first_index": (
                    first_trade_ready[
                        "index"
                    ]
                    if first_trade_ready
                    else None
                ),
                "first_timestamp": (
                    first_trade_ready[
                        "timestamp"
                    ]
                    if first_trade_ready
                    else None
                ),
                "cycles_before": (
                    first_trade_ready[
                        "index"
                    ]
                    if first_trade_ready
                    else None
                ),
                "pre_trade_build_up_detected": (
                    self._pre_trade_build_up(
                        cycle_states,
                        first_trade_ready,
                    )
                ),
            },
            "cycle_states": cycle_states,
        }