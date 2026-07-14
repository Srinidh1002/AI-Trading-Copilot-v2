import pytest

from services.blocker_intelligence import (
    BlockerIntelligence,
)


def make_entry(
    *,
    decision="NO_TRADE",
    risk_flags=None,
    setup_reasons=None,
    blockers=None,
    timestamp=None,
):
    entry = {
        "decision": decision,
        "timestamp": timestamp,
    }

    if risk_flags is not None:
        entry["risk_flags"] = risk_flags

    if setup_reasons is not None:
        entry["setup_reasons"] = setup_reasons

    if blockers is not None:
        entry["blockers"] = blockers

    return entry


def make_engine():
    return BlockerIntelligence()


def test_none_entries_returns_empty_analysis():
    result = make_engine().analyze(
        None
    )

    assert result["cycles_observed"] == 0
    assert result["blocked_cycles"] == 0


def test_invalid_entries_rejected():
    with pytest.raises(
        ValueError,
        match="entries must be a list or tuple",
    ):
        make_engine().analyze(
            {
                "decision": "NO_TRADE",
            }
        )


def test_non_dictionary_entries_ignored():
    result = make_engine().analyze(
        [
            None,
            "bad",
            123,
            make_entry(),
        ]
    )

    assert result["cycles_observed"] == 1


def test_risk_flags_are_blockers():
    result = make_engine().analyze(
        [
            make_entry(
                risk_flags=[
                    "Conflicting patterns",
                ]
            ),
        ]
    )

    state = result["cycle_states"][0]

    assert state["blocked"] is True
    assert state["blocker_count"] == 1


def test_setup_reasons_are_blockers():
    result = make_engine().analyze(
        [
            make_entry(
                setup_reasons=[
                    "Breakout not confirmed",
                ]
            ),
        ]
    )

    assert (
        result["cycle_states"][0]["blockers"]
        == [
            "Breakout not confirmed",
        ]
    )


def test_explicit_blockers_supported():
    result = make_engine().analyze(
        [
            make_entry(
                blockers=[
                    "Low volume",
                ]
            ),
        ]
    )

    assert (
        result["cycle_states"][0]["blockers"]
        == [
            "Low volume",
        ]
    )


def test_duplicate_blockers_removed_case_insensitively():
    result = make_engine().analyze(
        [
            make_entry(
                risk_flags=[
                    "Low Volume",
                ],
                blockers=[
                    "low volume",
                ],
            ),
        ]
    )

    assert (
        result["cycle_states"][0]["blocker_count"]
        == 1
    )


def test_blocked_cycle_counted():
    result = make_engine().analyze(
        [
            make_entry(
                risk_flags=["A"]
            ),
            make_entry(),
            make_entry(
                risk_flags=["B"]
            ),
        ]
    )

    assert result["blocked_cycles"] == 2
    assert result["unblocked_cycles"] == 1


def test_trade_ready_cycles_counted():
    result = make_engine().analyze(
        [
            make_entry(),
            make_entry(
                decision="TRADE_READY"
            ),
            make_entry(
                decision="TRADE_READY"
            ),
        ]
    )

    assert result["trade_ready_cycles"] == 2


def test_blocker_statistics_created():
    result = make_engine().analyze(
        [
            make_entry(
                risk_flags=["A"]
            ),
            make_entry(
                risk_flags=["A"]
            ),
            make_entry(
                risk_flags=["B"]
            ),
        ]
    )

    statistics = result[
        "blocker_statistics"
    ]

    assert statistics[0]["blocker"] == "A"
    assert statistics[0]["occurrences"] == 2
    assert statistics[0]["blocked_cycles"] == 2


def test_persistence_percent_calculated():
    result = make_engine().analyze(
        [
            make_entry(
                risk_flags=["A"]
            ),
            make_entry(
                risk_flags=["A"]
            ),
            make_entry(),
            make_entry(),
        ]
    )

    assert (
        result[
            "blocker_statistics"
        ][
            0
        ][
            "persistence_percent"
        ]
        == 50.0
    )


def test_blocker_transition_created():
    result = make_engine().analyze(
        [
            make_entry(
                risk_flags=["A"]
            ),
            make_entry(
                risk_flags=["B"]
            ),
        ]
    )

    assert (
        result[
            "blocker_transitions"
        ][
            0
        ]
        == {
            "from": "A",
            "to": "B",
            "count": 1,
        }
    )


def test_unchanged_blocker_state_not_transition():
    result = make_engine().analyze(
        [
            make_entry(
                risk_flags=["A"]
            ),
            make_entry(
                risk_flags=["A"]
            ),
        ]
    )

    assert (
        result["blocker_transitions"]
        == []
    )


