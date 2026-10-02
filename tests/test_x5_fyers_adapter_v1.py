"""Offline FYERS-native chain adapter tests: no SDK, auth, network, PAPER or orders."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from services.x5.contracts_v1 import X5ContractV1
from services.x5.fyers_adapter_v1 import adapt_fyers_option_chain_v1

NOW = datetime(2026, 10, 1, 10, 0, tzinfo=UTC)
EXPIRY = date(2026, 10, 29)
EPOCH = 1793232000
MARKETS = {
    "NIFTY": ("NFO", "NSE:NIFTY50-INDEX", "NSE:NIFTY26OCT291000"),
    "SENSEX": ("BFO", "BSE:SENSEX-INDEX", "BSE:SENSEX26OCT291000"),
    "CRUDEOILM": ("MCX", "MCX:CRUDEOILM", "MCX:CRUDEOILM26OCT291000"),
    "GOLDM": ("MCX", "MCX:GOLDM", "MCX:GOLDM26OCT291000"),
    "NATGASMINI": ("MCX", "MCX:NATGASMINI", "MCX:NATGASMINI26OCT291000"),
}
UNITS = {
    "NIFTY": "INDEX_POINTS",
    "SENSEX": "INDEX_POINTS",
    "CRUDEOILM": "INR_PER_BARREL",
    "GOLDM": "INR_PER_10G",
    "NATGASMINI": "INR_PER_MMBTU",
}


def make_args(market="NIFTY"):
    exchange, root, prefix = MARKETS[market]
    rows = tuple(
        {
            "symbol": prefix + side,
            "type": side,
            "strike": 100.0,
            "expiry": EPOCH,
            "ltp": 5.0,
            "bid": 4.5,
            "ask": 5.5,
            "oi": 200.0 if side == "CE" else 100.0,
            "volume": 20.0 if side == "CE" else 10.0,
            "oich": -10.0 if side == "CE" else 5.0,
        }
        for side in ("CE", "PE")
    )
    contract = X5ContractV1(
        market=market,
        provider="FYERS",
        underlying_provider_symbol=root,
        option_exchange=exchange,
        expiry=EXPIRY,
        expiry_source_id="FYERS_EXPIRY_CAPTURE",
        metadata_status="VERIFIED",
        metadata_source="TEST_MASTER_EVIDENCE",
    )
    symbols = tuple(x["symbol"] for x in rows)
    return dict(
        contract=contract,
        provider_result={
            "provider": "FYERS",
            "underlying_symbol": root,
            "rows": rows,
            "request_count": 1,
            "per_contract_depth_requests": 0,
            "data_only": True,
            "live_execution_eligible": False,
            "expiry_data": ({"date": EXPIRY.isoformat(), "expiry": EPOCH},),
            "provider_expiry_date": EXPIRY.isoformat(),
            "provider_expiry_timestamp": EPOCH,
        },
        canonical_ids_by_symbol={symbol: "TEST_CANONICAL:" + symbol for symbol in symbols},
        observed_at_by_symbol={symbol: NOW - timedelta(seconds=2) for symbol in symbols},
        as_of=NOW,
        captured_at=NOW,
        session_id="2026-10-01:TEST",
        capture_id="CAPTURE_TEST",
        source_id="SOURCE_TEST",
        capture_verified=True,
        expiry_verified=True,
        timestamp_semantics_verified=True,
        point_in_time_verified=True,
        historical_retrieval=False,
        oi_unit=None,
        oi_unit_verified=False,
        oi_timestamp_verified=False,
        volume_unit=None,
        volume_unit_verified=False,
        volume_timestamp_verified=False,
        premium_unit=None,
        premium_unit_verified=False,
        oi_change_is_absolute_verified=False,
        oi_change_baselines_by_symbol=None,
        underlying_value=100.0,
        underlying_unit=UNITS[market],
        underlying_verified=False,
        underlying_source_id=None,
        underlying_observed_at=None,
        max_age_seconds=60,
    )


def adapted(**overrides):
    args = make_args()
    args.update(overrides)
    return adapt_fyers_option_chain_v1(**args)


def set_result(args, **changes):
    args["provider_result"] = {**args["provider_result"], **changes}
    return args


def change_row(args, index=0, **changes):
    rows = list(args["provider_result"]["rows"])
    rows[index] = {**rows[index], **changes}
    args["provider_result"] = {**args["provider_result"], "rows": tuple(rows)}
    return args


def known_units(args):
    args.update(
        oi_unit="CONTRACTS",
        oi_unit_verified=True,
        oi_timestamp_verified=True,
        volume_unit="CONTRACTS",
        volume_unit_verified=True,
        volume_timestamp_verified=True,
        premium_unit="INR_PER_OPTION_UNIT",
        premium_unit_verified=True,
        underlying_verified=True,
        underlying_source_id="INDEPENDENT_SPOT",
        underlying_observed_at=NOW - timedelta(seconds=2),
    )
    return args


@pytest.mark.parametrize("market", tuple(MARKETS))
def test_all_five_market_native_contracts(market):
    args = make_args(market)
    result = adapt_fyers_option_chain_v1(**args)
    assert result.capture.contract.market == market
    assert result.capture.contract.option_exchange == MARKETS[market][0]
    assert result.validation.call_count == result.validation.put_count == 1
    assert result.validation.complete_pair_count == 1
    assert result.validation.source_capture_sha256 == result.capture.sha256()
    assert result.capture.data_only and not result.live_execution_eligible


@pytest.mark.parametrize("market", tuple(MARKETS))
def test_verified_metrics_for_all_markets_without_fabricating_iv_greeks(market):
    result = adapt_fyers_option_chain_v1(**known_units(make_args(market)))
    readiness = dict(result.validation.readiness)
    assert all(
        readiness[name] == "AVAILABLE"
        for name in (
            "PCR_OI",
            "PCR_VOLUME",
            "MAX_PAIN",
            "OI_CONCENTRATION",
            "OI_SUPPORT_RESISTANCE",
            "QUOTE_SPREAD",
        )
    )
    assert readiness["OI_BUILDUP"] == "UNAVAILABLE"
    assert readiness["IV_SKEW"] == readiness["GREEKS"] == "UNAVAILABLE"
    assert result.validation.status == "PARTIAL"
    assert all(
        x.implied_volatility is None and x.delta is None for x in result.capture.observations
    )


def test_unverified_native_numeric_values_are_never_research_ready():
    result = adapted()
    assert result.validation.status == "PARTIAL"
    assert dict(result.validation.readiness)["PCR_OI"] == "UNAVAILABLE"
    assert dict(result.validation.readiness)["PCR_VOLUME"] == "UNAVAILABLE"
    row = result.capture.observations[0]
    assert row.open_interest is not None and row.oi_unit_verified is False
    assert row.volume is not None and row.volume_unit_verified is False
    assert row.change_in_open_interest is None and row.oi_change_verified is False


def test_absolute_signed_oi_change_needs_verified_baselines():
    args = known_units(make_args())
    args["oi_change_is_absolute_verified"] = True
    args["oi_change_baselines_by_symbol"] = {
        symbol: "BASE:" + symbol for symbol in args["canonical_ids_by_symbol"]
    }
    result = adapt_fyers_option_chain_v1(**args)
    assert dict(result.validation.readiness)["OI_BUILDUP"] == "AVAILABLE"
    assert sorted(x.change_in_open_interest for x in result.capture.observations) == [-10, 5]
    assert all(x.oi_change_baseline_id for x in result.capture.observations)


@pytest.mark.parametrize("flag", ["oi_unit_verified", "oi_timestamp_verified"])
def test_proving_oi_requires_both_flags(flag):
    args = known_units(make_args())
    args[flag] = False
    result = adapt_fyers_option_chain_v1(**args)
    assert dict(result.validation.readiness)["PCR_OI"] == "UNAVAILABLE"


@pytest.mark.parametrize("flag", ["volume_unit_verified", "volume_timestamp_verified"])
def test_proving_volume_requires_both_flags(flag):
    args = known_units(make_args())
    args[flag] = False
    result = adapt_fyers_option_chain_v1(**args)
    assert dict(result.validation.readiness)["PCR_VOLUME"] == "UNAVAILABLE"


@pytest.mark.parametrize(
    "field",
    [
        "provider",
        "underlying_symbol",
        "data_only",
        "live_execution_eligible",
        "request_count",
        "per_contract_depth_requests",
    ],
)
def test_provider_response_cannot_change_authority_identity_or_request_shape(field):
    args = make_args()
    replacement = {
        "provider": "ANGEL",
        "underlying_symbol": "NSE:BANKNIFTY-INDEX",
        "data_only": False,
        "live_execution_eligible": True,
        "request_count": 2,
        "per_contract_depth_requests": 1,
    }[field]
    set_result(args, **{field: replacement})
    with pytest.raises(ValueError):
        adapt_fyers_option_chain_v1(**args)


@pytest.mark.parametrize(
    "field,replacement",
    [
        ("provider_expiry_date", "2026-10-30"),
        ("provider_expiry_date", None),
        ("provider_expiry_timestamp", None),
        ("provider_expiry_timestamp", 0),
        ("provider_expiry_timestamp", True),
        ("expiry_data", ()),
        ("expiry_data", ({"date": EXPIRY.isoformat(), "expiry": 123},)),
        (
            "expiry_data",
            (
                {"date": EXPIRY.isoformat(), "expiry": EPOCH},
                {"date": EXPIRY.isoformat(), "expiry": EPOCH},
            ),
        ),
    ],
)
def test_provider_expiry_provenance_must_agree(field, replacement):
    args = make_args()
    set_result(args, **{field: replacement})
    with pytest.raises(ValueError):
        adapt_fyers_option_chain_v1(**args)


@pytest.mark.parametrize("expiry", [None, "2026-10-30", "1793232001", 123, True])
def test_row_expiry_missing_or_different_fails_closed(expiry):
    args = change_row(make_args(), expiry=expiry)
    with pytest.raises(ValueError):
        adapt_fyers_option_chain_v1(**args)


@pytest.mark.parametrize("expiry", [EXPIRY, EXPIRY.isoformat(), str(EPOCH)])
def test_row_expiry_can_use_exact_verified_epoch_or_iso_date(expiry):
    result = adapt_fyers_option_chain_v1(**change_row(make_args(), expiry=expiry))
    assert result.capture.observations[0].expiry == EXPIRY


@pytest.mark.parametrize(
    "changes",
    [
        {"symbol": "NSE:BANKNIFTY26OCT291000CE"},
        {"symbol": "BSE:SENSEX26OCT291000CE"},
        {"symbol": "NSE:NIFTY26OCT291000PE"},
        {"type": "PUT"},
        {"type": "PE"},
        {"strike": 0},
        {"strike": -1},
        {"strike": True},
        {"strike": float("nan")},
        {"ltp": -1},
        {"ltp": float("inf")},
        {"oi": -1},
        {"volume": -1},
        {"bid": 10.0, "ask": 5.0},
    ],
)
def test_invalid_option_rows_rejected(changes):
    args = change_row(make_args(), **changes)
    with pytest.raises(ValueError):
        adapt_fyers_option_chain_v1(**args)


def test_missing_ce_pe_pair_retained_not_fabricated():
    args = make_args()
    row = args["provider_result"]["rows"][0]
    set_result(args, rows=(row,))
    args["canonical_ids_by_symbol"] = {row["symbol"]: "ONLY_CE"}
    args["observed_at_by_symbol"] = {row["symbol"]: NOW - timedelta(seconds=2)}
    result = adapt_fyers_option_chain_v1(**args)
    assert result.validation.complete_pair_count == 0
    assert result.validation.call_only_count == 1
    assert dict(result.validation.readiness)["PCR_OI"] == "UNAVAILABLE"


def test_duplicate_contract_rows_fail_closed():
    args = make_args()
    row = args["provider_result"]["rows"][0]
    set_result(args, rows=(row, row))
    with pytest.raises(ValueError):
        adapt_fyers_option_chain_v1(**args)


def test_duplicate_strike_side_fails_even_different_symbol():
    args = make_args()
    second = {**args["provider_result"]["rows"][0], "symbol": "NSE:NIFTY26OCT291001CE"}
    set_result(args, rows=(*args["provider_result"]["rows"], second))
    args["canonical_ids_by_symbol"][second["symbol"]] = "SECOND_CE"
    args["observed_at_by_symbol"][second["symbol"]] = NOW - timedelta(seconds=2)
    with pytest.raises(ValueError):
        adapt_fyers_option_chain_v1(**args)


@pytest.mark.parametrize("field", ["canonical_ids_by_symbol", "observed_at_by_symbol"])
def test_incomplete_or_extra_identity_inventory_rejected(field):
    args = make_args()
    args[field] = {
        **args[field],
        "NSE:OTHERCE": "UNUSED" if field == "canonical_ids_by_symbol" else NOW,
    }
    with pytest.raises(ValueError):
        adapt_fyers_option_chain_v1(**args)


def test_colliding_canonical_option_ids_fail_closed():
    args = make_args()
    args["canonical_ids_by_symbol"] = {key: "SAME" for key in args["canonical_ids_by_symbol"]}
    with pytest.raises(ValueError):
        adapt_fyers_option_chain_v1(**args)


@pytest.mark.parametrize("time", [NOW + timedelta(seconds=1), NOW.replace(tzinfo=None)])
def test_invalid_row_observation_time_rejected(time):
    args = make_args()
    symbol = next(iter(args["observed_at_by_symbol"]))
    args["observed_at_by_symbol"][symbol] = time
    with pytest.raises(ValueError):
        adapt_fyers_option_chain_v1(**args)


def test_stale_row_does_not_gain_readiness():
    args = known_units(make_args())
    args["observed_at_by_symbol"] = {
        k: NOW - timedelta(seconds=61) for k in args["observed_at_by_symbol"]
    }
    r = adapt_fyers_option_chain_v1(**args)
    assert r.validation.status == "UNAVAILABLE"
    assert "STALE_OPTION_ROWS" in r.validation.blockers
    assert all(s == "UNAVAILABLE" for _, s in r.validation.readiness)


@pytest.mark.parametrize(
    "flag", ["capture_verified", "expiry_verified", "timestamp_semantics_verified"]
)
def test_unverified_capture_gates_research(flag):
    args = make_args()
    args[flag] = False
    args["point_in_time_verified"] = False
    r = adapt_fyers_option_chain_v1(**args)
    assert r.validation.status == "UNAVAILABLE"
    assert all(s == "UNAVAILABLE" for _, s in r.validation.readiness)


def test_retrospective_download_cannot_claim_historical_point_in_time():
    args = make_args()
    args.update(
        captured_at=NOW + timedelta(hours=1),
        historical_retrieval=True,
        point_in_time_verified=False,
    )
    result = adapt_fyers_option_chain_v1(**args)
    assert result.validation.status == "PARTIAL"
    assert "POINT_IN_TIME_AVAILABILITY_UNPROVEN" in result.validation.warnings
    args["point_in_time_verified"] = True
    with pytest.raises(ValueError):
        adapt_fyers_option_chain_v1(**args)


def test_unmarked_late_capture_fails_closed():
    args = make_args()
    args["captured_at"] = NOW + timedelta(seconds=1)
    with pytest.raises(ValueError):
        adapt_fyers_option_chain_v1(**args)


@pytest.mark.parametrize(
    "field", ["oi_unit_verified", "volume_unit_verified", "premium_unit_verified"]
)
def test_verified_unit_must_be_named(field):
    args = make_args()
    args[field] = True
    with pytest.raises(ValueError):
        adapt_fyers_option_chain_v1(**args)


def test_underlying_requires_separately_timed_source():
    args = make_args()
    args["underlying_verified"] = True
    with pytest.raises(ValueError):
        adapt_fyers_option_chain_v1(**args)
    args["underlying_source_id"] = "SPOT:1"
    args["underlying_observed_at"] = NOW - timedelta(seconds=61)
    with pytest.raises(ValueError):
        adapt_fyers_option_chain_v1(**args)


def test_unverified_oich_is_not_converted_to_signed_absolute_change():
    args = known_units(make_args())
    r = adapt_fyers_option_chain_v1(**args)
    assert all(row.change_in_open_interest is None for row in r.capture.observations)
    assert dict(r.validation.readiness)["OI_BUILDUP"] == "UNAVAILABLE"


def test_verified_oich_requires_complete_baseline_inventory():
    args = known_units(make_args())
    args["oi_change_is_absolute_verified"] = True
    args["oi_change_baselines_by_symbol"] = {
        next(iter(args["canonical_ids_by_symbol"])): "ONLY_ONE"
    }
    with pytest.raises(ValueError):
        adapt_fyers_option_chain_v1(**args)


def test_zero_volume_and_oi_are_real_zero_values():
    args = known_units(make_args())
    args = change_row(args, oi=0, volume=0)
    result = adapt_fyers_option_chain_v1(**args)
    assert result.capture.observations[0].open_interest == 0
    assert result.capture.observations[0].volume == 0
    assert dict(result.validation.readiness)["PCR_OI"] == "AVAILABLE"


def test_missing_oi_not_replaced_by_zero():
    args = known_units(make_args())
    args = change_row(args, oi=None)
    result = adapt_fyers_option_chain_v1(**args)
    assert result.capture.observations[0].open_interest is None
    assert dict(result.validation.readiness)["PCR_OI"] == "UNAVAILABLE"


def test_mixed_order_deterministic_hash_and_row_order():
    args = make_args()
    first = adapt_fyers_option_chain_v1(**args)
    set_result(args, rows=tuple(reversed(args["provider_result"]["rows"])))
    second = adapt_fyers_option_chain_v1(**args)
    assert first.capture.sha256() == second.capture.sha256()
    assert first.validation.sha256() == second.validation.sha256()
    assert tuple(row.option_type for row in second.capture.observations) == ("CE", "PE")


def test_payload_hash_changes_with_provider_oi():
    a = adapted()
    b = adapted(provider_result=change_row(make_args(), oi=201)["provider_result"])
    assert a.source_payload_sha256 != b.source_payload_sha256
    assert a.capture.sha256() != b.capture.sha256()


@pytest.mark.parametrize(
    "field",
    [
        "execution_authority",
        "risk_authority",
        "position_authority",
        "certification_authority",
        "live_execution_eligible",
    ],
)
def test_adapter_result_cannot_acquire_any_authority(field):
    result = adapted()
    with pytest.raises(ValueError):
        replace(result, **{field: True})


def test_capture_result_is_frozen():
    r = adapted()
    with pytest.raises(FrozenInstanceError):
        r.source_payload_sha256 = "fake"


def test_mcx_same_day_conservatively_blocked():
    args = make_args("GOLDM")
    args["contract"] = replace(
        args["contract"], expiry=NOW.astimezone(timezone(timedelta(hours=5, minutes=30))).date()
    )
    # Provider expiry metadata must follow the same contract date; use exact date in rows.
    exp = args["contract"].expiry.isoformat()
    same_day_epoch = int(datetime(2026, 10, 1, tzinfo=UTC).timestamp())
    set_result(
        args,
        provider_expiry_date=exp,
        provider_expiry_timestamp=same_day_epoch,
        expiry_data=({"date": exp, "expiry": same_day_epoch},),
    )
    rows = tuple({**row, "expiry": exp} for row in args["provider_result"]["rows"])
    set_result(args, rows=rows)
    r = adapt_fyers_option_chain_v1(**args)
    assert "MCX_SAME_DAY_EXPIRY_REQUIRES_SEPARATE_REVIEW" in r.validation.blockers
    assert r.validation.status == "UNAVAILABLE"


def test_inconsistent_expiry_epoch_calendar_date_rejected():
    args = make_args()
    set_result(
        args,
        provider_expiry_timestamp=1792627200,
        expiry_data=({"date": EXPIRY.isoformat(), "expiry": 1792627200},),
    )
    with pytest.raises(ValueError):
        adapt_fyers_option_chain_v1(**args)


@pytest.mark.parametrize(
    "field,value", [("request_count", True), ("per_contract_depth_requests", False)]
)
def test_provider_request_counters_must_be_exact_integers(field, value):
    args = make_args()
    set_result(args, **{field: value})
    with pytest.raises(ValueError):
        adapt_fyers_option_chain_v1(**args)


def test_unexpected_non_normalized_provider_field_rejected():
    args = change_row(make_args(), password="NOT_A_VALID_PROVIDER_FIELD")
    with pytest.raises(ValueError):
        adapt_fyers_option_chain_v1(**args)


@pytest.mark.parametrize("bad", [0, float("nan"), -3, True])
def test_invalid_freshness_budget_rejected(bad):
    args = make_args()
    args["max_age_seconds"] = bad
    with pytest.raises(ValueError):
        adapt_fyers_option_chain_v1(**args)
