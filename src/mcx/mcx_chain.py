"""Legacy MCX chain compatibility boundary.

The canonical MCX PAPER path uses MCXFyersNativeChainV2.

This module intentionally contains:
- no broker authentication;
- no SmartAPI client;
- no credentials;
- no provider fallback;
- no certification mutation.

build_chain() exists only for legacy callers and delegates exclusively to an
already-composed FYERS native-chain runtime/engine.
"""

from __future__ import annotations


LEGACY_CHAIN_RETIRED = True
CANONICAL_PROVIDER = "FYERS"


def build_chain(obj, product, window_steps=10):
    """Delegate to an injected FYERS native-chain engine.

    Accepted objects:
    - MCXFyersRuntimeV2 (has native_chain)
    - MCXFyersNativeChainV2 itself (has build)

    All other callers fail closed.
    """

    if obj is None:
        return {
            "status": "LEGACY_CHAIN_RETIRED",
            "reason": "FYERS_NATIVE_CHAIN_REQUIRED",
            "provider": "FYERS",
        }

    engine = getattr(
        obj,
        "native_chain",
        None,
    )

    if (
        engine is not None
        and hasattr(engine, "build")
    ):
        return engine.build(
            product,
            window_steps=window_steps,
        )

    if (
        getattr(obj, "provider", None)
        == "FYERS"
        and hasattr(obj, "build")
    ):
        return obj.build(
            product,
            window_steps=window_steps,
        )

    return {
        "status": "LEGACY_CHAIN_RETIRED",
        "reason": "FYERS_NATIVE_CHAIN_REQUIRED",
        "provider": "FYERS",
    }


def print_chain(chain):
    if not isinstance(chain, dict):
        print("CHAIN_UNAVAILABLE")
        return

    if chain.get("status") != "OK":
        print(
            "CHAIN_UNAVAILABLE: "
            f"{chain.get('status')} "
            f"{chain.get('reason', '')}"
        )
        return

    print(
        f"\n{chain.get('product')}  "
        f"provider={chain.get('provider', 'FYERS')}  "
        f"expiry={chain.get('expiry')}"
    )

    print(
        f"future={chain.get('future')}  "
        f"ltp=₹{float(chain.get('future_ltp') or 0):.2f}  "
        f"ATM={float(chain.get('atm') or 0):.0f}"
    )

    print(
        f"PCR_OI={chain.get('pcr_oi')}  "
        f"MaxPain={chain.get('max_pain')}"
    )

    print(
        "Resistance(top CE OI)="
        f"{chain.get('resistance')}"
    )

    print(
        "Support(top PE OI)="
        f"{chain.get('support')}"
    )


if __name__ == "__main__":
    print(
        "LEGACY_CHAIN_RETIRED — "
        "use MCXFyersNativeChainV2"
    )
