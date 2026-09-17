# FYERS five-market PAPER readiness audit — 17 September 2026

## Verdict and scope

**HOLD** for five-market live-session PAPER testing and automatic scheduling.
**HOLD** for F14R1 freeze pending a successful two-market, market-hours canary.
This is an inspection of commit `1640604cafae14431e49cb7c787532d11d898cd5`
plus a narrow observational-gate hardening change. It is not a live-session
proof. The repository does not contain this operator's local credentials,
provider session, or untracked certification data; no provider calls or PAPER
entries were made during this audit.

## Dependency and authority map

| Market requested | Repository identity and data | Analysis / PAPER runtime | Certification authority | Verdict |
| --- | --- | --- | --- | --- |
| NIFTY | `services/core/five_market_universe_v2.py`; FYERS `NSE:NIFTY50-INDEX`, F8 resolver; F9 stream | `ProviderInjectedUnifiedTradingBotV2` delegates to `UnifiedTradingBot`; F14 is observation only | Existing Task 9 launcher and counting evaluator cover NIFTY/NSE, but the injected FYERS bot is not shown connected to that launcher | HOLD |
| SENSEX | FYERS `BSE:SENSEX-INDEX`, F8 resolver; F9 stream | Same F12/F14 path | Existing Task 9 launcher covers SENSEX/BSE, not a proven FYERS live lifecycle | HOLD |
| CRUDEOILM | F8 FYERS MCX resolution demonstrated as data foundation | `src/mcx/mcx_paper_bot.py` authenticates Angel SmartAPI and reads Angel MCX data | Separate MCX product epoch; eligible flag true; FYERS provenance through entry, exit and reconciliation unproven | HOLD |
| GOLDM | F8 FYERS MCX data foundation | Same Angel-backed MCX bot; contract metadata provisional | MCX epoch explicitly `certification_eligible=False` | HOLD |
| SILVERM | Absent from `TARGET_FIVE_MARKETS`, F8 resolver mapping, MCX product registry and bot choices | No canonical PAPER runner | No /100 authority | FAIL for requested coverage |

The fifth repository market is **NATGASMINI**, not SILVERM. NATGASMINI is
present in the FYERS universe and MCX bot, but its MCX epoch is also
precertification. Do not rename it to SILVERM: contract, expiry, capital,
context, risk and counting semantics are product specific.

```text
FYERS REST/F9 stream -> F8 identity -> F12 injected two-index bot
                                         -> F13 native options -> F14 observation
Existing two-index Task 9 launcher -> historical certified child composition
MCX Angel SmartAPI -> MCX bot -> MCX reconciliation / separate epoch
```

There is no demonstrated connection from the F14 observational route to the
two-index Task 9 entry/exit/counting route, nor from the FYERS route to the
MCX PAPER bot. `run_nifty.py` and `run_sensex.py` instantiate the inherited
Angel-era bot directly; they are not FYERS migration entrypoints. The
`services/scheduler/trading_scheduler.py` interval loop uses local weekday
time and one 09:15–15:30 window. `src/mcx/mcx_scheduler.py` is documented
as a manual framework and calls for Angel authentication. Neither is the
requested five-market FYERS scheduler.

## Evidence by subsystem

| Subsystem | NIFTY / SENSEX | CRUDEOILM / GOLDM | SILVERM |
| --- | --- | --- | --- |
| Quote, depth, candles, OI, WebSocket | F7–F12 adapters and focused unit tests; live F14 quote/stream reported in operator checkpoint | FYERS F8–F10 data foundation, not connected to PAPER bot | Absent |
| Native option chain, expiry, PCR, max pain, candidate | F13 path present; last F14 canary had `expiry=None`, zero options and no candidate; causal reason still unproven | MCX Angel option path exists; FYERS-to-MCX chain, expiry and execution model unproven | Absent |
| Premarket, constituents, indicators, regime | Inherited engines and F12 premarket backfill present; availability/freshness of all requested pillars unproven in current session | Separate MCX context and indicator modules; Angel-backed PAPER composition | Absent |
| Capital, entry, active position, SL, T1/T2/T3, exit, P&L | Inherited PAPER bot has these paths; F14 reads a diagnostic executable quote and targets but cannot prove lifecycle | MCX bot has separate capital/position/reconciliation code; contract metadata is provisional | Absent |
| Reconciliation and independent /100 | Existing Task 9 evaluator excludes replay, out-of-session, open, unreconciled and missing-entry records for two indexes; FYERS provenance is not established in it | CRUDEOILM has separate eligible epoch; GOLDM is precertification | Absent |
| Calendar, restart, scheduler, dashboard | Two-index session validator/holiday models and Task 9 read models exist; five-market orchestration not established | Different MCX holiday/session code; scheduler is a stub | Absent |

