from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from pytest import mark, raises

from services.x3.multi_timeframe_v1 import build_x3_multi_timeframe_v1
from services.x3.pipeline_v1 import build_x3_timeframe_v1
from services.x3.research_view_v1 import build_x23_research_view_v1
from services.x3.series_validation_v1 import admitted_candles_v1

BASE = datetime(2026, 9, 18, 9, 0, tzinfo=UTC)


@dataclass(frozen=True)
class Candle:
    candle_id: str
    start_at: datetime
    end_at: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float
    is_complete: bool = True

    @property
    def provenance(self):
        return SimpleNamespace(provider="FYERS")


def series(timeframe="5m", n=60, volume=100.0, *, increment=0.1):
    spacing = {"5m": 5, "15m": 15, "1h": 60, "1d": 1440}[timeframe]
    candles = []
    for i in range(n):
        close = 100 + i * increment
        start = BASE + timedelta(minutes=spacing * i)
        candles.append(
            Candle(
                f"c{i}",
                start,
                start + timedelta(minutes=spacing),
                close - 0.1,
                close + 1,
                close - 1,
                close,
                volume,
            )
        )
    return SimpleNamespace(
        series_id=f"evidence-{timeframe}",
        timeframe=timeframe,
        candles=tuple(candles),
        blockers=(),
        warnings=(),
    )


class ExistingCanonicalPrimitivesFixture:
    """Injected stand-in; canonical primitives are imported in the real repo."""

    @staticmethod
    def calculate_sma(values, period):
        return None if len(values) < period else sum(values[-period:]) / period

    @staticmethod
    def calculate_volume_average(values, period):
        return None if len(values) < period else sum(values[-period:]) / period

    @staticmethod
    def calculate_ema(values, period):
        return None if len(values) < period else sum(values[-period:]) / period

    @staticmethod
    def calculate_adx(h, low, c, period):
        return 25.0 if len(c) >= period * 2 + 1 else None

    @staticmethod
    def calculate_rsi(c, period):
        return 65.0 if len(c) >= period + 1 else None

    @staticmethod
    def calculate_macd(c, fast, slow, signal):
        return (1.0, 0.5, 0.5) if len(c) >= slow + signal - 1 else None

    @staticmethod
    def calculate_atr(h, low, c, period):
        return 2.0 if len(c) >= period else None

    @staticmethod
    def calculate_bollinger_bands(c, period, stddev):
        return (
            (min(c[-period:]), sum(c[-period:]) / period, max(c[-period:]))
            if len(c) >= period
            else None
        )

    @staticmethod
    def calculate_vwap(h, low, c, v):
        return sum(z * q for z, q in zip(c, v)) / sum(v) if sum(v) > 0 else None


STD = ExistingCanonicalPrimitivesFixture
MARKETS = ("NIFTY", "SENSEX", "CRUDEOILM", "GOLDM", "NATGASMINI")


@mark.parametrize("market", MARKETS)
def test_five_markets_independent_feature_evaluation(market):
    data = series()
    result = build_x3_timeframe_v1(
        market=market,
        instrument_id=f"{market}-FUT",
        series=data,
        as_of=data.candles[-1].end_at,
        source_quality="READY",
        standard=STD,
    )
    assert result.market == market and len(result.families) == 7
    assert (
        result.sha256
        == build_x3_timeframe_v1(
            market=market,
            instrument_id=f"{market}-FUT",
            series=data,
            as_of=data.candles[-1].end_at,
            source_quality="READY",
            standard=STD,
        ).sha256
    )
    assert next(f for f in result.families if f.family == "TREND").state == "BULLISH"


def test_price_only_features_remain_valid_when_volume_missing():
    data = series(volume=0.0)
    result = build_x3_timeframe_v1(
        market="NIFTY",
        instrument_id="NIFTY-INDEX",
        series=data,
        as_of=data.candles[-1].end_at,
        source_quality="READY",
        standard=STD,
    )
    f = {x.feature_id: x for x in result.features}
    assert f["RSI"].status == "VALID"
    assert f["VWAP_PROXY"].status == "UNAVAILABLE" and f["MFI"].status == "UNAVAILABLE"
    assert next(x for x in result.families if x.family == "VOLUME_PARTICIPATION").state == "MISSING"


def test_unverified_source_blocks_all_feature_calculations():
    data = series()
    result = build_x3_timeframe_v1(
        market="NIFTY",
        instrument_id="INDEX",
        series=data,
        as_of=data.candles[-1].end_at,
        source_quality="UNVERIFIED",
        standard=STD,
    )
    assert result.blockers == ("source_quality_not_ready",) and result.features == ()


def test_incomplete_latest_candle_is_excluded_without_lookahead():
    data = series()
    candles = data.candles[:-1] + (Candle(**{**data.candles[-1].__dict__, "is_complete": False}),)
    partial = SimpleNamespace(**{**vars(data), "candles": candles})
    result = build_x3_timeframe_v1(
        market="NIFTY",
        instrument_id="INDEX",
        series=partial,
        as_of=candles[-1].end_at,
        source_quality="READY",
        standard=STD,
    )
    assert "latest_incomplete_candle_excluded" in result.warnings
    assert all(f.observed_at <= candles[-2].end_at for f in result.features)


def test_future_candle_fails_closed():
    data = series()
    c, blockers, _ = admitted_candles_v1(
        data, as_of=data.candles[-2].end_at, source_quality="READY"
    )
    assert not c and blockers == ("invalid_or_future_candle",)


def test_duplicate_timestamp_fails_closed():
    data = series()
    dup = SimpleNamespace(
        **{**vars(data), "candles": data.candles[:2] + (data.candles[1],) + data.candles[3:]}
    )
    _, blockers, _ = admitted_candles_v1(dup, as_of=data.candles[-1].end_at, source_quality="READY")
    assert blockers == ("duplicate_or_overlapping_candle",)


