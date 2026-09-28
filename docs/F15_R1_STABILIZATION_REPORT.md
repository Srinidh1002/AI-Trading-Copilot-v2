# F15-R1 Stabilization Report

**Frozen base (F15):** `70900688aea8728fd7c133bac79338b5dac9dce0` — `docs(F15): five-market PAPER baseline freeze`
**Repair branch:** `f15r1-runtime-repair`
**Repair HEAD:** `23ddf85521d92be3637ca595c0f4bdbfc30fff02`
**Remote HEAD:** matches local (`origin/f15r1-runtime-repair`)
**Target branch:** `five-market-offline-readiness` untouched at `7090068`
**Worktree:** clean
**Merge status:** NOT MERGED — awaiting ChatGPT adjudication

---

## 1. Scope

Fifteen distinct runtime defects and safety gaps were identified after the
2026-09-28 live F15 PAPER session. Eleven commits on `f15r1-runtime-repair`
address the offline-safe subset. Four phases (8, 12, 13, 14) require a
live FYERS token and are deferred.

---

## 2. Safety contract

Unchanged and verified at every step:

- `EXECUTION_MODE=PAPER`
- `BROKER_SUBMISSION=False`
- `LIVE_EXECUTION=False`
- `LIVE_EXECUTION_ELIGIBLE=False`
- `AUTOMATIC_ANGEL_FALLBACK=False`
- FYERS is the sole canonical data provider.

No certification counter was incremented, decremented, or reset by any
commit on this branch. `counted_trade_ids` was never modified by any apply
path. No live data was mutated — every verification ran against `tmp_path`
copies of the frozen state.

---

## 3. Fixes

### `6a36e62` — `fix(supervisor): consume worker exits once per process generation`

**Root cause.** The supervisor tick loop re-polled `rt.process` on every
tick. A worker that had already exited was classified again, appending a
fresh entry to `rt.restart_failures` on each tick. A single dead PID
observed on three ticks therefore opened `WORKER_CIRCUIT_OPEN` without
three separate worker generations.

**Fix.** `_consume_exit` now clears `rt.process = None` after each
consumed exit and records the classification in `rt.exit_history` /
`rt.last_exit_*` exactly once. `generation_id` and `consumed_exit_count`
track history for audit.

**Coverage.** `tests/test_f15r1_supervisor_lifecycle_v2.py` — 9 tests:
single-consumption, three genuine generations, clean rc=0 close vs
unexpected rc=0, ownership-hold non-counting, spawn-failure counting,
15:28 close-window classification, new-day reset, exit-history
preservation.

### `6a36e62` (folded) — session/circuit reset authority and index close window

`_reset_session_authority_if_needed` clears per-day restart state on the
first tick of a new trading date, preserving `exit_history` for audit.
`_in_close_grace` treats rc=0 exits inside `[close-1500s, close+300s]` as
`CLEAN_SESSION_END`, distinguishing legitimate end-of-session shutdown
from unexpected early exit.

### `6ccf559` — `feat(supervisor): add worker heartbeat and stage markers (Phase 5)`

**New module.** `services/paper_orchestration/worker_heartbeat_v2.py`

Atomic JSON heartbeat per market, written at 14 stage boundaries in the
MCX worker (CALENDAR → IDENTITY → CHAIN → MTF → EXTERNAL → PCR → VWAP →
FUTURE_QUOTE → DATA_QUALITY → DECISION → POSITION_MARK → POSITION_EXIT →
STATE_SAVE → SLEEP) and at SESSION/SLEEP for NIFTY and SENSEX.

Schema fields: `schema_version, market, pid, worker_generation,
timestamp, cycle_number, stage, stage_started_at,
last_cycle_completed_at, has_active_position, trade_id,
execution_mode=PAPER`.

Atomic via `tempfile.mkstemp` + `os.fsync` + `os.replace`. Best-effort:
any I/O failure is logged once per path and never raised into the trading
loop. Path `logs/supervisor/heartbeats/<MARKET>.json`, overridable via
`PAPER_HEARTBEAT_DIR`.

**Motivating evidence.** NATGASMINI worker hung ~4.5 h inside a
synchronous provider call (isolation probe measured the same chain call
at ~43 s). With no heartbeat, the supervisor had no way to detect the
stall until the process was externally killed.

### `5fc4657` — `feat(supervisor): recycle stale flat workers, recover stale active-position workers (Phase 6)`

**New module.** `services/paper_orchestration/worker_liveness_v2.py`

