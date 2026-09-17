"""F8 - focused tests for the FYERS five-market instrument resolver.

Offline. Deterministic. No auth, no network, no order APIs.

Run:  pytest -q tests/test_f8_fyers_five_market_resolver_v2.py
"""
from __future__ import annotations
import unittest

from datetime import date, datetime, timedelta, timezone

import pytest

from services.broker.fyers_five_market_resolver_v2 import (
    FyersFiveMarketInstrumentResolverV2,
    FyersResolutionError,
)
from services.broker.fyers_symbol_master_v2 import (
    FyersSymbolMasterIndexV2,
    parse_master_record_v2,
)


# ---------- Fakes ----------

class _FakeMasterStore:
    def __init__(self, by_segment: dict[str, list[dict]]) -> None:
        self._idx = {
            seg: FyersSymbolMasterIndexV2.from_rows(rows, seg)
            for seg, rows in by_segment.items()
        }

    def get_index(self, segment):
        if segment not in self._idx:
            raise RuntimeError("segment not cached: " + segment)
        return self._idx[segment]


class _FakeFyersClient:
    def __init__(self, futures_chains=None):
        self._fc = futures_chains or {}
        self.calls = []

    def futures_chain(self, data):
        sym = data.get("symbol")
        self.calls.append(("futures_chain", sym))
        if sym in self._fc:
            return self._fc[sym]
        return {"s": "error", "message": "no data for " + str(sym)}

    def optionchain(self, data):
        self.calls.append(("optionchain", data.get("symbol")))
        return {"s": "error", "message": "not used"}

    def expiry_dates(self, data):
        self.calls.append(("expiry_dates", data.get("symbol")))
        return {"s": "error", "message": "not used"}


def _clock_fixed(dt):
    return lambda: dt


# ---------- Master fixtures ----------

NSE_CM_ROWS = [
    {"symbol": "NSE:NIFTY50-INDEX", "exch": "NSE", "segment": "NSE_CM",
     "instrument_type": "INDEX", "fyToken": "99926000"},
]

BSE_CM_ROWS = [
    {"symbol": "BSE:SENSEX-INDEX", "exch": "BSE", "segment": "BSE_CM",
     "instrument_type": "INDEX", "fyToken": "1"},
]

NSE_FO_ROWS = [
    {"symbol": "NSE:NIFTY26SEPFUT", "exch": "NSE", "segment": "NSE_FO",
     "instrument_type": "FUT", "underlying_symbol": "NIFTY",
     "expiry": "2026-09-30", "fyToken": "N1", "lot_size": "50",
     "tick_size": "0.05"},
    {"symbol": "NSE:NIFTY26OCTFUT", "exch": "NSE", "segment": "NSE_FO",
     "instrument_type": "FUT", "underlying_symbol": "NIFTY",
     "expiry": "2026-10-28", "fyToken": "N2", "lot_size": "50",
     "tick_size": "0.05"},
    {"symbol": "NSE:NIFTY26SEP25000CE", "exch": "NSE", "segment": "NSE_FO",
     "instrument_type": "OPT", "underlying_symbol": "NIFTY",
     "expiry": "2026-09-30", "strike": "25000", "option_type": "CE",
     "fyToken": "NC1", "lot_size": "50", "tick_size": "0.05"},
    {"symbol": "NSE:NIFTY26SEP25000PE", "exch": "NSE", "segment": "NSE_FO",
     "instrument_type": "OPT", "underlying_symbol": "NIFTY",
     "expiry": "2026-09-30", "strike": "25000", "option_type": "PE",
     "fyToken": "NP1", "lot_size": "50", "tick_size": "0.05"},
    # F8R4 same-day expiry (2026-09-17)
    {"symbol": "NSE:NIFTY26SEP1725000CE", "exch": "NSE", "segment": "NSE_FO",
     "instrument_type": "OPT", "underlying_symbol": "NIFTY",
     "expiry": "2026-09-17", "strike": "25000", "option_type": "CE",
     "fyToken": "NS17C", "lot_size": "50", "tick_size": "0.05"},
    {"symbol": "NSE:NIFTY26SEP1725000PE", "exch": "NSE", "segment": "NSE_FO",
     "instrument_type": "OPT", "underlying_symbol": "NIFTY",
     "expiry": "2026-09-17", "strike": "25000", "option_type": "PE",
     "fyToken": "NS17P", "lot_size": "50", "tick_size": "0.05"},
]

