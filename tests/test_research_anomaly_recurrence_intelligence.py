"""
Behavioral tests for
ResearchAnomalyRecurrenceIntelligence.

READ ONLY.
RESEARCH ONLY.

No execution authority.
No broker integration.
No order placement.
No paper-trade mutation.
No strategy tuning.
"""

from copy import deepcopy

import pytest

from services.research_anomaly_recurrence_intelligence import (
    ResearchAnomalyRecurrenceIntelligence,
)


def build_engine():
    return ResearchAnomalyRecurrenceIntelligence()


def build_session(
    session_date,
    codes=None,
    *,
    decision="HOLD",
    direction="BULLISH",
    regime="TRENDING",
    trade_ready=False,
    highest_severity="HIGH",
):
    codes = list(codes or [])

    return {
        "session_date": session_date,
        "research_snapshot": {
            "final_decision": decision,
            "final_direction": direction,
            "final_regime": regime,
            "trade_ready_observed": trade_ready,
        },
        "research_anomaly_intelligence": {
            "anomaly_codes": codes,
            "highest_severity": highest_severity,
        },
    }


def build_recurrence_sessions():
    return [
        build_session(
            "2026-07-10",
            ["CONFIDENCE_RISK_DIVERGENCE"],
        ),
        build_session(
            "2026-07-11",
            [
                "CONFIDENCE_RISK_DIVERGENCE",
                "TRADE_READY_RISK_CONTRADICTION",
            ],
            decision="TRADE_READY",
            direction="BEARISH",
            regime="VOLATILE",
            trade_ready=True,
            highest_severity="CRITICAL",
        ),
        build_session(
            "2026-07-13",
            ["CONFIDENCE_RISK_DIVERGENCE"],
            direction="BEARISH",
            regime="VOLATILE",
        ),
        build_session(
            "2026-07-14",
            [
                "CONFIDENCE_RISK_DIVERGENCE",
                "TRADE_READY_RISK_CONTRADICTION",
            ],
            decision="TRADE_READY",
            direction="BEARISH",
            regime="VOLATILE",
            trade_ready=True,
            highest_severity="CRITICAL",
        ),
    ]


def recurrence_by_code(result, code):
    return next(
        item
        for item in result["anomaly_recurrence"]
        if item["code"] == code
    )


def test_empty_input_completed():
    result = build_engine().analyze([])

    assert result["status"] == "COMPLETED"


def test_empty_input_read_only():
    result = build_engine().analyze([])

    assert result["read_only"] is True


def test_empty_input_research_only():
    result = build_engine().analyze([])

    assert result["research_only"] is True


def test_empty_input_zero_sessions():
    result = build_engine().analyze([])

    assert result["sessions_observed"] == 0


def test_empty_input_zero_anomaly_sessions():
    result = build_engine().analyze([])

    assert result["sessions_with_anomalies"] == 0


def test_empty_input_zero_unique_codes():
    result = build_engine().analyze([])

    assert result["unique_anomaly_codes"] == 0


def test_empty_input_recurrence_empty():
    result = build_engine().analyze([])

    assert result["anomaly_recurrence"] == []


def test_empty_input_combinations_empty():
    result = build_engine().analyze([])

    assert result["combination_recurrence"] == []


def test_empty_input_pattern_unavailable():
    result = build_engine().analyze([])

    assert (
        result["current_pattern"]["pattern_state"]
        == "UNAVAILABLE"
    )


def test_empty_input_has_observation():
    result = build_engine().analyze([])

    assert result["research_observations"]


@pytest.mark.parametrize(
    "invalid",
    [
        None,
        {},
        "invalid",
        123,
        True,
        (),
    ],
)
def test_invalid_input_normalized(invalid):
    result = build_engine().analyze(invalid)

    assert result["status"] == "COMPLETED"
    assert result["sessions_observed"] == 0


def test_non_dictionary_sessions_are_ignored():
    result = build_engine().analyze(
        [
            None,
            [],
            "invalid",
            build_session(
                "2026-07-14",
                ["ANOMALY_A"],
            ),
        ]
    )

    assert result["sessions_observed"] == 1


def test_input_not_mutated():
    source = build_recurrence_sessions()
    original = deepcopy(source)

    build_engine().analyze(source)

    assert source == original


