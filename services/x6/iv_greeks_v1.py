"""X6-B2: deterministic IV calibration and analytical model sensitivities.

Research-only European reference models. The X5 capture supplies premiums;
X6-A supplies independently verified model assumptions. Neither model nor
sensitivity is an executable quote, hedge ratio, position instruction or vote.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import datetime

from services.x5.contracts_v1 import X5ChainCaptureV1, canonical_sha256
from services.x6.contracts_v1 import MODEL_BY_MARKET, PRICE_UNITS, X6VolatilityCaptureV1
from services.x6.input_validation_v1 import validate_x6_input_v1
from services.x6.reference_pricing_v1 import black76_price_v1, black_scholes_price_v1

_MAX_VOL = 5.0  # decimal annualized volatility; consistent with X6-B1
_SQRT_2 = math.sqrt(2.0)
_SQRT_2PI = math.sqrt(2.0 * math.pi)


def _cdf(value: float) -> float:
    return 0.5 * math.erfc(-value / _SQRT_2)


def _pdf(value: float) -> float:
    return math.exp(-0.5 * value * value) / _SQRT_2PI


def _finite(value: object, *, positive: bool = False, signed: bool = False) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Expected a finite real number, never bool")
    result = float(value)
    if (positive and result <= 0) or (not signed and result < 0):
        raise ValueError("Invalid numeric sign")
    return result


def _model_price(
    *,
    model: str,
    reference_price: float,
    strike: float,
    years: float,
    rate: float,
    dividend_yield: float | None,
    sigma: float,
    option_type: str,
) -> float:
    arguments = dict(
        strike=strike, years=years, rate=rate, volatility=sigma, option_type=option_type
    )
    if model == "BLACK_SCHOLES_SPOT":
        if dividend_yield is None:
            raise ValueError("Spot pricing requires verified dividend yield")
        return black_scholes_price_v1(
            spot=reference_price, dividend_yield=dividend_yield, **arguments
        )
    if model == "BLACK_76_FUTURES":
        if dividend_yield is not None:
            raise ValueError("Black-76 must not receive a dividend yield")
        return black76_price_v1(future=reference_price, **arguments)
    raise ValueError("Unsupported X6 pricing model")


class X6IVEstimationError(ValueError):
    """Explicit model/identifiability condition, not a trading decision."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _vega_annual(
    *,
    model: str,
    reference_price: float,
    strike: float,
    years: float,
    rate: float,
    dividend_yield: float | None,
    sigma: float,
) -> float:
    s = reference_price
    root_t = math.sqrt(years)
    if model == "BLACK_SCHOLES_SPOT":
        q = dividend_yield
        d1 = (math.log(s / strike) + (rate - q + 0.5 * sigma * sigma) * years) / (sigma * root_t)
        return s * math.exp(-q * years) * _pdf(d1) * root_t
    d1 = (math.log(s / strike) + 0.5 * sigma * sigma * years) / (sigma * root_t)
    return math.exp(-rate * years) * s * _pdf(d1) * root_t