# BSE SENSEX futures deliberately have blank optType - must still resolve.
BSE_FO_ROWS = [
    {"symbol": "BSE:SENSEX26SEPFUT", "exch": "BSE", "segment": "BSE_FO",
     "instrument_type": "FUT", "underlying_symbol": "SENSEX",
     "expiry": "2026-09-30", "fyToken": "S1", "lot_size": "20",
     "tick_size": "0.05", "optType": ""},
    {"symbol": "BSE:SENSEX26SEP74000CE", "exch": "BSE", "segment": "BSE_FO",
     "instrument_type": "OPT", "underlying_symbol": "SENSEX",
     "expiry": "2026-09-30", "strike": "74000", "option_type": "CE",
     "fyToken": "SC1", "lot_size": "20", "tick_size": "0.05"},
    {"symbol": "BSE:SENSEX26SEP74000PE", "exch": "BSE", "segment": "BSE_FO",
     "instrument_type": "OPT", "underlying_symbol": "SENSEX",
     "expiry": "2026-09-30", "strike": "74000", "option_type": "PE",
     "fyToken": "SP1", "lot_size": "20", "tick_size": "0.05"},
    # F8R4 same-day expiry (2026-09-17)
    {"symbol": "BSE:SENSEX26SEP1774000CE", "exch": "BSE", "segment": "BSE_FO",
     "instrument_type": "OPT", "underlying_symbol": "SENSEX",
     "expiry": "2026-09-17", "strike": "74000", "option_type": "CE",
     "fyToken": "SS17C", "lot_size": "20", "tick_size": "0.05"},
    {"symbol": "BSE:SENSEX26SEP1774000PE", "exch": "BSE", "segment": "BSE_FO",
     "instrument_type": "OPT", "underlying_symbol": "SENSEX",
     "expiry": "2026-09-17", "strike": "74000", "option_type": "PE",
     "fyToken": "SS17P", "lot_size": "20", "tick_size": "0.05"},
]

# MCX master rows: futures without optType at all. Must still classify.
MCX_COM_ROWS = [
    # CRUDEOILM product root
    {"symbol": "MCX:CRUDEOILM", "exch": "MCX", "segment": "MCX_COM",
     "instrument_type": "COMMODITY", "underlying_symbol": "CRUDEOILM"},
    {"symbol": "MCX:CRUDEOILM26SEPFUT", "exch": "MCX", "segment": "MCX_COM",
     "instrument_type": "FUT", "underlying_symbol": "CRUDEOILM",
     "expiry": "2026-09-30", "fyToken": "C1", "lot_size": "10",
     "tick_size": "0.10"},
    {"symbol": "MCX:CRUDEOILM26OCTFUT", "exch": "MCX", "segment": "MCX_COM",
     "instrument_type": "FUT", "underlying_symbol": "CRUDEOILM",
     "expiry": "2026-10-31", "fyToken": "C2", "lot_size": "10",
     "tick_size": "0.10"},
    # GOLDM
    {"symbol": "MCX:GOLDM", "exch": "MCX", "segment": "MCX_COM",
     "instrument_type": "COMMODITY", "underlying_symbol": "GOLDM"},
    {"symbol": "MCX:GOLDM26OCTFUT", "exch": "MCX", "segment": "MCX_COM",
     "instrument_type": "FUT", "underlying_symbol": "GOLDM",
     "expiry": "2026-10-31", "fyToken": "G1", "lot_size": "1",
     "tick_size": "1.00"},
    # SILVERM
    {"symbol": "MCX:SILVERM", "exch": "MCX", "segment": "MCX_COM",
     "instrument_type": "COMMODITY", "underlying_symbol": "SILVERM"},
    {"symbol": "MCX:SILVERM26SEPFUT", "exch": "MCX", "segment": "MCX_COM",
     "instrument_type": "FUT", "underlying_symbol": "SILVERM",
     "expiry": "2026-09-30", "fyToken": "N1", "lot_size": "1",
     "tick_size": "0.10"},
    # Expired MCX future (must never be chosen)
    {"symbol": "MCX:CRUDEOILM26AUGFUT", "exch": "MCX", "segment": "MCX_COM",
     "instrument_type": "FUT", "underlying_symbol": "CRUDEOILM",
     "expiry": "2026-08-31", "fyToken": "CX", "lot_size": "10",
     "tick_size": "0.10"},
]