`classify(market, now)` returns `NO_HEARTBEAT | HEARTBEAT_OK |
HEARTBEAT_STALE`. Threshold `HEARTBEAT_MAX_AGE_SECONDS = 300.0` (2× the
worst plausible healthy gap).

Supervisor hook in the tick loop, when a live worker's heartbeat is stale:

- **flat** (no persisted active position): log `HUNG_WORKER_DETECTED
  stage=<last> age=<s>`, call `_stop_worker` with 5 s grace, let next
  tick's `_consume_exit` record exactly one failure generation.
- **active position** (MCX state shows `active_position` with a
  `trade_id`): log `ACTIVE_POSITION_RECOVERY_REQUIRED`, set
  `rt.recovery_required = True`, stop the worker, bypass
  `_may_start`'s circuit-open and backoff gates so the recovery worker
  restarts immediately. `_consume_exit` suppresses failure recording
  while `recovery_required` is set.

`recovery_required` is cleared only when a restarted worker finds the
persisted position terminal.

**Coverage.** `tests/test_f15r1_supervisor_liveness_v2.py` — 12 tests.

### `3ed537e` — `chore: ignore runtime-only MCX evidence and counterfactual capture directories`

Adds two narrow `.gitignore` rules:
`data/execution_evidence/mcx/fyers/` and
`data/paper_trades/counterfactual/`. Verified via `git check-ignore` to
match those paths and not to hide any tracked file. No de-duplication of
the pre-existing `.gitignore`.

### `b2d7a4d` — `fix(reporting): align daily audit with current ledger schema`

**Root cause.** `campaign_analysis_v2.analyze_market_day` was reading
fields that do not exist in the current ledgers:

- tested `action in ("CALL", "PUT")` (real values are `BUY_CALL` /
  `BUY_PUT`)
- read `rec.get("outcome")` (the outcome row has no such field)
- checked `outcome == "T1_FIRST"` (the real field is
  `first_touch_result`)

Result: every report printed `Entries: 0 / Wins: 0 / Losses: 0` even
with real trades.

**Fix.** New `services/paper_orchestration/ledger_schema_v2.py` reads
the actual schemas and produces separate economic and certification
summaries. `write_daily_report` now shows:

- Decision count, entry-action count, WAIT/NO_TRADE count
- Raw closed outcomes
- Economic wins / losses / net P&L
- **Certification** countable / wins / losses
- First-touch histogram: `T1_FIRST` / `SL_FIRST` / `AMBIGUOUS` / `NONE`
- Monitoring-gap ambiguity count
- Active position at close (list-aware for index, dict-aware for MCX)

**Verified against real data** (temp mirror of the live F15 worktree):

- NIFTY: decisions=45, entry signals=28, raw closed=5, economic
  wins=2 / losses=3, net P&L=+903.03, cert countable=2, cert
  losses=1, cert wins=0, first-touch SL_FIRST=1, AMBIGUOUS=3, NONE=1
- SENSEX: decisions=329, entry signals=271, raw closed=5, economic
  wins=1 / losses=4, net P&L=-1121.85, cert countable=3, cert
  losses=3, cert wins=0, first-touch SL_FIRST=3, AMBIGUOUS=2

### `e943612` — `fix(index): reconcile proven same-day stale active records safely`

**New module.**
`services/paper_orchestration/active_state_reconciler_v2.py`

**New CLI.** `tools/reconcile_active_state_v2.py`
(default dry-run; `--apply` moves proven orphans only)

**Root cause.** After the F15 close, NIFTY `active_trades` contained two
records and SENSEX contained one, all `status=OPEN`, none appearing in
either market's `outcomes.jsonl`. They were same-day restart/orphan
records from mid-session restarts, never reconciled.

**Classifier rules** (conservative, fail-closed):

1. `trade_id` in this market's outcomes ledger → `TERMINAL_ALREADY_RECORDED`
2. `trade_id` in `counted_trade_ids` → `TERMINAL_ALREADY_RECORDED`
3. `trade_id` already in `orphaned_trades` → `STALE_RESTART_ORPHAN_PROVEN`
   (idempotent)
4. `first_touch_result in (None, "")` → `STALE_RESTART_ORPHAN_PROVEN`
5. `first_touch_state.last_valid_quote_time` older than 4 h →
   `STALE_RESTART_ORPHAN_PROVEN`
6. otherwise → `UNRESOLVED_HOLD` (record retained, not deleted)

