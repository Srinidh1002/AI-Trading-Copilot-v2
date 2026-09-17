import sys
sys.path.append("src")
from capital_engine import CapitalEngine

eng = CapitalEngine()
test_cases = [
    (175.00, 175.20, 175.10, "BUY"),
    (174.00, 175.00, 174.50, "SELL"),
    (99.90, 100.10, 100.00, "BUY"),
    (350.10, 350.40, 350.20, "SELL"),
]
print(f"{'bid':>8} {'ask':>8} {'ltp':>8} {'dir':<5} {'fill':>10} {'mod0.05':>10}")
print("-" * 60)
for bid, ask, ltp, direction in test_cases:
    fill, status = eng.compute_paper_fill(bid, ask, ltp, direction=direction)
    mod = round(fill / 0.05) * 0.05
    ok = abs(fill - mod) < 1e-9
    print(f"{bid:>8.2f} {ask:>8.2f} {ltp:>8.2f} {direction:<5} {fill:>10.2f} {str(ok):>10}")

print()
b_fill, _ = eng.compute_paper_fill(100.00, 100.20, 100.10, direction="BUY")
s_fill, _ = eng.compute_paper_fill(100.00, 100.20, 100.10, direction="SELL")
print(f"  BUY fill {b_fill} vs ask 100.20 -> {'OK' if b_fill >= 100.20 else 'FAIL'}")
print(f"  SELL fill {s_fill} vs bid 100.00 -> {'OK' if s_fill <= 100.00 else 'FAIL'}")
assert abs(b_fill - 100.25) < 1e-9, f"expected 100.25, got {b_fill}"
assert abs(s_fill - 99.95) < 1e-9, f"expected 99.95, got {s_fill}"
print("D6 verification PASSED")
