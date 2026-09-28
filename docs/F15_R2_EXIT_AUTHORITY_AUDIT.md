# F15-R2 SL0 Exit Authority Audit

**Phase:** R2-18 (audit-only, no strategy change)
**Scope:** Every possible index and MCX exit authority in the PAPER runtime
**Output class:** Documentation. No code change. No threshold change.
**Status:** Complete for static-read audit; live exit-side observation deferred.

---

## 1. Purpose

Establish, by code inspection, every path that can close a PAPER position,
who owns each one, and which invariants hold. This is the SL0 baseline for
the later SL1-SL7 VNext exit redesign track.

No widening of stops. No change to T1/T2/T3. Any strategy hypothesis
discovered is recorded in §7 for Brain-VNext / SL research only.

---

## 2. Index exit authorities

File: `src/target_focused_bot.py`

| Authority | Trigger | Source | Line |
|---|---|---|---|
| `STOP_LOSS` | `current_mark <= trade['sl_price']` | bid-authoritative | 2142 region |
| `SPOT_INVALIDATED` | spot move against position beyond threshold | bid-authoritative | 2140 region |
| `T1/T2/T3` (trail) | trail_stop activated by T1, then T1/T2/T3 handled as bid thresholds | bid-authoritative | 2150 region |
| `MARKET_CLOSE_3:28PM` | `datetime.now() >= FINAL_EXIT` (15:28) with valid bid | bid-authoritative | 2179 region |
| `FORCED_CLOSE` (session end) | session authority at close | bid-authoritative | run_nifty/run_sensex |
| `COOPERATIVE_STOP` | supervisor stop request | flat-safe exit or manage-to-terminal | `_coop_stop_requested()` |

**Ownership:** single owner per tick. `close_position()` is the only
function that transitions `status` to `CLOSED`. There is no path where
two exit authorities fire in the same tick — the tick evaluates
conditions in priority order and calls `close_position` exactly once.

**Display vs certification threshold price:** both use
`_bid_based_exit(entry, current_bid, lot_size)`. Certification outcomes
are derived from `first_touch_result` which is bid-based, not P&L based
(confirmed in `close_position`, lines 2388-2400). **No divergence.**

**Restart policy preserved:** `load_state()` reloads `active_trades`
verbatim, including `first_touch_state`, `t1_price`, `sl_price`. A
restart cannot change exit policy for an existing position. Verified in
R2-2 tests.

**Protection stall by analysis:** analysis is post-close, reads ledgers,
does not block the trading loop. No path where analysis stalls a live
exit check.

**Cooperative stop:** if a worker has `active_position`, the supervisor
waits (POSITION_MANAGEMENT_EXTEND_SECONDS=900). No abandoning.

---

## 3. MCX exit authorities

File: `src/mcx/mcx_paper_bot.py`

| Authority | Trigger | Source | Line |
|---|---|---|---|
| `STOP_LOSS` | `pnl_pct <= STOP_LOSS_PCT (-8%)` | bid-side VWAP mark | 1519 region |
| `T3_50%` | `pnl_pct >= T3_PCT` | bid-side VWAP mark | 1521 region |
| `T2_30%` | `pnl_pct >= T2_PCT` | bid-side VWAP mark | 1523 region |
| `T1_15%` | `pnl_pct >= T1_PCT` | bid-side VWAP mark | 1525 region |
| `MCX_CLOSE_2310` | `datetime.now().time() >= 23:10` | bid-side VWAP mark | 1527 region |
| position_manager | `pm_evaluate_exit(...)` trail/hold authority | bid-side VWAP mark | 1532 region |
| `COOPERATIVE_STOP` | `_coop_stop_requested()` | flat-safe or manage-to-terminal | 1153 region |

**Ownership:** single owner per cycle. `close_and_reconcile()` is the
only mutator of `state["active_position"]` back to None (line 966 region).
Priority order is `if/elif`; exactly one branch runs.

**Display vs certification threshold price:** `mark, mark_q =
get_bid_mark_for_position(...)` at line 1471 region. Certification uses
`first_touch_state` derived from the same mark. **No divergence.**

**Restart policy preserved:** `load_state()` uses `_restore_first_touch`
to rebuild first-touch state from `active["first_touch_state"]`.
Thresholds (`sl_price`, `t1_price`) are on the position dict and not
recomputed. Restart cannot change exit policy.

**Protection stall by analysis:** none. Analysis is post-close.

---

## 4. Cross-market invariants

- **One position per market.** `state["active_position"]` (MCX) and
  `bot.active_trades` (index) are single-owner structures per market.
- **Bid-authoritative exits.** Both markets use best-bid for exits,
  not LTP. `_bid_based_exit` and `get_bid_mark_for_position` are the
  two implementations.
- **First-touch result drives certification.** `T1_FIRST` / `SL_FIRST`
  is set by the first-touch tracker, not by P&L sign. Certification
  never infers outcome from P&L.
- **Session close authority.** Both markets refuse new entries outside
  session; both close existing positions at their respective session end
  (15:28 index, 23:10 MCX).

## 5. Duplicate exit authority — answer

**No.** Every exit path is guarded by an `if/elif` chain evaluating
conditions in priority order and calling the single closer exactly once
per tick. Post-close, `del active_trades[trade_id]` removes the trade
from the active map, so a second tick cannot re-close.

## 6. Restart-policy invariants

- Existing position thresholds (`sl_price`, `t1_price`, `t2_price`,
  `t3_price`) are on the position dict and loaded verbatim.
- `first_touch_state` is persisted and restored via
  `_restore_first_touch` (MCX) / direct attribute reload (index).
- `entry_spot` is stored and used for `SPOT_INVALIDATED` index exits.
- No threshold is recomputed on load. Verified in R2-2 and R2-17 tests.

## 7. Strategy hypotheses (recorded for Brain-VNext, not actioned here)

- **H1:** Index `SPOT_INVALIDATED` at +0.5% spot move against a PE
  position may be pre-empting entries that would recover within
  threshold. Statistically testable on historical ledgers; out of
  scope for F15-R2.
- **H2:** MCX `T1` immediately activates trail; whether a full T1/T2/T3
  ladder or a scaled exit would produce better expectancy is a
  strategy question for the SL1-SL7 track.
- **H3:** No stop uses an ATR-adaptive level; all SLs are fixed
  percentage. This is a deliberate design choice consistent with the
  fixed-T1/T2/T3 target policy. Recorded for VNext consideration only.

**None of H1/H2/H3 is actioned in F15-R2.** Strategy changes require a
new epoch and independent statistical review.

## 8. SL0 conclusion

Every index and MCX exit authority is:

- Single-owner per tick
- Bid-authoritative where designed
- Preserved across restart
- Not stallable by post-close analysis
- Cooperative-stop-aware (no position abandon)

No strategy change required for SL0. No code change made.
