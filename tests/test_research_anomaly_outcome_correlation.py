from copy import deepcopy
from datetime import date, datetime
from types import SimpleNamespace

import pytest

from services.research_anomaly_outcome_correlation import (
    ResearchAnomalyOutcomeCorrelation,
)


def build_engine():
    return ResearchAnomalyOutcomeCorrelation()


def build_session(
    session_date="2026-07-14",
    codes=None,
):
    if codes is None:
        codes = ["ANOMALY_A"]

    return {
        "session_date": session_date,
        "research_anomaly_intelligence": {
            "anomaly_codes": codes,
        },
    }


def build_trade(
    session_date="2026-07-14",
    pnl=100,
    status="CLOSED",
):
    return {
        "status": status,
        "realized_pnl": pnl,
        "session_date": session_date,
    }


def correlation_by_code(
    result,
    code,
):
    return next(
        item
        for item in result[
            "anomaly_correlations"
        ]
        if item["code"] == code
    )


def test_empty_analysis_contract():
    result = build_engine().analyze(
        [],
        [],
    )

    assert result["status"] == "COMPLETED"
    assert result["read_only"] is True
    assert result["research_only"] is True
    assert (
        result["correlation_not_causation"]
        is True
    )
    assert result["sessions_observed"] == 0
    assert result["closed_trades_observed"] == 0
    assert result["unique_anomaly_codes"] == 0
    assert result["anomaly_correlations"] == []
    assert result["combination_correlations"] == []
    assert result["session_records"] == []
    assert result["closed_trade_records"] == []


def test_empty_analysis_observation():
    result = build_engine().analyze(
        [],
        [],
    )

    assert result["research_observations"] == [
        (
            "No research sessions were available "
            "for anomaly outcome correlation."
        )
    ]


@pytest.mark.parametrize(
    "sessions",
    [
        None,
    ],
)
def test_none_sessions_rejected(
    sessions,
):
    with pytest.raises(
        ValueError,
        match="sessions must not be None",
    ):
        build_engine().analyze(
            sessions,
            [],
        )


@pytest.mark.parametrize(
    "sessions",
    [
        {},
        "sessions",
        1,
        1.5,
        True,
        set(),
    ],
)
def test_invalid_sessions_type_rejected(
    sessions,
):
    with pytest.raises(
        ValueError,
        match=(
            "sessions must be a list or tuple"
        ),
    ):
        build_engine().analyze(
            sessions,
            [],
        )


def test_none_trades_rejected():
    with pytest.raises(
        ValueError,
        match="trades must not be None",
    ):
        build_engine().analyze(
            [],
            None,
        )


@pytest.mark.parametrize(
    "trades",
    [
        {},
        "trades",
        1,
        1.5,
        True,
        set(),
    ],
)
def test_invalid_trades_type_rejected(
    trades,
):
    with pytest.raises(
        ValueError,
        match=(
            "trades must be a list or tuple"
        ),
    ):
        build_engine().analyze(
            [],
            trades,
        )


def test_tuple_inputs_are_supported():
    result = build_engine().analyze(
        (
            build_session(),
        ),
        (
            build_trade(),
        ),
    )

    assert result["sessions_observed"] == 1
    assert result["closed_trades_observed"] == 1


def test_inputs_are_not_mutated():
    sessions = [
        build_session()
    ]

    trades = [
        build_trade()
    ]

    original_sessions = deepcopy(
        sessions
    )

    original_trades = deepcopy(
        trades
    )

    build_engine().analyze(
        sessions,
        trades,
    )

    assert sessions == original_sessions
    assert trades == original_trades


def test_result_is_independent_of_inputs():
    sessions = [
        build_session()
    ]

    trades = [
        build_trade()
    ]

    result = build_engine().analyze(
        sessions,
        trades,
    )

    sessions[0]["session_date"] = (
        "2099-01-01"
    )

    trades[0]["realized_pnl"] = 999999

    assert (
        result["session_records"][0][
            "session_date"
        ]
        == "2026-07-14"
    )

    assert (
        result["closed_trade_records"][0][
            "realized_pnl"
        ]
        == 100.0
    )


