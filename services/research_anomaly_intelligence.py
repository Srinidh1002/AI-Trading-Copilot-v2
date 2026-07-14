"""
Research Anomaly Intelligence.

READ ONLY.
RESEARCH ONLY.

This service examines baseline-drift research output and identifies
cross-signal contradictions, divergences, and compound behavioural
anomalies.

It has no broker authority.
It cannot place orders.
It cannot authorize paper trades.
It cannot mutate risk controls.
It cannot tune strategy parameters.
It cannot retrain models.
"""

from copy import deepcopy


class ResearchAnomalyIntelligence:
    """
    Detect research anomalies from baseline drift output.
    """

    def analyze(
        self,
        drift_result=None,
    ):
        source = (
            deepcopy(drift_result)
            if isinstance(drift_result, dict)
            else {}
        )

        metric_drift = self._dictionary(
            source.get("metric_drift")
        )

        trade_ready_drift = self._dictionary(
            source.get("trade_ready_drift")
        )

        decision_drift = self._dictionary(
            source.get("decision_drift")
        )

        direction_drift = self._dictionary(
            source.get("direction_drift")
        )

        regime_drift = self._dictionary(
            source.get("regime_drift")
        )

        overall_drift = self._dictionary(
            source.get("overall_drift")
        )

        current = self._dictionary(
            source.get("current")
        )

        anomalies = []

        confidence_drift = self._drift_value(
            metric_drift.get("confidence")
        )

        readiness_drift = self._drift_value(
            metric_drift.get("readiness")
        )

        risk_drift = self._drift_value(
            metric_drift.get("risk_flag_count")
        )

        setup_drift = self._drift_value(
            metric_drift.get("setup_score")
        )

        trade_ready = self._boolean(
            current.get("trade_ready_observed")
        )

        current_decision = self._category(
            current.get("decision")
        )

        current_regime = self._category(
            current.get("regime")
        )

        historical_regime = self._category(
            regime_drift.get(
                "historical_dominant"
            )
        )

        self._append_if(
            anomalies,
            condition=(
                self._is_increase(confidence_drift)
                and self._is_decrease(
                    readiness_drift
                )
            ),
            anomaly=self._anomaly(
                code=(
                    "CONFIDENCE_READINESS_DIVERGENCE"
                ),
                severity="HIGH",
                signals=[
                    "confidence",
                    "readiness",
                ],
                description=(
                    "Confidence increased while "
                    "readiness decreased against "
                    "the historical research baseline."
                ),
            ),
        )

        self._append_if(
            anomalies,
            condition=(
                self._is_increase(confidence_drift)
                and self._is_increase(risk_drift)
            ),
            anomaly=self._anomaly(
                code="CONFIDENCE_RISK_DIVERGENCE",
                severity="HIGH",
                signals=[
                    "confidence",
                    "risk_flag_count",
                ],
                description=(
                    "Confidence increased while "
                    "risk flags also increased."
                ),
            ),
        )

        self._append_if(
            anomalies,
            condition=(
                trade_ready is True
                and self._is_decrease(
                    readiness_drift
                )
            ),
            anomaly=self._anomaly(
                code=(
                    "TRADE_READY_READINESS_CONTRADICTION"
                ),
                severity="CRITICAL",
                signals=[
                    "trade_ready_observed",
                    "readiness",
                ],
                description=(
                    "TRADE_READY was observed while "
                    "readiness decreased against the "
                    "historical research baseline."
                ),
            ),
        )

        self._append_if(
            anomalies,
            condition=(
                trade_ready is True
                and self._is_increase(risk_drift)
            ),
            anomaly=self._anomaly(
                code=(
                    "TRADE_READY_RISK_CONTRADICTION"
                ),
                severity="CRITICAL",
                signals=[
                    "trade_ready_observed",
                    "risk_flag_count",
                ],
                description=(
                    "TRADE_READY was observed while "
                    "risk flags increased."
                ),
            ),
        )

        self._append_if(
            anomalies,
            condition=(
                self._is_increase(confidence_drift)
                and self._is_decrease(setup_drift)
            ),
            anomaly=self._anomaly(
                code="CONFIDENCE_SETUP_DIVERGENCE",
                severity="HIGH",
                signals=[
                    "confidence",
                    "setup_score",
                ],
                description=(
                    "Confidence increased while the "
                    "setup score decreased."
                ),
            ),
        )

        self._append_if(
            anomalies,
            condition=(
                historical_regime is not None
                and current_regime is not None
                and historical_regime
                != current_regime
                and (
                    trade_ready is True
                    or current_decision
                    == "TRADE_READY"
                )
            ),
            anomaly=self._anomaly(
                code=(
                    "REGIME_TRANSITION_TRADE_READY_ANOMALY"
                ),
                severity="HIGH",
                signals=[
                    "regime",
                    "trade_ready_observed",
                ],
                description=(
                    "TRADE_READY behaviour was observed "
                    "during a change from the dominant "
                    "historical market regime."
                ),
            ),
        )

        base_anomaly_count = len(anomalies)

        if base_anomaly_count >= 3:
            anomalies.append(
                self._anomaly(
                    code="COMPOUND_RESEARCH_ANOMALY",
                    severity="CRITICAL",
                    signals=[
                        item["code"]
                        for item in anomalies
                    ],
                    description=(
                        "Multiple cross-signal research "
                        "anomalies were observed together."
                    ),
                )
            )

        anomalies = self._deduplicate_anomalies(
            anomalies
        )

        severity_distribution = (
            self._severity_distribution(
                anomalies
            )
        )

        highest_severity = (
            self._highest_severity(
                anomalies
            )
        )

        anomaly_codes = [
            item["code"]
            for item in anomalies
        ]

        observations = (
            self._research_observations(
                anomalies=anomalies,
                overall_drift=overall_drift,
            )
        )

        return {
            "status": "COMPLETED",
            "read_only": True,
            "research_only": True,
            "anomaly_detected": bool(anomalies),
            "anomaly_count": len(anomalies),
            "base_anomaly_count": base_anomaly_count,
            "highest_severity": highest_severity,
            "severity_distribution": (
                severity_distribution
            ),
            "anomaly_codes": anomaly_codes,
            "anomalies": anomalies,
            "source_overall_drift_state": (
                self._category(
                    overall_drift.get("state")
                )
            ),
            "research_observations": observations,
        }

    def analyse(
        self,
        drift_result=None,
    ):
        return self.analyze(
            drift_result
        )

    def _dictionary(
        self,
        value,
    ):
        if not isinstance(value, dict):
            return {}

        return value

    def _drift_value(
        self,
        value,
    ):
        item = self._dictionary(value)

        drift = item.get("drift")

        if not isinstance(drift, str):
            return "UNAVAILABLE"

        normalized = drift.strip().upper()

        if not normalized:
            return "UNAVAILABLE"

        return normalized

    def _boolean(
        self,
        value,
    ):
        if isinstance(value, bool):
            return value

        return None

    def _category(
        self,
        value,
    ):
        if not isinstance(value, str):
            return None

        normalized = value.strip().upper()

        if normalized in {
            "",
            "UNKNOWN",
            "UNAVAILABLE",
            "NONE",
            "NULL",
        }:
            return None

        return normalized

    def _is_increase(
        self,
        drift,
    ):
        return (
            isinstance(drift, str)
            and drift.endswith("_INCREASE")
        )

    def _is_decrease(
        self,
        drift,
    ):
        return (
            isinstance(drift, str)
            and drift.endswith("_DECREASE")
        )

    def _anomaly(
        self,
        *,
        code,
        severity,
        signals,
        description,
    ):
        return {
            "code": code,
            "severity": severity,
            "signals": list(signals),
            "description": description,
        }

    def _append_if(
        self,
        anomalies,
        *,
        condition,
        anomaly,
    ):
        if condition:
            anomalies.append(anomaly)

    def _deduplicate_anomalies(
        self,
        anomalies,
    ):
        result = []
        seen = set()

        for anomaly in anomalies:
            code = anomaly.get("code")

            if code in seen:
                continue

            seen.add(code)
            result.append(anomaly)

        return result

    def _severity_distribution(
        self,
        anomalies,
    ):
        counts = {}

        for anomaly in anomalies:
            severity = anomaly.get("severity")

            if not isinstance(severity, str):
                continue

            counts[severity] = (
                counts.get(severity, 0)
                + 1
            )

        order = {
            "CRITICAL": 0,
            "HIGH": 1,
            "MODERATE": 2,
            "LOW": 3,
        }

        return [
            {
                "severity": severity,
                "count": count,
            }
            for severity, count in sorted(
                counts.items(),
                key=lambda item: (
                    order.get(item[0], 99),
                    item[0],
                ),
            )
        ]

    def _highest_severity(
        self,
        anomalies,
    ):
        order = {
            "CRITICAL": 4,
            "HIGH": 3,
            "MODERATE": 2,
            "LOW": 1,
        }

        highest = None
        highest_rank = 0

        for anomaly in anomalies:
            severity = anomaly.get("severity")

            rank = order.get(
                severity,
                0,
            )

            if rank > highest_rank:
                highest = severity
                highest_rank = rank

        return highest

    def _research_observations(
        self,
        *,
        anomalies,
        overall_drift,
    ):
        observations = []

        if not anomalies:
            observations.append(
                "No cross-signal research anomalies "
                "were detected."
            )

        for anomaly in anomalies:
            observations.append(
                anomaly["description"]
            )

        overall_state = self._category(
            overall_drift.get("state")
        )

        if (
            anomalies
            and overall_state
            == "SIGNIFICANT_DRIFT"
        ):
            observations.append(
                "Cross-signal anomalies coincided "
                "with significant baseline drift."
            )

        return self._deduplicate_strings(
            observations
        )

    def _deduplicate_strings(
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