def implied_volatility_v1(
    *,
    model: str,
    reference_price: float,
    strike: float,
    years: float,
    rate: float,
    dividend_yield: float | None,
    premium: float,
    option_type: str,
) -> float:
    """Bisection IV in decimal annual units; reject non-identifiable premiums.

    Implied volatility is *model-implied*, not independently observed volatility.
    An intrinsic-price equality does not uniquely identify a stable positive IV.
    The supported range is (0, 5); a root on its endpoints is unavailable.
    """
    _finite(reference_price, positive=True)
    _finite(strike, positive=True)
    _finite(years, positive=True)
    _finite(rate, signed=True)
    observed = _finite(premium)
    if not 0 < years <= 100 or abs(rate) > 1:
        raise ValueError("Model time or annual rate outside X6 supported domain")
    if option_type not in ("CE", "PE"):
        raise ValueError("Expected CE or PE")
    if model == "BLACK_SCHOLES_SPOT":
        if dividend_yield is None or abs(_finite(dividend_yield, signed=True)) > 1:
            raise ValueError("Verified decimal dividend yield required")
    elif model != "BLACK_76_FUTURES" or dividend_yield is not None:
        raise ValueError("Incorrect X6 model/dividend convention")
    kwargs = dict(
        model=model,
        reference_price=reference_price,
        strike=strike,
        years=years,
        rate=rate,
        dividend_yield=dividend_yield,
        option_type=option_type,
    )
    lower = _model_price(sigma=0.0, **kwargs)
    high_price = _model_price(sigma=_MAX_VOL, **kwargs)
    price_tolerance = max(1e-10, 1e-12 * max(1.0, reference_price, observed))
    if observed < lower - price_tolerance:
        raise X6IVEstimationError("PREMIUM_BELOW_DISCOUNTED_INTRINSIC")
    if observed > high_price + price_tolerance:
        raise X6IVEstimationError("PREMIUM_ABOVE_SUPPORTED_VOLATILITY_RANGE")
    if observed - lower <= price_tolerance:
        raise X6IVEstimationError("IV_NOT_IDENTIFIABLE_AT_INTRINSIC")
    if high_price - observed <= price_tolerance:
        raise X6IVEstimationError("IV_AT_VOLATILITY_RANGE_BOUNDARY")
    low, high = 0.0, _MAX_VOL
    for _ in range(96):
        middle = (low + high) / 2
        priced = _model_price(sigma=middle, **kwargs)
        if priced < observed:
            low = middle
        else:
            high = middle
    sigma = (low + high) / 2
    if not 1e-10 < sigma < _MAX_VOL - 1e-10:
        raise X6IVEstimationError("IV_NEAR_UNSTABLE_MODEL_BOUNDARY")
    residual = abs(_model_price(sigma=sigma, **kwargs) - observed)
    if residual > price_tolerance:
        raise X6IVEstimationError("IV_SOLVER_RESIDUAL_TOO_LARGE")
    vega_per_1pp = (
        _vega_annual(
            model=model,
            reference_price=reference_price,
            strike=strike,
            years=years,
            rate=rate,
            dividend_yield=dividend_yield,
            sigma=sigma,
        )
        * 0.01
    )
    if not math.isfinite(vega_per_1pp) or vega_per_1pp <= price_tolerance * 100:
        raise X6IVEstimationError("IV_NUMERICALLY_ILL_CONDITIONED")
    return sigma


def analytical_greeks_v1(
    *,
    model: str,
    reference_price: float,
    strike: float,
    years: float,
    rate: float,
    dividend_yield: float | None,
    volatility: float,
    option_type: str,
) -> tuple[float, float, float, float, float]:
    """(delta, gamma, theta/calendar-day, vega/1 vol pp, rho/1 rate pp).

    For Black-76, delta/gamma differentiate the supplied FUTURES reference
    at fixed r and maturity. Black-76 rho differentiates at fixed futures
    reference; it is -T*theoretical_price/100, even for calls.
    """
    price = _model_price(
        model=model,
        reference_price=reference_price,
        strike=strike,
        years=years,
        rate=rate,
        dividend_yield=dividend_yield,
        sigma=volatility,
        option_type=option_type,
    )
    if not 0 < volatility <= _MAX_VOL:
        raise ValueError("Greeks require positive, finite sigma")
    s, k, t, r, sigma = (float(x) for x in (reference_price, strike, years, rate, volatility))
    root_t = math.sqrt(t)
    if model == "BLACK_SCHOLES_SPOT":
        q = float(dividend_yield)
        d1 = (math.log(s / k) + (r - q + 0.5 * sigma * sigma) * t) / (sigma * root_t)
        d2 = d1 - sigma * root_t
        ds = math.exp(-q * t)
        dk = math.exp(-r * t)
        common = s * ds * _pdf(d1) * sigma / (2 * root_t)
        if option_type == "CE":
            delta = ds * _cdf(d1)
            theta_year = -common - r * k * dk * _cdf(d2) + q * s * ds * _cdf(d1)
            rho = k * t * dk * _cdf(d2) * 0.01
        else:
            delta = ds * (_cdf(d1) - 1)
            theta_year = -common + r * k * dk * _cdf(-d2) - q * s * ds * _cdf(-d1)
            rho = -k * t * dk * _cdf(-d2) * 0.01
        gamma = ds * _pdf(d1) / (s * sigma * root_t)
        vega = s * ds * _pdf(d1) * root_t * 0.01
    else:
        d1 = (math.log(s / k) + 0.5 * sigma * sigma * t) / (sigma * root_t)
        disc = math.exp(-r * t)
        if option_type == "CE":
            delta = disc * _cdf(d1)
        else:
            delta = disc * (_cdf(d1) - 1)
        gamma = disc * _pdf(d1) / (s * sigma * root_t)
        vega = disc * s * _pdf(d1) * root_t * 0.01
        theta_year = r * price - disc * s * _pdf(d1) * sigma / (2 * root_t)
        rho = -t * price * 0.01
    result = (delta, gamma, theta_year / 365, vega, rho)
    if not all(math.isfinite(x) for x in result):
        raise ValueError("Nonfinite Greeks: reject model result")
    return result