def test_transition_to_none_created():
    result = make_engine().analyze(
        [
            make_entry(
                risk_flags=["A"]
            ),
            make_entry(),
        ]
    )

    assert (
        result[
            "blocker_transitions"
        ][
            0
        ][
            "to"
        ]
        == "NONE"
    )


def test_blocker_cleared_before_trade_ready():
    result = make_engine().analyze(
        [
            make_entry(
                risk_flags=["A", "B"]
            ),
            make_entry(
                decision="TRADE_READY",
                risk_flags=[],
            ),
        ]
    )

    cleared = result[
        "cleared_before_trade_ready"
    ]

    assert {
        item["blocker"]
        for item in cleared
    } == {
        "A",
        "B",
    }


def test_persistent_blocker_not_counted_as_cleared():
    result = make_engine().analyze(
        [
            make_entry(
                risk_flags=["A", "B"]
            ),
            make_entry(
                decision="TRADE_READY",
                risk_flags=["A"],
            ),
        ]
    )

    cleared = result[
        "cleared_before_trade_ready"
    ]

    assert cleared == [
        {
            "blocker": "B",
            "count": 1,
        }
    ]


def test_clearance_only_measured_before_trade_ready():
    result = make_engine().analyze(
        [
            make_entry(
                risk_flags=["A"]
            ),
            make_entry(),
        ]
    )

    assert (
        result[
            "cleared_before_trade_ready"
        ]
        == []
    )


def test_longest_blocker_streak_created():
    result = make_engine().analyze(
        [
            make_entry(
                risk_flags=["A"]
            ),
            make_entry(
                risk_flags=["A"]
            ),
            make_entry(
                risk_flags=["A"]
            ),
            make_entry(),
        ]
    )

    streak = result[
        "longest_blocker_streak"
    ]

    assert streak["blocker"] == "A"
    assert streak["cycles"] == 3
    assert streak["start_index"] == 0
    assert streak["end_index"] == 2


def test_longest_streak_resets_after_clearance():
    result = make_engine().analyze(
        [
            make_entry(
                risk_flags=["A"]
            ),
            make_entry(
                risk_flags=["A"]
            ),
            make_entry(),
            make_entry(
                risk_flags=["A"]
            ),
        ]
    )

    assert (
        result[
            "longest_blocker_streak"
        ][
            "cycles"
        ]
        == 2
    )


def test_final_blocker_state_none():
    result = make_engine().analyze(
        [
            make_entry(
                risk_flags=["A"]
            ),
            make_entry(),
        ]
    )

    final_state = result[
        "final_blocker_state"
    ]

    assert final_state["blocked"] is False
    assert final_state["state"] == "NONE"


def test_final_blocker_state_blocked():
    result = make_engine().analyze(
        [
            make_entry(
                risk_flags=["A"]
            ),
        ]
    )

    final_state = result[
        "final_blocker_state"
    ]

    assert final_state["blocked"] is True
    assert final_state["state"] == "A"


def test_string_risk_flag_supported():
    result = make_engine().analyze(
        [
            make_entry(
                risk_flags="A"
            ),
        ]
    )

    assert (
        result["cycle_states"][0]["blockers"]
        == ["A"]
    )


def test_nested_market_decision_risk_flags_supported():
    entry = make_entry()

    entry["market_decision"] = {
        "risk_flags": [
            "A",
            "B",
        ],
    }

    result = make_engine().analyze(
        [
            entry,
        ]
    )

    assert (
        result["cycle_states"][0]["blocker_count"]
        == 2
    )


def test_nested_setup_reasons_supported():
    entry = make_entry()

    entry["setup"] = {
        "reasons": [
            "Confirmation missing",
        ],
    }

    result = make_engine().analyze(
        [
            entry,
        ]
    )

    assert (
        result["cycle_states"][0]["blockers"]
        == [
            "Confirmation missing",
        ]
    )


def test_whitespace_normalized():
    result = make_engine().analyze(
        [
            make_entry(
                risk_flags=[
                    "  Low   volume  ",
                ]
            ),
        ]
    )

    assert (
        result["cycle_states"][0]["blockers"]
        == [
            "Low volume",
        ]
    )


def test_timestamp_preserved():
    result = make_engine().analyze(
        [
            make_entry(
                timestamp="T1"
            ),
        ]
    )

    assert (
        result["cycle_states"][0]["timestamp"]
        == "T1"
    )


def test_session_date_preserved():
    result = make_engine().analyze(
        [],
        session_date="2026-07-15",
    )

    assert (
        result["session_date"]
        == "2026-07-15"
    )


def test_result_is_read_only():
    result = make_engine().analyze(
        []
    )

    assert result["read_only"] is True


def test_input_not_modified():
    entries = [
        make_entry(
            risk_flags=["A"]
        ),
    ]

    original = [
        make_entry(
            risk_flags=["A"]
        ),
    ]

    make_engine().analyze(
        entries
    )

    assert entries == original