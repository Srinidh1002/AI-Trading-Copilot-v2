# PositionSizeResultV1

`PositionSizeResultV1` is an immutable, deterministic record for a future
P3-5 sizing calculation. An `APPROVED` result must carry complete validated
sizing data but always has `execution_eligible=False`. Non-approved results may
represent honest absent sizing values with blockers.

For non-approved outcomes, selected-contract identifiers and related identity
fields may be `null` when validation stopped before a complete trade-plan
identity existed. `APPROVED` results continue to require complete identity.

Non-approved outcomes may also preserve a non-actionable `WAIT` action with
`option_type=null`. `WAIT` cannot carry a fabricated CALL or PUT; approved
results remain limited to BUY/CALL and SELL/PUT.
