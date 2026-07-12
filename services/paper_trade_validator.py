"""
Paper trade validation service.

Validates trading-pipeline output before a simulated
paper position may be opened.

This module is paper-only.
It does not connect to brokers and does not place orders.
"""

import math
from copy import deepcopy


class PaperTradeValidator:
    """
    Strict fail-closed validator for paper-trade creation.

    A paper trade may only be created when:
    - The pipeline decision is TRADE_ALLOWED.
    - A valid option contract was selected.
    - A valid trade plan explicitly allows the trade.
    - Required contract, price, quantity, and risk data exist.
    """

    ALLOWED_OPTION_TYPES = {
        "CE",
        "PE",
    }

    ALLOWED_DIRECTIONS = {
        "BULLISH",
        "BEARISH",
    }

    REQUIRED_DECISION = (
        "TRADE_ALLOWED"
    )

    @staticmethod
    def _require_dict(
        value,
        field_name,
    ):
        """
        Require a dictionary.
        """

        if not isinstance(
            value,
            dict,
        ):
            raise ValueError(
                f"{field_name} must be a dictionary."
            )

        return value

    @staticmethod
    def _validate_required_text(
        value,
        field_name,
    ):
        """
        Validate a required non-empty text value.
        """

        if value is None:
            raise ValueError(
                f"{field_name} is required."
            )

        text = str(
            value
        ).strip()

        if not text:
            raise ValueError(
                f"{field_name} must not be empty."
            )

        return text

    @staticmethod
    def _validate_positive_number(
        value,
        field_name,
    ):
        """
        Validate a finite number greater than zero.

        Boolean values are rejected explicitly because
        bool is a subclass of int in Python.
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
    def _validate_non_negative_number(
        value,
        field_name,
    ):
        """
        Validate a finite number greater than or equal to zero.
        """

        if isinstance(
            value,
            bool,
        ):
            raise ValueError(
                f"{field_name} must be a non-negative number."
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
                f"{field_name} must be a non-negative number."
            ) from exc

        if not math.isfinite(
            number
        ):
            raise ValueError(
                f"{field_name} must be finite."
            )

        if number < 0:
            raise ValueError(
                f"{field_name} must be greater than or equal to zero."
            )

        return number

    @staticmethod
    def _validate_positive_integer(
        value,
        field_name,
    ):
        """
        Validate a true positive integer.

        Values such as:
        - 1.5
        - "1.5"
        - True

        are rejected rather than silently truncated.
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
    def validate_pipeline_result(
        cls,
        pipeline_result,
    ):
        """
        Validate a complete live decision-pipeline result.

        Returns a normalized, independent dictionary
        containing the data required to create a paper trade.

        The original pipeline result is never mutated.
        """

        result = cls._require_dict(
            pipeline_result,
            "pipeline_result",
        )

        # ---------------------------------
        # FINAL DECISION GATE
        # ---------------------------------

        decision = (
            cls._validate_required_text(
                result.get(
                    "decision"
                ),
                "decision",
            )
            .upper()
        )

        if decision != cls.REQUIRED_DECISION:
            raise ValueError(
                "Paper trade creation requires "
                "decision TRADE_ALLOWED."
            )

        # ---------------------------------
        # DIRECTION VALIDATION
        # ---------------------------------

        direction = (
            cls._validate_required_text(
                result.get(
                    "direction"
                ),
                "direction",
            )
            .upper()
        )

        if direction not in cls.ALLOWED_DIRECTIONS:
            raise ValueError(
                "direction must be BULLISH or BEARISH."
            )

        # ---------------------------------
        # CONTRACT VALIDATION
        # ---------------------------------

        contract = cls._require_dict(
            result.get(
                "contract"
            ),
            "contract",
        )

        if contract.get(
            "selected"
        ) is not True:
            raise ValueError(
                "A selected option contract is required."
            )

        option_symbol = (
            cls._validate_required_text(
                contract.get(
                    "symbol"
                ),
                "contract.symbol",
            )
        )

        option_type = (
            cls._validate_required_text(
                contract.get(
                    "option_type"
                ),
                "contract.option_type",
            )
            .upper()
        )

        if option_type not in cls.ALLOWED_OPTION_TYPES:
            raise ValueError(
                "contract.option_type must be CE or PE."
            )

        if (
            direction == "BULLISH"
            and option_type != "CE"
        ):
            raise ValueError(
                "BULLISH paper trades require a CE contract."
            )

        if (
            direction == "BEARISH"
            and option_type != "PE"
        ):
            raise ValueError(
                "BEARISH paper trades require a PE contract."
            )

        strike = (
            cls._validate_positive_number(
                contract.get(
                    "strike"
                ),
                "contract.strike",
            )
        )

        expiry = (
            cls._validate_required_text(
                contract.get(
                    "expiry"
                ),
                "contract.expiry",
            )
        )

        contract_premium = (
            cls._validate_positive_number(
                contract.get(
                    "premium"
                ),
                "contract.premium",
            )
        )

        contract_lot_size = (
            cls._validate_positive_integer(
                contract.get(
                    "lot_size"
                ),
                "contract.lot_size",
            )
        )

        # ---------------------------------
        # TRADE PLAN VALIDATION
        # ---------------------------------

        trade_plan = cls._require_dict(
            result.get(
                "trade_plan"
            ),
            "trade_plan",
        )

        if trade_plan.get(
            "allowed"
        ) is not True:
            raise ValueError(
                "trade_plan must explicitly allow the trade."
            )

        levels = cls._require_dict(
            trade_plan.get(
                "levels"
            ),
            "trade_plan.levels",
        )

        risk = cls._require_dict(
            trade_plan.get(
                "risk"
            ),
            "trade_plan.risk",
        )

        # ---------------------------------
        # PRICE LEVEL VALIDATION
        # ---------------------------------

        entry_price = (
            cls._validate_positive_number(
                levels.get(
                    "option_entry_price"
                ),
                "trade_plan.levels.option_entry_price",
            )
        )

        stop_loss_price = (
            cls._validate_positive_number(
                levels.get(
                    "option_stop_loss"
                ),
                "trade_plan.levels.option_stop_loss",
            )
        )

        target_price = (
            cls._validate_positive_number(
                levels.get(
                    "option_target"
                ),
                "trade_plan.levels.option_target",
            )
        )

        if stop_loss_price >= entry_price:
            raise ValueError(
                "Option stop-loss price must be below "
                "the entry price for a long option position."
            )

        if target_price <= entry_price:
            raise ValueError(
                "Option target price must be above "
                "the entry price for a long option position."
            )

        # ---------------------------------
        # RISK VALIDATION
        # ---------------------------------

        if risk.get(
            "allowed"
        ) is not True:
            raise ValueError(
                "trade_plan.risk must explicitly allow the trade."
            )

        lots = (
            cls._validate_positive_integer(
                risk.get(
                    "lots"
                ),
                "trade_plan.risk.lots",
            )
        )

        quantity = (
            cls._validate_positive_integer(
                risk.get(
                    "quantity"
                ),
                "trade_plan.risk.quantity",
            )
        )

        required_capital = (
            cls._validate_positive_number(
                risk.get(
                    "required_capital"
                ),
                "trade_plan.risk.required_capital",
            )
        )

        estimated_maximum_loss = (
            cls._validate_non_negative_number(
                risk.get(
                    "estimated_maximum_loss"
                ),
                "trade_plan.risk.estimated_maximum_loss",
            )
        )

        expected_quantity = (
            contract_lot_size
            * lots
        )

        if quantity != expected_quantity:
            raise ValueError(
                "trade_plan.risk.quantity must equal "
                "contract.lot_size multiplied by lots."
            )

        # ---------------------------------
        # CONTRACT / ENTRY CONSISTENCY
        # ---------------------------------

        tolerance = max(
            0.01,
            abs(
                entry_price
            )
            * 0.05,
        )

        if (
            abs(
                contract_premium
                - entry_price
            )
            > tolerance
        ):
            raise ValueError(
                "Contract premium and planned option entry "
                "price are materially inconsistent."
            )

        # ---------------------------------
        # NORMALIZED OUTPUT
        # ---------------------------------

        return deepcopy(
            {
                "decision": decision,
                "direction": direction,
                "contract": {
                    "selected": True,
                    "symbol": option_symbol,
                    "option_type": option_type,
                    "strike": strike,
                    "expiry": expiry,
                    "premium": contract_premium,
                    "lot_size": contract_lot_size,
                },
                "trade_plan": {
                    "allowed": True,
                    "levels": {
                        "option_entry_price": entry_price,
                        "option_stop_loss": stop_loss_price,
                        "option_target": target_price,
                    },
                    "risk": {
                        "allowed": True,
                        "lots": lots,
                        "quantity": quantity,
                        "required_capital": required_capital,
                        "estimated_maximum_loss": (
                            estimated_maximum_loss
                        ),
                    },
                },
            }
        )

    @classmethod
    def validate_open_request(
        cls,
        pipeline_result,
        underlying,
        exchange,
        symboltoken=None,
    ):
        """
        Validate the pipeline result and required market identity.

        Returns normalized data ready for PaperTrade.create().
        """

        validated = (
            cls.validate_pipeline_result(
                pipeline_result
            )
        )

        normalized_underlying = (
            cls._validate_required_text(
                underlying,
                "underlying",
            )
            .upper()
        )

        normalized_exchange = (
            cls._validate_required_text(
                exchange,
                "exchange",
            )
            .upper()
        )

        normalized_symboltoken = None

        if symboltoken is not None:
            normalized_symboltoken = (
                cls._validate_required_text(
                    symboltoken,
                    "symboltoken",
                )
            )

        return {
            "underlying": normalized_underlying,
            "exchange": normalized_exchange,
            "symboltoken": normalized_symboltoken,
            **deepcopy(
                validated
            ),
        }