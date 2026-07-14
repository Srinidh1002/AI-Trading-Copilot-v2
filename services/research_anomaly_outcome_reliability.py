"""
Research Anomaly Outcome Reliability Intelligence.

Read-only research service for evaluating the observed reliability
of anomaly/outcome correlations.

This service does not establish causation and has no execution,
strategy-tuning, confidence, risk, or paper-trade authority.
"""

from copy import deepcopy
from math import sqrt


class ResearchAnomalyOutcomeReliability:
    """
    Evaluate repeated anomaly/outcome correlation evidence.

    The engine consumes the output of
    ResearchAnomalyOutcomeCorrelation and classifies the amount and
    consistency of observed evidence.

    Correlation is not causation.
    """

    def analyze(self, correlation_result):
        """
        Analyze anomaly/outcome correlation reliability.
        """

        if correlation_result is None:
            raise ValueError(
                "correlation_result must not be None"
            )

        if not isinstance(correlation_result, dict):
            raise ValueError(
                "correlation_result must be a dictionary"
            )

        source = deepcopy(correlation_result)

        anomaly_correlations = self._safe_list(
            source.get("anomaly_correlations")
        )

        combination_correlations = self._safe_list(
            source.get("combination_correlations")
        )

        anomaly_reliability = [
            self._build_reliability_record(
                item=item,
                record_type="ANOMALY",
            )
            for item in anomaly_correlations
            if isinstance(item, dict)
        ]

        combination_reliability = [
            self._build_reliability_record(
                item=item,
                record_type="COMBINATION",
            )
            for item in combination_correlations
            if isinstance(item, dict)
        ]

        anomaly_reliability.sort(
            key=lambda item: item["code"]
        )

        combination_reliability.sort(
            key=lambda item: tuple(item["codes"])
        )

        evidence_distribution = (
            self._evidence_distribution(
                anomaly_reliability
            )
        )

        reliability_distribution = (
            self._reliability_distribution(
                anomaly_reliability
            )
        )

        strongest_negative_evidence = (
            self._strongest_evidence(
                anomaly_reliability,
                direction="NEGATIVE",
            )
        )

        strongest_positive_evidence = (
            self._strongest_evidence(
                anomaly_reliability,
                direction="POSITIVE",
            )
        )

        research_observations = (
            self._research_observations(
                anomaly_reliability=(
                    anomaly_reliability
                ),
                combination_reliability=(
                    combination_reliability
                ),
                strongest_negative_evidence=(
                    strongest_negative_evidence
                ),
                strongest_positive_evidence=(
                    strongest_positive_evidence
                ),
            )
        )

        return {
            "status": "COMPLETED",
            "read_only": True,
            "research_only": True,
            "correlation_not_causation": True,
            "anomalies_observed": len(
                anomaly_reliability
            ),
            "combinations_observed": len(
                combination_reliability
            ),
            "anomaly_reliability": (
                anomaly_reliability
            ),
            "combination_reliability": (
                combination_reliability
            ),
            "evidence_distribution": (
                evidence_distribution
            ),
            "reliability_distribution": (
                reliability_distribution
            ),
            "strongest_negative_evidence": (
                strongest_negative_evidence
            ),
            "strongest_positive_evidence": (
                strongest_positive_evidence
            ),
            "research_observations": (
                research_observations
            ),
        }

    def _build_reliability_record(
        self,
        item,
        record_type,
    ):
        linked_closed_trades = self._safe_int(
            item.get("linked_closed_trades")
        )

        anomaly_sessions = self._safe_int(
            item.get("anomaly_sessions")
        )

        wins = self._safe_int(
            item.get("wins")
        )

        losses = self._safe_int(
            item.get("losses")
        )

        flat = self._safe_int(
            item.get("flat")
        )

        average_realized_pnl = self._safe_float(
            item.get("average_realized_pnl")
        )

        win_rate_percent = self._safe_float(
            item.get("win_rate_percent")
        )

        loss_rate_percent = self._safe_float(
            item.get("loss_rate_percent")
        )

        outcome_state = self._safe_text(
            item.get("outcome_state")
        )

        evidence_level = self._evidence_level(
            linked_closed_trades
        )

        directional_consistency = (
            self._directional_consistency(
                wins=wins,
                losses=losses,
                flat=flat,
            )
        )

        standard_error = self._proportion_standard_error(
            wins=wins,
            losses=losses,
            flat=flat,
        )

        reliability_state = self._reliability_state(
            linked_closed_trades=(
                linked_closed_trades
            ),
            average_realized_pnl=(
                average_realized_pnl
            ),
            directional_consistency=(
                directional_consistency
            ),
        )

        record = {
            "record_type": record_type,
            "anomaly_sessions": anomaly_sessions,
            "linked_closed_trades": (
                linked_closed_trades
            ),
            "wins": wins,
            "losses": losses,
            "flat": flat,
            "win_rate_percent": win_rate_percent,
            "loss_rate_percent": loss_rate_percent,
            "average_realized_pnl": (
                average_realized_pnl
            ),
            "outcome_state": outcome_state,
            "evidence_level": evidence_level,
            "directional_consistency_percent": (
                directional_consistency
            ),
            "proportion_standard_error": (
                standard_error
            ),
            "reliability_state": reliability_state,
        }

        if record_type == "ANOMALY":
            record["code"] = self._safe_text(
                item.get("code")
            )

        else:
            record["codes"] = self._safe_codes(
                item.get("codes")
            )

        return record

    def _evidence_level(
        self,
        linked_closed_trades,
    ):
        if linked_closed_trades <= 0:
            return "NONE"

        if linked_closed_trades < 5:
            return "VERY_LOW"

        if linked_closed_trades < 10:
            return "LOW"

        if linked_closed_trades < 20:
            return "MODERATE"

        if linked_closed_trades < 50:
            return "HIGH"

        return "VERY_HIGH"

    def _directional_consistency(
        self,
        wins,
        losses,
        flat,
    ):
        total = wins + losses + flat

        if total <= 0:
            return None

        dominant = max(
            wins,
            losses,
            flat,
        )

        return round(
            (
                dominant
                / total
            )
            * 100.0,
            4,
        )

    def _proportion_standard_error(
        self,
        wins,
        losses,
        flat,
    ):
        total = wins + losses + flat

        if total <= 0:
            return None

        dominant = max(
            wins,
            losses,
            flat,
        )

        proportion = dominant / total

        return round(
            sqrt(
                (
                    proportion
                    * (
                        1.0 - proportion
                    )
                )
                / total
            ),
            6,
        )

    def _reliability_state(
        self,
        linked_closed_trades,
        average_realized_pnl,
        directional_consistency,
    ):
        if (
            linked_closed_trades <= 0
            or average_realized_pnl is None
            or directional_consistency is None
        ):
            return "INSUFFICIENT_DATA"

        if linked_closed_trades < 5:
            return "WEAK_EVIDENCE"

        if average_realized_pnl == 0:
            if linked_closed_trades >= 20:
                return "STRONG_NEUTRAL_EVIDENCE"

            return "NEUTRAL_EVIDENCE"

        if average_realized_pnl < 0:
            direction = "NEGATIVE"
        else:
            direction = "POSITIVE"

        if (
            linked_closed_trades >= 20
            and directional_consistency >= 70.0
        ):
            return (
                f"STRONG_{direction}_EVIDENCE"
            )

        if (
            linked_closed_trades >= 10
            and directional_consistency >= 60.0
        ):
            return (
                f"MODERATE_{direction}_EVIDENCE"
            )

        return (
            f"WEAK_{direction}_EVIDENCE"
        )

    def _evidence_distribution(
        self,
        records,
    ):
        counts = {}

        for item in records:
            value = item["evidence_level"]

            counts[value] = (
                counts.get(value, 0)
                + 1
            )

        order = {
            "NONE": 0,
            "VERY_LOW": 1,
            "LOW": 2,
            "MODERATE": 3,
            "HIGH": 4,
            "VERY_HIGH": 5,
        }

        return [
            {
                "evidence_level": key,
                "count": counts[key],
            }
            for key in sorted(
                counts,
                key=lambda value: (
                    order.get(value, 999),
                    value,
                ),
            )
        ]

    def _reliability_distribution(
        self,
        records,
    ):
        counts = {}

        for item in records:
            value = item["reliability_state"]

            counts[value] = (
                counts.get(value, 0)
                + 1
            )

        return [
            {
                "reliability_state": key,
                "count": counts[key],
            }
            for key in sorted(counts)
        ]

    def _strongest_evidence(
        self,
        records,
        direction,
    ):
        suffix = (
            f"_{direction}_EVIDENCE"
        )

        candidates = [
            item
            for item in records
            if item[
                "reliability_state"
            ].endswith(suffix)
        ]

        if not candidates:
            return None

        candidates.sort(
            key=lambda item: (
                -item["linked_closed_trades"],
                -(
                    item[
                        "directional_consistency_percent"
                    ]
                    or 0.0
                ),
                (
                    item[
                        "average_realized_pnl"
                    ]
                    if direction == "NEGATIVE"
                    else -item[
                        "average_realized_pnl"
                    ]
                ),
                item["code"],
            )
        )

        return deepcopy(candidates[0])

    def _research_observations(
        self,
        anomaly_reliability,
        combination_reliability,
        strongest_negative_evidence,
        strongest_positive_evidence,
    ):
        observations = []

        if (
            not anomaly_reliability
            and not combination_reliability
        ):
            return [
                (
                    "No anomaly outcome correlations "
                    "were available for reliability "
                    "analysis."
                )
            ]
        strong_records = [
            item
            for item in anomaly_reliability
            if item["reliability_state"].startswith(
                "STRONG_"
            )
        ]

        if strong_records:
            observations.append(
                (
                    "At least one anomaly correlation "
                    "showed strong repeated outcome "
                    "evidence."
                )
            )

        if strongest_negative_evidence is not None:
            observations.append(
                (
                    f"{strongest_negative_evidence['code']} "
                    "showed the strongest repeated "
                    "negative outcome evidence."
                )
            )

        if strongest_positive_evidence is not None:
            observations.append(
                (
                    f"{strongest_positive_evidence['code']} "
                    "showed the strongest repeated "
                    "positive outcome evidence."
                )
            )

        recurring_combinations = [
            item
            for item in combination_reliability
            if item["anomaly_sessions"] > 1
        ]

        if recurring_combinations:
            observations.append(
                (
                    "At least one recurring multi-anomaly "
                    "combination had linked closed-trade "
                    "outcome evidence."
                )
            )

        weak_records = [
            item
            for item in anomaly_reliability
            if item["reliability_state"] in {
                "INSUFFICIENT_DATA",
                "WEAK_EVIDENCE",
                "WEAK_NEGATIVE_EVIDENCE",
                "WEAK_POSITIVE_EVIDENCE",
            }
        ]

        if (
            weak_records
            and len(weak_records)
            == len(anomaly_reliability)
        ):
            observations.append(
                (
                    "Observed anomaly correlations remain "
                    "too limited or inconsistent for "
                    "strong research reliability."
                )
            )

        if not observations:
            observations.append(
                (
                    "Anomaly outcome reliability was "
                    "measured without establishing "
                    "causation."
                )
            )

        return observations

    def _safe_list(
        self,
        value,
    ):
        if isinstance(value, (list, tuple)):
            return list(value)

        return []

    def _safe_int(
        self,
        value,
    ):
        if isinstance(value, bool):
            return 0

        try:
            parsed = int(value)
        except (
            TypeError,
            ValueError,
            OverflowError,
        ):
            return 0

        return max(parsed, 0)

    def _safe_float(
        self,
        value,
    ):
        if isinstance(value, bool):
            return None

        try:
            parsed = float(value)
        except (
            TypeError,
            ValueError,
            OverflowError,
        ):
            return None

        if parsed != parsed:
            return None

        if parsed in {
            float("inf"),
            float("-inf"),
        }:
            return None

        return round(parsed, 4)

    def _safe_text(
        self,
        value,
    ):
        if value is None:
            return None

        text = str(value).strip()

        if not text:
            return None

        return text

    def _safe_codes(
        self,
        value,
    ):
        if not isinstance(value, (list, tuple)):
            return []

        codes = {
            text
            for item in value
            if (
                text := self._safe_text(item)
            )
        }

        return sorted(codes)