def test_recurrence_fixture_has_four_sessions():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    assert result["sessions_observed"] == 4


def test_recurrence_fixture_all_sessions_have_anomalies():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    assert result["sessions_with_anomalies"] == 4


def test_recurrence_fixture_has_two_unique_codes():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    assert result["unique_anomaly_codes"] == 2


def test_confidence_risk_sessions_count():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    item = recurrence_by_code(
        result,
        "CONFIDENCE_RISK_DIVERGENCE",
    )

    assert item["sessions"] == 4


def test_confidence_risk_frequency():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    item = recurrence_by_code(
        result,
        "CONFIDENCE_RISK_DIVERGENCE",
    )

    assert (
        item["session_frequency_percent"]
        == 100.0
    )


def test_confidence_risk_first_session():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    item = recurrence_by_code(
        result,
        "CONFIDENCE_RISK_DIVERGENCE",
    )

    assert item["first_session"] == "2026-07-10"


def test_confidence_risk_last_session():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    item = recurrence_by_code(
        result,
        "CONFIDENCE_RISK_DIVERGENCE",
    )

    assert item["last_session"] == "2026-07-14"


def test_confidence_risk_trade_ready_sessions():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    item = recurrence_by_code(
        result,
        "CONFIDENCE_RISK_DIVERGENCE",
    )

    assert item["trade_ready_sessions"] == 2


def test_confidence_risk_occurrence_indices():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    item = recurrence_by_code(
        result,
        "CONFIDENCE_RISK_DIVERGENCE",
    )

    assert item["occurrence_indices"] == [
        0,
        1,
        2,
        3,
    ]


def test_confidence_risk_longest_streak():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    item = recurrence_by_code(
        result,
        "CONFIDENCE_RISK_DIVERGENCE",
    )

    assert item["longest_streak"] == {
        "sessions": 4,
        "start_index": 0,
        "end_index": 3,
    }


def test_trade_ready_risk_sessions_count():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    item = recurrence_by_code(
        result,
        "TRADE_READY_RISK_CONTRADICTION",
    )

    assert item["sessions"] == 2


def test_trade_ready_risk_frequency():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    item = recurrence_by_code(
        result,
        "TRADE_READY_RISK_CONTRADICTION",
    )

    assert (
        item["session_frequency_percent"]
        == 50.0
    )


def test_trade_ready_risk_trade_ready_sessions():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    item = recurrence_by_code(
        result,
        "TRADE_READY_RISK_CONTRADICTION",
    )

    assert item["trade_ready_sessions"] == 2


def test_trade_ready_risk_occurrence_indices():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    item = recurrence_by_code(
        result,
        "TRADE_READY_RISK_CONTRADICTION",
    )

    assert item["occurrence_indices"] == [1, 3]


def test_non_consecutive_occurrences_streak_one():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    item = recurrence_by_code(
        result,
        "TRADE_READY_RISK_CONTRADICTION",
    )

    assert item["longest_streak"] == {
        "sessions": 1,
        "start_index": 1,
        "end_index": 1,
    }


def test_regime_distribution():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    item = recurrence_by_code(
        result,
        "CONFIDENCE_RISK_DIVERGENCE",
    )

    assert item["regime_distribution"] == [
        {
            "value": "VOLATILE",
            "count": 3,
        },
        {
            "value": "TRENDING",
            "count": 1,
        },
    ]


def test_decision_distribution():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    item = recurrence_by_code(
        result,
        "CONFIDENCE_RISK_DIVERGENCE",
    )

    assert item["decision_distribution"] == [
        {
            "value": "HOLD",
            "count": 2,
        },
        {
            "value": "TRADE_READY",
            "count": 2,
        },
    ]


def test_direction_distribution():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    item = recurrence_by_code(
        result,
        "CONFIDENCE_RISK_DIVERGENCE",
    )

    assert item["direction_distribution"] == [
        {
            "value": "BEARISH",
            "count": 3,
        },
        {
            "value": "BULLISH",
            "count": 1,
        },
    ]


def test_exact_combination_sessions_two():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    assert (
        result["combination_recurrence"][0][
            "sessions"
        ]
        == 2
    )


def test_exact_combination_frequency_fifty_percent():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    assert (
        result["combination_recurrence"][0][
            "session_frequency_percent"
        ]
        == 50.0
    )


