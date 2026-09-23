"""Tar one day's runtime evidence into _evidence/{date}/evidence_{date}.tar.gz."""
from __future__ import annotations
import argparse, os, tarfile
from datetime import date

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TRADES = os.path.join(_REPO, "data", "paper_trades")
_LOGS = os.path.join(_REPO, "logs")
_AUDIT = os.path.join(_REPO, "docs", "daily_audit")
_OUT = os.path.join(_REPO, "_evidence")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=date.today().strftime("%Y%m%d"))
    args = ap.parse_args()
    os.makedirs(os.path.join(_OUT, args.date), exist_ok=True)
    tar_path = os.path.join(_OUT, args.date, f"evidence_{args.date}.tar.gz")
    with tarfile.open(tar_path, "w:gz") as tar:
        for path, name in ((_TRADES, "paper_trades"), (_LOGS, "logs"), (_AUDIT, "daily_audit")):
            if os.path.isdir(path):
                tar.add(path, arcname=name)
    print(f"wrote {tar_path}")
    print(f"size  {os.path.getsize(tar_path)} bytes")


if __name__ == "__main__":
    main()
