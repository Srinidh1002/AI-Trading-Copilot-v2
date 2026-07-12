"""
Paper Trading Orchestrator.

Connects advisory trading decisions to the paper-trading
subsystem without enabling real broker execution.

Responsibilities:
- Accept a completed pipeline decision result.
- Open paper trades only for TRADE_ALLOWED decisions.
- Skip non-trade decisions safely.
- Prevent duplicate source decisions from opening
  duplicate paper trades.
- Preserve source decision and audit references.
- Isolate paper-trading failures from the decision pipeline.
- Return structured orchestration results.

This module:
- Does NOT place real broker orders.
- Does NOT modify the decision pipeline.
- Does NOT call broker execution APIs.
"""

from copy import deepcopy
from typing import Any, Dict, Optional


class PaperTradingOrchestrator:
    """
    Coordinate decision results with PaperTradingEngine.
    """

    STATUS_OPENED = "OPENED"
    STATUS_SKIPPED = "SKIPPED"
    STATUS_FAILED = "FAILED"

    TRADE_ALLOWED = "TRADE_ALLOWED"

    def __init__(
        self,
        paper_trading_engine,
        enabled=True,
    ):
        """
        Initialize the orchestrator.

        Parameters
        ----------
        paper_trading_engine
            PaperTradingEngine-compatible instance.

        enabled : bool
            Whether automatic paper-trade orchestration
            is enabled.
        """

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

        self.paper_trading_engine = (
            paper_trading_engine
        )

        self.enabled = enabled

        # Tracks source decision IDs successfully opened
        # during the current process lifetime.
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
        """
        Process one completed decision result.

        A paper trade is opened only when:

        - orchestrator is enabled
        - pipeline_result is valid
        - decision == TRADE_ALLOWED
        - source_decision_id has not already been processed

        Returns
        -------
        dict
            Structured orchestration result.

        Notes
        -----
        Paper-trading engine exceptions are isolated and
        returned as FAILED results.

        The original pipeline_result is never modified.
        """

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
                reason=(
                    "PAPER_TRADING_DISABLED"
                ),
                decision=decision,
                source_decision_id=(
                    source_decision_id
                ),
            )

        # ----------------------------------------------------
        # DECISION IS NOT TRADE_ALLOWED
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
        # DUPLICATE DECISION PROTECTION
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
        # BUILD SAFE METADATA
        # ----------------------------------------------------

        safe_metadata = (
            deepcopy(metadata)
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
                error=str(exc),
            )

        # ----------------------------------------------------
        # MARK DECISION AS PROCESSED ONLY AFTER SUCCESS
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
            reason=(
                "PAPER_TRADE_OPENED"
            ),
            decision=decision,
            source_decision_id=(
                source_decision_id
            ),
            trade=trade,
        )

    def process(
        self,
        pipeline_result,
        **kwargs,
    ):
        """
        Alias for process_decision().
        """

        return self.process_decision(
            pipeline_result,
            **kwargs,
        )

    def has_processed_decision(
        self,
        source_decision_id,
    ):
        """
        Return whether a source decision ID has already
        opened a paper trade in this process.
        """

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
        """
        Return a defensive copy of processed decision IDs.
        """

        return set(
            self._processed_decision_ids
        )

    def clear_processed_decision_ids(
        self,
    ):
        """
        Clear in-memory duplicate tracking.

        Intended for controlled testing or explicit lifecycle
        reset only.
        """

        self._processed_decision_ids.clear()

    # ========================================================
    # INTERNAL HELPERS
    # ========================================================

    @staticmethod
    def _validate_pipeline_result(
        pipeline_result,
    ):
        """
        Validate the top-level pipeline result.
        """

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
        """
        Validate required non-empty text.
        """

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
        """
        Validate optional text.
        """

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

    @staticmethod
    def _trade_to_dict(
        trade,
    ):
        """
        Convert a trade object into a safe dictionary.

        Supports:
        - objects exposing as_dict()
        - objects exposing to_dict()
        - dictionaries
        """

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

        # Fallback preserves the trade object safely enough
        # for compatibility with mocked/custom engines.
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
    ):
        """
        Build a consistent orchestration result.
        """

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
        }