@pytest.mark.parametrize(
    "status",
    [
        "OPEN",
        "open",
        "Closed",
        "closed",
        "",
        None,
    ],
)
def test_only_exact_closed_status_is_eligible(
    status,
):
    result = build_engine().analyze(
        [
            build_session()
        ],
        [
            build_trade(
                status=status,
            )
        ],
    )

    assert (
        result["closed_trades_observed"]
        == 0
    )


def test_exact_closed_status_is_eligible():
    result = build_engine().analyze(
        [
            build_session()
        ],
        [
            build_trade(
                status="CLOSED",
            )
        ],
    )

    assert (
        result["closed_trades_observed"]
        == 1
    )


@pytest.mark.parametrize(
    "pnl",
    [
        None,
        "invalid",
        {},
        [],
        object(),
    ],
)
def test_invalid_realized_pnl_is_ignored(
    pnl,
):
    result = build_engine().analyze(
        [
            build_session()
        ],
        [
            build_trade(
                pnl=pnl,
            )
        ],
    )

    assert (
        result["closed_trades_observed"]
        == 0
    )


@pytest.mark.parametrize(
    ("pnl", "expected"),
    [
        (100, 100.0),
        (100.5, 100.5),
        ("100", 100.0),
        ("-25.5", -25.5),
        (0, 0.0),
    ],
)
def test_numeric_realized_pnl_is_normalized(
    pnl,
    expected,
):
    result = build_engine().analyze(
        [
            build_session()
        ],
        [
            build_trade(
                pnl=pnl,
            )
        ],
    )

    assert (
        result["closed_trade_records"][0][
            "realized_pnl"
        ]
        == expected
    )


@pytest.mark.parametrize(
    ("pnl", "outcome"),
    [
        (100, "WIN"),
        (-100, "LOSS"),
        (0, "FLAT"),
    ],
)
def test_trade_outcome_classification(
    pnl,
    outcome,
):
    result = build_engine().analyze(
        [
            build_session()
        ],
        [
            build_trade(
                pnl=pnl,
            )
        ],
    )

    assert (
        result["closed_trade_records"][0][
            "outcome"
        ]
        == outcome
    )


def test_non_dictionary_sessions_are_ignored():
    result = build_engine().analyze(
        [
            None,
            "invalid",
            123,
            build_session(),
        ],
        [],
    )

    assert result["sessions_observed"] == 1


def test_session_without_date_is_ignored():
    result = build_engine().analyze(
        [
            {
                "research_anomaly_intelligence": {
                    "anomaly_codes": ["A"]
                }
            }
        ],
        [],
    )

    assert result["sessions_observed"] == 0


@pytest.mark.parametrize(
    "codes",
    [
        None,
        "A",
        123,
        True,
        {},
    ],
)
def test_invalid_anomaly_code_container_normalizes_empty(
    codes,
):
    session = {
        "session_date": "2026-07-14",
        "research_anomaly_intelligence": {
            "anomaly_codes": codes,
        },
    }

    result = build_engine().analyze(
        [session],
        [],
    )

    assert result["unique_anomaly_codes"] == 0


def test_duplicate_anomaly_codes_are_deduplicated():
    result = build_engine().analyze(
        [
            build_session(
                codes=[
                    "A",
                    "A",
                    "B",
                    "B",
                ]
            )
        ],
        [],
    )

    assert result["unique_anomaly_codes"] == 2

    assert [
        item["code"]
        for item in result[
            "anomaly_correlations"
        ]
    ] == [
        "A",
        "B",
    ]


def test_anomaly_codes_are_trimmed_and_sorted():
    result = build_engine().analyze(
        [
            build_session(
                codes=[
                    " Z ",
                    "A",
                    "",
                    "   ",
                ]
            )
        ],
        [],
    )

    assert (
        result["session_records"][0][
            "anomaly_codes"
        ]
        == [
            "A",
            "Z",
        ]
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            "2026-07-14",
            "2026-07-14",
        ),
        (
            date(2026, 7, 14),
            "2026-07-14",
        ),
        (
            datetime(
                2026,
                7,
                14,
                10,
                30,
            ),
            "2026-07-14",
        ),
        (
            "2026-07-14T10:30:00",
            "2026-07-14",
        ),
        (
            "2026-07-14T10:30:00Z",
            "2026-07-14",
        ),
    ],
)
def test_session_date_normalization(
    value,
    expected,
):
    session = build_session()
    session["session_date"] = value

    result = build_engine().analyze(
        [session],
        [],
    )

    assert (
        result["session_records"][0][
            "session_date"
        ]
        == expected
    )


