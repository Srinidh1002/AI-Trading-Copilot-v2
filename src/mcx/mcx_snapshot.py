"""FYERS MCX combined snapshot — READ ONLY.

Composes FYERS identity + FYERS native chain + external context.
Does not submit trades and does not mutate PAPER certification.
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

from mcx.mcx_external_context import (
    fetch_context,
    print_context,
)
from mcx.mcx_fyers_runtime_v2 import (
    build_mcx_fyers_runtime_from_env_v2,
)
from mcx.mcx_chain import print_chain


SUPPORTED = (
    "CRUDEOILM",
    "GOLDM",
    "SILVERM",
)


def build_runtime():
    load_dotenv()

    log_dir = os.path.join(
        "logs",
        "mcx_fyers_snapshot",
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


def read_summary(chain, ctx):
    rows = []

    if chain.get("status") == "OK":
        pcr = chain.get("pcr_oi")
        mp = chain.get("max_pain")
        atm = chain.get("atm")

        pcr_read = "NEUTRAL"

        if pcr is not None:
            if pcr > 1.3:
                pcr_read = "BULLISH"
            elif pcr < 0.7:
                pcr_read = "BEARISH"
            elif pcr > 1.1:
                pcr_read = "WEAK_BULLISH"
            elif pcr < 0.9:
                pcr_read = "WEAK_BEARISH"

        rows.append(
            (
                "Chain PCR_OI",
                str(pcr),
                pcr_read,
            )
        )

        rows.append(
            (
                "Max Pain vs ATM",
                f"{mp} vs {atm}",
                "INFORMATIONAL",
            )
        )

    if ctx.get("status") == "OK":
        rows.append(
            (
                "External composite",
                str(
                    ctx.get(
                        "composite_move_1d_pct"
                    )
                ),
                ctx.get(
                    "composite_regime",
                    "UNKNOWN",
                ),
            )
        )

    return rows


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
    print("MCX FYERS SNAPSHOT — read only")
    print(
        "Run at",
        datetime.now().isoformat(
            timespec="seconds"
        ),
    )
    print("=" * 100)

    runtime = build_runtime()

    if runtime is None:
        return 2

    identity = runtime.identity.resolve_active(
        product
    )

    print(
        "provider=",
        runtime.provider,
        "identity=",
        identity.get("status"),
    )

    chain = runtime.native_chain.build(
        product,
        window_steps=10,
    )

    print()
    print("PART 1 — FYERS NATIVE CHAIN")
    print_chain(chain)

    print()
    print("PART 2 — EXTERNAL CONTEXT")

    ctx = fetch_context(product)
    print_context(ctx)

    print()
    print(
        "PART 3 — INFORMATIONAL SUMMARY"
    )

    for layer, value, reading in read_summary(
        chain,
        ctx,
    ):
        print(
            f"{layer:<24} "
            f"{value:<24} "
            f"{reading}"
        )

    print()
    print("BROKER_SUBMISSION=false")
    print("LIVE_EXECUTION=false")
    print("CERTIFICATION_COUNTER_DELTA=0")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
