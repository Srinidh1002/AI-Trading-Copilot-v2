"""
Tests for the inspect_audit_log CLI tool.
"""

import json
import sys
from io import StringIO
from pathlib import Path
from subprocess import run
from unittest.mock import (
    MagicMock,
    patch,
)

import pytest

import inspect_audit_log


def make_record(
    logged_at,
    final_decision,
    underlying,
    spot_price=None,
    event_count=5,
):
    """
    Helper to create a complete audit record.
    """

    return {
        "logged_at": logged_at,
        "final_decision": final_decision,
        "event_count": event_count,
        "metadata": {
            "exchange": "NSE",
            "symboltoken": "99926000",
            "underlying": underlying,
            "spot_price": (
                spot_price
                if spot_price is not None
                else 24206.50
            ),
            "final_decision": final_decision,
        },
        "audit_trail": {
            "events": [
                {
                    "sequence": i,
                    "stage": "STAGE",
                    "status": "COMPLETED",
                    "decision": final_decision,
                    "reasons": [],
                    "details": {},
                }
                for i in range(event_count)
            ],
            "final_decision": final_decision,
            "event_count": event_count,
        },
    }


def test_format_timestamp():
    """
    Timestamp formatting works correctly.
    """

    result = inspect_audit_log.format_timestamp(
        "2026-07-12T14:30:00+00:00"
    )

    assert result == "2026-07-12T14:30:00"

    # Short timestamp
    result = inspect_audit_log.format_timestamp(
        "short"
    )

    assert result == "short"

    # Empty
    result = inspect_audit_log.format_timestamp(
        None
    )

    assert result == "N/A"


def test_format_record():
    """
    Record formatting extracts correct fields.
    """

    record = make_record(
        "2026-07-12T14:30:00+00:00",
        "TRADE_ALLOWED",
        "NIFTY",
        spot_price=24206.50,
        event_count=7,
    )

    formatted = (
        inspect_audit_log.format_record(
            record
        )
    )

    assert (
        formatted["logged_at"]
        == "2026-07-12T14:30:00"
    )

    assert formatted["underlying"] == "NIFTY"

    assert formatted["spot_price"] == 24206.50

    assert (
        formatted["decision"]
        == "TRADE_ALLOWED"
    )

    assert formatted["events"] == 7


def test_cli_default_limit(
    tmp_path,
):
    """
    CLI defaults to showing 10 records.
    """

    file_path = (
        tmp_path / "audit.jsonl"
    )

    # Create 15 records
    with file_path.open(
        mode="w",
        encoding="utf-8",
    ) as f:
        for i in range(15):
            record = make_record(
                f"2026-07-12T10:{i:02d}:00+00:00",
                "TRADE_ALLOWED",
                "NIFTY",
            )
            f.write(
                json.dumps(record) + "\n"
            )

    # Mock argv to call with default limit
    with patch.object(
        sys,
        "argv",
        [
            "inspect_audit_log.py",
            "--file",
            str(file_path),
        ],
    ):

        with patch(
            "sys.stdout",
            new=StringIO(),
        ) as mock_stdout:

            exit_code = (
                inspect_audit_log.main()
            )

            output = mock_stdout.getvalue()

    assert exit_code == 0

    # Should show 10 records (last 10 of 15)
    lines = output.strip().split("\n")

    # Count data rows (skip header/footer/blank)
    data_rows = [
        l
        for l in lines
        if l
        and not l.startswith("=")
        and "Logged At" not in l
        and "Recent Audit" not in l
    ]

    assert len(data_rows) == 10


def test_cli_custom_limit(
    tmp_path,
):
    """
    CLI respects --limit argument.
    """

    file_path = (
        tmp_path / "audit.jsonl"
    )

    # Create 10 records
    with file_path.open(
        mode="w",
        encoding="utf-8",
    ) as f:
        for i in range(10):
            record = make_record(
                f"2026-07-12T10:{i:02d}:00+00:00",
                "TRADE_ALLOWED",
                "NIFTY",
            )
            f.write(
                json.dumps(record) + "\n"
            )

    with patch.object(
        sys,
        "argv",
        [
            "inspect_audit_log.py",
            "--file",
            str(file_path),
            "--limit",
            "3",
        ],
    ):

        with patch(
            "sys.stdout",
            new=StringIO(),
        ) as mock_stdout:

            exit_code = (
                inspect_audit_log.main()
            )

            output = mock_stdout.getvalue()

    assert exit_code == 0

    lines = output.strip().split("\n")

    data_rows = [
        l
        for l in lines
        if l
        and not l.startswith("=")
        and "Logged At" not in l
        and "Recent Audit" not in l
    ]

    assert len(data_rows) == 3