def test_exact_combination_codes_sorted():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    assert result["combination_recurrence"][0][
        "codes"
    ] == [
        "CONFIDENCE_RISK_DIVERGENCE",
        "TRADE_READY_RISK_CONTRADICTION",
    ]


def test_current_pattern_date():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    assert (
        result["current_pattern"]["session_date"]
        == "2026-07-14"
    )


def test_current_pattern_detected():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    assert (
        result["current_pattern"][
            "anomaly_detected"
        ]
        is True
    )


def test_current_pattern_historical_sessions():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    assert (
        result["current_pattern"][
            "historical_sessions"
        ]
        == 3
    )


def test_current_pattern_has_no_new_codes():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    assert (
        result["current_pattern"][
            "new_anomaly_codes"
        ]
        == []
    )


def test_current_pattern_recurring_codes():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    assert result["current_pattern"][
        "recurring_anomaly_codes"
    ] == [
        "CONFIDENCE_RISK_DIVERGENCE",
        "TRADE_READY_RISK_CONTRADICTION",
    ]


def test_current_exact_combination_historical_sessions():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    assert (
        result["current_pattern"][
            "exact_combination_historical_sessions"
        ]
        == 1
    )


def test_current_pattern_exact_recurring():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    assert (
        result["current_pattern"]["pattern_state"]
        == "EXACT_PATTERN_RECURRING"
    )


def test_single_first_anomaly_is_new_pattern():
    result = build_engine().analyze(
        [
            build_session(
                "2026-07-14",
                ["ANOMALY_A"],
            )
        ]
    )

    assert (
        result["current_pattern"]["pattern_state"]
        == "NEW_PATTERN"
    )


def test_current_no_anomaly_state():
    result = build_engine().analyze(
        [
            build_session(
                "2026-07-13",
                ["ANOMALY_A"],
            ),
            build_session(
                "2026-07-14",
                [],
            ),
        ]
    )

    assert (
        result["current_pattern"]["pattern_state"]
        == "NO_CURRENT_ANOMALY"
    )


def test_recurring_single_anomaly_state():
    result = build_engine().analyze(
        [
            build_session(
                "2026-07-13",
                ["ANOMALY_A"],
            ),
            build_session(
                "2026-07-14",
                ["ANOMALY_A"],
            ),
        ]
    )

    assert (
        result["current_pattern"]["pattern_state"]
        == "RECURRING_ANOMALIES"
    )


def test_mixed_new_and_recurring_state():
    result = build_engine().analyze(
        [
            build_session(
                "2026-07-13",
                ["ANOMALY_A"],
            ),
            build_session(
                "2026-07-14",
                [
                    "ANOMALY_A",
                    "ANOMALY_B",
                ],
            ),
        ]
    )

    assert (
        result["current_pattern"]["pattern_state"]
        == "MIXED_NEW_AND_RECURRING"
    )


def test_exact_combination_recurring_state():
    result = build_engine().analyze(
        [
            build_session(
                "2026-07-12",
                [
                    "ANOMALY_A",
                    "ANOMALY_B",
                ],
            ),
            build_session(
                "2026-07-13",
                ["ANOMALY_A"],
            ),
            build_session(
                "2026-07-14",
                [
                    "ANOMALY_B",
                    "ANOMALY_A",
                ],
            ),
        ]
    )

    assert (
        result["current_pattern"]["pattern_state"]
        == "EXACT_PATTERN_RECURRING"
    )


def test_exact_combination_order_independent():
    result = build_engine().analyze(
        [
            build_session(
                "2026-07-13",
                [
                    "ANOMALY_A",
                    "ANOMALY_B",
                ],
            ),
            build_session(
                "2026-07-14",
                [
                    "ANOMALY_B",
                    "ANOMALY_A",
                ],
            ),
        ]
    )

    assert (
        result["current_pattern"][
            "exact_combination_historical_sessions"
        ]
        == 1
    )


def test_different_recurring_combination_state():
    result = build_engine().analyze(
        [
            build_session(
                "2026-07-11",
                ["ANOMALY_A"],
            ),
            build_session(
                "2026-07-12",
                ["ANOMALY_B"],
            ),
            build_session(
                "2026-07-14",
                [
                    "ANOMALY_A",
                    "ANOMALY_B",
                ],
            ),
        ]
    )

    assert (
        result["current_pattern"]["pattern_state"]
        == "RECURRING_ANOMALIES"
    )


