# X9-B3 — Five-market descriptive comparison safeguards

New source: `services/x9/comparison_safeguards_v1.py`.

The audit consumes the exact five-market ledger and B2 research-eligibility result for a single parent cycle. The independently supplied, finite capture-skew budget may downgrade otherwise comparable contexts to `TIMING_SKEW`. Other states (`REPORTED_CLOSED`, `SESSION_UNKNOWN`, `EVIDENCE_INCOMPLETE`) remain visible in canonical market order. Explicit shared-source warnings are retained and deduplicated, not converted to assumed numerical correlations.

`ready_for_descriptive_comparison` denotes simultaneous descriptive context only; it is not trade eligibility or sufficient evidence to rank markets. `selected_market` remains None, `rankings` empty and all authority flags false. `validate_x9_comparison_safeguards_v1` recalculates from the original ledger and eligibility to detect falsely promoted stored results. Do not use it to replace the authoritative session calendar, risk policy or market-selector.
