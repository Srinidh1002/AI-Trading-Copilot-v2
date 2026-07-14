"""
Research Evidence Stability Intelligence.

Read-only research analytics for comparing earlier and more recent
closed-trade outcome evidence linked to observed anomaly patterns.

This module does not execute trades, place orders, size positions,
change risk, tune strategies, or establish causation.
"""

from copy import deepcopy
from math import isfinite, sqrt


class ResearchEvidenceStabilityIntelligence:
    """Measure whether observed anomaly outcome evidence is stable."""

    _MIN_WINDOW_TRADES = 5
    _MODERATE_CHANGE_PERCENT = 15.0
    _SIGNIFICANT_CHANGE_PERCENT = 30.0

    def analyze(self, correlation_result):
        """Analyze stability of anomaly and combination outcome evidence."""
        if correlation_result is None:
            raise ValueError(
                "correlation_result cannot be None"
            )

        if not isinstance(correlation_result, dict):
            raise ValueError(
                "correlation_result must be a dictionary"
            )

        source = deepcopy(correlation_result)

        anomaly_correlations = self._collection(
            source.get("anomaly_correlations")
        )
        combination_correlations = self._collection(
            source.get("combination_correlations")
        )

        anomaly_stability = sorted(
            [
                self._analyze_record(
                    item,
                    record_type="ANOMALY",
                )
                for item in anomaly_correlations
                if isinstance(item, dict)
            ],
            key=lambda item: item["code"],
        )

        combination_stability = sorted(
            [
                self._analyze_record(
                    item,
                    record_type="COMBINATION",
                )
                for item in combination_correlations
                if isinstance(item, dict)
            ],
            key=lambda item: tuple(item["codes"]),
        )

        all_records = (
            anomaly_stability
            + combination_stability
        )

        stability_distribution = self._distribution(
            all_records,
            "stability_state",
            "stability_state",
        )

        direction_distribution = self._distribution(
            all_records,
            "recent_direction",
            "direction",
        )

        most_strengthened = self._strongest_record(
            all_records,
            state="STRENGTHENING",
        )
        most_weakened = self._strongest_record(
            all_records,
            state="WEAKENING",
        )
        strongest_reversal = self._strongest_record(
            all_records,
            state="DIRECTION_REVERSAL",
        )

        observations = self._research_observations(
            anomaly_stability,
            combination_stability,
            most_strengthened,
            most_weakened,
            strongest_reversal,
        )

        return {
            "status": "COMPLETED",
            "read_only": True,
            "research_only": True,
            "correlation_not_causation": True,
            "minimum_window_trades": (
                self._MIN_WINDOW_TRADES
            ),
            "anomalies_observed": len(
                anomaly_stability
            ),
            "combinations_observed": len(
                combination_stability
            ),
            "anomaly_stability": anomaly_stability,
            "combination_stability": (
                combination_stability
            ),
            "stability_distribution": (
                stability_distribution
            ),
            "recent_direction_distribution": (
                direction_distribution
            ),
            "most_strengthened_evidence": (
                deepcopy(most_strengthened)
            ),
            "most_weakened_evidence": (
                deepcopy(most_weakened)
            ),
            "strongest_direction_reversal": (
                deepcopy(strongest_reversal)
            ),
            "research_observations": observations,
        }

    def _analyze_record(
        self,
        record,
        record_type,
    ):
        outcomes = self._outcomes(record)

        midpoint = len(outcomes) // 2

        earlier = outcomes[:midpoint]
        recent = outcomes[midpoint:]

        earlier_metrics = self._window_metrics(
            earlier
        )
        recent_metrics = self._window_metrics(
            recent
        )

        stability = self._stability(
            earlier_metrics,
            recent_metrics,
        )

        result = {
            "record_type": record_type,
            "linked_closed_trades": len(outcomes),
            "earlier_window": earlier_metrics,
            "recent_window": recent_metrics,
            "earlier_direction": (
                earlier_metrics["direction"]
            ),
            "recent_direction": (
                recent_metrics["direction"]
            ),
            "directional_consistency_change": (
                stability[
                    "directional_consistency_change"
                ]
            ),
            "average_pnl_change": (
                stability["average_pnl_change"]
            ),
            "stability_state": (
                stability["stability_state"]
            ),
            "stability_magnitude": (
                stability["stability_magnitude"]
            ),
        }

        if record_type == "ANOMALY":
            result["code"] = self._text(
                record.get("code")
            )
        else:
            result["codes"] = self._codes(
                record.get("codes")
            )

        return result

    def _outcomes(self, record):
        raw = record.get("linked_trade_outcomes")

        if not isinstance(raw, (list, tuple)):
            return []

        outcomes = []

        for item in raw:
            if not isinstance(item, dict):
                continue

            pnl = self._number(
                item.get("realized_pnl")
            )

            if pnl is None:
                continue

            outcomes.append(
                {
                    "session_date": self._text(
                        item.get("session_date")
                    ),
                    "realized_pnl": pnl,
                }
            )

        return sorted(
            outcomes,
            key=lambda item: (
                item["session_date"] or "",
            ),
        )

    def _window_metrics(self, outcomes):
        count = len(outcomes)

        if count == 0:
            return {
                "trades": 0,
                "wins": 0,
                "losses": 0,
                "flat": 0,
                "win_rate_percent": None,
                "loss_rate_percent": None,
                "directional_consistency_percent": None,
                "average_realized_pnl": None,
                "direction": "UNAVAILABLE",
            }

        pnls = [
            item["realized_pnl"]
            for item in outcomes
        ]

        wins = sum(
            1 for value in pnls if value > 0
        )
        losses = sum(
            1 for value in pnls if value < 0
        )
        flat = sum(
            1 for value in pnls if value == 0
        )

        win_rate = round(
            wins / count * 100.0,
            4,
        )
        loss_rate = round(
            losses / count * 100.0,
            4,
        )

        average_pnl = round(
            sum(pnls) / count,
            4,
        )

        if wins > losses:
            direction = "POSITIVE"
            dominant = wins
        elif losses > wins:
            direction = "NEGATIVE"
            dominant = losses
        else:
            direction = "NEUTRAL"
            dominant = max(
                wins,
                losses,
                flat,
            )

        consistency = round(
            dominant / count * 100.0,
            4,
        )

        return {
            "trades": count,
            "wins": wins,
            "losses": losses,
            "flat": flat,
            "win_rate_percent": win_rate,
            "loss_rate_percent": loss_rate,
            "directional_consistency_percent": (
                consistency
            ),
            "average_realized_pnl": average_pnl,
            "direction": direction,
        }

    def _stability(
        self,
        earlier,
        recent,
    ):
        if (
            earlier["trades"]
            < self._MIN_WINDOW_TRADES
            or recent["trades"]
            < self._MIN_WINDOW_TRADES
        ):
            return {
                "directional_consistency_change": None,
                "average_pnl_change": None,
                "stability_state": (
                    "INSUFFICIENT_DATA"
                ),
                "stability_magnitude": None,
            }

        consistency_change = round(
            recent[
                "directional_consistency_percent"
            ]
            - earlier[
                "directional_consistency_percent"
            ],
            4,
        )

        pnl_change = round(
            recent["average_realized_pnl"]
            - earlier["average_realized_pnl"],
            4,
        )

        earlier_direction = earlier["direction"]
        recent_direction = recent["direction"]

        earlier_evidence_score = (
        self._directional_evidence_score(
                earlier_direction,
                earlier[
                    "directional_consistency_percent"
                ],
            )
        )

        recent_evidence_score = (
            self._directional_evidence_score(
                recent_direction,
                recent[
                    "directional_consistency_percent"
                ],
            )
        )

        magnitude = round(
            abs(
                recent_evidence_score
                - earlier_evidence_score
            ),
            4,
        )

        if (
            earlier_direction
            in {"POSITIVE", "NEGATIVE"}
            and recent_direction
            in {"POSITIVE", "NEGATIVE"}
            and earlier_direction != recent_direction
        ):
            state = "DIRECTION_REVERSAL"

        elif (
            earlier_direction == "NEUTRAL"
            and recent_direction
            in {"POSITIVE", "NEGATIVE"}
        ):
            state = "STRENGTHENING"

        elif (
            earlier_direction
            in {"POSITIVE", "NEGATIVE"}
            and recent_direction == "NEUTRAL"
        ):
            state = "WEAKENING"

        elif (
            consistency_change
            >= self._MODERATE_CHANGE_PERCENT
        ):
            state = "STRENGTHENING"

        elif (
            consistency_change
            <= -self._MODERATE_CHANGE_PERCENT
        ):
            state = "WEAKENING"

        else:
            state = "STABLE"

        return {
            "directional_consistency_change": (
                consistency_change
            ),
            "average_pnl_change": pnl_change,
            "stability_state": state,
            "stability_magnitude": magnitude,
        }
    def _directional_evidence_score(
        self,
        direction,
        consistency_percent,
    ):
        if direction == "POSITIVE":
            return consistency_percent

        if direction == "NEGATIVE":
            return -consistency_percent

        return 0.0
    def _strongest_record(
        self,
        records,
        state,
    ):
        candidates = [
            item
            for item in records
            if item["stability_state"] == state
        ]

        if not candidates:
            return None

        return deepcopy(
            sorted(
                candidates,
                key=lambda item: (
                    -(
                        item["stability_magnitude"]
                        or 0.0
                    ),
                    -item["linked_closed_trades"],
                    self._identity(item),
                ),
            )[0]
        )

    def _research_observations(
        self,
        anomaly_stability,
        combination_stability,
        most_strengthened,
        most_weakened,
        strongest_reversal,
    ):
        if (
            not anomaly_stability
            and not combination_stability
        ):
            return [
                (
                    "No anomaly outcome evidence "
                    "was available for stability "
                    "analysis."
                )
            ]

        observations = []

        if strongest_reversal is not None:
            observations.append(
                (
                    f"{self._label(strongest_reversal)} "
                    "showed a direction reversal "
                    "between earlier and recent "
                    "outcome evidence."
                )
            )

        if most_strengthened is not None:
            observations.append(
                (
                    f"{self._label(most_strengthened)} "
                    "showed strengthening recent "
                    "outcome consistency."
                )
            )

        if most_weakened is not None:
            observations.append(
                (
                    f"{self._label(most_weakened)} "
                    "showed weakening recent "
                    "outcome consistency."
                )
            )

        available = [
            item
            for item in (
                anomaly_stability
                + combination_stability
            )
            if item["stability_state"]
            != "INSUFFICIENT_DATA"
        ]

        if (
            available
            and all(
                item["stability_state"] == "STABLE"
                for item in available
            )
        ):
            observations.append(
                (
                    "Available anomaly outcome "
                    "evidence remained stable "
                    "between earlier and recent "
                    "observation windows."
                )
            )

        if not available:
            observations.append(
                (
                    "Observed anomaly outcome "
                    "evidence did not contain "
                    "enough trades in both time "
                    "windows for stability analysis."
                )
            )

        if not observations:
            observations.append(
                (
                    "Anomaly outcome stability was "
                    "measured without establishing "
                    "causation."
                )
            )

        return observations

    def _distribution(
        self,
        records,
        source_key,
        output_key,
    ):
        counts = {}

        for item in records:
            value = item.get(source_key)

            if value is None:
                continue

            counts[value] = (
                counts.get(value, 0) + 1
            )

        return [
            {
                output_key: value,
                "count": counts[value],
            }
            for value in sorted(counts)
        ]

    def _collection(self, value):
        if isinstance(value, (list, tuple)):
            return list(value)

        return []

    def _codes(self, value):
        if not isinstance(value, (list, tuple)):
            return []

        return sorted(
            {
                text
                for item in value
                if (text := self._text(item))
            }
        )

    def _identity(self, item):
        if item["record_type"] == "ANOMALY":
            return item.get("code") or ""

        return "|".join(
            item.get("codes") or []
        )

    def _label(self, item):
        if item["record_type"] == "ANOMALY":
            return item.get("code") or "UNKNOWN"

        codes = item.get("codes") or []

        if not codes:
            return "UNKNOWN COMBINATION"

        return " + ".join(codes)

    def _text(self, value):
        if value is None:
            return None

        text = str(value).strip()

        return text or None

    def _number(self, value):
        if isinstance(value, bool):
            return None

        try:
            number = float(value)
        except (TypeError, ValueError):
            return None

        if not isfinite(number):
            return None

        return number