@dataclass(frozen=True, slots=True)
class X6IVGreeksRowV1:
    canonical_option_id: str
    source_record_id: str
    option_type: str
    strike: float
    status: str
    implied_volatility_decimal: float | None
    model_price: float | None
    price_residual: float | None
    delta: float | None
    gamma: float | None
    theta_per_calendar_day: float | None
    vega_per_1vol_pp: float | None
    rho_per_1rate_pp: float | None
    blockers: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    schema_version: str = "X6_IV_GREEKS_ROW_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if any(
            not isinstance(x, str) or not x or x.strip() != x
            for x in (self.canonical_option_id, self.source_record_id)
        ) or self.option_type not in ("CE", "PE"):
            raise ValueError("Invalid option identity")
        _finite(self.strike, positive=True)
        if self.status not in ("AVAILABLE", "RETROSPECTIVE", "UNAVAILABLE"):
            raise ValueError("Unknown IV/Greeks status")
        values = (
            self.implied_volatility_decimal,
            self.model_price,
            self.price_residual,
            self.delta,
            self.gamma,
            self.theta_per_calendar_day,
            self.vega_per_1vol_pp,
            self.rho_per_1rate_pp,
        )
        if self.status == "UNAVAILABLE":
            if any(x is not None for x in values) or not self.blockers:
                raise ValueError("Unavailable row cannot retain inferred sensitivities")
        else:
            if any(x is None for x in values) or self.blockers:
                raise ValueError("Available row needs all values and no blockers")
            if not 0 < _finite(self.implied_volatility_decimal) <= _MAX_VOL:
                raise ValueError("IV must be annual decimal in supported range")
            _finite(self.model_price)
            _finite(self.price_residual, signed=True)
            for value in values[3:]:
                _finite(value, signed=True)
            if self.gamma < 0 or self.vega_per_1vol_pp < 0:
                raise ValueError("Gamma and vega cannot be negative under the model")
        if (
            type(self.blockers) is not tuple
            or type(self.warnings) is not tuple
            or any(
                not isinstance(x, str) or not x or x.strip() != x
                for x in self.blockers + self.warnings
            )
        ):
            raise ValueError("Diagnostics must be immutable, nonempty identifiers")
        if (
            self.schema_version != "X6_IV_GREEKS_ROW_V1"
            or self.data_only is not True
            or (
                self.independent_vote is not False
                or any(
                    getattr(self, f) is not False
                    for f in (
                        "execution_authority",
                        "risk_authority",
                        "position_authority",
                        "certification_authority",
                        "live_execution_eligible",
                    )
                )
            )
        ):
            raise ValueError("X6 rows cannot acquire trading authority")