Apply path is atomic and enforces immutable-field invariants
(`certification_counter`, `certification_wins`, `certification_losses`,
`counted_trade_ids`, `completed_trades`) — if any of those differs from
the pre-apply snapshot, the module raises and does not persist.

**Verified against real data** (read-only temp mirror):

- NIFTY: 2 records → `TRD_20260928_095648` proven orphan
  (`LAST_QUOTE_STALE:37870s`), `TRD_20260928_100056` proven orphan
  (`FIRST_TOUCH_UNINITIALIZED`). Counter unchanged (4),
  `counted_trade_ids` unchanged (4). Orphaned list grew 1 → 3.
- SENSEX: 1 record → `TRD_20260928_100057` proven orphan
  (`FIRST_TOUCH_UNINITIALIZED`). Counter unchanged (5),
  `counted_trade_ids` unchanged (5). Orphaned list grew 0 → 1.
- Second apply: `moved=[]` (idempotent).

### `0232372` — `test(mcx): land Option-D depth-freshness regression coverage`

Lands `tests/test_p0_f15_option_d_freshness_v2.py` (6 tests), previously
untracked in the main worktree. Uses `tmp_path` throughout; no live writes.
A `# noqa: E402` was added on the post-`sys.path.insert` import to match
the repo's bootstrap convention.

### `3cdd8ce` — `fix(mcx): create FYERS SDK log directory at runtime builder boundary`

**Root cause.** Ad-hoc MCX scripts (`mcx_probe.py`, `mcx_replay.py`,
`mcx_snapshot.py`, calibration tools) call
`build_mcx_fyers_runtime_from_env_v2(log_path=...)` without first
creating the directory. `mcx_paper_bot.login()` already does, but probe
scripts did not, and the FYERS SDK raises `FileNotFoundError` when the
log directory is absent — this was the observed F15
`logs/natgas_readonly_probe/fyersApi.log` failure.

**Fix.** `build_mcx_fyers_runtime_v2` calls
`os.makedirs(log_path, exist_ok=True)` immediately after validating
`log_path`, before invoking the SDK client builder. Fail-closed: if
`log_path` points at an existing file, `makedirs` raises
`FileExistsError`.

The shared SDK boundary (`fyers_sdk_data_client_v2.build_*`) was
deliberately left untouched — it explicitly documents that credentials
are caller-supplied and never reads the environment; adding directory
side-effects there would silently redefine its contract for index and
preflight callers.

**Coverage.** `tests/test_f15r1_mcx_runtime_log_dir_v2.py` — 5 tests.

### `7178dd8` — `ci: extend offline-stability workflow with F15-R1 focused test files`

Adds 9 new test files to `.github/workflows/offline-stability.yml`:

- `tests/test_p0_f15_option_d_freshness_v2.py`
- `tests/test_f15r1_worker_heartbeat_v2.py`
- `tests/test_f15r1_worker_liveness_v2.py`
- `tests/test_f15r1_supervisor_liveness_v2.py`
- `tests/test_f15r1_supervisor_lifecycle_v2.py`
- `tests/test_f15r1_ledger_schema_v2.py`
- `tests/test_f15r1_campaign_analysis_v2.py`
- `tests/test_f15r1_active_state_reconciler_v2.py`
- `tests/test_f15r1_mcx_runtime_log_dir_v2.py`

The CI trigger fires only on push/PR to `five-market-offline-readiness`;
this commit changes the future behaviour of the workflow on that branch
but does not gate `f15r1-runtime-repair` itself.

### `a34be5f`, `23ddf85` — ruff cleanups

- `style(test): drop unused imports flagged by ruff on f15r1 supervisor lifecycle`
- `chore(preflight): file-level ruff exception for repo-root bootstrap`
  (matches commit `1085267` on the same class of file)

---

## 4. Tests

- **319 passed** on the exact pytest command from the modified workflow
  (all 24 base P0 files plus the 9 new F15-R1 files).
- **Ruff.** All 17 CI-maintained files clean; all 16 F15-R1 new/changed
  files clean.
- **GitHub Actions.** Not triggered by this branch (workflow only fires
  on `five-market-offline-readiness`). Local reproduction of the
  workflow's steps — syntax check, ruff, focused pytest, live-lock
  guard — is green.

---

## 5. Live read-only probes

Every probe ran against a `shutil.copy2` mirror of the live worktree in
`tempfile.mkdtemp()`. No live file was read-write opened. The main
worktree's supervisor was running throughout and was not disturbed.

- **Phase 10 (index state reconciliation).** Dry-run then apply on the
  mirror — 3 proven orphans, counters unchanged, idempotent on re-run.
