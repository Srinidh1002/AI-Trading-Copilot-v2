from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from services.certification.task9_session_independent_readiness import run_readiness


IST = ZoneInfo("Asia/Kolkata")


def _row(value):
    return [value.isoformat(), 100, 101, 99, 100, 10]


def test_offline_readiness_uses_only_injected_completed_session_evidence(tmp_path):
    calls = []

    def reader(**kwargs):
        calls.append(kwargs)
        def interval(minutes, final_hour, final_minute):
            current = datetime(2026, 8, 10, 9, 15, tzinfo=IST)
            final = datetime(2026, 8, 10, final_hour, final_minute, tzinfo=IST)
            rows = []
            while current <= final:
                rows.append(_row(current))
                current = current + timedelta(minutes=minutes)
            return rows
        return {
            "5m": interval(5, 15, 25),
            "15m": interval(15, 15, 15),
            "1h": [_row(datetime(2026, 8, 10, hour, 0, tzinfo=IST)) for hour in range(9, 15)],
            "1d": [
                _row(datetime(2026, 8, 7, 0, 0, tzinfo=IST)),
            ],
        }

    result = run_readiness(trading_date=date(2026, 8, 10), completed_session_reader=reader, persistence_root=tmp_path / "historical")
    assert result["status"] == "PASSED"
    assert result["network_access_used"] is False
    assert len(calls) == 2
    assert result["reader_calls"] == 2
    assert result["receipt_count"] == 1


def test_readiness_fingerprints_supplied_live_state_and_rejects_overlap_or_mutation(tmp_path):
    live = tmp_path / "official-live"
    live.mkdir()
    sentinel = live / "state.json"
    sentinel.write_text('{"state":"unchanged"}', encoding="utf-8")

    def reader(**_):
        return {
            "5m": [_row(datetime(2026, 8, 10, 9, 15, tzinfo=IST)), *[_row(datetime(2026, 8, 10, 9, minute, tzinfo=IST)) for minute in range(20, 60, 5)], *[_row(datetime(2026, 8, 10, hour, minute, tzinfo=IST)) for hour in range(10, 15) for minute in range(0, 60, 5)], _row(datetime(2026, 8, 10, 15, 0, tzinfo=IST)), _row(datetime(2026, 8, 10, 15, 5, tzinfo=IST)), _row(datetime(2026, 8, 10, 15, 10, tzinfo=IST)), _row(datetime(2026, 8, 10, 15, 15, tzinfo=IST)), _row(datetime(2026, 8, 10, 15, 20, tzinfo=IST)), _row(datetime(2026, 8, 10, 15, 25, tzinfo=IST))],
            "15m": [_row(datetime(2026, 8, 10, hour, minute, tzinfo=IST)) for hour in range(9, 16) for minute in ((15, 30, 45) if hour == 9 else (0, 15, 30, 45)) if not (hour == 15 and minute > 15)],
            "1h": [_row(datetime(2026, 8, 10, hour, 0, tzinfo=IST)) for hour in range(9, 15)],
            "1d": [_row(datetime(2026, 8, 7, 0, 0, tzinfo=IST))],
        }

    overlap = run_readiness(trading_date=date(2026, 8, 10), completed_session_reader=reader, persistence_root=live, live_state_paths={"progress": live})
    assert overlap["status"] == "FAILED"

    result = run_readiness(trading_date=date(2026, 8, 10), completed_session_reader=reader, persistence_root=tmp_path / "replay", live_state_paths={"progress": live}, report_publisher=lambda _: sentinel.write_text('{"state":"mutated"}', encoding="utf-8"))
    assert result["status"] == "FAILED"
    assert result["live_state_unchanged"] is False
