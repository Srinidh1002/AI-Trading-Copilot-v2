
# F15-R2 Five-Market Paper Readiness Report

**F15 base:** `70900688aea8728fd7c133bac79338b5dac9dce0`
**F15-R1 base:** `b96f7fa57b4f6b17761a7e94a55ef27652389e70`
**R2 branch:** `f15r2-five-market-paper-readiness`
**R2 head:** `fff9237` (13 commits above R1 base)
**Target:** `five-market-offline-readiness` untouched at `7090068`
**Merge status:** NOT MERGED
**Long-term campaign:** NOT STARTED

---

## 1. Commits


---

## 2. F1 — Certification writer/ledger inconsistency

**Root cause.** `close_position` wrote the outcome row (`outcome_ledger.record`,
line 2405) before evaluating certification admission
(`_try_increment_certification_counter`, line 2455). The row serialized
the entry-time optimistic default `certification_countable=True` (line
1935). The generic rejection branch at line 2293 returned without
demoting, so any non-diversity reject (first_touch=NONE, wrong epoch,
non-PAPER, etc.) left `row['certification_countable']=True` while the
authoritative counter correctly rejected.

**Fix (R2-2, c3fd3bc).** Split into `_evaluate_certification_admission`
(pure) and `_apply_certification_acceptance` (mutating, idempotent by
trade_id). `close_position` now:
  1. Evaluates admission
  2. Snapshots the decision onto `trade['certification_countable']` and
     `trade['certification_countability_reason']`
  3. Writes the row
  4. Applies counter only if row write succeeded AND admission accepted
  5. Downgrades to `NOT_RECONCILED` if row write fails after acceptance

**Historical disposition — TRD_20260928_145859:**
- first_touch_result = NONE
- row certification_countable = true (pre-fix artifact)
- authoritative counted_id present = false
- rejection_reason (would have been) = NO_TERMINAL_FIRST_TOUCH
- counter manually mutated = NO
- row preserved as-is; no backfill

**Tests:** 19 in `test_f15r2_certification_authority_v2.py`.
Idempotent on duplicate close, restart-safe, ledger-write failure
downgrade, T1_FIRST/SL_FIRST/AMBIGUOUS/NONE all classified correctly.
