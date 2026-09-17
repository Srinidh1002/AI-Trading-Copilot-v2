# P6D-2A Three-target plan shell

Historical shell stage; see `P6D_THREE_TARGET_TRADE_PLAN.md` for final contract scope.
## Purpose
Immutable PAPER-only plan identity/status shell.
## Architectural boundary
No execution, broker, provider, or calculation dependency.
## Identity and provenance
Caller supplies IDs, aware timestamps, immutable provenance and JSON-safe metadata.
## Plan statuses
READY, BLOCKED, and NO_TRADE enforce minimal diagnostics.
## Market and direction
Canonical index identity, INDEX_OPTION, and BULLISH/BEARISH only.
## Confidence
All confidence uses 0–1.
## Diagnostics
Immutable, stripped, first-occurrence deduplicated tuples.
## Serialization and immutability
Frozen deterministic dict/JSON; semantic form excludes ID, evaluation time, and source timestamps.
## PAPER-only guarantees
Live execution is disabled.
## Deferred fields
No entry, stop-loss, targets, option contract, quantity, capital, costs, or expiry yet.
## P6D-2B handoff
Later work adds calculated plan groups.
