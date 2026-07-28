"""Deterministic quality and freshness evaluation for canonical option chains."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import math


_BLOCKING_STATUSES = {
    "EMPTY",
    "STALE",
    "FUTURE",
    "INCOMPLETE",
    "MALFORMED",
    "UNSUPPORTED",
    "FAILED",
}


def _is_aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _resolve_clock(clock: Callable[[], datetime] | None) -> datetime:
    if clock is not None and not callable(clock):
        raise ValueError("clock must be callable when supplied.")
    value = clock() if clock is not None else datetime.now(timezone.utc)
    if not _is_aware(value):
        raise ValueError("clock must return a timezone-aware datetime.")
    return value


def _next_id(factory: Callable[[], object] | None, snapshot_id: str) -> str:
    value = factory() if factory is not None else f"option-chain-quality-{snapshot_id}"
    if not isinstance(value, str) or not value.strip():
        raise ValueError("option_chain_quality_result_id_factory must return a non-empty string.")
    return value


def _unique(values) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        if isinstance(value, str) and value and value not in result:
            result.append(value)
    return tuple(result)


def _contains_marker(values, marker: str) -> bool:
    return any(marker in value.lower() for value in values if isinstance(value, str))


def _controlled_warning(value: str) -> bool:
    return value == "crossed_market" or value.startswith("duplicate_option_side:")


def evaluate_option_chain_quality(
    *,
    snapshot,
    policy=None,
    clock=None,
    option_chain_quality_result_id_factory=None,
):
    """Return a bounded, non-directional quality result for ``snapshot``.

    The evaluator deliberately only measures structural completeness, freshness,
    identity, and explicitly represented malformed conditions.  It does not
    derive PCR, OI, volatility, directional, or selection intelligence.
    """
    from services.contracts import (
        DEFAULT_OPTION_CHAIN_POLICY,
        OptionChainPolicyV1,
        OptionChainQualityResultV1,
        OptionChainSnapshotV1,
    )

    if not isinstance(snapshot, OptionChainSnapshotV1):
        raise ValueError("snapshot must be OptionChainSnapshotV1.")
    if policy is None:
        policy = DEFAULT_OPTION_CHAIN_POLICY
    if not isinstance(policy, OptionChainPolicyV1):
        raise ValueError("policy must be OptionChainPolicyV1.")
    if option_chain_quality_result_id_factory is not None and not callable(option_chain_quality_result_id_factory):
        raise ValueError("option_chain_quality_result_id_factory must be callable when supplied.")

    now = _resolve_clock(clock)
    # Snapshot validation guarantees a timezone-aware timestamp.  Keep the
    # explicit check here so manually constructed future contract revisions fail
    # closed rather than leaking a type error from datetime arithmetic.
    if not _is_aware(snapshot.source_timestamp):
        raise ValueError("snapshot source_timestamp must be timezone-aware.")

    rows = snapshot.strike_rows
    total_strikes = len(rows)
    complete_pair_count = sum(row.call is not None and row.put is not None for row in rows)
    missing_call_count = sum(row.call is None for row in rows)
    missing_put_count = sum(row.put is None for row in rows)
    completeness_ratio = complete_pair_count / total_strikes if total_strikes else 0.0

    quote_warnings = []
    quote_blockers = []
    malformed_quote_count = 0
    for row in rows:
        for quote in (row.call, row.put):
            if quote is None:
                continue
            quote_warnings.extend(quote.warnings)
            quote_blockers.extend(quote.blockers)
            crossed = quote.bid_price is not None and quote.ask_price is not None and quote.bid_price > quote.ask_price
            malformed = crossed or _contains_marker(quote.blockers + quote.warnings, "malformed")
            malformed_quote_count += int(malformed)

    row_warnings = [warning for row in rows for warning in row.warnings]
    row_blockers = [blocker for row in rows for blocker in row.blockers]
    snapshot_warnings = tuple(snapshot.warnings)
    snapshot_blockers = tuple(snapshot.blockers)
    duplicate_strike_count = sum(warning.startswith("duplicate_option_side:") for warning in snapshot_warnings)
    crossed_market = any(
        quote.bid_price is not None and quote.ask_price is not None and quote.bid_price > quote.ask_price
        for row in rows
        for quote in (row.call, row.put)
        if quote is not None
    )

    all_blockers = tuple(snapshot_blockers) + tuple(row_blockers) + tuple(quote_blockers)
    identity_supported = (snapshot.underlying_symbol, snapshot.exchange) in policy.supported_markets
    # Preserve a negative age for future evidence rather than disguising it as
    # fresh data.  The FUTURE status is still selected from the policy tolerance.
    age_seconds = float((now - snapshot.source_timestamp).total_seconds())
    future = snapshot.source_timestamp > now and (snapshot.source_timestamp - now).total_seconds() > policy.future_tolerance_seconds

    malformed_marker = _contains_marker(all_blockers, "malformed") or _contains_marker(snapshot_warnings + tuple(row_warnings) + tuple(quote_warnings), "malformed")
    failed_marker = _contains_marker(all_blockers, "failed")
    unsupported_marker = _contains_marker(all_blockers, "unsupported")
    unknown_blocker = any(
        blocker not in {"empty_option_chain"}
        and not _contains_marker((blocker,), "failed")
        and not _contains_marker((blocker,), "unsupported")
        and not _contains_marker((blocker,), "malformed")
        for blocker in all_blockers
    )

    base_warnings = list(snapshot_warnings) + row_warnings + quote_warnings
    # A crossed quote or duplicate is not automatically a quality warning under
    # ALLOW; it remains observable in the immutable source snapshot but does not
    # alter the policy-controlled quality conclusion.
    if policy.crossed_market_behavior == "ALLOW":
        base_warnings = [warning for warning in base_warnings if warning != "crossed_market"]
    if policy.duplicate_strike_behavior == "ALLOW":
        base_warnings = [warning for warning in base_warnings if not warning.startswith("duplicate_option_side:")]

    warnings = _unique(base_warnings)
    blockers: tuple[str, ...]
    status: str

    # Preserve the documented status precedence exactly.
    if failed_marker:
        status = "FAILED"
        blockers = _unique(all_blockers + ("option_chain_failed",))
    elif not identity_supported or unsupported_marker:
        status = "UNSUPPORTED"
        blockers = _unique(all_blockers + ("unsupported_market_identity",))
    elif malformed_marker or unknown_blocker or (crossed_market and policy.crossed_market_behavior == "BLOCK") or (duplicate_strike_count and policy.duplicate_strike_behavior == "BLOCK"):
        status = "MALFORMED"
        additional = []
        if crossed_market and policy.crossed_market_behavior == "BLOCK":
            additional.append("crossed_market")
        if duplicate_strike_count and policy.duplicate_strike_behavior == "BLOCK":
            additional.append("duplicate_option_side")
        if malformed_quote_count and not additional:
            additional.append("malformed_quote")
        blockers = _unique(all_blockers + tuple(additional) + ("malformed_option_chain",))
    elif future:
        status = "FUTURE"
        blockers = _unique(("source_timestamp_in_future",))
    elif not total_strikes:
        status = "EMPTY"
        blockers = _unique(("empty_option_chain",))
    elif age_seconds > policy.maximum_age_seconds:
        status = "STALE"
        blockers = _unique(("option_chain_stale",))
    else:
        incomplete_reasons = []
        if total_strikes < policy.minimum_total_strikes:
            incomplete_reasons.append("minimum_total_strikes_not_met")
        if complete_pair_count < policy.minimum_complete_pairs:
            incomplete_reasons.append("minimum_complete_pairs_not_met")
        if completeness_ratio < policy.minimum_completeness_ratio:
            incomplete_reasons.append("minimum_completeness_ratio_not_met")
        missing_reasons = []
        if missing_call_count:
            missing_reasons.append("missing_call_side")
        if missing_put_count:
            missing_reasons.append("missing_put_side")

        if incomplete_reasons and policy.incomplete_behavior == "BLOCK":
            status = "INCOMPLETE"
            blockers = _unique(tuple(incomplete_reasons))
        elif missing_reasons and policy.missing_side_behavior == "BLOCK":
            status = "INCOMPLETE"
            blockers = _unique(tuple(missing_reasons))
        else:
            if incomplete_reasons and policy.incomplete_behavior == "WARN":
                warnings = _unique(warnings + tuple(incomplete_reasons))
            if missing_reasons and policy.missing_side_behavior == "WARN":
                warnings = _unique(warnings + tuple(missing_reasons))
            if crossed_market and policy.crossed_market_behavior == "WARN":
                warnings = _unique(warnings + ("crossed_market",))
            if duplicate_strike_count and policy.duplicate_strike_behavior == "WARN":
                warnings = _unique(warnings + ("duplicate_option_side",))
            status = "VALID_WITH_WARNINGS" if warnings else "VALID"
            blockers = ()

    result_id = _next_id(option_chain_quality_result_id_factory, snapshot.option_chain_snapshot_id)
    return OptionChainQualityResultV1(
        option_chain_quality_result_id=result_id,
        created_at=now,
        option_chain_snapshot_id=snapshot.option_chain_snapshot_id,
        underlying_symbol=snapshot.underlying_symbol,
        exchange=snapshot.exchange,
        expiry=snapshot.expiry,
        quality_status=status,
        age_seconds=age_seconds,
        total_strikes=total_strikes,
        complete_pair_count=complete_pair_count,
        missing_call_count=missing_call_count,
        missing_put_count=missing_put_count,
        malformed_quote_count=malformed_quote_count,
        duplicate_strike_count=duplicate_strike_count,
        completeness_ratio=completeness_ratio,
        blockers=blockers,
        # Blocking findings do not erase independently observed bounded source
        # warnings.  A fully VALID result, however, intentionally has none.
        warnings=warnings if status != "VALID" else (),
    )
