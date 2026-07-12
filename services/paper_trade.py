"""
Paper trade domain model.

Represents a simulated option position for testing,
validation, analysis, and paper-trading lifecycle tracking.

This module is paper-only.
It does not connect to brokers and does not place orders.
"""

from copy import deepcopy
from dataclasses import (
    asdict,
    dataclass,
    field,
)
from datetime import (
    datetime,
    timezone,
)
from typing import Optional
from uuid import uuid4


class PaperTradeStatus:
    """
    Allowed paper trade lifecycle statuses.
    """

    OPEN = "OPEN"
    CLOSED = "CLOSED"

    ALL = {
        OPEN,
        CLOSED,
    }


class PaperTradeExitReason:
    """
    Allowed paper trade exit reasons.
    """

    STOP_LOSS = "STOP_LOSS"
    TARGET = "TARGET"
    MANUAL_EXIT = "MANUAL_EXIT"

    ALL = {
        STOP_LOSS,
        TARGET,
        MANUAL_EXIT,
    }


@dataclass
class PaperTrade:
    """
    Represents one simulated long option position.

    Required fields are intentionally defined before
    optional/default fields so dataclass construction
    remains valid and predictable.

    All prices are expressed in rupees.
    Quantity represents total option units.
    Timestamps use ISO 8601 strings.
    """

    # ---------------------------------
    # REQUIRED IDENTITY AND LIFECYCLE
    # ---------------------------------

    trade_id: str
    status: str
    opened_at: str
    updated_at: str

    # ---------------------------------
    # REQUIRED UNDERLYING DETAILS
    # ---------------------------------

    underlying: str
    exchange: str

    # ---------------------------------
    # REQUIRED OPTION CONTRACT DETAILS
    # ---------------------------------

    option_symbol: str
    option_type: str
    strike: float
    expiry: str

    # ---------------------------------
    # REQUIRED POSITION DETAILS
    # ---------------------------------

    direction: str
    entry_price: float
    stop_loss_price: float
    target_price: float

    # ---------------------------------
    # REQUIRED QUANTITY AND CAPITAL
    # ---------------------------------

    lot_size: int
    lots: int
    quantity: int
    required_capital: float
    estimated_maximum_loss: float

    # ---------------------------------
    # OPTIONAL LIFECYCLE DETAILS
    # ---------------------------------

    closed_at: Optional[str] = None

    # ---------------------------------
    # OPTIONAL MARKET DETAILS
    # ---------------------------------

    symboltoken: Optional[str] = None
    current_price: Optional[float] = None
    exit_price: Optional[float] = None

    # ---------------------------------
    # OPTIONAL P&L DETAILS
    # ---------------------------------

    unrealized_pnl: Optional[float] = None
    realized_pnl: Optional[float] = None
    exit_reason: Optional[str] = None

    # ---------------------------------
    # OPTIONAL SOURCE REFERENCES
    # ---------------------------------

    source_decision_id: Optional[str] = None
    source_audit_ref: Optional[str] = None

    # ---------------------------------
    # OPTIONAL CUSTOM METADATA
    # ---------------------------------

    metadata: dict = field(
        default_factory=dict
    )

    @staticmethod
    def utc_timestamp():
        """
        Return the current timezone-aware UTC timestamp
        as an ISO 8601 string.
        """

        return (
            datetime.now(
                timezone.utc
            )
            .isoformat()
        )

    @classmethod
    def create(
        cls,
        underlying,
        exchange,
        option_symbol,
        option_type,
        strike,
        expiry,
        direction,
        entry_price,
        stop_loss_price,
        target_price,
        lot_size,
        lots,
        required_capital,
        estimated_maximum_loss,
        symboltoken=None,
        source_decision_id=None,
        source_audit_ref=None,
        opened_at=None,
        metadata=None,
        trade_id=None,
    ):
        """
        Create a new OPEN paper trade.

        Validation is expected to be performed by
        PaperTradeValidator before this factory is called.

        A custom trade_id and opened_at may be supplied
        for deterministic testing.
        """

        timestamp = (
            str(
                opened_at
            )
            if opened_at is not None
            else cls.utc_timestamp()
        )

        resolved_trade_id = (
            str(
                trade_id
            ).strip()
            if trade_id is not None
            else str(
                uuid4()
            )
        )

        return cls(
            trade_id=resolved_trade_id,
            status=PaperTradeStatus.OPEN,
            opened_at=timestamp,
            updated_at=timestamp,
            underlying=str(
                underlying
            ),
            exchange=str(
                exchange
            ),
            option_symbol=str(
                option_symbol
            ),
            option_type=str(
                option_type
            ),
            strike=float(
                strike
            ),
            expiry=str(
                expiry
            ),
            direction=str(
                direction
            ),
            entry_price=float(
                entry_price
            ),
            stop_loss_price=float(
                stop_loss_price
            ),
            target_price=float(
                target_price
            ),
            lot_size=int(
                lot_size
            ),
            lots=int(
                lots
            ),
            quantity=(
                int(
                    lot_size
                )
                * int(
                    lots
                )
            ),
            required_capital=float(
                required_capital
            ),
            estimated_maximum_loss=float(
                estimated_maximum_loss
            ),
            symboltoken=(
                None
                if symboltoken is None
                else str(
                    symboltoken
                )
            ),
            source_decision_id=(
                None
                if source_decision_id is None
                else str(
                    source_decision_id
                )
            ),
            source_audit_ref=(
                None
                if source_audit_ref is None
                else str(
                    source_audit_ref
                )
            ),
            metadata=deepcopy(
                metadata
                if metadata is not None
                else {}
            ),
        )

    def as_dict(
        self,
    ):
        """
        Return a deep-copied dictionary representation.

        Nested metadata cannot mutate the PaperTrade
        instance through the returned dictionary.
        """

        return deepcopy(
            asdict(
                self
            )
        )

    @classmethod
    def from_dict(
        cls,
        data,
    ):
        """
        Reconstruct a PaperTrade from a dictionary.

        The input dictionary is deep-copied so nested
        external objects cannot become shared mutable state.
        """

        if not isinstance(
            data,
            dict,
        ):
            raise TypeError(
                "Paper trade data must be a dictionary."
            )

        copied = deepcopy(
            data
        )

        return cls(
            trade_id=copied[
                "trade_id"
            ],
            status=copied[
                "status"
            ],
            opened_at=copied[
                "opened_at"
            ],
            updated_at=copied[
                "updated_at"
            ],
            underlying=copied[
                "underlying"
            ],
            exchange=copied[
                "exchange"
            ],
            option_symbol=copied[
                "option_symbol"
            ],
            option_type=copied[
                "option_type"
            ],
            strike=copied[
                "strike"
            ],
            expiry=copied[
                "expiry"
            ],
            direction=copied[
                "direction"
            ],
            entry_price=copied[
                "entry_price"
            ],
            stop_loss_price=copied[
                "stop_loss_price"
            ],
            target_price=copied[
                "target_price"
            ],
            lot_size=copied[
                "lot_size"
            ],
            lots=copied[
                "lots"
            ],
            quantity=copied[
                "quantity"
            ],
            required_capital=copied[
                "required_capital"
            ],
            estimated_maximum_loss=copied[
                "estimated_maximum_loss"
            ],
            closed_at=copied.get(
                "closed_at"
            ),
            symboltoken=copied.get(
                "symboltoken"
            ),
            current_price=copied.get(
                "current_price"
            ),
            exit_price=copied.get(
                "exit_price"
            ),
            unrealized_pnl=copied.get(
                "unrealized_pnl"
            ),
            realized_pnl=copied.get(
                "realized_pnl"
            ),
            exit_reason=copied.get(
                "exit_reason"
            ),
            source_decision_id=copied.get(
                "source_decision_id"
            ),
            source_audit_ref=copied.get(
                "source_audit_ref"
            ),
            metadata=deepcopy(
                copied.get(
                    "metadata",
                    {},
                )
            ),
        )

    def copy(
        self,
    ):
        """
        Return a completely independent PaperTrade copy.
        """

        return self.from_dict(
            self.as_dict()
        )