def _store_all():
    return _FakeMasterStore({
        "NSE_CM": NSE_CM_ROWS,
        "NSE_FO": NSE_FO_ROWS,
        "BSE_CM": BSE_CM_ROWS,
        "BSE_FO": BSE_FO_ROWS,
        "MCX_COM": MCX_COM_ROWS,
    })


def _fixed_as_of(y=2026, m=9, d=15):
    return datetime(y, m, d, 9, 15, tzinfo=timezone.utc)


def _resolver(fc=None, as_of=None):
    return FyersFiveMarketInstrumentResolverV2(
        data_client=_FakeFyersClient(fc or {}),
        master_store=_store_all(),
        clock=_clock_fixed(as_of or _fixed_as_of()),
    )


# ---------- Parser-level tests ----------

class TestMasterParser:
    def test_bse_sensex_futures_with_blank_optype_still_classify(self):
        rec = parse_master_record_v2(
            BSE_FO_ROWS[0], default_segment="BSE_FO"
        )
        assert rec is not None
        assert rec.instrument_kind == "FUTURE"

    def test_mcx_futures_without_optype_classify(self):
        rec = parse_master_record_v2(
            MCX_COM_ROWS[1], default_segment="MCX_COM"
        )
        assert rec is not None
        assert rec.instrument_kind == "FUTURE"
        assert rec.underlying_symbol == "CRUDEOILM"

    def test_malformed_row_returns_none(self):
        assert parse_master_record_v2({"x": "y"}, default_segment="NSE_FO") is None


# ---------- Underlying ----------

class TestUnderlying:
    def test_nifty_underlying(self):
        r = _resolver().resolve(
            market_symbol="NIFTY", instrument_type="UNDERLYING",
            as_of=_fixed_as_of(),
        )
        assert r["provider"] == "FYERS"
        assert r["provider_symbol"] == "NSE:NIFTY50-INDEX"
        assert r["provider_exchange"] == "NSE"
        assert r["instrument_type"] == "UNDERLYING"
        assert r["data_only"] is True
        assert r["execution_mode"] == "PAPER"
        assert r["live_execution_eligible"] is False
        assert r["contract_metadata_status"] == "NOT_APPLICABLE"

    def test_sensex_underlying(self):
        r = _resolver().resolve(
            market_symbol="SENSEX", instrument_type="UNDERLYING",
            as_of=_fixed_as_of(),
        )
        assert r["provider_symbol"] == "BSE:SENSEX-INDEX"
        assert r["provider_exchange"] == "BSE"

    def test_crudeoilm_underlying_from_master(self):
        r = _resolver().resolve(
            market_symbol="CRUDEOILM", instrument_type="UNDERLYING",
            as_of=_fixed_as_of(),
        )
        assert r["provider_symbol"] == "MCX:CRUDEOILM"
        assert r["instrument_type"] == "UNDERLYING"


# ---------- Futures ----------

