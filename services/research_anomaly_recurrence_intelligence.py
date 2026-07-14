"""
Research Anomaly Recurrence Intelligence.

READ ONLY.
RESEARCH ONLY.

This service analyses anomaly observations across archived
research sessions.

It does not:

- place orders
- authorize trades
- reject trades
- mutate paper-trading state
- change risk limits
- modify confidence
- tune strategies
- retrain models
"""

from collections import Counter
from copy import deepcopy


class ResearchAnomalyRecurrenceIntelligence:
    """
    Analyse recurrence of research anomaly patterns across
    historical session records.
    """

    INVALID_CATEGORY_VALUES = {
        "",
        "UNKNOWN",
        "UNAVAILABLE",
        "NONE",
        "NULL",
    }

    def analyze(
        self,
        sessions=None,
    ):
        normalized_sessions = self._normalize_sessions(
            sessions
        )

        session_records = []

        for index, session in enumerate(
            normalized_sessions
        ):
            session_records.append(
                self._build_session_record(
                    index=index,
                    session=session,
                )
            )

        anomaly_recurrence = (
            self._build_anomaly_recurrence(
                session_records
            )
        )

        combination_recurrence = (
            self._build_combination_recurrence(
                session_records
            )
        )

        current_pattern = (
            self._build_current_pattern(
                session_records=session_records,
                anomaly_recurrence=(
                    anomaly_recurrence
                ),
                combination_recurrence=(
                    combination_recurrence
                ),
            )
        )

        research_observations = (
            self._build_research_observations(
                session_records=session_records,
                anomaly_recurrence=(
                    anomaly_recurrence
                ),
                combination_recurrence=(
                    combination_recurrence
                ),
                current_pattern=current_pattern,
            )
        )

        return {
            "status": "COMPLETED",
            "read_only": True,
            "research_only": True,
            "sessions_observed": len(
                session_records
            ),
            "sessions_with_anomalies": sum(
                1
                for record in session_records
                if record["anomaly_detected"]
            ),
            "unique_anomaly_codes": len(
                anomaly_recurrence
            ),
            "anomaly_recurrence": (
                anomaly_recurrence
            ),
            "combination_recurrence": (
                combination_recurrence
            ),
            "current_pattern": current_pattern,
            "research_observations": (
                research_observations
            ),
            "session_records": deepcopy(
                session_records
            ),
        }

    def analyse(
        self,
        sessions=None,
    ):
        return self.analyze(sessions)

    def _normalize_sessions(
        self,
        sessions,
    ):
        if not isinstance(sessions, list):
            return []

        return [
            deepcopy(session)
            for session in sessions
            if isinstance(session, dict)
        ]

    def _build_session_record(
        self,
        *,
        index,
        session,
    ):
        session_date = self._session_date(session)

        anomaly_source = self._anomaly_source(
            session
        )

        anomaly_codes = self._anomaly_codes(
            anomaly_source
        )

        snapshot = self._snapshot(session)

        return {
            "index": index,
            "session_date": session_date,
            "anomaly_detected": bool(
                anomaly_codes
            ),
            "anomaly_count": len(
                anomaly_codes
            ),
            "anomaly_codes": anomaly_codes,
            "highest_severity": (
                self._category(
                    anomaly_source.get(
                        "highest_severity"
                    )
                )
            ),
            "decision": self._category(
                snapshot.get(
                    "final_decision"
                )
            ),
            "direction": self._category(
                snapshot.get(
                    "final_direction"
                )
            ),
            "regime": self._category(
                snapshot.get(
                    "final_regime"
                )
            ),
            "trade_ready_observed": (
                snapshot.get(
                    "trade_ready_observed"
                )
                is True
            ),
        }

    def _session_date(
        self,
        session,
    ):
        for key in (
            "session_date",
            "date",
        ):
            value = session.get(key)

            normalized = self._text(value)

            if normalized is not None:
                return normalized

        return None

    def _anomaly_source(
        self,
        session,
    ):
        candidates = [
            session.get(
                "research_anomaly_intelligence"
            ),
            session.get(
                "anomaly_intelligence"
            ),
            session.get(
                "research_anomalies"
            ),
        ]

        for candidate in candidates:
            if isinstance(candidate, dict):
                return candidate

        if (
            "anomaly_codes" in session
            or "anomalies" in session
        ):
            return session

        return {}

    def _snapshot(
        self,
        session,
    ):
        candidates = [
            session.get(
                "research_snapshot"
            ),
            session.get(
                "snapshot"
            ),
        ]

        for candidate in candidates:
            if isinstance(candidate, dict):
                return candidate

        return {}

    def _anomaly_codes(
        self,
        anomaly_source,
    ):
        codes = []

        direct_codes = anomaly_source.get(
            "anomaly_codes"
        )

        if isinstance(direct_codes, list):
            for value in direct_codes:
                code = self._category(value)

                if code is not None:
                    codes.append(code)

        anomalies = anomaly_source.get(
            "anomalies"
        )

        if isinstance(anomalies, list):
            for anomaly in anomalies:
                if not isinstance(anomaly, dict):
                    continue

                code = self._category(
                    anomaly.get("code")
                )

                if code is not None:
                    codes.append(code)

        return self._deduplicate(codes)

    def _build_anomaly_recurrence(
        self,
        session_records,
    ):
        all_codes = []

        for record in session_records:
            all_codes.extend(
                record["anomaly_codes"]
            )

        unique_codes = sorted(
            set(all_codes)
        )

        recurrence = []

        for code in unique_codes:
            matching = [
                record
                for record in session_records
                if code in record["anomaly_codes"]
            ]

            regimes = Counter(
                record["regime"]
                for record in matching
                if record["regime"] is not None
            )

            decisions = Counter(
                record["decision"]
                for record in matching
                if record["decision"] is not None
            )

            directions = Counter(
                record["direction"]
                for record in matching
                if record["direction"] is not None
            )

            occurrence_indices = [
                record["index"]
                for record in matching
            ]

            longest_streak = (
                self._longest_occurrence_streak(
                    code=code,
                    session_records=(
                        session_records
                    ),
                )
            )

            recurrence.append(
                {
                    "code": code,
                    "sessions": len(matching),
                    "session_frequency_percent": (
                        self._percentage(
                            len(matching),
                            len(session_records),
                        )
                    ),
                    "first_session": (
                        matching[0]["session_date"]
                        if matching
                        else None
                    ),
                    "last_session": (
                        matching[-1]["session_date"]
                        if matching
                        else None
                    ),
                    "trade_ready_sessions": sum(
                        1
                        for record in matching
                        if record[
                            "trade_ready_observed"
                        ]
                    ),
                    "regime_distribution": (
                        self._counter_distribution(
                            regimes
                        )
                    ),
                    "decision_distribution": (
                        self._counter_distribution(
                            decisions
                        )
                    ),
                    "direction_distribution": (
                        self._counter_distribution(
                            directions
                        )
                    ),
                    "occurrence_indices": (
                        occurrence_indices
                    ),
                    "longest_streak": (
                        longest_streak
                    ),
                }
            )

        recurrence.sort(
            key=lambda item: (
                -item["sessions"],
                item["code"],
            )
        )

        return recurrence

    def _build_combination_recurrence(
        self,
        session_records,
    ):
        combinations = Counter()

        combination_sessions = {}

        for record in session_records:
            codes = tuple(
                sorted(
                    record["anomaly_codes"]
                )
            )

            if len(codes) < 2:
                continue

            combinations[codes] += 1

            combination_sessions.setdefault(
                codes,
                [],
            ).append(
                record["session_date"]
            )

        result = []

        for codes, count in combinations.items():
            dates = combination_sessions.get(
                codes,
                [],
            )

            result.append(
                {
                    "codes": list(codes),
                    "sessions": count,
                    "session_frequency_percent": (
                        self._percentage(
                            count,
                            len(session_records),
                        )
                    ),
                    "first_session": (
                        dates[0]
                        if dates
                        else None
                    ),
                    "last_session": (
                        dates[-1]
                        if dates
                        else None
                    ),
                }
            )

        result.sort(
            key=lambda item: (
                -item["sessions"],
                item["codes"],
            )
        )

        return result

    def _build_current_pattern(
        self,
        *,
        session_records,
        anomaly_recurrence,
        combination_recurrence,
    ):
        if not session_records:
            return {
                "session_date": None,
                "anomaly_detected": False,
                "anomaly_codes": [],
                "historical_sessions": 0,
                "new_anomaly_codes": [],
                "recurring_anomaly_codes": [],
                "exact_combination_historical_sessions": 0,
                "pattern_state": "UNAVAILABLE",
            }

        current = session_records[-1]

        historical_sessions = max(
            len(session_records) - 1,
            0,
        )

        current_codes = current[
            "anomaly_codes"
        ]

        historical_code_counts = {
            item["code"]: sum(
                1
                for index in item[
                    "occurrence_indices"
                ]
                if index < current["index"]
            )
            for item in anomaly_recurrence
        }

        new_codes = [
            code
            for code in current_codes
            if historical_code_counts.get(
                code,
                0,
            )
            == 0
        ]

        recurring_codes = [
            code
            for code in current_codes
            if historical_code_counts.get(
                code,
                0,
            )
            > 0
        ]

        exact_historical_sessions = 0

        current_combination = tuple(
            sorted(current_codes)
        )

        if len(current_combination) >= 2:
            for item in combination_recurrence:
                if (
                    tuple(item["codes"])
                    == current_combination
                ):
                    exact_historical_sessions = sum(
                        1
                        for record in session_records[
                            :-1
                        ]
                        if tuple(
                            sorted(
                                record[
                                    "anomaly_codes"
                                ]
                            )
                        )
                        == current_combination
                    )
                    break

        if not current_codes:
            pattern_state = "NO_CURRENT_ANOMALY"

        elif new_codes and recurring_codes:
            pattern_state = "MIXED_NEW_AND_RECURRING"

        elif new_codes:
            pattern_state = "NEW_PATTERN"

        elif exact_historical_sessions > 0:
            pattern_state = "EXACT_PATTERN_RECURRING"

        else:
            pattern_state = "RECURRING_ANOMALIES"

        return {
            "session_date": current[
                "session_date"
            ],
            "anomaly_detected": current[
                "anomaly_detected"
            ],
            "anomaly_codes": deepcopy(
                current_codes
            ),
            "historical_sessions": (
                historical_sessions
            ),
            "new_anomaly_codes": new_codes,
            "recurring_anomaly_codes": (
                recurring_codes
            ),
            "exact_combination_historical_sessions": (
                exact_historical_sessions
            ),
            "pattern_state": pattern_state,
        }

    def _longest_occurrence_streak(
        self,
        *,
        code,
        session_records,
    ):
        best = 0
        best_start = None
        best_end = None

        current = 0
        current_start = None

        for record in session_records:
            if code in record["anomaly_codes"]:
                if current == 0:
                    current_start = record["index"]

                current += 1

                if current > best:
                    best = current
                    best_start = current_start
                    best_end = record["index"]

            else:
                current = 0
                current_start = None

        return {
            "sessions": best,
            "start_index": best_start,
            "end_index": best_end,
        }

    def _build_research_observations(
        self,
        *,
        session_records,
        anomaly_recurrence,
        combination_recurrence,
        current_pattern,
    ):
        observations = []

        if not session_records:
            observations.append(
                "No research sessions were available "
                "for anomaly recurrence analysis."
            )

            return observations

        sessions_with_anomalies = sum(
            1
            for record in session_records
            if record["anomaly_detected"]
        )

        if sessions_with_anomalies == 0:
            observations.append(
                "No archived research session contained "
                "a cross-signal anomaly."
            )

            return observations

        if anomaly_recurrence:
            most_recurrent = anomaly_recurrence[0]

            observations.append(
                f"{most_recurrent['code']} was the most "
                f"recurrent observed anomaly across "
                f"{most_recurrent['sessions']} session(s)."
            )

        repeated_combinations = [
            item
            for item in combination_recurrence
            if item["sessions"] > 1
        ]

        if repeated_combinations:
            observations.append(
                "At least one multi-anomaly combination "
                "recurred across multiple research sessions."
            )

        pattern_state = current_pattern[
            "pattern_state"
        ]

        if pattern_state == "NEW_PATTERN":
            observations.append(
                "The current session anomaly pattern was "
                "not observed in earlier research sessions."
            )

        elif (
            pattern_state
            == "MIXED_NEW_AND_RECURRING"
        ):
            observations.append(
                "The current session contained both new "
                "and historically recurring anomaly codes."
            )

        elif (
            pattern_state
            == "EXACT_PATTERN_RECURRING"
        ):
            observations.append(
                "The current session's exact anomaly "
                "combination has occurred previously."
            )

        elif (
            pattern_state
            == "RECURRING_ANOMALIES"
        ):
            observations.append(
                "The current session contained historically "
                "recurring anomaly codes in a different "
                "combination."
            )

        elif (
            pattern_state
            == "NO_CURRENT_ANOMALY"
        ):
            observations.append(
                "The current session did not contain a "
                "cross-signal anomaly."
            )

        return self._deduplicate(observations)

    def _counter_distribution(
        self,
        counter,
    ):
        result = [
            {
                "value": value,
                "count": count,
            }
            for value, count in counter.items()
        ]

        result.sort(
            key=lambda item: (
                -item["count"],
                item["value"],
            )
        )

        return result

    def _percentage(
        self,
        numerator,
        denominator,
    ):
        if denominator <= 0:
            return 0.0

        return round(
            (numerator / denominator) * 100,
            4,
        )

    def _category(
        self,
        value,
    ):
        normalized = self._text(value)

        if normalized is None:
            return None

        normalized = normalized.upper()

        if (
            normalized
            in self.INVALID_CATEGORY_VALUES
        ):
            return None

        return normalized

    def _text(
        self,
        value,
    ):
        if not isinstance(value, str):
            return None

        value = value.strip()

        if not value:
            return None

        return value

    def _deduplicate(
        self,
        values,
    ):
        result = []
        seen = set()

        for value in values:
            if value in seen:
                continue

            seen.add(value)
            result.append(value)

        return result