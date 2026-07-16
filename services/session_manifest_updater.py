import json
from pathlib import Path


def _update_manifest(
    session_date,
    key,
    value,
):
    try:

        manifest = (
            Path("data")
            / "market_journal"
            / str(session_date)
            / "session_manifest.json"
        )

        if not manifest.exists():
            return

        data = json.loads(
            manifest.read_text(
                encoding="utf-8"
            )
        )

        if isinstance(
            data.get(key),
            list,
        ):
            data[key].append(value)
        else:
            data[key] = value

        manifest.write_text(
            json.dumps(
                data,
                indent=4,
            ),
            encoding="utf-8",
        )

    except Exception:
        pass


def update_snapshot(
    session_date,
    snapshot_path,
):
    _update_manifest(
        session_date,
        "snapshots",
        snapshot_path,
    )


def update_log(
    session_date,
    log_path,
):
    _update_manifest(
        session_date,
        "logs",
        log_path,
    )


def update_paper_trade(
    session_date,
    trade_path,
):
    _update_manifest(
        session_date,
        "paper_trades",
        trade_path,
    )


def update_research(
    session_date,
    report_path,
):
    _update_manifest(
        session_date,
        "research_reports",
        report_path,
    )


def update_market_summary(
    session_date,
    summary_path,
):
    _update_manifest(
        session_date,
        "market_summary",
        summary_path,
    )


def mark_session_complete(
    session_date,
):
    _update_manifest(
        session_date,
        "status",
        "COMPLETED",
    )