"""
Paper trading lifecycle engine.

Manages simulated option positions through their lifecycle:

TRADE_ALLOWED
    -> OPEN
    -> PRICE UPDATE
    -> UNREALIZED P&L
    -> STOP LOSS / TARGET / MANUAL EXIT
    -> CLOSED
    -> REALIZED P&L

The engine also integrates:
- PaperTradeLifecycleAudit for structured in-memory events.
- PaperTradeJournal for optional persistent JSONL logging.

Journal persistence is optional and failure-isolated.
A journal failure must never change a paper-trade state,
P&L result, or lifecycle decision.

This module is paper-only.
It does not connect to brokers and does not place orders.
"""

import math
from copy import deepcopy

from services.paper_trade import (
    PaperTrade,
    PaperTradeExitReason,
    PaperTradeStatus,
)

from services.paper_trade_validator import (
    PaperTradeValidator,
)

from services.paper_pnl_engine import (
    PaperPnLEngine,
)

from services.paper_trade_lifecycle_audit import (
    PaperTradeLifecycleAudit,
)

from services.paper_trade_journal import (
    PaperTradeJournal,
)


class PaperTradingEngine:
    """
    Manage in-memory paper trade positions.

    Responsibilities:
    - Open validated paper trades.
    - Prevent duplicate trade IDs.
    - Retrieve paper trades safely.
    - Update open positions with simulated market prices.
    - Calculate unrealized P&L.
    - Automatically close positions at stop loss or target.
    - Support manual simulated exits.
    - Calculate realized P&L.
    - Record structured lifecycle audit events.
    - Optionally persist lifecycle events.
    - Isolate journal failures from paper-trade behavior.
    - Preserve defensive-copy boundaries.

    This engine never places real broker orders.
    """

    def __init__(
        self,
        validator=None,
        pnl_engine=None,
        lifecycle_audit_factory=None,
        journal=None,
        persist_journal=False,
    ):
        self.validator = (
            validator
            if validator is not None
            else PaperTradeValidator
        )

        self.pnl_engine = (
            pnl_engine
            if pnl_engine is not None
            else PaperPnLEngine
        )

        self.lifecycle_audit_factory = (
            lifecycle_audit_factory
            if lifecycle_audit_factory is not None
            else PaperTradeLifecycleAudit
        )

        if not callable(
            self.lifecycle_audit_factory
        ):
            raise TypeError(
                "lifecycle_audit_factory must be callable."
            )

        self.journal = journal

        self.persist_journal = bool(
            persist_journal
        )

        self._trades = {}

        self._lifecycle_audits = {}

        self._journal_status = {}

    # ---------------------------------
    # VALIDATION HELPERS
    # ---------------------------------

    @staticmethod
    def _validate_trade_id(
        trade_id,
    ):
        """
        Validate and normalize a trade ID.
        """

        if trade_id is None:
            raise ValueError(
                "trade_id is required."
            )

        text = str(
            trade_id
        ).strip()

        if not text:
            raise ValueError(
                "trade_id must not be empty."
            )

        return text

    @staticmethod
    def _validate_price(
        price,
        field_name="price",
    ):
        """
        Validate a finite positive simulated market price.
        """

        if isinstance(
            price,
            bool,
        ):
            raise ValueError(
                f"{field_name} must be a positive number."
            )

        try:
            resolved_price = float(
                price
            )

        except (
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(
                f"{field_name} must be a positive number."
            ) from exc

        if not math.isfinite(
            resolved_price
        ):
            raise ValueError(
                f"{field_name} must be finite."
            )

        if resolved_price <= 0:
            raise ValueError(
                f"{field_name} must be greater than zero."
            )

        return resolved_price

    @staticmethod
    def _validate_exit_reason(
        exit_reason,
    ):
        """
        Validate and normalize a paper trade exit reason.
        """

        if exit_reason is None:
            raise ValueError(
                "exit_reason is required."
            )

        normalized = str(
            exit_reason
        ).strip().upper()

        if normalized not in PaperTradeExitReason.ALL:
            raise ValueError(
                "exit_reason must be STOP_LOSS, "
                "TARGET, or MANUAL_EXIT."
            )

        return normalized

    # ---------------------------------
    # INTERNAL STORAGE HELPERS
    # ---------------------------------

    def _require_trade(
        self,
        trade_id,
    ):
        """
        Return the internally stored trade.

        This method intentionally returns the internal
        object and must only be used inside this engine.
        """

        resolved_trade_id = (
            self._validate_trade_id(
                trade_id
            )
        )

        if resolved_trade_id not in self._trades:
            raise ValueError(
                f"Paper trade not found: "
                f"{resolved_trade_id}"
            )

        return self._trades[
            resolved_trade_id
        ]

    def _require_open_trade(
        self,
        trade_id,
    ):
        """
        Return an internally stored OPEN trade.
        """

        trade = self._require_trade(
            trade_id
        )

        if trade.status != PaperTradeStatus.OPEN:
            raise ValueError(
                "Paper trade must be OPEN."
            )

        return trade

    def _require_lifecycle_audit(
        self,
        trade_id,
    ):
        """
        Return the lifecycle audit for a paper trade.
        """

        resolved_trade_id = (
            self._validate_trade_id(
                trade_id
            )
        )

        if (
            resolved_trade_id
            not in self._lifecycle_audits
        ):
            raise ValueError(
                "Lifecycle audit not found for "
                f"paper trade: {resolved_trade_id}"
            )

        return self._lifecycle_audits[
            resolved_trade_id
        ]

    # ---------------------------------
    # JOURNAL HELPERS
    # ---------------------------------

    def _build_journal_metadata(
        self,
        trade,
    ):
        """
        Build stable metadata for journal persistence.
        """

        return {
            "underlying": (
                trade.underlying
            ),
            "exchange": (
                trade.exchange
            ),
            "option_symbol": (
                trade.option_symbol
            ),
            "option_type": (
                trade.option_type
            ),
            "strike": (
                trade.strike
            ),
            "expiry": (
                trade.expiry
            ),
            "direction": (
                trade.direction
            ),
            "symboltoken": (
                trade.symboltoken
            ),
            "source_decision_id": (
                trade.source_decision_id
            ),
            "source_audit_ref": (
                trade.source_audit_ref
            ),
        }

    def _persist_lifecycle_event(
        self,
        trade,
        lifecycle_event,
    ):
        """
        Optionally persist one lifecycle event.

        Persistence is deliberately failure-isolated.

        A journal exception:
        - is captured
        - is reported through journal status
        - does not change the paper trade
        - does not change P&L
        - does not raise into the trade lifecycle
        """

        status = {
            "enabled": (
                self.persist_journal
            ),
            "persisted": False,
            "error": None,
        }

        if not self.persist_journal:
            self._journal_status[
                trade.trade_id
            ] = deepcopy(
                status
            )

            return deepcopy(
                status
            )

        if self.journal is None:
            status[
                "error"
            ] = (
                "Journal persistence is enabled "
                "but no journal is configured."
            )

            self._journal_status[
                trade.trade_id
            ] = deepcopy(
                status
            )

            return deepcopy(
                status
            )

        try:
            self.journal.log(
                lifecycle_event=(
                    lifecycle_event
                ),
                metadata=(
                    self._build_journal_metadata(
                        trade
                    )
                ),
            )

            status[
                "persisted"
            ] = True

        except Exception as exc:
            status[
                "error"
            ] = str(
                exc
            )

        self._journal_status[
            trade.trade_id
        ] = deepcopy(
            status
        )

        return deepcopy(
            status
        )

    def _record_and_persist(
        self,
        trade,
        recorder,
        **kwargs,
    ):
        """
        Record one lifecycle event and optionally persist it.

        The in-memory lifecycle event is authoritative.
        Journal persistence is secondary and cannot
        modify the trade lifecycle.
        """

        lifecycle_event = (
            recorder(
                **kwargs
            )
        )

        self._persist_lifecycle_event(
            trade=trade,
            lifecycle_event=(
                lifecycle_event
            ),
        )

        return deepcopy(
            lifecycle_event
        )

    # ---------------------------------
    # OPEN PAPER TRADE
    # ---------------------------------

    def open_trade(
        self,
        pipeline_result,
        underlying,
        exchange,
        symboltoken=None,
        source_decision_id=None,
        source_audit_ref=None,
        opened_at=None,
        metadata=None,
        trade_id=None,
    ):
        """
        Open a new simulated paper trade.

        The pipeline result must pass the strict
        PaperTradeValidator and must contain an explicit
        TRADE_ALLOWED decision.

        A lifecycle OPENED event is recorded after the
        paper trade has been successfully created.

        No real order is placed.
        """

        validated = (
            self.validator.validate_open_request(
                pipeline_result=(
                    pipeline_result
                ),
                underlying=underlying,
                exchange=exchange,
                symboltoken=symboltoken,
            )
        )

        contract = validated[
            "contract"
        ]

        trade_plan = validated[
            "trade_plan"
        ]

        levels = trade_plan[
            "levels"
        ]

        risk = trade_plan[
            "risk"
        ]

        resolved_trade_id = None

        if trade_id is not None:
            resolved_trade_id = (
                self._validate_trade_id(
                    trade_id
                )
            )

            if resolved_trade_id in self._trades:
                raise ValueError(
                    "A paper trade with this trade_id "
                    "already exists."
                )

        trade = PaperTrade.create(
            underlying=validated[
                "underlying"
            ],
            exchange=validated[
                "exchange"
            ],
            option_symbol=contract[
                "symbol"
            ],
            option_type=contract[
                "option_type"
            ],
            strike=contract[
                "strike"
            ],
            expiry=contract[
                "expiry"
            ],
            direction=validated[
                "direction"
            ],
            entry_price=levels[
                "option_entry_price"
            ],
            stop_loss_price=levels[
                "option_stop_loss"
            ],
            target_price=levels[
                "option_target"
            ],
            lot_size=contract[
                "lot_size"
            ],
            lots=risk[
                "lots"
            ],
            required_capital=risk[
                "required_capital"
            ],
            estimated_maximum_loss=risk[
                "estimated_maximum_loss"
            ],
            symboltoken=validated[
                "symboltoken"
            ],
            source_decision_id=(
                source_decision_id
            ),
            source_audit_ref=(
                source_audit_ref
            ),
            opened_at=opened_at,
            metadata=deepcopy(
                metadata
                if metadata is not None
                else {}
            ),
            trade_id=resolved_trade_id,
        )

        if trade.trade_id in self._trades:
            raise ValueError(
                "A paper trade with this trade_id "
                "already exists."
            )

        trade.current_price = (
            trade.entry_price
        )

        initial_snapshot = (
            self.pnl_engine.calculate_unrealized(
                entry_price=trade.entry_price,
                current_price=trade.current_price,
                quantity=trade.quantity,
            )
        )

        trade.unrealized_pnl = (
            initial_snapshot[
                "pnl"
            ]
        )

        lifecycle_audit = (
            self.lifecycle_audit_factory(
                trade.trade_id
            )
        )

        self._trades[
            trade.trade_id
        ] = trade

        self._lifecycle_audits[
            trade.trade_id
        ] = lifecycle_audit

        self._journal_status[
            trade.trade_id
        ] = {
            "enabled": (
                self.persist_journal
            ),
            "persisted": False,
            "error": None,
        }

        self._record_and_persist(
            trade=trade,
            recorder=(
                lifecycle_audit.record_opened
            ),
            price=trade.entry_price,
            status=trade.status,
            details={
                "quantity": (
                    trade.quantity
                ),
                "lot_size": (
                    trade.lot_size
                ),
                "lots": (
                    trade.lots
                ),
                "stop_loss_price": (
                    trade.stop_loss_price
                ),
                "target_price": (
                    trade.target_price
                ),
            },
            timestamp=opened_at,
        )

        return trade.copy()

    # ---------------------------------
    # GET PAPER TRADE
    # ---------------------------------

    def get_trade(
        self,
        trade_id,
    ):
        """
        Return an independent copy of one paper trade.
        """

        trade = self._require_trade(
            trade_id
        )

        return trade.copy()

    # ---------------------------------
    # LIST PAPER TRADES
    # ---------------------------------

    def get_all_trades(
        self,
    ):
        """
        Return independent copies of all paper trades.
        """

        return [
            trade.copy()
            for trade in self._trades.values()
        ]

    def get_open_trades(
        self,
    ):
        """
        Return independent copies of all OPEN trades.
        """

        return [
            trade.copy()
            for trade in self._trades.values()
            if trade.status
            == PaperTradeStatus.OPEN
        ]

    def get_closed_trades(
        self,
    ):
        """
        Return independent copies of all CLOSED trades.
        """

        return [
            trade.copy()
            for trade in self._trades.values()
            if trade.status
            == PaperTradeStatus.CLOSED
        ]

    # ---------------------------------
    # LIFECYCLE AUDIT QUERIES
    # ---------------------------------

    def get_lifecycle_events(
        self,
        trade_id,
    ):
        """
        Return lifecycle events for one paper trade.
        """

        lifecycle_audit = (
            self._require_lifecycle_audit(
                trade_id
            )
        )

        return lifecycle_audit.get_events()

    def get_lifecycle_summary(
        self,
        trade_id,
    ):
        """
        Return the complete lifecycle audit summary
        for one paper trade.
        """

        lifecycle_audit = (
            self._require_lifecycle_audit(
                trade_id
            )
        )

        return lifecycle_audit.build_summary()

    def get_latest_lifecycle_event(
        self,
        trade_id,
    ):
        """
        Return the latest lifecycle event for one trade.
        """

        lifecycle_audit = (
            self._require_lifecycle_audit(
                trade_id
            )
        )

        return lifecycle_audit.latest_event()

    def get_journal_status(
        self,
        trade_id,
    ):
        """
        Return the latest journal persistence status
        for one paper trade.
        """

        resolved_trade_id = (
            self._validate_trade_id(
                trade_id
            )
        )

        self._require_trade(
            resolved_trade_id
        )

        return deepcopy(
            self._journal_status.get(
                resolved_trade_id,
                {
                    "enabled": (
                        self.persist_journal
                    ),
                    "persisted": False,
                    "error": None,
                },
            )
        )

    # ---------------------------------
    # UPDATE PAPER TRADE
    # ---------------------------------

    def update_price(
        self,
        trade_id,
        current_price,
        updated_at=None,
        auto_close=True,
    ):
        """
        Update an OPEN paper trade with a simulated price.

        Every successful price update records a
        PRICE_UPDATED lifecycle event.

        When auto_close is enabled:
        - price <= stop loss -> STOP_LOSS close
        - price >= target -> TARGET close

        Returns the updated PaperTrade copy.
        """

        trade = self._require_open_trade(
            trade_id
        )

        resolved_price = (
            self._validate_price(
                current_price,
                "current_price",
            )
        )

        trade.current_price = (
            resolved_price
        )

        trade.updated_at = (
            str(
                updated_at
            )
            if updated_at is not None
            else PaperTrade.utc_timestamp()
        )

        snapshot = (
            self.pnl_engine.calculate_unrealized(
                entry_price=trade.entry_price,
                current_price=resolved_price,
                quantity=trade.quantity,
            )
        )

        trade.unrealized_pnl = (
            snapshot[
                "pnl"
            ]
        )

        lifecycle_audit = (
            self._require_lifecycle_audit(
                trade.trade_id
            )
        )

        self._record_and_persist(
            trade=trade,
            recorder=(
                lifecycle_audit.record_price_updated
            ),
            price=resolved_price,
            unrealized_pnl=(
                trade.unrealized_pnl
            ),
            status=trade.status,
            details={
                "auto_close": (
                    bool(
                        auto_close
                    )
                ),
            },
            timestamp=updated_at,
        )

        if auto_close:

            if (
                resolved_price
                <= trade.stop_loss_price
            ):
                return self._close_internal(
                    trade=trade,
                    exit_price=resolved_price,
                    exit_reason=(
                        PaperTradeExitReason.STOP_LOSS
                    ),
                    closed_at=updated_at,
                )

            if (
                resolved_price
                >= trade.target_price
            ):
                return self._close_internal(
                    trade=trade,
                    exit_price=resolved_price,
                    exit_reason=(
                        PaperTradeExitReason.TARGET
                    ),
                    closed_at=updated_at,
                )

        return trade.copy()

    # ---------------------------------
    # MANUAL PAPER EXIT
    # ---------------------------------

    def close_trade(
        self,
        trade_id,
        exit_price,
        exit_reason=(
            PaperTradeExitReason.MANUAL_EXIT
        ),
        closed_at=None,
    ):
        """
        Manually close an OPEN paper trade.

        This is a simulated close only.
        """

        trade = self._require_open_trade(
            trade_id
        )

        resolved_price = (
            self._validate_price(
                exit_price,
                "exit_price",
            )
        )

        resolved_reason = (
            self._validate_exit_reason(
                exit_reason
            )
        )

        return self._close_internal(
            trade=trade,
            exit_price=resolved_price,
            exit_reason=resolved_reason,
            closed_at=closed_at,
        )

    # ---------------------------------
    # INTERNAL CLOSE
    # ---------------------------------

    def _close_internal(
        self,
        trade,
        exit_price,
        exit_reason,
        closed_at=None,
    ):
        """
        Close an internally stored OPEN paper trade.

        Lifecycle behavior:

        STOP_LOSS:
            STOP_LOSS_HIT
            CLOSED

        TARGET:
            TARGET_HIT
            CLOSED

        MANUAL_EXIT:
            CLOSED
        """

        if not isinstance(
            trade,
            PaperTrade,
        ):
            raise TypeError(
                "trade must be a PaperTrade."
            )

        if trade.status != PaperTradeStatus.OPEN:
            raise ValueError(
                "Paper trade must be OPEN."
            )

        resolved_price = (
            self._validate_price(
                exit_price,
                "exit_price",
            )
        )

        resolved_reason = (
            self._validate_exit_reason(
                exit_reason
            )
        )

        timestamp = (
            str(
                closed_at
            )
            if closed_at is not None
            else PaperTrade.utc_timestamp()
        )

        realized_snapshot = (
            self.pnl_engine.calculate_realized(
                entry_price=trade.entry_price,
                exit_price=resolved_price,
                quantity=trade.quantity,
            )
        )

        trade.status = (
            PaperTradeStatus.CLOSED
        )

        trade.current_price = (
            resolved_price
        )

        trade.exit_price = (
            resolved_price
        )

        trade.realized_pnl = (
            realized_snapshot[
                "pnl"
            ]
        )

        trade.unrealized_pnl = None

        trade.exit_reason = (
            resolved_reason
        )

        trade.closed_at = (
            timestamp
        )

        trade.updated_at = (
            timestamp
        )

        lifecycle_audit = (
            self._require_lifecycle_audit(
                trade.trade_id
            )
        )

        close_details = {
            "exit_reason": (
                resolved_reason
            ),
            "entry_price": (
                trade.entry_price
            ),
            "exit_price": (
                resolved_price
            ),
            "quantity": (
                trade.quantity
            ),
        }

        if (
            resolved_reason
            == PaperTradeExitReason.STOP_LOSS
        ):
            self._record_and_persist(
                trade=trade,
                recorder=(
                    lifecycle_audit
                    .record_stop_loss_hit
                ),
                price=resolved_price,
                realized_pnl=(
                    trade.realized_pnl
                ),
                status=trade.status,
                details=(
                    close_details
                ),
                timestamp=closed_at,
            )

        elif (
            resolved_reason
            == PaperTradeExitReason.TARGET
        ):
            self._record_and_persist(
                trade=trade,
                recorder=(
                    lifecycle_audit
                    .record_target_hit
                ),
                price=resolved_price,
                realized_pnl=(
                    trade.realized_pnl
                ),
                status=trade.status,
                details=(
                    close_details
                ),
                timestamp=closed_at,
            )

        self._record_and_persist(
            trade=trade,
            recorder=(
                lifecycle_audit.record_closed
            ),
            price=resolved_price,
            realized_pnl=(
                trade.realized_pnl
            ),
            reason=(
                resolved_reason
            ),
            status=trade.status,
            details=(
                close_details
            ),
            timestamp=closed_at,
        )

        return trade.copy()

    # ---------------------------------
    # PAPER TRADE P&L SNAPSHOT
    # ---------------------------------

    def get_pnl_snapshot(
        self,
        trade_id,
        current_price=None,
    ):
        """
        Return a complete P&L snapshot for a paper trade.

        OPEN:
            Uses current_price when supplied, otherwise
            the trade's stored current_price.

        CLOSED:
            Uses the recorded exit price.
        """

        trade = self._require_trade(
            trade_id
        )

        return deepcopy(
            self.pnl_engine.calculate_trade_snapshot(
                trade=trade,
                current_price=current_price,
            )
        )

    # ---------------------------------
    # COUNTS
    # ---------------------------------

    def count_trades(
        self,
    ):
        """
        Return total number of paper trades.
        """

        return len(
            self._trades
        )

    def count_open_trades(
        self,
    ):
        """
        Return number of OPEN paper trades.
        """

        return sum(
            1
            for trade in self._trades.values()
            if trade.status
            == PaperTradeStatus.OPEN
        )

    def count_closed_trades(
        self,
    ):
        """
        Return number of CLOSED paper trades.
        """

        return sum(
            1
            for trade in self._trades.values()
            if trade.status
            == PaperTradeStatus.CLOSED
        )