def test_duplicate_direct_codes_deduplicated():
    result = build_engine().analyze(
        [
            build_session(
                "2026-07-14",
                [
                    "ANOMALY_A",
                    "ANOMALY_A",
                ],
            )
        ]
    )

    assert result["session_records"][0][
        "anomaly_codes"
    ] == ["ANOMALY_A"]


def test_codes_from_anomaly_records_are_read():
    session = build_session(
        "2026-07-14",
        [],
    )

    session[
        "research_anomaly_intelligence"
    ] = {
        "anomalies": [
            {
                "code": "ANOMALY_A",
            },
            {
                "code": "ANOMALY_B",
            },
        ]
    }

    result = build_engine().analyze([session])

    assert result["session_records"][0][
        "anomaly_codes"
    ] == [
        "ANOMALY_A",
        "ANOMALY_B",
    ]


def test_direct_and_record_codes_deduplicated():
    session = build_session(
        "2026-07-14",
        ["ANOMALY_A"],
    )

    session[
        "research_anomaly_intelligence"
    ]["anomalies"] = [
        {
            "code": "ANOMALY_A",
        }
    ]

    result = build_engine().analyze([session])

    assert result["session_records"][0][
        "anomaly_codes"
    ] == ["ANOMALY_A"]


@pytest.mark.parametrize(
    "invalid_code",
    [
        None,
        "",
        " ",
        "UNKNOWN",
        "UNAVAILABLE",
        "NONE",
        "NULL",
        123,
        True,
        [],
        {},
    ],
)
def test_invalid_codes_ignored(invalid_code):
    session = build_session(
        "2026-07-14",
        [
            invalid_code,
            "ANOMALY_A",
        ],
    )

    result = build_engine().analyze([session])

    assert result["session_records"][0][
        "anomaly_codes"
    ] == ["ANOMALY_A"]


def test_codes_are_case_normalized():
    result = build_engine().analyze(
        [
            build_session(
                "2026-07-14",
                [" anomaly_a "],
            )
        ]
    )

    assert result["session_records"][0][
        "anomaly_codes"
    ] == ["ANOMALY_A"]


def test_snapshot_categories_case_normalized():
    result = build_engine().analyze(
        [
            build_session(
                "2026-07-14",
                ["ANOMALY_A"],
                decision=" hold ",
                direction=" bearish ",
                regime=" volatile ",
            )
        ]
    )

    record = result["session_records"][0]

    assert record["decision"] == "HOLD"
    assert record["direction"] == "BEARISH"
    assert record["regime"] == "VOLATILE"


def test_trade_ready_requires_boolean_true():
    session = build_session(
        "2026-07-14",
        ["ANOMALY_A"],
    )

    session["research_snapshot"][
        "trade_ready_observed"
    ] = 1

    result = build_engine().analyze([session])

    assert (
        result["session_records"][0][
            "trade_ready_observed"
        ]
        is False
    )


@pytest.mark.parametrize(
    "value",
    [
        "true",
        "TRUE",
        1,
        0,
        [],
        {},
    ],
)
def test_non_boolean_trade_ready_is_false(value):
    session = build_session(
        "2026-07-14",
        ["ANOMALY_A"],
    )

    session["research_snapshot"][
        "trade_ready_observed"
    ] = value

    result = build_engine().analyze([session])

    assert (
        result["session_records"][0][
            "trade_ready_observed"
        ]
        is False
    )


def test_true_trade_ready_preserved():
    result = build_engine().analyze(
        [
            build_session(
                "2026-07-14",
                ["ANOMALY_A"],
                trade_ready=True,
            )
        ]
    )

    assert (
        result["session_records"][0][
            "trade_ready_observed"
        ]
        is True
    )


def test_alternative_anomaly_source_supported():
    session = build_session(
        "2026-07-14",
        [],
    )

    session.pop(
        "research_anomaly_intelligence"
    )

    session["anomaly_intelligence"] = {
        "anomaly_codes": ["ANOMALY_A"],
    }

    result = build_engine().analyze([session])

    assert result["session_records"][0][
        "anomaly_codes"
    ] == ["ANOMALY_A"]