def test_same_session_gap_fails_closed():
    data = series(n=5)
    gap = SimpleNamespace(**{**vars(data), "candles": data.candles[:2] + data.candles[3:]})
    _, blockers, _ = admitted_candles_v1(gap, as_of=data.candles[-1].end_at, source_quality="READY")
    assert blockers == ("unverified_same_session_gap",)


def test_mtf_missing_does_not_fill_lower_timeframe():
    d = series()
    result = build_x3_multi_timeframe_v1(
        market="NIFTY",
        instrument_id="INDEX",
        series_by_timeframe={"5m": d},
        quality_by_timeframe={"5m": "READY"},
        as_of=d.candles[-1].end_at,
        standard=STD,
    )
    assert result.missing_timeframes == ("15m", "1h", "1d")
    assert result.alignment == "UNKNOWN"


def test_mtf_deterministic_full_single_timeframe():
    d = series()
    kwargs = dict(
        market="NIFTY",
        instrument_id="INDEX",
        series_by_timeframe={"5m": d},
        quality_by_timeframe={"5m": "READY"},
        as_of=d.candles[-1].end_at,
        required_timeframes=("5m",),
        standard=STD,
    )
    assert (
        build_x3_multi_timeframe_v1(**kwargs).sha256 == build_x3_multi_timeframe_v1(**kwargs).sha256
    )


def test_combined_research_view_preserves_independent_hashes():
    d = series()
    x3 = build_x3_multi_timeframe_v1(
        market="NIFTY",
        instrument_id="INDEX",
        series_by_timeframe={"5m": d},
        quality_by_timeframe={"5m": "READY"},
        as_of=d.candles[-1].end_at,
        required_timeframes=("5m",),
        standard=STD,
    )

    class X2:
        def to_dict(self):
            return {"schema_version": "X2_TEST_V1", "index_symbol": "NIFTY", "members": ["A", "B"]}

    result = build_x23_research_view_v1(x3, {"breadth": X2()})
    assert result.x2_available and result.x3_available and len(result.x2_evidence_hashes) == 1
    assert result.sha256 == build_x23_research_view_v1(x3, {"breadth": X2()}).sha256


def test_combined_cross_market_mismatch_blocked():
    d = series()
    x3 = build_x3_multi_timeframe_v1(
        market="NIFTY",
        instrument_id="INDEX",
        series_by_timeframe={"5m": d},
        quality_by_timeframe={"5m": "READY"},
        as_of=d.candles[-1].end_at,
        required_timeframes=("5m",),
        standard=STD,
    )

    class OtherX2:
        def to_dict(self):
            return {"schema_version": "X2_TEST_V1", "index_symbol": "SENSEX"}

    with raises(ValueError):
        build_x23_research_view_v1(x3, {"breadth": OtherX2()})


def test_missing_provider_provenance_fails_closed():
    d = series(n=3)
    candles = list(d.candles)
    candles[1] = SimpleNamespace(**{k: v for k, v in vars(candles[1]).items()})
    d.candles = tuple(candles)
    _, blockers, _ = admitted_candles_v1(d, as_of=d.candles[-1].end_at, source_quality="READY")
    assert blockers == ("source_provenance_missing",)


def test_mixed_providers_fail_closed():
    d = series(n=3)
    candles = list(d.candles)
    candles[1] = SimpleNamespace(
        **{**vars(candles[1]), "provenance": SimpleNamespace(provider="ANGEL_SMARTAPI")}
    )
    d.candles = tuple(candles)
    _, blockers, _ = admitted_candles_v1(d, as_of=d.candles[-1].end_at, source_quality="READY")
    assert blockers == ("mixed_source_providers",)


def test_zero_current_session_volume_does_not_create_vwap_proxy():
    d = series(n=60)
    # First session has volume, but later session only has zero volume.
    candles = []
    for i, c in enumerate(d.candles):
        vol = 100.0 if i < 40 else 0.0
        candles.append(Candle(**{**vars(c), "volume": vol}))
    # Force a genuine later India trading date, while keeping intra-day ordering.
    shift = timedelta(days=1)
    for i in range(40, 60):
        c = candles[i]
        candles[i] = Candle(
            **{**vars(c), "start_at": c.start_at + shift, "end_at": c.end_at + shift}
        )
    d.candles = tuple(candles)
    output = build_x3_timeframe_v1(
        market="NIFTY",
        instrument_id="INDEX",
        series=d,
        as_of=d.candles[-1].end_at,
        source_quality="READY",
        standard=STD,
    )
    assert next(f for f in output.features if f.feature_id == "VWAP_PROXY").status == "UNAVAILABLE"


def test_daily_vwap_proxy_is_unavailable_not_invented():
    d = series(timeframe="1d", n=60)
    output = build_x3_timeframe_v1(
        market="NIFTY",
        instrument_id="INDEX",
        series=d,
        as_of=d.candles[-1].end_at,
        source_quality="READY",
        standard=STD,
    )
    assert next(f for f in output.features if f.feature_id == "VWAP_PROXY").status == "UNAVAILABLE"


def test_research_without_x2_preserves_x3_independence():
    d = series()
    x3 = build_x3_multi_timeframe_v1(
        market="NIFTY",
        instrument_id="INDEX",
        series_by_timeframe={"5m": d},
        quality_by_timeframe={"5m": "READY"},
        as_of=d.candles[-1].end_at,
        required_timeframes=("5m",),
        standard=STD,
    )
    view = build_x23_research_view_v1(x3, {})
    assert not view.x2_available and view.x3_available
    assert view.x3_result_sha256 == x3.sha256
