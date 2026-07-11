import pandas as pd

from services.regime_indicator_builder import (
    add_regime_indicators,
)


def test_adds_required_regime_indicators():

    data = pd.DataFrame({
        "High": range(110, 170),
        "Low": range(90, 150),
        "Close": range(100, 160),
    })

    result = add_regime_indicators(data)

    required = {
        "EMA20",
        "EMA50",
        "ATR",
        "ADX",
        "BB_UPPER",
        "BB_LOWER",
    }

    assert required.issubset(
        result.columns
    )

    assert result.iloc[-1][
        "EMA20"
    ] > 0