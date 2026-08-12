"""Strict validation of Angel FULL option quote responses.

Read-only.
No broker order submission.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from copy import deepcopy

from services.paper_orchestration.angel_provider_timestamp import (
    validate_angel_quote_timestamp,
)


class OptionFullResponseValidationError(RuntimeError):
    """Raised when an Angel FULL option response fails closed."""


def _mapping(
    value: object,
    *,
    name: str,
) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise OptionFullResponseValidationError(
            f"{name} must be a mapping."
        )

    return value


def _sequence(
    value: object,
    *,
    name: str,
) -> Sequence[object]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes))
    ):
        raise OptionFullResponseValidationError(
            f"{name} must be a sequence."
        )

    return value


def _required_text(
    value: object,
    *,
    name: str,
) -> str:
    result = str(
        value
        if value is not None
        else ""
    ).strip()

    if not result:
        raise OptionFullResponseValidationError(
            f"{name} must be a non-empty string."
        )

    return result


def _finite_float(
    value: object,
    *,
    name: str,
    positive: bool = False,
    non_negative: bool = False,
) -> float:
    if isinstance(value, bool):
        raise OptionFullResponseValidationError(
            f"{name} must be numeric."
        )

    try:
        result = float(value)
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise OptionFullResponseValidationError(
            f"{name} must be numeric."
        ) from exc

    if not math.isfinite(result):
        raise OptionFullResponseValidationError(
            f"{name} must be finite."
        )

    if positive and result <= 0:
        raise OptionFullResponseValidationError(
            f"{name} must be greater than zero."
        )

    if non_negative and result < 0:
        raise OptionFullResponseValidationError(
            f"{name} cannot be negative."
        )

    return result


def _non_negative_integer(
    value: object,
    *,
    name: str,
) -> int:
    number = _finite_float(
        value,
        name=name,
        non_negative=True,
    )

    if not number.is_integer():
        raise OptionFullResponseValidationError(
            f"{name} must be a whole number."
        )

    return int(number)


def _best_price(
    depth: Mapping[str, object],
    *,
    side: str,
) -> float:
    entries = _sequence(
        depth.get(side),
        name=f"depth.{side}",
    )

    if not entries:
        raise OptionFullResponseValidationError(
            f"depth.{side} cannot be empty."
        )

    first = _mapping(
        entries[0],
        name=f"depth.{side}[0]",
    )

    return _finite_float(
        first.get("price"),
        name=f"depth.{side}[0].price",
        positive=True,
    )


def _identity(
    item: Mapping[str, object],
    *,
    expected_exchange: str,
) -> tuple[str, str]:
    raw_exchange = item.get("exchange")

    exchange = (
        expected_exchange
        if raw_exchange is None
        or not str(raw_exchange).strip()
        else _required_text(
            raw_exchange,
            name="fetched exchange",
        ).upper()
    )

    token = _required_text(
        item.get(
            "symbolToken",
            item.get("symboltoken"),
        ),
        name="fetched symbolToken",
    )

    return exchange, token


def _unfetched_identity(
    item: Mapping[str, object],
    *,
    expected_exchange: str,
) -> tuple[str, str]:
    exchange = str(
        item.get("exchange", expected_exchange)
    ).strip().upper()

    token = _required_text(
        item.get(
            "symbolToken",
            item.get("symboltoken"),
        ),
        name="unfetched symbolToken",
    )

    return exchange, token


def validate_option_full_response(
    *,
    response: object,
    option_exchange: str,
    requested_tokens: Sequence[str],
    received_at=None,
    maximum_quote_age_seconds: float = 300.0,
    maximum_future_skew_seconds: float = 5.0,
) -> dict[str, dict[str, object]]:
    """Validate exact one-for-one FULL coverage for requested option tokens."""

    exchange = _required_text(
        option_exchange,
        name="option_exchange",
    ).upper()

    if exchange not in {"NFO", "BFO"}:
        raise OptionFullResponseValidationError(
            "option_exchange must be NFO or BFO."
        )

    requested = []

    for index, raw_token in enumerate(
        _sequence(
            requested_tokens,
            name="requested_tokens",
        )
    ):
        token = _required_text(
            raw_token,
            name=f"requested_tokens[{index}]",
        )

        if token in requested:
            raise OptionFullResponseValidationError(
                f"Duplicate requested option token: {token}."
            )

        requested.append(token)

    if not requested:
        raise OptionFullResponseValidationError(
            "requested_tokens cannot be empty."
        )

    expected = {
        (exchange, token)
        for token in requested
    }

    envelope = _mapping(
        response,
        name="option FULL response",
    )

    if envelope.get("status") is not True:
        raise OptionFullResponseValidationError(
            "Option FULL response status must be true."
        )

    data = _mapping(
        envelope.get("data"),
        name="option FULL response data",
    )

    fetched = _sequence(
        data.get("fetched"),
        name="option FULL fetched",
    )

    unfetched = _sequence(
        data.get("unfetched"),
        name="option FULL unfetched",
    )

    for index, raw_item in enumerate(
        unfetched
    ):
        item = _mapping(
            raw_item,
            name=f"option FULL unfetched[{index}]",
        )

        identity = _unfetched_identity(
            item,
            expected_exchange=exchange,
        )

        if identity not in expected:
            raise OptionFullResponseValidationError(
                "Option FULL response contains an "
                "unexpected unfetched identity."
            )

        reason = str(
            item.get(
                "message",
                item.get(
                    "errorCode",
                    "provider did not fetch token",
                ),
            )
        ).strip()

        raise OptionFullResponseValidationError(
            "Requested option token was unfetched: "
            f"{identity[1]}: {reason}"
        )

    if not fetched:
        raise OptionFullResponseValidationError(
            "No live option contracts were "
            "received from the broker."
        )

    validated: dict[
        tuple[str, str],
        dict[str, object],
    ] = {}

    for index, raw_item in enumerate(
        fetched
    ):
        item = _mapping(
            raw_item,
            name=f"option FULL fetched[{index}]",
        )

        identity = _identity(
            item,
            expected_exchange=exchange,
        )

        if identity not in expected:
            raise OptionFullResponseValidationError(
                "Option FULL response contains an "
                "unexpected fetched identity."
            )

        if identity in validated:
            raise OptionFullResponseValidationError(
                "Option FULL response contains a "
                f"duplicate fetched token: {identity[1]}."
            )

        ltp = _finite_float(
            item.get("ltp"),
            name=f"{identity[1]} ltp",
            positive=True,
        )

        volume = _non_negative_integer(
            item.get("tradeVolume"),
            name=f"{identity[1]} tradeVolume",
        )

        open_interest = _non_negative_integer(
            item.get("opnInterest"),
            name=f"{identity[1]} opnInterest",
        )

        depth = _mapping(
            item.get("depth"),
            name=f"{identity[1]} depth",
        )

        bid = _best_price(
            depth,
            side="buy",
        )

        ask = _best_price(
            depth,
            side="sell",
        )

        if ask < bid:
            raise OptionFullResponseValidationError(
                f"{identity[1]} option market is crossed."
            )

        copied = deepcopy(
            dict(item)
        )

        copied["_validated_ltp"] = ltp
        copied["_validated_volume"] = volume
        copied["_validated_open_interest"] = (
            open_interest
        )
        copied["_validated_bid"] = bid
        copied["_validated_ask"] = ask

        if received_at is not None:
            try:
                timestamp = validate_angel_quote_timestamp(
                    data=item,
                    received_at=received_at,
                    maximum_age_seconds=(
                        maximum_quote_age_seconds
                    ),
                    maximum_future_skew_seconds=(
                        maximum_future_skew_seconds
                    ),
                )
            except (
                TypeError,
                ValueError,
            ) as exc:
                raise OptionFullResponseValidationError(
                    f"{identity[1]} option quote timestamp "
                    f"is invalid: {exc}"
                ) from exc

            copied[
                "_validated_provider_timestamp"
            ] = timestamp.provider_timestamp

            copied[
                "_validated_provider_timestamp_field"
            ] = timestamp.timestamp_field

            copied[
                "_validated_provider_timestamp_age_seconds"
            ] = timestamp.age_seconds

        validated[identity] = copied

    missing = expected - set(validated)

    if missing:
        missing_tokens = ", ".join(
            sorted(
                token
                for _, token in missing
            )
        )

        raise OptionFullResponseValidationError(
            "Option FULL response is missing requested "
            f"tokens: {missing_tokens}."
        )

    return {
        token: deepcopy(
            validated[(exchange, token)]
        )
        for token in requested
    }
