# P9 Final Certification Matrix

## Scope

P9 is the authoritative PAPER-only orchestration path for deterministic opportunity evaluation, PAPER lifecycle mutation, portfolio projection, persistence, restart recovery, and repeated runtime execution.

P9 closure does not add live execution or new trading logic. It certifies the existing P6, P7, and P8 authorities and their ordering.

## Locked authority chains

### New opportunity cycle

DATA → SESSION → ANALYSIS → OPPORTUNITY → P6_PLAN → P8_ADMISSION → P7_LIFECYCLE → P8_PORTFOLIO_UPDATE → immutable P9 cycle result → PERSISTENCE journal commit

### Existing-position monitoring cycle

P7_LIFECYCLE → P8_PORTFOLIO_UPDATE → immutable P9 cycle result → PERSISTENCE journal commit

### Outer idempotency boundary

journal classification → deterministic cycle execution → result validation → journal commit

### Continuous runtime boundary

startup recovery → opportunity coordinator → monitoring coordinator → wait → repeat

## Rejected authorities

P9 must not import or call live order executors, live order managers, live market engine authorities, broker order placement, legacy paper-engine fallbacks, Streamlit transition ownership, or alternate schedulers as orchestration authority.

A textual safety statement mentioning a rejected name is allowed. An import, symbol reference, attribute access, or executable call is not.

## Safety invariants

1. Execution mode is always `PAPER`.
2. `live_execution_eligible` is always `False`.
3. Identities are caller supplied or deterministically derived.
4. Authoritative orchestration does not place broker orders.
5. Missing, stale, invalid, or corrupt state fails closed.
6. Duplicate payloads do not repeat PAPER actions.
7. Idempotency payload conflicts fail closed.
8. P6, P7, and P8 retain sole authority over their domains.
9. P7 mutation occurs before P8 projection.
10. Persistence integrity is checked during recovery.
11. Startup recovery failure prevents runtime cycles.
12. One runtime operation failing does not suppress the other.

## Closure batches

| Batch | Certification focus |
|---|---|
| WP4-1 | authority matrix, exports, repository safety |
| WP4-2 | sequential opportunity and monitoring cycles |
| WP4-3 | restart, replay, duplicates, and conflicts |
| WP4-4 | multi-position and portfolio consistency |
| WP4-5 | corruption, failure isolation, and safety |
| WP4-6 | documentation reconciliation and final repository gate |

## Current certification baseline

Before WP4, the repository passed 14,266 tests with 0 failures and 2 pre-existing warnings.
