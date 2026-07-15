"""
Trade Readiness Convergence Intelligence.

Combines chronological candidate momentum and trigger-approach
intelligence to study whether independent pre-trade signals are
converging toward trade readiness.

IMPORTANT:
- READ ONLY.
- RESEARCH AND OBSERVABILITY ONLY.
- DOES NOT authorize trades.
- DOES NOT reject trades.
- DOES NOT modify live decision logic.
- DOES NOT modify paper-trading state.
- DOES NOT place real orders.
"""

from copy import deepcopy


class TradeReadinessConvergence:
    """
    Analyze convergence between candidate momentum and
    trigger-approach intelligence.
    """

    STATUS_COMPLETED = "COMPLETED"

    CONVERGENCE_STRONG = "STRONG"
    CONVERGENCE_MODERATE = "MODERATE"
    CONVERGENCE_WEAK = "WEAK"
    CONVERGENCE_DIVERGING = "DIVERGING"
    CONVERGENCE_UNAVAILABLE = "UNAVAILABLE"

    CANDIDATE_RISING = "RISING"
    CANDIDATE_FALLING = "FALLING"

    TRIGGER_CLOSING = "CLOSING"
    TRIGGER_MOVING_AWAY = "MOVING_AWAY"

    SPEED_ACCELERATING = "ACCELERATING"

    def _safe_dict(
        self,
        value,
    ):
        if isinstance(
            value,
            dict,
        ):
            return deepcopy(
                value
            )

        return {}

    def _normalize_label(
        self,
        value,
    ):
        if value is None:
            return None

        normalized = str(
            value
        ).strip()

        if not normalized:
            return None

        return normalized.upper()

    def _safe_float(
        self,
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

    def _candidate_signal(
        self,
        candidate_momentum,
    ):
        observations = (
            candidate_momentum.get(
                "observations",
                0,
            )
        )

        trend = self._normalize_label(
            candidate_momentum.get(
                "trend"
            )
        )

        change = self._safe_float(
            candidate_momentum.get(
                "change"
            )
        )

        longest_increase = (
            candidate_momentum.get(
                "longest_increase_sequence",
                0,
            )
        )

        rising = (
            observations >= 2
            and trend
            == self.CANDIDATE_RISING
            and change is not None
            and change > 0
        )

        persistent_rise = (
            rising
            and longest_increase >= 2
        )

        return {
            "observations": observations,
            "trend": trend,
            "change": change,
            "longest_increase_sequence": (
                longest_increase
            ),
            "rising": rising,
            "persistent_rise": persistent_rise,
        }

    def _trigger_signal(
        self,
        trigger_approach,
    ):
        observations = (
            trigger_approach.get(
                "observations",
                0,
            )
        )

        trend = self._normalize_label(
            trigger_approach.get(
                "approach_trend"
            )
        )

        speed = self._normalize_label(
            trigger_approach.get(
                "approach_speed"
            )
        )

        total_distance_closed = (
            self._safe_float(
                trigger_approach.get(
                    "total_distance_closed_percent"
                )
            )
        )

        final_distance = self._safe_float(
            trigger_approach.get(
                "final_distance_percent"
            )
        )

        closing = (
            observations >= 2
            and trend
            == self.TRIGGER_CLOSING
            and total_distance_closed
            is not None
            and total_distance_closed > 0
        )

        accelerating = (
            closing
            and speed
            == self.SPEED_ACCELERATING
        )

        return {
            "observations": observations,
            "trend": trend,
            "speed": speed,
            "total_distance_closed_percent": (
                total_distance_closed
            ),
            "final_distance_percent": (
                final_distance
            ),
            "closing": closing,
            "accelerating": accelerating,
        }

    def _determine_convergence(
        self,
        candidate_signal,
        trigger_signal,
    ):
        candidate_observations = (
            candidate_signal.get(
                "observations",
                0,
            )
        )

        trigger_observations = (
            trigger_signal.get(
                "observations",
                0,
            )
        )

        if (
            candidate_observations < 2
            or trigger_observations < 2
        ):
            return self.CONVERGENCE_UNAVAILABLE

        candidate_rising = (
            candidate_signal.get(
                "rising",
                False,
            )
        )

        persistent_rise = (
            candidate_signal.get(
                "persistent_rise",
                False,
            )
        )

        trigger_closing = (
            trigger_signal.get(
                "closing",
                False,
            )
        )

        trigger_accelerating = (
            trigger_signal.get(
                "accelerating",
                False,
            )
        )

        if (
            persistent_rise
            and trigger_closing
            and trigger_accelerating
        ):
            return self.CONVERGENCE_STRONG

        if (
            candidate_rising
            and trigger_closing
        ):
            return self.CONVERGENCE_MODERATE

        candidate_trend = (
            candidate_signal.get(
                "trend"
            )
        )

        trigger_trend = (
            trigger_signal.get(
                "trend"
            )
        )

        if (
            candidate_trend
            == self.CANDIDATE_FALLING
            or trigger_trend
            == self.TRIGGER_MOVING_AWAY
        ):
            return self.CONVERGENCE_DIVERGING

        return self.CONVERGENCE_WEAK

    def _build_reasons(
        self,
        convergence,
        candidate_signal,
        trigger_signal,
    ):
        reasons = []

        if candidate_signal.get(
            "rising",
            False,
        ):
            reasons.append(
                "Trade candidate score is rising."
            )

        if candidate_signal.get(
            "persistent_rise",
            False,
        ):
            reasons.append(
                "Trade candidate improvement is persistent."
            )

        if trigger_signal.get(
            "closing",
            False,
        ):
            reasons.append(
                "Market price is closing distance to the setup trigger."
            )

        if trigger_signal.get(
            "accelerating",
            False,
        ):
            reasons.append(
                "Trigger approach speed is accelerating."
            )

        if (
            convergence
            == self.CONVERGENCE_DIVERGING
        ):
            reasons.append(
                "At least one readiness signal is moving away from trade readiness."
            )

        if (
            convergence
            == self.CONVERGENCE_UNAVAILABLE
        ):
            reasons.append(
                "Insufficient chronological observations for convergence analysis."
            )

        return reasons

    def analyze(
        self,
        evolution_analysis,
        *,
        session_date=None,
    ):
        """
        Analyze trade-readiness convergence.
        """

        if not isinstance(
            evolution_analysis,
            dict,
        ):
            raise ValueError(
                "evolution_analysis must be a dictionary."
            )

        candidate_momentum = (
            self._safe_dict(
                evolution_analysis.get(
                    "candidate_momentum"
                )
            )
        )

        trigger_approach = (
            self._safe_dict(
                evolution_analysis.get(
                    "trigger_approach"
                )
            )
        )

        candidate_signal = (
            self._candidate_signal(
                candidate_momentum
            )
        )

        trigger_signal = (
            self._trigger_signal(
                trigger_approach
            )
        )

        convergence = (
            self._determine_convergence(
                candidate_signal,
                trigger_signal,
            )
        )

        reasons = self._build_reasons(
            convergence,
            candidate_signal,
            trigger_signal,
        )

        return {
            "status": self.STATUS_COMPLETED,
            "read_only": True,
            "session_date": session_date,
            "convergence": convergence,
            "candidate_signal": (
                candidate_signal
            ),
            "trigger_signal": (
                trigger_signal
            ),
            "reasons": reasons,
        }
