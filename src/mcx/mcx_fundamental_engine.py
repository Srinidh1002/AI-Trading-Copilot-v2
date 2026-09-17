"""Fundamental engine orchestrator — Section 5.11, 5.18, 5.23, 5.30, 5.36.
Shadow-only. Never passed to compose_decision().
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.dirname(_HERE)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mcx.mcx_crude_fundamentals import build_crude_observations, summarize_crude
from mcx.mcx_natgas_fundamentals import build_natgas_observations, summarize_natgas
from mcx.mcx_gold_fundamentals import build_gold_observations, summarize_gold


class FundamentalEngine:
    def __init__(self):
        self.shadow_mode = True  # Section 5 freeze: always true in Section 5

    def build_for(self, product):
        p = product.upper()
        if p == "CRUDEOILM":
            obs = build_crude_observations()
            return obs, summarize_crude(obs)
        if p == "NATGASMINI":
            obs = build_natgas_observations()
            return obs, summarize_natgas(obs)
        if p == "GOLDM":
            obs = build_gold_observations()
            return obs, summarize_gold(obs)
        raise ValueError(f"UNSUPPORTED_PRODUCT: {product}")

    def shadow_summary(self, product):
        obs, s = self.build_for(product)
        s["shadow_only"] = True
        s["trade_influence"] = False
        return s

    def print_summary(self, product):
        s = self.shadow_summary(product)
        print("=" * 72)
        print(f"{product} FUNDAMENTALS (SHADOW ONLY)")
        print("=" * 72)
        for k, v in s.items():
            if k in ("shadow_only", "trade_influence"):
                continue
            print(f"  {k:22} {v}")
        print(f"  SHADOW_ONLY            TRUE")
        print(f"  TRADE_INFLUENCE        FALSE")
        print("=" * 72)


if __name__ == "__main__":
    e = FundamentalEngine()
    for p in ("CRUDEOILM", "GOLDM", "NATGASMINI"):
        e.print_summary(p)
