import json
from datetime import (
    datetime,
    timezone,
)

import pytest

from services.market_cycle_journal import (
    MarketCycleJournal,
)


def make_pipeline_result():
    return {
        "decision": "NO_TRADE",
        "market_decision": "NO_TRADE",
        "direction": "BEARISH",
        "market_analysis": {
            "strategy": {
                "strategy": (
                    "TREND_CONTINUATION"
                ),
                "decision": "NO_TRADE",
                "confidence": 80,
                "risk_flags": [
                    (
                        "Conflicting bullish and "
                        "bearish chart patterns"
                    )
                ],
            },
            "regime": {
                "primary_regime": (
                    "TRENDING_BEARISH"
                ),
                "trend": "BEARISH",
                "confidence": 51,
            },
            "timeframe": {
                "overall_trend": "BEARISH",
                "alignment": "ALIGNED",
                "confidence": 75,
            },
            "technical": {
                "trend": "BEARISH",
                "score": -4,
                "confidence": 70,
            },
            "volume": {
                "bias": "NEUTRAL",
                "relative_volume": None,
                "volume_spike": False,
            },
        },
        "setup_trigger": {
            "status": "NO_SETUP",
            "direction": "BEARISH",
            "trigger_type": None,
            "trigger_price": None,
        },
        "contract": {},
        "session_status": {
            "status": "SESSION_VALID",
            "market_open": True,
        },
    }


def make_paper_result():
    return {
        "status": "SKIPPED",
        "opened": False,
        "trade_id": None,
        "reason": (
            "DECISION_NOT_TRADE_ALLOWED"
        ),
    }


def test_default_base_directory():
    journal = (
        MarketCycleJournal()
    )

    assert (
        journal.base_directory
        == MarketCycleJournal.DEFAULT_BASE_DIRECTORY
    )


def test_custom_base_directory(
    tmp_path,
):
    journal = (
        MarketCycleJournal(
            base_directory=tmp_path
        )
    )

    assert (
        journal.base_directory
        == tmp_path
    )


def test_build_entry_requires_pipeline_dictionary(
    tmp_path,
):
    journal = (
        MarketCycleJournal(
            base_directory=tmp_path
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "pipeline_result must be a dictionary"
        ),
    ):
        journal.build_entry(
            pipeline_result=None
        )


def test_build_entry_extracts_market_intelligence(
    tmp_path,
):
    journal = (
        MarketCycleJournal(
            base_directory=tmp_path
        )
    )

    entry = (
        journal.build_entry(
            pipeline_result=(
                make_pipeline_result()
            ),
            paper_trading_result=(
                make_paper_result()
            ),
            timestamp=(
                "2026-07-15T09:31:00+05:30"
            ),
        )
    )

    assert (
        entry["session_date"]
        == "2026-07-15"
    )

    assert (
        entry["decision"]
        == "NO_TRADE"
    )

    assert (
        entry["direction"]
        == "BEARISH"
    )

    assert (
        entry["strategy"]
        == "TREND_CONTINUATION"
    )

    assert (
        entry["confidence"]
        == 80
    )

    assert (
        entry["market_regime"]
        == "TRENDING_BEARISH"
    )

    assert (
        entry["regime_confidence"]
        == 51
    )

    assert (
        entry["setup_status"]
        == "NO_SETUP"
    )

    assert (
        entry["paper_trade_status"]
        == "SKIPPED"
    )

    assert (
        entry["paper_trade_opened"]
        is False
    )


def test_build_entry_preserves_risk_flags(
    tmp_path,
):
    pipeline_result = (
        make_pipeline_result()
    )

    journal = (
        MarketCycleJournal(
            base_directory=tmp_path
        )
    )

    entry = (
        journal.build_entry(
            pipeline_result=(
                pipeline_result
            ),
            timestamp=(
                "2026-07-15T09:31:00+05:30"
            ),
        )
    )

    assert entry["risk_flags"] == [
        (
            "Conflicting bullish and "
            "bearish chart patterns"
        )
    ]


