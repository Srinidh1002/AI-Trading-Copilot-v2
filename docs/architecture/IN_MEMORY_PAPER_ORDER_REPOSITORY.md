# In-memory paper-order repository

P4-5 provides `InMemoryPaperOrderRepository`: an explicitly constructed,
process-local, thread-safe store for immutable `PaperOrderStateV1` records.
It does not execute, authorise, submit, replay, or persist an order.

## API and storage

The public operations are `save`, `get`, `get_by_execution_request_id`,
`contains`, `list_all`, `list_by_status`, `list_by_identity`, `transition`,
`count`, and `clear`.  `add` aliases `save`; `snapshot` aliases `list_all`.
Every ingress and egress is copied with `dataclasses.replace`; all list APIs
return tuples. Ordering is always `(created_at, paper_order_id)` ascending.

Order IDs and execution-request IDs are unique. Non-null execution-result IDs
are also unique. A duplicate replay never overwrites a record.

`PaperOrderStateV1` carries required canonical `underlying_symbol` and
`exchange` fields. `list_by_identity` resolves an omitted exchange only at its
public boundary and filters the stored canonical pair directly; it never
guesses identity from a trading symbol.

## Transitions and concurrency

Transitions use the contract's conservative graph: `CREATED` to
`AUTHORIZED`, `BLOCKED`, or `FAILED`; `AUTHORIZED` to `SUBMITTED`, `BLOCKED`,
or `FAILED`; and `SUBMITTED` to `FILLED`, `REJECTED`, `CANCELLED`, or `FAILED`.
Terminal states have no outbound transition. Compare-and-set uses
`expected_current_status` atomically and rejects stale state.

An `RLock` protects all maps, indexes, transition checks, listings, counts,
and clear operations. The repository has no worker, TTL, eviction, network,
provider, broker, database, filesystem, or credential access.

## Lifecycle and future work

Callers own the lifecycle and explicitly save a returned order state. There is
no hidden P4-4 pipeline integration and no automatic paper or live execution.
The four supported market identities remain available at the public identity
query boundary. P4-6 may add replay/observability integration; persistence is
explicitly out of scope.
