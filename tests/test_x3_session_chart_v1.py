from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import isclose

from services.x3.chart_patterns_v1 import detect_chart_formations_v1
from services.x3.session_levels_v1 import calculate_session_levels_v1
from services.x3.structure_v1 import analyze_price_structure_v1

BASE = datetime(2026, 9, 17, 9, 0, tzinfo=UTC)


@dataclass(frozen=True)
class C:
    candle_id: str
    start_at: datetime
    end_at: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float = 1
    is_complete: bool = True


def cs(rows):
    return tuple(
        C(str(i), BASE + timedelta(minutes=5 * i), BASE + timedelta(minutes=5 * (i + 1)), *r)
        for i, r in enumerate(rows)
    )


def test_prior_session_high_low_classic_pivots_and_opening_gap():
    rows = cs([(10, 12, 9, 11), (11, 15, 10, 14)])
    first = rows
    nxt = C("2", BASE + timedelta(days=1), BASE + timedelta(days=1, minutes=5), 15, 16, 14, 15.5)
    result = calculate_session_levels_v1(first + (nxt,))
    assert result.previous_high == 15 and result.previous_low == 9 and result.previous_close == 14
    assert isclose(result.pivot_point, (15 + 9 + 14) / 3)
    assert isclose(result.support_1, 2 * result.pivot_point - 15)
    assert isclose(result.resistance_1, 2 * result.pivot_point - 9)
    assert isclose(result.opening_gap_percent, 100 * (15 / 14 - 1))


def test_no_previous_session_does_not_fabricate_levels():
    result = calculate_session_levels_v1(cs([(10, 11, 9, 10)]))
    assert result.previous_high is None and result.blockers == ("previous_session_unavailable",)


def test_confirmed_double_top_only_after_neckline_break():
    rows = [
        (10, 11, 9, 10),
        (11, 15, 9.5, 11),
        (10, 12, 9.5, 10),
        (10, 11, 8.5, 10),
        (10, 12, 9.5, 10),
        (11, 15.02, 9.6, 11),
        (11, 12, 9.7, 10),
        (10, 10.2, 8, 8.4),
    ]
    partial = cs(rows[:-1])
    assert (
        detect_chart_formations_v1(partial, analyze_price_structure_v1(partial, lookback=1)) == ()
    )
    all_candles = cs(rows)
    found = detect_chart_formations_v1(
        all_candles, analyze_price_structure_v1(all_candles, lookback=1)
    )
    assert len(found) == 1 and found[0].name == "DOUBLE_TOP_CONFIRMED"
    assert found[0].confirmed_at == all_candles[-1].end_at


def test_double_top_with_unbroken_neckline_remains_unconfirmed():
    rows = [
        (10, 11, 9, 10),
        (11, 15, 9.5, 11),
        (10, 12, 9.5, 10),
        (10, 11, 8.5, 10),
        (10, 12, 9.5, 10),
        (11, 15.01, 9.6, 11),
        (11, 12, 9.7, 10),
        (10, 10.5, 9, 9.5),
    ]
    candles = cs(rows)
    assert (
        detect_chart_formations_v1(candles, analyze_price_structure_v1(candles, lookback=1)) == ()
    )


def test_confirmed_double_bottom_needs_neckline_break():
    rows = [
        (10, 11, 9, 10),
        (10, 10.5, 8, 9),
        (10, 12, 9.5, 10),
        (11, 15, 9.5, 12),
        (11, 12, 9.5, 10),
        (10, 10.6, 8.02, 9),
        (10, 12, 9.5, 10),
        (15, 15.5, 10, 15.2),
    ]
    candles = cs(rows)
    found = detect_chart_formations_v1(candles, analyze_price_structure_v1(candles, lookback=1))
    assert any(x.name == "DOUBLE_BOTTOM_CONFIRMED" and x.direction == "BULLISH" for x in found)