Specific calendar defect: `src/mcx/mcx_holidays.py` contains one provisional
2026 date and returns `(None, None)` for every other date;
`src/mcx/mcx_calendar.py:get_session` treats that result as an open weekday.
Its documented fail-closed behavior is therefore not implemented. The MCX
calendar must be populated from verified exchange data and default to closed
when verification is unavailable before any scheduler or official MCX run.
The MCX bot's `if not cal.get("tradable")` branch also skips its later active
position monitor. A calendar fix must preserve a separate close/recovery path
for an already open PAPER position; simply returning `tradable=False` would
leave that path unattended.
The generic interval scheduler and MCX session cutoff are also separate
authorities. Existing NSE/BSE configuration does not establish MCX holidays.

The **tracked** Task 9 projection reports NIFTY 0 and SENSEX 0 countable
trades, but is not a substitute for the operator's current untracked local
ledgers. The tracked CRUDEOILM state records `POST_PRECISION_V2`, whereas
`src/mcx/mcx_version.py` requires `POST_PRECISION_V4`; do not overwrite or
reset this historical state merely to make the version check pass. GOLDM's
tracked state is precertification. SILVERM has no state.

Security inspection found `.env` ignored and untracked at this checkout.
F14 uses FYERS for the primary quote and Angel only for shadow parity;
automatic fallback is prohibited in that route. The old direct runners and
MCX bot still import Angel SmartAPI. No claim about all repository paths or
historical secrets is made from this targeted inspection.

## Code change in this audit

`has_complete_canary_market_evidence` now requires a nonblank expiry, positive
ATM and explicit injected FYERS provider mode before F14 can pass. A canary
with a superficially OK chain but missing expiry can no longer pass the
observational gate. No threshold, entry, lifecycle, counter or broker code
was changed.

## Offline test record

All commands ran in an isolated worktree with no local `.env` and did not
start a provider session:

| Inventory | Result |
| --- | --- |
| F7–F14 plus P44 provider/five-market files (22 explicit test files) | **219 passed** |
| Task 9 countability/end-to-end fixture, three targets and MCX product/replay subset | **32 passed** |
| MCX first-100, PAPER P&L/reconciliation and index calendar subset | **137 passed** |

These are **388 passing focused tests**, not a full repository test suite or
live-session proof. The 219-test inventory exactly matches the previously
reported focused count; earlier 177-test subset omitted the five P44 files,
which supplied the other 42 tests. The additional 169 tests cover selected
accounting and calendar contracts, not a five-market FYERS lifecycle.

## Operator steps for the next valid market session

From the repository root in PowerShell, with the operator's existing local
`.env` and current `data/instruments.json`, run the read-only canary during
the actual NSE/BSE derivatives session. Confirm the exchange calendar first.
The command also obtains an Angel **shadow quote**; it does not submit orders.

```powershell
git fetch origin p10-two-market-weekend-readiness
git rev-parse origin/p10-two-market-weekend-readiness
git status --short
venv\Scripts\python.exe -m pytest -q tests/test_f14_two_market_observational_canary_v2.py tests/test_f14_provider_evidence_repairs_v2.py
if ($LASTEXITCODE -ne 0) { throw 'F14 static regression failed' }
venv\Scripts\python.exe scripts/f14_two_market_observational_canary.py --env-file .env --instruments data/instruments.json --ipv4-only
if ($LASTEXITCODE -ne 0) { throw 'F14 market-hours canary HOLD/FAIL; do not freeze or schedule' }
```

Record for **each** index: expiry, native chain request count, option count,
PCR OI, candidate, executable bid/ask, paper fill, lot size, affordable lots,
SL/T1/T2/T3, WebSocket health, premarket availability, Angel parity, zero
ledger writes and zero counter mutation. A PASS requires all gates together.
If expiry remains absent during market hours, inspect local instrument
freshness and F12 `get_expiry` selection before an F14R2 root-cause fix.
Do not interpret after-hours absence alone as an expiry defect.

There is **no safe command to enable a five-market scheduler at this
checkpoint**. Implement and expose such a command only after SILVERM
identity/contracts are established; MCX uses FYERS data only; all five
individual markets prove real-session PAPER entry, monitoring, exit,
reconciliation and independent counting; and one trusted NSE/BSE/MCX
calendar plus restart/duplicate-process protection passes regression.
Until then, use F14 observation only for the two indexes and preserve all
existing runtime and certification evidence.

## Pending proof matrix

1. F14 market-hours NIFTY and SENSEX full evidence and parity: **HOLD**.
2. SILVERM provider symbols, contract master, lot/tick/expiry and commodity
   context: **FAIL** (not implemented).
3. FYERS-injected PAPER entry/monitor/exit and complete P&L arithmetic on
   both indexes: **HOLD** (not proven by observation).
4. FYERS MCX runtime for three requested products and futures/options
   contract model: **HOLD**.
5. Five independent eligible /100 counters with real FYERS provenance and
   duplicate/replay exclusions: **HOLD**.
6. Exchange calendars (MCX unknown weekdays currently fail open), scheduler
   lease/recovery, dashboard five-market projection and full safe
   regression/security pass: **HOLD**; MCX calendar behavior is a confirmed
   defect requiring a scoped fix before any MCX scheduler activation.
