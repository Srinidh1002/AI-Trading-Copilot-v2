from datetime import datetime
from pathlib import Path
import json


def create_session_manifest(
    session_date,
    underlying,
):
    """
    Create one manifest file for the trading session.

    If it already exists, leave it unchanged.
    """

    session_path = (
        Path("data")
        / "market_journal"
        / str(session_date)
    )

    session_path.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest = (
        session_path
        / "session_manifest.json"
    )

    if manifest.exists():
        return manifest

    data = {
        "session_date": str(session_date),
        "underlying": underlying,
        "created_at": datetime.now().isoformat(),
        "snapshots": [],
        "paper_trades": [],
        "logs": [],
        "research_reports": [],
        "market_summary": None,
        "status": "ACTIVE",
    }

    manifest.write_text(
        json.dumps(
            data,
            indent=4,
        ),
        encoding="utf-8",
    )

    return manifest