class TestFutures:
    def test_nifty_front_future(self):
        fc = {
            "NSE:NIFTY50-INDEX": {"s": "ok", "d": [
                {"symbol": "NSE:NIFTY26SEPFUT", "expiry": "2026-09-30",
                 "fyToken": "N1", "lot_size": 50, "tick_size": 0.05},
                {"symbol": "NSE:NIFTY26OCTFUT", "expiry": "2026-10-28",
                 "fyToken": "N2", "lot_size": 50, "tick_size": 0.05},
            ]},
        }
        r = _resolver(fc).resolve(
            market_symbol="NIFTY", instrument_type="FUTURE",
            as_of=_fixed_as_of(),
        )
        assert r["provider_symbol"] == "NSE:NIFTY26SEPFUT"
        assert r["expiry"] == "2026-09-30"
        assert r["lot_size"] == 50
        assert r["contract_metadata_status"] == "VERIFIED"

    def test_sensex_front_future(self):
        fc = {
            "BSE:SENSEX-INDEX": {"s": "ok", "d": [
                {"symbol": "BSE:SENSEX26SEPFUT", "expiry": "2026-09-30",
                 "fyToken": "S1", "lot_size": 20, "tick_size": 0.05},
            ]},
        }
        r = _resolver(fc).resolve(
            market_symbol="SENSEX", instrument_type="FUTURE",
            as_of=_fixed_as_of(),
        )
        assert r["provider_symbol"] == "BSE:SENSEX26SEPFUT"

    def test_crudeoilm_front_future_from_master(self):
        r = _resolver().resolve(
            market_symbol="CRUDEOILM", instrument_type="FUTURE",
            as_of=_fixed_as_of(),
        )
        assert r["provider_symbol"] == "MCX:CRUDEOILM26SEPFUT"
        assert r["expiry"] == "2026-09-30"
        assert r["lot_size"] == 10

    def test_goldm_front_future_from_master(self):
        r = _resolver().resolve(
            market_symbol="GOLDM", instrument_type="FUTURE",
            as_of=_fixed_as_of(),
        )
        assert r["provider_symbol"] == "MCX:GOLDM26OCTFUT"
        assert r["expiry"] == "2026-10-31"

    def test_silverm_front_future_from_master(self):
        r = _resolver().resolve(
            market_symbol="SILVERM", instrument_type="FUTURE",
            as_of=_fixed_as_of(),
        )
        assert r["provider_symbol"] == "MCX:SILVERM26SEPFUT"

    def test_nifty_requested_future_expiry(self):
        fc = {
            "NSE:NIFTY50-INDEX": {"s": "ok", "d": [
                {"symbol": "NSE:NIFTY26SEPFUT", "expiry": "2026-09-30",
                 "fyToken": "N1", "lot_size": 50, "tick_size": 0.05},
                {"symbol": "NSE:NIFTY26OCTFUT", "expiry": "2026-10-28",
                 "fyToken": "N2", "lot_size": 50, "tick_size": 0.05},
            ]},
        }
        r = _resolver(fc).resolve(
            market_symbol="NIFTY", instrument_type="FUTURE",
            as_of=_fixed_as_of(), expiry=date(2026, 10, 28),
        )
        assert r["provider_symbol"] == "NSE:NIFTY26OCTFUT"

    def test_sensex_requested_future_expiry(self):
        fc = {
            "BSE:SENSEX-INDEX": {"s": "ok", "d": [
                {"symbol": "BSE:SENSEX26SEPFUT", "expiry": "2026-09-30",
                 "fyToken": "S1", "lot_size": 20, "tick_size": 0.05},
            ]},
        }
        r = _resolver(fc).resolve(
            market_symbol="SENSEX", instrument_type="FUTURE",
            as_of=_fixed_as_of(), expiry=date(2026, 9, 30),
        )
        assert r["provider_symbol"] == "BSE:SENSEX26SEPFUT"

    def test_expired_future_rejection_mcx(self):
        # Ask for CRUDEOILM with as_of AFTER the front future expiry
        r_res = _resolver()
        with pytest.raises(FyersResolutionError):
            r_res.resolve(
                market_symbol="CRUDEOILM", instrument_type="FUTURE",
                as_of=datetime(2026, 12, 1, 9, 15, tzinfo=timezone.utc),
            )

    def test_expired_future_rejection_nifty(self):
        # as_of after the only provided future expiry
        fc = {"NSE:NIFTY50-INDEX": {"s": "ok", "d": [
            {"symbol": "NSE:NIFTY26SEPFUT", "expiry": "2026-09-30",
             "fyToken": "N1", "lot_size": 50, "tick_size": 0.05},
        ]}}
        with pytest.raises(FyersResolutionError):
            _resolver(fc).resolve(
                market_symbol="NIFTY", instrument_type="FUTURE",
                as_of=datetime(2026, 10, 1, 9, 15, tzinfo=timezone.utc),
            )