def test_cli_filter_by_decision(
    tmp_path,
):
    """
    CLI --decision filter works.
    """

    file_path = (
        tmp_path / "audit.jsonl"
    )

    records = [
        make_record(
            "2026-07-12T10:00:00+00:00",
            "NO_TRADE",
            "NIFTY",
        ),
        make_record(
            "2026-07-12T10:05:00+00:00",
            "TRADE_ALLOWED",
            "NIFTY",
        ),
        make_record(
            "2026-07-12T10:10:00+00:00",
            "NO_TRADE",
            "NIFTY",
        ),
    ]

    with file_path.open(
        mode="w",
        encoding="utf-8",
    ) as f:
        for record in records:
            f.write(
                json.dumps(record) + "\n"
            )

    with patch.object(
        sys,
        "argv",
        [
            "inspect_audit_log.py",
            "--file",
            str(file_path),
            "--decision",
            "TRADE_ALLOWED",
        ],
    ):

        with patch(
            "sys.stdout",
            new=StringIO(),
        ) as mock_stdout:

            exit_code = (
                inspect_audit_log.main()
            )

            output = mock_stdout.getvalue()

    assert exit_code == 0

    assert "TRADE_ALLOWED" in output

    # Should only have 1 data row
    lines = output.strip().split("\n")

    data_rows = [
        l
        for l in lines
        if l
        and not l.startswith("=")
        and "Logged At" not in l
        and "Recent Audit" not in l
    ]

    assert len(data_rows) == 1


def test_cli_filter_by_underlying(
    tmp_path,
):
    """
    CLI --underlying filter works.
    """

    file_path = (
        tmp_path / "audit.jsonl"
    )

    records = [
        make_record(
            "2026-07-12T10:00:00+00:00",
            "TRADE_ALLOWED",
            "NIFTY",
        ),
        make_record(
            "2026-07-12T10:05:00+00:00",
            "TRADE_ALLOWED",
            "BANKNIFTY",
        ),
        make_record(
            "2026-07-12T10:10:00+00:00",
            "TRADE_ALLOWED",
            "NIFTY",
        ),
    ]

    with file_path.open(
        mode="w",
        encoding="utf-8",
    ) as f:
        for record in records:
            f.write(
                json.dumps(record) + "\n"
            )

    with patch.object(
        sys,
        "argv",
        [
            "inspect_audit_log.py",
            "--file",
            str(file_path),
            "--underlying",
            "BANKNIFTY",
        ],
    ):

        with patch(
            "sys.stdout",
            new=StringIO(),
        ) as mock_stdout:

            exit_code = (
                inspect_audit_log.main()
            )

            output = mock_stdout.getvalue()

    assert exit_code == 0

    assert "BANKNIFTY" in output

    lines = output.strip().split("\n")

    data_rows = [
        l
        for l in lines
        if l
        and not l.startswith("=")
        and "Logged At" not in l
        and "Recent Audit" not in l
    ]

    assert len(data_rows) == 1


def test_cli_summary_mode(
    tmp_path,
):
    """
    CLI --summary shows statistics.
    """

    file_path = (
        tmp_path / "audit.jsonl"
    )

    records = [
        make_record(
            "2026-07-12T10:00:00+00:00",
            "NO_TRADE",
            "NIFTY",
        ),
        make_record(
            "2026-07-12T10:05:00+00:00",
            "TRADE_ALLOWED",
            "NIFTY",
        ),
        make_record(
            "2026-07-12T10:10:00+00:00",
            "TRADE_ALLOWED",
            "BANKNIFTY",
        ),
    ]

    with file_path.open(
        mode="w",
        encoding="utf-8",
    ) as f:
        for record in records:
            f.write(
                json.dumps(record) + "\n"
            )

    with patch.object(
        sys,
        "argv",
        [
            "inspect_audit_log.py",
            "--file",
            str(file_path),
            "--summary",
        ],
    ):

        with patch(
            "sys.stdout",
            new=StringIO(),
        ) as mock_stdout:

            exit_code = (
                inspect_audit_log.main()
            )

            output = mock_stdout.getvalue()

    assert exit_code == 0

    assert "Total Records: 3" in output

    assert "NO_TRADE: 1" in output

    assert "TRADE_ALLOWED: 2" in output

    assert "NIFTY: 2" in output

    assert "BANKNIFTY: 1" in output

    assert "Audit Summary Statistics" in output


