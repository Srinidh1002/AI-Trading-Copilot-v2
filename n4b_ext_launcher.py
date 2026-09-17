"""N4B extended - launcher + analyzer.

Spawns NIFTY and SENSEX subprocesses in parallel, each running 15 cycles.
Aggregates metrics from per-market logs.
"""
import subprocess, sys, time, json, os, re
from datetime import datetime

CYCLES = 15
LOG_DIR = "n4b_ext_logs"
os.makedirs(LOG_DIR, exist_ok=True)
stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
nifty_log = f"{LOG_DIR}/nifty_{stamp}.log"
sensex_log = f"{LOG_DIR}/sensex_{stamp}.log"

print("=" * 80)
print(f"N4B EXTENDED ACCEPTANCE — {CYCLES} cycles per market")
print(f"Started: {datetime.now().isoformat()}")
print(f"Logs: {nifty_log}  |  {sensex_log}")
print("=" * 80)

with open(nifty_log, "w", encoding="utf-8") as f1, \
     open(sensex_log, "w", encoding="utf-8") as f2:
    p1 = subprocess.Popen([sys.executable, "n4b_ext_single.py", "NIFTY", str(CYCLES)],
                          stdout=f1, stderr=subprocess.STDOUT, encoding="utf-8")
    time.sleep(2)
    p2 = subprocess.Popen([sys.executable, "n4b_ext_single.py", "SENSEX", str(CYCLES)],
                          stdout=f2, stderr=subprocess.STDOUT, encoding="utf-8")
    print(f"NIFTY  pid={p1.pid}  SENSEX pid={p2.pid}")
    p1.wait()
    p2.wait()

print("Both processes finished. Parsing logs...")

def parse_log(path, market):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    rate_limited  = len(re.findall(r"RATE_LIMITED", text))
    ev_unavail    = len(re.findall(r"EVIDENCE_UNAVAILABLE", text))
    full_cov      = len(re.findall(r"Coverage: 7/7 \(100%\)", text))
    partial_cov   = len(re.findall(r"Coverage: [1-6]/7", text))
    m = None
    for line in text.splitlines():
        if line.startswith("N4B_EXT_JSON "):
            try:
                m = json.loads(line[len("N4B_EXT_JSON "):])
            except Exception:
                pass
    return {
        "log": path,
        "rate_limited_events": rate_limited,
        "evidence_unavailable_events": ev_unavail,
        "full_coverage_cycles": full_cov,
        "partial_coverage_cycles": partial_cov,
        "summary": m or {},
    }

nifty = parse_log(nifty_log, "NIFTY")
sensex = parse_log(sensex_log, "SENSEX")

def report(name, d):
    s = d.get("summary", {})
    print()
    print(f"===== {name} =====")
    print(f"  cycles                 : {s.get('cycles')}")
    print(f"  errors                 : {s.get('errors')}")
    print(f"  rate_limited_events    : {d['rate_limited_events']}")
    print(f"  evidence_unavailable   : {d['evidence_unavailable_events']}")
    print(f"  full_coverage_cycles   : {d['full_coverage_cycles']}")
    print(f"  partial_coverage_cycles: {d['partial_coverage_cycles']}")
    print(f"  trades                 : {s.get('trades')}")
    print(f"  counter                : {s.get('counter_start')} -> {s.get('counter_end')}")
    print(f"  identity_violations    : {s.get('identity_violations')}")
    print(f"  BROKER_SUBMISSION      : {s.get('broker_submission')}")
    print(f"  LIVE_EXECUTION         : {s.get('live_execution')}")
    print(f"  EXECUTION_MODE         : {s.get('execution_mode')}")
    print(f"  elapsed_s              : {s.get('elapsed_s')}")

report("NIFTY", nifty)
report("SENSEX", sensex)

# Cross-market isolation
nv = nifty["summary"].get("identity_violations", -1)
sv = sensex["summary"].get("identity_violations", -1)
isolation_ok = (nv == 0 and sv == 0)

nc = nifty["summary"].get("cycles", 0) or 0
sc = sensex["summary"].get("cycles", 0) or 0
nerr = nifty["summary"].get("errors", 1) or 0
serr = sensex["summary"].get("errors", 1) or 0

# REST stability: no massive rate-limit avalanche
# Threshold: <= 30 events per market for the run is "acceptable", > 60 is critical
nrl = nifty["rate_limited_events"]
srl = sensex["rate_limited_events"]
rest_stable = (nrl <= 30 and srl <= 30)

# Coverage adequacy: at least 60% of cycles have any coverage entry
min_ok = int(0.6 * CYCLES)
n_any = nifty["full_coverage_cycles"] + nifty["partial_coverage_cycles"]
s_any = sensex["full_coverage_cycles"] + sensex["partial_coverage_cycles"]
coverage_ok = (n_any >= min_ok and s_any >= min_ok)

long_ready = (
    nc >= CYCLES and sc >= CYCLES
    and nerr == 0 and serr == 0
    and isolation_ok
    and rest_stable
    and coverage_ok
    and nifty["summary"].get("broker_submission") is False
    and nifty["summary"].get("live_execution") is False
    and nifty["summary"].get("execution_mode") == "PAPER"
    and sensex["summary"].get("broker_submission") is False
    and sensex["summary"].get("live_execution") is False
    and sensex["summary"].get("execution_mode") == "PAPER"
)

print()
print("=" * 80)
print(f"CROSS_MARKET_ISOLATION = {'PASS' if isolation_ok else 'FAIL'}")
print(f"REST_STABILITY         = {'PASS' if rest_stable else 'FAIL'} (nifty_rl={nrl} sensex_rl={srl})")
print(f"COVERAGE_ADEQUATE      = {'PASS' if coverage_ok else 'FAIL'} (n_any={n_any} s_any={s_any} min={min_ok})")
print(f"LONG_CAMPAIGN_READY    = {'true' if long_ready else 'false'}")
print("=" * 80)
print("STOP - campaign NOT started automatically.")
