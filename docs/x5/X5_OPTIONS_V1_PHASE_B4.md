# X5-B4 — Historical replay and provenance audit (research only)

## Scope

`services/x5/replay_provenance_v1.py` consumes existing, immutable X5-A/B1/B2/B3 contracts. It has **no broker/SDK I/O, order submission, market selection, risk authority, PAPER certification authority, execution authority, portfolio writes, or feature votes**. It does not modify frozen B1–B4/X1–X4 or production R2.2.

It verifies chronological, same-contract, same-session replay and rebuilds X5 validation, analytics and the B3 research view from each captured snapshot at an explicit freshness budget. The stored source objects and per-row content must match the retained SHA-256 witness. An output record links to the preceding record digest. All analytics remain explicitly scoped to `CAPTURED_STRIKE_WINDOW`; no historical trade outcomes or inter-frame metric deltas are calculated.

## Public API

- `seal_x5_replay_frame_v1(capture=..., max_age_seconds=...) -> X5ReplayFrameV1`: constructs source validation, analytics and research view, plus capture/validation/analytics/view hashes and per-row hashes. Save the resulting witness independently of the payload immediately after genuine capture. This helper does **not** authenticate FYERS data or establish that flags supplied by a caller are true.
- `replay_x5_history_v1(frames=(...), max_age_seconds=..., max_step_seconds=...) -> X5ReplayResultV1`: accepts a nonempty immutable chronological tuple and re-evaluates every frame from its original observation data.
- `X5ReplayRecordV1`: immutable record of one checkpoint, its hashes, captured strike-window hash, `FIRST_FRAME`/`SAME_WINDOW`/`WINDOW_CHANGED`, historical availability classification, original nine-metric research availability and chain link.
- `X5ReplayResultV1`: immutable aggregate of records and counts, with a deterministic digest; no trade/action/score/independent-vote fields.

## Fail-closed checks

1. Market, underlying provider identity, option exchange, expiry, contract metadata, and session remain unchanged within one replay. **Expiry rolls and new sessions require new replay sequences**, not silently merged histories.
2. Checkpoints must be strictly increasing and within the caller's explicit `max_step_seconds` gap allowance, within one local IST session date. Duplicate capture and source IDs fail.
3. Each recorded content and row hash must match the expected frozen witness. Reuse of a source-record ID with different content fails. A shared strike/CE-PE contract cannot switch canonical ID/provider symbol during one replay.
4. Original X5 validation is recomputed with the *same explicit* freshness policy; analytics and the research projection are recomputed, and any divergence from the stored version fails.
5. The entire set of CE and PE observation keys `(strike, option_type)` defines the captured window. Additions, removals, and replacements change its digest and produce `WINDOW_CHANGED` + `NON_COMPARABLE_STRIKE_WINDOW`; no synthetic strikes, interpolation, exchange-wide extrapolation or inter-frame delta comparison is provided.
6. Retrospective retrieval (`historical_retrieval=True`) and any unproven point-in-time availability remain flagged as **unproven**; the earlier X5 validation prevents such captures from contributing available metrics. A source timestamp by itself is not proof that the provider made data available at that historical time.
7. The replay result validates its own chronological record-hash links, record counts and exact disabled-authority flags. It is descriptive and cannot update PAPER journals or certification counters.

## Provenance and operational limitations

- SHA-256 detects changes **relative to a separately retained trusted witness**. An attacker able to rewrite both data and the witness can create matching hashes; digest equality is not a digital signature, provider authentication, chain-of-custody guarantee or independent validation of declared units.
- An in-memory `seal_x5_replay_frame_v1` call creates a self-consistent witness, not independent FYERS proof. Never reseal a suspicious capture to make it pass. Capture authenticity and prior availability require external corroboration.
- X5-B1 requires explicit evidence for expiry bindings and per-row timestamps. B1 does not independently verify historical availability, units, OI-change semantics, IV or Greeks. B4 does not lift these restrictions.
- `point_in_time_verified=True` is an *input claim* from separately verified source evidence, not something B4 can independently establish.
- OI/volume, quote units, IV and Greeks are still governed by upstream validation; B4 never upgrades unavailable metrics.
- A stable captured strike window is **necessary but not sufficient** for economic comparability (underlying price, market conditions and depth may change). Accordingly `cross_frame_metric_comparison_allowed=False` even for `SAME_WINDOW`.
- Tested with deterministic offline fixtures across NIFTY, SENSEX, CRUDEOILM, GOLDM and NATGASMINI. These tests do not certify live FYERS connectivity, execution readiness or any trading performance.

## Development gates

- Offline X5 A+B1+B2+B3+B4 focused tests.
- Scoped Ruff format and lint check on `services/x5/` and `tests/test_x5_*.py`.
- Selected combined `test_(brain|x1|x2|x3|x4|x5)_*.py` regression.
- Existing FYERS resolver/provider/SDK/bridge test compatibility regression.
- Final B5 read-only source and authority audit, then an exact-file-list Git commit on `x23-shadow-features-v2`. Production PAPER worktree remains unchanged.
