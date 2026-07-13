"""
Paper Trading Orchestrator.

Connects advisory trading decisions to the paper-trading
subsystem without enabling real broker execution.

Responsibilities:
- Accept a completed pipeline decision result.
- Open paper trades only for TRADE_ALLOWED decisions.
- Skip non-trade decisions safely.
- Prevent duplicate source decisions.
- Optionally enforce PaperTradingRiskGuard.
- Preserve source decision and audit references.
- Attach decision snapshots.
- Attach advisory historical context.
- Isolate paper-trading, risk-guard, and historical-context failures.
- Return structured orchestration results.

IMPORTANT:
- PAPER TRADING ONLY.
- Does NOT place real broker orders.
- Historical context is advisory only.
- Historical context cannot override live safety.
"""

from copy import deepcopy

from services.decision_snapshot import (
    build_decision_snapshot,
)

from services.historical_context_engine import (
    HistoricalContextEngine,
)


class PaperTradingOrchestrator:

    STATUS_OPENED = "OPENED"
    STATUS_SKIPPED = "SKIPPED"
    STATUS_FAILED = "FAILED"

    TRADE_ALLOWED = "TRADE_ALLOWED"

    def __init__(
        self,
        paper_trading_engine,
        enabled=True,
        risk_guard=None,
        historical_context_engine=None,
    ):
        if paper_trading_engine is None:
            raise ValueError(
                "paper_trading_engine is required."
            )

        if not isinstance(
            enabled,
            bool,
        ):
            raise ValueError(
                "enabled must be a boolean."
            )

        if (
            risk_guard is not None
            and not callable(
                getattr(
                    risk_guard,
                    "evaluate",
                    None,
                )
            )
        ):
            raise ValueError(
                "risk_guard must expose an evaluate method."
            )

        if (
            historical_context_engine is not None
            and not callable(
                getattr(
                    historical_context_engine,
                    "evaluate",
                    None,
                )
            )
        ):
            raise ValueError(
                "historical_context_engine must expose "
                "an evaluate method."
            )

        self.paper_trading_engine = (
            paper_trading_engine
        )

        self.enabled = enabled

        self.risk_guard = (
            risk_guard
        )

        self.historical_context_engine = (
            historical_context_engine
            if historical_context_engine is not None
            else HistoricalContextEngine()
        )

        self._processed_decision_ids = set()

    # ========================================================
    # PUBLIC API
    # ========================================================

    def process_decision(
        self,
        pipeline_result,
        *,
        underlying,
        exchange,
        symboltoken,
        source_decision_id=None,
        source_audit_ref=None,
        opened_at=None,
        metadata=None,
        trade_id=None,
    ):
        self._validate_pipeline_result(
            pipeline_result
        )

        self._validate_required_text(
            underlying,
            "underlying",
        )

        self._validate_required_text(
            exchange,
            "exchange",
        )

        self._validate_required_text(
            symboltoken,
            "symboltoken",
        )

        self._validate_optional_text(
            source_decision_id,
            "source_decision_id",
        )

        self._validate_optional_text(
            source_audit_ref,
            "source_audit_ref",
        )

        self._validate_optional_text(
            opened_at,
            "opened_at",
        )

        self._validate_optional_text(
            trade_id,
            "trade_id",
        )

        if (
            metadata is not None
            and not isinstance(
                metadata,
                dict,
            )
        ):
            raise ValueError(
                "metadata must be a dictionary or None."
            )

        decision = (
            pipeline_result.get(
                "decision"
            )
        )

        # ----------------------------------------------------
        # ORCHESTRATION DISABLED
        # ----------------------------------------------------

        if not self.enabled:
            return self._build_result(
                status=self.STATUS_SKIPPED,
                reason="PAPER_TRADING_DISABLED",
                decision=decision,
                source_decision_id=(
                    source_decision_id
                ),
            )

        # ----------------------------------------------------
        # NON-TRADE DECISION
        # ----------------------------------------------------

        if (
            decision
            != self.TRADE_ALLOWED
        ):
            return self._build_result(
                status=self.STATUS_SKIPPED,
                reason=(
                    "DECISION_NOT_TRADE_ALLOWED"
                ),
                decision=decision,
                source_decision_id=(
                    source_decision_id
                ),
            )

        # ----------------------------------------------------
        # DUPLICATE SOURCE DECISION
        # ----------------------------------------------------

        if (
            source_decision_id
            is not None
            and source_decision_id
            in self._processed_decision_ids
        ):
            return self._build_result(
                status=self.STATUS_SKIPPED,
                reason=(
                    "DUPLICATE_SOURCE_DECISION"
                ),
                decision=decision,
                source_decision_id=(
                    source_decision_id
                ),
            )

        # ----------------------------------------------------
        # RISK GUARD
        # ----------------------------------------------------

        risk_result = (
            self._evaluate_risk_guard(
                pipeline_result=(
                    pipeline_result
                ),
                underlying=underlying,
                symboltoken=symboltoken,
            )
        )

        if (
            risk_result is not None
            and not risk_result.get(
                "allowed",
                False,
            )
        ):
            return self._build_result(
                status=self.STATUS_SKIPPED,
                reason="RISK_GUARD_BLOCKED",
                decision=decision,
                source_decision_id=(
                    source_decision_id
                ),
                risk_guard=(
                    risk_result
                ),
            )

        # ----------------------------------------------------
        # DECISION SNAPSHOT
        # ----------------------------------------------------

        decision_snapshot = (
            build_decision_snapshot(
                pipeline_result
            )
        )

        # ----------------------------------------------------
        # HISTORICAL CONTEXT
        #
        # Advisory only.
        # It cannot:
        # - Block the trade
        # - Change direction
        # - Change strategy
        # - Change quantity
        # - Change stop-loss
        # - Override live safety
        # ----------------------------------------------------

        historical_context = (
            self._evaluate_historical_context(
                decision_snapshot=(
                    decision_snapshot
                )
            )
        )

        # ----------------------------------------------------
        # SAFE METADATA
        # ----------------------------------------------------

        safe_metadata = (
            deepcopy(
                metadata
            )
            if metadata is not None
            else {}
        )

        safe_metadata.setdefault(
            "orchestrated_by",
            "PaperTradingOrchestrator",
        )

        safe_metadata.setdefault(
            "paper_trade",
            True,
        )

        safe_metadata.setdefault(
            "decision_snapshot",
            deepcopy(
                decision_snapshot
            ),
        )

        safe_metadata.setdefault(
            "historical_context",
            deepcopy(
                historical_context
            ),
        )

        if risk_result is not None:
            safe_metadata[
                "risk_guard"
            ] = deepcopy(
                risk_result
            )

        # ----------------------------------------------------
        # OPEN PAPER TRADE
        # ----------------------------------------------------

        try:
            trade = (
                self.paper_trading_engine
                .open_trade(
                    pipeline_result=(
                        deepcopy(
                            pipeline_result
                        )
                    ),
                    underlying=underlying,
                    exchange=exchange,
                    symboltoken=symboltoken,
                    source_decision_id=(
                        source_decision_id
                    ),
                    source_audit_ref=(
                        source_audit_ref
                    ),
                    opened_at=opened_at,
                    metadata=safe_metadata,
                    trade_id=trade_id,
                )
            )

        except Exception as exc:
            return self._build_result(
                status=self.STATUS_FAILED,
                reason=(
                    "PAPER_TRADE_OPEN_FAILED"
                ),
                decision=decision,
                source_decision_id=(
                    source_decision_id
                ),
                error=str(
                    exc
                ),
                risk_guard=(
                    risk_result
                ),
            )

        # ----------------------------------------------------
        # MARK SOURCE DECISION AFTER SUCCESS
        # ----------------------------------------------------

        if (
            source_decision_id
            is not None
        ):
            self._processed_decision_ids.add(
                source_decision_id
            )

        return self._build_result(
            status=self.STATUS_OPENED,
            reason="PAPER_TRADE_OPENED",
            decision=decision,
            source_decision_id=(
                source_decision_id
            ),
            trade=trade,
            risk_guard=(
                risk_result
            ),
        )

    def process(
        self,
        pipeline_result,
        **kwargs,
    ):
        return self.process_decision(
            pipeline_result,
            **kwargs,
        )

    def has_processed_decision(
        self,
        source_decision_id,
    ):
        self._validate_required_text(
            source_decision_id,
            "source_decision_id",
        )

        return (
            source_decision_id
            in self._processed_decision_ids
        )

    def get_processed_decision_ids(
        self,
    ):
        return set(
            self._processed_decision_ids
        )

    def clear_processed_decision_ids(
        self,
    ):
        self._processed_decision_ids.clear()

    # ========================================================
    # HISTORICAL CONTEXT
    # ========================================================

    def _evaluate_historical_context(
        self,
        *,
        decision_snapshot,
    ):
        """
        Build advisory historical context from previous
        paper trades.

        Historical context must never block or modify the
        current live trading decision.

        Failures are isolated and returned as advisory
        metadata instead of failing the paper trade.
        """

        try:
            trades = (
                self.paper_trading_engine
                .get_all_trades()
            )

        except Exception as exc:
            return {
                "historical_bias": (
                    "INSUFFICIENT_DATA"
                ),
                "similar_trades": 0,
                "sufficient_sample": False,
                "reason": (
                    "Historical trade data could not "
                    "be loaded."
                ),
                "error": (
                    f"{type(exc).__name__}: {exc}"
                ),
                "advisory_only": True,
                "can_override_live_safety": False,
            }

        try:
            result = (
                self.historical_context_engine
                .evaluate(
                    trades=trades,
                    decision_snapshot=(
                        deepcopy(
                            decision_snapshot
                        )
                    ),
                )
            )

        except Exception as exc:
            return {
                "historical_bias": (
                    "INSUFFICIENT_DATA"
                ),
                "similar_trades": 0,
                "sufficient_sample": False,
                "reason": (
                    "Historical context evaluation "
                    "failed."
                ),
                "error": (
                    f"{type(exc).__name__}: {exc}"
                ),
                "advisory_only": True,
                "can_override_live_safety": False,
            }

        if not isinstance(
            result,
            dict,
        ):
            return {
                "historical_bias": (
                    "INSUFFICIENT_DATA"
                ),
                "similar_trades": 0,
                "sufficient_sample": False,
                "reason": (
                    "Historical context engine "
                    "returned invalid data."
                ),
                "error": (
                    "INVALID_HISTORICAL_CONTEXT_RESULT"
                ),
                "advisory_only": True,
                "can_override_live_safety": False,
            }

        safe_result = deepcopy(
            result
        )

        # Enforce advisory-only safety regardless
        # of the historical engine output.

        safe_result[
            "advisory_only"
        ] = True

        safe_result[
            "can_override_live_safety"
        ] = False

        return safe_result

    # ========================================================
    # RISK GUARD
    # ========================================================

    def _evaluate_risk_guard(
        self,
        *,
        pipeline_result,
        underlying,
        symboltoken,
    ):
        if self.risk_guard is None:
            return None

        try:
            trades = (
                self.paper_trading_engine
                .get_all_trades()
            )

        except Exception as exc:
            return {
                "allowed": False,
                "code": (
                    "TRADE_HISTORY_UNAVAILABLE"
                ),
                "message": (
                    "Paper trade blocked because "
                    "trade history could not be loaded: "
                    f"{type(exc).__name__}: {exc}"
                ),
                "metrics": {},
            }

        candidate = (
            self._build_risk_candidate(
                pipeline_result=(
                    pipeline_result
                ),
                underlying=underlying,
                symboltoken=symboltoken,
            )
        )

        try:
            result = (
                self.risk_guard.evaluate(
                    candidate,
                    trades,
                )
            )

        except Exception as exc:
            return {
                "allowed": False,
                "code": "RISK_GUARD_ERROR",
                "message": (
                    "Paper trade blocked because "
                    "the risk guard failed: "
                    f"{type(exc).__name__}: {exc}"
                ),
                "metrics": {},
            }

        if not isinstance(
            result,
            dict,
        ):
            return {
                "allowed": False,
                "code": (
                    "INVALID_RISK_GUARD_RESULT"
                ),
                "message": (
                    "Paper trade blocked because "
                    "the risk guard returned invalid data."
                ),
                "metrics": {},
            }

        if not isinstance(
            result.get(
                "allowed"
            ),
            bool,
        ):
            return {
                "allowed": False,
                "code": (
                    "INVALID_RISK_GUARD_RESULT"
                ),
                "message": (
                    "Paper trade blocked because "
                    "the risk guard result did not contain "
                    "a valid allowed flag."
                ),
                "metrics": {},
            }

        return deepcopy(
            result
        )

    @classmethod
    def _build_risk_candidate(
        cls,
        *,
        pipeline_result,
        underlying,
        symboltoken,
    ):
        option_symbol = (
            cls._find_nested_value(
                pipeline_result,
                (
                    "option_symbol",
                    "tradingsymbol",
                    "trading_symbol",
                    "symbol",
                ),
            )
        )

        return {
            "underlying": underlying,
            "option_symbol": (
                option_symbol
            ),
            "symboltoken": symboltoken,
        }

    @classmethod
    def _find_nested_value(
        cls,
        value,
        keys,
    ):
        if isinstance(
            value,
            dict,
        ):
            for key in keys:
                candidate = (
                    value.get(
                        key
                    )
                )

                if (
                    candidate is not None
                    and str(
                        candidate
                    ).strip()
                ):
                    return candidate

            for nested_value in (
                value.values()
            ):
                found = (
                    cls._find_nested_value(
                        nested_value,
                        keys,
                    )
                )

                if found is not None:
                    return found

        elif isinstance(
            value,
            (list, tuple),
        ):
            for item in value:
                found = (
                    cls._find_nested_value(
                        item,
                        keys,
                    )
                )

                if found is not None:
                    return found

        return None

    # ========================================================
    # VALIDATION
    # ========================================================

    @staticmethod
    def _validate_pipeline_result(
        pipeline_result,
    ):
        if not isinstance(
            pipeline_result,
            dict,
        ):
            raise ValueError(
                "pipeline_result must be a dictionary."
            )

        if "decision" not in pipeline_result:
            raise ValueError(
                "pipeline_result must contain decision."
            )

        decision = (
            pipeline_result.get(
                "decision"
            )
        )

        if not isinstance(
            decision,
            str,
        ):
            raise ValueError(
                "pipeline_result decision must be a string."
            )

        if not decision.strip():
            raise ValueError(
                "pipeline_result decision must not be empty."
            )

    @staticmethod
    def _validate_required_text(
        value,
        field_name,
    ):
        if not isinstance(
            value,
            str,
        ):
            raise ValueError(
                f"{field_name} must be a string."
            )

        if not value.strip():
            raise ValueError(
                f"{field_name} must not be empty."
            )

    @staticmethod
    def _validate_optional_text(
        value,
        field_name,
    ):
        if value is None:
            return

        if not isinstance(
            value,
            str,
        ):
            raise ValueError(
                f"{field_name} must be a string or None."
            )

        if not value.strip():
            raise ValueError(
                f"{field_name} must not be empty."
            )

    # ========================================================
    # RESULT HELPERS
    # ========================================================

    @staticmethod
    def _trade_to_dict(
        trade,
    ):
        if trade is None:
            return None

        if isinstance(
            trade,
            dict,
        ):
            return deepcopy(
                trade
            )

        if hasattr(
            trade,
            "as_dict",
        ):
            return deepcopy(
                trade.as_dict()
            )

        if hasattr(
            trade,
            "to_dict",
        ):
            return deepcopy(
                trade.to_dict()
            )

        return deepcopy(
            trade
        )

    def _build_result(
        self,
        *,
        status,
        reason,
        decision,
        source_decision_id=None,
        trade=None,
        error=None,
        risk_guard=None,
    ):
        trade_data = (
            self._trade_to_dict(
                trade
            )
        )

        trade_id = None

        if isinstance(
            trade_data,
            dict,
        ):
            trade_id = (
                trade_data.get(
                    "trade_id"
                )
            )

        elif (
            trade is not None
            and hasattr(
                trade,
                "trade_id",
            )
        ):
            trade_id = (
                trade.trade_id
            )

        return {
            "status": status,
            "opened": (
                status
                == self.STATUS_OPENED
            ),
            "skipped": (
                status
                == self.STATUS_SKIPPED
            ),
            "failed": (
                status
                == self.STATUS_FAILED
            ),
            "reason": reason,
            "decision": decision,
            "source_decision_id": (
                source_decision_id
            ),
            "trade_id": trade_id,
            "trade": trade_data,
            "error": error,
            "risk_guard": (
                deepcopy(
                    risk_guard
                )
                if risk_guard is not None
                else None
            ),
        }