# ---------- Options ----------

class TestOptions:
    def test_nifty_ce_exact(self):
        r = _resolver().resolve(
            market_symbol="NIFTY", instrument_type="OPTION",
            as_of=_fixed_as_of(), expiry=date(2026, 9, 30),
            strike=25000.0, option_type="CE",
        )
        assert r["provider_symbol"] == "NSE:NIFTY26SEP25000CE"
        assert r["option_type"] == "CE"
        assert r["strike"] == 25000.0

    def test_nifty_pe_exact(self):
        r = _resolver().resolve(
            market_symbol="NIFTY", instrument_type="OPTION",
            as_of=_fixed_as_of(), expiry=date(2026, 9, 30),
            strike=25000.0, option_type="PE",
        )
        assert r["provider_symbol"] == "NSE:NIFTY26SEP25000PE"

    def test_sensex_ce_exact(self):
        r = _resolver().resolve(
            market_symbol="SENSEX", instrument_type="OPTION",
            as_of=_fixed_as_of(), expiry=date(2026, 9, 30),
            strike=74000.0, option_type="CE",
        )
        assert r["provider_symbol"] == "BSE:SENSEX26SEP74000CE"

    def test_sensex_pe_exact(self):
        r = _resolver().resolve(
            market_symbol="SENSEX", instrument_type="OPTION",
            as_of=_fixed_as_of(), expiry=date(2026, 9, 30),
            strike=74000.0, option_type="PE",
        )
        assert r["provider_symbol"] == "BSE:SENSEX26SEP74000PE"

    def test_expired_option_rejection(self):
        with pytest.raises(FyersResolutionError):
            _resolver().resolve(
                market_symbol="NIFTY", instrument_type="OPTION",
                as_of=_fixed_as_of(), expiry=date(2026, 8, 31),
                strike=25000.0, option_type="CE",
            )

    def test_unknown_strike_rejection(self):
        with pytest.raises(FyersResolutionError):
            _resolver().resolve(
                market_symbol="NIFTY", instrument_type="OPTION",
                as_of=_fixed_as_of(), expiry=date(2026, 9, 30),
                strike=99999.0, option_type="CE",
            )

    def test_invalid_option_type_rejection(self):
        with pytest.raises(FyersResolutionError):
            _resolver().resolve(
                market_symbol="NIFTY", instrument_type="OPTION",
                as_of=_fixed_as_of(), expiry=date(2026, 9, 30),
                strike=25000.0, option_type="XX",
            )


# ---------- Rejections / fail-closed ----------

class TestFailClosed:
    def test_unknown_market_rejection(self):
        with pytest.raises(Exception):
            _resolver().resolve(
                market_symbol="BANKNIFTY", instrument_type="UNDERLYING",
                as_of=_fixed_as_of(),
            )

    def test_unsupported_instrument_type(self):
        with pytest.raises(FyersResolutionError):
            _resolver().resolve(
                market_symbol="NIFTY", instrument_type="SWAP",
                as_of=_fixed_as_of(),
            )

    def test_ambiguous_option_identity(self):
        # Add two CE records for the same (expiry, strike, opt_type).
        store = _store_all()
        extra_row = {
            "symbol": "NSE:NIFTY26SEP25000CE_ALT", "exch": "NSE",
            "segment": "NSE_FO", "instrument_type": "OPT",
            "underlying_symbol": "NIFTY", "expiry": "2026-09-30",
            "strike": "25000", "option_type": "CE",
            "fyToken": "NC1b", "lot_size": "50", "tick_size": "0.05",
        }
        store._idx["NSE_FO"] = FyersSymbolMasterIndexV2.from_rows(
            NSE_FO_ROWS + [extra_row], "NSE_FO"
        )
        r = FyersFiveMarketInstrumentResolverV2(
            data_client=_FakeFyersClient(),
            master_store=store,
            clock=_clock_fixed(_fixed_as_of()),
        )
        with pytest.raises(FyersResolutionError):
            r.resolve(
                market_symbol="NIFTY", instrument_type="OPTION",
                as_of=_fixed_as_of(), expiry=date(2026, 9, 30),
                strike=25000.0, option_type="CE",
            )

    def test_missing_master_fails_closed(self):
        class _EmptyStore:
            def get_index(self, segment):
                raise RuntimeError("master not cached")
        r = FyersFiveMarketInstrumentResolverV2(
            data_client=_FakeFyersClient(),
            master_store=_EmptyStore(),
            clock=_clock_fixed(_fixed_as_of()),
        )
        with pytest.raises(FyersResolutionError):
            r.resolve(
                market_symbol="CRUDEOILM", instrument_type="FUTURE",
                as_of=_fixed_as_of(),
            )

    def test_naive_as_of_rejected(self):
        with pytest.raises(FyersResolutionError):
            _resolver().resolve(
                market_symbol="NIFTY", instrument_type="UNDERLYING",
                as_of=datetime(2026, 9, 15, 9, 15),
            )

    def test_futures_chain_missing_symbol_fails_closed(self):
        with pytest.raises(FyersResolutionError):
            _resolver().resolve(
                market_symbol="NIFTY", instrument_type="FUTURE",
                as_of=_fixed_as_of(),
            )