def test_session_date_can_use_date_field():
    session = build_session()
    session.pop("session_date")
    session["date"] = "2026-07-14"

    result = build_engine().analyze(
        [session],
        [],
    )

    assert result["sessions_observed"] == 1


def test_session_date_can_use_research_snapshot():
    session = {
        "research_snapshot": {
            "session_date": "2026-07-14"
        },
        "research_anomaly_intelligence": {
            "anomaly_codes": ["A"]
        },
    }

    result = build_engine().analyze(
        [session],
        [],
    )

    assert result["sessions_observed"] == 1


@pytest.mark.parametrize(
    "field",
    [
        "session_date",
        "closed_at",
        "exit_time",
        "updated_at",
        "timestamp",
    ],
)
def test_trade_date_supported_from_direct_fields(
    field,
):
    trade = {
        "status": "CLOSED",
        "realized_pnl": 100,
        field: "2026-07-14",
    }

    result = build_engine().analyze(
        [
            build_session()
        ],
        [trade],
    )

    assert result["closed_trades_observed"] == 1


@pytest.mark.parametrize(
    "field",
    [
        "session_date",
        "closed_at",
        "exit_time",
        "updated_at",
        "timestamp",
    ],
)
def test_trade_date_supported_from_metadata(
    field,
):
    trade = {
        "status": "CLOSED",
        "realized_pnl": 100,
        "metadata": {
            field: "2026-07-14"
        },
    }

    result = build_engine().analyze(
        [
            build_session()
        ],
        [trade],
    )

    assert result["closed_trades_observed"] == 1


@pytest.mark.parametrize(
    "field",
    [
        "session_date",
        "closed_at",
        "exit_time",
        "updated_at",
        "timestamp",
    ],
)
def test_trade_date_supported_from_decision_snapshot(
    field,
):
    trade = {
        "status": "CLOSED",
        "realized_pnl": 100,
        "metadata": {
            "decision_snapshot": {
                field: "2026-07-14"
            }
        },
    }

    result = build_engine().analyze(
        [
            build_session()
        ],
        [trade],
    )

    assert result["closed_trades_observed"] == 1


def test_trade_without_resolvable_date_is_ignored():
    result = build_engine().analyze(
        [
            build_session()
        ],
        [
            {
                "status": "CLOSED",
                "realized_pnl": 100,
            }
        ],
    )

    assert result["closed_trades_observed"] == 0


def test_object_trade_is_supported():
    trade = SimpleNamespace(
        status="CLOSED",
        realized_pnl=125,
        session_date="2026-07-14",
        metadata={},
    )

    result = build_engine().analyze(
        [
            build_session()
        ],
        [trade],
    )

    assert result["closed_trades_observed"] == 1

    assert (
        result["closed_trade_records"][0][
            "realized_pnl"
        ]
        == 125.0
    )


def test_win_loss_flat_metrics():
    sessions = [
        build_session()
    ]

    trades = [
        build_trade(pnl=100),
        build_trade(pnl=-50),
        build_trade(pnl=0),
    ]

    result = build_engine().analyze(
        sessions,
        trades,
    )

    item = correlation_by_code(
        result,
        "ANOMALY_A",
    )

    assert item["linked_closed_trades"] == 3
    assert item["wins"] == 1
    assert item["losses"] == 1
    assert item["flat"] == 1
    assert item["win_rate_percent"] == 33.3333
    assert item["loss_rate_percent"] == 33.3333
    assert item["flat_rate_percent"] == 33.3333


def test_realized_pnl_metrics():
    sessions = [
        build_session()
    ]

    trades = [
        build_trade(pnl=100),
        build_trade(pnl=-50),
        build_trade(pnl=25),
    ]

    result = build_engine().analyze(
        sessions,
        trades,
    )

    item = correlation_by_code(
        result,
        "ANOMALY_A",
    )

    assert item["total_realized_pnl"] == 75.0
    assert item["average_realized_pnl"] == 25.0
    assert item["minimum_realized_pnl"] == -50.0
    assert item["maximum_realized_pnl"] == 100.0


