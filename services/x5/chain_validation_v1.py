"""Fail-closed X5 chain quality, pairing and metric-readiness assessment."""

from __future__ import annotations

import math

from services.x5.contracts_v1 import IST, X5ChainCaptureV1, X5ChainValidationV1

METRICS = (
    "PCR_OI",
    "PCR_VOLUME",
    "MAX_PAIN",
    "OI_CONCENTRATION",
    "OI_BUILDUP",
    "OI_SUPPORT_RESISTANCE",
    "IV_SKEW",
    "QUOTE_SPREAD",
    "GREEKS",
)


def validate_x5_chain_v1(
    capture: X5ChainCaptureV1, *, max_age_seconds: float
) -> X5ChainValidationV1:
    """Inspect supplied evidence; does not fetch chains or compute directional metrics.

    AVAILABLE means a metric can be attempted by a later engine, not that the
    metric is valid, independently informative or approved for trading.
    """
    if not isinstance(capture, X5ChainCaptureV1):
        raise ValueError("A versioned X5 chain capture is required")
    if (
        type(max_age_seconds) not in (int, float)
        or not math.isfinite(max_age_seconds)
        or max_age_seconds <= 0
    ):
        raise ValueError("Positive finite freshness budget is required")
    rows = capture.observations
    calls = {float(row.strike) for row in rows if row.option_type == "CE"}
    puts = {float(row.strike) for row in rows if row.option_type == "PE"}
    pair_count = len(calls & puts)
    blockers: list[str] = []
    warnings: list[str] = []
    if capture.contract.metadata_status != "VERIFIED":
        blockers.append("CONTRACT_METADATA_UNVERIFIED")
    if not capture.capture_verified:
        blockers.append("CAPTURE_UNVERIFIED")
    if not capture.expiry_verified:
        blockers.append("EXPIRY_UNVERIFIED")
    if not capture.timestamp_semantics_verified:
        blockers.append("TIMESTAMP_SEMANTICS_UNVERIFIED")
    local_time = capture.as_of.astimezone(IST)
    if local_time.date() > capture.contract.expiry:
        blockers.append("EXPIRED_OPTION_CHAIN")
    elif local_time.date() == capture.contract.expiry:
        if capture.contract.option_exchange == "MCX":
            blockers.append("MCX_SAME_DAY_EXPIRY_REQUIRES_SEPARATE_REVIEW")
        elif local_time.hour >= 15 and (local_time.hour > 15 or local_time.minute >= 30):
            blockers.append("INDEX_OPTION_EXPIRY_CUTOFF")
    if not rows:
        blockers.append("EMPTY_CHAIN")
    elif any((capture.as_of - row.observed_at).total_seconds() > max_age_seconds for row in rows):
        blockers.append("STALE_OPTION_ROWS")
    if capture.historical_retrieval or not capture.point_in_time_verified:
        warnings.append("POINT_IN_TIME_AVAILABILITY_UNPROVEN")
    if pair_count == 0 and rows:
        warnings.append("NO_COMPLETE_CE_PE_PAIR")
    if len(calls ^ puts) > 0:
        warnings.append("INCOMPLETE_CE_PE_PAIRS")
    if not capture.underlying_verified:
        warnings.append("UNDERLYING_PRICE_OR_UNIT_UNVERIFIED")
    if any(row.oi_unit_verified is False for row in rows):
        warnings.append("OI_UNIT_UNVERIFIED_FOR_SOME_ROWS")
    if any(row.volume_unit_verified is False for row in rows):
        warnings.append("VOLUME_UNIT_UNVERIFIED_FOR_SOME_ROWS")
    if any(row.iv_verified is False for row in rows):
        warnings.append("IV_UNIT_UNVERIFIED_FOR_SOME_ROWS")
    if any(row.greeks_verified is False for row in rows):
        warnings.append("GREEKS_UNVERIFIED_FOR_SOME_ROWS")

    # Full-strike coverage is required for whole-chain totals. Partial chain
    # metrics cannot silently extrapolate to an exchange-wide number.
    whole_chain = bool(rows) and bool(pair_count) and len(calls) == len(puts) == pair_count
    oi_ready = (
        whole_chain
        and all(row.oi_unit_verified and row.oi_timestamp_verified for row in rows)
        and len({row.oi_unit for row in rows}) == 1
    )
    volume_ready = (
        whole_chain
        and all(row.volume_unit_verified and row.volume_timestamp_verified for row in rows)
        and len({row.volume_unit for row in rows}) == 1
    )
    oi_change_ready = oi_ready and all(row.oi_change_verified for row in rows)
    iv_ready = whole_chain and all(row.iv_verified for row in rows)
    # IV skew requires the same declared IV unit for all paired observations.
    iv_ready = iv_ready and len({row.iv_unit for row in rows}) == 1
    quotes_ready = (
        whole_chain
        and all(
            row.bid_price is not None and row.ask_price is not None and row.premium_unit_verified
            for row in rows
        )
        and len({row.premium_unit for row in rows}) == 1
    )
    greeks_ready = whole_chain and all(
        row.greeks_verified
        and all(getattr(row, name) is not None for name in ("delta", "gamma", "theta", "vega"))
        for row in rows
    )
    can_research = not blockers and capture.point_in_time_verified
    states = (
        ("PCR_OI", oi_ready),
        ("PCR_VOLUME", volume_ready),
        ("MAX_PAIN", oi_ready and capture.underlying_verified),
        ("OI_CONCENTRATION", oi_ready),
        ("OI_BUILDUP", oi_change_ready),
        ("OI_SUPPORT_RESISTANCE", oi_ready and capture.underlying_verified),
        ("IV_SKEW", iv_ready),
        ("QUOTE_SPREAD", quotes_ready),
        ("GREEKS", greeks_ready),
    )
    readiness = tuple(
        (name, "AVAILABLE" if can_research and eligible else "UNAVAILABLE")
        for name, eligible in states
    )
    if blockers:
        status = "UNAVAILABLE"
    elif not capture.point_in_time_verified or any(
        state == "UNAVAILABLE" for _, state in readiness
    ):
        status = "PARTIAL"
    else:
        status = "AVAILABLE"
    return X5ChainValidationV1(
        market=capture.contract.market,
        expiry=capture.contract.expiry,
        capture_id=capture.capture_id,
        as_of=capture.as_of,
        status=status,
        call_count=len(calls),
        put_count=len(puts),
        complete_pair_count=pair_count,
        call_only_count=len(calls - puts),
        put_only_count=len(puts - calls),
        readiness=readiness,
        blockers=tuple(blockers),
        warnings=tuple(warnings),
        source_capture_sha256=capture.sha256(),
    )
