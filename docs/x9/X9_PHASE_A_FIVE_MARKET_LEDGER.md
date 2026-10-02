# X9 Phase A — five-market Shadow comparison ledger

Frozen parent: X7 commit `b69061f562ab03b2deb3a17cd8a3943bda955cb2`. The existing `services/opportunity_ranking` compares a historical four-index universe and should not be rewritten, duplicated or assumed to support three MCX products. X9 Phase A captures the **five-market completeness boundary**; it does not calculate a ranking.

`build_x9_five_market_ledger_v1` requires exactly one immutable `X8RegimeReadinessV1` for each market, exactly in the canonical five-market output order: NIFTY, SENSEX, CRUDEOILM, GOLDM, NATGASMINI. Input order does not change the output or hash. Every slot binds the complete X8 digest, source as-of, the unmodified readiness state, and permanently UNASSESSED regime and eligibility. No unavailable market is silently omitted or replaced with NIFTY.

The caller supplies one parent-cycle ID, an aware as-of and a finite nonnegative maximum skew. Future captures and excessive parent-to-market capture lag fail closed. A five-market ledger is COMPLETE_RESEARCH only if all five X8 reference inventories are READY; an unavailable/partial market stays visible and results in INCOMPLETE_RESEARCH. In either state, `selected_market` remains None, `rankings` remains empty and no CALL/PUT or trade recommendation exists. COMPLETE_RESEARCH does **not** imply all markets are open or comparable for execution; differing NSE/BSE/MCX sessions and contract liquidity require distinct later gates.

No order, strategy, sizing, broker, risk policy, PAPER counters or production runtime integration. The historical four-index opportunity-ranking policy must not be copied without a new five-market evidence/eligibility review.

Next joint batch: evaluate read-only five-market market/session compatibility and explicit eligibility vocabulary **after** separate X8 regime classification is available. Only later, following a documented scoring and tie-policy review, can a *shadow* comparator be added.
