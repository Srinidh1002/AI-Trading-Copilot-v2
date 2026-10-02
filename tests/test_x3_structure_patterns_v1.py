from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from services.x3.patterns_v1 import detect_candlestick_patterns_v1
from services.x3.structure_v1 import analyze_price_structure_v1

BASE = datetime(2026, 9, 18, 9, 0, tzinfo=UTC)


@dataclass(frozen=True)
class C:
    candle_id: str
    start_at: datetime
    end_at: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float = 100
    is_complete: bool = True


def cs(rows):
    return tuple(
        C(
            str(i),
            BASE + timedelta(minutes=5 * i),
            BASE + timedelta(minutes=5 * (i + 1)),
            o,
            h,
            low,
            c,
        )
        for i, (o, h, low, c) in enumerate(rows)
    )


def test_swing_not_visible_until_right_window_closes():
    rows = [(10, 11, 9, 10), (11, 15, 9.5, 11), (10, 12, 9.5, 10), (11, 13, 9.6, 11)]
    assert analyze_price_structure_v1(cs(rows[:2]), lookback=1).high_points == ()
    complete = analyze_price_structure_v1(cs(rows[:3]), lookback=1)
    assert complete.high_points[0].candle_index == 1
    assert complete.high_points[0].confirmed_at == cs(rows)[2].end_at


def test_last_lookback_candles_not_confirmed_as_swing():
    a = analyze_price_structure_v1(
        cs([(10, 11, 9, 10), (10, 12, 9, 10), (10, 20, 9, 19)]), lookback=1
    )
    assert all(s.price != 20 for s in a.high_points)


def test_insufficient_swing_history():
    a = analyze_price_structure_v1(cs([(10, 11, 9, 10)]), lookback=2)
    assert a.state == "UNKNOWN" and a.blockers


def test_breakout_requires_post_confirmation_close():
    rows = [(10, 11, 9, 10), (11, 15, 9.5, 11), (10, 12, 9.5, 10), (11, 16, 10, 15.5)]
    x = analyze_price_structure_v1(cs(rows), lookback=1)
    assert x.breakout_state == "UP_BREAK" and x.breakout_reference == 15


def test_retest_requires_later_candle():
    rows = [
        (10, 11, 9, 10),
        (11, 15, 9.5, 11),
        (10, 12, 9.5, 10),
        (15, 16, 10, 15.5),
        (15, 16, 14.8, 15.2),
    ]
    x = analyze_price_structure_v1(cs(rows), lookback=1)
    assert x.breakout_state == "UP_RETEST"


def test_failed_breakout():
    rows = [
        (10, 11, 9, 10),
        (11, 15, 9.5, 11),
        (10, 12, 9.5, 10),
        (15, 16, 10, 15.5),
        (14.8, 15, 13.5, 14),
    ]
    x = analyze_price_structure_v1(cs(rows), lookback=1)
    assert x.breakout_state == "UP_FAILURE"


def test_engulfing_bullish_and_completed_timestamp():
    rows = [(12, 12.5, 9.5, 10), (9.8, 12.8, 9.5, 12.4)]
    patterns = detect_candlestick_patterns_v1(cs(rows))
    b = next(p for p in patterns if p.name == "BULLISH_ENGULFING")
    assert b.direction == "BULLISH" and b.available_at == cs(rows)[-1].end_at
    assert b.candle_ids == ("0", "1")


def test_doji_is_not_directional():
    patterns = detect_candlestick_patterns_v1(cs([(10, 11, 9, 10.02)]))
    doji = next(p for p in patterns if p.name == "DOJI")
    assert doji.direction == "NON_DIRECTIONAL"


def test_hammer_shape_not_bullish_without_context():
    patterns = detect_candlestick_patterns_v1(cs([(10, 10.3, 8, 10.2)]))
    hammer = next(p for p in patterns if p.name == "HAMMER_SHAPE")
    assert hammer.direction == "NON_DIRECTIONAL"


def test_shape_confirmation_needs_next_candle_and_context():
    rows = [(10, 10.3, 8, 10.2), (10.3, 11, 10.2, 10.8)]
    first = detect_candlestick_patterns_v1(cs(rows[:1]), context="DOWNTREND")
    assert "HAMMER_CONFIRMED" not in {p.name for p in first}
    second = detect_candlestick_patterns_v1(cs(rows), context="DOWNTREND")
    assert "HAMMER_CONFIRMED" in {p.name for p in second}