def test_cli_empty_log(
    tmp_path,
):
    """
    CLI handles empty log gracefully.
    """

    file_path = (
        tmp_path / "audit.jsonl"
    )

    # Create empty file
    file_path.write_text(
        "",
        encoding="utf-8",
    )

    with patch.object(
        sys,
        "argv",
        [
            "inspect_audit_log.py",
            "--file",
            str(file_path),
        ],
    ):

        with patch(
            "sys.stdout",
            new=StringIO(),
        ) as mock_stdout:

            exit_code = (
                inspect_audit_log.main()
            )

            output = mock_stdout.getvalue()

    assert exit_code == 0

    assert (
        "No audit records found."
        in output
    )


def test_cli_missing_file(
    tmp_path,
):
    """
    CLI handles missing file gracefully.
    """

    file_path = (
        tmp_path / "missing.jsonl"
    )

    with patch.object(
        sys,
        "argv",
        [
            "inspect_audit_log.py",
            "--file",
            str(file_path),
        ],
    ):

        with patch(
            "sys.stdout",
            new=StringIO(),
        ) as mock_stdout:

            exit_code = (
                inspect_audit_log.main()
            )

            output = mock_stdout.getvalue()

    assert exit_code == 0

    assert (
        "No audit records found."
        in output
    )


def test_cli_malformed_json(
    tmp_path,
):
    """
    CLI reports malformed JSON with error exit.
    """

    file_path = (
        tmp_path / "audit.jsonl"
    )

    # Write malformed JSON
    file_path.write_text(
        "not-valid-json\n",
        encoding="utf-8",
    )

    with patch.object(
        sys,
        "argv",
        [
            "inspect_audit_log.py",
            "--file",
            str(file_path),
        ],
    ):

        with patch(
            "sys.stderr",
            new=StringIO(),
        ) as mock_stderr:

            exit_code = (
                inspect_audit_log.main()
            )

            error_output = (
                mock_stderr.getvalue()
            )

    assert exit_code != 0

    assert "Error:" in error_output


def test_cli_invalid_timestamp(
    tmp_path,
):
    """
    CLI reports invalid timestamp with error exit.
    """

    with patch.object(
        sys,
        "argv",
        [
            "inspect_audit_log.py",
            "--start-time",
            "not-a-timestamp",
        ],
    ):

        with patch(
            "sys.stderr",
            new=StringIO(),
        ) as mock_stderr:

            exit_code = (
                inspect_audit_log.main()
            )

            error_output = (
                mock_stderr.getvalue()
            )

    assert exit_code == 1

    assert "Invalid timestamp format" in error_output


def test_cli_help():
    """
    CLI --help shows usage.
    """

    with patch.object(
        sys,
        "argv",
        [
            "inspect_audit_log.py",
            "--help",
        ],
    ):

        with pytest.raises(
            SystemExit,
        ) as exc_info:

            inspect_audit_log.parse_arguments()

        # argparse exits with 0 for --help
        assert exc_info.value.code == 0


def test_cli_combined_filters(
    tmp_path,
):
    """
    CLI with multiple filters works correctly.
    """

    file_path = (
        tmp_path / "audit.jsonl"
    )

    records = [
        make_record(
            "2026-07-12T10:00:00+00:00",
            "NO_TRADE",
            "NIFTY",
        ),
        make_record(
            "2026-07-12T10:05:00+00:00",
            "TRADE_ALLOWED",
            "NIFTY",
        ),
        make_record(
            "2026-07-12T10:10:00+00:00",
            "TRADE_ALLOWED",
            "BANKNIFTY",
        ),
        make_record(
            "2026-07-12T10:15:00+00:00",
            "TRADE_ALLOWED",
            "NIFTY",
        ),
    ]

    with file_path.open(
        mode="w",
        encoding="utf-8",
    ) as f:
        for record in records:
            f.write(
                json.dumps(record) + "\n"
            )

    with patch.object(
        sys,
        "argv",
        [
            "inspect_audit_log.py",
            "--file",
            str(file_path),
            "--decision",
            "TRADE_ALLOWED",
            "--underlying",
            "NIFTY",
            "--limit",
            "5",
        ],
    ):

        with patch(
            "sys.stdout",
            new=StringIO(),
        ) as mock_stdout:

            exit_code = (
                inspect_audit_log.main()
            )

            output = mock_stdout.getvalue()

    assert exit_code == 0

    lines = output.strip().split("\n")

    data_rows = [
        l
        for l in lines
        if l
        and not l.startswith("=")
        and "Logged At" not in l
        and "Recent Audit" not in l
    ]

    # Should have 2 TRADE_ALLOWED NIFTY records
    assert len(data_rows) == 2
