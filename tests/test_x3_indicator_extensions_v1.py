from math import isclose

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


def test_stochastic_k_d_against_manual_reference():
    k, d = calculate_stochastic((10, 11, 12), (8, 8, 9), (9, 10, 11), 2, 2)
    assert isclose(k, 75.0) and isclose(d, (200 / 3 + 75) / 2)


def test_stochastic_warmup():
    assert calculate_stochastic((10, 11), (8, 9), (9, 10), 2, 2) is None


def test_stochastic_flat_range_neutral():
    assert calculate_stochastic((10, 10, 10), (10, 10, 10), (10, 10, 10), 2, 2) == (50, 50)


def test_cci_against_manual_mean_deviation():
    assert isclose(calculate_cci((10, 11, 12), (10, 11, 12), (10, 11, 12), 3), 100.0)


def test_cci_flat_series_zero():
    assert calculate_cci((10, 10), (10, 10), (10, 10), 2) == 0


def test_williams_manual():
    assert calculate_williams_r((10, 11, 12), (8, 8, 9), (9, 10, 10), 3) == -50


def test_williams_flat_neutral():
    assert calculate_williams_r((10, 10), (10, 10), (10, 10), 2) == -50


def test_aroon_manual_latest_extrema():
    assert calculate_aroon((5, 7, 6, 8), (4, 3, 2, 1), 3) == (100.0, 100.0)


def test_aroon_latest_tie_wins():
    assert calculate_aroon((10, 10, 10), (5, 5, 5), 2) == (100.0, 100.0)


def test_mfi_against_manual_flow():
    result = calculate_mfi((10, 12, 11), (10, 12, 11), (10, 12, 11), (2, 3, 4), 2)
    assert isclose(result, 45.0)


def test_mfi_zero_volume_missing():
    assert calculate_mfi((10, 11), (10, 11), (10, 11), (0, 0), 1) is None


def test_mfi_flat_price_positive_volume_neutral():
    assert calculate_mfi((10, 10, 10), (10, 10, 10), (10, 10, 10), (1, 2, 3), 2) == 50


def test_roc_percentage_and_lookback():
    assert isclose(calculate_roc((10, 11, 12), 2), 20)
    assert calculate_roc((10, 11), 2) is None


def test_momentum_price_units():
    assert calculate_momentum((10, 11, 12), 2) == 2


def test_volume_change_percentage():
    assert calculate_volume_change((5, 10)) == 100
    assert calculate_volume_change((0, 10)) is None


def test_invalid_nonfinite_and_bools():
    assert calculate_aroon((1, float("nan")), (1, 1), 1) is None
    assert calculate_cci((True, 2), (1, 1), (1, 2), 1) is None
    assert calculate_roc((10, 12), True) is None
    assert calculate_mfi((1, 2), (1, 2), (1, 2), (-1, 2), 1) is None
