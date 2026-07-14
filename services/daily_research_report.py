"""Read-only daily aggregation of existing market research engines."""

from copy import deepcopy

from services.blocker_intelligence import BlockerIntelligence
from services.decision_evolution_analyzer import DecisionEvolutionAnalyzer
from services.historical_trade_performance import (
    HistoricalTradePerformanceEngine,
)
from services.market_session_summary import MarketSessionSummaryEngine
from services.session_journal_analytics import SessionJournalAnalyticsEngine
from services.strategy_regime_performance import StrategyRegimePerformanceEngine
from services.trade_readiness_momentum import TradeReadinessMomentum


class DailyResearchReport:
    """Compose existing research outputs without affecting trading state."""

    def __init__(
        self,
        *,
        decision_evolution_analyzer=None,
        trade_readiness_momentum=None,
        blocker_intelligence=None,
        historical_trade_performance=None,
        strategy_regime_performance=None,
        market_session_summary=None,
        session_journal_analytics=None,
    ):
        self.decision_evolution_analyzer = (
            decision_evolution_analyzer or DecisionEvolutionAnalyzer()
        )
        self.trade_readiness_momentum = (
            trade_readiness_momentum or TradeReadinessMomentum()
        )
        self.blocker_intelligence = blocker_intelligence or BlockerIntelligence()
        self.historical_trade_performance = (
            historical_trade_performance or HistoricalTradePerformanceEngine()
        )
        self.strategy_regime_performance = (
            strategy_regime_performance or StrategyRegimePerformanceEngine()
        )
        self.market_session_summary = (
            market_session_summary or MarketSessionSummaryEngine()
        )
        self.session_journal_analytics = (
            session_journal_analytics or SessionJournalAnalyticsEngine()
        )

    @staticmethod
    def _safe_collection(value):
        """Return an independent list accepted by every composed engine."""
        if not isinstance(value, (list, tuple)):
            return []
        return deepcopy(list(value))

    @staticmethod
    def _safe_mapping(value):
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _error_result(error):
        return {
            "status": "ERROR",
            "read_only": True,
            "error": "{}: {}".format(type(error).__name__, str(error)),
        }

    def _safe_call(self, callback):
        try:
            result = callback()
            return deepcopy(result) if isinstance(result, dict) else {}
        except Exception as error:  # Research reports must isolate engines.
            return self._error_result(error)

    @staticmethod
    def _append_observation(observations, seen, message):
        if message not in seen:
            observations.append(message)
            seen.add(message)

    def _research_observations(
        self,
        decision,
        readiness,
        blocker,
        historical,
        regime,
        cycles_observed,
    ):
        observations = []
        seen = set()

        if cycles_observed == 0:
            self._append_observation(
                observations,
                seen,
                (
                    "No market cycles were observed "
                    "for the requested session."
                ),
            )

        else:
            confidence = self._safe_mapping(
                decision.get(
                    "confidence"
                )
            )

            trend = confidence.get(
                "trend"
            )

            if trend == "RISING":
                self._append_observation(
                    observations,
                    seen,
                    (
                        "Confidence increased during "
                        "the observed session."
                    ),
                )

            elif trend == "FALLING":
                self._append_observation(
                    observations,
                    seen,
                    (
                        "Confidence decreased during "
                        "the observed session."
                    ),
                )

            decision_stability = (
                self._safe_mapping(
                    decision.get(
                        "decision_stability"
                    )
                )
            )

            if (
                decision_stability.get(
                    "stable"
                )
                is True
            ):
                self._append_observation(
                    observations,
                    seen,
                    (
                        "Decision state remained stable "
                        "across most observed cycles."
                    ),
                )

            momentum = readiness.get(
                "momentum"
            )

            if momentum == "BUILDING":
                self._append_observation(
                    observations,
                    seen,
                    (
                        "Trade-readiness momentum "
                        "improved during the observed "
                        "session."
                    ),
                )

            elif momentum == "DETERIORATING":
                self._append_observation(
                    observations,
                    seen,
                    (
                        "Trade-readiness momentum "
                        "weakened during the observed "
                        "session."
                    ),
                )

            final_blocker_state = (
                self._safe_mapping(
                    blocker.get(
                        "final_blocker_state"
                    )
                )
            )

            if (
                final_blocker_state.get(
                    "blocked"
                )
                is True
            ):
                self._append_observation(
                    observations,
                    seen,
                    (
                        "One or more blockers remained "
                        "active at the final observed "
                        "cycle."
                    ),
                )

            cleared = blocker.get(
                "cleared_before_trade_ready"
            )

            if (
                cleared is True
                or bool(
                    cleared
                )
                or self._safe_mapping(
                    cleared
                ).get(
                    "cleared"
                )
                is True
            ):
                self._append_observation(
                    observations,
                    seen,
                    (
                        "Observed blockers cleared "
                        "before the first TRADE_READY "
                        "state."
                    ),
                )

            trade_ready = (
                self._safe_mapping(
                    readiness.get(
                        "trade_ready"
                    )
                )
            )

            if (
                trade_ready.get(
                    "observed"
                )
                is False
            ):
                self._append_observation(
                    observations,
                    seen,
                    (
                        "No TRADE_READY state was "
                        "observed."
                    ),
                )

        overall = self._safe_mapping(
            historical.get(
                "overall"
            )
        )

        if (
            overall
            and overall.get(
                "sufficient_sample"
            )
            is False
        ):
            self._append_observation(
                observations,
                seen,
                (
                    "Historical closed-trade sample "
                    "is insufficient for a strong "
                    "research observation."
                ),
            )

        if regime.get(
            "positive_combinations"
        ):
            self._append_observation(
                observations,
                seen,
                (
                    "A historically positive "
                    "strategy-regime combination "
                    "was observed."
                ),
            )

        if regime.get(
            "negative_combinations"
        ):
            self._append_observation(
                observations,
                seen,
                (
                    "A historically negative "
                    "strategy-regime combination "
                    "was observed."
                ),
            )

        return observations
    def _research_snapshot(self, decision, readiness, blocker, regime):
        final_state = self._safe_mapping(decision.get("final_state"))
        confidence = self._safe_mapping(decision.get("confidence"))
        readiness_values = self._safe_mapping(readiness.get("readiness"))
        risk_flags = self._safe_mapping(readiness.get("risk_flags"))
        setup = self._safe_mapping(readiness.get("setup"))
        trade_ready = self._safe_mapping(readiness.get("trade_ready"))
        final_blocker_state = self._safe_mapping(blocker.get("final_blocker_state"))

        return {
            "final_decision": final_state.get("decision"),
            "final_direction": final_state.get("direction"),
            "final_regime": final_state.get("regime"),
            "final_confidence": final_state.get("confidence"),
            "confidence_trend": confidence.get("trend"),
            "readiness_momentum": readiness.get("momentum"),
            "final_readiness": readiness_values.get("final"),
            "final_risk_flag_count": risk_flags.get("final_count"),
            "final_setup_score": setup.get("final_score"),
            "trade_ready_observed": trade_ready.get("observed", False),
            "final_blocked": final_blocker_state.get("blocked", False),
            "final_blocker_state": deepcopy(final_blocker_state) if final_blocker_state else None,
            "positive_strategy_regime_combinations": len(regime.get("positive_combinations") or []),
            "negative_strategy_regime_combinations": len(regime.get("negative_combinations") or []),
            "best_observed_combination": deepcopy(regime.get("best_observed_combination")),
            "worst_observed_combination": deepcopy(regime.get("worst_observed_combination")),
        }

    def build_report(self, entries, *, trades=None, session_date=None):
        """Build deterministic, descriptive intelligence from existing engines."""
        safe_entries = self._safe_collection(entries)
        safe_trades = self._safe_collection(trades)

        session_summary = self._safe_call(
            lambda: self.market_session_summary.summarize(deepcopy(safe_entries), session_date=session_date)
        )
        journal_analytics = self._safe_call(
            lambda: self.session_journal_analytics.analyze(deepcopy(safe_entries), session_date=session_date)
        )
        decision = self._safe_call(
            lambda: self.decision_evolution_analyzer.analyze(deepcopy(safe_entries), session_date=session_date)
        )
        readiness = self._safe_call(
            lambda: self.trade_readiness_momentum.analyze(deepcopy(safe_entries), session_date=session_date)
        )
        blocker = self._safe_call(
            lambda: self.blocker_intelligence.analyze(deepcopy(safe_entries), session_date=session_date)
        )
        historical = self._safe_call(
            lambda: self.historical_trade_performance.analyse(deepcopy(safe_trades))
        )
        regime = self._safe_call(
            lambda: self.strategy_regime_performance.analyze(deepcopy(safe_trades))
        )

        components = (session_summary, journal_analytics, decision, readiness, blocker, historical, regime)
        status = "COMPLETED_WITH_ERRORS" if any(item.get("status") == "ERROR" for item in components) else "COMPLETED"

        return {
            "status": status,
            "read_only": True,
            "research_only": True,
            "session_date": session_date,
            "cycles_observed": len(safe_entries),
            "trades_observed": len(safe_trades),
            "session_intelligence": {
                "market_session_summary": deepcopy(session_summary),
                "journal_analytics": deepcopy(journal_analytics),
            },
            "decision_intelligence": deepcopy(decision),
            "readiness_intelligence": deepcopy(readiness),
            "blocker_intelligence": deepcopy(blocker),
            "historical_performance": deepcopy(historical),
            "strategy_regime_performance": deepcopy(regime),
                        "research_observations": (
                self._research_observations(
                    decision,
                    readiness,
                    blocker,
                    historical,
                    regime,
                    len(
                        safe_entries
                    ),
                )
            ),
            "research_snapshot": self._research_snapshot(decision, readiness, blocker, regime),
        }
