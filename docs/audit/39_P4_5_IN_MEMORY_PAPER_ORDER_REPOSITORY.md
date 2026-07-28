# P4-5 in-memory paper-order repository audit

## Scope

Created `services/paper/order_repository.py` and four focused repository test
modules. `services/paper/__init__.py` exports the explicit repository and its
bounded exceptions. No P4-4 execution path changed.

## Public API and invariants

`InMemoryPaperOrderRepository` stores only `PaperOrderStateV1`, copies records
at ingress/egress, returns tuples, and sorts snapshots by `created_at` then
`paper_order_id`. It prevents duplicate order IDs, execution-request IDs, and
non-null execution-result IDs. A standard-library `RLock` makes save, lookup,
listing, transition, count, and clear coherent and atomic.

The transition matrix is the existing contract graph: `CREATED → AUTHORIZED |
BLOCKED | FAILED`; `AUTHORIZED → SUBMITTED | BLOCKED | FAILED`; `SUBMITTED →
FILLED | REJECTED | CANCELLED | FAILED`. Existing linkage and trade fields
cannot change; later states may add contract-valid evidence only.

`PaperOrderStateV1` now requires exact canonical `underlying_symbol` and
`exchange` fields. Identity lookup filters those stored fields directly and
never derives an identity from a trading symbol.

## Certification commands and exact outputs

- Repository core: `105 passed in 0.67s`.
- Order-state contract: `99 passed in 0.74s`.
- Executor propagation: `140 passed in 0.82s`.
- Transitions: `71 passed in 0.65s`.
- Isolation/concurrency: `40 passed in 0.67s`.
- Four-index compatibility: `41 passed in 0.62s`.
- Combined P4-5: `257 passed in 0.90s`.
- P4-4 regression: `170 passed in 0.77s`.
- P4 regression: `660 passed in 1.54s`.
- Safety regression: `244 passed, 2 warnings in 1.78s`.
- Import check: `P4-5 identity imports passed`.
- Full repository: `5102 passed, 2 warnings in 15.65s`.

## Safety and certification

One test syntax defect in the newly added transition coverage was corrected
before certification. The identity-storage blocker is resolved. No execution-runtime defects were found. No persistence, provider, broker,
network, filesystem, credentials, automatic authorisation, automatic paper
execution, or live execution was introduced. Focused, regression, import, and
full-suite commands passed. The two SmartAPI TLS deprecation warnings remain
pre-existing. P4-5 is certified.
