"""
Cross-Session Research Intelligence.

Analyzes archived DailyResearchReport outputs across multiple
market sessions.

The engine studies:

- decision persistence
- direction persistence
- market-regime persistence
- confidence evolution
- readiness evolution
- blocker recurrence
- trade-ready frequency
- strategy-regime research observations

IMPORTANT:
- READ ONLY.
- RESEARCH ONLY.
- DOES NOT authorize a trade.
- DOES NOT reject a trade.
- DOES NOT modify live pipeline state.
- DOES NOT modify paper-trading state.
- DOES NOT modify risk.
- DOES NOT tune strategy.
- DOES NOT retrain a model.
- DOES NOT place real orders.
"""

from collections import Counter
from copy import deepcopy


class CrossSessionResearchIntelligence:
    """
    Analyze DailyResearchReport outputs across market sessions.
    """

    UNKNOWN = "UNKNOWN"
    UNAVAILABLE = "UNAVAILABLE"

    TREND_RISING = "RISING"
    TREND_FALLING = "FALLING"
    TREND_FLAT = "FLAT"
    TREND_MIXED = "MIXED"
    TREND_UNAVAILABLE = "UNAVAILABLE"

    def _normalize_reports(
        self,
        reports,
    ):
        if reports is None:
            return []

        if not isinstance(
            reports,
            (
                list,
                tuple,
            ),
        ):
            raise ValueError(
                "reports must be a list or tuple."
            )

        normalized = []

        for report in reports:
            if not isinstance(
                report,
                dict,
            ):
                continue

            normalized.append(
                deepcopy(
                    report
                )
            )

        return normalized

    @staticmethod
    def _safe_mapping(
        value,
    ):
        if isinstance(
            value,
            dict,
        ):
            return value

        return {}

    @staticmethod
    def _safe_collection(
        value,
    ):
        if isinstance(
            value,
            (
                list,
                tuple,
            ),
        ):
            return list(
                value
            )

        return []

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

    @staticmethod
    def _numeric_value(
        value,
    ):
        if isinstance(
            value,
            bool,
        ):
            return None

        try:
            return float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):
            return None

    def _snapshot(
        self,
        report,
    ):
        return self._safe_mapping(
            report.get(
                "research_snapshot"
            )
        )

    def _session_date(
        self,
        report,
    ):
        value = report.get(
            "session_date"
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

    def _build_session_record(
        self,
        report,
        index,
    ):
        snapshot = self._snapshot(
            report
        )

        final_blocker_state = (
            self._safe_mapping(
                snapshot.get(
                    "final_blocker_state"
                )
            )
        )

        blockers = [
            self._normalize_label(
                blocker
            )
            for blocker in (
                self._safe_collection(
                    final_blocker_state.get(
                        "blockers"
                    )
                )
            )
        ]

        blockers = [
            blocker
            for blocker in blockers
            if blocker != self.UNKNOWN
        ]

        return {
            "index": index,
            "session_date": (
                self._session_date(
                    report
                )
            ),
            "cycles_observed": (
                report.get(
                    "cycles_observed"
                )
            ),
            "trades_observed": (
                report.get(
                    "trades_observed"
                )
            ),
            "decision": (
                self._normalize_label(
                    snapshot.get(
                        "final_decision"
                    )
                )
            ),
            "direction": (
                self._normalize_label(
                    snapshot.get(
                        "final_direction"
                    )
                )
            ),
            "regime": (
                self._normalize_label(
                    snapshot.get(
                        "final_regime"
                    )
                )
            ),
            "confidence": (
                self._numeric_value(
                    snapshot.get(
                        "final_confidence"
                    )
                )
            ),
            "confidence_trend": (
                self._normalize_label(
                    snapshot.get(
                        "confidence_trend"
                    )
                )
            ),
            "readiness": (
                self._numeric_value(
                    snapshot.get(
                        "final_readiness"
                    )
                )
            ),
            "readiness_momentum": (
                self._normalize_label(
                    snapshot.get(
                        "readiness_momentum"
                    )
                )
            ),
            "risk_flag_count": (
                self._numeric_value(
                    snapshot.get(
                        "final_risk_flag_count"
                    )
                )
            ),
            "setup_score": (
                self._numeric_value(
                    snapshot.get(
                        "final_setup_score"
                    )
                )
            ),
            "trade_ready_observed": (
                snapshot.get(
                    "trade_ready_observed"
                )
                is True
            ),
            "final_blocked": (
                snapshot.get(
                    "final_blocked"
                )
                is True
            ),
            "final_blockers": blockers,
            "positive_strategy_regime_combinations": (
                self._numeric_value(
                    snapshot.get(
                        "positive_strategy_regime_combinations"
                    )
                )
            ),
            "negative_strategy_regime_combinations": (
                self._numeric_value(
                    snapshot.get(
                        "negative_strategy_regime_combinations"
                    )
                )
            ),
            "best_observed_combination": deepcopy(
                snapshot.get(
                    "best_observed_combination"
                )
            ),
            "worst_observed_combination": deepcopy(
                snapshot.get(
                    "worst_observed_combination"
                )
            ),
        }

    def _build_distribution(
        self,
        records,
        key,
    ):
        counter = Counter(
            record[
                key
            ]
            for record in records
            if record[
                key
            ]
            != self.UNKNOWN
        )

        return [
            {
                key: value,
                "count": count,
            }
            for (
                value,
                count,
            ) in counter.most_common()
        ]

    def _dominant_value(
        self,
        records,
        key,
    ):
        values = [
            record[
                key
            ]
            for record in records
            if record[
                key
            ]
            != self.UNKNOWN
        ]

        if not values:
            return None

        counter = Counter(
            values
        )

        value, count = (
            counter.most_common(
                1
            )[0]
        )

        return {
            key: value,
            "count": count,
            "sessions_observed": len(
                values
            ),
            "persistence_percent": round(
                (
                    count
                    / len(
                        values
                    )
                )
                * 100.0,
                2,
            ),
        }

    def _build_transitions(
        self,
        records,
        key,
    ):
        counter = Counter()

        for (
            previous,
            current,
        ) in zip(
            records,
            records[
                1:
            ],
        ):
            source = previous[
                key
            ]

            destination = current[
                key
            ]

            if (
                source == self.UNKNOWN
                or destination == self.UNKNOWN
            ):
                continue

            if source == destination:
                continue

            counter[
                (
                    source,
                    destination,
                )
            ] += 1

        return [
            {
                "from": source,
                "to": destination,
                "count": count,
            }
            for (
                source,
                destination,
            ), count in counter.most_common()
        ]

    def _longest_streak(
        self,
        records,
        key,
    ):
        best_value = None
        best_count = 0
        best_start = None
        best_end = None

        current_value = None
        current_count = 0
        current_start = None

        for (
            index,
            record,
        ) in enumerate(
            records
        ):
            value = record[
                key
            ]

            if value == self.UNKNOWN:
                current_value = None
                current_count = 0
                current_start = None
                continue

            if value == current_value:
                current_count += 1

            else:
                current_value = value
                current_count = 1
                current_start = index

            if current_count > best_count:
                best_value = current_value
                best_count = current_count
                best_start = current_start
                best_end = index

        return {
            key: best_value,
            "sessions": best_count,
            "start_index": best_start,
            "end_index": best_end,
        }

    def _numeric_series(
        self,
        records,
        key,
    ):
        return [
            {
                "index": record[
                    "index"
                ],
                "session_date": record[
                    "session_date"
                ],
                "value": record[
                    key
                ],
            }
            for record in records
            if record[
                key
            ]
            is not None
        ]

    def _determine_numeric_trend(
        self,
        series,
    ):
        values = [
            item[
                "value"
            ]
            for item in series
        ]

        if len(
            values
        ) < 2:
            return self.TREND_UNAVAILABLE

        increases = 0
        decreases = 0

        for (
            previous,
            current,
        ) in zip(
            values,
            values[
                1:
            ],
        ):
            if current > previous:
                increases += 1

            elif current < previous:
                decreases += 1

        if (
            increases > 0
            and decreases == 0
        ):
            return self.TREND_RISING

        if (
            decreases > 0
            and increases == 0
        ):
            return self.TREND_FALLING

        if (
            increases == 0
            and decreases == 0
        ):
            return self.TREND_FLAT

        return self.TREND_MIXED

    def _numeric_intelligence(
        self,
        records,
        key,
    ):
        series = self._numeric_series(
            records,
            key,
        )

        values = [
            item[
                "value"
            ]
            for item in series
        ]

        return {
            "observations": len(
                values
            ),
            "first": (
                values[
                    0
                ]
                if values
                else None
            ),
            "final": (
                values[
                    -1
                ]
                if values
                else None
            ),
            "minimum": (
                min(
                    values
                )
                if values
                else None
            ),
            "maximum": (
                max(
                    values
                )
                if values
                else None
            ),
            "average": (
                round(
                    sum(
                        values
                    )
                    / len(
                        values
                    ),
                    4,
                )
                if values
                else None
            ),
            "change": (
                round(
                    values[
                        -1
                    ]
                    - values[
                        0
                    ],
                    4,
                )
                if len(
                    values
                ) >= 2
                else None
            ),
            "trend": (
                self._determine_numeric_trend(
                    series
                )
            ),
            "series": series,
        }

    def _build_blocker_recurrence(
        self,
        reports,
    ):
        counter = Counter()

        session_counter = Counter()

        for report in reports:
            blocker_intelligence = (
                self._safe_mapping(
                    report.get(
                        "blocker_intelligence"
                    )
                )
            )

            statistics = (
                self._safe_collection(
                    blocker_intelligence.get(
                        "blocker_statistics"
                    )
                )
            )

            session_blockers = set()

            for statistic in statistics:
                if not isinstance(
                    statistic,
                    dict,
                ):
                    continue

                blocker = (
                    self._normalize_label(
                        statistic.get(
                            "blocker"
                        )
                    )
                )

                if blocker == self.UNKNOWN:
                    continue

                occurrences = (
                    self._numeric_value(
                        statistic.get(
                            "occurrences"
                        )
                    )
                )

                if occurrences is None:
                    occurrences = 0.0

                counter[
                    blocker
                ] += occurrences

                session_blockers.add(
                    blocker
                )

            for blocker in session_blockers:
                session_counter[
                    blocker
                ] += 1

        blockers = []

        for (
            blocker,
            occurrences,
        ) in counter.most_common():
            blockers.append(
                {
                    "blocker": blocker,
                    "occurrences": occurrences,
                    "sessions_observed": (
                        session_counter[
                            blocker
                        ]
                    ),
                }
            )

        return blockers

    def _build_final_blocker_recurrence(
        self,
        records,
    ):
        counter = Counter()

        for record in records:
            counter.update(
                set(
                    record[
                        "final_blockers"
                    ]
                )
            )

        return [
            {
                "blocker": blocker,
                "sessions": sessions,
                "persistence_percent": round(
                    (
                        sessions
                        / len(
                            records
                        )
                    )
                    * 100.0,
                    2,
                ),
            }
            for (
                blocker,
                sessions,
            ) in counter.most_common()
        ]

    def _build_trade_ready_intelligence(
        self,
        records,
    ):
        observed_records = [
            record
            for record in records
            if record[
                "trade_ready_observed"
            ]
        ]

        return {
            "sessions_observed": len(
                records
            ),
            "trade_ready_sessions": len(
                observed_records
            ),
            "trade_ready_frequency_percent": (
                round(
                    (
                        len(
                            observed_records
                        )
                        / len(
                            records
                        )
                    )
                    * 100.0,
                    2,
                )
                if records
                else 0.0
            ),
            "first_trade_ready_session": (
                deepcopy(
                    observed_records[
                        0
                    ]
                )
                if observed_records
                else None
            ),
            "last_trade_ready_session": (
                deepcopy(
                    observed_records[
                        -1
                    ]
                )
                if observed_records
                else None
            ),
        }

    def _build_strategy_regime_observations(
        self,
        reports,
    ):
        positive_counter = Counter()

        negative_counter = Counter()

        for report in reports:
            performance = (
                self._safe_mapping(
                    report.get(
                        "strategy_regime_performance"
                    )
                )
            )

            positive = (
                self._safe_collection(
                    performance.get(
                        "positive_combinations"
                    )
                )
            )

            negative = (
                self._safe_collection(
                    performance.get(
                        "negative_combinations"
                    )
                )
            )

            for combination in positive:
                if not isinstance(
                    combination,
                    dict,
                ):
                    continue

                regime = (
                    self._normalize_label(
                        combination.get(
                            "market_regime"
                        )
                    )
                )

                strategy = (
                    self._normalize_label(
                        combination.get(
                            "strategy"
                        )
                    )
                )

                positive_counter[
                    (
                        regime,
                        strategy,
                    )
                ] += 1

            for combination in negative:
                if not isinstance(
                    combination,
                    dict,
                ):
                    continue

                regime = (
                    self._normalize_label(
                        combination.get(
                            "market_regime"
                        )
                    )
                )

                strategy = (
                    self._normalize_label(
                        combination.get(
                            "strategy"
                        )
                    )
                )

                negative_counter[
                    (
                        regime,
                        strategy,
                    )
                ] += 1

        return {
            "positive": [
                {
                    "market_regime": regime,
                    "strategy": strategy,
                    "sessions_observed": count,
                }
                for (
                    regime,
                    strategy,
                ), count in (
                    positive_counter.most_common()
                )
            ],
            "negative": [
                {
                    "market_regime": regime,
                    "strategy": strategy,
                    "sessions_observed": count,
                }
                for (
                    regime,
                    strategy,
                ), count in (
                    negative_counter.most_common()
                )
            ],
        }

    def _build_observations(
        self,
        records,
        decision,
        direction,
        regime,
        confidence,
        readiness,
        blockers,
        trade_ready,
        strategy_regime,
    ):
        observations = []

        seen = set()

        def append(
            message,
        ):
            if message not in seen:
                observations.append(
                    message
                )
                seen.add(
                    message
                )

        if not records:
            append(
                "No archived research sessions were observed."
            )

            return observations

        dominant_decision = decision.get(
            "dominant"
        )

        if (
            isinstance(
                dominant_decision,
                dict,
            )
            and dominant_decision.get(
                "persistence_percent"
            )
            is not None
        ):
            persistence = (
                dominant_decision[
                    "persistence_percent"
                ]
            )

            if persistence >= 75.0:
                append(
                    "A dominant final decision persisted "
                    "across most observed sessions."
                )

        dominant_direction = direction.get(
            "dominant"
        )

        if (
            isinstance(
                dominant_direction,
                dict,
            )
            and dominant_direction.get(
                "persistence_percent"
            )
            is not None
            and dominant_direction[
                "persistence_percent"
            ]
            >= 75.0
        ):
            append(
                "A dominant market direction persisted "
                "across most observed sessions."
            )

        dominant_regime = regime.get(
            "dominant"
        )

        if (
            isinstance(
                dominant_regime,
                dict,
            )
            and dominant_regime.get(
                "persistence_percent"
            )
            is not None
            and dominant_regime[
                "persistence_percent"
            ]
            >= 75.0
        ):
            append(
                "A dominant market regime persisted "
                "across most observed sessions."
            )

        if confidence.get(
            "trend"
        ) == self.TREND_RISING:
            append(
                "Final session confidence increased "
                "across the observed research window."
            )

        elif confidence.get(
            "trend"
        ) == self.TREND_FALLING:
            append(
                "Final session confidence decreased "
                "across the observed research window."
            )

        if readiness.get(
            "trend"
        ) == self.TREND_RISING:
            append(
                "Final trade readiness improved "
                "across the observed research window."
            )

        elif readiness.get(
            "trend"
        ) == self.TREND_FALLING:
            append(
                "Final trade readiness weakened "
                "across the observed research window."
            )

        if blockers:
            append(
                "One or more blockers recurred "
                "across archived market sessions."
            )

        if (
            trade_ready.get(
                "trade_ready_sessions",
                0,
            )
            == 0
        ):
            append(
                "No archived session observed "
                "a TRADE_READY state."
            )

        elif (
            trade_ready.get(
                "trade_ready_frequency_percent",
                0.0,
            )
            >= 50.0
        ):
            append(
                "TRADE_READY was observed in at least "
                "half of archived sessions."
            )

        if strategy_regime.get(
            "positive"
        ):
            append(
                "A historically positive strategy-regime "
                "combination recurred across reports."
            )

        if strategy_regime.get(
            "negative"
        ):
            append(
                "A historically negative strategy-regime "
                "combination recurred across reports."
            )

        return observations

    def analyze(
        self,
        reports,
    ):
        """
        Analyze archived daily research reports.

        The returned result is descriptive research only.
        """

        normalized_reports = (
            self._normalize_reports(
                reports
            )
        )

        records = [
            self._build_session_record(
                report,
                index,
            )
            for (
                index,
                report,
            ) in enumerate(
                normalized_reports
            )
        ]

        decision_intelligence = {
            "distribution": (
                self._build_distribution(
                    records,
                    "decision",
                )
            ),
            "dominant": (
                self._dominant_value(
                    records,
                    "decision",
                )
            ),
            "transitions": (
                self._build_transitions(
                    records,
                    "decision",
                )
            ),
            "longest_streak": (
                self._longest_streak(
                    records,
                    "decision",
                )
            ),
        }

        direction_intelligence = {
            "distribution": (
                self._build_distribution(
                    records,
                    "direction",
                )
            ),
            "dominant": (
                self._dominant_value(
                    records,
                    "direction",
                )
            ),
            "transitions": (
                self._build_transitions(
                    records,
                    "direction",
                )
            ),
            "longest_streak": (
                self._longest_streak(
                    records,
                    "direction",
                )
            ),
        }

        regime_intelligence = {
            "distribution": (
                self._build_distribution(
                    records,
                    "regime",
                )
            ),
            "dominant": (
                self._dominant_value(
                    records,
                    "regime",
                )
            ),
            "transitions": (
                self._build_transitions(
                    records,
                    "regime",
                )
            ),
            "longest_streak": (
                self._longest_streak(
                    records,
                    "regime",
                )
            ),
        }

        confidence_intelligence = (
            self._numeric_intelligence(
                records,
                "confidence",
            )
        )

        readiness_intelligence = (
            self._numeric_intelligence(
                records,
                "readiness",
            )
        )

        risk_flag_intelligence = (
            self._numeric_intelligence(
                records,
                "risk_flag_count",
            )
        )

        setup_score_intelligence = (
            self._numeric_intelligence(
                records,
                "setup_score",
            )
        )

        blocker_recurrence = (
            self._build_blocker_recurrence(
                normalized_reports
            )
        )

        final_blocker_recurrence = (
            self._build_final_blocker_recurrence(
                records
            )
        )

        trade_ready_intelligence = (
            self._build_trade_ready_intelligence(
                records
            )
        )

        strategy_regime_observations = (
            self._build_strategy_regime_observations(
                normalized_reports
            )
        )

        observations = (
            self._build_observations(
                records,
                decision_intelligence,
                direction_intelligence,
                regime_intelligence,
                confidence_intelligence,
                readiness_intelligence,
                blocker_recurrence,
                trade_ready_intelligence,
                strategy_regime_observations,
            )
        )

        return {
            "status": "COMPLETED",
            "read_only": True,
            "research_only": True,
            "sessions_observed": len(
                records
            ),
            "session_dates": [
                record[
                    "session_date"
                ]
                for record in records
                if record[
                    "session_date"
                ]
                is not None
            ],
            "decision_intelligence": (
                decision_intelligence
            ),
            "direction_intelligence": (
                direction_intelligence
            ),
            "regime_intelligence": (
                regime_intelligence
            ),
            "confidence_intelligence": (
                confidence_intelligence
            ),
            "readiness_intelligence": (
                readiness_intelligence
            ),
            "risk_flag_intelligence": (
                risk_flag_intelligence
            ),
            "setup_score_intelligence": (
                setup_score_intelligence
            ),
            "blocker_recurrence": (
                blocker_recurrence
            ),
            "final_blocker_recurrence": (
                final_blocker_recurrence
            ),
            "trade_ready_intelligence": (
                trade_ready_intelligence
            ),
            "strategy_regime_observations": (
                strategy_regime_observations
            ),
            "research_observations": (
                observations
            ),
            "session_records": records,
        }