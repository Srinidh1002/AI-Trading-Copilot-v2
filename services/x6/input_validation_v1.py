"""Validate offline X6 pricing assumptions and exact X5 observation provenance.

No FYERS SDK calls; proof is limited to the provided immutable captures.
The supplied independent rate/reference/expiry verification flags are not
independent evidence that the upstream provider represented them correctly.
"""

from __future__ import annotations

import math

from services.x5.contracts_v1 import X5ChainCaptureV1
from services.x6.contracts_v1 import (
    X6InputValidationV1,
    X6VolatilityCaptureV1,
)


def validate_x6_input_v1(
    *, capture: X6VolatilityCaptureV1, source_x5: X5ChainCaptureV1
) -> X6InputValidationV1:
    """Fail closed on incorrect source binding; return unavailable for missing evidence."""
    if not isinstance(capture, X6VolatilityCaptureV1) or not isinstance(
        source_x5, X5ChainCaptureV1
    ):
        raise TypeError("X6 and X5 immutable capture contracts are required")
    ctx = capture.context
    if capture.source_x5_capture_sha256 != source_x5.sha256():
        raise ValueError("X5 source content does not match the bound SHA-256")
    if (
        ctx.market != source_x5.contract.market
        or ctx.option_expiry != source_x5.contract.expiry
        or ctx.as_of != source_x5.as_of
        or capture.session_id != source_x5.session_id
        or capture.capture_id != source_x5.capture_id
    ):
        raise ValueError("X6 context and X5 market/session/expiry/capture mismatch")
    if capture.point_in_time_verified and not source_x5.point_in_time_verified:
        raise ValueError("X6 cannot promote retrospective X5 evidence to point-in-time")
    if ctx.expiry_instant_verified and not source_x5.expiry_verified:
        raise ValueError("X6 expiry proof conflicts with X5 expiry provenance")
    if (
        ctx.reference_verified
        and source_x5.underlying_verified
        and (
            not math.isclose(ctx.reference_price, source_x5.underlying_value, rel_tol=1e-12)
            or ctx.reference_unit != source_x5.underlying_unit
        )
    ):
        raise ValueError("Independently provided reference conflicts with verified X5 reference")
    mapped = {row.canonical_option_id: row for row in source_x5.observations}
    verified_premiums = 0
    for row in capture.observations:
        original = mapped.get(row.canonical_option_id)
        if original is None or (
            row.source_record_id != original.source_record_id
            or row.option_type != original.option_type
            or row.strike != original.strike
            or row.observed_at != original.observed_at
        ):
            raise ValueError("X6 row cannot be bound to the exact X5 option observation")
        original_price = None
        if row.premium_source == "LTP":
            original_price = original.ltp
        elif row.premium_source == "MID":
            if original.bid_price is not None and original.ask_price is not None:
                original_price = (original.bid_price + original.ask_price) / 2
        if row.premium is not None and (
            original_price is None
            or not math.isclose(row.premium, original_price, abs_tol=1e-10, rel_tol=1e-12)
        ):
            raise ValueError("X6 premium is not the named X5 source price")
        if row.premium_verified and not original.premium_unit_verified:
            raise ValueError("X6 cannot promote an unverified X5 option premium")
        if row.premium_verified and original.premium_unit != ctx.premium_unit:
            raise ValueError("Source premium units differ from X6 pricing-model units")
        if row.premium_verified:
            verified_premiums += 1
    blockers: list[str] = []
    warnings: list[str] = []
    t = ctx.time_to_expiry_years()
    if t is None or t <= 0 or not ctx.expiry_instant_verified:
        blockers.append("EXACT_FUTURE_EXPIRY_INSTANT_UNAVAILABLE")
    if not ctx.reference_verified:
        blockers.append("REFERENCE_PRICE_UNVERIFIED")
    if not ctx.rate_verified:
        blockers.append("DISCOUNT_RATE_UNVERIFIED")
    if ctx.model == "BLACK_SCHOLES_SPOT" and not ctx.dividend_verified:
        blockers.append("DIVIDEND_YIELD_UNVERIFIED")
    if ctx.model == "BLACK_76_FUTURES" and not ctx.futures_identity_verified:
        blockers.append("UNDERLYING_FUTURES_IDENTITY_UNVERIFIED")
    if source_x5.contract.metadata_status != "VERIFIED":
        blockers.append("X5_CONTRACT_METADATA_UNVERIFIED")
    if not source_x5.capture_verified or not source_x5.timestamp_semantics_verified:
        blockers.append("X5_CAPTURE_OR_TIMESTAMPS_UNVERIFIED")
    if verified_premiums == 0:
        blockers.append("VERIFIED_OPTION_PREMIUM_UNAVAILABLE")
    if not capture.observations:
        warnings.append("NO_OBSERVATIONS_IN_CAPTURE")
    if len(capture.observations) < len(source_x5.observations):
        warnings.append("PARTIAL_CAPTURED_STRIKE_WINDOW")
    time_status = (
        "POINT_IN_TIME"
        if capture.point_in_time_verified and source_x5.point_in_time_verified
        else "RETROSPECTIVE"
    )
    if time_status == "RETROSPECTIVE":
        warnings.append("NOT_PROVEN_POINT_IN_TIME")
    model_blockers = tuple(x for x in blockers if x != "VERIFIED_OPTION_PREMIUM_UNAVAILABLE")
    model_status = "UNAVAILABLE" if model_blockers else "AVAILABLE"
    premium_status = "AVAILABLE" if verified_premiums else "UNAVAILABLE"
    status = (
        "UNAVAILABLE"
        if model_status == "UNAVAILABLE" or premium_status == "UNAVAILABLE"
        else "AVAILABLE"
        if time_status == "POINT_IN_TIME"
        else "PARTIAL"
    )
    return X6InputValidationV1(
        market=ctx.market,
        capture_id=capture.capture_id,
        as_of=ctx.as_of,
        model_status=model_status,
        premium_status=premium_status,
        time_status=time_status,
        status=status,
        blockers=tuple(blockers),
        warnings=tuple(warnings),
        source_capture_sha256=capture.sha256(),
        source_x5_capture_sha256=source_x5.sha256(),
    )