def test_research_anomalies_source_supported():
    session = build_session(
        "2026-07-14",
        [],
    )

    session.pop(
        "research_anomaly_intelligence"
    )

    session["research_anomalies"] = {
        "anomaly_codes": ["ANOMALY_A"],
    }

    result = build_engine().analyze([session])

    assert result["session_records"][0][
        "anomaly_codes"
    ] == ["ANOMALY_A"]


def test_top_level_anomaly_codes_supported():
    session = {
        "session_date": "2026-07-14",
        "anomaly_codes": ["ANOMALY_A"],
    }

    result = build_engine().analyze([session])

    assert result["session_records"][0][
        "anomaly_codes"
    ] == ["ANOMALY_A"]


def test_alternative_snapshot_supported():
    session = {
        "session_date": "2026-07-14",
        "snapshot": {
            "final_decision": "HOLD",
            "final_direction": "BEARISH",
            "final_regime": "VOLATILE",
            "trade_ready_observed": False,
        },
        "anomaly_codes": ["ANOMALY_A"],
    }

    result = build_engine().analyze([session])

    record = result["session_records"][0]

    assert record["decision"] == "HOLD"
    assert record["direction"] == "BEARISH"
    assert record["regime"] == "VOLATILE"


def test_date_fallback_supported():
    session = build_session(
        "2026-07-14",
        ["ANOMALY_A"],
    )

    session["date"] = session.pop(
        "session_date"
    )

    result = build_engine().analyze([session])

    assert (
        result["session_records"][0][
            "session_date"
        ]
        == "2026-07-14"
    )


def test_missing_date_allowed():
    session = build_session(
        "2026-07-14",
        ["ANOMALY_A"],
    )

    session.pop("session_date")

    result = build_engine().analyze([session])

    assert (
        result["session_records"][0][
            "session_date"
        ]
        is None
    )


def test_recurrence_sorted_by_count_then_code():
    result = build_engine().analyze(
        [
            build_session(
                "2026-07-10",
                ["B"],
            ),
            build_session(
                "2026-07-11",
                ["A"],
            ),
            build_session(
                "2026-07-12",
                ["B"],
            ),
            build_session(
                "2026-07-13",
                ["A"],
            ),
            build_session(
                "2026-07-14",
                ["C"],
            ),
        ]
    )

    assert [
        item["code"]
        for item in result[
            "anomaly_recurrence"
        ]
    ] == [
        "A",
        "B",
        "C",
    ]


def test_distribution_sorted_by_count_then_value():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    item = recurrence_by_code(
        result,
        "CONFIDENCE_RISK_DIVERGENCE",
    )

    assert [
        row["value"]
        for row in item["regime_distribution"]
    ] == [
        "VOLATILE",
        "TRENDING",
    ]


def test_percentage_rounding():
    result = build_engine().analyze(
        [
            build_session(
                "2026-07-10",
                ["ANOMALY_A"],
            ),
            build_session(
                "2026-07-11",
                [],
            ),
            build_session(
                "2026-07-12",
                [],
            ),
        ]
    )

    item = recurrence_by_code(
        result,
        "ANOMALY_A",
    )

    assert (
        item["session_frequency_percent"]
        == 33.3333
    )


def test_combination_requires_at_least_two_codes():
    result = build_engine().analyze(
        [
            build_session(
                "2026-07-14",
                ["ANOMALY_A"],
            )
        ]
    )

    assert result["combination_recurrence"] == []


def test_combination_first_and_last_sessions():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    item = result["combination_recurrence"][0]

    assert item["first_session"] == "2026-07-11"
    assert item["last_session"] == "2026-07-14"


def test_observation_identifies_most_recurrent():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    assert (
        "CONFIDENCE_RISK_DIVERGENCE was the "
        "most recurrent observed anomaly across "
        "4 session(s)."
        in result["research_observations"]
    )


def test_observation_identifies_repeated_combination():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    assert (
        "At least one multi-anomaly combination "
        "recurred across multiple research sessions."
        in result["research_observations"]
    )


def test_observation_identifies_exact_recurring_pattern():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    assert (
        "The current session's exact anomaly "
        "combination has occurred previously."
        in result["research_observations"]
    )


