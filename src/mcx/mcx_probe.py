"""FYERS MCX live probe — READ ONLY.

No trades.
No PAPER state writes.
No certification mutation.
No Angel fallback.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

from dotenv import load_dotenv

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_HERE)

if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mcx.mcx_contracts import PRODUCTS
from mcx.mcx_fyers_runtime_v2 import (
    build_mcx_fyers_runtime_from_env_v2,
)


SUPPORTED = (
    "CRUDEOILM",
    "GOLDM",
    "NATGASMINI",
)


def build_runtime():
    load_dotenv()

    log_dir = os.path.join(
        "logs",
        "mcx_fyers_probe",
    )

    os.makedirs(
        log_dir,
        exist_ok=True,
    )

    try:
        return (
            build_mcx_fyers_runtime_from_env_v2(
                log_path=log_dir,
            )
        )
    except Exception as exc:
        print(
            "FYERS_RUNTIME_UNAVAILABLE: "
            f"{type(exc).__name__}: "
            f"{str(exc)[:120]}"
        )
        return None


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--product",
        default="CRUDEOILM",
        choices=SUPPORTED,
    )

    args = parser.parse_args()

    product = args.product.upper()

    print("=" * 100)
    print("MCX FYERS PROBE — read only")
    print("=" * 100)

    runtime = build_runtime()

    if runtime is None:
        return 2

    spec = PRODUCTS[product]

    print(f"Product: {product}")
    print(f"Provider: {runtime.provider}")
    print(f"Data only: {runtime.data_only}")

    print(
        f"trading_unit={spec['trading_unit']} "
        f"cash_multiplier={spec['cash_multiplier']} "
        f"tick={spec['tick_size']} "
        f"strike_step={spec['strike_interval']}"
    )

    identity = runtime.identity.resolve_active(
        product
    )

    print(
        "Identity:",
        identity.get("status"),
    )

    if identity.get("status") != "OK":
        return 3

    fut = identity["futures"]

    print(
        "Future:",
        fut.get("symbol"),
        "expiry=",
        fut.get("expiry"),
    )

    print(
        "Option expiry:",
        identity.get("option_expiry"),
    )

    chain = runtime.native_chain.build(
        product,
        window_steps=10,
    )

    print(
        "Chain:",
        chain.get("status"),
    )

    if chain.get("status") != "OK":
        print(
            "reason=",
            chain.get("reason"),
        )
        return 4

    print(
        "future_ltp=",
        chain.get("future_ltp"),
        "ATM=",
        chain.get("atm"),
    )

    print(
        "PCR_OI=",
        chain.get("pcr_oi"),
        "max_pain=",
        chain.get("max_pain"),
    )

    print(
        "native_option_chain_requests=",
        chain.get(
            "option_chain_request_count"
        ),
    )

    print(
        "per_contract_depth_requests=",
        chain.get(
            "per_contract_depth_requests"
        ),
    )

    print(
        "fetched_at=",
        datetime.now().isoformat(
            timespec="seconds"
        ),
    )

    print("BROKER_SUBMISSION=false")
    print("LIVE_EXECUTION=false")
    print("CERTIFICATION_COUNTER_DELTA=0")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
