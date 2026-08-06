import pandas as pd
import pytest

from services.data_normalizer import normalize_angel_candles


def test_normalize_angel_candles():

    candles = [
        [
            "2026-07-10T09:15:00+05:30",
            24124.7,
            24187.9,
            24120.35,
            24162.7,
            0,
        ],
        [
            "2026-07-10T09:20:00+05:30",
            24165.85,
            24178.2,
            24154.3,
            24174.75,
            0,
        ],
    ]

    df = normalize_angel_candles(candles)

    assert isinstance(df, pd.DataFrame)

    assert list(df.columns) == [
        "timestamp",
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]

    assert len(df) == 2
    assert df.loc[0, "Close"] == 24162.7


def test_empty_candles():

    with pytest.raises(
        ValueError,
        match="No candle data provided",
    ):
        normalize_angel_candles([])


@pytest.mark.parametrize(
    "row",
    (
        [
            "2026-07-10T09:15:00+05:30",
            100,
            101,
            99,
            100,
        ],
        [
            "2026-07-10T09:15:00+05:30",
            100,
            101,
            99,
            100,
            10,
            "extra",
        ],
        None,
        "invalid-row",
    ),
)
def test_candle_row_requires_exact_six_value_sequence(
    row,
):
    with pytest.raises(
        ValueError,
        match="sequence|exactly 6",
    ):
        normalize_angel_candles(
            [row]
        )


@pytest.mark.parametrize(
    "timestamp",
    (
        "invalid",
        "",
        None,
        "2026-07-10T09:15:00",
    ),
)
def test_timestamp_must_be_valid_and_timezone_aware(
    timestamp,
):
    with pytest.raises(
        ValueError,
        match="timestamp",
    ):
        normalize_angel_candles(
            [
                [
                    timestamp,
                    100,
                    101,
                    99,
                    100,
                    10,
                ]
            ]
        )


@pytest.mark.parametrize(
    (
        "field_index",
        "value",
    ),
    (
        (1, None),
        (1, "invalid"),
        (1, float("nan")),
        (2, float("inf")),
        (3, float("-inf")),
        (4, True),
        (5, "invalid"),
    ),
)
def test_ohlcv_values_must_be_finite_numeric(
    field_index,
    value,
):
    row = [
        "2026-07-10T09:15:00+05:30",
        100,
        101,
        99,
        100,
        10,
    ]

    row[field_index] = value

    with pytest.raises(
        ValueError,
        match="invalid|non-finite",
    ):
        normalize_angel_candles(
            [row]
        )


def test_negative_volume_is_rejected():
    with pytest.raises(
        ValueError,
        match="negative volume",
    ):
        normalize_angel_candles(
            [
                [
                    "2026-07-10T09:15:00+05:30",
                    100,
                    101,
                    99,
                    100,
                    -1,
                ]
            ]
        )


@pytest.mark.parametrize(
    "row",
    (
        [
            "2026-07-10T09:15:00+05:30",
            100,
            99,
            101,
            100,
            10,
        ],
        [
            "2026-07-10T09:15:00+05:30",
            102,
            101,
            99,
            100,
            10,
        ],
        [
            "2026-07-10T09:15:00+05:30",
            100,
            101,
            99,
            102,
            10,
        ],
    ),
)
def test_invalid_ohlc_relationships_are_rejected(
    row,
):
    with pytest.raises(
        ValueError,
        match="low|open|close",
    ):
        normalize_angel_candles(
            [row]
        )


def test_duplicate_timestamp_is_rejected():
    row = [
        "2026-07-10T09:15:00+05:30",
        100,
        101,
        99,
        100,
        10,
    ]

    with pytest.raises(
        ValueError,
        match="strictly increasing",
    ):
        normalize_angel_candles(
            [
                row,
                list(row),
            ]
        )


def test_out_of_order_timestamp_is_rejected():
    with pytest.raises(
        ValueError,
        match="strictly increasing",
    ):
        normalize_angel_candles(
            [
                [
                    "2026-07-10T09:20:00+05:30",
                    100,
                    101,
                    99,
                    100,
                    10,
                ],
                [
                    "2026-07-10T09:15:00+05:30",
                    100,
                    101,
                    99,
                    100,
                    10,
                ],
            ]
        )


def test_normalizer_preserves_timezone_and_row_order():
    dataframe = normalize_angel_candles(
        [
            [
                "2026-07-10T09:15:00+05:30",
                100,
                101,
                99,
                100,
                10,
            ],
            [
                "2026-07-10T09:20:00+05:30",
                101,
                102,
                100,
                101,
                20,
            ],
        ]
    )

    assert len(dataframe) == 2

    assert (
        dataframe.loc[
            0,
            "timestamp",
        ].utcoffset()
        is not None
    )

    assert (
        dataframe.loc[
            0,
            "timestamp",
        ]
        < dataframe.loc[
            1,
            "timestamp",
        ]
    )
