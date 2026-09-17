# P10-WP3 — Publication Design

## Required invariants

- PAPER-only
- immutable publication envelope
- caller-supplied identity
- caller-supplied timestamps
- deterministic projection
- exact typed sources
- no direct Streamlit dependency
- no direct persistence dependency
- no business computation
- no clearing last-known-good state on failure

## Publication statuses

Recommended values:

- `READY`
- `READY_WITH_WARNINGS`
- `NO_ACTION`
- `BLOCKED`
- `STALE`
- `FAILED_ATTEMPT_PRESERVED`

The envelope itself represents coherent published state. Failed attempts belong
in store attempt metadata and must not replace the last valid envelope.

## Freshness statuses

Recommended values:

- `FRESH`
- `STALE`
- `UNKNOWN`

Freshness is supplied or evaluated using an injected caller clock.

## Identity coherence

When multiple views are present:

- opportunity identity must match the plan selected opportunity
- plan identity must match the P7 trade plan identity
- market identities must agree when present
- PAPER-only flags must agree
- source timestamps must be timezone-aware

## No-data behavior

An empty store is valid.

Streamlit should continue rendering explicit no-data states until the first
coherent publication arrives.

## Duplicate behavior

Equivalent duplicate publication attempts must not:

- increment semantic publication state unnecessarily
- clear diagnostics
- reorder source evidence
- generate new trading values

Attempt counters may still record the duplicate attempt.

## Failure behavior

Projection failure must:

- record attempt failure
- preserve the previous envelope
- preserve the previous sequence
- expose the failure diagnostically
- never publish partial values

## Thread ownership

Runtime and dashboard may operate on different threads.

The publication store must provide atomic:

- `publish`
- `record_failure`
- `get_snapshot`
- `reset`

No method may expose mutable internal state.
