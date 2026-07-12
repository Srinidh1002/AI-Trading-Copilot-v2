"""
Option-chain market-data integrity validator.

Validates normalized option contracts before they are
trusted by the contract-selection and trading pipelines.

Checks:
- Contract structure
- Symbol presence
- Valid CE/PE option type
- Positive strike and premium
- Valid bid and ask prices
- Ask not below bid
- Non-negative volume and open interest
- Positive lot size
- Optional Greeks are finite when supplied
- Duplicate contract detection

Read-only.
No orders are placed.
"""

import math


class OptionChainValidationError(ValueError):
    """
    Raised when option-chain data fails
    mandatory integrity validation.
    """


def _to_finite_float(
    value,
    field_name,
):
    """
    Convert a value to a finite float.
    """

    try:
        number = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise OptionChainValidationError(
            f"{field_name} must be numeric."
        ) from exc

    if not math.isfinite(
        number
    ):
        raise OptionChainValidationError(
            f"{field_name} must be finite."
        )

    return number


def _to_non_negative_integer(
    value,
    field_name,
):
    """
    Convert a value to a non-negative integer.
    """

    number = _to_finite_float(
        value,
        field_name,
    )

    if number < 0:
        raise OptionChainValidationError(
            f"{field_name} cannot be negative."
        )

    if not number.is_integer():
        raise OptionChainValidationError(
            f"{field_name} must be a whole number."
        )

    return int(
        number
    )


def _normalize_optional_greek(
    value,
    field_name,
):
    """
    Validate an optional Greek value.

    None is allowed because Greeks are optional.
    """

    if value is None:
        return None

    return _to_finite_float(
        value,
        field_name,
    )


def validate_option_contract(
    contract,
):
    """
    Validate one normalized option contract.

    Returns a normalized contract dictionary.
    """

    if not isinstance(
        contract,
        dict,
    ):
        raise OptionChainValidationError(
            "Option contract must be a dictionary."
        )

    symbol = str(
        contract.get(
            "symbol",
            "",
        )
        or ""
    ).strip()

    if not symbol:
        raise OptionChainValidationError(
            "Option contract symbol is required."
        )

    token = str(
        contract.get(
            "token",
            "",
        )
        or ""
    ).strip()

    option_type = str(
        contract.get(
            "option_type",
            "",
        )
        or ""
    ).strip().upper()

    if option_type not in {
        "CE",
        "PE",
    }:
        raise OptionChainValidationError(
            "Option type must be CE or PE."
        )

    strike = _to_finite_float(
        contract.get(
            "strike"
        ),
        "Strike",
    )

    premium = _to_finite_float(
        contract.get(
            "premium"
        ),
        "Premium",
    )

    bid = _to_finite_float(
        contract.get(
            "bid"
        ),
        "Bid",
    )

    ask = _to_finite_float(
        contract.get(
            "ask"
        ),
        "Ask",
    )

    volume = _to_non_negative_integer(
        contract.get(
            "volume",
            0,
        ),
        "Volume",
    )

    open_interest = (
        _to_non_negative_integer(
            contract.get(
                "open_interest",
                0,
            ),
            "Open interest",
        )
    )

    lot_size = _to_non_negative_integer(
        contract.get(
            "lot_size",
            0,
        ),
        "Lot size",
    )

    if strike <= 0:
        raise OptionChainValidationError(
            "Strike must be greater than zero."
        )

    if premium <= 0:
        raise OptionChainValidationError(
            "Premium must be greater than zero."
        )

    if bid <= 0:
        raise OptionChainValidationError(
            "Bid must be greater than zero."
        )

    if ask <= 0:
        raise OptionChainValidationError(
            "Ask must be greater than zero."
        )

    if ask < bid:
        raise OptionChainValidationError(
            "Ask cannot be below Bid."
        )

    if lot_size <= 0:
        raise OptionChainValidationError(
            "Lot size must be greater than zero."
        )

    delta = _normalize_optional_greek(
        contract.get(
            "delta"
        ),
        "Delta",
    )

    gamma = _normalize_optional_greek(
        contract.get(
            "gamma"
        ),
        "Gamma",
    )

    theta = _normalize_optional_greek(
        contract.get(
            "theta"
        ),
        "Theta",
    )

    vega = _normalize_optional_greek(
        contract.get(
            "vega"
        ),
        "Vega",
    )

    iv = _normalize_optional_greek(
        contract.get(
            "iv"
        ),
        "IV",
    )

    normalized = dict(
        contract
    )

    normalized.update({
        "token": token,
        "symbol": symbol,
        "strike": strike,
        "option_type": option_type,
        "premium": premium,
        "bid": bid,
        "ask": ask,
        "volume": volume,
        "open_interest": open_interest,
        "lot_size": lot_size,
        "delta": delta,
        "gamma": gamma,
        "theta": theta,
        "vega": vega,
        "iv": iv,
    })

    return normalized


def validate_option_chain(
    contracts,
):
    """
    Validate a complete normalized option chain.

    Invalid contracts are rejected from the returned
    chain instead of allowing corrupted data to reach
    contract selection.

    At least one valid contract must remain.

    Duplicate contracts are removed using:
    - symbol when available
    - otherwise option type + strike + expiry

    Returns:
        list of validated normalized contracts
    """

    if not isinstance(
        contracts,
        (
            list,
            tuple,
        ),
    ):
        raise OptionChainValidationError(
            "Option contracts must be a list or tuple."
        )

    if not contracts:
        raise OptionChainValidationError(
            "Option contracts cannot be empty."
        )

    validated_contracts = []

    seen_contracts = set()

    validation_errors = []

    for index, contract in enumerate(
        contracts
    ):

        try:

            validated = (
                validate_option_contract(
                    contract
                )
            )

        except OptionChainValidationError as exc:

            validation_errors.append(
                f"Contract {index}: {exc}"
            )

            continue

        symbol = validated.get(
            "symbol"
        )

        if symbol:

            identity = (
                "SYMBOL",
                symbol.upper(),
            )

        else:

            identity = (
                "CONTRACT",
                validated.get(
                    "option_type"
                ),
                validated.get(
                    "strike"
                ),
                validated.get(
                    "expiry"
                ),
            )

        if identity in seen_contracts:
            continue

        seen_contracts.add(
            identity
        )

        validated_contracts.append(
            validated
        )

    if not validated_contracts:

        error_summary = (
            "; ".join(
                validation_errors[:3]
            )
        )

        message = (
            "No valid option contracts remain "
            "after integrity validation."
        )

        if error_summary:

            message += (
                " "
                + error_summary
            )

        raise OptionChainValidationError(
            message
        )

    return validated_contracts