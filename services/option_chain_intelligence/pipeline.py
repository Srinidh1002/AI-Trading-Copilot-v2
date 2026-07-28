"""Canonical, supplied-record-only option-chain foundation pipeline."""
from __future__ import annotations

from datetime import datetime, timezone

from .normalization import _resolve_clock, _validate_normalization_inputs


def build_canonical_option_chain_foundation(
    *,
    underlying_symbol,
    exchange,
    expiry,
    underlying_value,
    source_timestamp,
    provider_name,
    records,
    policy=None,
    clock=None,
    option_quote_id_factory=None,
    strike_row_id_factory=None,
    option_chain_snapshot_id_factory=None,
    option_chain_quality_result_id_factory=None,
):
    """Normalize supplied records once, then evaluate their quality once.

    The pipeline has no fetch, cache, provider adapter, option scoring, or
    execution behavior.  A single timezone-aware instant is shared by every
    object produced in a call.
    """
    _validate_normalization_inputs(
        underlying_symbol=underlying_symbol,
        exchange=exchange,
        expiry=expiry,
        underlying_value=underlying_value,
        source_timestamp=source_timestamp,
        provider_name=provider_name,
        records=records,
        option_quote_id_factory=option_quote_id_factory,
        strike_row_id_factory=strike_row_id_factory,
        option_chain_snapshot_id_factory=option_chain_snapshot_id_factory,
    )
    if option_chain_quality_result_id_factory is not None and not callable(option_chain_quality_result_id_factory):
        raise ValueError("option_chain_quality_result_id_factory must be callable when supplied.")

    # Validate the policy before consuming the caller's clock.  This preserves
    # deterministic failure behavior and prevents invalid inputs from invoking
    # external clock hooks.
    from services.contracts import DEFAULT_OPTION_CHAIN_POLICY, OptionChainPolicyV1

    if policy is None:
        policy = DEFAULT_OPTION_CHAIN_POLICY
    if not isinstance(policy, OptionChainPolicyV1):
        raise ValueError("policy must be OptionChainPolicyV1.")
    now = _resolve_clock(clock)

    from .normalization import normalize_option_chain_records
    from .quality import evaluate_option_chain_quality

    snapshot = normalize_option_chain_records(
        underlying_symbol=underlying_symbol,
        exchange=exchange,
        expiry=expiry,
        underlying_value=underlying_value,
        source_timestamp=source_timestamp,
        provider_name=provider_name,
        records=records,
        clock=lambda: now,
        option_quote_id_factory=option_quote_id_factory,
        strike_row_id_factory=strike_row_id_factory,
        option_chain_snapshot_id_factory=option_chain_snapshot_id_factory,
    )
    quality = evaluate_option_chain_quality(
        snapshot=snapshot,
        policy=policy,
        clock=lambda: now,
        option_chain_quality_result_id_factory=option_chain_quality_result_id_factory,
    )
    if (
        quality.option_chain_snapshot_id != snapshot.option_chain_snapshot_id
        or (quality.underlying_symbol, quality.exchange, quality.expiry)
        != (snapshot.underlying_symbol, snapshot.exchange, snapshot.expiry)
    ):
        raise ValueError("Option-chain pipeline linkage mismatch.")
    return snapshot, quality