@dataclass(frozen=True, slots=True)
class X6IVGreeksResultV1:
    market: str
    model: str
    capture_id: str
    as_of: datetime
    reference_unit: str
    time_to_expiry_years: float | None
    rows: tuple[X6IVGreeksRowV1, ...]
    status: str
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    source_x6_capture_sha256: str
    source_x5_capture_sha256: str
    source_validation_sha256: str
    schema_version: str = "X6_IV_GREEKS_RESULT_V1"
    data_only: bool = True
    independent_vote: bool = False
    execution_authority: bool = False
    risk_authority: bool = False
    position_authority: bool = False
    certification_authority: bool = False
    live_execution_eligible: bool = False

    def __post_init__(self) -> None:
        if self.market not in MODEL_BY_MARKET or self.model != MODEL_BY_MARKET[self.market]:
            raise ValueError("Result market/model identity mismatch")
        if (
            self.reference_unit != PRICE_UNITS[self.market]
            or not isinstance(self.capture_id, str)
            or not self.capture_id
        ):
            raise ValueError("Invalid result capture or unit")
        if (
            not isinstance(self.as_of, datetime)
            or self.as_of.tzinfo is None
            or (self.as_of.utcoffset() is None)
        ):
            raise ValueError("Aware as-of timestamp required")
        if self.time_to_expiry_years is not None:
            _finite(self.time_to_expiry_years, signed=True)
        if type(self.rows) is not tuple or any(
            not isinstance(x, X6IVGreeksRowV1) for x in self.rows
        ):
            raise ValueError("Result rows must be immutable X6 rows")
        if len({x.canonical_option_id for x in self.rows}) != len(self.rows):
            raise ValueError("Duplicate option sensitivities")
        if self.status not in ("AVAILABLE", "RETROSPECTIVE", "PARTIAL", "UNAVAILABLE"):
            raise ValueError("Unknown result availability")
        if (
            type(self.blockers) is not tuple
            or type(self.warnings) is not tuple
            or any(
                not isinstance(x, str) or not x or x.strip() != x
                for x in self.blockers + self.warnings
            )
        ):
            raise ValueError("Immutable diagnostics required")
        for digest in (
            self.source_x6_capture_sha256,
            self.source_x5_capture_sha256,
            self.source_validation_sha256,
        ):
            if (
                not isinstance(digest, str)
                or len(digest) != 64
                or any(c not in "0123456789abcdef" for c in digest)
            ):
                raise ValueError("Invalid source SHA-256")
        if self.status == "AVAILABLE" and (
            not self.rows or any(row.status != "AVAILABLE" for row in self.rows)
        ):
            raise ValueError("AVAILABLE result needs all point-in-time rows")
        if self.status == "UNAVAILABLE" and any(row.status != "UNAVAILABLE" for row in self.rows):
            raise ValueError("UNAVAILABLE result cannot carry available rows")
        if self.status == "RETROSPECTIVE" and (
            not self.rows or any(row.status != "RETROSPECTIVE" for row in self.rows)
        ):
            raise ValueError("RETROSPECTIVE result needs retrospective rows")
        if (
            self.schema_version != "X6_IV_GREEKS_RESULT_V1"
            or self.data_only is not True
            or (
                self.independent_vote is not False
                or any(
                    getattr(self, f) is not False
                    for f in (
                        "execution_authority",
                        "risk_authority",
                        "position_authority",
                        "certification_authority",
                        "live_execution_eligible",
                    )
                )
            )
        ):
            raise ValueError("X6 result cannot acquire trading authority")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def sha256(self) -> str:
        return canonical_sha256(self.to_dict())


