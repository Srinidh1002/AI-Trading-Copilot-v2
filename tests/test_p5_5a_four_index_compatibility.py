"""Four-market compatibility coverage for the P5-5A option-chain foundation.

These checks deliberately use only the public, provider-neutral P5-5A boundary.
They do not import legacy option-chain helpers or provider adapters.
"""
from datetime import date, datetime, timezone

import pytest

from services.core.market_identity import SUPPORTED_MARKET_IDENTITIES
from services.option_chain_intelligence import (
    DEFAULT_OPTION_CHAIN_POLICY,
    build_canonical_option_chain_foundation,
    evaluate_option_chain_quality,
    normalize_option_chain_records,
)


NOW = datetime(2025, 1, 2, 9, 30, tzinfo=timezone.utc)
EXPIRY = date(2025, 1, 30)
IDENTITIES = (
    ("NIFTY", "NSE"),
    ("BANKNIFTY", "NSE"),
    ("FINNIFTY", "NSE"),
    ("SENSEX", "BSE"),
)


def _records(*, start=100.0, count=10, complete=True, provider_value=20000.0):
    """Return unordered, complete CALL/PUT records with no implied interval."""
    records = []
    # Deliberately irregular intervals prove P5-5A does not assume a NIFTY grid.
    strikes = tuple(start + offset for offset in (0, 37.5, 112.5, 175.0, 287.5, 350.0, 462.5, 525.0, 637.5, 700.0))[:count]
    for row_number, strike in enumerate(strikes):
        for option_type in ("CALL", "PUT"):
            records.append(
                {
                    "strike": strike,
                    "option_type": option_type,
                    "ltp": 10.0 + row_number,
                    "bid_price": 9.0 + row_number,
                    "ask_price": 11.0 + row_number,
                    "bid_quantity": 100 + row_number,
                    "ask_quantity": 110 + row_number,
                    "volume": 1000 + row_number,
                    "open_interest": 2000 + row_number,
                    "change_in_open_interest": row_number,
                    "implied_volatility": 15.0,
                    "underlying_value": provider_value,
                    "source_record_id": f"{option_type}-{row_number}",
                    "is_complete": complete,
                }
            )
    # Providers may supply records unordered; only the normalized rows may sort.
    return tuple(reversed(records))


def _normalize(symbol, exchange, *, records=None, provider_name="TEST_PROVIDER"):
    return normalize_option_chain_records(
        underlying_symbol=symbol,
        exchange=exchange,
        expiry=EXPIRY,
        underlying_value=20000.0,
        source_timestamp=NOW,
        provider_name=provider_name,
        records=_records() if records is None else records,
        clock=lambda: NOW,
    )


def _pipeline(symbol, exchange, *, records=None, provider_name="TEST_PROVIDER"):
    return build_canonical_option_chain_foundation(
        underlying_symbol=symbol,
        exchange=exchange,
        expiry=EXPIRY,
        underlying_value=20000.0,
        source_timestamp=NOW,
        provider_name=provider_name,
        records=_records() if records is None else records,
        clock=lambda: NOW,
    )


@pytest.mark.parametrize("symbol,exchange", IDENTITIES)
def test_normalization_preserves_the_exact_authoritative_identity(symbol, exchange):
    snapshot = _normalize(symbol, exchange)
    assert (snapshot.underlying_symbol, snapshot.exchange) == (symbol, exchange)


@pytest.mark.parametrize("symbol,exchange", IDENTITIES)
def test_normalized_rows_preserve_each_market_identity_and_expiry(symbol, exchange):
    snapshot = _normalize(symbol, exchange)
    assert all(
        (row.underlying_symbol, row.exchange, row.expiry) == (symbol, exchange, EXPIRY)
        for row in snapshot.strike_rows
    )


@pytest.mark.parametrize("symbol,exchange", IDENTITIES)
def test_quality_result_preserves_the_exact_authoritative_identity(symbol, exchange):
    snapshot = _normalize(symbol, exchange)
    quality = evaluate_option_chain_quality(snapshot=snapshot, clock=lambda: NOW)
    assert (quality.underlying_symbol, quality.exchange, quality.expiry) == (symbol, exchange, EXPIRY)


@pytest.mark.parametrize("symbol,exchange", IDENTITIES)
def test_pipeline_preserves_identity_on_both_linked_outputs(symbol, exchange):
    snapshot, quality = _pipeline(symbol, exchange)
    assert (snapshot.underlying_symbol, snapshot.exchange) == (symbol, exchange)
    assert (quality.underlying_symbol, quality.exchange) == (symbol, exchange)
    assert quality.option_chain_snapshot_id == snapshot.option_chain_snapshot_id


