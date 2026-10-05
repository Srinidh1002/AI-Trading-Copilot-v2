"""Build a read-only five-market PAPER certification report snapshot."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from services.certification.five_market_certification_report_builder_v1 import (
    build_five_market_certification_report_v1,
)
from services.certification.five_market_certification_report_writer_v1 import (
    write_five_market_certification_report_v1,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    report = build_five_market_certification_report_v1(root)

    if args.output:
        path, digest = write_five_market_certification_report_v1(
            report,
            args.output,
        )
        print(f"REPORT={path}")
        print(f"REPORT_SHA256={digest}")
    else:
        print(
            json.dumps(
                report.to_dict(),
                sort_keys=True,
                indent=2,
                allow_nan=False,
            )
        )

    print("REPORT_MODE=READ_ONLY")
    print("TRADING_STATE_MUTATIONS=NONE")
    print("LIVE_BROKER_ORDERS=PROHIBITED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