@pytest.mark.parametrize(
    ("pnl", "expected"),
    [
        (
            100,
            "POSITIVE_CORRELATION",
        ),
        (
            -100,
            "NEGATIVE_CORRELATION",
        ),
        (
            0,
            "NEUTRAL_CORRELATION",
        ),
    ],
)
def test_outcome_state(
    pnl,
    expected,
):
    result = build_engine().analyze(
        [
            build_session()
        ],
        [
            build_trade(
                pnl=pnl,
            )
        ],
    )

    item = correlation_by_code(
        result,
        "ANOMALY_A",
    )

    assert item["outcome_state"] == expected


def test_outcome_state_insufficient_without_linked_trades():
    result = build_engine().analyze(
        [
            build_session()
        ],
        [],
    )

    item = correlation_by_code(
        result,
        "ANOMALY_A",
    )

    assert (
        item["outcome_state"]
        == "INSUFFICIENT_DATA"
    )

    assert item["win_rate_percent"] is None
    assert item["loss_rate_percent"] is None
    assert item["flat_rate_percent"] is None
    assert item["total_realized_pnl"] == 0.0
    assert item["average_realized_pnl"] is None
    assert item["minimum_realized_pnl"] is None
    assert item["maximum_realized_pnl"] is None


def test_trade_links_only_to_matching_session_date():
    result = build_engine().analyze(
        [
            build_session(
                session_date="2026-07-14",
                codes=["A"],
            ),
            build_session(
                session_date="2026-07-15",
                codes=["B"],
            ),
        ],
        [
            build_trade(
                session_date="2026-07-14",
                pnl=100,
            ),
            build_trade(
                session_date="2026-07-15",
                pnl=-100,
            ),
        ],
    )

    assert (
        correlation_by_code(
            result,
            "A",
        )["average_realized_pnl"]
        == 100.0
    )

    assert (
        correlation_by_code(
            result,
            "B",
        )["average_realized_pnl"]
        == -100.0
    )


def test_multiple_trades_same_session_are_all_linked():
    result = build_engine().analyze(
        [
            build_session(
                codes=["A"]
            )
        ],
        [
            build_trade(pnl=100),
            build_trade(pnl=-50),
            build_trade(pnl=25),
        ],
    )

    item = correlation_by_code(
        result,
        "A",
    )

    assert item["linked_closed_trades"] == 3


def test_combination_requires_two_or_more_codes():
    result = build_engine().analyze(
        [
            build_session(
                codes=["A"]
            )
        ],
        [
            build_trade()
        ],
    )

    assert result["combination_correlations"] == []


def test_multi_anomaly_combination_is_correlated():
    result = build_engine().analyze(
        [
            build_session(
                codes=[
                    "B",
                    "A",
                ]
            )
        ],
        [
            build_trade(
                pnl=-100
            )
        ],
    )

    assert len(
        result["combination_correlations"]
    ) == 1

    item = result[
        "combination_correlations"
    ][0]

    assert item["codes"] == [
        "A",
        "B",
    ]

    assert item["linked_closed_trades"] == 1

    assert (
        item["outcome_state"]
        == "NEGATIVE_CORRELATION"
    )


def test_same_combination_across_sessions_is_aggregated():
    result = build_engine().analyze(
        [
            build_session(
                session_date="2026-07-14",
                codes=["A", "B"],
            ),
            build_session(
                session_date="2026-07-15",
                codes=["B", "A"],
            ),
        ],
        [
            build_trade(
                session_date="2026-07-14",
                pnl=100,
            ),
            build_trade(
                session_date="2026-07-15",
                pnl=-50,
            ),
        ],
    )

    item = result[
        "combination_correlations"
    ][0]

    assert item["anomaly_sessions"] == 2
    assert item["linked_closed_trades"] == 2
    assert item["total_realized_pnl"] == 50.0
    assert item["average_realized_pnl"] == 25.0


def test_no_anomaly_codes_observation():
    result = build_engine().analyze(
        [
            build_session(
                codes=[]
            )
        ],
        [],
    )

    assert (
        "No anomaly codes were observed across "
        "the available research sessions."
        in result["research_observations"]
    )


def test_no_closed_trades_observation():
    result = build_engine().analyze(
        [
            build_session()
        ],
        [],
    )

    assert (
        "No eligible closed trades with realized "
        "P&L were available for outcome correlation."
        in result["research_observations"]
    )