def test_build_entry_deep_copies_risk_flags(
    tmp_path,
):
    pipeline_result = (
        make_pipeline_result()
    )

    journal = (
        MarketCycleJournal(
            base_directory=tmp_path
        )
    )

    entry = (
        journal.build_entry(
            pipeline_result=(
                pipeline_result
            ),
            timestamp=(
                "2026-07-15T09:31:00+05:30"
            ),
        )
    )

    pipeline_result[
        "market_analysis"
    ][
        "strategy"
    ][
        "risk_flags"
    ].append(
        "NEW_FLAG"
    )

    assert (
        "NEW_FLAG"
        not in entry["risk_flags"]
    )


def test_naive_datetime_defaults_to_utc(
    tmp_path,
):
    journal = (
        MarketCycleJournal(
            base_directory=tmp_path
        )
    )

    entry = (
        journal.build_entry(
            pipeline_result=(
                make_pipeline_result()
            ),
            timestamp=(
                datetime(
                    2026,
                    7,
                    15,
                    9,
                    31,
                )
            ),
        )
    )

    assert (
        entry["timestamp"]
        == (
            "2026-07-15T09:31:00+00:00"
        )
    )


def test_explicit_session_date_controls_directory(
    tmp_path,
):
    journal = (
        MarketCycleJournal(
            base_directory=tmp_path
        )
    )

    entry = (
        journal.build_entry(
            pipeline_result=(
                make_pipeline_result()
            ),
            timestamp=(
                "2026-07-14T23:30:00+00:00"
            ),
            session_date=(
                "2026-07-15"
            ),
        )
    )

    assert (
        entry["session_date"]
        == "2026-07-15"
    )


def test_invalid_session_date_rejected(
    tmp_path,
):
    journal = (
        MarketCycleJournal(
            base_directory=tmp_path
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "session_date must use YYYY-MM-DD format"
        ),
    ):
        journal.build_entry(
            pipeline_result=(
                make_pipeline_result()
            ),
            session_date="15-07-2026",
        )


def test_append_entry_requires_dictionary(
    tmp_path,
):
    journal = (
        MarketCycleJournal(
            base_directory=tmp_path
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "entry must be a dictionary"
        ),
    ):
        journal.append_entry(
            None
        )


def test_append_entry_requires_session_date(
    tmp_path,
):
    journal = (
        MarketCycleJournal(
            base_directory=tmp_path
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "entry must contain session_date"
        ),
    ):
        journal.append_entry(
            {
                "decision": "NO_TRADE",
            }
        )


def test_record_cycle_creates_jsonl_file(
    tmp_path,
):
    journal = (
        MarketCycleJournal(
            base_directory=tmp_path
        )
    )

    journal.record_cycle(
        pipeline_result=(
            make_pipeline_result()
        ),
        paper_trading_result=(
            make_paper_result()
        ),
        timestamp=(
            "2026-07-15T09:31:00+05:30"
        ),
    )

    journal_path = (
        tmp_path
        / "2026-07-15"
        / "cycles.jsonl"
    )

    assert (
        journal_path.exists()
    )


def test_record_cycle_writes_valid_json(
    tmp_path,
):
    journal = (
        MarketCycleJournal(
            base_directory=tmp_path
        )
    )

    journal.record_cycle(
        pipeline_result=(
            make_pipeline_result()
        ),
        timestamp=(
            "2026-07-15T09:31:00+05:30"
        ),
    )

    journal_path = (
        journal.get_journal_path(
            "2026-07-15"
        )
    )

    content = (
        journal_path
        .read_text(
            encoding="utf-8"
        )
        .strip()
    )

    entry = json.loads(
        content
    )

    assert (
        entry["decision"]
        == "NO_TRADE"
    )