def test_no_anomaly_sessions_observation():
    result = build_engine().analyze(
        [
            build_session(
                "2026-07-13",
                [],
            ),
            build_session(
                "2026-07-14",
                [],
            ),
        ]
    )

    assert result["research_observations"] == [
        "No archived research session contained "
        "a cross-signal anomaly."
    ]


def test_observations_deduplicated():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    observations = result[
        "research_observations"
    ]

    assert len(observations) == len(
        set(observations)
    )


def test_analyse_alias_matches_analyze():
    source = build_recurrence_sessions()
    engine = build_engine()

    assert engine.analyse(source) == engine.analyze(
        source
    )


def test_result_independent_after_source_mutation():
    source = build_recurrence_sessions()

    result = build_engine().analyze(source)

    source[0][
        "research_anomaly_intelligence"
    ]["anomaly_codes"].clear()

    assert result["sessions_with_anomalies"] == 4
    assert result["unique_anomaly_codes"] == 2


def test_session_records_are_independent():
    source = build_recurrence_sessions()

    result = build_engine().analyze(source)

    source[0]["research_snapshot"][
        "final_regime"
    ] = "CHANGED"

    assert (
        result["session_records"][0]["regime"]
        == "TRENDING"
    )


def test_public_result_contains_expected_sections():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    expected = {
        "status",
        "read_only",
        "research_only",
        "sessions_observed",
        "sessions_with_anomalies",
        "unique_anomaly_codes",
        "anomaly_recurrence",
        "combination_recurrence",
        "current_pattern",
        "research_observations",
        "session_records",
    }

    assert expected.issubset(result.keys())


def test_recurrence_record_schema():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    for item in result["anomaly_recurrence"]:
        assert set(item.keys()) == {
            "code",
            "sessions",
            "session_frequency_percent",
            "first_session",
            "last_session",
            "trade_ready_sessions",
            "regime_distribution",
            "decision_distribution",
            "direction_distribution",
            "occurrence_indices",
            "longest_streak",
        }


def test_combination_record_schema():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    for item in result[
        "combination_recurrence"
    ]:
        assert set(item.keys()) == {
            "codes",
            "sessions",
            "session_frequency_percent",
            "first_session",
            "last_session",
        }


def test_current_pattern_schema():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    assert set(
        result["current_pattern"].keys()
    ) == {
        "session_date",
        "anomaly_detected",
        "anomaly_codes",
        "historical_sessions",
        "new_anomaly_codes",
        "recurring_anomaly_codes",
        "exact_combination_historical_sessions",
        "pattern_state",
    }


def test_session_record_schema():
    result = build_engine().analyze(
        build_recurrence_sessions()
    )

    for record in result["session_records"]:
        assert set(record.keys()) == {
            "index",
            "session_date",
            "anomaly_detected",
            "anomaly_count",
            "anomaly_codes",
            "highest_severity",
            "decision",
            "direction",
            "regime",
            "trade_ready_observed",
        }


def test_consecutive_streak_resets():
    result = build_engine().analyze(
        [
            build_session(
                "2026-07-10",
                ["A"],
            ),
            build_session(
                "2026-07-11",
                ["A"],
            ),
            build_session(
                "2026-07-12",
                [],
            ),
            build_session(
                "2026-07-13",
                ["A"],
            ),
            build_session(
                "2026-07-14",
                ["A"],
            ),
            build_session(
                "2026-07-15",
                ["A"],
            ),
        ]
    )

    item = recurrence_by_code(result, "A")

    assert item["longest_streak"] == {
        "sessions": 3,
        "start_index": 3,
        "end_index": 5,
    }


def test_equal_streak_keeps_first_longest_streak():
    result = build_engine().analyze(
        [
            build_session(
                "2026-07-10",
                ["A"],
            ),
            build_session(
                "2026-07-11",
                ["A"],
            ),
            build_session(
                "2026-07-12",
                [],
            ),
            build_session(
                "2026-07-13",
                ["A"],
            ),
            build_session(
                "2026-07-14",
                ["A"],
            ),
        ]
    )

    item = recurrence_by_code(result, "A")

    assert item["longest_streak"] == {
        "sessions": 2,
        "start_index": 0,
        "end_index": 1,
    }