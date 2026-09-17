# Deterministic paper executor

`execute_paper_order` is an explicit paper-only API accepting
`PaperExecutionRequestV1`, an `AUTHORIZED` `PaperAuthorizationResultV1`, an
optional `InMemoryPaperExecutionIdempotencyStore`, clock, and result-ID factory.
It returns only `PaperExecutionResultV1`.

Validation order: input types; timezone-aware time; usable authorization;
request validity window; exact authorization/request linkage and identity;
optional idempotency lookup; deterministic full fill; successful claim.

The fill is immediate and full: requested/filled quantity and lots equal the
request; reference/fill price equal entry price; capital used is price ×
quantity; maximum loss is `(fill_price - stop_loss_price) × quantity`.
BUY/CALL/LONG and SELL/PUT/LONG remain the only directions.

With a store, the first successful key fills and a repeated key returns
`DUPLICATE` without fill evidence. With no store, execution remains deterministic
but cannot provide cross-call exactly-once protection. There is no persistence,
order-state lifecycle, retry, partial fill, slippage, broker/provider, legacy
executor, network, filesystem, database, credential, or live-execution path.
P4-4 will orchestrate; P4-5 will own lifecycle state.
