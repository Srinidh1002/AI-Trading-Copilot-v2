"""Pure Black-Scholes (spot) / Black-76 (futures) research reference pricing.

Model prices are per underlying price unit, NOT execution quotes, predictions,
contract recommendations or proof of provider accuracy. No network or orders.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import datetime

from services.x5.contracts_v1 import X5ChainCaptureV1, canonical_sha256
from services.x6.contracts_v1 import (
    MODEL_BY_MARKET,
    PRICE_UNITS,
    X6VolatilityCaptureV1,
)
from services.x6.input_validation_v1 import validate_x6_input_v1

_MAX_YEARS = 100.0
_MAX_SIGMA = 5.0
_SQRT_TWO = math.sqrt(2.0)


def _real(value: object, label: str, *, positive: bool = False, signed: bool = False) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite real number, not bool")
    number = float(value)
    if positive and number <= 0 or not signed and number < 0:
        raise ValueError(f"{label} has an invalid sign")
    return number


def _math_inputs(
    *,
    price: float,
    strike: float,
    years: float,
    rate: float,
    volatility: float,
    option_type: str,
    dividend: float | None = None,
) -> None:
    _real(price, "reference_price", positive=True)
    _real(strike, "strike", positive=True)
    t = _real(years, "time_to_expiry", positive=True)
    if t > _MAX_YEARS:
        raise ValueError("time_to_expiry outside reference model range")
    r = _real(rate, "annual_rate", signed=True)
    if abs(r) > 1:
        raise ValueError("annual_rate outside verified context convention")
    sigma = _real(volatility, "annual_volatility")
    if sigma > _MAX_SIGMA:
        raise ValueError("annual_volatility outside reference model range")
    if option_type not in ("CE", "PE"):
        raise ValueError("Expected CE or PE")
    if dividend is not None:
        q = _real(dividend, "annual_dividend_yield", signed=True)
        if abs(q) > 1:
            raise ValueError("annual_dividend_yield outside verified context convention")


def _normal_cdf(x: float) -> float:
    return 0.5 * math.erfc(-x / _SQRT_TWO)


def _bounded_price(value: float, lower: float, upper: float) -> float:
    if not all(math.isfinite(v) for v in (value, lower, upper)):
        raise ValueError("Nonfinite reference model result")
    tolerance = 1e-11 * max(1.0, abs(upper))
    if value < lower - tolerance or value > upper + tolerance:
        raise ValueError("Reference pricing result violated static bounds")
    return min(upper, max(lower, value))


def black_scholes_price_v1(
    *,
    spot: float,
    strike: float,
    years: float,
    rate: float,
    dividend_yield: float,
    volatility: float,
    option_type: str,
) -> float:
    """Spot option price, annual continuous r/q, sigma decimal, ACT/365 years."""
    _math_inputs(
        price=spot,
        strike=strike,
        years=years,
        rate=rate,
        dividend=dividend_yield,
        volatility=volatility,
        option_type=option_type,
    )
    s, k, t, r, q, sigma = (
        float(v) for v in (spot, strike, years, rate, dividend_yield, volatility)
    )
    discounted_spot = s * math.exp(-q * t)
    discounted_strike = k * math.exp(-r * t)
    lower = (
        max(0.0, discounted_spot - discounted_strike)
        if option_type == "CE"
        else max(0.0, discounted_strike - discounted_spot)
    )
    upper = discounted_spot if option_type == "CE" else discounted_strike
    if sigma == 0.0:
        return _bounded_price(lower, lower, upper)
    standard_deviation = sigma * math.sqrt(t)
    d1 = (math.log(s / k) + (r - q + 0.5 * sigma * sigma) * t) / standard_deviation
    d2 = d1 - standard_deviation
    if option_type == "CE":
        value = discounted_spot * _normal_cdf(d1) - discounted_strike * _normal_cdf(d2)
    else:
        value = discounted_strike * _normal_cdf(-d2) - discounted_spot * _normal_cdf(-d1)
    return _bounded_price(value, lower, upper)


def black76_price_v1(
    *, future: float, strike: float, years: float, rate: float, volatility: float, option_type: str
) -> float:
    """European option on explicitly supplied futures/forward reference, Black-76."""
    _math_inputs(
        price=future,
        strike=strike,
        years=years,
        rate=rate,
        volatility=volatility,
        option_type=option_type,
    )
    f, k, t, r, sigma = (float(v) for v in (future, strike, years, rate, volatility))
    discount = math.exp(-r * t)
    lower = discount * max(0.0, f - k) if option_type == "CE" else discount * max(0.0, k - f)
    upper = discount * (f if option_type == "CE" else k)
    if sigma == 0.0:
        return _bounded_price(lower, lower, upper)
    standard_deviation = sigma * math.sqrt(t)
    d1 = (math.log(f / k) + 0.5 * sigma * sigma * t) / standard_deviation
    d2 = d1 - standard_deviation
    if option_type == "CE":
        value = discount * (f * _normal_cdf(d1) - k * _normal_cdf(d2))
    else:
        value = discount * (k * _normal_cdf(-d2) - f * _normal_cdf(-d1))
    return _bounded_price(value, lower, upper)


@dataclass(frozen=True, slots=True)
class X6ReferencePriceV1:
    """One descriptive theoretical price with direct X5 observation identity."""

    canonical_option_id: str
    source_record_id: str
    option_type: str
    strike: float
    theoretical_price: float | None
    status: str
    blockers: tuple[str, ...]
    schema_version: str = "X6_REFERENCE_PRICE_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if not all(
            isinstance(x, str) and x and x.strip() == x
            for x in (self.canonical_option_id, self.source_record_id)
        ) or self.option_type not in ("CE", "PE"):
            raise ValueError("Invalid reference option identity")
        _real(self.strike, "strike", positive=True)
        if self.status not in ("AVAILABLE", "RETROSPECTIVE", "UNAVAILABLE"):
            raise ValueError("Unknown reference status")
        if self.status == "UNAVAILABLE":
            if self.theoretical_price is not None or not self.blockers:
                raise ValueError("Unavailable price needs blockers, never a value")
        elif self.theoretical_price is None or self.blockers:
            raise ValueError("Available price must have a value and no blockers")
        if self.theoretical_price is not None:
            _real(self.theoretical_price, "theoretical_price")
        if type(self.blockers) is not tuple or any(
            not isinstance(x, str) or not x for x in self.blockers
        ):
            raise ValueError("Invalid reference blockers")
        if (
            self.schema_version != "X6_REFERENCE_PRICE_V1"
            or self.data_only is not True
            or (
                self.independent_vote is not False
                or any(
                    getattr(self, field) is not False
                    for field in (
                        "execution_authority",
                        "risk_authority",
                        "position_authority",
                        "certification_authority",
                        "live_execution_eligible",
                    )
                )
            )
        ):
            raise ValueError("Reference price cannot acquire trading authority")


@dataclass(frozen=True, slots=True)
class X6ReferencePricingResultV1:
    market: str
    model: str
    capture_id: str
    as_of: datetime
    reference_unit: str
    annual_volatility: float | None
    time_to_expiry_years: float | None
    prices: tuple[X6ReferencePriceV1, ...]
    status: str
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    source_x6_capture_sha256: str
    source_x5_capture_sha256: str
    source_validation_sha256: str
    volatility_source_id: str | None
    schema_version: str = "X6_REFERENCE_PRICING_RESULT_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if self.market not in MODEL_BY_MARKET or self.model != MODEL_BY_MARKET[self.market]:
            raise ValueError("Result market/model mismatch")
        if (
            not isinstance(self.as_of, datetime)
            or self.as_of.tzinfo is None
            or (self.as_of.utcoffset() is None)
            or not isinstance(self.capture_id, str)
            or not self.capture_id
        ):
            raise ValueError("Invalid capture identity")
        if self.reference_unit != PRICE_UNITS[self.market]:
            raise ValueError("Result price unit mismatch")
        if self.annual_volatility is not None:
            _real(self.annual_volatility, "annual_volatility")
        if self.time_to_expiry_years is not None:
            _real(self.time_to_expiry_years, "time_to_expiry_years", signed=True)
        if type(self.prices) is not tuple or any(
            not isinstance(x, X6ReferencePriceV1) for x in self.prices
        ):
            raise ValueError("Invalid reference prices")
        if len({x.canonical_option_id for x in self.prices}) != len(self.prices):
            raise ValueError("Duplicate reference option")
        if self.status not in ("AVAILABLE", "RETROSPECTIVE", "PARTIAL", "UNAVAILABLE"):
            raise ValueError("Unknown result status")
        if type(self.blockers) is not tuple or type(self.warnings) is not tuple:
            raise ValueError("Result diagnostics must be immutable")
        if self.volatility_source_id is not None and (
            not isinstance(self.volatility_source_id, str) or not self.volatility_source_id.strip()
        ):
            raise ValueError("Invalid volatility provenance")
        if any(
            not isinstance(s, str) or len(s) != 64 or any(c not in "0123456789abcdef" for c in s)
            for s in (
                self.source_x6_capture_sha256,
                self.source_x5_capture_sha256,
                self.source_validation_sha256,
            )
        ):
            raise ValueError("Result requires exact source hashes")
        if (
            self.schema_version != "X6_REFERENCE_PRICING_RESULT_V1"
            or self.data_only is not True
            or (
                self.independent_vote is not False
                or any(
                    getattr(self, field) is not False
                    for field in (
                        "execution_authority",
                        "risk_authority",
                        "position_authority",
                        "certification_authority",
                        "live_execution_eligible",
                    )
                )
            )
        ):
            raise ValueError("Reference pricing cannot acquire trading authority")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def sha256(self) -> str:
        return canonical_sha256(self.to_dict())


def price_x6_capture_v1(
    *,
    capture: X6VolatilityCaptureV1,
    source_x5: X5ChainCaptureV1,
    annual_volatility: float | None,
    volatility_source_id: str | None,
    volatility_verified: bool,
) -> X6ReferencePricingResultV1:
    """Model-valued projection with X5 binding; no observed premium calibration.

    The caller must independently establish volatility units and input provenance;
    true flags here alone are not evidence of correctness of the external data.
    """
    if type(volatility_verified) is not bool:
        raise ValueError("volatility_verified must be exact bool")
    if annual_volatility is not None:
        _real(annual_volatility, "annual_volatility")
        if annual_volatility > _MAX_SIGMA:
            raise ValueError("annual volatility must be decimal in [0,5]")
    if volatility_source_id is not None and (
        not isinstance(volatility_source_id, str)
        or not volatility_source_id
        or volatility_source_id.strip() != volatility_source_id
    ):
        raise ValueError("volatility_source_id must be a canonical identifier")
    if volatility_verified and (annual_volatility is None or volatility_source_id is None):
        raise ValueError("Verified volatility requires an explicit value and provenance")
    validation = validate_x6_input_v1(capture=capture, source_x5=source_x5)
    ctx = capture.context
    blockers: list[str] = []
    if validation.model_status != "AVAILABLE":
        blockers.extend(
            x for x in validation.blockers if x != "VERIFIED_OPTION_PREMIUM_UNAVAILABLE"
        )
    t = ctx.time_to_expiry_years()
    if not volatility_verified:
        blockers.append(
            "VOLATILITY_UNVERIFIED" if annual_volatility is not None else "VOLATILITY_UNAVAILABLE"
        )
    if not capture.observations:
        blockers.append("NO_CAPTURED_OPTIONS")
    if t is not None and t > _MAX_YEARS:
        blockers.append("TIME_TO_EXPIRY_OUT_OF_RANGE")
    # Do not return a valid theoretical price when any model prerequisite is missing.
    blockers = list(dict.fromkeys(blockers))
    status = "AVAILABLE" if validation.time_status == "POINT_IN_TIME" else "RETROSPECTIVE"
    prices: list[X6ReferencePriceV1] = []
    for row in capture.observations:
        price = None
        row_blockers = tuple(blockers)
        if not row_blockers:
            kwargs = dict(
                strike=row.strike,
                years=t,
                rate=ctx.annual_risk_free_rate,
                volatility=annual_volatility,
                option_type=row.option_type,
            )
            if ctx.model == "BLACK_SCHOLES_SPOT":
                price = black_scholes_price_v1(
                    spot=ctx.reference_price, dividend_yield=ctx.annual_dividend_yield, **kwargs
                )
            else:
                price = black76_price_v1(future=ctx.reference_price, **kwargs)
        prices.append(
            X6ReferencePriceV1(
                canonical_option_id=row.canonical_option_id,
                source_record_id=row.source_record_id,
                option_type=row.option_type,
                strike=row.strike,
                theoretical_price=price,
                status=status if price is not None else "UNAVAILABLE",
                blockers=() if price is not None else row_blockers,
            )
        )
    overall = status if not blockers else "UNAVAILABLE"
    warnings = list(validation.warnings)
    if validation.premium_status != "AVAILABLE":
        warnings.append("NO_VERIFIED_OBSERVED_PREMIUM_FOR_COMPARISON")
    return X6ReferencePricingResultV1(
        market=ctx.market,
        model=ctx.model,
        capture_id=capture.capture_id,
        as_of=ctx.as_of,
        reference_unit=ctx.reference_unit,
        annual_volatility=float(annual_volatility)
        if annual_volatility is not None and volatility_verified
        else None,
        time_to_expiry_years=t,
        prices=tuple(prices),
        status=overall,
        blockers=tuple(blockers),
        warnings=tuple(dict.fromkeys(warnings)),
        source_x6_capture_sha256=capture.sha256(),
        source_x5_capture_sha256=source_x5.sha256(),
        source_validation_sha256=validation.sha256(),
        volatility_source_id=volatility_source_id if volatility_verified else None,
    )