def test_negative_observation_uses_most_negative_average():
    result = build_engine().analyze(
        [
            build_session(
                session_date="2026-07-14",
                codes=["A"],
            ),
            build_session(
                session_date="2026-07-15",
                codes=["B"],
            ),
        ],
        [
            build_trade(
                session_date="2026-07-14",
                pnl=-50,
            ),
            build_trade(
                session_date="2026-07-15",
                pnl=-200,
            ),
        ],
    )

    assert (
        result["research_observations"][0]
        == (
            "B showed the most negative average "
            "closed-trade P&L among observed "
            "anomaly correlations."
        )
    )


def test_positive_observation_uses_most_positive_average():
    result = build_engine().analyze(
        [
            build_session(
                session_date="2026-07-14",
                codes=["A"],
            ),
            build_session(
                session_date="2026-07-15",
                codes=["B"],
            ),
        ],
        [
            build_trade(
                session_date="2026-07-14",
                pnl=50,
            ),
            build_trade(
                session_date="2026-07-15",
                pnl=200,
            ),
        ],
    )

    assert (
        result["research_observations"][0]
        == (
            "B showed the most positive average "
            "closed-trade P&L among observed "
            "anomaly correlations."
        )
    )


def test_recurring_combination_observation():
    result = build_engine().analyze(
        [
            build_session(
                session_date="2026-07-14",
                codes=["A", "B"],
            ),
            build_session(
                session_date="2026-07-15",
                codes=["A", "B"],
            ),
        ],
        [],
    )

    assert (
        "At least one multi-anomaly combination "
        "was observed across multiple sessions "
        "and linked to closed-trade outcomes."
        in result["research_observations"]
    )


def test_unlinked_anomaly_observation():
    result = build_engine().analyze(
        [
            build_session(
                session_date="2026-07-14",
                codes=["A"],
            )
        ],
        [
            build_trade(
                session_date="2026-07-15",
                pnl=100,
            )
        ],
    )

    assert (
        "Observed anomalies could not yet be "
        "linked to eligible closed trades."
        in result["research_observations"]
    )


def test_session_records_are_deterministically_sorted():
    result = build_engine().analyze(
        [
            build_session(
                session_date="2026-07-15",
            ),
            build_session(
                session_date="2026-07-14",
            ),
        ],
        [],
    )

    assert [
        item["session_date"]
        for item in result["session_records"]
    ] == [
        "2026-07-14",
        "2026-07-15",
    ]


def test_closed_trade_records_are_deterministically_sorted():
    result = build_engine().analyze(
        [
            build_session()
        ],
        [
            build_trade(
                session_date="2026-07-15",
            ),
            build_trade(
                session_date="2026-07-14",
            ),
        ],
    )

    assert [
        item["session_date"]
        for item in result[
            "closed_trade_records"
        ]
    ] == [
        "2026-07-14",
        "2026-07-15",
    ]


def test_anomaly_correlations_are_sorted_by_code():
    result = build_engine().analyze(
        [
            build_session(
                codes=[
                    "Z",
                    "A",
                    "M",
                ]
            )
        ],
        [],
    )

    assert [
        item["code"]
        for item in result[
            "anomaly_correlations"
        ]
    ] == [
        "A",
        "M",
        "Z",
    ]


def test_malformed_metadata_is_safe():
    trade = {
        "status": "CLOSED",
        "realized_pnl": 100,
        "metadata": "invalid",
        "session_date": "2026-07-14",
    }

    result = build_engine().analyze(
        [
            build_session()
        ],
        [trade],
    )

    assert result["closed_trades_observed"] == 1


def test_malformed_decision_snapshot_is_safe():
    trade = {
        "status": "CLOSED",
        "realized_pnl": 100,
        "metadata": {
            "decision_snapshot": "invalid"
        },
        "session_date": "2026-07-14",
    }

    result = build_engine().analyze(
        [
            build_session()
        ],
        [trade],
    )

    assert result["closed_trades_observed"] == 1


def test_service_has_no_execution_methods():
    engine = build_engine()

    forbidden_names = {
        "place_order",
        "execute_order",
        "submit_order",
        "authorize_trade",
        "reject_trade",
        "open_trade",
        "close_trade",
        "buy",
        "sell",
    }

    assert forbidden_names.isdisjoint(
        set(
            dir(engine)
        )
    )