- **Phase 28 (daily audit).** Dry-run on the mirror — NIFTY / SENSEX
  both report coherent economic + certification breakdowns
  (see §3 `b2d7a4d`).

**FYERS WebSocket canary (Phase 12)** — deferred, requires a same-day
access token. The adapter at `services/broker/fyers_streaming_v2.py`
uses the official `fyers_apiv3.FyersWebsocket.data_ws.FyersDataSocket`
and constructs the socket with an authenticated token; the FYERS
2026-09-30 WebSocket requirement is therefore expected to be satisfied
without code change, but this has not been proven live tonight.

---

## 6. Certification state

Unchanged from the frozen base:

| Market | Counter | Wins | Losses |
|---|---|---|---|
| NIFTY | 4/100 | 0 | 4 |
| SENSEX | 5/100 | 0 | 5 |
| CRUDEOILM | 0/100 | 0 | 0 |
| GOLDM | 0/100 | 0 | 0 |
| NATGASMINI | 0/100 | 0 | 0 |

`counted_trade_ids`:

- NIFTY: `TRD_20260923_130132, TRD_20260923_143054, TRD_20260923_144243, TRD_20260928_113315`
- SENSEX: `TRD_20260923_133405, TRD_20260923_134130, TRD_20260928_095648, TRD_20260928_105204, TRD_20260928_110121`

No commit on this branch modified either list or any counter.

---

## 7. Findings (not fixed — require separate review)

### F1 — NIFTY outcome row over-reports `certification_countable`

`TRD_20260928_145859` (`MARKET_CLOSE_3:28PM`, `first_touch_result=NONE`)
carries `certification_countable=true, certification_win=false,
certification_loss=false` in `nifty_outcomes.jsonl`, yet its trade ID is
absent from `counted_trade_ids` and the counter did not increment for
it. The audit parser faithfully reports what the row says. The F15
report says the counter went 3 → 4 with only `TRD_20260928_113315`. The
row and the state disagree — a writer-side inconsistency, not a reader
bug. Fixing it changes evidence semantics and is out of scope for
F15-R1.

### F2 — `trade_id` is not market-scoped

`TRD_20260928_095648` appears both as a NIFTY `active_trades` record and
in SENSEX `counted_trade_ids` as a legitimate SENSEX cert trade. Today
each market's reconciler reads only its own state file, so no
misclassification occurred, but a future cross-market reasoning path
would collide. The generator should namespace by market.

### F3 — "Entry actions" in the daily report counts decisions, not trades

The line `Entry actions (BUY_CALL/BUY_PUT): 28` for NIFTY counts
`action == BUY_PUT` rows across all cycle ticks, not actual trade opens.
Real opens for the day were 5 raw closed + 2 active. Informational only;
a follow-up rename to "Decision signals" would remove the ambiguity.

---

## 8. Deferred phases

| Phase | Description | Blocker |
|---|---|---|
| 8 | GOLDM StablePCR root-cause probe | Live FYERS token |
| 12 | FYERS WebSocket auth canary | Live FYERS token |
| 13 | WS invalid-token fail-closed tests | (mocked — can run offline) |
| 14 | WS reconnect semantics tests | (mocked — can run offline) |
| 26 | NATGAS pipeline liveness probe | Live FYERS token |
| 30 | All-five repair canary | Requires original F15 supervisor idle |

---

## 9. Outstanding engineering issues

- F1, F2, F3 above.
- `src/mcx/mcx_paper_bot.py` carries 127 pre-existing ruff errors
  (E402, E501, F401, F541, E702, F821). Not in the CI ruff list, not
  touched by this branch. Notably, `setup` is referenced at line 1448
  in the counterfactual-capture block before assignment at line 1443.
  The `except Exception` swallows the resulting `NameError`, silently
  dropping every WAIT-mode counterfactual capture. This defeats the
  threshold-70 study and deserves its own commit.
- `.gitignore` has significant duplication (`.env`, `__pycache__/`,
  `logs/`, `data/paper_trades/*`, `data/rate_limit/`, `*.bak*` each
  appear 2–3 times). Cosmetic; not de-duplicated here to keep the
  Phase 17 diff narrow.

---

## 10. Merge status

**NOT MERGED** into `five-market-offline-readiness`.

The target branch is unchanged at `7090068`. This branch is published
as `origin/f15r1-runtime-repair` at `23ddf85` and awaits ChatGPT merge
adjudication before any cherry-pick, rebase, or merge.