def test_record_cycle_appends_one_line_per_cycle(
    tmp_path,
):
    journal = (
        MarketCycleJournal(
            base_directory=tmp_path
        )
    )

    journal.record_cycle(
        pipeline_result=(
            make_pipeline_result()
        ),
        timestamp=(
            "2026-07-15T09:31:00+05:30"
        ),
    )

    journal.record_cycle(
        pipeline_result=(
            make_pipeline_result()
        ),
        timestamp=(
            "2026-07-15T09:32:00+05:30"
        ),
    )

    journal_path = (
        journal.get_journal_path(
            "2026-07-15"
        )
    )

    lines = (
        journal_path
        .read_text(
            encoding="utf-8"
        )
        .splitlines()
    )

    assert (
        len(lines)
        == 2
    )


def test_read_entries_returns_all_cycles(
    tmp_path,
):
    journal = (
        MarketCycleJournal(
            base_directory=tmp_path
        )
    )

    journal.record_cycle(
        pipeline_result=(
            make_pipeline_result()
        ),
        timestamp=(
            "2026-07-15T09:31:00+05:30"
        ),
    )

    journal.record_cycle(
        pipeline_result=(
            make_pipeline_result()
        ),
        timestamp=(
            "2026-07-15T09:32:00+05:30"
        ),
    )

    entries = (
        journal.read_entries(
            "2026-07-15"
        )
    )

    assert (
        len(entries)
        == 2
    )

    assert (
        entries[0]["timestamp"]
        == (
            "2026-07-15T09:31:00+05:30"
        )
    )

    assert (
        entries[1]["timestamp"]
        == (
            "2026-07-15T09:32:00+05:30"
        )
    )


def test_read_entries_missing_journal_returns_empty(
    tmp_path,
):
    journal = (
        MarketCycleJournal(
            base_directory=tmp_path
        )
    )

    assert (
        journal.read_entries(
            "2026-07-15"
        )
        == []
    )


def test_invalid_json_line_is_rejected(
    tmp_path,
):
    journal = (
        MarketCycleJournal(
            base_directory=tmp_path
        )
    )

    journal_path = (
        journal.get_journal_path(
            "2026-07-15"
        )
    )

    journal_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    journal_path.write_text(
        "{INVALID JSON}\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match=(
            "Invalid market-cycle journal JSON"
        ),
    ):
        journal.read_entries(
            "2026-07-15"
        )


def test_metadata_is_deep_copied(
    tmp_path,
):
    metadata = {
        "entry_point": (
            "live_option_decision_nifty.py"
        ),
        "tags": [
            "LIVE",
        ],
    }

    journal = (
        MarketCycleJournal(
            base_directory=tmp_path
        )
    )

    entry = (
        journal.build_entry(
            pipeline_result=(
                make_pipeline_result()
            ),
            timestamp=(
                "2026-07-15T09:31:00+05:30"
            ),
            metadata=metadata,
        )
    )

    metadata["tags"].append(
        "CHANGED"
    )

    assert (
        entry["metadata"]["tags"]
        == [
            "LIVE",
        ]
    )


def test_rupee_symbol_metadata_persists_as_utf8(
    tmp_path,
):
    journal = (
        MarketCycleJournal(
            base_directory=tmp_path
        )
    )

    journal.record_cycle(
        pipeline_result=(
            make_pipeline_result()
        ),
        timestamp=(
            "2026-07-15T09:31:00+05:30"
        ),
        metadata={
            "capital": "₹10,000.00",
        },
    )

    journal_path = (
        journal.get_journal_path(
            "2026-07-15"
        )
    )

    content = (
        journal_path
        .read_text(
            encoding="utf-8"
        )
    )

    assert (
        "₹10,000.00"
        in content
    )


def test_timestamp_datetime_with_timezone_preserved(
    tmp_path,
):
    timestamp = datetime(
        2026,
        7,
        15,
        9,
        31,
        tzinfo=timezone.utc,
    )

    journal = (
        MarketCycleJournal(
            base_directory=tmp_path
        )
    )

    entry = (
        journal.build_entry(
            pipeline_result=(
                make_pipeline_result()
            ),
            timestamp=timestamp,
        )
    )

    assert (
        entry["timestamp"]
        == (
            "2026-07-15T09:31:00+00:00"
        )
    )