@pytest.mark.parametrize("symbol,exchange", IDENTITIES)
def test_valid_market_has_no_hidden_nifty_or_nse_fallback(symbol, exchange):
    snapshot, quality = _pipeline(symbol, exchange, provider_name=f"SOURCE-{symbol}-{exchange}")
    assert snapshot.provider_name == f"SOURCE-{symbol}-{exchange}"
    assert quality.underlying_symbol == symbol
    assert quality.exchange == exchange


@pytest.mark.parametrize("symbol,exchange", IDENTITIES)
def test_irregular_strikes_are_preserved_without_market_specific_grid_assumptions(symbol, exchange):
    snapshot = _normalize(symbol, exchange)
    actual = tuple(row.strike for row in snapshot.strike_rows)
    assert actual == tuple(sorted(actual))
    assert actual == (100.0, 137.5, 212.5, 275.0, 387.5, 450.0, 562.5, 625.0, 737.5, 800.0)


@pytest.mark.parametrize("symbol,exchange", IDENTITIES)
def test_supported_market_policy_includes_each_exact_pair(symbol, exchange):
    assert (symbol, exchange) in DEFAULT_OPTION_CHAIN_POLICY.supported_markets
    assert (symbol, exchange) in SUPPORTED_MARKET_IDENTITIES


@pytest.mark.parametrize("symbol,exchange", IDENTITIES)
def test_snapshot_serialization_keeps_each_exact_market_pair(symbol, exchange):
    snapshot = _normalize(symbol, exchange)
    serialized = snapshot.to_dict()
    assert (serialized["underlying_symbol"], serialized["exchange"]) == (symbol, exchange)


@pytest.mark.parametrize("symbol,exchange", IDENTITIES)
def test_each_market_reconciles_complete_pair_and_side_counts(symbol, exchange):
    snapshot = _normalize(symbol, exchange)
    assert snapshot.strike_count == 10
    assert snapshot.complete_pair_count == 10
    assert snapshot.call_only_count == 0
    assert snapshot.put_only_count == 0


@pytest.mark.parametrize("symbol,exchange", IDENTITIES)
def test_each_market_normalization_does_not_mutate_supplied_records(symbol, exchange):
    records = _records()
    original = tuple(dict(record) for record in records)
    _normalize(symbol, exchange, records=records)
    assert records == tuple(original)


@pytest.mark.parametrize(
    "symbol,exchange",
    (
        ("NIFTY", "BSE"),
        ("BANKNIFTY", "BSE"),
        ("FINNIFTY", "BSE"),
        ("SENSEX", "NSE"),
        ("NIFTY", ""),
        ("SENSEX", ""),
        ("OTHER", "NSE"),
        ("OTHER", "BSE"),
    ),
)
def test_noncanonical_or_mismatched_market_pairs_are_rejected(symbol, exchange):
    with pytest.raises((TypeError, ValueError)):
        _normalize(symbol, exchange)


@pytest.mark.parametrize(
    "symbol",
    (
        "NIFTY 50",
        "NIFTY50",
        "BANK NIFTY",
        "NIFTY BANK",
        "FIN NIFTY",
        "NIFTY FINANCIAL SERVICES",
        "BSE SENSEX",
    ),
)
def test_aliases_are_not_accepted_as_canonical_option_chain_identities(symbol):
    with pytest.raises((TypeError, ValueError)):
        _normalize(symbol, "BSE" if symbol == "BSE SENSEX" else "NSE")


@pytest.mark.parametrize("symbol,exchange", IDENTITIES)
def test_partial_chain_keeps_market_identity_without_fabricating_missing_sides(symbol, exchange):
    call_only = tuple(record for record in _records() if record["option_type"] == "CALL")
    snapshot = _normalize(symbol, exchange, records=call_only)
    assert (snapshot.underlying_symbol, snapshot.exchange) == (symbol, exchange)
    assert snapshot.call_only_count == len(snapshot.strike_rows)
    assert snapshot.put_only_count == 0


@pytest.mark.parametrize("symbol,exchange", IDENTITIES)
def test_sensex_is_the_only_bse_authoritative_pair_and_nse_indices_stay_nse(symbol, exchange):
    snapshot = _normalize(symbol, exchange)
    assert (symbol == "SENSEX") is (snapshot.exchange == "BSE")
