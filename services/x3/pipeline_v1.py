"""Offline-only X3 feature assembly from independently admitted candle series."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from services.x3.chart_patterns_v1 import detect_chart_formations_v1
from services.x3.contracts_v1 import MARKETS, X3FeatureV1, X3TimeframeResultV1
from services.x3.family_normalization_v1 import reduce_all_families_v1
from services.x3.indicator_extensions_v1 import (
    calculate_aroon,
    calculate_cci,
    calculate_mfi,
    calculate_momentum,
    calculate_roc,
    calculate_stochastic,
    calculate_volume_change,
    calculate_williams_r,
)
from services.x3.patterns_v1 import detect_candlestick_patterns_v1
from services.x3.series_validation_v1 import admitted_candles_v1
from services.x3.session_levels_v1 import calculate_session_levels_v1
from services.x3.structure_v1 import analyze_price_structure_v1

DEFAULT_PERIODS = {
    "rsi": 14,
    "ema_fast": 20,
    "ema_slow": 50,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "adx": 14,
    "atr": 14,
    "bands": 20,
    "stochastic": 14,
    "cci": 20,
    "williams": 14,
    "aroon": 14,
    "mfi": 14,
    "roc": 12,
    "momentum": 10,
}


def _default_standard():
    # These are independently verified repository primitives. Import lazily:
    # importing X3 must never construct a provider, import the SDK or do I/O.
    from services.technical_intelligence import indicators

    return indicators


def build_x3_timeframe_v1(
    *,
    market: str,
    instrument_id: str,
    series,
    as_of: datetime,
    source_quality: str,
    standard=None,
    tick_size: float = 0.0,
) -> X3TimeframeResultV1:
    """Return numeric feature and one reduced state per family.

    ``source_quality`` must be provided by existing upstream data-quality
    evidence. No X1 quote is misrepresented as a completed candle.
    ``standard`` is an optional injected implementation for isolated tests;
    normally existing canonical repository primitives are used unchanged.
    """
    if market not in MARKETS or not isinstance(instrument_id, str) or not instrument_id:
        raise ValueError("unsupported market or instrument")
    candles, blockers, warnings = admitted_candles_v1(
        series,
        as_of=as_of,
        source_quality=source_quality,
    )
    source_id = getattr(series, "series_id", None) or "source-unavailable"
    timeframe = getattr(series, "timeframe", None) or "unknown"
    n = len(candles)
    timestamp = candles[-1].end_at if candles else as_of
    output = []
    provider = (
        getattr(getattr(candles[-1], "provenance", None), "provider", "UNVERIFIED")
        if candles
        else "UNVERIFIED"
    )

    def add(
        name,
        family,
        value,
        req,
        *,
        unit="INDEX",
        direction="NON_DIRECTIONAL",
        dependency="OHLC",
        unavailable=False,
    ):
        if blockers:
            status, why = "UNVERIFIED", tuple(blockers)
        elif unavailable:
            status, why = "UNAVAILABLE", ("source_field_unavailable",)
        elif n < req or value is None:
            status, why = "INSUFFICIENT_HISTORY", ("insufficient_history_or_undefined",)
        else:
            status, why = "VALID", ()
        output.append(
            X3FeatureV1(
                feature_id=name,
                market=market,
                instrument_id=instrument_id,
                timeframe=timeframe,
                family=family,
                value=value if status == "VALID" else None,
                unit=unit,
                direction=direction if status == "VALID" else "UNKNOWN",
                status=status,
                observed_at=timestamp,
                source_id=source_id,
                required_history=req,
                available_history=n,
                dependency_ids=(f"{dependency}:{source_id}",),
                blockers=why,
                warnings=warnings,
                provider=provider,
            )
        )

    if blockers:
        # Explicit blocked result; never calculate over unverified series.
        return X3TimeframeResultV1(
            market,
            instrument_id,
            timeframe,
            as_of,
            source_id,
            (),
            reduce_all_families_v1(()),
            blockers,
            warnings,
        )

    base = standard if standard is not None else _default_standard()
    h = tuple(c.high_price for c in candles)
    low = tuple(c.low_price for c in candles)
    c = tuple(c.close_price for c in candles)
    v = tuple(candle.volume for candle in candles)
    p = DEFAULT_PERIODS
    usable_volume = any(q > 0 for q in v)

    sma20 = base.calculate_sma(c, 20)
    sma50 = base.calculate_sma(c, 50)
    add("SMA20", "TREND", sma20, 20, unit="PRICE")
    add("SMA50", "TREND", sma50, 50, unit="PRICE")
    ema20 = base.calculate_ema(c, p["ema_fast"])
    ema50 = base.calculate_ema(c, p["ema_slow"])
    add("EMA20", "TREND", ema20, 20, unit="PRICE", direction="NON_DIRECTIONAL")
    add("EMA50", "TREND", ema50, 50, unit="PRICE", direction="NON_DIRECTIONAL")
    add(
        "EMA_TREND",
        "TREND",
        (ema20 - ema50) if ema20 is not None and ema50 is not None else None,
        50,
        unit="PRICE",
        direction="BULLISH"
        if ema20 is not None and ema50 is not None and ema20 > ema50
        else "BEARISH"
        if ema20 is not None and ema50 is not None and ema20 < ema50
        else "NON_DIRECTIONAL",
    )
    adx = base.calculate_adx(h, low, c, p["adx"])
    add("ADX", "TREND", adx, 2 * p["adx"] + 1, unit="INDEX", direction="NON_DIRECTIONAL")
    aroon = calculate_aroon(h, low, p["aroon"])
    add(
        "AROON_UP",
        "TREND",
        aroon[0] if aroon else None,
        15,
        unit="PERCENT",
        direction="NON_DIRECTIONAL",
    )
    add(
        "AROON_DOWN",
        "TREND",
        aroon[1] if aroon else None,
        15,
        unit="PERCENT",
        direction="NON_DIRECTIONAL",
    )
    add(
        "AROON_DIRECTION",
        "TREND",
        aroon[0] - aroon[1] if aroon else None,
        15,
        unit="PERCENT_POINTS",
        direction="BULLISH"
        if aroon and aroon[0] > aroon[1]
        else "BEARISH"
        if aroon and aroon[0] < aroon[1]
        else "NON_DIRECTIONAL",
    )
    rsi = base.calculate_rsi(c, p["rsi"])
    add(
        "RSI",
        "MOMENTUM",
        rsi,
        15,
        direction="BULLISH"
        if rsi is not None and rsi > 50
        else "BEARISH"
        if rsi is not None and rsi < 50
        else "NON_DIRECTIONAL",
    )
    macd = base.calculate_macd(c, p["macd_fast"], p["macd_slow"], p["macd_signal"])
    add("MACD_LINE", "MOMENTUM", macd[0] if macd else None, 34, unit="PRICE")
    add("MACD_SIGNAL", "MOMENTUM", macd[1] if macd else None, 34, unit="PRICE")
    add(
        "MACD_HISTOGRAM",
        "MOMENTUM",
        macd[2] if macd else None,
        34,
        unit="PRICE",
        direction="BULLISH"
        if macd and macd[2] > 0
        else "BEARISH"
        if macd and macd[2] < 0
        else "NON_DIRECTIONAL",
    )
    roc = calculate_roc(c, p["roc"])
    add(
        "ROC",
        "MOMENTUM",
        roc,
        13,
        unit="PERCENT",
        direction="BULLISH"
        if roc is not None and roc > 0
        else "BEARISH"
        if roc is not None and roc < 0
        else "NON_DIRECTIONAL",
    )
    momentum = calculate_momentum(c, p["momentum"])
    add(
        "MOMENTUM",
        "MOMENTUM",
        momentum,
        11,
        unit="PRICE",
        direction="BULLISH"
        if momentum is not None and momentum > 0
        else "BEARISH"
        if momentum is not None and momentum < 0
        else "NON_DIRECTIONAL",
    )

    stoch = calculate_stochastic(h, low, c, p["stochastic"], 3)
    add("STOCHASTIC_K", "EXHAUSTION", stoch[0] if stoch else None, 16, unit="PERCENT")
    add("STOCHASTIC_D", "EXHAUSTION", stoch[1] if stoch else None, 16, unit="PERCENT")
    add("CCI", "EXHAUSTION", calculate_cci(h, low, c, p["cci"]), 20)
    add(
        "WILLIAMS_R",
        "EXHAUSTION",
        calculate_williams_r(h, low, c, p["williams"]),
        14,
        unit="PERCENT",
    )

    atr = base.calculate_atr(h, low, c, p["atr"])
    add("ATR", "VOLATILITY", atr, p["atr"], unit="PRICE")
    bands = base.calculate_bollinger_bands(c, p["bands"], 2.0)
    add("BOLLINGER_LOWER", "VOLATILITY", bands[0] if bands else None, 20, unit="PRICE")
    add("BOLLINGER_MIDDLE", "VOLATILITY", bands[1] if bands else None, 20, unit="PRICE")
    add("BOLLINGER_UPPER", "VOLATILITY", bands[2] if bands else None, 20, unit="PRICE")
    add(
        "BOLLINGER_WIDTH",
        "VOLATILITY",
        ((bands[2] - bands[0]) / bands[1] if bands and bands[1] != 0 else None),
        20,
        unit="RATIO",
    )

    volume_average = base.calculate_volume_average(v, 20) if usable_volume else None
    add(
        "VOLUME_AVERAGE",
        "VOLUME_PARTICIPATION",
        volume_average,
        20,
        unit="VOLUME",
        unavailable=not usable_volume,
    )
    mfi_usable = n >= p["mfi"] + 1 and sum(v[-p["mfi"] :]) > 0
    mfi = calculate_mfi(h, low, c, v, p["mfi"]) if mfi_usable else None
    add(
        "MFI",
        "VOLUME_PARTICIPATION",
        mfi,
        15,
        unit="INDEX",
        unavailable=not usable_volume or (n >= 15 and not mfi_usable),
    )
    volume_change_usable = len(v) >= 2 and v[-2] > 0
    vc = calculate_volume_change(v) if volume_change_usable else None
    add(
        "VOLUME_CHANGE",
        "VOLUME_PARTICIPATION",
        vc,
        2,
        unit="PERCENT",
        unavailable=not usable_volume or (n >= 2 and not volume_change_usable),
    )
    # Existing primitive computes an OHLCV typical-price weighted proxy.
    # Restrict it to the current India trading date; a multi-session cumulative
    # value must not be passed off as session VWAP. Daily OHLC cannot reconstruct
    # intraday VWAP, so report it unavailable instead of manufacturing it.
    intraday_volume = usable_volume and timeframe != "1d"
    vwap = None
    current_session_volume = False
    if intraday_volume:
        india_date = candles[-1].start_at.astimezone(ZoneInfo("Asia/Kolkata")).date()
        session = tuple(
            x
            for x in candles
            if x.start_at.astimezone(ZoneInfo("Asia/Kolkata")).date() == india_date
        )
        current_session_volume = any(x.volume > 0 for x in session)
        if current_session_volume:
            vwap = base.calculate_vwap(
                tuple(x.high_price for x in session),
                tuple(x.low_price for x in session),
                tuple(x.close_price for x in session),
                tuple(x.volume for x in session),
            )
    add(
        "VWAP_PROXY",
        "VOLUME_PARTICIPATION",
        vwap,
        1,
        unit="PRICE",
        direction="BULLISH"
        if vwap is not None and c[-1] > vwap
        else "BEARISH"
        if vwap is not None and c[-1] < vwap
        else "NON_DIRECTIONAL",
        unavailable=not intraday_volume or not current_session_volume,
    )

    structure = analyze_price_structure_v1(candles, tick_size=tick_size)
    add(
        "STRUCTURE_TREND",
        "STRUCTURE",
        1.0 if structure.state not in {"UNKNOWN"} else None,
        5,
        unit="CLASSIFICATION",
        direction=structure.state if structure.state != "UNKNOWN" else "UNKNOWN",
    )
    add("LAST_SUPPORT", "STRUCTURE", structure.last_support, 5, unit="PRICE")
    add("LAST_RESISTANCE", "STRUCTURE", structure.last_resistance, 5, unit="PRICE")
    breakout_direction = (
        "BULLISH"
        if structure.breakout_state in {"UP_BREAK", "UP_RETEST", "DOWN_FAILURE"}
        else "BEARISH"
        if structure.breakout_state in {"DOWN_BREAK", "DOWN_RETEST", "UP_FAILURE"}
        else "NON_DIRECTIONAL"
    )
    add(
        "BREAKOUT_STATE",
        "STRUCTURE",
        1.0 if structure.breakout_state != "NONE" else 0.0,
        5,
        unit="CLASSIFICATION",
        direction=breakout_direction,
    )
    levels = calculate_session_levels_v1(candles)
    for label, value, unit in (
        ("PREVIOUS_HIGH", levels.previous_high, "PRICE"),
        ("PREVIOUS_LOW", levels.previous_low, "PRICE"),
        ("PREVIOUS_CLOSE", levels.previous_close, "PRICE"),
        ("PIVOT_POINT", levels.pivot_point, "PRICE"),
        ("PIVOT_R1", levels.resistance_1, "PRICE"),
        ("PIVOT_S1", levels.support_1, "PRICE"),
        ("OPENING_GAP", levels.opening_gap_percent, "PERCENT"),
    ):
        add(label, "STRUCTURE", value, 2, unit=unit, dependency="SESSION_LEVELS")
    ctx = (
        "DOWNTREND"
        if structure.state == "BEARISH"
        else "UPTREND"
        if structure.state == "BULLISH"
        else "UNKNOWN"
    )
    patterns = detect_candlestick_patterns_v1(candles, context=ctx)
    chart_formations = detect_chart_formations_v1(candles, structure)
    for formation in chart_formations:
        add(
            "CHART_" + formation.name,
            "PATTERN",
            1.0,
            len(formation.source_candle_ids),
            unit="BINARY",
            direction=formation.direction,
            dependency="PRICE_STRUCTURE",
        )
    if not patterns and not chart_formations:
        add("PATTERN_NONE", "PATTERN", 0.0, 1, unit="BINARY")
    else:
        for pattern in patterns:
            add(
                "PATTERN_" + pattern.name,
                "PATTERN",
                1.0,
                len(pattern.candle_ids),
                unit="BINARY",
                direction=pattern.direction,
                dependency="CANDLE_PATTERN",
            )
    return X3TimeframeResultV1(
        market,
        instrument_id,
        timeframe,
        as_of,
        source_id,
        tuple(output),
        reduce_all_families_v1(tuple(output)),
        (),
        warnings,
    )
