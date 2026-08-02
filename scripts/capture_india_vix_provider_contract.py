"""Manual-only redacted India VIX provider-contract diagnostic."""
from __future__ import annotations
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from services.angel_instrument_master import AngelInstrumentMaster
from services.broker.shared_client import get_market_client
from services.diagnostics.india_vix_provider_contract_capture import capture_provider_contract, load_cached_master

def main(argv=None, *, master_factory=AngelInstrumentMaster, client_factory=get_market_client, clock=lambda: datetime.now(timezone.utc)) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-provider-read", action="store_true")
    parser.add_argument("--inspect-historical", action="store_true", help="permit at most one bounded daily schema inspection when previous close is absent")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if not args.confirm_provider_read:
        print("Diagnostic only: pass --confirm-provider-read to permit one master read and one FULL quote.", file=sys.stderr)
        return 2
    print("DIAGNOSTIC ONLY: no orders, no production configuration, redacted evidence only.", file=sys.stderr)
    output = args.output or Path("artifacts/diagnostics") / f"india-vix-provider-contract-{clock().strftime('%Y%m%dT%H%M%SZ')}.json"
    try:
        master = master_factory(); evidence = capture_provider_contract(master_fetcher=master.fetch_instruments, market_client=client_factory(), clock=clock, cached_records=load_cached_master(Path("data/instruments.json")), inspect_historical=args.inspect_historical)
        output.parent.mkdir(parents=True, exist_ok=True); output.write_text(evidence.to_json(), encoding="utf-8")
        print(evidence.to_json() if args.output is None else str(output))
        return 0 if evidence.status == "CONFIRMED" else 1
    except Exception as exc:
        print(f"Diagnostic failed safely: {type(exc).__name__}", file=sys.stderr); return 1
if __name__ == "__main__": raise SystemExit(main())
