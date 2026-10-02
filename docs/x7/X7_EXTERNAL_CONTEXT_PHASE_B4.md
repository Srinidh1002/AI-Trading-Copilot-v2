# X7-B4 — Consolidated external-context view and provenance replay

## Ownership and boundary

Offline Shadow X7 only; `services/x7/` owns the composition of **supplied** and
already-adapted X7-A/B1/B2/B3 evidence. This module does **not** fetch market
observations, authenticate upstream publishers, infer direction, score confidence,
place orders, set trading restrictions, mutate the session calendar, allocate
capital, affect production PAPER counters or issue independent votes. Every
new result retains immutable zero-authority fields (`data_only=True`,
`independent_vote=False`, all execution/risk/position/certification/live flags
`False`). No frozen Brain, X1–X6, or earlier X7 source file is modified.

## `X7SourceTraceV1` and `X7ResearchViewV1`

`build_x7_research_view_v1` requires an exact `X7GlobalBatchV1` and accepts
optional index-only `X7InstitutionalBatchV1` and `X7EventBatchV1`. All supplied
batches must have the same five-market identity, session, capture and aware
as-of time. Institutional batch evidence is prohibited for CRUDEOILM, GOLDM and
NATGASMINI; missing index cash flow is explicit and never invented.

The view contains the original immutable `X7ContextCaptureV1` and
`X7ContextValidationV1`; all three batch hashes; exact global, institutional
and event freshness budgets; source/fact identifiers; raw-record and
caller-proof SHA-256 hashes; observation, publication and availability instants;
fixed descriptive dependency groups; and a deterministic provenance manifest.
Unknown, partial, tentative, postponed, cancelled, stale and historical records
retain their original classifications. A source ID and source-record ID pair
cannot be reused as distinct evidence in one view. Shared publisher IDs are
explicitly grouped even when record IDs differ.

Global groups reuse the frozen B1 grouping for US equity closes, Asia equity
closes, GIFT index futures, crude benchmarks, FX context, bond yields and India
VIX. Institutional cash-equity dates form **one dependent family**, not several
independent votes. Calendar facts are grouped by exact event category. Shared
source IDs across groups are separately retained in `shared_source_groups`.
Neither grouping computes correlation coefficients nor estimates a scoring
weight. This is dependency disclosure, not statistical independence proof.

The X7-A validator is called with explicit freshness limits; no evidence family
is silently upgraded from `UNAVAILABLE` to `AVAILABLE`. For MCX, the missing
index-only institutional family means the current three-family validator cannot
return fully `AVAILABLE`; `PARTIAL` correctly describes the present scope.

## `replay_x7_research_view_v1`

Replay requires the view **and its separately retained expected SHA-256**, plus
the exact original normalized raw-record and caller-proof tuples and global
per-name age budgets. It invokes each original adapter, compares independently
recalculated batch digests, re-runs the original composition and validation,
and requires exact reconstructed-view equality and hash equality. An unexpected
source, missing/modified measurement, proof, expiry, schedule state, time,
market, budget, dependency or persisted-result change raises an error.

The independently retained expected hash must be recorded **outside** the
artifact being checked. A self-reported hash alone cannot detect an attacker
who rewrites both content and checksum. Internal replay also does not prove
publisher authenticity, source truth or true historical point-in-time access.
All replay inputs are caller-supplied; this module does not load persisted
files or download them.

`audit_x7_replay_timeline_v1` checks externally anchored view digests, rejects
repeated market/session/capture IDs and strictly non-increasing as-of times per
market, and records historical/unproven views separately. It verifies only an
**already-built view sequence**. Full raw/proof re-adaptation requires calling
`replay_x7_research_view_v1` for every view first.

## Testing and release gates

B4 tests cover five-market and controlled-global-name matrices, both index
markets, missing families, shared source and cross-family duplicate records,
provisional/absent institutional flow, retrospective point-in-time boundaries,
raw/proof/result tampering, budget and batch identity inconsistencies, ordered
multi-market replay, immutable zero-authority contracts, and blocked-import
static scans. Run X7-focused, combined Brain + X1–X7, and selected FYERS
compatibility regressions after local Ruff format/lint.

B4 does not certify real provider availability, correlation independence,
news truth, trading profitability, live execution or future PAPER trades. The
production PAPER worktree is untouched. X7 remains uncommitted until the B5
scoped inventory, authority audit and freeze.