# ---------- Safety / contract ----------

class TestContractAndSafety:
    def test_to_provider_instrument_shape(self):
        r = _resolver().resolve(
            market_symbol="NIFTY", instrument_type="UNDERLYING",
            as_of=_fixed_as_of(),
        )
        for k in (
            "resolution_id", "provider", "market_symbol", "market_type",
            "underlying_exchange", "derivative_exchange", "instrument_type",
            "canonical_instrument_id", "provider_symbol", "provider_exchange",
            "provider_token", "expiry", "strike", "option_type",
            "lot_size", "tick_size", "contract_metadata_status",
            "metadata_source", "resolved_at", "data_only", "execution_mode",
            "live_execution_eligible", "warnings", "schema_version",
        ):
            assert k in r

    def test_safety_flags_all_underlying_types(self):
        cases = [
            ("NIFTY", "UNDERLYING", None, None, None),
            ("SENSEX", "UNDERLYING", None, None, None),
            ("CRUDEOILM", "UNDERLYING", None, None, None),
            ("CRUDEOILM", "FUTURE", None, None, None),
            ("SILVERM", "FUTURE", None, None, None),
        ]
        for ms, it, ex, st, ot in cases:
            r = _resolver().resolve(
                market_symbol=ms, instrument_type=it,
                as_of=_fixed_as_of(), expiry=ex, strike=st, option_type=ot,
            )
            assert r["data_only"] is True
            assert r["execution_mode"] == "PAPER"
            assert r["live_execution_eligible"] is False
            assert r["provider"] == "FYERS"

    def test_resolution_id_is_deterministic(self):
        a = _resolver().resolve(
            market_symbol="NIFTY", instrument_type="UNDERLYING",
            as_of=_fixed_as_of(),
        )["resolution_id"]
        b = _resolver().resolve(
            market_symbol="NIFTY", instrument_type="UNDERLYING",
            as_of=_fixed_as_of(),
        )["resolution_id"]
        assert a == b

    def test_provider_token_absent_is_acceptable(self):
        # Underlying has no token; resolver must still succeed.
        r = _resolver().resolve(
            market_symbol="NIFTY", instrument_type="UNDERLYING",
            as_of=_fixed_as_of(),
        )
        assert r["provider_token"] is None

    def test_provider_token_present_when_available(self):
        r = _resolver().resolve(
            market_symbol="CRUDEOILM", instrument_type="FUTURE",
            as_of=_fixed_as_of(),
        )
        assert r["provider_token"] == "C1"


