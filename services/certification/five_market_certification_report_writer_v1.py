"""Immutable writer for five-market PAPER certification report snapshots."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from services.contracts.five_market_certification_report_v1 import (
    FiveMarketCertificationReportV1,
)


def write_five_market_certification_report_v1(
    report: FiveMarketCertificationReportV1,
    output_path: str | Path,
) -> tuple[Path, str]:
    if type(report) is not FiveMarketCertificationReportV1:
        raise TypeError("report")
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(
            f"immutable certification report already exists: {path}"
        )
    payload = (
        json.dumps(
            report.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    path.write_bytes(payload)
    return path, hashlib.sha256(payload).hexdigest()
