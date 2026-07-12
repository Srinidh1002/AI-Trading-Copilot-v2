"""
Paper trading profit-and-loss calculation engine.

Provides deterministic P&L calculations for simulated
long option positions.

This module is paper-only.
It does not connect to brokers and does not place orders.
"""

import math
from decimal import (
    Decimal,
    ROUND_HALF_UP,
)


class PaperPnLEngine:
    """
    Calculate unrealized and realized P&L for paper trades.

    The current paper-trading subsystem supports long
    option positions only.
    """

    MONEY_QUANTIZER = Decimal("0.01")

    @staticmethod
    def _validate_positive_number(
        value,
        field_name,
    ):
        """
        Validate a finite number greater than zero.
        """

        if isinstance(
            value,
            bool,
        ):
            raise ValueError(
                f"{field_name} must be a positive number."
            )

        try:
            number = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(
                f"{field_name} must be a positive number."
            ) from exc

        if not math.isfinite(
            number
        ):
            raise ValueError(
                f"{field_name} must be finite."
            )

        if number <= 0:
            raise ValueError(
                f"{field_name} must be greater than zero."
            )

        return number

    @staticmethod
    def _validate_positive_integer(
        value,
        field_name,
    ):
        """
        Validate a true positive integer.

        Fractional values and booleans are rejected.
        """

        if isinstance(
            value,
            bool,
        ):
            raise ValueError(
                f"{field_name} must be a positive integer."
            )

        if isinstance(
            value,
            int,
        ):
            integer = value

        elif isinstance(
            value,
            float,
        ):
            if (
                not math.isfinite(
                    value
                )
                or not value.is_integer()
            ):
                raise ValueError(
                    f"{field_name} must be a positive integer."
                )

            integer = int(
                value
            )

        elif isinstance(
            value,
            str,
        ):
            text = value.strip()

            if not text:
                raise ValueError(
                    f"{field_name} must be a positive integer."
                )

            try:
                number = float(
                    text
                )

            except ValueError as exc:
                raise ValueError(
                    f"{field_name} must be a positive integer."
                ) from exc

            if (
                not math.isfinite(
                    number
                )
                or not number.is_integer()
            ):
                raise ValueError(
                    f"{field_name} must be a positive integer."
                )

            integer = int(
                number
            )

        else:
            raise ValueError(
                f"{field_name} must be a positive integer."
            )

        if integer <= 0:
            raise ValueError(
                f"{field_name} must be greater than zero."
            )

        return integer

    @classmethod
    def _round_decimal(
        cls,
        value,
    ):
        """
        Round a Decimal value to two decimal places
        using deterministic financial ROUND_HALF_UP.
        """

        return float(
            value.quantize(
                cls.MONEY_QUANTIZER,
                rounding=ROUND_HALF_UP,
            )
        )

    @classmethod
    def calculate_pnl(
        cls,
        entry_price,
        current_price,
        quantity,
    ):
        """
        Calculate absolute P&L for a long option position.

        Formula:
            (current_price - entry_price) * quantity
        """

        entry = (
            cls._validate_positive_number(
                entry_price,
                "entry_price",
            )
        )

        current = (
            cls._validate_positive_number(
                current_price,
                "current_price",
            )
        )

        resolved_quantity = (
            cls._validate_positive_integer(
                quantity,
                "quantity",
            )
        )

        pnl = (
            (
                Decimal(
                    str(
                        current
                    )
                )
                - Decimal(
                    str(
                        entry
                    )
                )
            )
            * Decimal(
                resolved_quantity
            )
        )

        return cls._round_decimal(
            pnl
        )

    @classmethod
    def calculate_pnl_percent(
        cls,
        entry_price,
        current_price,
    ):
        """
        Calculate percentage price movement from entry.

        Formula:
            ((current_price - entry_price) / entry_price) * 100
        """

        entry = (
            cls._validate_positive_number(
                entry_price,
                "entry_price",
            )
        )

        current = (
            cls._validate_positive_number(
                current_price,
                "current_price",
            )
        )

        entry_decimal = Decimal(
            str(
                entry
            )
        )

        current_decimal = Decimal(
            str(
                current
            )
        )

        pnl_percent = (
            (
                (
                    current_decimal
                    - entry_decimal
                )
                / entry_decimal
            )
            * Decimal("100")
        )

        return cls._round_decimal(
            pnl_percent
        )

    @classmethod
    def calculate_position_value(
        cls,
        price,
        quantity,
    ):
        """
        Calculate total simulated position value.
        """

        resolved_price = (
            cls._validate_positive_number(
                price,
                "price",
            )
        )

        resolved_quantity = (
            cls._validate_positive_integer(
                quantity,
                "quantity",
            )
        )

        position_value = (
            Decimal(
                str(
                    resolved_price
                )
            )
            * Decimal(
                resolved_quantity
            )
        )

        return cls._round_decimal(
            position_value
        )

    @classmethod
    def calculate_unrealized(
        cls,
        entry_price,
        current_price,
        quantity,
    ):
        """
        Build a complete unrealized P&L snapshot.
        """

        pnl = cls.calculate_pnl(
            entry_price=entry_price,
            current_price=current_price,
            quantity=quantity,
        )

        pnl_percent = (
            cls.calculate_pnl_percent(
                entry_price=entry_price,
                current_price=current_price,
            )
        )

        entry_value = (
            cls.calculate_position_value(
                price=entry_price,
                quantity=quantity,
            )
        )

        current_value = (
            cls.calculate_position_value(
                price=current_price,
                quantity=quantity,
            )
        )

        return {
            "type": "UNREALIZED",
            "entry_price": float(
                entry_price
            ),
            "current_price": float(
                current_price
            ),
            "quantity": int(
                quantity
            ),
            "entry_value": entry_value,
            "current_value": current_value,
            "pnl": pnl,
            "pnl_percent": pnl_percent,
        }

    @classmethod
    def calculate_realized(
        cls,
        entry_price,
        exit_price,
        quantity,
    ):
        """
        Build a complete realized P&L snapshot.
        """

        pnl = cls.calculate_pnl(
            entry_price=entry_price,
            current_price=exit_price,
            quantity=quantity,
        )

        pnl_percent = (
            cls.calculate_pnl_percent(
                entry_price=entry_price,
                current_price=exit_price,
            )
        )

        entry_value = (
            cls.calculate_position_value(
                price=entry_price,
                quantity=quantity,
            )
        )

        exit_value = (
            cls.calculate_position_value(
                price=exit_price,
                quantity=quantity,
            )
        )

        return {
            "type": "REALIZED",
            "entry_price": float(
                entry_price
            ),
            "exit_price": float(
                exit_price
            ),
            "quantity": int(
                quantity
            ),
            "entry_value": entry_value,
            "exit_value": exit_value,
            "pnl": pnl,
            "pnl_percent": pnl_percent,
        }

    @classmethod
    def calculate_trade_snapshot(
        cls,
        trade,
        current_price=None,
    ):
        """
        Calculate P&L from a PaperTrade-like object.

        OPEN trades use current_price.
        CLOSED trades use exit_price.

        The object must expose the required attributes.
        """

        if trade is None:
            raise ValueError(
                "trade is required."
            )

        status = str(
            getattr(
                trade,
                "status",
                "",
            )
        ).strip().upper()

        if status == "OPEN":

            resolved_current_price = (
                current_price
                if current_price is not None
                else getattr(
                    trade,
                    "current_price",
                    None,
                )
            )

            return cls.calculate_unrealized(
                entry_price=getattr(
                    trade,
                    "entry_price",
                    None,
                ),
                current_price=(
                    resolved_current_price
                ),
                quantity=getattr(
                    trade,
                    "quantity",
                    None,
                ),
            )

        if status == "CLOSED":

            return cls.calculate_realized(
                entry_price=getattr(
                    trade,
                    "entry_price",
                    None,
                ),
                exit_price=getattr(
                    trade,
                    "exit_price",
                    None,
                ),
                quantity=getattr(
                    trade,
                    "quantity",
                    None,
                ),
            )

        raise ValueError(
            "trade.status must be OPEN or CLOSED."
        )