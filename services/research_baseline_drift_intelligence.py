"""
Research Baseline and Drift Intelligence.

Compares the current archived research session against
historical archived research sessions.

IMPORTANT:
- READ ONLY.
- RESEARCH ONLY.
- NO BROKER EXECUTION.
- NO ORDER PLACEMENT.
- NO PAPER-TRADE MUTATION.
- NO STRATEGY TUNING.
- NO MODEL RETRAINING.
"""

from copy import deepcopy
from statistics import mean


class ResearchBaselineDriftIntelligence:
    """
    Build a historical research baseline and detect
    current-session behavioural drift.
    """

    METRIC_CONFIG = {
        "confidence": {
            "record_key": "confidence",
            "label": "Confidence",
        },
        "readiness": {
            "record_key": "readiness",
            "label": "Readiness",
        },
        "risk_flag_count": {
            "record_key": "risk_flag_count",
            "label": "Risk Flag Count",
        },
        "setup_score": {
            "record_key": "setup_score",
            "label": "Setup Score",
        },
    }

    def analyze(
        self,
        session_records,
    ):
        """
        Compare the latest session with prior sessions.

        The latest valid session is treated as current.
        All earlier valid sessions form the historical baseline.
        """

        records = self._normalize_records(
            session_records
        )

        if not records:
            return self._empty_result()

        current = deepcopy(
            records[-1]
        )

        historical = deepcopy(
            records[:-1]
        )

        baseline = self._build_baseline(
            historical
        )

        current_snapshot = (
            self._build_current_snapshot(
                current
            )
        )

        metric_drift = (
            self._build_metric_drift(
                baseline,
                current_snapshot,
            )
        )

        trade_ready_drift = (
            self._build_trade_ready_drift(
                historical,
                current,
            )
        )

        decision_drift = (
            self._build_categorical_drift(
                historical,
                current,
                key="decision",
                label="Decision",
            )
        )

        direction_drift = (
            self._build_categorical_drift(
                historical,
                current,
                key="direction",
                label="Direction",
            )
        )

        regime_drift = (
            self._build_categorical_drift(
                historical,
                current,
                key="regime",
                label="Regime",
            )
        )

        overall = self._build_overall_drift(
            metric_drift,
            trade_ready_drift,
            decision_drift,
            direction_drift,
            regime_drift,
        )

        observations = (
            self._build_research_observations(
                baseline=baseline,
                current=current_snapshot,
                metric_drift=metric_drift,
                trade_ready_drift=(
                    trade_ready_drift
                ),
                decision_drift=decision_drift,
                direction_drift=direction_drift,
                regime_drift=regime_drift,
                overall=overall,
            )
        )

        return {
            "status": "COMPLETED",
            "read_only": True,
            "research_only": True,
            "sessions_observed": len(
                records
            ),
            "historical_sessions": len(
                historical
            ),
            "current_session_date": (
                current.get(
                    "session_date"
                )
            ),
            "baseline": baseline,
            "current": current_snapshot,
            "metric_drift": metric_drift,
            "trade_ready_drift": (
                trade_ready_drift
            ),
            "decision_drift": decision_drift,
            "direction_drift": direction_drift,
            "regime_drift": regime_drift,
            "overall_drift": overall,
            "research_observations": (
                observations
            ),
        }

    def analyse(
        self,
        session_records,
    ):
        """
        British spelling compatibility.
        """

        return self.analyze(
            session_records
        )

    def _normalize_records(
        self,
        session_records,
    ):
        if not isinstance(
            session_records,
            (list, tuple),
        ):
            return []

        normalized = []

        for record in session_records:
            if not isinstance(
                record,
                dict,
            ):
                continue

            normalized.append(
                deepcopy(
                    record
                )
            )

        return normalized

    def _empty_result(
        self,
    ):
        return {
            "status": "COMPLETED",
            "read_only": True,
            "research_only": True,
            "sessions_observed": 0,
            "historical_sessions": 0,
            "current_session_date": None,
            "baseline": (
                self._empty_baseline()
            ),
            "current": (
                self._empty_current()
            ),
            "metric_drift": (
                self._empty_metric_drift()
            ),
            "trade_ready_drift": {
                "status": "UNAVAILABLE",
                "historical_frequency_percent": (
                    None
                ),
                "current_trade_ready": None,
                "difference_percentage_points": (
                    None
                ),
                "drift": "UNAVAILABLE",
            },
            "decision_drift": (
                self._empty_categorical_drift(
                    "Decision"
                )
            ),
            "direction_drift": (
                self._empty_categorical_drift(
                    "Direction"
                )
            ),
            "regime_drift": (
                self._empty_categorical_drift(
                    "Regime"
                )
            ),
            "overall_drift": {
                "state": "UNAVAILABLE",
                "significant_signals": 0,
                "moderate_signals": 0,
                "stable_signals": 0,
                "available_signals": 0,
            },
            "research_observations": [
                (
                    "No research sessions were "
                    "available for baseline drift "
                    "analysis."
                ),
            ],
        }

    def _build_baseline(
        self,
        historical,
    ):
        baseline = {
            "sessions": len(
                historical
            ),
            "metrics": {},
            "trade_ready_frequency_percent": (
                None
            ),
            "decision_distribution": [],
            "direction_distribution": [],
            "regime_distribution": [],
        }

        for metric_name, config in (
            self.METRIC_CONFIG.items()
        ):
            values = self._numeric_values(
                historical,
                config["record_key"],
            )

            baseline["metrics"][
                metric_name
            ] = self._metric_baseline(
                values
            )

        if historical:
            trade_ready_count = sum(
                1
                for record in historical
                if (
                    record.get(
                        "trade_ready_observed"
                    )
                    is True
                )
            )

            baseline[
                "trade_ready_frequency_percent"
            ] = round(
                (
                    trade_ready_count
                    / len(
                        historical
                    )
                )
                * 100.0,
                4,
            )

        baseline[
            "decision_distribution"
        ] = self._distribution(
            historical,
            "decision",
        )

        baseline[
            "direction_distribution"
        ] = self._distribution(
            historical,
            "direction",
        )

        baseline[
            "regime_distribution"
        ] = self._distribution(
            historical,
            "regime",
        )

        return baseline

    def _empty_baseline(
        self,
    ):
        return {
            "sessions": 0,
            "metrics": {
                metric_name: (
                    self._metric_baseline(
                        []
                    )
                )
                for metric_name in (
                    self.METRIC_CONFIG
                )
            },
            "trade_ready_frequency_percent": (
                None
            ),
            "decision_distribution": [],
            "direction_distribution": [],
            "regime_distribution": [],
        }

    def _build_current_snapshot(
        self,
        current,
    ):
        return {
            "session_date": current.get(
                "session_date"
            ),
            "confidence": self._number(
                current.get(
                    "confidence"
                )
            ),
            "readiness": self._number(
                current.get(
                    "readiness"
                )
            ),
            "risk_flag_count": self._number(
                current.get(
                    "risk_flag_count"
                )
            ),
            "setup_score": self._number(
                current.get(
                    "setup_score"
                )
            ),
            "trade_ready_observed": (
                current.get(
                    "trade_ready_observed"
                )
                is True
            ),
            "decision": self._category(
                current.get(
                    "decision"
                )
            ),
            "direction": self._category(
                current.get(
                    "direction"
                )
            ),
            "regime": self._category(
                current.get(
                    "regime"
                )
            ),
        }

    def _empty_current(
        self,
    ):
        return {
            "session_date": None,
            "confidence": None,
            "readiness": None,
            "risk_flag_count": None,
            "setup_score": None,
            "trade_ready_observed": None,
            "decision": None,
            "direction": None,
            "regime": None,
        }

    def _build_metric_drift(
        self,
        baseline,
        current,
    ):
        result = {}

        metrics = (
            baseline.get(
                "metrics",
                {},
            )
            or {}
        )

        for metric_name in (
            self.METRIC_CONFIG
        ):
            baseline_metric = (
                metrics.get(
                    metric_name,
                    {},
                )
                or {}
            )

            baseline_average = (
                baseline_metric.get(
                    "average"
                )
            )

            current_value = current.get(
                metric_name
            )

            result[
                metric_name
            ] = self._metric_drift(
                baseline_average,
                current_value,
            )

        return result

    def _empty_metric_drift(
        self,
    ):
        return {
            metric_name: (
                self._metric_drift(
                    None,
                    None,
                )
            )
            for metric_name in (
                self.METRIC_CONFIG
            )
        }

    def _metric_baseline(
        self,
        values,
    ):
        if not values:
            return {
                "observations": 0,
                "minimum": None,
                "maximum": None,
                "average": None,
            }

        return {
            "observations": len(
                values
            ),
            "minimum": min(
                values
            ),
            "maximum": max(
                values
            ),
            "average": round(
                mean(
                    values
                ),
                4,
            ),
        }

    def _metric_drift(
        self,
        baseline_average,
        current_value,
    ):
        baseline_number = self._number(
            baseline_average
        )

        current_number = self._number(
            current_value
        )

        if (
            baseline_number is None
            or current_number is None
        ):
            return {
                "status": "UNAVAILABLE",
                "baseline_average": (
                    baseline_number
                ),
                "current": current_number,
                "difference": None,
                "absolute_difference": None,
                "relative_change_percent": None,
                "direction": "UNAVAILABLE",
                "severity": "UNAVAILABLE",
                "drift": "UNAVAILABLE",
            }

        difference = round(
            (
                current_number
                - baseline_number
            ),
            4,
        )

        absolute_difference = round(
            abs(
                difference
            ),
            4,
        )

        relative_change = None

        if baseline_number != 0:
            relative_change = round(
                (
                    difference
                    / abs(
                        baseline_number
                    )
                )
                * 100.0,
                4,
            )

        direction = "STABLE"

        if difference > 0:
            direction = "INCREASE"

        elif difference < 0:
            direction = "DECREASE"

        severity = self._severity(
            relative_change=relative_change,
            absolute_difference=(
                absolute_difference
            ),
            baseline_average=(
                baseline_number
            ),
        )

        drift = severity

        if severity not in {
            "STABLE",
            "UNAVAILABLE",
        }:
            drift = (
                f"{severity}_{direction}"
            )

        return {
            "status": "COMPLETED",
            "baseline_average": (
                baseline_number
            ),
            "current": current_number,
            "difference": difference,
            "absolute_difference": (
                absolute_difference
            ),
            "relative_change_percent": (
                relative_change
            ),
            "direction": direction,
            "severity": severity,
            "drift": drift,
        }

    def _severity(
        self,
        *,
        relative_change,
        absolute_difference,
        baseline_average,
    ):
        if (
            relative_change is None
        ):
            if absolute_difference == 0:
                return "STABLE"

            return "SIGNIFICANT"

        magnitude = abs(
            relative_change
        )

        if magnitude < 5.0:
            return "STABLE"

        if magnitude < 15.0:
            return "MODERATE"

        return "SIGNIFICANT"

    def _build_trade_ready_drift(
        self,
        historical,
        current,
    ):
        if not historical:
            return {
                "status": "UNAVAILABLE",
                "historical_frequency_percent": (
                    None
                ),
                "current_trade_ready": (
                    current.get(
                        "trade_ready_observed"
                    )
                    is True
                ),
                "difference_percentage_points": (
                    None
                ),
                "drift": "UNAVAILABLE",
            }

        historical_count = sum(
            1
            for record in historical
            if (
                record.get(
                    "trade_ready_observed"
                )
                is True
            )
        )

        historical_frequency = round(
            (
                historical_count
                / len(
                    historical
                )
            )
            * 100.0,
            4,
        )

        current_trade_ready = (
            current.get(
                "trade_ready_observed"
            )
            is True
        )

        current_percent = (
            100.0
            if current_trade_ready
            else 0.0
        )

        difference = round(
            (
                current_percent
                - historical_frequency
            ),
            4,
        )

        magnitude = abs(
            difference
        )

        if magnitude < 10.0:
            drift = "STABLE"

        elif magnitude < 30.0:
            drift = "MODERATE"

        else:
            drift = "SIGNIFICANT"

        if drift != "STABLE":
            direction = (
                "INCREASE"
                if difference > 0
                else "DECREASE"
            )

            drift = (
                f"{drift}_{direction}"
            )
        return {
            "status": "COMPLETED",
            "historical_frequency_percent": (
                historical_frequency
            ),
            "current_trade_ready": (
                current_trade_ready
            ),
            "difference_percentage_points": (
                difference
            ),
            "drift": drift,
        }

    def _build_categorical_drift(
        self,
        historical,
        current,
        *,
        key,
        label,
    ):
        values = []

        for record in historical:
            value = self._category(
                record.get(
                    key
                )
            )

            if value is not None:
                values.append(
                    value
                )

        current_value = self._category(
            current.get(
                key
            )
        )

        if (
            not values
            or current_value is None
        ):
            return self._empty_categorical_drift(
                label
            )

        distribution = (
            self._distribution_from_values(
                values
            )
        )

        dominant = (
            distribution[0]["value"]
            if distribution
            else None
        )

        dominant_count = (
            distribution[0]["count"]
            if distribution
            else 0
        )

        dominant_percent = round(
            (
                dominant_count
                / len(
                    values
                )
            )
            * 100.0,
            4,
        )

        matches_dominant = (
            current_value
            == dominant
        )

        if matches_dominant:
            drift = "STABLE"

        elif dominant_percent >= 70.0:
            drift = "SIGNIFICANT"

        else:
            drift = "MODERATE"

        return {
            "status": "COMPLETED",
            "label": label,
            "historical_distribution": (
                distribution
            ),
            "historical_dominant": dominant,
            "historical_dominant_percent": (
                dominant_percent
            ),
            "current": current_value,
            "matches_historical_dominant": (
                matches_dominant
            ),
            "drift": drift,
        }

    def _empty_categorical_drift(
        self,
        label,
    ):
        return {
            "status": "UNAVAILABLE",
            "label": label,
            "historical_distribution": [],
            "historical_dominant": None,
            "historical_dominant_percent": (
                None
            ),
            "current": None,
            "matches_historical_dominant": (
                None
            ),
            "drift": "UNAVAILABLE",
        }

    def _build_overall_drift(
        self,
        metric_drift,
        trade_ready_drift,
        decision_drift,
        direction_drift,
        regime_drift,
    ):
        signals = []

        for result in (
            metric_drift.values()
        ):
            if not isinstance(
                result,
                dict,
            ):
                continue

            signals.append(
                result.get(
                    "severity"
                )
            )

        trade_ready_state = (
            trade_ready_drift.get(
                "drift"
            )
            if isinstance(
                trade_ready_drift,
                dict,
            )
            else None
        )

        signals.append(
            self._signal_severity(
                trade_ready_state
            )
        )

        for result in (
            decision_drift,
            direction_drift,
            regime_drift,
        ):
            state = (
                result.get(
                    "drift"
                )
                if isinstance(
                    result,
                    dict,
                )
                else None
            )

            signals.append(
                self._signal_severity(
                    state
                )
            )

        available = [
            signal
            for signal in signals
            if signal in {
                "STABLE",
                "MODERATE",
                "SIGNIFICANT",
            }
        ]

        significant = available.count(
            "SIGNIFICANT"
        )

        moderate = available.count(
            "MODERATE"
        )

        stable = available.count(
            "STABLE"
        )

        if not available:
            state = "UNAVAILABLE"

        elif significant >= 2:
            state = "SIGNIFICANT_DRIFT"

        elif significant == 1:
            state = "ELEVATED_DRIFT"

        elif moderate >= 2:
            state = "MODERATE_DRIFT"

        elif moderate == 1:
            state = "LOW_DRIFT"

        else:
            state = "STABLE"

        return {
            "state": state,
            "significant_signals": significant,
            "moderate_signals": moderate,
            "stable_signals": stable,
            "available_signals": len(
                available
            ),
        }

    def _signal_severity(
        self,
        value,
    ):
        if not isinstance(
            value,
            str,
        ):
            return "UNAVAILABLE"

        normalized = (
            value
            .strip()
            .upper()
        )

        if normalized.startswith(
            "SIGNIFICANT"
        ):
            return "SIGNIFICANT"

        if normalized.startswith(
            "MODERATE"
        ):
            return "MODERATE"

        if normalized == "STABLE":
            return "STABLE"

        return "UNAVAILABLE"

    def _build_research_observations(
        self,
        *,
        baseline,
        current,
        metric_drift,
        trade_ready_drift,
        decision_drift,
        direction_drift,
        regime_drift,
        overall,
    ):
        observations = []

        if (
            baseline.get(
                "sessions",
                0,
            )
            == 0
        ):
            observations.append(
                (
                    "Historical research baseline "
                    "is unavailable because no prior "
                    "session was observed."
                )
            )

        for metric_name, config in (
            self.METRIC_CONFIG.items()
        ):
            result = (
                metric_drift.get(
                    metric_name,
                    {},
                )
                or {}
            )

            severity = result.get(
                "severity"
            )

            if severity in {
                "MODERATE",
                "SIGNIFICANT",
            }:
                observations.append(
                    (
                        f"{config['label']} showed "
                        f"{result.get('drift')} drift "
                        "against the historical "
                        "research baseline."
                    )
                )

        trade_ready_state = (
            trade_ready_drift.get(
                "drift"
            )
            if isinstance(
                trade_ready_drift,
                dict,
            )
            else None
        )

        if self._signal_severity(
            trade_ready_state
        ) in {
            "MODERATE",
            "SIGNIFICANT",
        }:
            observations.append(
                (
                    "TRADE_READY behaviour differed "
                    "from its historical session "
                    "frequency."
                )
            )

        for result in (
            decision_drift,
            direction_drift,
            regime_drift,
        ):
            if not isinstance(
                result,
                dict,
            ):
                continue

            if result.get(
                "drift"
            ) in {
                "MODERATE",
                "SIGNIFICANT",
            }:
                observations.append(
                    (
                        f"{result.get('label')} "
                        "differed from the dominant "
                        "historical research state."
                    )
                )

        overall_state = overall.get(
            "state"
        )

        if overall_state == "SIGNIFICANT_DRIFT":
            observations.append(
                (
                    "Multiple research signals "
                    "showed significant behavioural "
                    "drift."
                )
            )

        elif overall_state == "ELEVATED_DRIFT":
            observations.append(
                (
                    "At least one research signal "
                    "showed significant behavioural "
                    "drift."
                )
            )

        elif overall_state == "STABLE":
            observations.append(
                (
                    "Observed research behaviour "
                    "remained within the historical "
                    "baseline."
                )
            )

        if not observations:
            observations.append(
                (
                    "Insufficient comparable research "
                    "signals were available for a "
                    "strong drift observation."
                )
            )

        return self._deduplicate(
            observations
        )

    def _numeric_values(
        self,
        records,
        key,
    ):
        values = []

        for record in records:
            value = self._number(
                record.get(
                    key
                )
            )

            if value is not None:
                values.append(
                    value
                )

        return values

    def _distribution(
        self,
        records,
        key,
    ):
        values = []

        for record in records:
            value = self._category(
                record.get(
                    key
                )
            )

            if value is not None:
                values.append(
                    value
                )

        return self._distribution_from_values(
            values
        )

    def _distribution_from_values(
        self,
        values,
    ):
        counts = {}

        for value in values:
            counts[value] = (
                counts.get(
                    value,
                    0,
                )
                + 1
            )

        return [
            {
                "value": value,
                "count": count,
            }
            for value, count in sorted(
                counts.items(),
                key=lambda item: (
                    -item[1],
                    item[0],
                ),
            )
        ]

    def _number(
        self,
        value,
    ):
        if isinstance(
            value,
            bool,
        ):
            return None

        if not isinstance(
            value,
            (int, float),
        ):
            return None

        return float(
            value
        )

    def _category(
        self,
        value,
    ):
        if not isinstance(
            value,
            str,
        ):
            return None

        normalized = (
            value
            .strip()
            .upper()
        )

        if normalized in {
            "",
            "UNKNOWN",
            "UNAVAILABLE",
            "NONE",
            "NULL",
        }:
            return None

        return normalized

    def _deduplicate(
        self,
        values,
    ):
        result = []
        seen = set()

        for value in values:
            if value in seen:
                continue

            seen.add(
                value
            )

            result.append(
                value
            )

        return result