def analyze_iv_greeks_v1(
    *, capture: X6VolatilityCaptureV1, source_x5: X5ChainCaptureV1
) -> X6IVGreeksResultV1:
    """Estimate each verified X5 premium independently; never fill missing data."""
    validation = validate_x6_input_v1(capture=capture, source_x5=source_x5)
    ctx = capture.context
    t = ctx.time_to_expiry_years()
    blockers = tuple(x for x in validation.blockers if x != "VERIFIED_OPTION_PREMIUM_UNAVAILABLE")
    if t is not None and t > 100:
        blockers += ("TIME_TO_EXPIRY_OUT_OF_RANGE",)
    if not capture.observations:
        blockers += ("NO_CAPTURED_OPTIONS",)
    row_status = "AVAILABLE" if validation.time_status == "POINT_IN_TIME" else "RETROSPECTIVE"
    rows: list[X6IVGreeksRowV1] = []
    for option in capture.observations:
        row_blockers = list(blockers)
        if not option.premium_verified:
            row_blockers.append("OPTION_PREMIUM_UNVERIFIED")
        if not row_blockers:
            kwargs = dict(
                model=ctx.model,
                reference_price=ctx.reference_price,
                strike=option.strike,
                years=t,
                rate=ctx.annual_risk_free_rate,
                dividend_yield=ctx.annual_dividend_yield,
                option_type=option.option_type,
            )
            try:
                sigma = implied_volatility_v1(premium=option.premium, **kwargs)
                model_price = _model_price(sigma=sigma, **kwargs)
                delta, gamma, theta, vega, rho = analytical_greeks_v1(volatility=sigma, **kwargs)
            except X6IVEstimationError as exc:
                row_blockers.append(exc.code)
            except (ValueError, OverflowError, ZeroDivisionError):
                row_blockers.append("NUMERICAL_MODEL_FAILURE")
        if row_blockers:
            rows.append(
                X6IVGreeksRowV1(
                    canonical_option_id=option.canonical_option_id,
                    source_record_id=option.source_record_id,
                    option_type=option.option_type,
                    strike=option.strike,
                    status="UNAVAILABLE",
                    implied_volatility_decimal=None,
                    model_price=None,
                    price_residual=None,
                    delta=None,
                    gamma=None,
                    theta_per_calendar_day=None,
                    vega_per_1vol_pp=None,
                    rho_per_1rate_pp=None,
                    blockers=tuple(dict.fromkeys(row_blockers)),
                )
            )
        else:
            rows.append(
                X6IVGreeksRowV1(
                    canonical_option_id=option.canonical_option_id,
                    source_record_id=option.source_record_id,
                    option_type=option.option_type,
                    strike=option.strike,
                    status=row_status,
                    implied_volatility_decimal=sigma,
                    model_price=model_price,
                    price_residual=model_price - option.premium,
                    delta=delta,
                    gamma=gamma,
                    theta_per_calendar_day=theta,
                    vega_per_1vol_pp=vega,
                    rho_per_1rate_pp=rho,
                    blockers=(),
                )
            )
    count = sum(row.status != "UNAVAILABLE" for row in rows)
    if not count:
        status = "UNAVAILABLE"
    elif count < len(rows):
        status = "PARTIAL"
    else:
        status = row_status
    if status == "UNAVAILABLE" and not blockers:
        blockers = ("NO_CALIBRATABLE_OPTIONS",)
    warnings_list = list(validation.warnings)
    if status == "PARTIAL":
        warnings_list.append("PARTIAL_IV_COVERAGE")
    warnings_list.append("CALIBRATION_LIMITED_TO_CAPTURED_STRIKE_WINDOW")
    warnings = tuple(dict.fromkeys(warnings_list))
    return X6IVGreeksResultV1(
        market=ctx.market,
        model=ctx.model,
        capture_id=capture.capture_id,
        as_of=ctx.as_of,
        reference_unit=ctx.reference_unit,
        time_to_expiry_years=t,
        rows=tuple(rows),
        status=status,
        blockers=blockers if status == "UNAVAILABLE" else (),
        warnings=warnings,
        source_x6_capture_sha256=capture.sha256(),
        source_x5_capture_sha256=source_x5.sha256(),
        source_validation_sha256=validation.sha256(),
    )