class TestSameDayExpiryValidity(unittest.TestCase):
    """F8R4 - same-day expiry eligibility must be timestamp-aware."""

    IST = timezone(timedelta(hours=5, minutes=30))

    def _resolve(self, market_symbol, instrument_type, as_of, **kwargs):
        return _resolver().resolve(
            market_symbol=market_symbol,
            instrument_type=instrument_type,
            as_of=as_of,
            **kwargs,
        )

    def test_01_sensex_same_day_option_pre_close_eligible(self):
        as_of = datetime(2026, 9, 17, 10, 0, tzinfo=self.IST)
        r = self._resolve(
            "SENSEX", "OPTION", as_of,
            expiry=date(2026, 9, 17), strike=74000.0, option_type="CE",
        )
        self.assertEqual(r["provider_symbol"], "BSE:SENSEX26SEP1774000CE")
        self.assertEqual(r["expiry"], "2026-09-17")
        self.assertIs(r["data_only"], True)
        self.assertEqual(r["execution_mode"], "PAPER")
        self.assertIs(r["live_execution_eligible"], False)

    def test_02a_sensex_same_day_option_post_close_rejected(self):
        as_of = datetime(2026, 9, 17, 16, 0, tzinfo=self.IST)
        with self.assertRaises(FyersResolutionError):
            self._resolve(
                "SENSEX", "OPTION", as_of,
                expiry=date(2026, 9, 17), strike=74000.0, option_type="CE",
            )

    def test_02b_sensex_next_expiry_option_post_close_resolvable(self):
        as_of = datetime(2026, 9, 17, 16, 0, tzinfo=self.IST)
        r = self._resolve(
            "SENSEX", "OPTION", as_of,
            expiry=date(2026, 9, 30), strike=74000.0, option_type="CE",
        )
        self.assertEqual(r["provider_symbol"], "BSE:SENSEX26SEP74000CE")

    def test_03_nifty_same_day_option_pre_close_eligible(self):
        as_of = datetime(2026, 9, 17, 10, 0, tzinfo=self.IST)
        r = self._resolve(
            "NIFTY", "OPTION", as_of,
            expiry=date(2026, 9, 17), strike=25000.0, option_type="CE",
        )
        self.assertEqual(r["provider_symbol"], "NSE:NIFTY26SEP1725000CE")
        self.assertEqual(r["expiry"], "2026-09-17")

    def test_04_nifty_same_day_option_post_close_rejected(self):
        as_of = datetime(2026, 9, 17, 16, 0, tzinfo=self.IST)
        with self.assertRaises(FyersResolutionError):
            self._resolve(
                "NIFTY", "OPTION", as_of,
                expiry=date(2026, 9, 17), strike=25000.0, option_type="CE",
            )

    def test_05_same_day_future_pre_close_valid(self):
        ist = self.IST
        fc = {"NSE:NIFTY50-INDEX": {"s": "ok", "data": [
            {"symbol": "NSE:NIFTY26SEP17FUT",
             "expiry": int(datetime(2026, 9, 17, 0, 0, tzinfo=ist).timestamp()),
             "fyToken": "NF1", "lp": 25000},
            {"symbol": "NSE:NIFTY26SEP29FUT",
             "expiry": int(datetime(2026, 9, 29, 0, 0, tzinfo=ist).timestamp()),
             "fyToken": "NF2", "lp": 25100},
        ]}}
        as_of = datetime(2026, 9, 17, 10, 0, tzinfo=ist)
        r = _resolver(fc).resolve(
            market_symbol="NIFTY", instrument_type="FUTURE", as_of=as_of,
        )
        self.assertEqual(r["provider_symbol"], "NSE:NIFTY26SEP17FUT")
        self.assertEqual(r["expiry"], "2026-09-17")

    def test_06_same_day_future_post_close_falls_through(self):
        ist = self.IST
        fc = {"NSE:NIFTY50-INDEX": {"s": "ok", "data": [
            {"symbol": "NSE:NIFTY26SEP17FUT",
             "expiry": int(datetime(2026, 9, 17, 0, 0, tzinfo=ist).timestamp()),
             "fyToken": "NF1", "lp": 25000},
            {"symbol": "NSE:NIFTY26SEP29FUT",
             "expiry": int(datetime(2026, 9, 29, 0, 0, tzinfo=ist).timestamp()),
             "fyToken": "NF2", "lp": 25100},
        ]}}
        as_of = datetime(2026, 9, 17, 16, 0, tzinfo=ist)
        r = _resolver(fc).resolve(
            market_symbol="NIFTY", instrument_type="FUTURE", as_of=as_of,
        )
        self.assertEqual(r["provider_symbol"], "NSE:NIFTY26SEP29FUT")
        self.assertEqual(r["expiry"], "2026-09-29")

    def test_07_previous_date_expiry_rejected(self):
        as_of = datetime(2026, 9, 17, 10, 0, tzinfo=self.IST)
        with self.assertRaises(FyersResolutionError):
            self._resolve(
                "SENSEX", "OPTION", as_of,
                expiry=date(2026, 9, 16), strike=74000.0, option_type="CE",
            )

    def test_08_future_expiry_unchanged(self):
        as_of = datetime(2026, 9, 17, 10, 0, tzinfo=self.IST)
        r = self._resolve(
            "SENSEX", "OPTION", as_of,
            expiry=date(2026, 9, 30), strike=74000.0, option_type="CE",
        )
        self.assertEqual(r["provider_symbol"], "BSE:SENSEX26SEP74000CE")

    def test_09_utc_pre_close_matches_ist_pre_close(self):
        ist_dt = datetime(2026, 9, 17, 10, 0, tzinfo=self.IST)
        utc_dt = ist_dt.astimezone(timezone.utc)
        r = self._resolve(
            "SENSEX", "OPTION", utc_dt,
            expiry=date(2026, 9, 17), strike=74000.0, option_type="CE",
        )
        self.assertEqual(r["expiry"], "2026-09-17")

    def test_10_utc_post_close_matches_ist_post_close(self):
        ist_dt = datetime(2026, 9, 17, 16, 0, tzinfo=self.IST)
        utc_dt = ist_dt.astimezone(timezone.utc)
        with self.assertRaises(FyersResolutionError):
            self._resolve(
                "SENSEX", "OPTION", utc_dt,
                expiry=date(2026, 9, 17), strike=74000.0, option_type="CE",
            )

    def test_11_naive_datetime_fails_closed(self):
        with self.assertRaises(FyersResolutionError):
            self._resolve(
                "SENSEX", "OPTION", datetime(2026, 9, 17, 10, 0),
                expiry=date(2026, 9, 17), strike=74000.0, option_type="CE",
            )

    def test_13a_mcx_same_day_future_fails_closed_at_resolver(self):
        store = _FakeMasterStore({
            "NSE_CM": NSE_CM_ROWS, "NSE_FO": NSE_FO_ROWS,
            "BSE_CM": BSE_CM_ROWS, "BSE_FO": BSE_FO_ROWS,
            "MCX_COM": MCX_COM_ROWS + [{
                "symbol": "MCX:CRUDEOILM26SEP17FUT",
                "exch": "MCX", "segment": "MCX_COM",
                "instrument_type": "FUT", "underlying_symbol": "CRUDEOILM",
                "expiry": "2026-09-17", "fyToken": "CX17",
                "lot_size": "10", "tick_size": "0.10",
            }],
        })
        r = FyersFiveMarketInstrumentResolverV2(
            data_client=_FakeFyersClient(),
            master_store=store,
            clock=_clock_fixed(datetime(2026, 9, 17, 5, 0, tzinfo=timezone.utc)),
        )
        result = r.resolve(
            market_symbol="CRUDEOILM", instrument_type="FUTURE",
            as_of=datetime(2026, 9, 17, 5, 0, tzinfo=timezone.utc),
        )
        self.assertNotEqual(result["provider_symbol"],
                            "MCX:CRUDEOILM26SEP17FUT")
        self.assertEqual(result["provider_symbol"],
                         "MCX:CRUDEOILM26SEPFUT")
        self.assertEqual(result["expiry"], "2026-09-30")

    def test_13b_mcx_helper_fails_closed_for_same_day(self):
        from services.broker.fyers_five_market_resolver_v2 import (
            _is_expiry_tradable,
        )
        as_of = datetime(2026, 9, 17, 10, 0, tzinfo=timezone.utc)
        for mk in ("CRUDEOILM", "GOLDM", "SILVERM"):
            self.assertFalse(
                _is_expiry_tradable(date(2026, 9, 17), as_of, mk),
                "MCX same-day must fail closed for " + mk,
            )
